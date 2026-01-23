## 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

本付録では，本研究で使用した主要な設定キーと物理の対応を表\ref{tab:app_config_physics_map}にまとめる．完全な設定スキーマは付属するコードに含め，論文本文では必要な範囲のみを示す．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{設定キーと物理の対応}
  \label{tab:app_config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 本文参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & 3節 \\
    \texttt{radiation.mars\_temperature}\newline \texttt{\_driver}\newline \texttt{.*} & 冷却ドライバ & 3節 \\
    \texttt{sizes.*} & 粒径グリッド（$s_{\min,\rm cfg},s_{\max},n_{\rm bins}$） & 3.1節, 3.3節 \\
    \texttt{shielding.mode} & 遮蔽 $\Phi$ & 2.2節 \\
    \texttt{sinks.mode} & 昇華/ガス抗力（追加シンク） & 2.5節 \\
    \texttt{blowout.enabled} & ブローアウト損失 & 2.1節 \\
    \texttt{supply.mode} & 表層供給 & 2.3節 \\
    \texttt{supply.mixing.epsilon\_mix} & 混合係数 $\epsilon_{\rm mix}$ & 2.3節, 3.3節 \\
    \texttt{optical\_depth.*} & 初期$\tau_0$規格化と停止判定 & 3.1節, 4.2節 \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & 4.2節 \\
    \hline
  \end{tabular}
\end{table}
