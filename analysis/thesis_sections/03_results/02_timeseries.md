## 2. 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
\includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
\caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $\dot{M}_{\rm out}$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは数値停止条件（4.2 節）による．}
\label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}に示すように，$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，その後に急速に減衰する．多くのケースでは $t\simeq0.05$--$1.3\,\mathrm{yr}$ で $\dot{M}_{\rm out}<10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ となる．また，$T_{M,0}=3000\,\mathrm{K}$ の一部ケースでは，開始直後から $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を下回る．

ピーク流出率は $T_{M,0}=3000\,\mathrm{K}$ で $7\times10^{-15}$--$1.4\times10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ であるのに対し，$T_{M,0}=4000$--$5000\,\mathrm{K}$ では $6\times10^{-12}$--$2.4\times10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ と3桁程度大きい．また，同一の $(T_{M,0},\epsilon_{\rm mix})$ に対して比較すると，$\tau_0=1.0$ は $\tau_0=0.5$ に比べて $\dot{M}_{\rm out}(t)$ の規模が概ね2倍となり，累積損失の差（5 節）としても現れる．
したがって，$\dot{M}_{\rm out}(t)$ が初期過渡期に集中し，その結果として累積損失 $M_{\rm loss}$ が短時間でほぼ確定していることがわかる．
