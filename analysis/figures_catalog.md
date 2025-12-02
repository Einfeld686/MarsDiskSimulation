このファイルはスライドや論文で再利用する「標準図」のカタログであり、対応する run_id と（あれば）静的画像ファイルを紐付ける。数式は `analysis/equations.md` のアンカーを参照し、ここでは再掲しない。

| fig_id | file_path | kind | run_refs | eq_refs | caption_ja | notes_for_AI |
| --- | --- | --- | --- | --- | --- | --- |
| FIG_BETA_SERIES_01 | out/*_temp-driver__*__/fig_beta_eff.png | time_series | RUN_TEMP_DRIVER_v01,RUN_MARS_GASPOOR_v01 | E.012,E.013,E.014 | β・a_blow・s_minの時系列で軽さ指標の閾値を示す。 | Emphasize beta threshold vs s_min clip; use for blow-out background slides. |
| FIG_MASS_BUDGET_01 | out/*_gaspoor-baseline__*__/fig_mass_budget_timeline.png | time_series | RUN_MARS_GASPOOR_v01 | E.011 | 質量保存誤差率と累積M_lossの時間推移。 | Use to discuss IMEX stability and mass_budget log; pair with summary.json stats. |
| FIG_SHIELDING_SERIES_01 | out/*_tl2003-toggle__*__/fig_shielding_series.png | time_series | RUN_TL2003_TOGGLE_v01,RUN_HIGH_BETA_SHIELD_v01 | E.015,E.016,E.017 | TL2003 on/offや高β条件でΦ・Σ_tau=1・M_out_dotを比較。 | Highlight gas-poor default vs gas-rich toggle; show shielding clip impact. |
| FIG_RUN_GRID_01 | analysis/outputs/fig_run_grid.png | diagnostic_table | RUN_MARS_GASPOOR_v01,RUN_TL2003_TOGGLE_v01,RUN_WAVY_PSD_v01 | E.008 | 代表runの主要指標を並べたグリッド概要。 | Use as overview tile; keep numbers minimal, focus on labels. |
| FIG_PSD_WAVY_01 | out/*_wavy-psd__*__/fig_psd_heatmap.png | PSD | RUN_WAVY_PSD_v01 | E.024,E.035 | blow-out近傍で現れる“wavy” PSDの時間×サイズ分布。 | Point out zig-zag near blow-out; mention wavy_strength setting. |
