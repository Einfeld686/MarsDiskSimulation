このカタログは論文・スライドに登場し得る図の唯一のレジストリであり、FIG_* ID は全体で一意かつ安定に保つ。実データやノートブックの所在をここで指し、図そのものは out/ や notebooks 側の生成物を参照する。`fig_id` の命名規則は `FIG_<TOPIC>_<NN>`（例: `FIG_BETA_SERIES_01`）。

| fig_id | short_caption | source_notebook_or_script | related_run_ids | eq_refs | status | notes |
| --- | --- | --- | --- | --- | --- | --- |
| FIG_BETA_SERIES_01 | β・a_blow・s_min の時系列 | notebooks/beta_series_demo.ipynb | RUN_MARS_GASPOOR_v01,RUN_TEMP_DRIVER_v01 | E.012,E.013,E.014 | placeholder | TODO: 実ノートブックと out/series を紐付け。 |
| FIG_PSD_WAVY_01 | “wavy” PSD スナップショット | notebooks/psd_wavy_demo.ipynb | RUN_WAVY_PSD_v01 | E.024,E.035 | placeholder | TODO: ジグザグ指標と凡例を決める。 |
| FIG_MASS_BUDGET_01 | 質量保存誤差の推移 | scripts/plot_mass_budget.py | RUN_MARS_GASPOOR_v01 | E.011 | placeholder | TODO: checks/mass_budget.csv を参照して更新。 |
| FIG_SHIELDING_SERIES_01 | τ・Φ・Σ_tau1 の時間発展 | notebooks/shielding_series.ipynb | RUN_TL2003_TOGGLE_v01 | E.015,E.016,E.017 | placeholder | TODO: TL2003 on/off 比較を並べる。 |
| FIG_RUN_GRID_01 | 代表 run の比較グリッド | notebooks/run_grid_overview.ipynb | RUN_MARS_GASPOOR_v01,RUN_TL2003_TOGGLE_v01,RUN_TEMP_DRIVER_v01,RUN_WAVY_PSD_v01 | E.008 | placeholder | TODO: summary.json から主要指標を抜粋。 |
