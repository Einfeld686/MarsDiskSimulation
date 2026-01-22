<!-- TEX_EXCLUDE_START -->
> **文書種別**: 手法（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# シミュレーション手法

本章では遷移期モデルの再現性を担保するため，状態変数・支配方程式・数値解法・出力・検証を再現手順に必要な範囲で定義する．

## 1. 状態変数と記号定義

粒径分布は対数ビンに離散化し，ビン $k$ の数面密度を $N_k(t)$ として扱う．粒子質量と表層面密度は式\ref{eq:mk_definition}–\ref{eq:sigma_surf_definition}で定義し，必要に応じて質量分率 $n_k$ を用いて分布形状と規格化を分離する．記号と単位の一覧は付録Eにまとめる．

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

PSD 下限は有効最小粒径 $s_{\min,\rm eff}$ により与え，設定下限とブローアウト境界の最大値で定める．$s_{\min,\rm eff}$ は供給注入とサイズ境界条件の下限として用い，時刻ごとに更新する．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

光学的厚さは衝突頻度の評価に用いる垂直方向 $\tau_{\perp}$ と，放射遮蔽に用いる視線方向 $\tau_{\rm los}$ を区別する．表層不透明度 $\kappa_{\rm surf}$ から $\tau_{\perp}$ を定義し，$\tau_{\rm los}$ は幾何補正因子 $f_{\rm los}$ により与える．参照面密度 $\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する．

\begin{equation}
\label{eq:kappa_surf_definition}
\kappa_{\rm surf}
=\frac{1}{\Sigma_{\rm surf}}\sum_k \pi s_k^2\,N_k
\end{equation}

\begin{equation}
\label{eq:tau_perp_definition}
\tau_{\perp}=\kappa_{\rm surf}\Sigma_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:tau_los_definition}
\tau_{\rm los}=f_{\rm los}\tau_{\perp}
\end{equation}

\begin{equation}
\label{eq:sigma_tau_los1_definition}
\Sigma_{\tau_{\rm los}=1}=\left(f_{\rm los}\kappa_{\rm surf}\right)^{-1}
\end{equation}
