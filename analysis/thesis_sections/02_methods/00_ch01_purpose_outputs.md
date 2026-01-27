<!-- TEX_EXCLUDE_START -->

> **文書種別**: 手法（Diátaxis: Explanation）

<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

## 1. 概要

### 1.1 目的

遷移期における放射圧起因の質量流出率 $\dot{M}_{\rm out}(t)$ と，その時間積分としての累積損失 $M_{\rm loss}$ を定量化することを目的とする．ここでの遷移期とは，衝突直後計算が与える非軸対称・高温状態から，長期モデルが仮定する準定常・軸対称円盤へ落ち着くまでの時間帯を指す．この間に生じる不可逆損失を長期モデルへ渡す入力に反映することが，本研究の目的である．そこでまずは，どこまで積分するかと何を損失として数えるかを議論する．本モデルでは外部ドライバとして火星表面温度 $T_M(t)$ を与え，その時刻値に応じて放射圧・遮蔽・供給・衝突カスケード・追加シンクを順に評価する．得られた一次シンクを $\dot{M}_{\rm out}$ として記録し，時間積分により $M_{\rm loss}$ を更新する．また衝突項は粒径ビン間の再配分として実装されるため，供給項と一次シンク・追加シンクと整合する形で質量収支検査を常に併記し，数値解が会計的に破綻していないことを検証基準として用いる（5.1節）．
入力内容としては，火星表面温度 $T_M(t)$ に加え，各時刻の $T_M$ に対して放射圧指標（$\beta$，$s_{\rm blow}$ 等）と温度依存シンク（質量フラックスなど）を評価するための設定・外部テーブルを与える．さらに，火星放射が表層へ到達するという近似の適用範囲を判定するため，停止条件 $\tau_{\rm los}>\tau_{\rm stop}$ を与える（1.3節，4.3節）．本研究で参照する主要な外部入力（テーブル）を表\ref{tab:method_external_inputs}に示す．

長期モデルへ渡す内側円盤質量は，短時間モデル開始時刻 $t_0$ における内側円盤質量 $M_{\rm in}(t_0)$ から，終端 $t_{\rm end}$ までの累積損失 $M_{\rm loss}(t_{\rm end})$ を差し引くことで更新する：
\begin{equation}
\label{eq:min0_update}
M_{\rm in}'=M_{\rm in}(t_0)-M_{\rm loss}(t_{\rm end})
\end{equation}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{外部入力（テーブル）とモデル内での役割}
  \label{tab:method_external_inputs}
  \begin{tabular}{@{}L{0.28\textwidth} L{0.50\textwidth} L{0.18\textwidth}@{}}
    \hline
    外部入力 & 役割（モデル内での使い方） & 設定キー（代表） \\
    \hline
    火星温度履歴 $T_M(t)$ &
    放射圧（$\beta,\,s_{\rm blow}$）と昇華の外部ドライバ &
    \texttt{radiation.\allowbreak mars\_\allowbreak temperature\_\allowbreak driver.\allowbreak *} \\
    Planck 平均 $\langle Q_{\rm pr}\rangle(s,T_M)$ &
    放射圧効率として $\beta$ と $s_{\rm blow}$ を決める &
    \texttt{radiation.\allowbreak qpr\_\allowbreak table\_\allowbreak path} \\
    遮蔽係数 $\Phi$ &
    $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ を通じて自己遮蔽を表現する（遮蔽有効時） &
    \texttt{shielding.\allowbreak table\_\allowbreak path} \\
    供給率テーブル $\dot{\Sigma}_{\rm in}(t)$（任意） &
    表層供給率を外部から与える（\texttt{supply.mode=table} のとき） &
    \texttt{supply.\allowbreak table.\allowbreak path} \\
    飽和蒸気圧テーブル $P_{\rm sat}(T)$（任意） &
    昇華フラックスの入力として飽和蒸気圧をテーブル補間で与える &
    \texttt{sinks.\allowbreak sub\_\allowbreak params.\allowbreak psat\_\allowbreak table\_\allowbreak path} \\
    \hline
  \end{tabular}
\end{table}
出力内容として，$\dot{M}_{\rm out}(t)$，$\tau_{\rm los}(t)$，$s_{\rm blow}(t)$，$\Sigma_{\rm surf}(t)$ などの時系列を保存する（5.1節）．積分終端では $M_{\rm loss}$ とその内訳を要約量として出力し（5.1節），あわせて質量収支検査と停止判定の履歴を付随ログとして残す（4.3節，5.1節）．
積分終端は，本研究が主に扱う高温期の評価範囲を区切るため $T_M=T_{\rm end}=2000\,\mathrm{K}$ に到達する時刻 $t_{\rm end}$ とする．また，視線方向光学的厚さ $\tau_{\rm los}>\tau_{\rm stop}$ による適用範囲判定（早期停止）も併用する（4.3節）．

### 1.2 研究対象と基本仮定

モデルは軸対称であり，方位方向に平均化した面密度・PSD を状態量として扱う．ロッシュ限界内側の環状領域 $[r_{\rm in},r_{\rm out}]$ を半径方向に $N_r$ 個のセルへ分割し，各セルで同一の時間グリッドにより粒径分布（PSD）を時間発展させる．したがって，半径方向セル間輸送は基準ケースでは含めないものとする．
停止条件として $\tau_{\rm los}>\tau_{\rm stop}$ を採用し，火星放射が表層へ到達するという近似が破綻する領域は本モデルの適用範囲外として以後の時間発展を追跡しない（4.3節）．ここでの停止は，あくまで照射近似が成立する範囲でのみ計算するという計算上の取り扱いであり，物理的に放射圧によるブローアウトが停止することを意味しない．

### 1.3 状態変数と記号定義

半径方向はセル $\ell=1,\dots,N_r$ に分割し，代表半径 $r_\ell$ とセル面積 $A_\ell$ を用いて局所量を評価する．粒径分布は対数ビン $k=1,\dots,n_{\rm bins}$ に離散化し，セル $\ell$ におけるビン $k$ の数面密度（面数密度）を $N_{k,\ell}(t)$ とする（単位 $\mathrm{m^{-2}}$）．以降の式は特定セルにおける局所量として記し，必要に応じて $r$ 依存（あるいは $\ell$ 添字）を省略する．記号と単位の一覧は付録（記号表）にまとめる．
ここでは，火星放射に直接さらされるのは円盤の有効表層であるとみなし，$\Sigma_{\rm surf}$ はその表層に存在するダストの面密度（状態量）を表す．一方で，中層の総質量 $M_{\rm in}$ は供給や初期条件の基準として別に保持する．表層の $\Sigma_{\rm surf}$ と PSD は，表層への供給・衝突カスケード・一次シンクのバランスで時間発展させる（3.1節）．
粒子質量と表層面密度は式\ref{eq:mk_definition}–\ref{eq:sigma_surf_definition}で定義し，必要に応じて質量分率 $n_k$ を用いて分布形状と規格化を分離する\citep{Wyatt2008,Krivov2006_AA455_509}．

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

ここで $\rho$ は粒子密度，$s_k$ はビン $k$ の代表粒径である．また $N_k$ は局所セルにおける数面密度であり，$N_{k,\ell}$ とも表す．$n_k$ は表層面密度 $\Sigma_{\rm surf}$ に対するビン $k$ の質量分率である．
PSD の下限は有効最小粒径 $s_{\min,\rm eff}$ により与え，設定下限 $s_{\min,\rm cfg}$ とブローアウト境界 $s_{\rm blow}$ の最大値で定める．$s_{\min,\rm eff}$ は供給注入とサイズ境界条件の下限として用い，時刻ごとに更新する．この下限クリップにより，$s_{\rm blow}$ 未満の粒子は滞在時間 $t_{\rm blow}$ の一次シンクで速やかに失われる．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

火星放射が表層へ到達するかどうかを評価するため，火星方向の光学的厚さ $\tau_{\rm los}$ を導入する．$\tau_{\rm los}$ は本来，火星から半径 $r$ の円盤表層へ向かう光線に沿った積分 $\tau=\int \kappa\rho,ds$ で定義される．ただし本研究では3次元構造（スケールハイト $H$ など）と半径方向の自己遮蔽を解かないため，局所表層面密度 $\Sigma_{\rm surf}$ と表層不透明度 $\kappa_{\rm surf}$ から近似的に与える．すなわち鉛直光学的厚さ $\tau_\perp\equiv\kappa_{\rm surf}\Sigma_{\rm surf}$ を導入し，火星方向の経路長が鉛直より長い効果を幾何因子 $f_{\rm los}\ge1$ として $\tau_{\rm los}=f_{\rm los}\tau_\perp$ と近似する．
表層不透明度 $\kappa_{\rm surf}$ は PSD の幾何学断面（$\pi s^2$）から評価する表層の 断面積/質量 の近似であり，放射圧効率の波長依存は $\langle Q_{\rm pr}\rangle$ を通じて別途 $\beta$ に反映する（2.1節）．遮蔽は $\Phi(\tau_{\rm los})$ により $\kappa_{\rm eff}$ へ写像して扱い（2.2節），適用範囲判定（早期停止）は $\tau_{\rm los}>\tau_{\rm stop}$ により行う（4.3節）．参照面密度 $\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する\citep{Krivov2006_AA455_509,Wyatt2008}．

\begin{equation}
\label{eq:kappa_surf_definition}
\kappa_{\rm surf}
=\frac{1}{\Sigma_{\rm surf}}\sum_k \pi s_k^2\,N_k
\end{equation}

\begin{equation}
\label{eq:tau_los_definition}
\tau_{\rm los}=f_{\rm los}\kappa_{\rm surf}\Sigma_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:sigma_tau_los1_definition}
\Sigma_{\tau_{\rm los}=1}=\left(f_{\rm los}\kappa_{\rm surf}\right)^{-1}
\end{equation}

式\ref{eq:sigma_tau_los1_definition} は $\tau_{\rm los}=1$ を満たす参照面密度の定義である\citep{Krivov2006_AA455_509,Wyatt2008}．

### 1.4 計算フロー

図\ref{fig:method_overview}に，設定・外部テーブルから状態量（$\Sigma_{\rm surf},N_k$）を更新し，時系列・要約・検証ログを出力するまでの全体像を示す．

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/thesis/methods_main_loop.png}
\caption{手法の全体フロー（入力→状態→更新→出力）}
\label{fig:method_overview}
\end{figure}

各時刻ステップでは，まず温度ドライバ $T_M(t)$ から放射圧比 $\beta(s)$ を評価し，ブローアウト境界 $s_{\rm blow}$ とブローアウト時間 $t_{\rm blow}$ を得る．これに基づいて有効最小粒径 $s_{\min,\rm eff}$ を更新する（2.1節）．次に表層への供給率 $\dot{\Sigma}_{\rm in}$ を計算し，サイズビンのソース項 $F_k$ を構成する（2.3節）．続いて衝突カーネル $C_{ij}$ と破片分布 $Y_{kij}$ から衝突の生成・損失を評価し，IMEX-BDF(1) により PSD $N_k$ を更新する（2.4節，4.2節）．その後に $\tau_{\rm los}$ と $\dot{M}_{\rm out}$ を診断し，累積損失 $M_{\rm loss}$ と質量収支検査を更新する（2.1節，4.2節，5.1節）．最後に停止条件を判定し，必要なら当該セルを停止する（4.2節）．
これは，放射圧で決まるサイズ境界と損失時間尺度が，供給・衝突を通じて PSD の更新項に入るからである．
