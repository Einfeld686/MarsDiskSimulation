## 6. 小結

本章では，軸対称 1D モデルの 12 ケース掃引により，放射圧ブローアウト（追加シンク無効）に伴う累積損失 $M_{\rm loss}$ の大きさと依存性を定量化した．$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，その後急速に減衰するため，$M_{\rm loss}(t)$ は 1 年以内にほぼ確定する（全ケースで 99\% 到達時刻は $t\simeq0.19$--$0.84\,\mathrm{yr}$；図\ref{fig:results_moutdot_grid}，図\ref{fig:results_cumloss_grid}）．

最終的な $M_{\rm loss}$ は $2.0\times 10^{-8}$--$1.09\times 10^{-4}\,M_{\rm Mars}$ に分布し，温度 $T_{M,0}$ が最も強い支配因子である（$3000\to4000\,\mathrm{K}$ で約 $10^3$ 倍；表\ref{tab:results_sweep_massloss_cases}）．初期光学的厚さ $\tau_0$ はほぼ線形に効いて $M_{\rm loss}$ を概ね 2 倍変える．一方，供給混合係数 $\epsilon_{\rm mix}$ は供給率の規格化の取り方に関する感度であり（手法章 2.3節），停止時刻の違いを除けば $M_{\rm loss}$ は一致する（表\ref{tab:results_sweep_massloss_cases}）．

半径方向には，流出は初期に外側から先に終息し，半径×時間マップでその構造が確認できる（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．また，本スイープでは $\tau_{\rm los}>\tau_{\rm stop}$ の早期停止は発生せず，照射近似が成立する範囲で評価できている．質量保存誤差は最大でも $10^{-13}\%$ 未満であり，収支ずれが結果を支配しない（表\ref{tab:results_mass_budget_summary}）．

以上の $M_{\rm loss}(t_{\rm end})$（$\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）は，遷移期の放射圧損失（下限評価）として，長期モデルへ渡す内側円盤質量の更新（式\ref{eq:min0_update}）に直接用いられる．序論で指摘した二つの系統差要因は，結果として $T_{M,0}$（温度条件）と $\tau_0$（照射され得る表層量）の感度として現れ，本章の範囲では温度依存性が卓越する．

これらの結果を踏まえ，次章では損失の物理的解釈と長期衛星形成モデルへの接続に対する含意を議論する．
