## 2. 主要時系列と累積量

本節では，代表ケースの主要時系列をまとめる．とくに，視線方向光学的厚さ $\tau_{\rm los}(t)$ と有効光学的厚さ $\tau_{\rm eff}(t)$ の推移と停止条件，放射圧流出率 $\dot{M}_{\rm out}(t)$，および累積損失 $M_{\rm loss}(t)$ を示す．

### 2.1 光学的厚さの推移と停止

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける $\tau_{\rm los}(t)$ の推移．}
  \label{fig:results_tau_los_timeseries}
\end{figure}

代表ケース（$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$）では，初期条件で $\tau_{\rm eff}(t_0)=\tau_0$ となるよう規格化した後，時間発展とともに $\tau_{\rm eff}$ が増加し，$\tau_{\rm eff}>\tau_{\rm stop}=2.30$ を満たして $t_{\rm end}\approx 1.27\,\mathrm{yr}$ で早期停止した（図\ref{fig:results_tau_los_timeseries}は診断量として $\tau_{\rm los}$ の推移を示す）．一方，$\tau_0=0.5$ の場合は $\tau_{\rm eff}$ が $\tau_{\rm stop}$ に達せず，$T_M=2000\,\mathrm{K}$ 到達まで積分が継続した．

### 2.2 放射圧流出率と累積損失

表層放射圧により除去される質量流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$ を図\ref{fig:results_outflux_and_cumloss}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける放射圧流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$ の時系列．}
  \label{fig:results_outflux_and_cumloss}
\end{figure}

\begin{table}[t]
  \centering
  \caption{代表ケースの終端要約}
  \label{tab:results_representative_summary}
  \begin{tabular}{p{0.50\textwidth} p{0.40\textwidth}}
    \hline
    指標 & 値 \\
    \hline
    停止理由 & $\tau_{\rm eff}>\tau_{\rm stop}$（$\tau_{\rm stop}=2.30$） \\
    終端時刻 $t_{\rm end}$ & $1.27\,\mathrm{yr}$ \\
    累積損失 $M_{\rm loss}(t_{\rm end})$ & $1.56\times 10^{-5}\,M_{\rm Mars}$ \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \caption{初期光学的厚さ $\tau_0$ の違いによる比較（$T_{M,0}=4000\,\mathrm{K}$）}
  \label{tab:results_tau0_comparison}
  \begin{tabular}{cccc}
    \hline
    $\tau_0$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\rm Mars}$] \\
    \hline
    0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 6.11 & $7.78\times 10^{-6}$ \\
    1.0 & $\tau_{\rm eff}>\tau_{\rm stop}$ & 1.27 & $1.56\times 10^{-5}$ \\
    \hline
  \end{tabular}
\end{table}
