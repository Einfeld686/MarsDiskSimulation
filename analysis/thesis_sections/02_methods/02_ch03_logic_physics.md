## 3. 初期条件・境界条件・パラメータ採用値

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

初期条件は $t=t_0$ における PSD $N_k(t_0)$ と内側円盤質量 $M_{\rm in}(t_0)$ で与える．初期 PSD は総質量または光学的厚さ $\tau_0$ により規格化し，標準では $\tau_{\rm los}=1$ を満たすように一様スケーリングする．

火星温度 $T_M(t)$ は外部ドライバとして与え，$\langle Q_{\rm pr}\rangle$ と $\Phi$ のテーブルは付録Cの外部入力を用いる．物性値（$\rho$，$\langle Q_{\rm pr}\rangle$ テーブル，HKL 係数など）と基準ケースの採用値は表\ref{tab:methods_baseline_params}と付録Aに整理する．感度掃引に用いる追加パラメータは付録Aにまとめる．

サイズ境界は $s\in[s_{\min},s_{\max}]$ とし，$s_{\min,\rm eff}$ 未満は存在しない（ブローアウトで即時除去）．0D では計算領域 $[r_{\rm in},r_{\rm out}]$ を面積 $A$ の環状領域として扱い，半径方向拡散は標準計算では無効とする．

\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}

\begin{table}[t]
  \centering
  \caption{基準計算の採用値（主要パラメータ）}
  \label{tab:methods_baseline_params}
  \begin{tabular}{p{0.28\textwidth} p{0.2\textwidth} p{0.16\textwidth} p{0.26\textwidth}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $s_{\min}$ & $1.0\times10^{-7}$ & m & PSD 下限（付録B） \\
    $s_{\max}$ & $3.0$ & m & PSD 上限（付録B） \\
    $n_{\rm bins}$ & 40 & -- & サイズビン数（付録B） \\
    $\tau_0$ & 1.0 & -- & 初期規格化（本研究） \\
    $\chi_{\rm blow}$ & 1.0 & -- & $t_{\rm blow}$ 係数（本研究） \\
    $t_{\rm end}$ & 2.0 & yr & 積分期間（本研究） \\
    $q$ & 3.5 & -- & 注入べき指数（本研究） \\
    $\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数（本研究） \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & フォルステライト \cite{VanLieshoutMinDominik2014_AA572_A76} \\
    \hline
  \end{tabular}
\end{table}
