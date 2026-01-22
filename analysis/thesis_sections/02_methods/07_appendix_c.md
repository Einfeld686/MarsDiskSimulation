### 付録 C. 外部入力（テーブル）一覧

<!--
実装(.py): marsdisk/run.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/tempdriver.py
-->

本モデルは，物性や放射輸送に関する外部テーブルを読み込み，本文中の式で用いる物理量（$T_M$, $\langle Q_{\rm pr}\rangle$, $\Phi$ など）を与える．論文ではテーブルの数値そのものを列挙せず，役割と参照先を表\ref{tab:external_inputs}にまとめる．実行時に採用したテーブルの出典と補間範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする（付録A）．

\begin{table}[t]
  \centering
  \caption{外部入力（テーブル）とモデル内での役割}
  \label{tab:external_inputs}
  \begin{tabular}{p{0.22\textwidth} p{0.46\textwidth} p{0.24\textwidth}}
    \hline
    外部入力 & 役割 & 本文参照（代表） \\
    \hline
    火星温度履歴 $T_M(t)$ &
    放射圧（β, $s_{\rm blow}$）・昇華・相判定の入力となる温度ドライバ &
    2.2.1節 \\
    Planck 平均 $\langle Q_{\rm pr}\rangle$ &
    放射圧効率として β と $s_{\rm blow}$ を決める（灰色体近似は例外） &
    2.2.2節 \\
    遮蔽係数 $\Phi(\tau_{\rm los})$（本研究では $\Phi=\exp(-\tau_{\rm los})$） &
    有効不透明度 $\kappa_{\rm eff}$ を通じて遮蔽と供給フィードバックに入る &
    2.2.3節 \\
    \hline
  \end{tabular}
\end{table}


---
