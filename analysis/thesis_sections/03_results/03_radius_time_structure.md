## 3. 半径依存：半径×時間の流出構造

本節では，半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径×時間マップを示す．図の色は各セルの $\dot{M}_{\rm out}(r,t)$ を表し，等高線として有効光学的厚さ $\tau_{\rm eff}(r,t)$（式\ref{eq:tau_eff_definition}）を重ねる．比較のため横軸は $t\le 2\,\mathrm{yr}$ の範囲を表示する（以降は流出率がほぼゼロとなる）．

### 3.1 $\tau_0=0.5$ の場合

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
  \caption{半径×時間の流出構造（$\tau_0=0.5$）．色は半径セルごとの $\dot{M}_{\rm out}(r,t)$，等高線は $\tau_{\rm eff}(r,t)$ を示す．各パネルは $(T_{M,0},\epsilon_{\rm mix})$ の組に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

### 3.2 $\tau_0=1.0$ の場合

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
  \caption{半径×時間の流出構造（$\tau_0=1.0$）．表記は図\ref{fig:results_time_radius_moutdot_tau_tau0p5}と同一である．}
  \label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}–\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，流出は初期（$t\lesssim 1\,\mathrm{yr}$）に集中し，時間とともに外側半径から流出が急速に弱まる．また，同じ温度 $T_{M,0}$ では $\tau_0$ が大きい方が $\dot{M}_{\rm out}(r,t)$ の規模が大きく，累積損失の差（図\ref{fig:results_cumloss_grid}）へ反映される．
