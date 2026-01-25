## 3. 半径依存：半径×時間の流出構造

本節では，半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径×時間マップを示す．横軸は時間 $t$ [yr]，縦軸は半径 $r/R_{\rm Mars}$ である．色は各セルの $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白はカラースケール下限（$10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$）以下を表す．本モデルは基準ケースとしてセル間輸送を含めないため，ここで見える半径依存は各セルの局所条件の違いとして解釈する．本スイープでは $\tau_{\rm los}$ の時間変化が小さい（2 節）ため，ここでは流出構造の差に焦点を当てて $\dot{M}_{\rm out}(r,t)$ のみを可視化する．比較のため横軸は $t\le 2\,\mathrm{yr}$ の範囲を表示する．

### 3.1 $\tau_0=0.5$ の場合

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
  \caption{半径×時間の流出構造（$\tau_0=0.5$）．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数カラースケール）を示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満である．パネルは (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

### 3.2 $\tau_0=1.0$ の場合

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
  \caption{半径×時間の流出構造（$\tau_0=1.0$）．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数カラースケール）を示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満である．パネルは (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，流出は初期（$t\lesssim 1\,\mathrm{yr}$）に集中し，時間とともに外側半径から流出が弱まることで，流出が生じる領域は内側へ縮退していく．また，同じ温度 $T_{M,0}$ では $\tau_0$ が大きい方が $\dot{M}_{\rm out}(r,t)$ の規模が大きく，累積損失の差（図\ref{fig:results_cumloss_grid}）へ反映される．

小括として，本節では全円盤積分量 $\dot{M}_{\rm out}(t)$ の背後にある半径方向の流出構造を可視化し，流出が初期に外側から先に弱まる様子を示した．次節では，得られた $M_{\rm loss}$ が数値誤差や停止判定に支配されていないことを検証する．
