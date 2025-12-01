このファイルは「スライドの並べ方」を決めるための単一ソースであり、本文・数式・図そのものはここに置かない。10 枚のコアスライドは常に存在し、内容更新は `analysis/equations.md`（式）、`analysis/figures_catalog.md`（図）、`analysis/run_catalog.md`（run メタ）への参照でまかなう。読者は自分自身（リポジトリオーナー）を想定し、LLM に対する口調や深さは notes に記す。

## コアスライド（固定10枚）
| slide_id | title | purpose | eq_refs | fig_refs | run_refs | analysis_refs | priority | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CORE_01_OVERVIEW | 目的とスコープ | gas-poor な火星ロッシュ内円盤で何を解くかを最短で思い出す。 | E.008,E.013 | FIG_OVERVIEW_BLOCK,FIG_BETA_SERIES_01 | RUN_MARS_GASPOOR_v01 | analysis/overview.md | core | 2–3 文で始め、不要な背景は避ける。 |
| CORE_02_PRIOR_WORK | 先行研究の位置づけ | Hyodo+, Ronnet+, Canup & Salmon などから gas-poor 前提を確認する。 |  | FIG_LIT_TIMELINE_01 | RUN_MARS_GASPOOR_v01 | analysis/literature_map.md | core | 文献名は略称で、式は貼らない。 |
| CORE_03_MODEL_ARCH | モデル構造 | 0D 円盤＋衝突カスケード＋表層剥離の結合フローを示す。 | E.006,E.010 | FIG_MODEL_ARCH_01 | RUN_MARS_GASPOOR_v01 | analysis/overview.md | core | LLM にはモジュール接続を箇条書きで説明させる。 |
| CORE_04_RADIATION_BLOWOUT | β と blow-out | ⟨Q_pr⟩→β→a_blow→t_blow の計算鎖を整理する。 | E.012,E.013,E.014 | FIG_BETA_SERIES_01 | RUN_MARS_GASPOOR_v01,RUN_TEMP_DRIVER_v01 | analysis/equations.md | core | 計算手順だけを短く、数値例は不要。 |
| CORE_05_PSD_COLLISIONS | PSD と破砕供給 | Smoluchowski、Q_D^*、“wavy” 補正、sub-blow-out 生成率の関係を押さえる。 | E.024,E.026,E.035 | FIG_PSD_WAVY_01 | RUN_WAVY_PSD_v01 | analysis/overview.md | core | 数式参照のみ、グラフを一枚置く。 |
| CORE_06_SURFACE_LAYER | 表層剥離と遮蔽 | Φ(τ,ω0,g)、Σ_tau=1 クリップ、TL2003 トグルの扱いを比較する。 | E.015,E.016,E.017 | FIG_SHIELDING_SERIES_01 | RUN_TL2003_TOGGLE_v01 | analysis/AI_USAGE.md | core | gas-poor 既定で TL2003 無効を明示。 |
| CORE_07_NUMERICS_CHECKS | 数値スキームと質量検査 | IMEX-BDF(1)、Wyatt t_coll スケール、質量誤差ログを振り返る。 | E.006,E.010,E.011 | FIG_MASS_BUDGET_01 | RUN_MARS_GASPOOR_v01 | analysis/run_catalog.md | core | 収束条件とログの読み方だけ。 |
| CORE_08_TEMPERATURE | 火星放射・温度ドライバ | 火星温度ドライバ、⟨Q_pr⟩テーブル、放射冷却解析解のつなぎ方を示す。 | E.012,E.042 | FIG_TEMPERATURE_DRIVER_01 | RUN_TEMP_DRIVER_v01 | analysis/overview.md | core | ドライバ優先順位を一言で。 |
| CORE_09_RUNSET | 代表 run セット | gas-poor 基本・gas-rich 感度・TL2003 トグル・wavy 実験の用途を整理する。 |  | FIG_RUN_GRID_01 | RUN_MARS_GASPOOR_v01,RUN_TL2003_TOGGLE_v01,RUN_WAVY_PSD_v01 | analysis/run_catalog.md | core | 1 行ずつ役割を書く、数値は載せない。 |
| CORE_10_OUTLOOK | 今後の課題 | 次に試すシナリオ・未実装物理・検証の ToDo を短く列挙する。 |  | FIG_OUTLOOK_CHECKLIST_01 | RUN_MARS_GASPOOR_v01 | analysis/overview.md | core | 箇条書きで、LLM には簡潔な口調を指示。 |

## Optional slides
以下は例示用のオプション枠（追加時は `priority="optional"` のまま明示する）。

| slide_id | title | purpose | eq_refs | fig_refs | run_refs | analysis_refs | priority | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OPT_01_COOLING_MAP | 冷却マップ概要 | SiO₂ 冷却マップと温度ドライバの関係を載せる案。 | E.042 | FIG_TEMPERATURE_DRIVER_01 | RUN_TEMP_DRIVER_v01 | analysis/overview.md | optional | TODO: 実際の PNG を作ったら差し替える。 |
| OPT_02_VALIDATION_SET | 検証セットまとめ | diagnostics/minimal など検証レシピの所在をメモ。 | E.011 | FIG_MASS_BUDGET_01 | RUN_MARS_GASPOOR_v01 | analysis/run_catalog.md | optional | TODO: run_card へのリンクを付ける。 |
| OPT_03_METHOD_APPENDIX | 数値手法詳細 | IMEX パラメータやサブステップ条件を補足する案。 | E.010 | FIG_NUMERICS_FLOW_01 | RUN_MARS_GASPOOR_v01 | analysis/equations.md | optional | TODO: 必要になったときだけ有効化。 |
