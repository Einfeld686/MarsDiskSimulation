<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 3. 半径依存：半径×時間の流出構造

半径セルごとの放射圧起因の質量流出率 $\dot{M}_{\rm out}(r,t)$ を半径–時間マップとして示し，全円盤で定義した流出率 $\dot{M}_{\rm out}(t)$ が初期に急減する要因を，寄与する半径帯の時間発展として可視化する（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}，図\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．横軸は時間 $t\,[\mathrm{yr}]$，縦軸は半径 $r/R_{\rm Mars}$ である．色は各セルの $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数スケールで表し，白はカラースケールの下限値 $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を示す．基準ケースでは半径方向のセル間輸送を考慮しないため，図に現れる半径依存性は，各セルの局所条件の違いによるものであると考えることができる．表示範囲は $t\le 2\,\mathrm{yr}$ である．

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}に，$\tau_0=0.5$ における放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径–時間分布（$t\le 2\,\mathrm{yr}$）を示す．
図\ref{fig:results_time_radius_moutdot_tau_tau0p5}では，流出が卓越する時間帯が初期に偏り，時間とともに流出が生じる半径帯が内側へ縮小する傾向が見て取れる

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
\caption{半径–時間の流出構造（$\tau_0=0.5$）．横軸は時間 $t$ [$\mathrm{yr}$]（表示範囲 $t\le 2\,\mathrm{yr}$），縦軸は半径 $r/R_{\rm Mars}$ である．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を表す．パネル (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応する．$i_0=0.05$，$\mu=1.0$ は共通である．}
\label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau1p0}に，$\tau_0=1.0$ の半径–時間分布を示す．図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}によると，質量流出が初期に集中し，流出の寄与が時間とともに内側へ限られていくことがわかる．

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
\caption{半径–時間の流出構造（$\tau_0=1.0$）．横軸は時間 $t$ [$\mathrm{yr}$]（表示範囲 $t\le 2\,\mathrm{yr}$），縦軸は半径 $r/R_{\rm Mars}$ である．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を表す．パネル (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応する．$i_0=0.05$，$\mu=1.0$ は共通である．}
\label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，$\dot{M}_{\rm out}(r,t)$ は初期（$t\lesssim 1\,\mathrm{yr}$）に大きく，その後は急速に弱まることが分かる．半径方向の時間発展に着目すると，外側半径側から順に $\dot{M}_{\rm out}(r,t)$ が低下し，流出に寄与する半径帯が時間とともに内側へ縮小していく．以降では可視化の閾値に合わせ，$\dot{M}_{\rm out}(r,t)\ge 10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を満たす領域を流出寄与領域と呼ぶ．
この流出寄与領域が外側から失われることで，全円盤積分量 $\dot{M}_{\rm out}(t)$ は短時間で急減し（図\ref{fig:results_moutdot_grid}），累積損失量 $M_{\rm loss}$ が $t\lesssim 1\,\mathrm{yr}$ でほぼ確定するという振る舞いが，半径方向の寄与として理解できる．また，同一の $T_{M,0}$ の下では，$\tau_0$ が大きいほど $\dot{M}_{\rm out}(r,t)$ の規模が全体に大きく，その差は累積損失量の差（図\ref{fig:results_cumloss_grid}）として現れる．
