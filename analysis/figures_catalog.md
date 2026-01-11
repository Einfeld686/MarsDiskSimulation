このファイルはスライドや論文で再利用する「標準図」のカタログであり、対応する run_id と（あれば）静的画像ファイルを紐付ける。数式は `analysis/equations.md` のアンカーを参照し、ここでは再掲しない。

`status` 列: `active`（現在の研究で使用）、`deprecated`（旧研究、参考程度）、`planned`（未生成）。

| fig_id | file_path | kind | run_refs | eq_refs | caption_ja | status | notes_for_AI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FIG_TEMP_SUPPLY_OVERVIEW | temp_supply_sweep/\*/T\*_eps\*_tau\*/plots/overview.png | summary | RUN_TEMP_SUPPLY_SWEEP_v01 | E.027,E.042,E.043 | 温度×供給スイープの各ケース概要図。τ, M_loss, 供給レートの時系列を一覧表示。 | active | 10ケースすべてに生成される。代表的なケース（T4000_eps1p0_tau1p0）をスライドで使用。 |
| FIG_SUPPLY_SURFACE | temp_supply_sweep/\*/T\*_eps\*_tau\*/plots/supply_surface.png | time_series | RUN_TEMP_SUPPLY_SWEEP_v01 | E.027 | 供給レートと表層密度の時間発展。deep_mixing 経路の効果を可視化。 | active | deep→surf フラックスの診断に使用。 |
| FIG_OPTICAL_DEPTH | temp_supply_sweep/\*/T\*_eps\*_tau\*/plots/optical_depth.png | time_series | RUN_TEMP_SUPPLY_SWEEP_v01 | E.015,E.016 | 光学的厚さ τ_vertical と τ_los の時間発展。τ≈1 維持条件の検証に使用。 | active | τ 条件（0.5-2）の評価区間をハイライト。 |
| FIG_MLOSS_HEATMAP | analysis/outputs/fig_mloss_heatmap.png | heatmap | RUN_TEMP_SUPPLY_SWEEP_v01 | E.011 | T×ε×τ パラメータ空間での M_loss 感度マップ。 | planned | スイープ完了後に生成予定。感度分析スライドの中心図。 |
| FIG_DEEP_MIXING_DIAGNOSTIC | temp_supply_sweep/\*/T\*_eps\*_tau\*/plots/deep_mixing.png | diagnostic | RUN_TEMP_SUPPLY_SWEEP_v01 | E.027 | deep_mixing 経路の診断図。σ_deep と deep→surf flux の時系列。 | active | transport.mode=deep_mixing のときのみ生成。 |
| FIG_BETA_SERIES_01 | out/*_temp-driver__*__/fig_beta_eff.png | time_series | RUN_TEMP_DRIVER_v01,RUN_MARS_GASPOOR_v01 | E.012,E.013,E.014 | β・a_blow・s_minの時系列で軽さ指標の閾値を示す。 | deprecated | 旧研究用。temp_supply_sweep の overview 図で代替。 |
| FIG_MASS_BUDGET_01 | out/*_gaspoor-baseline__*__/fig_mass_budget_timeline.png | time_series | RUN_MARS_GASPOOR_v01 | E.011 | 質量保存誤差率と累積M_lossの時間推移。 | deprecated | 旧研究用。数値検証にはまだ有用。 |
| FIG_SHIELDING_SERIES_01 | out/*_tl2003-toggle__*__/fig_shielding_series.png | time_series | RUN_TL2003_TOGGLE_v01,RUN_HIGH_BETA_SHIELD_v01 | E.015,E.016,E.017 | TL2003 on/offや高β条件でΦ・Σ_tau=1・M_out_dotを比較。 | deprecated | TL2003 は gas-poor 既定で無効のため非推奨。 |
| FIG_RUN_GRID_01 | analysis/outputs/fig_run_grid.png | diagnostic_table | RUN_MARS_GASPOOR_v01,RUN_TL2003_TOGGLE_v01,RUN_WAVY_PSD_v01 | E.008 | 代表runの主要指標を並べたグリッド概要。 | deprecated | 旧研究用。temp_supply_sweep 用のグリッド図に置換予定。 |
| FIG_PSD_WAVY_01 | out/*_wavy-psd__*__/fig_psd_heatmap.png | PSD | RUN_WAVY_PSD_v01 | E.024,E.035 | blow-out近傍で現れる"wavy" PSDの時間×サイズ分布。 | planned | wavy_strength 感度試験で使用予定。 |
