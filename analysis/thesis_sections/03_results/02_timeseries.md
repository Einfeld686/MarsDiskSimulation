## 2. 主要時系列と累積量

本節では，全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と累積損失 $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}）の代表的な時間発展を示す．序論で定義した不可逆損失 $\Delta M_{\rm in}(t)$（式\ref{eq:delta_min_def}）は，本論文では $M_{\rm loss}(t)$ と同義である．本章のスイープでは追加シンクを無効化しているため，$M_{\rm loss}$ は $\dot{M}_{\rm out}$ の時間積分（区分一定近似）に一致し，数値出力では $M_{\rm out,cum}$ として記録される．

積分終端 $t_{\rm end}$ は $T_M(t_{\rm end})=T_{\rm end}$（$T_{\rm end}=2000\,\mathrm{K}$）によって定義される（表\ref{tab:results_sweep_setup}）．

まず代表ケース（$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$，$\epsilon_{\rm mix}=1.0$）の時系列を図\ref{fig:results_outflow_tau_cumloss_representative}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/outflow_tau_cumloss_representative/T4000_eps1p0_tau1p0_i00p05_mu1p0.png}
  \caption{代表ケースの時系列．上段：全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数軸）．中段：視線方向光学的厚さ $\tau_{\rm los}(t)$（線形軸，破線は停止判定 $\tau_{\rm stop}=\ln 10$）．下段：累積損失 $M_{\rm loss}(t)$ [$M_{\rm Mars}$]（対数軸）．}
  \label{fig:results_outflow_tau_cumloss_representative}
\end{figure}

図\ref{fig:results_outflow_tau_cumloss_representative}より，$\dot{M}_{\rm out}(t)$ は計算開始直後に $\sim10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ のピークをとり，$\sim1\,\mathrm{yr}$ で $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 以下へ低下する．このため $M_{\rm loss}(t)$ は $t\simeq0.65\,\mathrm{yr}$ で最終値の 99\% に達し，それ以降の増分は小さい．また，$\tau_{\rm los}(t)$ は本ケースで $|\Delta\tau_{\rm los}|\sim3\times10^{-5}$ とほぼ一定であり，本スイープ全体でも $|\Delta\tau_{\rm los}|<1.4\times10^{-4}$ と小さい．以降では，この挙動がパラメータによりどう変化するかをグリッド図で示す．

なお，代表ケースの積分終端は $t_{\rm end}=6.11\,\mathrm{yr}$（表\ref{tab:results_sweep_massloss_cases}）であるが，$M_{\rm loss}$ の大半が $t\lesssim1\,\mathrm{yr}$ で確定することから，温度ドライバ $T_M(t)$ の系統差が結果へ入るとしても，主に初期の高温期（$t\lesssim1\,\mathrm{yr}$）の取り扱いが支配的になる．

### 2.1 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
  % \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
  \caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $\dot{M}_{\rm out}$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは停止条件（4 節）による．}
  \label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}より，$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，多くのケースでは $t\simeq0.05$--$1.3\,\mathrm{yr}$ で $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 以下へ低下する（$T_{M,0}=3000\,\mathrm{K}$ の一部ケースでは開始直後から $10^{-14}$ 以下）．ピーク流出率は $T_{M,0}=3000\,\mathrm{K}$ で $7\times10^{-15}$--$1.4\times10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ であるのに対し，$T_{M,0}=4000$--$5000\,\mathrm{K}$ では $6\times10^{-12}$--$2.4\times10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ と 3--4 桁大きい．また，同じ $(T_{M,0},\epsilon_{\rm mix})$ で比較すると $\tau_0=1.0$ は $\tau_0=0.5$ に比べて $\dot{M}_{\rm out}(t)$ の規模が概ね 2 倍となり，累積損失の差（次節）へ反映される．

### 2.2 累積損失 $M_{\rm loss}(t)$

図\ref{fig:results_cumloss_grid}に累積損失 $M_{\rm loss}(t)$ を示す（縦軸は $10^{-5}M_{\rm Mars}$ で規格化）．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau0p5.png}
  % \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau1p0.png}
  \caption{累積損失 $M_{\rm loss}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $M_{\rm loss}/(10^{-5}M_{\rm Mars})$ の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは停止条件（4 節）による．}
  \label{fig:results_cumloss_grid}
\end{figure}

図\ref{fig:results_cumloss_grid}より，$M_{\rm loss}(t)$ は $t\lesssim1\,\mathrm{yr}$ でほぼ飽和し，最終値は $2.0\times10^{-8}$--$1.1\times10^{-4}\,M_{\rm Mars}$ の範囲に分布する．したがって，$M_{\rm loss}$ の大小は初期の $\dot{M}_{\rm out}$ の規模で概ね決まり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が主要な支配因子となる．本スイープで得られた $M_{\rm loss}$ の範囲とパラメータ依存性は 5 節で定量的に要約する．

小括として，本節では $\dot{M}_{\rm out}(t)$ が遷移期の初期に集中し，$M_{\rm loss}$ が 1 年以内にほぼ確定することを示した．次節では，この流出が半径方向にどのように分布するかを示す．
