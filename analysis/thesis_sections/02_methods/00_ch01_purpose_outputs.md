<!-- TEX_EXCLUDE_START -->
> **文書種別**: 手法（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# 手法

## 1. 概要

### 1.1 目的と入出力

本研究の目的は，遷移期における放射圧起因の質量流出率 $\dot{M}_{\rm out}(t)$ と，その累積損失 $M_{\rm loss}$ を定量化することである．ここで遷移期とは，衝突直後計算が与える非軸対称・高温状態から，長期モデルが仮定する準定常・軸対称円盤へ落ち着くまでの時間帯を指し，この間に生じる不可逆損失を長期モデルへ渡す入力に反映することが狙いである．本論文ではこの累積損失を $M_{\rm loss}$ と記し，序論で導入した $\Delta M_{\rm in}$ と同義である．

以降の節を読み進めるため，ここでは「どこまで積分するか（停止条件）」「何を損失として数えるか（会計）」を先に固定する．本モデルは，外部ドライバである火星表面温度 $T_M(t)$ に応じて放射圧・遮蔽・供給・衝突カスケード・追加シンクを順に評価し，その結果として $\dot{M}_{\rm out}$ と $M_{\rm loss}$ を更新する．このとき衝突項は粒径ビン間の再配分として扱うため，供給・一次シンク・追加シンクと整合する形で質量収支検査を併記し，数値解が会計的に破綻していないことを検証基準として用いる（5.1節）．

**入力**は次のとおりである．

* 火星表面温度 $T_M(t)$（外部ドライバ；付録 C）．
* 各時刻の $T_M$ に対して評価する放射圧指標（$\beta,\,s_{\rm blow}$）と温度依存シンク（昇華など）．
* 適用範囲判定に用いる停止条件 $\tau_{\rm eff}>\tau_{\rm stop}$（2.2節，4.2節）．

**出力**は次のとおりである．

* 時系列：$\dot{M}_{\rm out}(t)$，$\tau_{\rm los}(t)$，$\tau_{\rm eff}(t)$，$s_{\rm blow}(t)$，$\Sigma_{\rm surf}(t)$ など（5.1節）．
* 要約：積分終端での $M_{\rm loss}$ と内訳（5.1節）．
* 付随ログ：質量収支検査と停止判定の履歴（4.2節，5.1節）．

積分終端は，本研究が主に扱う高温期の評価範囲を区切るため $T_M=T_{\rm end}=2000\,\mathrm{K}$ に到達する時刻 $t_{\rm end}$ とする．また，火星方向の有効光学的厚さ $\tau_{\rm eff}>\tau_{\rm stop}$ による適用範囲判定（早期停止）も併用する（2.2節，4.2節）．

次節では，本研究が対象とする円盤と，基準ケースで採用する近似を整理する．

### 1.2 研究対象と基本仮定

本研究はガス成分が支配的でない衝突起源ダスト円盤を対象とする．したがって基準ケースでは，ガス抗力やガス円盤の放射輸送を主効果としては含めず，必要なら追加シンクとして感度評価する（2.5節）．

モデルは軸対称で，方位方向に平均化した面密度・PSD を状態量として扱う．ロッシュ限界内側の環状領域 $[r_{\rm in},r_{\rm out}]$ を半径方向に $N_r$ 個のセルへ分割し，各セルで同一の時間グリッドにより粒径分布（PSD）を時間発展させる（セル間輸送は基準ケースでは含めない）．

停止条件として $\tau_{\rm eff}>\tau_{\rm stop}$ を採用し，火星放射が表層へ到達するという近似が破綻する領域は本モデルの適用範囲外として以後の時間発展を追跡しない（4.2節）．ここでの停止は，あくまで「照射近似が成立する範囲でのみ会計する」という計算上の取り扱いであり，物理的に「円盤が停止する」ことを意味しないことに注意する．

次節では，半径セルと粒径ビンで定義した状態量と主要診断量の記法を導入する．

### 1.3 状態変数（粒径・半径）と記号定義

半径方向はセル $\ell=1,\dots,N_r$ に分割し，代表半径 $r_\ell$ とセル面積 $A_\ell$ を用いて局所量を評価する．粒径分布は対数ビン $k=1,\dots,n_{\rm bins}$ に離散化し，セル $\ell$ におけるビン $k$ の数面密度（面数密度）を $N_{k,\ell}(t)$ とする（単位 $\mathrm{m^{-2}}$）．以降の式は特定セルにおける局所量として記し，必要に応じて $r$ 依存（あるいは $\ell$ 添字）を省略する．記号と単位の一覧は付録 Eにまとめる．

本論文では，火星放射に直接さらされるのは円盤の有効表層であるとみなし，$\Sigma_{\rm surf}$ はその表層に存在するダストの面密度（状態量）を表す．中層の総質量 $M_{\rm in}$ は供給や初期条件の基準として別に保持し，$\Sigma_{\rm surf}$ と PSD は表層への供給・衝突カスケード・一次シンクのバランスで時間発展させる（3.1節）．

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

ここで $\rho$ は粒子密度，$s_k$ はビン $k$ の代表粒径である．また $N_k$ は局所セルにおける数面密度であり，必要に応じて $N_{k,\ell}$ と書き分ける．$n_k$ は表層面密度 $\Sigma_{\rm surf}$ に対するビン $k$ の質量分率である．

PSD 下限は有効最小粒径 $s_{\min,\rm eff}$ により与え，設定下限 $s_{\min,\rm cfg}$ とブローアウト境界 $s_{\rm blow,eff}$ の最大値で定める．$s_{\min,\rm eff}$ は供給注入とサイズ境界条件の下限として用い，時刻ごとに更新する．この下限クリップにより，$s_{\rm blow}$ 未満の粒子は滞在時間 $t_{\rm blow}$ の一次シンクで速やかに失われ，PSD の有効範囲が時間とともに移動することを表現する．

本研究では $s_{\rm blow,eff}$ を式\ref{eq:s_blow_definition}で求めた $s_{\rm blow}$ と同一視し（以下では区別しない）．これは，遮蔽 $\Phi$ を放射圧そのものの減衰としては用いず，照射が成立するかどうか（$\tau_{\rm eff}$ による適用範囲判定）と供給規格化に反映するというモデル化に対応する．したがって照射が成立する限り，表層粒子は火星放射を直接受けると仮定し，ブローアウト境界（$\beta=0.5$）に基づく下限クリップの考え方は古典的整理に従う\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

本研究では，火星放射が表層へ到達するかどうかを評価するため，火星方向の光学的厚さ $\tau_{\rm los}$ を導入する．$\tau_{\rm los}$ は本来，火星から半径 $r$ の円盤表層へ向かう光線に沿った積分 $\tau=\int \kappa\rho,ds$ で定義されるが，3次元構造（スケールハイト $H$ など）と半径方向の自己遮蔽を解かないため，本研究では局所表層面密度 $\Sigma_{\rm surf}$ と表層不透明度 $\kappa_{\rm surf}$ から次の近似で与える．すなわち鉛直光学的厚さ $\tau_\perp\equiv\kappa_{\rm surf}\Sigma_{\rm surf}$ を定義し，火星方向の経路長が鉛直より長い効果を幾何因子 $f_{\rm los}\ge1$ として $\tau_{\rm los}=f_{\rm los}\tau_\perp$ と近似する．

表層不透明度 $\kappa_{\rm surf}$ は PSD の幾何学断面（$\pi s^2$）から評価する表層の「断面積/質量」の近似であり，放射圧効率の波長依存は $\langle Q_{\rm pr}\rangle$ を通じて別途 $\beta$ に反映する（2.1節）．遮蔽は $\Phi(\tau_{\rm los})$ により $\kappa_{\rm eff}$ へ写像して扱い（2.2節），停止判定に用いる有効光学的厚さ $\tau_{\rm eff}$ を定義する（4.2節）．参照面密度 $\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する\citep{Krivov2006_AA455_509,Wyatt2008}．

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

以上により，半径セルごとの表層面密度と PSD を状態量として定義した．次節（1.4）では更新フローを示し，2節以降で各項を与える．

### 1.4 計算の主経路（更新フロー）

図\ref{fig:method_overview}に，入力（設定・外部テーブル）から状態量（$\Sigma_{\rm surf},N_k$）を更新し，時系列・要約・検証ログを出力するまでの全体像を示す．ここで重要なのは，停止条件は「適用範囲判定」であり，会計（$M_{\rm loss}$ と質量収支検査）は停止時点まで必ず更新して保持する，という点である（4.2節，5.1節）．

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/thesis/methods_main_loop.pdf}
\caption{手法の全体フロー（入力→状態→更新→出力）}
\label{fig:method_overview}
\end{figure}

本研究の 1D 計算では，各時刻ステップで次を順に評価する．

1. 温度ドライバ $T_M(t)$ から放射圧比 $\beta(s)$，ブローアウト境界 $s_{\rm blow}$，ブローアウト時間 $t_{\rm blow}$ を計算し，有効最小粒径 $s_{\min,\rm eff}$ を更新する（2.1節）．
2. 表層への供給率 $\dot{\Sigma}_{\rm in}$ を評価し，サイズビンのソース項 $F_k$ を構成する（2.3節）．
3. 衝突カーネル $C_{ij}$ と破片分布 $Y_{kij}$ から衝突の生成・損失を評価し，IMEX-BDF(1) により PSD $N_k$ を更新する（2.4節，4.2節）．
4. $\tau_{\rm los}$ と $\dot{M}_{\rm out}$ を診断し，累積損失 $M_{\rm loss}$ と質量収支検査を更新する（2.1節，4.2節，5.1節）．
5. 停止条件を判定し，必要ならセルを停止する（4.2節）．

この順序は，放射圧で決まるサイズ境界と損失時間尺度が，供給・衝突を通じて PSD の更新項に入るためである．

本節で登場する主要量の定義位置をまとめると，$\beta,\,s_{\rm blow},\,t_{\rm blow},\,\dot{M}_{\rm out}$ は 2.1節，$\Phi(\tau_{\rm los})$ と $\kappa_{\rm eff}$ は 2.2節，$\dot{\Sigma}_{\rm in}$ と $F_k$ は 2.3節，$C_{ij}$ と $Y_{kij}$ と $t_{{\rm coll},k}$ は 2.4節，IMEX-BDF(1) と時間刻み・停止条件は 4.2節，出力仕様と合格基準は 5.1節で与える．

以上により，本節では「目的・入出力」「状態量」「更新順序」を先に固定し，2節以降で各項の式と採用値，数値手順，出力・検証基準を順に与える．
