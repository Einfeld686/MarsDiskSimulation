### 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

設定と物理の対応を次の表にまとめる．

\begin{table}[t]
  \centering
  \caption{設定キーと物理の対応}
  \label{tab:app_config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 本文参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & 2.2.1節 \\
    \texttt{radiation.mars\_temperature}\newline \texttt{\_driver}\newline \texttt{.*} & 冷却ドライバ & 2.2.1節 \\
	    \texttt{shielding.mode} & 遮蔽 $\Phi$ & 2.2.3節 \\
	    \texttt{shielding.los\_geometry}\newline \texttt{.*} & 視線補正係数 $f_{\rm los}$ & 2.1.2節 \\
	    \texttt{sinks.mode} & 昇華/ガス抗力 & 2.2.5節 \\
	    \texttt{blowout.enabled} & ブローアウト損失 & 2.2.2節 \\
	    \texttt{supply.mode} & 表層再供給 & 3.1節 \\
    \texttt{supply.feedback}\newline \texttt{.*} & $\tau$フィードバック制御 & 3.1.1節 \\
    \texttt{supply.temperature}\newline \texttt{.*} & 温度カップリング & 3.1.2節 \\
    \texttt{supply.reservoir}\newline \texttt{.*} & 有限質量リザーバ & 3.1.3節 \\
    \texttt{supply.transport}\newline \texttt{.*} & 深層ミキシング & 3.1.3節 \\
    \texttt{init\_tau1.*} & 初期$\tau=1$スケーリング & 4.2.3.1節 \\
    \texttt{phase.*} & 相判定 & 2.2.4節 \\
    \texttt{phase.q\_abs\_mean} & $\langle Q_{\rm abs}\rangle$（粒子温度） & 2.2.4節 \\
    \texttt{numerics.checkpoint.*} & チェックポイント & 4.2.3.3節 \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & 4.2.3.2節 \\
    \texttt{ALLOW\_TL2003} & gas-rich 表層 ODE トグル & 2.2.3節 \\
    \texttt{psd.wavy\_strength} & "wavy" 強度（0 で無効） & 2.1.1節 \\
    \hline
  \end{tabular}
\end{table}

#### B.1 粒径グリッド（既定値）

\begin{table}[t]
  \centering
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

表\ref{tab:app_psd_grid_defaults}の既定値では $s$ 範囲が広いため，対数等間隔の隣接比 $s_{k+1}/s_k$ は $O(1.5)$ となる．$s_{\rm blow}$ 近傍の解像度が必要な場合は $n_{\rm bins}$ を増やすか，対象とする $s_{\max}$ を再検討する（2.1.1節，5.1.2節）．

#### B.2 初期化（$\tau=1$ スケーリング）

\begin{table}[t]
  \centering
  \caption{初期 $\tau=1$ スケーリングの設定}
  \label{tab:app_init_tau1_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.3\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{init\_tau1.scale\_to\_tau1} & 有効化フラグ & \texttt{false} \\
    \texttt{init\_tau1.tau\_field} & \texttt{vertical} / \texttt{los} & \texttt{los} \\
    \texttt{init\_tau1.target\_tau} & 目標光学的厚さ & 1.0 \\
    \hline
  \end{tabular}
\end{table}

#### B.3 供給（フィードバック・温度カップリング・注入）

\begin{table}[t]
  \centering
  \caption{供給フィードバックの設定}
  \label{tab:app_supply_feedback_settings}
  \begin{tabular}{p{0.4\textwidth} p{0.36\textwidth} p{0.14\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.feedback.target\_tau} & 目標光学的厚さ & 0.9 \\
    \texttt{supply.feedback.gain} & 比例ゲイン & 1.2 \\
    \texttt{supply.feedback.response}\newline \texttt{\_time\_years} & 応答時定数 [yr] & 0.4 \\
    \texttt{supply.feedback.tau\_field} & $\tau$ 評価フィールド (\texttt{tau\_los}) & \texttt{tau\_los} \\
    \texttt{supply.feedback.min\_scale}\newline \texttt{supply.feedback.max\_scale} & スケール係数の上下限 & 1e-6 / 10.0 \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \caption{温度カップリングの設定}
  \label{tab:app_supply_temperature_settings}
  \begin{tabular}{p{0.46\textwidth} p{0.44\textwidth}}
    \hline
    設定キー & 意味 \\
    \hline
    \texttt{supply.temperature.reference\_K} & 基準温度 [K] \\
    \texttt{supply.temperature.exponent} & べき指数 $\alpha$ \\
    \texttt{supply.temperature.floor}\newline \texttt{supply.temperature.cap} & スケール係数の下限・上限 \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \caption{注入パラメータの設定}
  \label{tab:app_supply_injection_settings}
  \begin{tabular}{p{0.40\textwidth} p{0.32\textwidth} p{0.18\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.injection.mode} & \texttt{min\_bin}\newline \texttt{powerlaw\_bins} & \texttt{powerlaw\_bins} \\
    \texttt{supply.injection.q} & べき指数（衝突カスケード断片） & 3.5 \\
    \texttt{supply.injection.s\_inj}\newline \texttt{\_min}\newline \texttt{supply.injection.s\_inj}\newline \texttt{\_max} & 注入サイズ範囲 [m] & 自動 \\
    \texttt{supply.injection.velocity}\newline \texttt{.mode} & \texttt{inherit} / \texttt{fixed\_ei}\newline \texttt{/ factor} & \texttt{inherit} \\
    \hline
  \end{tabular}
\end{table}

#### B.4 診断（エネルギー簿記）

	\begin{table}[t]
	  \centering
	  \caption{エネルギー簿記に関連する設定キー}
	  \label{tab:app_energy_settings}
	  \begin{tabular}{p{0.36\textwidth} p{0.38\textwidth} l}
	    \hline
	    設定キー & 意味 & 既定値 \\
	    \hline
	    \texttt{dynamics.eps\_restitution} & 反発係数（$f_{ke,\rm frag}$ のデフォルトに使用） & 0.5 \\
	    \texttt{dynamics.f\_ke\_cratering} & 侵食時の非散逸率 & 0.1 \\
	    \texttt{dynamics.f\_ke\_fragmentation} & 破砕時の非散逸率 & None（$\varepsilon^2$ 使用） \\
	    \texttt{diagnostics.energy}\newline \texttt{\_bookkeeping}\newline \texttt{.stream} & energy 系列/簿記をストリーム出力 & true \\
	    \hline
	  \end{tabular}
		\end{table}

#### B.5 視線幾何（$f_{\rm los}$）

$f_{\rm los}$ は垂直光学厚 $\tau_\perp$ から火星視線方向光学厚 $\tau_{\rm los}=f_{\rm los}\tau_\perp$ を近似する補正係数である（2.1.2節）．実装では次の設定により
\[
f_{\rm los}=
\begin{cases}
\max\!\left(1,\dfrac{{\rm path\_multiplier}}{H/r}\right), & {\rm mode}=\texttt{aspect\_ratio\_factor},\\
1, & {\rm mode}=\texttt{none}
\end{cases}
\]
として与える．

\begin{table}[t]
  \centering
  \caption{視線補正係数 $f_{\rm los}$ の設定（\texttt{shielding.los\_geometry}）}
  \label{tab:los_geometry_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.34\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{shielding.los\_geometry.mode} & \texttt{aspect\_ratio\_factor} / \texttt{none} & \texttt{aspect\_ratio\_factor} \\
    \texttt{shielding.los\_geometry.h\_over\_r} & アスペクト比 $H/r$ & 1.0 \\
    \texttt{shielding.los\_geometry.path\_multiplier} & 視線方向の光路長係数 & 1.0 \\
    \hline
  \end{tabular}
\end{table}


---
