## 付録 C. 外部入力（テーブル）一覧

<!--
実装(.py): marsdisk/run.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/tempdriver.py
-->

本モデルは，物性や放射輸送に関する外部テーブルを読み込み，本文中の式で用いる物理量（$T_M$, $\langle Q_{\rm pr}\rangle$, $\Phi$ など）を与える．論文ではテーブルの数値そのものを列挙せず，外部入力の役割と参照先を表として整理する．実行時に採用したテーブルの出典と補間範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする（付録 A）．

主要な外部入力を表\ref{tab:app_external_inputs}に，設定により追加で参照する外部入力を表\ref{tab:app_external_inputs_optional}に示す．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{外部入力（基本）とモデル内での役割}
  \label{tab:app_external_inputs}
  \begin{tabular}{p{0.26\textwidth} p{0.54\textwidth} p{0.16\textwidth}}
    \hline
    外部入力 & 役割（モデル内での使い方） & 設定キー（代表） \\
    \hline
    火星温度履歴 $T_M(t)$ &
    放射圧（$\beta,\,s_{\rm blow}$）と昇華の外部ドライバ &
    \texttt{radiation.mars\_temperature\_driver.*} \\
    Planck 平均 $\langle Q_{\rm pr}\rangle(s,T_M)$ &
    放射圧効率として $\beta$ と $s_{\rm blow}$ を決める &
    \texttt{radiation.qpr\_table\_path} \\
    遮蔽係数 $\Phi$ &
    $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ を通じて自己遮蔽を表現する（遮蔽有効時） &
    \texttt{shielding.table\_path} \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{外部入力（オプション）}
  \label{tab:app_external_inputs_optional}
  \begin{tabular}{p{0.26\textwidth} p{0.54\textwidth} p{0.16\textwidth}}
    \hline
    外部入力 & 役割（モデル内での使い方） & 設定キー（代表） \\
    \hline
    供給率テーブル $\dot{\Sigma}_{\rm in}(t)$ &
    表層供給率を外部から与える（\texttt{supply.mode=table} のとき） &
    \texttt{supply.table.path} \\
    飽和蒸気圧テーブル $P_{\rm sat}(T)$ &
    昇華フラックスの入力として飽和蒸気圧をテーブル補間で与える（\texttt{psat\_model=tabulated} のとき） &
    \texttt{sinks.sub\_params.psat\_table\_path} \\
    \hline
  \end{tabular}
\end{table}
