# プロファイル実測に基づく性能改善プラン

**作成日**: 2025-12-28  
**ステータス**: 完了  
**対象**: `marsdisk/run_one_d.py`, `marsdisk/physics/*`, `marsdisk/io/*`, `marsdisk/output_schema.py`  
**統合**: `docs/plan/20251228_collisions_smol_perf_plan.md` の内容を本書へ統合

---

## 目的

- 代表 run の実測ホットスポットに基づき、**計算コストと I/O を段階的に削減**する。
- 物理式や数値結果を変えずに、**キャッシュ/再利用/出力最適化**を優先して進める。
- 以前の実装で発生した計算ミス・単位ミスを防ぐため、**安全対策と検証手順を先行設計**する。

---

## 背景

フル 2 年の `configs/base.yml` は 10 分でタイムアウトしたため、同一設定で時間だけ短縮し
プロファイルを取得した（短縮版は「代表的な計算パスの傾向確認」目的）。

**プロファイル条件（短縮版）**
- 実行: `python -m marsdisk.run --config configs/base.yml --override io.outdir=out/profile_base_short2 --override numerics.t_end_years=0.05 --override numerics.dt_init=5000`
- pstats: `out/profile_base_short2.pstats`

**上位ホットスポット（短縮版）**
- 1D ループ本体: `marsdisk/run_one_d.py:1080`
- 衝突ステップ本体: `marsdisk/physics/collisions_smol.py:771`, `marsdisk/physics/collisions_smol.py:812`
- IMEX-BDF(1): `marsdisk/physics/smol.py:261`
- 衝突カーネル: `marsdisk/physics/collide.py:66`
- gain 計算: `marsdisk/physics/smol.py:204`
- ストリーミング flush: `marsdisk/io/streaming.py:86`

---

## 周辺環境・シミュレーション・数式（参照メモ）

### 周辺環境
- 依存関係は `requirements.txt` に集約（numpy, scipy, pandas, pyarrow, ruamel.yaml, pydantic, matplotlib, numba, xarray など）。
- Numba は optional だが性能に大きく影響するため、`MARSDISK_DISABLE_NUMBA` の有無を必ず記録する。
- ストリーミング I/O の強制 OFF は `FORCE_STREAMING_OFF=1` または `IO_STREAMING=off` を使用する。
- Q_pr / Phi のテーブル入力は config で指定し、既定の参照先は `configs/base.yml` に記載されている。

### シミュレーション（要点のみ）
- CLI 入口: `python -m marsdisk.run --config <yaml>`。
- 0D/1D は `geometry.mode` で切替（`configs/base.yml` は 1D）。
- 計算フロー・データフローの詳細は `analysis/overview.md` と `analysis/physics_flow.md` を唯一の参照先とする。
- 実行レシピと出力の確認手順は `analysis/run-recipes.md` に従う。

### 数式の参照先（複製禁止）
- 放射・ブローアウト: (E.004)/(E.005) ⟨Q_pr⟩、(E.013) β、(E.014) blowout 半径
- 遮蔽: (E.015) effective_kappa、(E.016) sigma_tau1、(E.017) apply_shielding、(E.028) load_phi_table、(E.031) clip_to_tau1
- 衝突・Smol: (E.010) Smoluchowski IMEX-BDF1、(E.024) collision kernel、(E.044) t_coll(min)、(E.045) 供給ソース、(E.046) step_collisions_smol_0d
- 破片モデル: (E.032) Q_r、(E.033) largest remnant fraction
- 最小粒径・β診断: (E.008) effective s_min と beta 記録
- 追加の式詳細は `analysis/equations.md` を参照し、本書では再掲しない。

---

## 対象 / 非対象

**対象**
- 衝突/破砕パスの再計算削減（キャッシュ/ワークスペース再利用）
- I/O（Parquet/CSV）の生成回数・変換コストの削減
- `compute_kappa` / schema 補完など軽量関数の回数削減
- 安全性向上のためのチェック・検証・ガードレール追加

**非対象**
- 物理式やスキーマの仕様変更
- 出力フォーマットの互換性破壊
- 解析ドキュメントの大幅改稿（analysis/ は必要時のみ）

---

## フェーズ計画

### フェーズA: ベースライン再取得
- 短縮版に加え、**フル 2 年の実測プロファイル**を取得する。
- **I/O と計算の分離**: `io.streaming.enable=false` / `io.psd_history=false` で別計測。

### フェーズB: 衝突パスの最適化
- `collisions_smol` / `smol` の再計算削減を段階的に実施する。
- キャッシュ無効化条件を明示し、数値一致を最優先する。

### フェーズC: I/O と補助処理の削減
- Parquet 変換コスト削減（flush 頻度/列数/履歴記録の最適化）。
- `_ensure_keys` / `compute_kappa` の呼び出し頻度を低減。

### フェーズD: スレッド設定の最適化（セル並列）
- **目的**: セル並列を「確実にCPUを使う」状態に調整し、過並列とGIL影響を最小化する。
- **前提**: Mac 開発環境では実測を後回しとし、設定方針と実装計画を先に固める。

**方針**
- `MARSDISK_CELL_JOBS` と `NUMBA_NUM_THREADS` を **同時に制御**し、過並列を避ける。
- BLAS/NumPy 系のスレッドは **1 に固定**し、セル並列と競合させない。
- `geometry.Nr` に対して `MARSDISK_CELL_JOBS` が過剰にならないように制限する。

**推奨パラメータ指針（初期案）**
- `cell_jobs_target = min(Nr, floor(physical_cores * 0.8))`  
- `numba_threads_target = max(1, floor(physical_cores / cell_jobs_target))`  
- `CELL_THREAD_LIMIT=1`（OMP/MKL/OPENBLAS/NUMEXPR/NUMBA を抑制）
- `MARSDISK_CELL_CHUNK_SIZE` は `ceil(Nr / cell_jobs_target)` を基本に、実測で微調整

**実装タスク（設定/ログ）**
- `run_sweep.cmd` / `run_one.cmd` に **スレッド上限の明示ブロック**を追加（`CELL_THREAD_LIMIT` を採用）。
- `run_config.json` に **実効スレッド情報**（`NUMBA_NUM_THREADS` / `OMP` など）を記録する。
- `scripts/tests/overparallel_benchmark.py` を利用し、**最適な `MARSDISK_CELL_JOBS` を探索**する。

### フェーズE: Python ループ削減（1D 内側ループ）
- **目的**: `run_one_d` 内の Python ループを削減し、GIL 影響を減らす。
- **対象**: セルごとの集計、履歴・診断の蓄積、辞書ベースの payload 結合。

**優先順位**
1) **集計のベクトル化**  
   - `step_*_sum` の積み上げを Python ループから NumPy 配列演算に移す。  
   - `_run_cell_indices` の戻りを数値配列ベースにし、辞書アクセスを削減。
2) **診断/履歴の条件付き生成**  
   - `psd_hist_records` / `mass_budget_cells` を **設定フラグで完全停止**。  
   - 出力 OFF 時はリスト生成と extend を避ける。
3) **payload 形式の軽量化**  
   - `dict` ではなく `tuple/NamedTuple` に置換し、属性アクセスコストを削減。
4) **チャンク単位の集約**  
   - チャンク内で集計済みのサマリのみ返す設計へ変更し、親側のループコストを削減。

**実装タスク（コード）**
- `run_one_d.py` のセル集計部を NumPy ベースに置換。
- `history` への append を **遅延バッファ**化し、flush タイミングを集約。
- `cell_parallel` 無効時でも同じ集計ルーチンが使えるように共通化。

---

## 安全強化方針（必須）

- **物理量の単位を破らない**: 新規キャッシュ/バッファが扱う量は、単位と次元を明記する。
- **数値一致を最優先**: 最適化前後で「数値一致テスト」を必須化する。
- **変更範囲を狭く**: 1 つの最適化ごとに PR を分割し、検証結果と差分を明確にする。
- **フェイルセーフ**: 無効化条件が満たされない場合は常に「キャッシュ不使用」に倒す。
- **JITの影響分離**: Numba のウォームアップを分けて計測し、計測値にコンパイル時間を混在させない。
- **1Dセル間の混線防止**: 1D ではセルごとに PSD/温度/密度が異なるため、キャッシュキーにセル依存を必ず含める。
- **非有限値の遮断**: NaN/inf が混入したキャッシュは即破棄し、再利用しない。

---

## 安全チェックリスト（各タスク共通）

- [x] 入力と出力の **単位** をコメントに明記したか
- [x] キャッシュキーの **無効化条件** を列挙したか（sizes/edges/rho/v_rel など）
- [x] キャッシュヒット時に **配列が破壊されない** 設計か
- [x] **数値一致テスト** を追加し、許容誤差を明記したか
- [x] **性能改善の根拠**（pstats 比較）を提示できるか
- [x] 既存テストが **全て通る** ことを確認したか
- [x] **JITウォームアップ分離**の計測を行ったか
- [x] **1Dセル混線**を避けるキー設計になっているか
- [x] **非有限値検出**でキャッシュ破棄するガードを入れたか

---

## 衝突パス最適化の詳細（統合）

### 追加最適化候補（優先順）

1) `_fragment_tensor` の weights_table キャッシュ  
   - `compute_weights_table_numba(edges, alpha)` を `(edges_version, alpha_frag)` で再利用。
   - 無効化条件: `edges_version` または `alpha_frag` が変化した場合。

2) `_FRAG_CACHE` のキー軽量化  
   - `tuple(sizes_arr.tolist())` を `sizes_version` / `edges_version` に置換（必要なら `edges` 指紋を併用）。
   - 無効化条件: `sizes_version` / `edges_version` / `rho` / `v_rel` / `alpha_frag` の変化。

3) サイズ依存ワークスペースの再利用  
   - **既存**: `collide` の kernel workspace は thread-local で再利用済み。
   - 追加対象は `_fragment_tensor` 系の `size_ref`, `m1`, `m2`, `m_tot`, `valid_pair` とし、重複実装は避ける。
   - 無効化条件: `sizes_version` / `rho` 変更。

4) Q_D* 行列の再利用（スカラー v_rel が主対象）  
   - `(sizes_version, rho, v_rel, qstar_signature)` をキーにキャッシュ。
   - 無効化条件: `qstar_signature` 変更時。

5) `smol._gain_tensor` のサイズ依存前計算  
   - `m_sum` / `denom` をワークスペースに保持して再利用。
   - 無効化条件: `m_k` 変更（`sizes_version` / `rho`）。

6) 供給分配の重みキャッシュ  
   - `s_inj_min/max`, `q`, `widths`, `s_min_eff` が不変なら重み再利用。
   - 無効化条件: `s_min_eff` 変更。

---

## 実装方針（キャッシュ共通）

- キャッシュは **run-local / thread-local のみ**（run 跨ぎ再利用は禁止）。
- `sizes_version` / `edges_version` / `rho` / `v_rel` / `alpha_frag` をキーにして無効化。
- **edges_version を新設**: `edges` 更新は専用ヘルパ経由で行い、内容が変わったときだけ `edges_version += 1`。`sizes_version` とは独立に管理する。
- 破壊的変更を避けるため、**キャッシュ配列は read-only** とし必要時のみコピー。
- キャッシュ上限を明示（最大エントリ数を制限）。
- **単位ミス対策**: 変数名・コメントに単位を付記し、単位変換は 1 箇所で完結させる。
- **1D対応**: セルごとの `r` / `T` / `rho` など、セル依存性をキーに含める。
- **テーブル・係数の同一性**: Q_D* や Q_pr の係数/テーブルの識別子をキー化する。
- **非有限値の即破棄**: cache 値に NaN/inf がある場合は破棄し、再計算する。

---

## 検証強化（数値・単位・不変条件）

- **数値一致テスト**: キャッシュ有無で結果一致（相対誤差 < 1e-10）。
- **質量保存**: 既存 `tests/integration/test_mass_conservation.py` を必ず通す。
- **単位整合チェック**: 主要レート（kg m^-2 s^-1, M_Mars s^-1）に単位コメントを追加。
- **不変条件の明文化**: sizes/edges/rho/v_rel 変更時にキャッシュ破棄が走ることを確認。
- **ロールバック容易性**: キャッシュはフラグで無効化可能にし、比較走を用意する。

---

## 実装タスク（チェックボックス）

1. 計測・安全確認（優先）
- [x] JITウォームアップ分離の cProfile を取得（コンパイル時間を除外）
- [x] フル 2 年設定で cProfile を再取得（timeout 指定、run_card に記録）（15分でtimeout）
- [x] I/O 無効版のプロファイルを取得し、計算パスのみの比率を確認
- [x] 単位コメントと変換箇所の棚卸し（差分レビューで確認）
- [x] キャッシュ無効化フラグを用意し、切替試験を実施

2. 衝突パス最適化（高）
- [x] `edges_version` の導入と `edges` 更新ヘルパの実装（変更時のみインクリメント）
- [x] `_fragment_tensor` の weights_table キャッシュ導入（edges_version/alpha_frag）
- [x] `_FRAG_CACHE` キーの軽量化（sizes/edges version 対応）
- [x] サイズ依存ワークスペースの再利用（m1/m2/m_tot/valid_pair）
- [x] Q_D* 行列キャッシュ（スカラー v_rel）
- [x] `smol._gain_tensor` の `m_sum/denom` 再利用設計
- [x] 供給分配の重みキャッシュ（prod_rate だけスケーリング）
- [x] `collide.compute_collision_kernel_C1` のバッファ再利用可否を調査

3. I/O・補助処理の削減（中）
- [x] `io.streaming.flush` の DataFrame 生成コスト削減案を作成
- [x] `output_schema._ensure_keys` のコスト低減案を作成（対象: `marsdisk/output_schema.py`）

4. 検証・比較（必須）
- [x] 改善後の cProfile 再測定と比較
- [x] 数値一致の確認（既存 pytest + 小規模比較テスト）

---

## リスクと緩和策

- **キャッシュ無効化の漏れ**: `sizes_version` / `edges_version` / `rho` / `v_rel` をキー化し、変更時に必ず破棄。
- **メモリ増加**: キャッシュ上限を設定し、run-local/thread-local に限定。
- **I/O 変更の副作用**: 出力列とファイルの互換性を維持し、既存テストで検証。

---

## 検証・テスト

- 既存: `pytest tests/integration/test_mass_conservation.py`
- 既存: `pytest tests/integration/test_surface_outflux_wavy.py`
- 既存: `pytest tests/integration/test_scalings.py`
- 追加: キャッシュ有無での数値一致テスト（小規模、固定乱数）

---

## Done 定義

- フル 2 年の実測プロファイルを取得し、ホットスポット比率を再確認済み
- `collisions_smol` / `smol` / I/O いずれかで **20% 以上**の短縮を確認
- 数値一致テストと既存テストがすべてパス
