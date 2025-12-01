目的火星ロッシュ限界内の高密度ダスト円盤を対象に、

> **For AI Agents**: Before starting any task, you MUST read `analysis/AI_USAGE.md`. It contains critical protocols for handling references (`UNKNOWN_REF_REQUESTS`), documentation standards, and automated verification workflows. Failure to follow these protocols will result in rejected work.
* 内部（破砕のみSmoluchowski）で生成されるblow‑out未満の小粒子供給（式：C1–C3, P1, F1–F2, D1–D2）と、
* 表層（剥ぎ取り）での放射圧による剥離・流出（式：R1–R3, S0–S1）、を2年間カップリングして**$\dot M_{\rm out}(t)$ と $M_{\rm loss}$を定量化するシミュレーションを、新規リポジトリ構造で実装してください。先行研究の式を明示採用し、必要拡張（赤外光源・光学的厚さ・非定常PSD）以外は新式を導入しない**でください。
完成条件（必須の動作）
1. CLI: python -m marsdisk.run --config configs/base.yml で**0D（半径無次元）**が完走。
2. 出力:
    * 言語 必ず日本語で回答してください
    * 時系列 out/series/*.parquet：$\dot{\Sigma}^{(<a_{\rm blow})}{\rm prod}(t)$, $\dot M{\rm out}(t)$, 主要スカラー。
    * 集計 out/summary.json：2年間の $M_{\rm loss}$ と感度掃引の表。
    * 検証 out/checks/mass_budget.csv：質量保存（C4）のログ（|誤差| < 0.5%）。
3. ユニットテスト（pytest）
    * Wyattの衝突寿命スケーリング（$t_{\rm coll}!\approx!T_{\rm orb}/(4\pi\tau)$）のオーダー一致
    * Blow‑out即時消滅による**“wavy” PSDの定性的再現**
    * IMEX（loss陰・gain陽）で安定、$\Delta t\le 0.1\min t_{{\rm coll},k}$ で収束
4. YAMLで物理スイッチ（昇華・ガス抗力・自遮蔽倍率・wake係数など）を外出し。
技術選定と依存
* Python 3.11+, numpy, scipy, numba(任意), pydantic, ruamel.yaml, pandas, pyarrow, xarray(任意), matplotlib(検証用プロット)
* Mie平均$\langle Q_{\rm pr}\rangle$はテーブル読み込みを基本（CSV/NPZ）。ライブラリ（例：miepython）があれば生成ユーティリティも用意。
* 多層RTの自遮蔽係数$\Phi(\tau,\omega_0,g)$もテーブル入力＋双線形補間をデフォルト。

## ガス希薄（gas‑poor）前提と TL2003 トグル方針
- 火星ロッシュ限界内の衝突円盤は溶融物主体で蒸気成分が概ね **≲数%**、初期公転で揮発が急速に散逸するため **gas‑poor** 条件を標準とする（Hyodo et al. 2017; 2018）。  
- Phobos・Deimos を残すには低質量・低ガスの円盤が要ると報告されており、厚いガス層を伴うシナリオは既定の解析対象外とする（Canup & Salmon 2018）。  
- [無効: gas‑poor 既定] **Takeuchi & Lin (2003)** は光学的に厚い**ガス**円盤の表層塵アウトフローを仮定するため、標準設定では**適用しない**。`ALLOW_TL2003=false` をデフォルト値とし、gas‑rich 想定の感度試験でのみ明示的に `true` へ切り替える。  
- ガス希薄ディスクの放射圧・PRドラッグ支配の描像としては Strubbe & Chiang (2006) を参照する。総説整理は Kuramoto (2024)。

**参考**: Hyodo et al. 2017; 2018／Canup & Salmon 2018／Takeuchi & Lin 2003／Strubbe & Chiang 2006／Kuramoto 2024

リポジトリ構成
marsdisk/
  configs/
    base.yml
    sweep_example.yml
  marsdisk/
    __init__.py
    constants.py
    grid.py                  # 0D/1Dラッパ、Ω(r), vK(r)
    io/
      __init__.py
      writer.py              # parquet/json出力
      tables.py              # Mie/Qpr, Phi テーブル I/O
    physics/
      radiation.py           # R1–R3: Q_pr 平均, β, a_blow
      shielding.py           # S0: Φ(τ,ω0,g) 適用とΣ_τ=1クリップ
      dynamics.py            # D1–D2: 速度分散の自己調整 c_eq
      qstar.py               # F1: Q_D*(s), LS12補間
      fragments.py           # F2 + 破片分布（α, 最小size境界）
      psd.py                 # P1 + 3スロープ + "wavy"補正
      collide.py             # C1–C2: C_ij, 生成フラックス
      smol.py                # C3–C4: IMEX-BDF(1)実装, 質量検査
      surface.py             # S1: 表層ODE, 剥ぎ取り率
      sinks.py               # 昇華・ガス抗力など追加シンク
      viscosity.py           # C5(任意): 半径1D拡散(演算子分割)
    run.py                   # 全体オーケストレータ/CLI
    validate.py              # 検証・可視化スクリプト
    schema.py                # pydantic: 設定スキーマ
  tests/
    test_scalings.py
    test_mass_conservation.py
    test_surface_outflux.py
  out/   # 生成物
  README.md
  pyproject.toml / requirements.txt
数値仕様（最小要件）
* サイズビン：対数30–60（デフォルト40）。範囲 $s\in[10^{-6},3]$ m
* 時間積分：IMEX-BDF(1)（loss陰, gain陽, S_k陽）。必要ならBDF2も実装可。
* Blow‑out滞在時間：$t_{\rm blow}=1/\Omega$（デフォルト・感度スイープ可）
* PSD下限：$s_{\min}(t)=\max(a_{\rm blow}, s_{\rm sub}(T))$
* 自遮蔽：$\Sigma_{\rm surf}\to\min(\Sigma_{\rm surf},,\Sigma_{\tau=1}=1/\kappa_{\rm surf}^{\rm eff})$
* 乱流速度：$c\to c_{\rm eq}(\tau,\epsilon)$（Ohtsuki型）を固定点反復で解く
* 0Dを先に完成 → 任意で1D半径拡張（C5）をスイッチ実装
出力に最低限含めるカラム
* time, dt, tau, a_blow, s_min, kappa, Qpr_mean, beta_at_smin
* Sigma_surf, Sigma_tau1, outflux_surface, t_blow
* prod_subblow_area_rate (=\dot{Σ}^{(<a_blow)}_{prod})
* M_out_dot, M_loss_cum
* mass_total_bins, mass_lost_by_blowout, mass_lost_by_sinks
検証（ログ）
* 式(C4)に基づく質量差分を毎ステップ記録（%）
* Wyattスケールの $t_{\rm coll}$ 推定とモデル内 $t_{\rm coll}$ の比
* “wavy”の指標（隣接ビンの偏差ジグザグ度）

## DocSyncAgent
- トリガ一文: 「analysis を現在の状況に更新して」
- 実行コマンド: `python -m tools.doc_sync_agent --all --write`
- コミットまで行う場合の例: 「analysis を現在の状況に更新して（コミットまで）」 → `python -m tools.doc_sync_agent --all --write --commit`
- Makefile エイリアス: `make analysis-sync` / `make analysis-sync-commit`
- Codex がコード／analysis を変更した場合は、DocSyncAgent 実行直後に `make analysis-doc-tests`（`tools/run_analysis_doc_tests.py` 経由で `pytest tests/test_analysis_* -q` を束ね、ASCII バーで合格率を表示）を必ず走らせ、ドキュメント系テストをまとめて確認する。標準手順として同一バッチで実行し忘れを防ぐこと。
- チャットで「analysisファイルを更新してください」と指示された場合は `make analysis-update`（DocSyncAgent → doc テストの順で実行する複合ターゲット）を走らせること。Codex 側で DocSync とテストを忘れずにセット実行するためのショートカットとする。
- Codex が code/analysis をアップデートする際は、上記 `make analysis-update` を完走させた直後に **必ず** 自動評価 CLI `python -m tools.evaluation_system --outdir <run_dir>` を実行し、analysis 仕様に基づく検証レポートを取得・run_card に反映させること（`<run_dir>` は直近のシミュレーション出力パス、例: `out` や `out/20251022-0426_run4000K__0fdd14772`）。

## シミュレーション結果の保管と実行記録
- 実行結果は out/<YYYYMMDD-HHMM>_<short-title>__<shortsha>__seed<n>/ を作成して格納する。
- 各実行フォルダには、（i）参照レシピ名とコミットID、（ii）環境（Python・依存関係・OS等）、（iii）乱数の初期値と主要パラメータ、（iv）実行コマンド、（v）主要生成物とハッシュ、（vi）analysis/run-recipes.md の確認リストの結果――を run_card.md として記録する。
- 手順の定義や評価基準は analysis/ を唯一の仕様源とし、実行フォルダでは重複記述をしない（参照のみ）。
- out/ は Git では原則無視し（大容量を避けるため）、PR には実行ログの抜粋と要約のみ添付する。

## ドキュメントとファイル配置の原則
- 物理の式・前提・数値処理は `analysis/equations.md` に一本化し、他の資料にはコピーしない。
- モジュール責務やデータフローは `analysis/overview.md` を更新して整理する。
- 実行手順・感度掃引は `analysis/run-recipes.md` のレシピを拡張し、ここでは概要だけを指し示す。
- 生成物・集計・カバレッジは `analysis/coverage.json` と `analysis/coverage_report.md` を自動生成して参照し、手編集を禁止する。
- 自動生成・テスト支援コードは `agent_test/`、完成済みドキュメントと指標は `analysis/` に集約し、新規ファイルは実務上必要と合意した最小限のものに限る。
- AI エージェント向け補足: `analysis/slides_outline.md` は人間向けスライドビューなのでまずここで骨子を掴み、必要に応じて `analysis/overview.md` に潜る。FIG_/RUN_/REF_ を選ぶときは `run_catalog.md` / `figures_catalog.md` / `literature_map.md` を優先的に参照し、out/ を自動スキャンしてスライド構成を作らない。新しい ID を使う場合は `analysis/AI_USAGE.md` のラベル一意性・coverage ポリシーに従う。

## analysisファイルの目的・適用範囲
`analysis/` 以下の完成済み資料を唯一の仕様源とし、参照手順と合格条件のみを定義します。
- エージェントとCIは既存の analysis 節を読み込み、更新時は該当節に反映したうえで本書の受入基準を満たすこと。
- 人手での修正も analysis に直接加筆し、本書に詳細を重複させない。
- シミュレーション評価は analysis の指標・手順で判定し、乖離が生じた場合は analysis 側を整備してからコード変更を提案する。
- 物理の式・前提・数値処理は `analysis/equations.md` に一本化し、他の資料にはコピーしない。
- モジュール責務やデータフローは `analysis/overview.md` を更新して整理する。
- 実行手順・感度掃引は `analysis/run-recipes.md` のレシピを拡張し、ここでは概要だけを指し示す。
- 生成物・集計・カバレッジは `analysis/coverage.json` と `analysis/coverage_report.md` を自動生成して参照し、手編集を禁止する。
- 自動生成・テスト支援コードは `agent_test/`、完成済みドキュメントと指標は `analysis/` に集約し、新規ファイルは実務上必要と合意した最小限のものに限る。
- コード参照は `[marsdisk/path/file.py:開始–終了]` のコロン型を既定とし、例として `[marsdisk/grid.py:17–49]` を Ω(r) と v_K(r) の定義に割り当てる。
- `#L` 形式は補助のみ（コメント・脚注用途）で使用し、存在しない行や逆順の範囲を禁止する。
- 式番号は `(E.###)` を必須とし、既存番号を維持したまま欠番のみ補完する。節の並び替えでも再採番しない。
- DocSyncAgent が再生成するため `analysis/equations.md` の見出しは削除せず、必要な追記は heading を保ったまま行う。

## 受入基準（Fail-under とアンカー健全性）
`analysis/coverage.json` を基準に、以下を満たさない変更は差戻します。
- `function_reference_rate` は 0.75 以上を維持する（現状は 1.0）。下回る場合は欠番関数を特定し、分析文書で参照を補う。
- `anchor_consistency_rate` は 0.98 以上を保ち、`invalid_anchor_count` と `line_anchor_reversed_count` は常に 0 にする。
- 重複アンカーは `duplicate_anchor_count` に記録されるが、衝突など実害があれば必ず解消する（将来的にしきい値を引き上げる余地を残す）。
- CI では `python -m agent_test.ci_guard_analysis --coverage analysis/coverage.json --refs analysis/doc_refs.json --inventory analysis/inventory.json --fail-under 0.75 --require-clean-anchors` を実行し、必要に応じて `--show-top` で不足箇所を確認する。

@-- BEGIN:SIO2_DISK_COOLING_AGENTS --
## SiO₂ Disk Cooling シミュレーション（自動生成）
- 目的：火星放射冷却に基づく SiO₂ 凝固優勢の距離×時間マップの作成
- 実行: `python siO2_disk_cooling/siO2_cooling_map.py`
- 出力: `siO2_disk_cooling/outputs/` 配下の PNG/CSV
@-- END:SIO2_DISK_COOLING_AGENTS --
