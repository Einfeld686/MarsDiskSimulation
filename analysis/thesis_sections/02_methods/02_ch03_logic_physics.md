## 3. 初期条件・境界条件・パラメータ

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

本節では，1D 計算における初期条件・サイズ境界・停止条件に関わるパラメータを整理し，基準計算で採用した値を表としてまとめる．

### 3.1 初期条件と境界条件

初期条件は $t=t_0$ における PSD $N_k(t_0)$ と，環状領域 $[r_{\rm in},r_{\rm out}]$ の幾何・温度入力で与える．1D 計算では初期表層面密度 $\Sigma_{\rm surf}(t_0,r)$ を，目標光学的厚さ $\tau_0$ を満たすように一様に規格化する．基準計算では melt lognormal mixture を用い，採用値は表\ref{tab:methods_initial_psd_params}に示す．

火星温度 $T_M(t)$ は外部ドライバとして与え，$\langle Q_{\rm pr}\rangle$ と $\Phi$ は外部入力として与える（付録 C，表\ref{tab:app_external_inputs}）．

サイズ境界は $s\in[s_{\min,\rm cfg},s_{\max}]$ とし，$s_{\min,\rm eff}$ 未満は存在しない（ブローアウトで即時除去）．

\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}

ここで $A$ は面密度と質量の換算に用いる幾何学的定義であり，環状近似に基づく 0D/1D の取り扱いと整合させる\citep{Wyatt2008}．

### 3.2 物理定数・物性値

本研究で用いる主要な物理定数と物性値を表\ref{tab:method-phys}にまとめる．密度や蒸気圧係数などの材料依存パラメータは，基準ケースではフォルステライト相当の値を採用する（付録 Aも参照）．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{物理定数・物性値（基準計算）}
  \label{tab:method-phys}
  \begin{tabular}{p{0.30\textwidth} p{0.22\textwidth} p{0.12\textwidth} p{0.26\textwidth}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $G$ & $6.67430\times10^{-11}$ & m$^{3}$\,kg$^{-1}$\,s$^{-2}$ & 万有引力定数 \\
    $c$ & $2.99792458\times10^{8}$ & m\,s$^{-1}$ & 光速 \\
    $\sigma_{\rm SB}$ & $5.670374419\times10^{-8}$ & W\,m$^{-2}$\,K$^{-4}$ & ステファン・ボルツマン定数 \\
    $M_{\rm Mars}$ & $6.4171\times10^{23}$ & kg & 火星質量 \\
    $R_{\rm Mars}$ & $3.3895\times10^{6}$ & m & 火星半径 \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & 粒子密度（フォルステライト） \\
    $R$ & 8.314462618 & J\,mol$^{-1}$\,K$^{-1}$ & 気体定数（HKL に使用） \\
    \hline
  \end{tabular}
\end{table}

### 3.3 基準パラメータ

本研究で用いる幾何・力学・供給の基準パラメータを表\ref{tab:method-param}に整理する．衝突カスケードの $Q_D^*$ 係数は表\ref{tab:methods_qdstar_coeffs}に示し，感度掃引で用いる追加パラメータは付録 Aにまとめる．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{基準計算の採用値（幾何・力学・供給）}
  \label{tab:method-param}
  \begin{tabular}{p{0.3\textwidth} p{0.22\textwidth} p{0.12\textwidth} p{0.26\textwidth}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $r_{\rm in}$ & 1.0 & $R_{\rm Mars}$ & 内端半径 \\
    $r_{\rm out}$ & 2.7 & $R_{\rm Mars}$ & 外端半径 \\
    $N_r$ & 32 & -- & 半径セル数（リング分割） \\
    $M_{\rm in}$ & $3.0\times10^{-5}$ & $M_{\rm Mars}$ & 内側円盤質量 \\
    $s_{\min,\rm cfg}$ & $1.0\times10^{-7}$ & m & PSD 下限 \\
    $s_{\max}$ & $3.0$ & m & PSD 上限 \\
    $n_{\rm bins}$ & 40 & -- & サイズビン数 \\
    $\tau_0$ & 1.0 & -- & 初期 $\tau_{\rm los}$ 目標値 \\
    $\tau_{\rm stop}$ & 2.302585 & -- & 停止判定（$\ln 10$） \\
    $e_0$ & 0.5 & -- & 離心率 \\
    $i_0$ & 0.05 & -- & 傾斜角 \\
    $H_{\rm factor}$ & 1.0 & -- & $H_k=H_{\rm factor} i r$ \\
    $\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数 \\
    $\alpha_{\rm frag}$ & 3.5 & -- & 破片分布指数 \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & 粒子密度（表\ref{tab:method-phys}） \\
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
  \caption{基準計算の $Q_D^*$ 係数（$v_{\rm ref}$ は $\mathrm{km\,s^{-1}}$，$Q_s$ と $B$ は BA99 cgs 単位）}
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

以上により，初期条件・境界条件と基準パラメータを整理した．次節では，これらの設定のもとで PSD を時間発展させる数値解法を述べる．
