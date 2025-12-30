# 1D 性能改善プラン（セルループ中心）

**作成日**: 2025-12-30  
**ステータス**: 提案中  
**対象**: `marsdisk/run_one_d.py`, `marsdisk/physics/collisions_smol.py`, `marsdisk/physics/smol.py`, `marsdisk/output_schema.py`, `marsdisk/io/streaming.py`

---

## 目的

- 1D 実行の wall-time を短縮し、特に Python ループの負荷を下げる
- 物理結果・出力互換・テスト結果は維持する
- 既存の改善プランと整合させ、重複実装を避ける

---

## 背景（短縮プロファイルの傾向）

1D 実行では、セルループ本体と衝突/Smol の計算が主なホットスポットとなっている。  
I/O と dict 生成も目立つため、**Python ループ削減 + I/O 抑制**を優先する。

主なホットスポット（例）:
- `marsdisk/run_one_d.py` セルループ本体
- `marsdisk/physics/collisions_smol.py` 衝突ステップ
- `marsdisk/physics/smol.py` IMEX-BDF(1) と gain 計算
- `marsdisk/output_schema.py` のキー整備
- `marsdisk/io/streaming.py` の flush

---

## テスト結果反映（/Volumes/KIOXIA/tests, 2025-12-30）

### セル並列の速度比較

`cell_parallel_speed_20251230-170512` の結果では、**セル並列 ON が遅い**。

- `cell_parallel_on`: 14.74s（jobs=4, Nr=32, NUMBA_NUM_THREADS=1）
- `cell_parallel_off`: 6.39s
- `speedup_off_over_on`: 0.433（並列が約 2.3x 遅い）

結論: **小規模セル数では並列のオーバーヘッドが支配的**。  
セル並列は既定 OFF の維持と、有効化条件の厳格化が必要。

### Python ループのプロファイル

`python_loop_profile_20251230-170755`（internal time, 上位抜粋）:

- `run_one_d.py:_run_cell_indices` が最大（tottime 0.871s, cum 3.998s）
- `collisions_smol.step_collisions_smol_0d` / `smol.step_imex_bdf1_C3` が続く
- `psd.compute_kappa` と `output_schema._ensure_keys` の繰り返しが目立つ
- pandas/pyarrow 変換（DataFrame 生成、write_table）が上位に残る

結論: **セルループ本体の Python オーバーヘッド削減が最優先**。  
I/O と記録生成の縮退も同時に効く。

## 非スコープ

- 物理モデル変更・新式導入
- 0D の性能改善
- 出力フォーマットの互換性破壊
- 既存の分析ドキュメント（analysis/）の改稿

---

## 実装前の注意点（必須）

- **出力スキーマの維持**: `marsdisk/output_schema.py` のキーは必ず出力に揃える。`_ensure_keys` を削減する場合は「書き出し直前に補完」を徹底し、`tests/integration/test_run_one_d_output_parity.py` と `tests/integration/test_run_one_d_streaming_schema.py` の前提を崩さない。
- **psd_hist / mass_budget_cells の契約**: `io.psd_history` が OFF でない限り `series/psd_hist.parquet` を出力すること。`mass_budget_cells` は現状常時 ON のため、無効化フラグを導入する場合は `marsdisk/schema.py` とテスト更新が必須。
- **ストリーミング ON/OFF の整合**: `checks/mass_budget.csv` / `checks/mass_budget_cells.csv` は両モードで必ず生成し、列集合が一致することを維持する。
- **セル並列設定の更新はテストとセット**: `_resolve_cell_parallel_config` を変更する場合は `tests/unit/test_cell_parallel_config.py` と `run_config.json` の `cell_parallel` 仕様整合を同時に更新する。
- **キャッシュのスコープ制約**: thread-local/run-local に限定し、`MARSDISK_DISABLE_COLLISION_CACHE` / `MARSDISK_DISABLE_NUMBA` を尊重する。セル間混線の可能性がある共有バッファは禁止。

---

## 改善方針

### A. セルループの Python オーバーヘッド削減

- `_run_cell_indices` の **戻り値を dict から構造化データへ**切替（tuple/NamedTuple）
- ステップ集計値を **NumPy 配列で保持し、最後に合算**
- 各セルでの dict 生成（record/diagnostics）を **必要時のみ有効化**

### B. 出力レコード生成の縮退

- `psd_hist_records` と `mass_budget_cells` は **フラグ OFF 時に生成を完全スキップ**
- 生成する場合でも、**リストの append 回数を最小化**
- `output_schema._ensure_keys` の呼び出し頻度を抑え、出力直前に集中処理

### C. 衝突/Smol パスの再計算削減

- 1D セル内で `ImexWorkspace` / kernel workspace を再利用
- `sizes_version` / `edges_version` / `rho` 変化時のみキャッシュを更新
- Numba 無効時のフォールバック経路が走らないよう、環境設定を明確化

### D. I/O の最小化

- `io.streaming.enable=false` の軽量比較ケースを標準化
- flush 間隔と記録対象列を **計測用途に応じて切替**

### E. セル並列の有効条件見直し

- `Nr` と `jobs` に応じて **自動で無効化**（小規模では OFF）
- `chunk_size` の自動設定を見直し、**過細分割を避ける**
- 有効/無効の判定理由を `run_config.json` に記録

---

## 優先度（即効性順）

### 高

- 衝突・破片生成の再計算/再割当を削減  
  `marsdisk/physics/collisions_smol.py` の `_fragment_tensor` / `step_collisions_smol_0d` を中心に、  
  フラグメント用配列と作業領域を **pre-alloc + fill(0)** で再利用し、`numpy.zeros` の乱発を抑える。  
  `sizes/rho/v_rel/alpha` が不変なら **Q_D* 行列**と**フラグメント分配重み**をキャッシュ。

- Q_D / q_r / LRF の計算回数削減  
  `marsdisk/physics/qstar.py` の `compute_q_d_star_array` / `_q_d_star` の再評価を削減。  
  セルごとに同じ入力で毎ステップ呼ぶ場合はキャッシュし、**入力変化時のみ再計算**する。  
  併せて `q_r` / `largest_remnant_fraction` の中間行列も再利用する。

- 衝突カーネルと gain 計算の事前計算  
  `marsdisk/physics/collide.py` / `marsdisk/physics/smol.py` の kernel と gain の固定項を  
  **サイズバージョン単位で再利用**し、`m_sum` / `denom` などのワーク配列を使い回す。

### 中

- Python ループ・辞書変換の削減  
  `marsdisk/run_one_d.py` の `_run_cell_indices` で **dict → 配列/tuple** 化し、  
  `construction.convert` / `_list_of_dict_to_arrays` の負担を避ける。

- 診断・スキーマ補完の条件化  
  `marsdisk/output_schema.py` の `_ensure_keys` を **必要時のみ実行**し、  
  診断/履歴が不要なモードでは完全スキップする。

---

## 実装タスク（案）

0) セル並列の有効条件を再調整
- [x] `Nr` と `jobs` による **自動無効化条件** を追加
- [x] `chunk_size` の算出式を見直し（小規模時は単一チャンク）
- [x] 無効化理由を `run_config.json` に記録

1) 1D セルループ再設計
- [x] `_run_cell_indices` の出力を tuple 化（records/diagnostics は optional）
- [x] ステップ集計値を NumPy 配列化して `sum` を削減
- [ ] `step_records` の `t_coll_kernel_min` 付与を **ベクトル的に実施**（可能なら）

2) 出力経路の縮退
- [x] `psd_hist_records` は `io.psd_history=false` の場合のみ停止
- [x] `mass_budget_cells` を止める場合は **新フラグ追加＋schema/pytest 更新が前提**
- [x] `output_schema._ensure_keys` の呼び出し回数を削減
- [x] `writer.append_csv`/`write_parquet` 直前に必要キーを補完

3) 衝突/Smol ループの再利用
- [x] `ImexWorkspace` を 1D 各セルで再利用
- [x] kernel workspace をセル単位で持ち回し
- [x] Numba の有効/無効を `run_config.json` に記録

4) 計測の整備
- [x] 短縮ケース + I/O オフのプロファイルを定型化
- [x] 改善前後で pstats と wall-time を比較

---

## 検証計画

- **数値一致**: 既存テスト（mass_budget/PSD/wavy）を維持
- **再現性**: 並列 OFF 条件で `summary.json` の差分が許容誤差内
- **性能**: 短縮ケースで 20% 以上の改善を確認
- **セル並列**: `Nr` 小規模では OFF が高速であることを確認し、  
  大規模セル数でのみ ON の改善を評価する
- **出力整合**: `tests/integration/test_run_one_d_output_parity.py` と `tests/integration/test_run_one_d_streaming_schema.py` を必ず通す
- **mass_budget_cells**: `tests/integration/test_mass_budget_cells.py` を必ず通す

---

## リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| 生成レコードの欠落 | 出力差分 | 生成条件を明示し、ON/OFF を run_config に記録 |
| キャッシュ誤再利用 | 数値不一致 | sizes/edges/rho でキー無効化 |
| Numba 無効化 | 速度低下 | 実行ログにスイッチを記録 |
| スキーマ不整合 | テスト失敗 | 書き出し直前のキー補完で列集合を固定 |
| mass_budget_cells 欠落 | テスト失敗 | ON/OFF を導入するなら schema/pytest を同時更新 |

---

## 関連プラン

- `docs/plan/20251228_profile_hotspots_improvement_plan.md`
- `docs/plan/20251224_cell_loop_parallelization_plan.md`
- `docs/plan/20251219_qpr_vectorization_and_collision_perf.md`

---

## 受入基準

- 1D 短縮ケースの wall-time が 20% 以上短縮
- `summary.json` と `checks/mass_budget.csv` が許容差内
- 既存 pytest が全てパス
- 小規模セル数ではセル並列が自動で無効化される
