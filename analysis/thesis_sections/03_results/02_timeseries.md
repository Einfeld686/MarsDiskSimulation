## 2. 主要時系列と累積量

本節では，全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と累積損失 $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}）の代表的な時間発展を示す．序論で定義した不可逆損失 $\Delta M_{\rm in}(t)$（式\ref{eq:delta_min_def}）は，本論文では $M_{\rm loss}(t)$ と同義である．本章のスイープでは追加シンクを無効化しているため，$M_{\rm loss}$ は $\dot{M}_{\rm out}$ の時間積分（区分一定近似）に一致し，数値出力では $M_{\rm out,cum}$ として記録される．

また，$\tau_{\rm los}$（および $\tau_{\rm eff}$）の時間変化は小さいため，半径依存を含む形で 3 節にまとめて示す．

### 2.1 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
  \caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表す．}
  \label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}より，$\dot{M}_{\rm out}(t)$ は初期に大きく，短時間で急減して準定常値（ほぼゼロ）へ向かう．温度 $T_{M,0}$ に対する依存性が顕著であり，$T_{M,0}=3000\,\mathrm{K}$ では流出が小さい一方，$T_{M,0}\ge 4000\,\mathrm{K}$ では $\dot{M}_{\rm out}$ のピークが桁違いに大きい．また，同じ $(T_{M,0},\epsilon_{\rm mix})$ で比較すると $\tau_0=1.0$ は $\tau_0=0.5$ に比べて流出率が概ね大きく，累積損失の差（次節）へ反映される．

### 2.2 累積損失 $M_{\rm loss}(t)$

図\ref{fig:results_cumloss_grid}に累積損失 $M_{\rm loss}(t)$ を示す（縦軸は $10^{-5}M_{\rm Mars}$ で規格化）．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau1p0.png}
  \caption{累積損失 $M_{\rm loss}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．曲線の割り当ては図\ref{fig:results_moutdot_grid}と同一である．}
  \label{fig:results_cumloss_grid}
\end{figure}

図\ref{fig:results_cumloss_grid}より，$M_{\rm loss}(t)$ は初期に急増し，その後はほぼ一定値へ飽和する．したがって，$M_{\rm loss}$ の大小は初期の $\dot{M}_{\rm out}$ の規模で概ね決まり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が支配因子となる．本スイープで得られた $M_{\rm loss}$ の範囲とパラメータ依存性は 5 節で定量的に要約する．
