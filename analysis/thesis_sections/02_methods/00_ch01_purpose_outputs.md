<!-- TEX_EXCLUDE_START -->
> **文書種別**: 手法（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# シミュレーション手法

本章では，ロッシュ限界内の高密度ダスト円盤を対象に，放射圧によるブローアウトと衝突カスケードを結合した 1D（リング分割）モデルを定義し，本研究で用いた初期条件・数値解法・停止条件・出力・検証基準をまとめる．

## 1. モデルの概要

本節では，計算の目的と入出力を明確にしたうえで，1D モデルで用いる状態変数（半径セルと粒径ビン）を定義する．

### 1.1 目的と入出力

本研究の目的は，遷移期における放射圧起因の質量流出率 $\dot{M}_{\rm out}(t)$ と，その累積損失 $M_{\rm loss}$ を定量化することである．解析は火星表面温度 $T_M(t)$ を外部ドライバとして与え，$T_M=2000\,\mathrm{K}$ に到達する時刻を積分終端 $t_{\rm end}$ とする（早期停止条件は 4.2節）．計算からは $\dot{M}_{\rm out}(t)$，$\tau_{\rm los}(t)$，$s_{\rm blow}(t)$，$\Sigma_{\rm surf}(t)$ などの時系列と，終端での $M_{\rm loss}$ と内訳を得る．

### 1.2 研究対象と基本仮定

本研究はガス成分が支配的でない衝突起源ダスト円盤を対象とする．モデルは軸対称で，ロッシュ限界内側の環状領域 $[r_{\rm in},r_{\rm out}]$ を半径方向に $N_r$ 個のセルへ分割し，各セルで同一の時間グリッドにより粒径分布（PSD）を時間発展させる．停止条件として $\tau_{\rm los}>\tau_{\rm stop}$ を採用し，到達したセルは以後の時間発展から除外する．

### 1.3 状態変数（粒径・半径）と記号定義

半径方向はセル $\ell=1,\dots,N_r$ に分割し，代表半径 $r_\ell$ とセル面積 $A_\ell$ を用いて局所量を評価する．粒径分布は対数ビン $k=1,\dots,n_{\rm bins}$ に離散化し，セル $\ell$ におけるビン $k$ の数面密度（面数密度）を $N_{k,\ell}(t)$ とする（単位 $\mathrm{m^{-2}}$）．以降の式は特定セルにおける局所量として記し，必要に応じて $r$ 依存（あるいは $\ell$ 添字）を省略する．記号と単位の一覧は付録 Eにまとめる．

粒子質量と表層面密度は式\ref{eq:mk_definition}–\ref{eq:sigma_surf_definition}で定義し，必要に応じて質量分率 $n_k$ を用いて分布形状と規格化を分離する\cite{Wyatt2008,Krivov2006_AA455_509}．

\begin{equation}
\label{eq:mk_definition}
m_k=\frac{4\pi}{3}\rho s_k^3
\end{equation}

\begin{equation}
\label{eq:sigma_surf_definition}
\Sigma_{\rm surf}(t)=\sum_k m_k N_k(t)
\end{equation}

\begin{equation}
\label{eq:nk_massfrac_definition}
n_k(t)=\frac{m_k N_k(t)}{\Sigma_{\rm surf}(t)}
\end{equation}

PSD 下限は有効最小粒径 $s_{\min,\rm eff}$ により与え，設定下限 $s_{\min,\rm cfg}$ とブローアウト境界 $s_{\rm blow,eff}$ の最大値で定める．$s_{\min,\rm eff}$ は供給注入とサイズ境界条件の下限として用い，時刻ごとに更新する．ブローアウト境界（$\beta=0.5$）に基づく下限クリップの考え方は古典的整理に従うが\cite{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}，本研究では設定下限との最大値として実装する．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

本研究では，火星放射に対する遮蔽・停止判定に用いる光学的厚さを $\tau_{\rm los}$ とする．表層不透明度 $\kappa_{\rm surf}$ を PSD から評価し，$\tau_{\rm los}$ を次で与える．参照面密度 $\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する\cite{Krivov2006_AA455_509,Wyatt2008}．

\begin{equation}
\label{eq:kappa_surf_definition}
\kappa_{\rm surf}
=\frac{1}{\Sigma_{\rm surf}}\sum_k \pi s_k^2\,N_k
\end{equation}

\begin{equation}
\label{eq:tau_los_definition}
\tau_{\rm los}=\kappa_{\rm surf}\Sigma_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:sigma_tau_los1_definition}
\Sigma_{\tau_{\rm los}=1}=\kappa_{\rm surf}^{-1}
\end{equation}

式\ref{eq:sigma_tau_los1_definition} は $\tau_{\rm los}=1$ を満たす参照面密度の定義である\cite{Krivov2006_AA455_509,Wyatt2008}．

以上により，半径セルごとの表層面密度と PSD を状態量として定義した．次節では，これらを時間発展させる物理過程（放射圧・遮蔽・供給・衝突カスケード・追加シンク）を定式化する．

### 1.4 計算の主経路（更新フロー）

本研究の 1D 計算は半径セルごとに独立に行い，各時刻ステップで次を順に評価する．

1. 温度ドライバ $T_M(t)$ から放射圧比 $\beta(s)$，ブローアウト境界 $s_{\rm blow}$，ブローアウト時間 $t_{\rm blow}$ を計算し，有効最小粒径 $s_{\min,\rm eff}$ を更新する．
2. 表層への供給率 $\dot{\Sigma}_{\rm in}$ を評価し，サイズビンのソース項 $F_k$ を構成する．
3. 衝突カーネル $C_{ij}$ と破片分布 $Y_{kij}$ から衝突の生成・損失を評価し，IMEX-BDF(1) により PSD $N_k$ を更新する．
4. $\tau_{\rm los}$ と $\dot{M}_{\rm out}$ を診断し，累積損失 $M_{\rm loss}$ と質量収支検査を更新する．
5. 停止条件を判定し，必要ならセルを停止する．

この順序は，放射圧で決まるサイズ境界と損失時間尺度が，供給・衝突を通じて PSD の更新項に入るためである．
