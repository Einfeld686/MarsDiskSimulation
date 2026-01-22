## 5. 出力

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, marsdisk/io/checkpoint.py, marsdisk/io/archive.py, marsdisk/archive.py
-->

各ステップの主要診断量（$t,\,\Delta t,\,\tau_{\rm los},\,s_{\rm blow},\,s_{\min},\,\Sigma_{\rm surf},\,\dot{M}_{\rm out}$ など）を時系列として保存し，PSD 履歴 $N_k(t)$ を別途保存する．終端要約には 2 年累積損失 $M_{\rm loss}$ と主要スカラーを含め，質量検査ログは別ファイルに記録する．出力ファイルと主要カラムの一覧は付録Aに示す．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する．質量や流出率は $M_{\rm Mars}$ で規格化した値も併記する．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

## 6. 検証

検証は質量保存，衝突寿命スケーリング，wavy PSD の定性，IMEX 収束の4項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果は全て基準を満たした計算に限定する．質量保存は式\ref{eq:mass_budget_definition}の $\epsilon_{\rm mass}$ が $0.5\%$ 以下であることを要求する．

衝突寿命スケーリングは推定値 $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\perp})$ とモデル内 $t_{\rm coll}$ の比が $0.1$–$10$ に入ることを確認する \cite{StrubbeChiang2006_ApJ648_652}．wavy PSD は $s_{\rm blow}$ 近傍の $\log N_k$ の二階差分が符号反転することを指標とし \cite{ThebaultAugereau2007_AA472_169}，IMEX 収束は $\Delta t$ と $\Delta t/2$ の結果差が $1\%$ 以下であることを求める \cite{Krivov2006_AA455_509}．収束判定と PSD 解像度の比較は同一基準で行う．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{検証項目と合格基準}
  \label{tab:validation_criteria}
  \begin{tabular}{p{0.27\textwidth} p{0.69\textwidth}}
    \hline
    検証項目 & 合格基準（許容誤差） \\
    \hline
    質量保存 & 相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下 \\
    衝突寿命スケーリング & $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\perp})$ に対する比が $0.1$–$10$ \\
    wavy PSD & $s_{\rm blow}$ 近傍で $\Delta^2 \log N_k$ の符号が交互に反転 \\
    IMEX 収束 & $\Delta t$ と $\Delta t/2$ の主要時系列差が $1\%$ 以下 \\
    \hline
  \end{tabular}
\end{table}
