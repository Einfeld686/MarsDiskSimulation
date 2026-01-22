## 5. 感度解析

本節では，表\ref{tab:results_sweep_setup}の 16 ケースを用いて，$M_{\rm loss}$ が主要パラメータにどう依存するかを要約する．

### 4.1 累積損失 $M_{\rm loss}$ の温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_core}に，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ ごとに平均した $M_{\rm loss}$ と停止時刻を示す．本スイープでは，$T_{M,0}=4000\,\mathrm{K}$ のケースで $M_{\rm loss}$ が $10^{-5}$ オーダーに達する一方，$T_{M,0}=3000\,\mathrm{K}$ では $10^{-9}$ オーダーと小さく，温度依存性が卓越する．また，$\tau_0=1.0$ のケースでは $\tau_{\rm los}$ が閾値に到達して早期停止し，積分区間が短いにもかかわらず $M_{\rm loss}$ が増大する傾向が見られる．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{感度解析の要約図（例）：$T_{M,0}$ と $\tau_0$ に対する $M_{\rm loss}$ の比較．}
  \label{fig:results_sensitivity_summary}
\end{figure}

\begin{table}[t]
  \centering
  \caption{温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ に対する $M_{\rm loss}$ の感度（16 ケースの平均）}
  \label{tab:results_sweep_massloss_core}
  \begin{tabular}{ccccc}
    \hline
    $T_{M,0}$ [K] & $\tau_0$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\rm Mars}$] \\
    \hline
    3000 & 0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 4.92 & $3.14\times 10^{-9}$ \\
    3000 & 1.0 & $\tau_{\rm los}>\tau_{\rm stop}$ & 2.53 & $6.29\times 10^{-9}$ \\
    4000 & 0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 6.11 & $7.78\times 10^{-6}$ \\
    4000 & 1.0 & $\tau_{\rm los}>\tau_{\rm stop}$ & 1.27 & $1.56\times 10^{-5}$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 $\epsilon_{\rm mix}$ と $i_0$ の影響

同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}$ と $i_0$ を変えても，$M_{\rm loss}$ の変動幅は相対的に $\lesssim 3\times 10^{-4}$ と小さかった．したがって，本スイープ設定の範囲では，$M_{\rm loss}$ は主に $T_{M,0}$ と $\tau_0$ によって支配される．
