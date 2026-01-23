## 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

設定と物理の対応を次の表にまとめる．

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
	    \texttt{shielding.mode} & 遮蔽 $\Phi$ & 2.2節 \\
		    \texttt{sinks.mode} & 昇華/ガス抗力 & 2.5節 \\
		    \texttt{blowout.enabled} & ブローアウト損失 & 2.1節 \\
		    \texttt{supply.mode} & 表層再供給 & 2.3節 \\
	    \texttt{supply.mixing.epsilon\_mix} & 混合係数 $\epsilon_{\rm mix}$ & 2.3節 \\
	    \texttt{optical\_depth.*} & 初期$\tau_0$規格化と停止判定 & 3.1節 \\
	    \texttt{phase.*} & 相判定 & 本文では扱わない \\
	    \texttt{phase.q\_abs\_mean} & $\langle Q_{\rm abs}\rangle$（粒子温度） & 本文では扱わない \\
	    \texttt{numerics.checkpoint.*} & チェックポイント & 本文では扱わない \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & 4.2節 \\
    \texttt{psd.wavy\_strength} & "wavy" 強度（0 で無効） & 5.1節 \\
    \hline
  \end{tabular}
\end{table}

### B.1 粒径グリッド（既定値）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{PSD グリッドの既定値}
  \label{tab:app_psd_grid_defaults}
  \begin{tabular}{p{0.36\textwidth} p{0.2\textwidth} p{0.32\textwidth}}
    \hline
    設定キー & 既定値 & 意味 \\
    \hline
    \texttt{sizes.s\_min} & 1e-7 m & 最小粒径 $s_{\min,\rm cfg}$ \\
    \texttt{sizes.s\_max} & 3.0 m & 最大粒径 \\
    \texttt{sizes.n\_bins} & 40 & サイズビン数 \\
    \hline
  \end{tabular}
\end{table}

表\ref{tab:app_psd_grid_defaults}の既定値では $s$ 範囲が広いため，対数等間隔の隣接比 $s_{k+1}/s_k$ は $O(1.5)$ となる．$s_{\rm blow}$ 近傍の解像度が必要な場合は $n_{\rm bins}$ を増やすか，対象とする $s_{\max}$ を再検討する（1節，5.1節）．

### B.2 初期化（$\tau_0$ 規格化と停止判定）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{初期 $\tau_0$ 規格化と停止判定の設定}
  \label{tab:app_optical_depth_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.3\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{optical\_depth.tau0\_target} & 初期 $\tau_{\rm los}(t_0)$ の目標値 & 1.0 \\
    \texttt{optical\_depth.tau\_stop} & 停止判定の閾値（$\tau_{\rm los}$） & 2.302585 \\
    \texttt{optical\_depth.tau\_stop\_tol} & 停止判定の許容（$1+\mathrm{tol}$） & 1e-6 \\
    \texttt{optical\_depth.tau\_field} & $\tau$ 評価フィールド & \texttt{tau\_los} \\
    \hline
  \end{tabular}
\end{table}

### B.3 供給（設定）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{表層供給の設定（供給率と注入モード）}
  \label{tab:app_supply_settings}
  \begin{tabular}{p{0.46\textwidth} p{0.3\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.mode} & 供給率の入力形式 & \texttt{const} \\
    \texttt{supply.const.prod\_area\_rate\_kg\_m2\_s} & 定常供給率（面密度） & 0.0 \\
    \texttt{supply.table.path} & 供給率テーブル（任意） & \texttt{data/supply\_rate.csv} \\
    \texttt{supply.mixing.epsilon\_mix} & 混合係数 $\epsilon_{\rm mix}$ & 1.0 \\
    \texttt{supply.injection.mode} & 注入モード & \texttt{initial\_psd} \\
    \hline
  \end{tabular}
\end{table}

### B.4 診断（エネルギー簿記）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{エネルギー簿記に関連する設定キー}
  \label{tab:app_energy_settings}
  \begin{tabular}{p{0.36\textwidth} p{0.38\textwidth} l}
	    \hline
	    設定キー & 意味 & 既定値 \\
	    \hline
	    \texttt{dynamics.eps\_restitution} & 反発係数（$f_{ke,\rm frag}$ のデフォルトに使用） & 0.5 \\
	    \texttt{dynamics.f\_ke\_cratering} & 侵食時の非散逸率 & 0.1 \\
    \path{dynamics.f_ke_fragmentation} & 破砕時の非散逸率 & None（$\varepsilon^2$ 使用） \\
	    \texttt{diagnostics.energy}\newline \texttt{\_bookkeeping}\newline \texttt{.stream} & energy 系列/簿記をストリーム出力 & true \\
	    \hline
	  \end{tabular}
		\end{table}
