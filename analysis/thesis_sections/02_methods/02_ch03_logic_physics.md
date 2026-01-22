## 3. 初期条件・境界条件・パラメータ採用値

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

初期条件は $t=t_0$ における PSD $N_k(t_0)$ と内側円盤質量 $M_{\rm in}(t_0)$ で与える．初期 PSD は総質量または光学的厚さ $\tau_0$ により規格化し，標準では $\tau_{\rm los}=1$ を満たすように一様スケーリングする．基準計算では melt lognormal mixture を用い，採用値は表\ref{tab:methods_initial_psd_params}に示す．

火星温度 $T_M(t)$ は外部ドライバとして与え，$\langle Q_{\rm pr}\rangle$ と $\Phi$ のテーブルは付録Cの外部入力を用いる．基準計算では $T_M(t)$ を \texttt{data/mars\_temperature\_T4000p0K.csv}（時間単位 day）で補間し，$\langle Q_{\rm pr}\rangle$ は \texttt{data/qpr\_planck\_forsterite\_mie.csv} を用いる．物性値（$\rho$，HKL 係数など）と基準ケースの採用値は表\ref{tab:methods_baseline_params}と表\ref{tab:methods_qdstar_coeffs}に整理する．感度掃引に用いる追加パラメータは付録Aにまとめる．

サイズ境界は $s\in[s_{\min},s_{\max}]$ とし，$s_{\min,\rm eff}$ 未満は存在しない（ブローアウトで即時除去）．0D では計算領域 $[r_{\rm in},r_{\rm out}]$ を面積 $A$ の環状領域として扱い，半径方向拡散は標準計算では無効とする．

\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{基準計算の採用値（幾何・力学・供給）}
  \label{tab:methods_baseline_params}
  \begin{tabular}{p{0.3\textwidth} p{0.22\textwidth} p{0.12\textwidth} p{0.26\textwidth}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $r_{\rm in}$ & 1.0 & $R_{\rm Mars}$ & 内端半径 \\
    $r_{\rm out}$ & 2.7 & $R_{\rm Mars}$ & 外端半径 \\
    $M_{\rm in}$ & $3.0\times10^{-5}$ & $M_{\rm Mars}$ & 内側円盤質量 \\
    $M_{\rm tot,0}$ & $1.0\times10^{-7}$ & $M_{\rm Mars}$ & 初期総質量 \\
    $s_{\min}$ & $1.0\times10^{-7}$ & m & PSD 下限 \\
    $s_{\max}$ & $3.0$ & m & PSD 上限 \\
    $n_{\rm bins}$ & 40 & -- & サイズビン数 \\
    $\tau_0$ & 1.0 & -- & 初期規格化 \\
    $\tau_{\rm stop}$ & 2.302585 & -- & 停止判定（$\ln 10$） \\
    $f_{\rm los}$ & 1.0 & -- & $H/r=1$，path\_multiplier=1 \\
    $\Phi$ & 1.0 & -- & 基準計算の遮蔽 \\
    $e_0$ & 0.5 & -- & 離心率 \\
    $i_0$ & 0.05 & -- & 傾斜角 \\
    $H_{\rm factor}$ & 1.0 & -- & $H_k=H_{\rm factor} i r$ \\
    $\chi_{\rm blow}$ & auto & -- & $\beta$ と $Q_{\rm pr}$ から評価 \\
    $t_{\rm end}$ & 2.0 & yr & 積分期間 \\
    $\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数 \\
    $\dot{\Sigma}_{\rm prod}$ & 0.0 & kg\,m$^{-2}$\,s$^{-1}$ & 供給率（定常） \\
    $\alpha_{\rm frag}$ & 3.5 & -- & 破片分布指数 \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & フォルステライト \cite{VanLieshoutMinDominik2014_AA572_A76} \\
    \hline
  \end{tabular}
\end{table}

$s_{\rm cut}$ は凝縮粒子を除外するためのカットオフ粒径であり，$s_{\rm min,solid}$ と $s_{\rm max,solid}$ は固相 PSD の範囲を定める．${\rm width}_{\rm dex}$ は両成分に共通の対数幅（dex）である．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{基準計算の初期 PSD（melt lognormal mixture）}
  \label{tab:methods_initial_psd_params}
  \begin{tabular}{p{0.36\textwidth} p{0.22\textwidth} p{0.2\textwidth}}
    \hline
    記号 & 値 & 単位 \\
    \hline
    $f_{\rm fine}$ & 0.03 & -- \\
    $s_{\rm fine}$ & $1.0\times10^{-7}$ & m \\
    $s_{\rm meter}$ & 1.5 & m \\
    ${\rm width}_{\rm dex}$ & 0.3 & -- \\
    $s_{\rm cut}$ & $1.0\times10^{-7}$ & m \\
    $s_{\rm min,solid}$ & $1.0\times10^{-4}$ & m \\
    $s_{\rm max,solid}$ & 3.0 & m \\
    $\alpha_{\rm solid}$ & 3.5 & -- \\
    \hline
  \end{tabular}
\end{table}

表\ref{tab:methods_qdstar_coeffs}の係数は $f_{Q^*}=5.574$ のスケールを適用した値であり，$Q_s$ と $B$ に反映されている．速度補間の詳細は衝突カスケード節で用いる補間則に従う．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{基準計算の $Q_D^*$ 係数（$v_{\rm ref}$ は km/s，$Q_s$ と $B$ は BA99 cgs 単位）}
  \label{tab:methods_qdstar_coeffs}
  \begin{tabular}{p{0.16\textwidth} p{0.2\textwidth} p{0.16\textwidth} p{0.2\textwidth} p{0.16\textwidth}}
    \hline
    $v_{\rm ref}$ & $Q_s$ & $a_s$ & $B$ & $b_g$ \\
    \hline
    1 & 1.9509e8 & 0.38 & 0.8187652527440811 & 1.36 \\
    2 & 1.9509e8 & 0.38 & 1.28478039442684 & 1.36 \\
    3 & 1.9509e8 & 0.38 & 1.6722 & 1.36 \\
    4 & 2.92635e8 & 0.38 & 2.2296 & 1.36 \\
    5 & 3.9018e8 & 0.38 & 2.787 & 1.36 \\
    6 & 3.9018e8 & 0.38 & 3.137652034251613 & 1.36 \\
    7 & 3.9018e8 & 0.38 & 3.4683282387928047 & 1.36 \\
    \hline
  \end{tabular}
\end{table}
