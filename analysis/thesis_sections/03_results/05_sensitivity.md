## 5. 感度解析

本節では，表\ref{tab:results_sweep_setup}の 12 ケースを用いて，$M_{\rm loss}$ が主要パラメータにどう依存するかを要約する．

### 5.1 累積損失 $M_{\rm loss}$ の温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_cases}に，全 12 ケースの $M_{\rm loss}$ を示す．本スイープでは，$T_{M,0}$ の上昇に伴って $M_{\rm loss}$ が急増し，温度依存性が卓越する．また，同一の $T_{M,0}$ で比較すると，$\tau_0=1.0$ の $M_{\rm loss}$ は $\tau_0=0.5$ の概ね 2 倍となる．

温度依存性は，放射圧比 $\beta(s)$ とブローアウト粒径 $s_{\rm blow}$ を通じて一次シンク（ブローアウト）を規定することに由来する（手法章 2.1節，式\ref{eq:surface_outflux}）．また，$\tau_0$ は初期の $\tau_{\rm los}$ 規格化（式\ref{eq:tau_los_definition}）を通じて表層面密度のスケールを与えるため，$\tau_0$ を 2 倍にすると $M_{\rm loss}$ も概ね 2 倍となる．

\begin{table}[t]
  \centering
  \caption{スイープ 12 ケースにおける累積損失 $M_{\rm loss}$ と停止条件}
  \label{tab:results_sweep_massloss_cases}
  \begin{tabular}{cccccc}
    \hline
    $T_{M,0}$ [K] & $\tau_0$ & $\epsilon_{\rm mix}$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\rm Mars}$] \\
    \hline
    3000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 4.92 & $2.04\times 10^{-8}$ \\
    3000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $2.04\times 10^{-8}$ \\
    3000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 4.92 & $4.09\times 10^{-8}$ \\
    3000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $4.09\times 10^{-8}$ \\
    4000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 6.11 & $2.20\times 10^{-5}$ \\
    4000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $2.20\times 10^{-5}$ \\
    4000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 6.11 & $4.41\times 10^{-5}$ \\
    4000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $4.41\times 10^{-5}$ \\
    5000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 6.54 & $5.44\times 10^{-5}$ \\
    5000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $5.44\times 10^{-5}$ \\
    5000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 6.54 & $1.09\times 10^{-4}$ \\
    5000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $1.09\times 10^{-4}$ \\
    \hline
  \end{tabular}
\end{table}

### 5.2 $\epsilon_{\rm mix}$ の影響

表\ref{tab:results_sweep_massloss_cases}より，同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}=1.0$ と $1.5$ を比較すると，停止時刻は異なる一方で $M_{\rm loss}$ は一致する．供給モデルでは $\epsilon_{\rm mix}$ が供給率のスケールに入るが（手法章 2.3節，式\ref{eq:R_base_definition}），本スイープの範囲では $M_{\rm loss}$ は主に $T_{M,0}$ と $\tau_0$ によって支配される．したがって，$\epsilon_{\rm mix}$ は停止条件（\texttt{loss\_rate\_below\_threshold} の発生）を通じて終了時刻に影響するが，累積損失の値自体にはほとんど影響しない．
