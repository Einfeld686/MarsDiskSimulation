## 4. 検証：質量保存と停止条件

本節では，結果の信頼性を担保するために，（i）質量保存，（ii）停止条件の内訳を確認する．

### 4.1 質量保存（質量収支ログ）

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける質量保存誤差（相対誤差％）の時系列．}
  \label{fig:results_mass_budget_error}
\end{figure}

スイープ 16 ケースでは，質量保存誤差の最大値は $7\times 10^{-15}\%$ 程度であり，許容誤差 $0.5\%$ を十分に下回る．したがって，本章で報告する $M_{\rm loss}$ は収支誤差によって支配されていない．

\begin{table}[t]
  \centering
  \caption{質量保存誤差の要約（スイープ 16 ケース）}
  \label{tab:results_mass_budget_summary}
  \begin{tabular}{lc}
    \hline
    指標 & 値 \\
    \hline
    最大誤差（16 ケース中） & $6.81\times 10^{-15}\%$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 停止条件の内訳

本章のスイープでは，停止は二種類に分類された．（i）$T_M=2000\,\mathrm{K}$ 到達（$t_{\rm end}$ 到達），（ii）$\tau_{\rm eff}$ が $\tau_{\rm stop}=2.30$ を超過したための早期停止である．停止条件の違いは累積損失の積分区間を変えるため，感度解析の解釈に影響する．

\begin{table}[t]
  \centering
  \caption{停止条件の内訳（スイープ 16 ケース）}
  \label{tab:results_stop_reason_counts}
  \begin{tabular}{lc}
    \hline
    停止理由 & ケース数 \\
    \hline
    $T_M=2000\,\mathrm{K}$ 到達（$t_{\rm end}$） & 8 \\
    $\tau_{\rm eff}>\tau_{\rm stop}$（早期停止） & 8 \\
    \hline
  \end{tabular}
\end{table}
