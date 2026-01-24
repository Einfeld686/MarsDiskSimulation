## 6. 小結

本章では，軸対称 1D モデルを用いたスイープ計算により，放射圧流出に伴う累積損失 $M_{\rm loss}$ の大きさと依存性を示した．得られた主要結果を以下に要約する．

- 全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ は初期に大きく，短時間で急減して準定常値（ほぼゼロ）へ向かう（図\ref{fig:results_moutdot_grid}）．
- 累積損失 $M_{\rm loss}(t)$ は初期に急増し，その後はほぼ一定値へ飽和する（図\ref{fig:results_cumloss_grid}）．
- 半径依存を含む $\dot{M}_{\rm out}(r,t)$ は初期に集中し，時間とともに外側半径から流出が急速に弱まる（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．
- スイープ全体では，$M_{\rm loss}$ は $2.0\times 10^{-8}$ から $1.09\times 10^{-4}\,M_{\rm Mars}$ の範囲にあり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が主要な支配因子である（表\ref{tab:results_sweep_massloss_cases}）．
- 基準の内側円盤質量 $M_{\rm in}(t_0)=3\times10^{-5}M_{\rm Mars}$（表\ref{tab:method-param}）で規格化すると，$M_{\rm loss}(t_{\rm end})/M_{\rm in}(t_0)=6.8\times10^{-4}$--$3.6$（$0.07\%$--$360\%$）に相当する．
- 質量保存誤差は最大でも $8.72\times 10^{-14}\%$ 程度であり，本章の $M_{\rm loss}$ は収支誤差により支配されない（表\ref{tab:results_mass_budget_summary}）．
- 以上で得た $M_{\rm loss}(t_{\rm end})$（$\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）は，長期モデルへ渡す内側円盤質量 $M_{\rm in,0}$ の更新（式\ref{eq:min0_update}）に直接用いられる．

これらの結果を踏まえ，次章では損失の物理的解釈と長期衛星形成モデルへの接続に対する含意を議論する．
