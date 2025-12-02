このファイルは重要なシミュレーション run をAIと著者が共有するための機械可読インデックスである。各行は `out/` 配下の `run_card.md` へのパターンを示すが、`out/` 自体はGit管理外である。数式や物理定義は `analysis/equations.md` の (E.xxx) アンカーを参照し、ここでは再掲しない。

| run_id | short_label | config_path | out_pattern | purpose_ja | eq_refs | fig_refs | status | notes_for_AI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RUN_MARS_GASPOOR_v01 | ガス希薄基準（0D） | configs/base.yml | out/*_gaspoor-baseline__*__/run_card.md | gas-poor標準設定でβ→a_blow→表層剥離の連鎖と質量収支ログを確認する基準run。 | E.008,E.013,E.014,E.011 | FIG_BETA_SERIES_01,FIG_MASS_BUDGET_01,FIG_RUN_GRID_01 | active | Use as default reference; stable assumptions, TL2003 off. |
| RUN_TL2003_TOGGLE_v01 | TL2003トグル感度 | configs/base.yml + overrides | out/*_tl2003-toggle__*__/run_card.md | gas-rich想定で `ALLOW_TL2003` on/off によるΦとM_out_dot差分を比較する。 | E.015,E.016,E.017 | FIG_SHIELDING_SERIES_01 | active | Pair with gas-poor baseline; ensure shielding tables are available. |
| RUN_TEMP_DRIVER_v01 | 強放射・β掃引 | configs/mars_temperature_driver_table.yml | out/*_temp-driver__*__/run_card.md | 火星温度ドライバと⟨Q_pr⟩テーブル掃引でβ, a_blow, s_min の閾値を追跡する。 | E.012,E.013,E.014 | FIG_BETA_SERIES_01 | active | Use when probing high-β regime; requires qpr_table_path. |
| RUN_WAVY_PSD_v01 | wavy PSD実験 | configs/base.yml | out/*_wavy-psd__*__/run_card.md | psd.wavy_strengthと高速blow-out条件で“wavy” PSDを可視化し、sub-blow-out生成率を検証する。 | E.024,E.026,E.035 | FIG_PSD_WAVY_01 | planned | Keep dt/t_blow ≤ 0.1; request psd histograms. |
| RUN_HIGH_BETA_SHIELD_v01 | 高β・遮蔽テスト | configs/base.yml + overrides | out/*_high-beta-shield__*__/run_card.md | βが閾値を大きく超える設定で遮蔽クリップと質量損失の挙動を確認する感度試験。 | E.013,E.014,E.015,E.016 | FIG_SHIELDING_SERIES_01 | planned | Use aggressive Q_pr tables; contrast shielding on/off. |
