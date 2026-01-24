## 4. 検証：質量保存と停止条件

本節では，結果の信頼性を担保するために，（i）質量保存，（ii）停止条件の内訳を確認する．

### 4.1 質量保存（質量収支ログ）

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau1p0.png}
  \caption{質量保存誤差（相対誤差％）の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．各パネルは $(T_{M,0},\epsilon_{\rm mix})$ の組に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_mass_budget_error_grid}
\end{figure}

スイープ 12 ケースでは，質量保存誤差の最大値は $8.72\times 10^{-14}\%$ 程度であり，許容誤差 $0.5\%$ を十分に下回る．したがって，本章で報告する $M_{\rm loss}$ は収支誤差によって支配されていない．

ここでいう質量保存誤差は，手法章で定義した $\epsilon_{\rm mass}$（式\ref{eq:mass_budget_definition}）に対応するものであり，各内部ステップでの収支ずれが $0.5\%$ 以内となるよう時間刻みを制御している．

\begin{table}[t]
  \centering
  \caption{質量保存誤差の要約（スイープ 12 ケース）}
  \label{tab:results_mass_budget_summary}
  \begin{tabular}{lc}
    \hline
    指標 & 値 \\
    \hline
    最大誤差（12 ケース中） & $8.72\times 10^{-14}\%$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 停止条件の内訳

本章のスイープでは，停止は二種類に分類された．（i）所定の終了時刻（温度ドライバにより決まる $t_{\rm end}$）への到達（\texttt{t\_end\_reached}），（ii）全円盤の流出率が閾値未満となったための打ち切り（\texttt{loss\_rate\_below\_threshold}）である．手法章で述べた $\tau_{\rm los}>\tau_{\rm stop}$ による早期停止は，本スイープでは発生しなかった．

本スイープでは後者はいずれも $t\simeq 2\,\mathrm{yr}$ で停止したが，図\ref{fig:results_cumloss_grid}に示したとおり $M_{\rm loss}(t)$ は初期に飽和する．また，$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で $\dot{M}_{\rm out}$ を積分して更新するため，$\dot{M}_{\rm out}\approx 0$ の区間を延長しても $M_{\rm loss}$ の増分は無視できる．したがって，この打ち切りは $M_{\rm loss}$ の最終値に対する影響が小さい（5節）．

\begin{table}[t]
  \centering
  \caption{停止条件の内訳（スイープ 12 ケース）}
  \label{tab:results_stop_reason_counts}
  \begin{tabular}{lc}
    \hline
    停止理由 & ケース数 \\
    \hline
    \texttt{t\_end\_reached}（終了時刻到達） & 6 \\
    \texttt{loss\_rate\_below\_threshold}（流出率閾値以下） & 6 \\
    \hline
  \end{tabular}
\end{table}
