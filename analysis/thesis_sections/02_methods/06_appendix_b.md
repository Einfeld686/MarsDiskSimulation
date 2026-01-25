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
  \begin{tabular}{p{0.42\textwidth} p{0.28\textwidth} p{0.20\textwidth}}
    \hline
    設定キー & 物理 & 本文参照 \\
    \hline
    \multicolumn{3}{l}{\textbf{入力・幾何}} \\
    \texttt{geometry.mode}, \texttt{geometry.Nr} & 0D/1D と半径セル数 & 1.2節, 4.1節 \\
    \texttt{disk.geometry.r\_in\_RM}, \texttt{disk.geometry.r\_out\_RM} & 計算領域 $[r_{\rm in},r_{\rm out}]$ & 1.2節, 3.1節 \\
    \texttt{inner\_disk\_mass.*} & 内側円盤質量 $M_{\rm in}$ & 3.1節 \\
    \texttt{initial.*} & 初期 PSD/表層状態 & 3.1節 \\
    \hline
    \multicolumn{3}{l}{\textbf{粒径グリッド・PSD}} \\
    \texttt{sizes.s\_min}, \texttt{s\_max}, \texttt{n\_bins} & サイズビン範囲と解像度 & 3.1節, 4.1節 \\
    \texttt{psd.alpha} & PSD の傾き（基準形状） & 2.4節, 3.3節 \\
    \texttt{psd.wavy\_strength} & ``wavy'' 補正の強さ & 2.4節 \\
    \texttt{psd.floor.*} & PSD 下限 $s_{\min}$ の扱い & 2.1節, 3.1節 \\
    \hline
    \multicolumn{3}{l}{\textbf{衝突（速度・破壊強度）}} \\
    \texttt{dynamics.e0}, \texttt{i0} & 相対速度スケール（励起） & 2.4節, 3.3節 \\
    \texttt{dynamics.f\_wake} & wake 係数（速度分散の補正） & 2.4節 \\
    \texttt{qstar.*} & $Q_D^*(s)$（破壊閾値） & 2.4節, 3.3節 \\
    \hline
    \multicolumn{3}{l}{\textbf{放射圧・ブローアウト}} \\
    \texttt{radiation.TM\_K} & 火星温度（定数入力） & 2.1節 \\
    \texttt{radiation.mars\_temperature\_driver.*} & 火星温度 $T_M(t)$（非定常） & 2.1節, 付録 C \\
    \texttt{radiation.qpr\_table\_path} & $\langle Q_{\rm pr}\rangle$ テーブル & 2.1節, 付録 C \\
    \texttt{chi\_blow}, \texttt{blowout.*} & ブローアウト滞在時間と適用層 & 2.1節 \\
    \hline
    \multicolumn{3}{l}{\textbf{遮蔽・光学的厚さ}} \\
    \texttt{shielding.mode}, \texttt{shielding.table\_path} & 遮蔽 $\Phi$ とテーブル & 2.2節, 付録 C \\
    \texttt{optical\_depth.tau0\_target} & 初期 $\tau_0$ の規格化 & 3.1節 \\
    \texttt{optical\_depth.tau\_stop} & 適用範囲判定（停止） & 4.2節, 4.3節 \\
    \hline
    \multicolumn{3}{l}{\textbf{供給・追加シンク}} \\
    \texttt{supply.mode} & 表層供給モデル & 2.3節 \\
    \texttt{supply.mixing.epsilon\_mix} & 混合係数 $\epsilon_{\rm mix}$ & 2.3節, 3.3節 \\
    \texttt{sinks.mode} & 追加シンク（昇華/ガス抗力など） & 2.5節 \\
    \texttt{sinks.sub\_params.*} & 昇華（HKL）係数と設定 & 2.5節, 3.2節, 付録 C \\
    \hline
    \multicolumn{3}{l}{\textbf{数値設定}} \\
    \texttt{numerics.dt\_init}, \texttt{numerics.safety} & 時間刻みの初期値と安全率 & 4.2節 \\
    \texttt{numerics.dt\_over\_t\_blow\_max} & $\Delta t/t_{\rm blow}$ 制約 & 4.2節 \\
    \texttt{numerics.t\_end\_years} & 積分終端（年） & 4.2節 \\
    \texttt{numerics.t\_end\_until\_temperature\_K} & 積分終端（温度到達） & 4.2節 \\
    \hline
  \end{tabular}
\end{table}
