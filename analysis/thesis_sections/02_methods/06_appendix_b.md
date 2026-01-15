### 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

設定と物理の対応を次の表にまとめる。

\begin{table}[t]
  \centering
  \caption{設定キーと物理の対応}
  \label{tab:config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 詳細参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & config\_guide §3.2 \\
    \texttt{radiation.mars\_temperature}\newline \texttt{\_driver}\newline \texttt{.*} & 冷却ドライバ & config\_guide §3.2 \\
    \texttt{shielding.mode} & 遮蔽 $\Phi$ & config\_guide §3.4 \\
    \texttt{sinks.mode} & 昇華/ガス抗力 & config\_guide §3.6 \\
    \texttt{blowout.enabled} & ブローアウト損失 & config\_guide §3.9 \\
    \texttt{supply.mode} & 表層再供給 & config\_guide §3.7 \\
    \texttt{supply.feedback}\newline \texttt{.*} & $\tau$フィードバック制御 & config\_guide §3.7 \\
    \texttt{supply.temperature}\newline \texttt{.*} & 温度カップリング & config\_guide §3.7 \\
    \texttt{supply.reservoir}\newline \texttt{.*} & 有限質量リザーバ & config\_guide §3.7 \\
    \texttt{supply.transport}\newline \texttt{.*} & 深層ミキシング & config\_guide §3.7 \\
    \texttt{init\_tau1.*} & 初期$\tau=1$スケーリング & config\_guide §3.3 \\
    \texttt{phase.*} & 相判定 & config\_guide §3.8 \\
    \texttt{numerics.checkpoint.*} & チェックポイント & config\_guide §3.1 \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & config\_guide §3.1 \\
    \texttt{ALLOW\_TL2003} & gas-rich 表層 ODE トグル & config\_guide §3.6, §3.9 \\
    \texttt{psd.wavy\_strength} & "wavy" 強度（0 で無効） & config\_guide §3.3 \\
    \hline
  \end{tabular}
\end{table}

完全な設定キー一覧は analysis/config_guide.md を参照。


---
