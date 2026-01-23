## 5. 出力と検証

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, marsdisk/io/checkpoint.py, marsdisk/io/archive.py, marsdisk/archive.py
-->

本節では，計算結果を再解析可能な形で保存するための出力仕様と，本文で採用する計算の合格基準（検証）をまとめる．

### 5.1 出力と検証

各ステップの主要診断量（$t,\,\Delta t,\,\tau_{\rm los},\,s_{\rm blow},\,s_{\min},\,\Sigma_{\rm surf},\,\dot{M}_{\rm out}$ など）を時系列として保存し，PSD 履歴 $N_k(t)$ を別途保存する．1D 計算では半径セルごとの時系列を保存するため，任意時刻の円盤全体量は半径積分（離散和）により再構成できる．終端要約には $t_{\rm end}$ までの累積損失 $M_{\rm loss}$ と主要スカラーを含め，質量検査ログを別途記録する．保存情報の要点は付録 Aにまとめる．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する\cite{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示し，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様の規格化量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

検証は質量保存，衝突寿命スケーリング，wavy PSD の定性，IMEX 収束の 4 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．質量保存は式\ref{eq:mass_budget_definition}の $\epsilon_{\rm mass}$ が $0.5\%$ 以下であることを要求する．

衝突寿命スケーリングは推定値 $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\rm los})$ とモデル内 $t_{\rm coll}$ の比が $0.1$–$10$ に入ることを確認する \cite{StrubbeChiang2006_ApJ648_652}．wavy PSD は $s_{\rm blow}$ 近傍の $\log N_k$ の二階差分が符号反転することを指標とし \cite{ThebaultAugereau2007_AA472_169}，IMEX 収束は $\Delta t$ と $\Delta t/2$ の結果差が $1\%$ 以下であることを求める \cite{Krivov2006_AA455_509}．収束判定と PSD 解像度の比較は同一基準で行う．

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
    衝突寿命スケーリング & $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\rm los})$ に対する比が $0.1$–$10$ \\
    wavy PSD & $s_{\rm blow}$ 近傍で $\Delta^2 \log N_k$ の符号が交互に反転 \\
    IMEX 収束 & $\Delta t$ と $\Delta t/2$ の主要時系列差が $1\%$ 以下 \\
    \hline
  \end{tabular}
\end{table}

以上の出力仕様と検証基準により，結果の再現性（入力→出力の対応）と数値的健全性（質量保存・解像度）を担保したうえで，本論文の結果・議論を構成する．
