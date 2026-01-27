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
## 2. 支配方程式と物理モデル

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/io/tables.py, marsdisk/physics/psd.py, marsdisk/physics/sizes.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/initfields.py
-->

時間発展には，放射圧による除去\citep{Burns1979_Icarus40_1}，遮蔽，表層への供給，衝突カスケード，およびその他の損失過程をまとめた追加シンク項を含める．以下では，1.3節で定義した粒径ビン表現（$s_k,m_k,N_k$）に基づき，粒径をビン $k$ に離散化した量で記述する．
軌道力学量は，各半径セルの中心半径 $r$ で評価する．火星質量 $M_{\rm Mars}$ による点質量重力場を仮定し，粒子の軌道運動をケプラー運動で近似すると，ケプラー速度 $v_K(r)$，ケプラー角速度 $\Omega(r)$，および公転周期 $T_{\rm orb}(r)$ は式\ref{eq:vK_definition}–\ref{eq:torb_definition}で定義される．

\begin{equation}
\label{eq:vK_definition}
v_K(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r}}
\end{equation}

\begin{equation}
\label{eq:omega_definition}
\Omega(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r^{3}}}
\end{equation}

\begin{equation}
\label{eq:torb_definition}
T_{\rm orb}(r)=\frac{2\pi}{\Omega(r)}
\end{equation}

ここで $G$ は万有引力定数である．また，式\ref{eq:vK_definition}と式\ref{eq:omega_definition}より $v_K(r)=r\,\Omega(r)$ が成り立つ．

### 2.1 放射圧とブローアウト

放射圧と重力の比 $\beta(s)$ は式\ref{eq:beta_definition}で定義し，Planck 平均の $\langle Q_{\rm pr}\rangle$ は外部テーブルから与える（表\ref{tab:method_external_inputs}）\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．本研究では $\langle Q_{\rm pr}\rangle(s,T_M)$ を $(s,T_M)$ 格子上の双一次補間（$s$ と $T_M$ の両方向で線形補間）で評価し，テーブル範囲外では外挿を避けて端値を代表値として用いる．$\beta\ge0.5$ を非束縛条件とし，ブローアウト境界粒径 $s_{\rm blow}$ は $\beta(s_{\rm blow})=0.5$ の解として式\ref{eq:s_blow_definition}で与える\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．$\langle Q_{\rm pr}\rangle(s,T_M)$ を粒径依存のテーブル補間で与える場合，式\ref{eq:s_blow_definition}は $s_{\rm blow}$ に関する陰関数であるため，本研究では固定点反復により数値的に解く．ブローアウト滞在時間は式\ref{eq:t_blow_definition}とし\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}，$\chi_{\rm blow}$ は入力として与える．

\begin{equation}
\label{eq:beta_definition}
\beta(s) = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle(s,T_M)}{4\,G\,M_{\rm Mars}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle(s_{\rm blow},T_M)}{2\,G\,M_{\rm Mars}\,c\,\rho}
\end{equation}

\begin{equation}
\label{eq:t_blow_definition}
t_{\rm blow}=\chi_{\rm blow}\Omega^{-1}
\end{equation}

$\chi_{\rm blow}$ はブローアウト滞在時間の係数であり，非束縛となった粒子が表層から除去されるまでの有効滞在時間を $\Omega^{-1}$ で規格化した量であると仮定する．ブローアウトは公転位相や放出条件に依存し得るため，本研究では $\chi_{\rm blow}$ を order unity の不確かさを持つ入力パラメータとして扱い，極端な滞在時間を避けるため $0.5$–$2$ の範囲に制限する．`auto` を選ぶ場合は，$\beta$ と $\langle Q_{\rm pr}\rangle$ を $s=s_{\min,\rm eff}$ で評価した値から次の経験式で推定する（${\rm clip}_{[a,b]}(x)\equiv\min(\max(x,a),b)$）．

\begin{equation}
\label{eq:chi_blow_auto_definition}
\chi_{\rm blow}=
{\rm clip}_{[0.5,2.0]}\!\left[
{\rm clip}_{[0.1,\infty)}\!\left(\frac{1}{1+0.5\left(\beta/0.5-1\right)}\right)
\;{\rm clip}_{[0.5,1.5]}\!\left(\langle Q_{\rm pr}\rangle\right)
\right]
\end{equation}

表層からの質量損失は PSD に作用する一次シンクとして扱い，ブローアウト対象ビンでは $S_{{\rm blow},k}=1/t_{\rm blow}$ とする．ブローアウト対象は $\beta\ge0.5$ に対応する $s_k\le s_{\rm blow}$ のビンとする．表層からの面密度流出は式\ref{eq:surface_outflux}で与える\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}．

\begin{equation}
\label{eq:surface_outflux}
\dot{\Sigma}_{\rm out} = \sum_k m_k S_{{\rm blow},k} N_k
\end{equation}

円盤全体の流出率は式\ref{eq:mdot_out_definition}で定義し，1D では各セルの流出フラックスをセル面積で重み付けした総和で評価する\citep{Wyatt2008}．本論文では $\dot{M}_{\rm out}$ を $M_{\rm Mars}$ で規格化して扱う．

\begin{equation}
\label{eq:mdot_out_definition}
\dot{M}_{\rm out}(t)=\int_{r_{\rm in}}^{r_{\rm out}}2\pi r\,\dot{\Sigma}_{\rm out}(r,t)\,dr
\end{equation}

離散化では，セル $\ell$ の面積 $A_\ell$ と局所フラックス $\dot{\Sigma}_{{\rm out},\ell}(t)$ を用いて

\begin{equation}
\dot{M}_{\rm out}(t)\approx\sum_{\ell=1}^{N_r} A_\ell\,\dot{\Sigma}_{{\rm out},\ell}(t)
\end{equation}

と評価する．

### 2.2 遮蔽

遮蔽係数 $\Phi(\tau_{\rm los})$ は，自己遮蔽により火星放射が表層へ到達しにくくなる効果を，視線方向光学的厚さ $\tau_{\rm los}$ の関数として表す無次元係数である（表\ref{tab:method_external_inputs}）．
遮蔽の効果は，表層の質量不透明度 $\kappa_{\rm surf}$ [$\mathrm{m^2\,kg^{-1}}$] を，有効不透明度 $\kappa_{\rm eff}$ に置き換えることで取り込む．本研究では $\kappa_{\rm eff}$ を $\Phi$ によりスケールする近似を採用し，以下で定義する．

\begin{equation}
\label{eq:phi_definition}
\Phi=\Phi(\tau_{\rm los})
\end{equation}

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\rm eff} = \Phi\,\kappa_{\rm surf}
\end{equation}

ここで $\tau_{\rm los}$ は式\ref{eq:tau_los_definition}で定義した視線方向光学的厚さであり，$\Phi$ はその関数として与える．なお，$\Sigma_{\tau=1}$ の $\tau$ は有効不透明度に基づく鉛直光学的厚さ $\tau_{\rm eff}\equiv\kappa_{\rm eff}\Sigma_{\rm surf}$ を指す診断量であり，$\tau_{\rm los}$ と区別して用いる．
$\kappa_{\rm eff}$ に基づき，診断量として参照面密度 $\Sigma_{\tau=1}$ を式\ref{eq:sigma_tau1_definition}で定義する．$\kappa_{\rm eff}>0$ のとき $\Sigma_{\tau=1}$ は $\kappa_{\rm eff}\Sigma_{\rm surf}\simeq1$ に対応する表層面密度の目安であり，$\kappa_{\rm eff}\le0$ の場合は光学的に厚くならない極限として $\Sigma_{\tau=1}=\infty$ と置く．

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau=1} =
\begin{cases}
\kappa_{\rm eff}^{-1}, & \kappa_{\rm eff} > 0,\\
\infty, & \kappa_{\rm eff} \le 0
\end{cases}
\end{equation}

$\kappa_{\rm eff}$ は遮蔽を織り込んだ有効不透明度として照射・表層アウトフローの評価に用いる．一方，初期条件の光学的厚さの規格化と，$\tau_{\rm stop}$ による適用範囲判定（停止判定）には $\tau_{\rm los}$ を用いる．

### 2.3 表層への質量供給
\label{sec:method-supply}

表層への供給率を $\dot{\Sigma}_{\rm in}(t,r)$ と定義する．ここで $r$ は半径セルの中心半径であり，$\dot{\Sigma}_{\rm in}$ は表層（$\Sigma_{\rm surf}$）へ単位面積・単位時間あたりに注入される質量を表す．供給過程は，表層と下層との混合効率を表す無次元係数 $\epsilon_{\rm mix}$ と，基準供給率 $R_{\rm base}(r)$ を用いて式\ref{eq:prod_rate_definition}で与える．衝突カスケードのサイズ分布進化モデルでは，質量収支式に外部供給を明示的に導入する定式化が用いられており，$F_k$ はソース項に相当する（e.g. \citet{Wyatt2008,WyattClarkeBooth2011_CeMDA111_1}）．
基準ケースでは，$R_{\rm base}$ を参照面密度の一定割合を 1 軌道あたり供給する定常供給として式\ref{eq:R_base_definition}で定義する．このとき $R_{\rm base}$ 自体は初期時刻 $t_0$ の参照面密度 $\Sigma_{\tau_{\rm ref}}(t_0,r)$ と公転周期 $T_{\rm orb}(r)$ のみに依存する．

\begin{equation}
\label{eq:R_base_definition}
R_{\rm base}(r)=
\frac{\mu_{\rm sup}\,f_{\rm orb}}{\epsilon_{\rm mix}}
\frac{\Sigma_{\tau_{\rm ref}}(t_0,r)}{T_{\rm orb}(r)},
\qquad
\Sigma_{\tau_{\rm ref}}(t_0,r)=\frac{\tau_{\rm ref}}{f_{\rm los}\kappa_{\rm eff}(t_0,\tau_{\rm ref})}
\end{equation}

ここで $\mu_{\rm sup}$ は供給強度を定める無次元パラメータであり，$f_{\rm orb}$ は $\mu_{\rm sup}=1$ のときに 1 軌道あたりに供給される表層面密度が参照面密度 $\Sigma_{\tau_{\rm ref}}$ に対して占める無次元量の比率である．$\tau_{\rm ref}$ は参照光学的厚さ（既定値 1；$\tau_{\rm los}$）であり，$\Sigma_{\tau_{\rm ref}}$ は初期 PSD から評価した $\kappa_{\rm eff}$ に基づく参照面密度である．本研究では初期光学的厚さ $\tau_0$ を掃引して初期状態を変えるため，$\Sigma_{\tau_{\rm ref}}(t_0,r)$ を用いて供給率を規格化し，同じ $\mu_{\rm sup}$ が同程度の供給量を指すように定義する．なお，式\ref{eq:R_base_definition}に $\epsilon_{\rm mix}$ を含めたのは，式\ref{eq:prod_rate_definition}と合わせて $\dot{\Sigma}_{\rm in}$ が $\mu_{\rm sup}$ と $f_{\rm orb}$ により一意に決まり，$\epsilon_{\rm mix}$ の値に依存しない（$\dot{\Sigma}_{\rm in}=\mu_{\rm sup}f_{\rm orb}\Sigma_{\tau_{\rm ref}}/T_{\rm orb}$ に帰着する）ようにするためである．

供給率は式\ref{eq:supply_injection_definition}により PSD のソース項 $F_k$ として粒径ビン $k$ に注入する．ここで $F_k$ は単位面積あたりの粒子数密度 $N_k$ の増加率であり，質量保存条件 $\sum_k m_kF_k=\dot{\Sigma}_{\rm in}$ を満たすよう，無次元重み $w_k$ を $\sum_kw_k=1$ となるように正規化する．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\rm in}(t,r) = \max\!\left(\epsilon_{\rm mix}R_{\rm base}(r),\,0\right)
\end{equation}

\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},
\qquad
\sum_k w_k=1,
\qquad
\sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}

供給される表層物質の粒径分布は，下層からの混合が初期表層と同程度の組成・粒径分布を持つという近似の下で，初期 PSD の質量分率に比例すると仮定する．具体的には $w_k\propto m_kN_k(t_0,r)$ と置き，$\sum_kw_k=1$ となるように正規化して用いる．これにより，供給は分布形状を直接には変えず，規格化を更新する操作として実装される．

### 2.4 衝突カスケード

PSD の時間発展は Smoluchowski 方程式（式\ref{eq:smoluchowski}）で与え，注入 $F_k$ と一次シンク $S_k$ を含める\citep{Krivov2006_AA455_509,Thebault2003_AA408_775,Wyatt2008}．破片生成テンソル $Y_{kij}$ は質量保存条件 $\sum_k Y_{kij}=1$ を満たすよう定義する．

\begin{equation}
\label{eq:smoluchowski}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

\begin{equation}
\label{eq:fragment_yield_normalization}
\sum_k Y_{kij}=1
\end{equation}

衝突イベント率 $C_{ij}$ は式\ref{eq:collision_kernel}で与える\citep{Krivov2006_AA455_509}．スケールハイトは小傾斜近似の $z\sim ir$ に基づき $H_k=H_{\rm factor}\,i\,r$ とし，$H_{\rm factor}$ は分布形状や定義差を吸収する order unity の幾何因子として扱う．

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

相対速度 $v_{ij}$ は低離心率・低傾斜のレイリー分布近似として $e,i$ と $v_K$ から式\ref{eq:vrel_pericenter_definition}で評価する\citep{LissauerStewart1993_PP3,WetherillStewart1993_Icarus106_190,Ohtsuki2002_Icarus155_436,IdaMakino1992_Icarus96_107,ImazBlanco2023_MNRAS522_6150}．

\begin{equation}
\label{eq:vrel_pericenter_definition}
v_{ij}=v_K\,\sqrt{1.25\,e^{2}+i^{2}}
\end{equation}

ビンの衝突寿命は式\ref{eq:t_coll_definition}とし，時間刻みの上限に用いる\citep{Wyatt2008,StrubbeChiang2006_ApJ648_652}．

\begin{equation}
\label{eq:t_coll_definition}
t_{{\rm coll},k}=\left(\frac{\sum_j C_{kj}+C_{kk}}{N_k}\right)^{-1}
\end{equation}

破壊閾値 $Q_D^*$ は式\ref{eq:qdstar_definition}で与える\citep{BenzAsphaug1999_Icarus142_5,LeinhardtStewart2012_ApJ745_79,StewartLeinhardt2009_ApJ691_L133}．係数 $Q_s,B$ は BA99 の cgs 系で与えられるため，本研究では $s$ と $\rho$ を cgs へ変換して評価したのち $1\,{\rm erg\,g^{-1}}=10^{-4}\,{\rm J\,kg^{-1}}$ により SI へ換算する．

\begin{equation}
\label{eq:qdstar_definition}
Q_{D}^{*}(s,\rho,v)=Q_s(v)\,s^{-a_s(v)}+B(v)\,\rho\,s^{b_g(v)}
\end{equation}

具体的には $s$ を m，$\rho$ を kg\,m$^{-3}$ で与えたとき，

\begin{equation}
\label{eq:qdstar_cgs_to_si}
Q_{D}^{*}(s,\rho,v)=10^{-4}\!\left[
Q_s(v)\,(100s)^{-a_s(v)}+B(v)\,\left(\frac{\rho}{1000}\right)(100s)^{b_g(v)}
\right]
\end{equation}

を用いる．速度依存は参照速度 $v_{\rm ref}$ の表に基づき，$v_{ij}$ が表の範囲内では隣接する 2 点の $v_{\rm ref}$ で評価した $Q_D^*$ を線形補間し，範囲外では最近接の係数を採用したうえで重力項のみ $v^{-3\mu_{\rm LS}+2}$ のべきでスケールする（$\mu_{\rm LS}=0.45$）\citep{StewartLeinhardt2009_ApJ691_L133}．これは参照表の範囲外に対する外挿仮定である．

衝突の比エネルギーは reduced specific kinetic energy $Q_R$ を用い，

\begin{equation}
\label{eq:q_r_definition}
Q_R=\frac{1}{2}\frac{\mu_{ij}v_{ij}^{2}}{m_i+m_j},\qquad \mu_{ij}=\frac{m_i m_j}{m_i+m_j}
\end{equation}

と定義する．最大残存率 $F_{LF}$ は $\phi\equiv Q_R/Q_D^*$ の関数として，\citet{LeinhardtStewart2012_ApJ745_79} の近似を採用する．

\begin{equation}
\label{eq:F_LF_definition}
F_{LF}(\phi)=
\begin{cases}
1-\frac12\phi, & \phi<\phi_{\rm tr},\\
0.1\left(\dfrac{\phi}{\phi_{\rm tr}}\right)^{-1.5}, & \phi\ge\phi_{\rm tr},
\end{cases}
\qquad \phi_{\rm tr}=1.8
\end{equation}

最大残存体の粒径は $m_{\rm LR}=F_{LF}(m_i+m_j)$ に対応する $s_{\rm LR}=(3m_{\rm LR}/4\pi\rho)^{1/3}$ とし，$s_{\rm LR}$ を含むビンを $k_{\rm LR}$ として割り当てる．
最大残存率 $F_{LF}$ と破片分布 $w^{\rm frag}_k$ を通じて式\ref{eq:fragment_tensor_definition}で $Y_{kij}$ を構成する\citep{StewartLeinhardt2009_ApJ691_L133,Thebault2003_AA408_775}．

\begin{equation}
\label{eq:fragment_weights}
w^{\rm frag}_k(k_{\rm LR})=\frac{\int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\rm frag}}\,ds}{\sum_{\ell\le k_{\rm LR}}\int_{s_{\ell-}}^{s_{\ell+}} s^{-\alpha_{\rm frag}}\,ds}
\end{equation}

\begin{equation}
\label{eq:fragment_tensor_definition}
Y_{kij}=F_{LF}\delta_{k k_{\rm LR}}+(1-F_{LF})\,w^{\rm frag}_k(k_{\rm LR})
\end{equation}

### 2.5 質量フラックスによる粒径縮小

HKL 式（Hertz–Knudsen–Langmuir 式）に基づき，凝縮相（固相／液相）表面から気相へ輸送される正味の質量フラックス $J(T)$ を評価し，それに伴う粒径縮小をモデル化する\citep{VanLieshoutMinDominik2014_AA572_A76}．HKL 式は本来，$P_{\rm sat}(T)$ と $P_{\rm gas}$ の差に応じて蒸発／昇華と凝縮の双方を記述するが，本研究では気相の再凝縮・付着成長を追跡しないため，固体粒子の減少に寄与する $J\ge 0$ の範囲のみを用いる．すなわち $P_{\rm sat}(T)\le P_{\rm gas}$ では $J=0$ とする．
相変化（蒸発・昇華）フラックスの評価に用いる粒子温度 $T_p$ は，火星の熱放射による加熱と粒子自身の熱放射による冷却の釣り合いを灰色体近似で表し，式\ref{eq:grain_temperature_definition}で与える\citep{BohrenHuffman1983_Wiley}．ここで $\langle Q_{\rm abs}\rangle$ は吸収効率の Planck 平均であり，基準ケースでは $\langle Q_{\rm abs}\rangle=1$ を既定値とする．

\begin{equation}
\label{eq:grain_temperature_definition}
T_p = T_M\,\langle Q_{\rm abs}\rangle^{1/4}\sqrt{\frac{R_{\rm Mars}}{2r}}
\end{equation}

飽和蒸気圧 $P_{\rm sat}(T)$ は Clausius 型の近似式（式\ref{eq:psat_definition}）で与え\citep{Kubaschewski1974_Book,VisscherFegley2013_ApJL767_L12}，係数 $A,B$ は材料の相に応じて切り替える．係数は文献の実験・コンパイル値に基づき採用し，ここでは式形と依存性のみに着目する．ここで $A,B$ は当該単位系に整合するフィット係数である．

\begin{equation}
\label{eq:psat_definition}
P_{\rm sat}(T)=10^{A - B/T}
\end{equation}

相境界近傍で温度が往復する場合，微小な温度変動によって相の判定が頻繁に反転すると数値的不安定性を生む．本研究では相変化の微視的過程を解かない代わりに，相判定にヒステリシスを導入し，切替温度とヒステリシス幅は融点近傍の文献値に基づき設定する．これは固相・液相の寄与を有効パラメータで表現する近似である。
以上を用いて，凝縮相表面からの正味の質量フラックス $J(T)$ を HKL 式で与える\citep{VanLieshoutMinDominik2014_AA572_A76}．蒸発（固相では昇華）係数 $\alpha_{\rm evap}$ と周囲気相の分圧 $P_{\rm gas}$ を導入し，粒子の質量減少に寄与する成分のみを反映するため，$P_{\rm sat}(T)-P_{\rm gas}$ の正の部分を採用する．

\begin{equation}
\label{eq:hkl_flux}
J(T) =
\alpha_{\rm evap}\max\!\bigl(P_{\rm sat}(T) - P_{\rm gas},\,0\bigr)
\sqrt{\dfrac{\mu}{2\pi R T}}
\end{equation}

ここで $\mu$ は分子のモル質量，$R$ は気体定数である．
次に，$J(T)$ を粒径縮小速度へ写像する．粒子を密度 $\rho$ の球とみなすと，質量保存から $dm/dt=-4\pi s^{2}J$ および $m=(4/3)\pi\rho s^{3}$ が成り立つため，$ds/dt=-J/\rho$ を得る\citep{VanLieshoutMinDominik2014_AA572_A76}．したがって粒径の時間変化は式\ref{eq:dsdt_definition}で与える．

\begin{equation}
\label{eq:dsdt_definition}
\frac{ds}{dt}=-\frac{J(T)}{\rho}
\end{equation}

離散粒径ビンでの実装では，粒径縮小は連続的なサイズ空間の移流に相当するが，本研究では表層固体粒子の減少時定数を簡潔に表現するため，各ビンの代表粒径 $s_k$ に対して有効寿命 $t_{{\rm sub},k}=s_k/|ds/dt|$ を定義し，一次シンクとして Smoluchowski 方程式に組み込む．すなわち $ds/dt<0$ のとき，

\begin{equation}
\label{eq:sublimation_sink_definition}
S_{{\rm sub},k}=\frac{1}{t_{{\rm sub},k}}=\frac{|ds/dt|}{s_k}
\end{equation}

とし，式\ref{eq:smoluchowski}の $S_k$ に加算する．
## 3. パラメータ条件

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/physics/sizes.py, marsdisk/physics/psd.py, marsdisk/physics/qstar.py, marsdisk/io/tables.py
-->


### 3.1 初期条件と境界条件

初期条件は，時刻 $t=t_0$ における PSD $N_k(t_0)$ と，環状領域 $r\in[r_{\rm in},r_{\rm out}]$ の幾何・温度条件で与える．ここで $N_k$ は，粒径ビン $k$ に属する粒子の表面数密度として定義し，環状領域内の各半径位置で同様に与える．
火星放射が表層へ到達する深さは，火星方向の光学的厚さで決まる．本来，光学的厚さは三次元密度分布に対する線積分であるが，本研究では表層を薄い層として平均化し，火星方向の視線方向光学的厚さを 表層面密度 $\Sigma_{\rm surf}(t,r)$ と 表層不透明度 $\kappa_{\rm surf}(t,r)$ によって近似的に表す．すなわち，視線方向光学的厚さ $\tau_{\rm los}(t,r)$ を式\ref{eq:tau_los_definition}で与え，斜入射や経路長の違いを幾何因子 $f_{\rm los}$ に集約する．この近似は，表層が幾何学的に薄く，放射の減衰が主として表層の面密度と不透明度で支配される，という物理像を表現している．

$\kappa_{\rm eff}$ は，PSD が与える質量不透明度 $\kappa_{\rm surf}$ に対し，自己遮蔽や有効照射面積の低下を表す遮蔽係数 $\Phi$ を導入して
\[
\kappa_{\rm eff}=\Phi\,\kappa_{\rm surf}
\]
と定義する（2.2節）．$\Phi$ は，表層が濃くなるほど実効的に照射される粒子が減る，という効果を平均化して表す無次元補正であり，視線方向光学的厚さ $\tau_{\rm los}$ に依存する．

以上を踏まえ，初期表層面密度 $\Sigma_{\rm surf}(t_0,r)$ は，視線方向光学的厚さが $\tau_{\rm los}(t_0,r)=\tau_0$ となるように，環状領域内で一様に定める．このとき，
\begin{equation}
\label{eq:sigma_surf0_from_tau0}
\Sigma_{\rm surf}(t_0,r)=\frac{\tau_0}{f_{\rm los}\kappa_{\rm surf}(t_0)}
\end{equation}
とおく．ここで $\kappa_{\rm surf}(t_0)$ は初期 PSD から評価した表層不透明度であり，その形状（$w_{\rm melt}$）により決まる．この初期化により，遮蔽係数は $\Phi(\tau_0)$ として与えられ，初期有効不透明度は $\kappa_{\rm eff}(t_0)=\Phi(\tau_0)\kappa_{\rm surf}(t_0)$ で決まる（2.2節）．

基準計算の初期 PSD は，巨大衝突後に形成される溶融滴成分と微細粒子成分の共存を，2成分の対数正規分布の混合で近似した melt lognormal mixture とする\citep{Hyodo2017a_ApJ845_125}．初期 PSD の質量分布形状を $w_{\rm melt}(s)$ として
\begin{equation}
\label{eq:initial_psd_lognormal_mixture}
\begin{aligned}
w_{\rm melt}(s)\propto {} &
(1-f_{\rm fine})\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm meter})}{\sigma_{\ln}}\right)^2\right] \\
& + f_{\rm fine}\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm fine})}{\sigma_{\ln}}\right)^2\right], \\
\sigma_{\ln} = {} & {\rm width}_{\rm dex}\ln 10
\end{aligned}
\end{equation}
で与える．この形は，代表的な溶融滴と微細粒子の二峰性を，有限個のパラメータで取り扱うための近似である．採用値は表\ref{tab:methods_initial_psd_params}に示す．

なお，$s<s_{\rm cut}$ の領域は $w_{\rm melt}(s)=0$ とする．これは凝縮粒子が存在しないことを表すものではなく凝集・再付着など未解像の微細粒子過程を，最小スケール $s_{\rm cut}$ によってパラメタライズし，初期 PSD の最微小端を有限の自由度として切り出すための近似である\citep{Hyodo2017a_ApJ845_125}．

$N_k(t_0)$ の設定では，式\ref{eq:initial_psd_lognormal_mixture} が与える質量分布に従って各粒径ビンへ質量を配分し，その全体規格化を初期表層面密度が式\ref{eq:sigma_surf_definition}の $\Sigma_{\rm surf}(t_0)$ を満たすように定める．これにより，初期 PSD は形状（$w_{\rm melt}$） + 総量（$\Sigma_{\rm surf}$）として物理的に解釈できる形で与えられる．

火星温度 $T_M(t)$ は，火星からの熱放射場を規定する外部条件として与える．同様に，放射圧効率の平均量 $\langle Q_{\rm pr}\rangle$ と遮蔽係数 $\Phi$ は，本研究では外部条件として与え，その定義と採用値を表\ref{tab:method_external_inputs}にまとめる．

粒径の取り扱いは $s\in[s_{\min,\rm cfg},s_{\max}]$ を計算上の範囲とし，放射圧により力学的に束縛されない粒子は，表層から短い力学時間で除去されるものとして PSD に含めない．具体的には，実効ブローアウト粒径 $s_{\min,\rm eff}$ 未満の粒子は存在しないとして扱い，$s_{\min,\rm cfg}$ は数値的に追跡する最小粒径として設定する\citep{Burns1979_Icarus40_1,Hyodo2018_ApJ860_150}．

環状領域で平均化した面密度と総質量の換算には，環状近似に基づく面積
\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}
を用いる．これは，衝突カスケードを particle-in-a-box で扱う際の，セル平均量での記述と整合的である\citep{Thebault2003_AA408_775,WyattClarkeBooth2011_CeMDA111_1}．

最後に，表\ref{tab:method-param}の $M_{\rm in}$ はロッシュ限界内側の総質量を表す．一方，初期表層質量 $M_{\rm surf}(t_0)=\int 2\pi r\,\Sigma_{\rm surf}(t_0,r)\,dr$ は，式\ref{eq:sigma_surf0_from_tau0}で与えた $\tau_0$ と初期 PSD から 派生する量として扱う．したがって，$\tau_0$ を指定した基準設定では $M_{\rm surf}(t_0)\approx \Sigma_{\rm surf}(t_0)A$ が定まり，$M_{\rm in}$ と独立に任意調整できる自由度は持たない．本研究では $M_{\rm in}$ を深部供給を支える貯蔵層の基準量として保持し，表層はその上に形成される照射・除去の対象として区別する．

### 3.2 物理定数・物性値

本研究で用いる主要な物理定数・惑星定数・粒子物性を表\ref{tab:method-phys}にまとめる．定数（$G,c,\sigma_{\rm SB},R$）は 2018 CODATA 推奨値に基づき採用した \citep{Tiesinga2021_RMP_CODATA2018}．火星質量 $M_{\rm Mars}$ と平均半径 $R_{\rm Mars}$ は，NASA/JPL Horizons が提供する惑星物理量（physical data）から採用した \citep{JPLHorizons}．材料依存パラメータは基準ケースではフォルステライト（$\mathrm{Mg_2SiO_4}$）を代表組成として近似し，粒子密度 $\rho$ や飽和蒸気圧式の係数などは文献の実験・コンパイル値に基づいて与える．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{物理定数・惑星定数・粒子物性（基準計算）}
  \label{tab:method-phys}
  \begin{tabular}{@{}L{0.24\textwidth} L{0.18\textwidth} L{0.14\textwidth} L{0.36\textwidth}@{}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $G$ & $6.67430\times10^{-11}$ & m$^{3}$\,kg$^{-1}$\,s$^{-2}$ & 万有引力定数（CODATA 2018） \\
    $c$ & $2.99792458\times10^{8}$ & m\,s$^{-1}$ & 光速（定義値；CODATA 2018） \\
    $\sigma_{\rm SB}$ & $5.670374419\times10^{-8}$ & W\,m$^{-2}$\,K$^{-4}$ & ステファン・ボルツマン定数（CODATA 2018） \\
    $M_{\rm Mars}$ & $6.4171\times10^{23}$ & kg & 火星質量（Horizons physical data） \\
    $R_{\rm Mars}$ & $3.38992\times10^{6}$ & m & 火星体積平均半径（Horizons physical data） \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & 粒子密度（フォルステライト） \\
    $R$ & 8.314462618 & J\,mol$^{-1}$\,K$^{-1}$ & 気体定数（CODATA 2018；HKL に使用） \\
    \hline
  \end{tabular}
\end{table}


### 3.3 基準パラメータ

基準計算の採用値を表\ref{tab:method-param}に，衝突破砕の破壊閾値比エネルギー $Q_D^*(s)$ の係数を表\ref{tab:methods_qdstar_coeffs}に示す．
シミュレーションは $r\in[r_{\rm in},r_{\rm out}]$ の環状領域とし，巨大衝突により形成されるロッシュ限界内側のデブリ円盤成分を代表させる．ロッシュ限界はおよそ数 $R_{\rm Mars}$ に位置し\citep{Rosenblatt2016_NatGeo9_8}，岩石質粒子に対しては $a_R\simeq 2.7\,R_{\rm Mars}$ 程度が用いられる\citep{CanupSalmon2018_SciAdv4_eaar6887}．基準計算では $r_{\rm out}=2.7\,R_{\rm Mars}$ としてロッシュ限界付近まで計算領域を取り，ロッシュ限界外側での衛星胚形成過程は本研究の対象外とする．
粒子の力学的励起度は，離心率 $e_0$ と傾斜角 $i_0$ により与える．巨大衝突直後の粒子群は強く励起され得るため，基準計算では比較的大きな $e_0$ を採用し（表\ref{tab:method-param}），その影響は感度解析で評価する．鉛直スケールハイトは $H_k=H_{\rm factor}\, i r$ とし，$H_{\rm factor}$ は幾何学的厚みの不確かさを吸収する補正因子として導入する．

表層面密度の初期値は 3.1節の規格化条件（$\tau_0$）により定まり，基準計算では $\tau_0=1$ を採用する．この設定は，照射を受ける表層が視線方向光学的厚さ $\tau_{\rm los}\sim 1$ の層で代表されるという物理像に対応する\citep{TakeuchiLin2003_ApJ593_524}．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\caption{基準計算の採用値（幾何・力学・供給）}
\label{tab:method-param}
\begin{tabular}{p{0.30\textwidth} p{0.22\textwidth} p{0.12\textwidth} p{0.26\textwidth}}
\hline
記号 & 値 & 単位 & 備考 \\
\hline
$r_{\rm in}$ & 1.0 & $R_{\rm Mars}$ & 内端半径 \\
$r_{\rm out}$ & 2.7 & $R_{\rm Mars}$ & 外端半径 \\
$N_r$ & 32 & -- & 半径セル数（リング分割） \\
$M_{\rm in}$ & $3.0\times10^{-5}$ & $M_{\rm Mars}$ & 内側円盤質量 \\
$s_{\min,\rm cfg}$ & $1.0\times10^{-7}$ & $\mathrm{m}$ & PSD 下限（計算上） \\
$s_{\max}$ & $3.0$ & $\mathrm{m}$ & PSD 上限 \\
$n_{\rm bins}$ & 40 & -- & サイズビン数 \\
$f_{\rm los}$ & 1.0 & -- & LOS 幾何因子（式\ref{eq:tau_los_definition}） \\
$\tau_0$ & 1.0 & -- & 初期 $\tau_{\rm los}$ 規格化値（式\ref{eq:sigma_surf0_from_tau0}） \\
$\tau_{\rm stop}$ & 2.302585 & -- & 評価の停止指標（$\ln 10$） \\
$e_0$ & 0.5 & -- & 離心率 \\
$i_0$ & 0.05 & $\mathrm{rad}$ & 傾斜角 \\
$H_{\rm factor}$ & 1.0 & -- & $H_k=H_{\rm factor}\, i r$ \\
$\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数 \\
$\mu_{\rm sup}$ & 1.0 & -- & 供給スケール（式\ref{eq:R_base_definition}） \\
$f_{\rm orb}$ & 0.05 & -- & $\mu_{\rm sup}=1$ のときの 1 軌道あたり供給比率 \\
$\tau_{\rm ref}$ & 1.0 & -- & 供給スケール参照光学的厚さ（$\tau_{\rm los}$） \\
$\alpha_{\rm frag}$ & 3.5 & -- & 破片分布指数 \\
$\rho$ & 3270 & $\mathrm{kg\,m^{-3}}$ & 粒子密度（表\ref{tab:method-phys}） \\
\hline
\end{tabular}
\end{table}

初期 PSD のパラメータを表\ref{tab:methods_initial_psd_params}に示す．$s_{\rm cut}$ は最微小粒子領域をパラメタライズするカットオフ粒径であり，$s_{\rm min,solid}$ と $s_{\rm max,solid}$ は固相 PSD の範囲を定める．${\rm width}_{\rm dex}$ は両成分に共通の対数幅である．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\caption{基準計算の初期 PSD（melt lognormal mixture）}
\label{tab:methods_initial_psd_params}
\begin{tabular}{p{0.36\textwidth} p{0.22\textwidth} p{0.20\textwidth}}
\hline
記号 & 値 & 単位 \\
\hline
$f_{\rm fine}$ & 0.03 & -- \\
$s_{\rm fine}$ & $1.0\times10^{-7}$ & $\mathrm{m}$ \\
$s_{\rm meter}$ & 1.5 & $\mathrm{m}$ \\
${\rm width}_{\rm dex}$ & 0.3 & -- \\
$s_{\rm cut}$ & $1.0\times10^{-7}$ & $\mathrm{m}$ \\
$s_{\rm min,solid}$ & $1.0\times10^{-4}$ & $\mathrm{m}$ \\
$s_{\rm max,solid}$ & 3.0 & $\mathrm{m}$ \\
$\alpha_{\rm solid}$ & 3.5 & -- \\
\hline
\end{tabular}
\end{table}

衝突破砕における破片分布指数 $\alpha_{\rm frag}$ は，定常的な衝突カスケードで用いられる $3.5$ を基準値とする\citep{Dohnanyi1969_JGR74_2531,Birnstiel2011_AA525_A11}．破壊閾値比エネルギー $Q_D^*(s)$ は，強度支配項と重力支配項を併せ持つ経験式に基づき，係数として \citet{BenzAsphaug1999_Icarus142_5} のスケーリングを採用する．衝突速度に依存する係数は代表速度で与え，速度域 $1$--$7\,\mathrm{km\,s^{-1}}$ に対する採用値を表\ref{tab:methods_qdstar_coeffs}にまとめる．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\caption{基準計算の $Q_D^*$ 係数（$v_{\rm ref}$ は $\mathrm{km\,s^{-1}}$，$Q_s$ と $B$ は BA99 の cgs 単位）}
\label{tab:methods_qdstar_coeffs}
\begin{tabular}{p{0.16\textwidth} p{0.20\textwidth} p{0.16\textwidth} p{0.20\textwidth} p{0.16\textwidth}}
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
## 4. 数値計算法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

### 4.1 離散化

粒径 $s$ の空間は対数等間隔のビンで離散化し，$k$ 番目のビン中心を $s_k$，ビン境界を $s_{k-1/2},\,s_{k+1/2}$ とする．連続分布 $n(s)=\mathrm{d}N/\mathrm{d}s$ に対して，状態量 $N_k$ はビン内の数密度として

\[
N_k \equiv \int_{s_{k-1/2}}^{s_{k+1/2}} n(s)\,\mathrm{d}s
\]

で定義する．このとき，粒子の質量 $m_k$ を代表粒径 $s_k$ における球近似で $m_k=(4\pi/3)\rho s_k^3$ とおけば，表層の面密度は $\Sigma_{\rm surf}=\sum_k m_k N_k$ で与えられる．以後，衝突による損失は $N_k$ を減らす効果，生成は $N_k$ を増やす効果としてビン上で評価する．
シミュレーションの粒径範囲は下限 $s_{\min}$ と上限 $s_{\max}$ により与え，$s_{\min}\le s \le s_{\max}$ を数値的に解像する領域とみなす．ただし下限側は，放射圧によって束縛軌道を維持できない粒子が存在するため，有効下限

\[
s_{\min,\rm eff}(t)\equiv \max\!\left(s_{\min},\,s_{\rm blow}(t)\right)
\]

を用いる．ここで $s_{\rm blow}(t)$ はその時刻のブローアウト粒径である．実装上は粒径格子そのものを時刻ごとに張り替えるのではなく，$s\lesssim s_{\rm blow}$ の領域を一次シンクとして除去することで，結果として $s_{\min,\rm eff}$ 未満が系に留まりにくい状態を再現する．この $s_{\min,\rm eff}$ は，供給粒子をどのビンに注入するか等の境界条件としても働くため，下限の扱いを明示しておくことが再現性に直結する．
上限 $s_{\max}$ より大きい成分は，衝突破砕によって短時間に形成される未解像の大粒子ではなく，むしろ外部供給や深部リザーバとして代表化したい成分である．そこで本研究では，$s_{\max}$ を超える粒子を直接追跡せず，その影響は供給項 $F_k$ として粒径分布へ注入する近似を採る．
半径方向は第1節で定義したセル分割に従い，セルごとに局所量（$\Sigma_{\rm surf}$，$\tau_{\rm los}$，供給率など）を更新しつつ，粒径分布の進化を計算する．

### 4.2 数値解法と停止条件

衝突破砕の Smoluchowski 型の連立常微分方程式は，粒径ビン数が増えるほど剛性が強くなり，とくに小粒径側で衝突頻度が高い場合に，陽的時間積分は刻み制約を受けやすい．実際，デブリ円盤やデブリディスクでは，一次の Euler 法と可変刻み制御により時間発展を追っている\citep{Thebault2003_AA408_775,Krivov2006_AA455_509}．一方で，定常解や長時間スケールを効率よく求めるため，陰的スキームを用いる実装も採られている\citep{Birnstiel2011_AA525_A11}．
本研究で必要なのは，(i) 衝突による損失が大きい領域でも $N_k\ge 0$ を維持でき，(ii) 衝突過程それ自体の質量保存を破らない範囲で，供給とシンクを加えた質量収支を追跡でき，(iii) 放射圧による急速なブローアウトとも整合的に結合できることである．そこで，衝突損失のみを陰的に扱い，生成・供給・一次シンクを陽的に扱う IMEX（implicit–explicit）型の一次 BDF（BDF(1)）を採用する．この分割は，発散しやすい（剛性の強い）項に限定して陰解法を用い，残りは見通しのよい陽解法で扱う．

$N_k^n$ を時刻 $t^n$ における $k$ ビンの数密度とする．衝突カーネル $C_{ij}$ と破片再配分テンソルから，衝突による生成項 $G_k^n$ と損失時定数 $t_{{\rm coll},k}^n$ を評価し，さらに供給項 $F_k^n$ と一次シンク $S_k^n$（ブローアウト，昇華，追加シンク等の合算）を加える．このとき，IMEX-BDF(1) による更新は次式で与える：

\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}.
\end{equation}

ここで $dt_{\rm eff}$ はこの更新で実際に用いる内部ステップ幅である．分母の項が衝突損失の陰的取り扱いに対応し，$dt_{\rm eff}\gtrsim t_{{\rm coll},k}$ の場合でも $N_k^{n+1}$ が負に落ちにくい形になっている．一方，$G_k$ と $F_k$ は陽的に入るため，時間刻みが過大であれば過剰生成により非負性を破る可能性が残る．したがって本研究では，次節で述べるように非負性と質量収支の二重の判定により $dt_{\rm eff}$ を制御する．
$t_{{\rm coll},k}$ は，衝突カーネルが与える単位面積当たりの衝突頻度から，$k$ ビン粒子 1 個あたりの損失率に換算した量で定義する．具体的には，$k$ ビン粒子が他の全ビンと衝突する頻度を $N_k$ で割った量を損失係数とみなし，その逆数として衝突時定数を得る．この定義は，$t_{{\rm coll},k}$ が短いほど $k$ ビン粒子が速く失われるという描像と合致する．
外側の時間刻み $\Delta t$ は，温度曲線 $T_M(t)$ の与え方や，ブローアウト時定数 $t_{\rm blow}$ を含む物理過程の変化を解像できるように設定する．ただし，粒径分布の更新では，$\Delta t$ のまま式\ref{eq:imex_bdf1_update}を適用すると非負性や質量収支が破れる場合がある．そこで，粒径分布の更新には内部ステップ幅 $dt_{\rm eff}\le \Delta t$ を導入し，まず

\[
dt_{\rm eff}\leftarrow \min\!\left(\Delta t,\, f_{\rm safe}\min_k t_{{\rm coll},k}\right)
\]

を初期値として与える．ここで $f_{\rm safe}$ は安全率であり，本研究では $f_{\rm safe}=0.1$ を用いる．この初期値は，衝突時定数が最も短いビンを基準に衝突損失の剛性を避けるための経験的な基準である．

そのうえで，$dt_{\rm eff}$ を用いて式\ref{eq:imex_bdf1_update}を一度評価し，(i) いずれかのビンで $N_k^{n+1}<0$ が生じる，あるいは (ii) 次節で定義する質量収支誤差 $\epsilon_{\rm mass}$ が許容値を超える場合には，$dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として同じ外側ステップ内で再計算する．この半減による受理判定を，非負性と質量収支の両方が満たされるまで繰り返し，最終的に受理された $dt_{\rm eff}$ をそのセルの粒径分布更新に採用する．
本論文では，外側ステップで時刻 $t$ を $\Delta t$ だけ進める一方，衝突カスケードの更新と質量収支判定には $dt_{\rm eff}$ を用いる．したがって，累積損失の更新（式\ref{eq:mass_loss_update}）で用いる $\Delta t$ は外側ステップ幅であり，$\dot{M}_{\rm out}$ などはその区間に対する平均量として記録する．

### 4.3 質量保存の検査と停止条件

衝突項だけを取り出せば，破片再配分が正しく実装されている限り，理想的には質量は保存される．しかし実際には，(i) 生成項が陽的であること，(ii) ブローアウトや追加シンクが陽的に入ること，(iii) 有限精度計算の丸め誤差が累積することにより，離散化された系では微小だが無視できない収支ずれが生じ得る．そこで本研究では，各内部ステップごとに次の形で質量収支誤差を定義し，時間刻み受理の判定に用いる：

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
\Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
\Delta\Sigma &= \Sigma^{n+1} + dt_{\rm eff}\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + dt_{\rm eff}\,\dot{\Sigma}_{\rm in}\right),\\
\epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

ここで $\dot{\Sigma}_{\rm in}$ は外部供給による面密度注入率であり，第\ref{sec:method-supply}節で与えた供給モデルに基づいて $F_k$ を構成したときの $\dot{\Sigma}_{\rm in}=\sum_k m_k F_k$ に対応する．一方，$\dot{\Sigma}_{\rm extra}$ はブローアウト，昇華，追加シンクなど，陽的に扱う一次損失の合算である．この定義により，衝突再配分は質量保存的であり，供給は系へ質量を加え，シンクは系から質量を奪うという期待が，離散化後の更新でも満たされているかを，$dt_{\rm eff}$ のスケールで直接点検できる．
本研究では，$\epsilon_{\rm mass}\le 5\times10^{-3}$（相対誤差 0.5%）を受理基準とし，この条件を満たさない場合は前節の手順に従って $dt_{\rm eff}$ を半減する．なお，$\dot{\Sigma}_{\rm extra}$ はステップ開始時の分布 $N_k^n$ に基づいて評価し，陽的に扱う損失と整合する形で収支を検査する．

計算全体の時間積分は，火星表面温度 $T_M$ が所定の閾値 $T_{\rm end}$ に到達する時刻を終端 $t_{\rm end}$ として定義する．本論文では $T_{\rm end}=2000,\mathrm{K}$ を採用し，高温期に対応する時間帯に解析対象を絞る．この設定は，放射圧による表層質量損失が顕著になる条件を外さない範囲で計算時間を制御する意図を持つ．加えて，各半径セルには早期停止条件を設ける．本研究の表層モデルは，火星放射が表層に到達して粒子温度や放射圧を決めるという近似の上に立っているため，視線方向の光学的厚さが大きくなると，この近似は破綻する．そこで，セルごとに

\[
\tau_{\rm los} > \tau_{\rm stop}
\]

を満たした時点でそのセルの粒径分布更新を停止し，以後は本モデルの適用範囲外として扱う．本論文では透過率 $\exp(-\tau_{\rm los})$ が $0.1$ 以下となる目安として $\tau_{\rm stop}=\ln 10$ を採用する．
さらに，ブローアウト粒径が格子下限を下回る状況（$s_{\rm blow}\le s_{\min}$）が継続する場合には，供給・損失の境界条件が実質的に変わるため，設定に応じて早期終了とする．これらの停止条件により，積分期間を物理的に意味のある高温期へ合わせると同時に，適用範囲外の領域で数値解を延命させることを避ける．
また，数値計算の効率化のため，全円盤の流出率 $\dot{M}_{\rm out}$ が十分小さく，式\ref{eq:mass_loss_update}で更新される $M_{\rm loss}$ の増分が無視できる状態が継続する場合には，それ以後の時間積分を打ち切る設定も用いる．これは累積損失の評価（$M_{\rm loss}(t_{\rm end})$）に実質的な寄与がない尾部を省略して計算時間を短縮するための処理である．
## 5. 出力と検証

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

### 5.1 出力と検証

直接追跡する状態量は，各粒径ビン $k$ に離散化した粒子数面密度 $N_k(t)$ と，表層面密度 $\Sigma_{\rm surf}(t)$ である．したがって，再解析のために必要な情報は，(a) これらの時間発展を決める入力条件（初期条件・物理パラメータ・外部テーブルの参照情報を含む）と，(b) 主要診断量の時系列，(c) PSD（粒径分布）の履歴，(d) 計算終了時点の集計，および (e) 数値的健全性を確認する検証ログである．これらを実行ごとに保存しておけば，本文の図表は保存された出力のみを入力として再構成できる．再解析に必要な出力の最小セットを表\ref{tab:method_repro_outputs}に示す．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{再解析に必要な出力（\texttt{OUTDIR/}）}
  \label{tab:method_repro_outputs}
\begin{tabular}{@{}L{0.30\textwidth} L{0.14\textwidth} L{0.52\textwidth}@{}}
    \hline
    相対パス & 形式 & 内容（要点） \\
    \hline
    \texttt{run\_config.json} &
    JSON &
    展開後の設定と採用値，実行環境，外部入力（テーブル等）の参照情報 \\
    \texttt{series/run.parquet} &
    Parquet &
    主要スカラー時系列（$t,\Delta t,\tau_{\rm los},s_{\rm blow},s_{\min},\Sigma_{\rm surf},\dot{M}_{\rm out},M_{\rm loss}$ など） \\
    \texttt{series/psd\_hist.parquet} &
    Parquet &
    PSD 履歴（粒径ビンごとの $N_k$，および $\Sigma_{\rm surf}$ など） \\
    \texttt{summary.json} &
    JSON &
    終端要約（$M_{\rm loss}$，停止理由，検証集計など） \\
    \texttt{checks/mass\_budget.csv} &
    CSV &
    質量検査ログ（式\ref{eq:mass_budget_definition}；$\epsilon_{\rm mass}$ の履歴） \\
    \texttt{series/diagnostics.parquet} &
    Parquet &
    （任意）遮蔽などの追加診断（設定により出力） \\
    \texttt{checks/\allowbreak mass\_budget\_cells.csv} &
    CSV &
    （任意, 1D）セル別の質量検査ログ（設定により出力） \\
    \texttt{checks/validation.json} &
    JSON &
    （任意）時間刻み・粒径ビンの収束判定など（設定により出力） \\
    \hline
  \end{tabular}
\end{table}

保存する診断量の中心は，各ステップの時刻 $t$ と時間刻み $\Delta t$ に加え，放射圧流出を特徴づける $\tau_{\rm los},\,s_{\rm blow},\,s_{\min}$，および表層の状態を表す $\Sigma_{\rm surf},\,\dot{M}_{\rm out}$ などである．PSD は $N_k(t)$ を独立に記録し，任意時刻の分布形状とその変化を追跡できるようにする．1D 計算では半径セルごとに同様の時系列を保存するため，円盤全体の量は半径積分として再構成できる．出力は JSON/Parquet/CSV で保存し，入力条件の記録，主要スカラー時系列，PSD 履歴，終端要約，質量検査ログが最小セットとして残るよう構成している．
円盤からの累積損失 $M_{\rm loss}$ は，表層流出率 $\dot{M}_{\rm out}$ と追加シンクによる損失率 $\dot{M}_{\rm sinks}$ を区分一定近似で積算し，式\ref{eq:mass_loss_update}で更新する\citep{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示すため，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様に規格化した量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

ここで $\Delta t$ は外側ステップ幅であり，$\dot{M}_{\rm out}^{n}$ と $\dot{M}_{\rm sinks}^{n}$ は区間 $[t^n,t^{n+1})$ に対するステップ平均量として扱う．粒径分布の更新で $dt_{\rm eff}<\Delta t$ が採用された場合でも，この平均量で損失を積算することで $M_{\rm loss}$ を更新する．
計算の検証は，質量保存，時間刻み収束，および粒径ビン収束の 3 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．質量保存は，式\ref{eq:mass_budget_definition}で定義する相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下であることを要求する．

一方，数値離散化に起因する系統誤差は，より細かい離散化に対する相対差で評価する．ここでは任意の指標 $X$ について相対差を

\begin{equation}
\label{eq:relative_difference_definition}
\Delta_{\rm rel}(X)\equiv \frac{|X({\rm coarse})-X({\rm ref})|}{|X({\rm ref})|}
\end{equation}

と定義する．時間刻み収束では ${\rm ref}$ を $\Delta t/2$ とした計算とし，$\Delta_{\rm rel}(M_{\rm loss})\le 1\%$ を合格条件とする．$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で時間積分される累積量であるため，離散化誤差が蓄積して現れやすく，収束判定の代表指標として適している．

粒径ビン収束では，${\rm ref}$ を粒径ビン幅を 1/2 にしてビン数を 2 倍とした PSD の計算とし，時間刻み収束と同じく $\Delta_{\rm rel}(M_{\rm loss})\le 1\%$ を要求する．この比較により，粒径離散化の取り方が，結論に影響し得る大きさの系統誤差を導入していないことを確認する．

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
時間刻み収束 & $\Delta t$ と $\Delta t/2$ の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
粒径ビン収束（PSD 解像度） & 基準ビンとビン数を 2 倍にした計算の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
\hline
\end{tabular}
\end{table}

### 5.2 仮定と限界

本手法は，いくつかの近似を導入している．
まず，半径方向の輸送過程（粘性拡散や PR ドラッグなど）は支配方程式としては解かず，各半径セルにおける局所進化を独立に評価する．
次に，衝突速度の評価では，相対速度を与える離心率 $e$ と傾斜角 $i$ を代表値として固定し，低離心率・低傾斜の近似式を速度スケールとして用いる．この近似は，厳密な励起・散乱過程を扱わない代わりに，衝突頻度と破壊効率の主要な依存性を一つのスケールに押し込み，衝突カスケードの時間発展を記述可能にするものである．
また，自己遮蔽は遮蔽係数 $\Phi$ を有効不透明度 $\kappa_{\rm eff}$ に反映させ，照射・表層アウトフローの評価に用いる．一方，早期停止は視線方向光学的厚さ $\tau_{\rm los}>\tau_{\rm stop}$ により行う．しかし，遮蔽によって放射圧パラメータ $\beta$ 自体が連続的に減衰するような詳細な放射輸送は扱わない．したがって本手法は，遮蔽が強くなり過ぎ，表層という概念が曖昧になる領域では，そもそも適用対象外として計算を停止する設計になっている．
さらに，昇華は粒径縮小 $ds/dt$ を一次シンクへ写像し，粒径空間の移流としては追跡しない．この近似は，昇華が分布形状を滑らかに輸送する効果よりも，その粒径帯の粒子が消失する効果を優先して取り込むものである．
<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

## 付録 A. 記号表

### A.1 主要記号（本研究のダスト円盤モデル）

\begin{longtable}{@{}L{0.17\linewidth}L{0.43\linewidth}L{0.12\linewidth}L{0.18\linewidth}@{}}
  \caption{主要記号表（本研究で用いる記号と単位）}\label{tab:app_symbols_main}\\
  \noalign{\small\setlength{\tabcolsep}{3pt}}
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endfirsthead
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endhead
  \hline
  \multicolumn{4}{r}{次ページへ続く}\\
  \hline
  \endfoot
  \hline
  \endlastfoot
  $t$ & 時刻 & $\mathrm{s}$ & 解析では年へ換算して表示する場合がある \\
  $r$ & 半径（代表半径） & $\mathrm{m}$ & 0D では代表値のみを用いる \\
  $r_{\rm in},r_{\rm out}$ & 計算領域の内端・外端半径 & $\mathrm{m}$ & 環状領域 $[r_{\rm in},r_{\rm out}]$ \\
  $A$ & 環状領域の面積 & $\mathrm{m^{2}}$ & 式\ref{eq:annulus_area_definition} \\
  $A_\ell$ & セル $\ell$ の面積 & $\mathrm{m^{2}}$ & 1D の半径セル（リング）ごとの面積 \\
  $M_{\rm in}$ & ロッシュ限界内側の内側円盤質量 & $\mathrm{kg}$ & 入力（3.1節） \\
  $\Delta M_{\rm in}$ & 遷移期における不可逆損失（累積） & $\mathrm{kg}$ & 本論文では $M_{\rm loss}$ と同義 \\
  $M_{\rm in}'$ & 更新後の内側円盤質量（長期モデルへ渡す量） & $\mathrm{kg}$ & $M_{\rm in}'=M_{\rm in}(t_0)-M_{\rm loss}(t_{\rm end})$ \\
  $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
  $T_{\rm orb}$ & 公転周期 & $\mathrm{s}$ & 式\ref{eq:torb_definition} \\
  $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
  $s$ & 粒子半径 & $\mathrm{m}$ & PSD の独立変数 \\
  $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
  $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
  $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
  $\rho$ & 粒子密度 & $\mathrm{kg\,m^{-3}}$ & 表\ref{tab:method-phys} \\
  $Y_{kij}$ & 衝突 $(i,j)$ による破片生成の質量分率（ビン $k$ への配分） & -- & $\sum_k Y_{kij}=1$（式\ref{eq:fragment_yield_normalization}） \\
  $F_k$ & 供給ソース項（サイズビン $k$ への注入率） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:smoluchowski} \\
  $S_k$ & 追加シンクの実効ロス率 & $\mathrm{s^{-1}}$ & 式\ref{eq:smoluchowski} \\
  $\Sigma_{\rm surf}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
  $\kappa_{\rm surf}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
  $\tau_\perp$ & 鉛直方向の光学的厚さ（近似） & -- & $\tau_\perp=\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
  $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ \\
  $\omega_0$ & 単一散乱アルベド（遮蔽テーブル入力） & -- & $\Phi(\tau,\omega_0,g)$ の入力 \\
  $g$ & 非対称因子（遮蔽テーブル入力） & -- & $g=\langle\cos\theta\rangle$；$\Phi(\tau,\omega_0,g)$ の入力 \\
  $\kappa_{\rm eff}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
  $f_{\rm los}$ & 鉛直光学的厚さ $\tau_\perp$ を $\tau_{\rm los}$ へ写像する幾何因子 & -- & $\tau_{\rm los}=f_{\rm los}\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
  $\tau_{\rm los}$ & 火星視線方向光学的厚さ（近似） & -- & 式\ref{eq:tau_los_definition}; 遮蔽評価・初期規格化・停止判定に用いる \\
  $\tau_0$ & 初期視線方向光学的厚さ（規格化値） & -- & 3.1節 \\
  $\tau_{\rm stop}$ & 停止判定の閾値（$\tau_{\rm los}>\tau_{\rm stop}$） & -- & 4.2節 \\
  $\Sigma_{\tau_{\rm los}=1}$ & $\tau_{\rm los}=1$ に対応する参照面密度 & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau_los1_definition}（$\Sigma_{\tau_{\rm los}=1}=(f_{\rm los}\kappa_{\rm surf})^{-1}$） \\
  $\Sigma_{\tau=1}$ & 光学的厚さ $\tau=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition} \\
\end{longtable}

\begin{longtable}{@{}L{0.17\linewidth}L{0.43\linewidth}L{0.12\linewidth}L{0.18\linewidth}@{}}
  \caption{主要記号表（続き）}\label{tab:app_symbols_main_cont}\\
  \noalign{\small\setlength{\tabcolsep}{3pt}}
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endfirsthead
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endhead
  \hline
  \multicolumn{4}{r}{次ページへ続く}\\
  \hline
  \endfoot
  \hline
  \endlastfoot
  $T_M$ & 火星表面温度 & $\mathrm{K}$ & 放射・昇華の入力 \\
  $\langle Q_{\rm abs}\rangle$ & 粒子温度評価に用いる有効吸収効率 & -- & 式\ref{eq:grain_temperature_definition} \\
  $\langle Q_{\rm pr}\rangle$ & Planck 平均放射圧効率 & -- & テーブル入力 \\
  $\beta$ & 軽さ指標（放射圧/重力） & -- & 式\ref{eq:beta_definition}; $\beta>0.5$ で非束縛 \\
  $s_{\rm blow}$ & ブローアウト粒径 & $\mathrm{m}$ & 式\ref{eq:s_blow_definition} \\
  $t_{\rm blow}$ & ブローアウト滞在時間 & $\mathrm{s}$ & 式\ref{eq:t_blow_definition} \\
  $\chi_{\rm blow}$ & ブローアウト滞在時間係数 & -- & 式\ref{eq:t_blow_definition}; \texttt{auto} は式\ref{eq:chi_blow_auto_definition} \\
  $\dot{\Sigma}_{\rm out}$ & 表層流出（面密度フラックス） & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:surface_outflux} \\
  $\dot{M}_{\rm out}$ & 円盤全体の質量流出率 & $\mathrm{kg\,s^{-1}}$ & 式\ref{eq:mdot_out_definition}（出力は $\dot{M}_{\rm out}/M_{\rm Mars}$ を記録） \\
  $M_{\rm loss}$ & 累積損失 & $\mathrm{kg}$ & $\dot{M}_{\rm out}$ 等を積分（出力は $M_{\rm loss}/M_{\rm Mars}$ を記録） \\
  $R_{\rm base}$ & 供給の基底レート & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:R_base_definition} \\
  $\epsilon_{\rm mix}$ & 混合係数（供給の有効度） & -- & 2.3節 \\
  $\mu_{\rm sup}$ & 供給スケール（無次元） & -- & 式\ref{eq:R_base_definition} \\
  $f_{\rm orb}$ & $\mu_{\rm sup}=1$ のときの 1 軌道あたり供給比率 & -- & 式\ref{eq:R_base_definition} \\
  $\tau_{\rm ref}$ & 供給スケール参照光学的厚さ & -- & 式\ref{eq:R_base_definition} \\
  $C_{ij}$ & 衝突イベント率（単位面積あたり，$N_iN_j$ を含む） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:collision_kernel} \\
  $v_{ij}$ & 相対速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vrel_pericenter_definition} \\
  $e, i$ & 離心率・傾斜角（分散） & -- & 相対速度の評価に用いる \\
  $Q_D^*$ & 破壊閾値（比エネルギー） & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:qdstar_definition} \\
  $Q_R$ & reduced specific kinetic energy & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:q_r_definition} \\
  $F_{LF}$ & 最大残存率（最大残存体質量/総質量） & -- & 式\ref{eq:F_LF_definition} \\
  $\mu_{\rm LS}$ & 速度外挿に用いる指数 & -- & $v^{-3\mu_{\rm LS}+2}$（既定 0.45） \\
  $\alpha_{\rm evap}$ & 蒸発（固相では昇華）係数（HKL） & -- & 式\ref{eq:hkl_flux} \\
  $\mu$ & 分子量（HKL） & $\mathrm{kg\,mol^{-1}}$ & 式\ref{eq:hkl_flux} \\
\end{longtable}

### A.2 主要定数と惑星パラメータ（参照）

\begin{longtable}{@{}L{0.17\linewidth}L{0.43\linewidth}L{0.18\linewidth}L{0.12\linewidth}@{}}
  \caption{主要定数と惑星パラメータ}\label{tab:app_symbols_constants}\\
  \noalign{\small\setlength{\tabcolsep}{3pt}}
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endfirsthead
  \hline
  記号 & 意味 & 単位 & 備考 \\
  \hline
  \endhead
  \hline
  \multicolumn{4}{r}{次ページへ続く}\\
  \hline
  \endfoot
  \hline
  \endlastfoot
  $G$ & 万有引力定数 & $\mathrm{m^{3}\,kg^{-1}\,s^{-2}}$ & 表\ref{tab:method-phys} \\
  $c$ & 光速 & $\mathrm{m\,s^{-1}}$ & 表\ref{tab:method-phys} \\
  $\sigma_{\rm SB}$ & ステファン--ボルツマン定数 & $\mathrm{W\,m^{-2}\,K^{-4}}$ & 表\ref{tab:method-phys} \\
  $R$ & 気体定数 & $\mathrm{J\,mol^{-1}\,K^{-1}}$ & 表\ref{tab:method-phys} \\
  $M_{\rm Mars}$ & 火星質量 & $\mathrm{kg}$ & 表\ref{tab:method-phys} \\
  $R_{\rm Mars}$ & 火星半径 & $\mathrm{m}$ & 表\ref{tab:method-phys} \\
\end{longtable}

### A.3 略語索引

\begin{longtable}{@{}L{0.18\textwidth}L{0.44\textwidth}L{0.28\textwidth}@{}}
  \caption{略語索引}\label{tab:app_abbreviations}\\
  \noalign{\small\setlength{\tabcolsep}{3pt}}
  \hline
  略語 & 日本語 / 英語 & 備考 \\
  \hline
  \endfirsthead
  \hline
  略語 & 日本語 / 英語 & 備考 \\
  \hline
  \endhead
  \hline
  \multicolumn{3}{r}{次ページへ続く}\\
  \hline
  \endfoot
  \hline
  \endlastfoot
  PSD & 粒径分布 / particle size distribution & サイズビン分布 $n(s)$ \\
  LOS & 視線方向 / line of sight & $\tau_{\rm los}$ に対応 \\
  IMEX & implicit-explicit & IMEX-BDF(1) に使用 \\
  BDF & backward differentiation formula & 一次 BDF \\
  $Q_{\rm pr}$ & 放射圧効率 / radiation pressure efficiency & テーブル入力 \\
  $Q_D^*$ & 破壊閾値 / critical specific energy & 破壊強度 \\
  HKL & Hertz--Knudsen--Langmuir & 昇華フラックス \\
  PR & ポインティング--ロバートソン / Poynting--Robertson & PR ドラッグ \\
  Mie & ミー散乱 / Mie scattering & $Q_{\rm pr}$ テーブル生成に使用 \\
  RT & 放射輸送 / radiative transfer & 遮蔽 $\Phi$ の近似に関係 \\
  RM & 火星半径 / Mars radii & $r_{\rm in},r_{\rm out}$ の規格化に使用 \\
  1D & one-dimensional & 半径方向セル分割（リング分割） \\
\end{longtable}
<!--
document_type: reference
title: 主要物理過程のコード
-->

<!--
実装(.py): marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collide.py, marsdisk/physics/smol.py, marsdisk/physics/surface.py
-->

## 付録 B. 主要物理過程のコード

本文で用いた主要物理過程の実装を，代表的な関数単位で掲載する．可読性のため，import 文や周辺の補助関数は省略し，該当部分のみを抜粋して示す．

### B.1 放射圧とブローアウト（R2–R3）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/radiation.py

def beta(
    s: float,
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Compute the ratio ``β`` of radiation pressure to gravity (R2). [@StrubbeChiang2006_ApJ648_652]

    The expression follows directly from conservation of momentum using the
    luminosity of Mars ``L_M = 4π R_M^2 σ T_M^4`` and reads

    ``β = 3 L_M ⟨Q_pr⟩ / (16 π c G M_M ρ s)``.
    """
    s_val = _validate_size(s)
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    qpr = _resolve_qpr(s_val, T_val, Q_pr, table, interp)
    numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
    denominator = 4.0 * constants.G * constants.M_MARS * constants.C * rho_val * s_val
    return float(numerator / denominator)


def blowout_radius(
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the blow-out grain size ``s_blow`` for ``β = 0.5`` (R3). [@StrubbeChiang2006_ApJ648_652]"""

    global _NUMBA_FAILED
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    if Q_pr is not None:
        qpr = _resolve_qpr(1.0, T_val, Q_pr, table, interp)
        if _USE_NUMBA_RADIATION and not _NUMBA_FAILED:
            try:
                return float(blowout_radius_numba(rho_val, T_val, qpr))
            except Exception as exc:
                _NUMBA_FAILED = True
                warnings.warn(
                    f"blowout radius numba kernel failed ({exc!r}); falling back to NumPy.",
                    NumericalWarning,
                )
        numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
        denominator = 2.0 * constants.G * constants.M_MARS * constants.C * rho_val
        return float(numerator / denominator)

    coef = (
        3.0
        * constants.SIGMA_SB
        * (T_val**4)
        * (constants.R_MARS**2)
        / (2.0 * constants.G * constants.M_MARS * constants.C * rho_val)
    )
    s_val = coef * _resolve_qpr(1.0, T_val, None, table, interp)
    for _ in range(8):
        qpr_val = _resolve_qpr(s_val, T_val, None, table, interp)
        s_new = coef * qpr_val
        if not np.isfinite(s_new) or s_new <= 0.0:
            break
        if abs(s_new - s_val) <= 1.0e-6 * max(s_new, 1.0e-30):
            s_val = s_new
            break
        s_val = s_new
    return float(s_val)
\end{Verbatim}

### B.2 自遮蔽と光学的厚さ（S0）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/shielding.py

def sigma_tau1(kappa_eff: float) -> float:
    """Return Σ_{τ=1} derived from κ_eff. Self-shielding Φ."""

    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for Σ_{τ=1}")
    if not np.isfinite(kappa_eff) or kappa_eff <= 0.0:
        return float(np.inf)
    return float(1.0 / float(kappa_eff))


def apply_shielding(
    kappa_surf: float,
    tau: float,
    w0: float,
    g: float,
    interp: type_Phi | None = None,
) -> Tuple[float, float]:
    """Return effective opacity and ``Σ_{τ=1}`` for given conditions. Self-shielding Φ."""

    if not isinstance(kappa_surf, Real):
        raise TypeError("surface opacity 'kappa_surf' must be a real number for Φ lookup")
    if not np.isfinite(kappa_surf):
        raise PhysicsError("surface opacity 'kappa_surf' must be finite for Φ lookup")
    if kappa_surf < 0.0:
        raise PhysicsError("surface opacity 'kappa_surf' must be greater or equal to 0 for Φ lookup")
    if not isinstance(tau, Real):
        raise TypeError("optical depth 'tau' must be a real number for Φ lookup")
    if not np.isfinite(tau):
        raise PhysicsError("optical depth 'tau' must be finite for Φ lookup")
    if not isinstance(w0, Real):
        raise TypeError("single-scattering albedo 'w0' must be a real number for Φ lookup")
    if not np.isfinite(w0):
        raise PhysicsError("single-scattering albedo 'w0' must be finite for Φ lookup")
    if not isinstance(g, Real):
        raise TypeError("asymmetry parameter 'g' must be a real number for Φ lookup")
    if not np.isfinite(g):
        raise PhysicsError("asymmetry parameter 'g' must be finite for Φ lookup")
    if interp is not None and not callable(interp):
        raise TypeError("Φ interpolator 'interp' must be callable")

    func = tables.interp_phi if interp is None else interp
    if not callable(func):
        raise TypeError("Φ interpolator must be callable")

    tau_val = float(tau)
    w0_val = float(w0)
    g_val = float(g)

    phi_table = _infer_phi_table(func)
    clamp_msgs: list[str] = []
    tau_min = tau_max = None
    if phi_table is not None:
        tau_vals = np.asarray(getattr(phi_table, "tau_vals"), dtype=float)
        w0_vals = np.asarray(getattr(phi_table, "w0_vals"), dtype=float)
        g_vals = np.asarray(getattr(phi_table, "g_vals"), dtype=float)
        if tau_vals.size:
            tau_min = float(np.min(tau_vals))
            tau_max = float(np.max(tau_vals))
            if tau_val < tau_min or tau_val > tau_max:
                clamped = float(np.clip(tau_val, tau_min, tau_max))
                clamp_msgs.append(
                    f"tau={tau_val:.6e}->{clamped:.6e} (range {tau_min:.6e}–{tau_max:.6e})"
                )
                tau_val = clamped
        if w0_vals.size:
            w0_min = float(np.min(w0_vals))
            w0_max = float(np.max(w0_vals))
            if w0_val < w0_min or w0_val > w0_max:
                clamped = float(np.clip(w0_val, w0_min, w0_max))
                clamp_msgs.append(
                    f"w0={w0_val:.6e}->{clamped:.6e} (range {w0_min:.6e}–{w0_max:.6e})"
                )
                w0_val = clamped
        if g_vals.size:
            g_min = float(np.min(g_vals))
            g_max = float(np.max(g_vals))
            if g_val < g_min or g_val > g_max:
                clamped = float(np.clip(g_val, g_min, g_max))
                clamp_msgs.append(
                    f"g={g_val:.6e}->{clamped:.6e} (range {g_min:.6e}–{g_max:.6e})"
                )
                g_val = clamped
    if clamp_msgs:
        logger.info("Φ lookup clamped: %s", ", ".join(clamp_msgs))

    def phi_wrapper(val_tau: float) -> float:
        tau_arg = float(val_tau)
        if phi_table is not None and tau_min is not None and tau_max is not None:
            tau_arg = float(np.clip(tau_arg, tau_min, tau_max))
        return float(func(tau_arg, w0_val, g_val))

    kappa_eff = effective_kappa(float(kappa_surf), tau_val, phi_wrapper)
    sigma_tau1_limit = sigma_tau1(kappa_eff)
    return kappa_eff, sigma_tau1_limit


def clip_to_tau1(sigma_surf: float, kappa_eff: float) -> float:
    """Clip ``Σ_surf`` so that it does not exceed ``Σ_{τ=1}``. Self-shielding Φ."""

    if not isinstance(sigma_surf, Real):
        raise TypeError("surface density 'sigma_surf' must be a real number for τ=1 clipping")
    if not np.isfinite(sigma_surf):
        raise PhysicsError("surface density 'sigma_surf' must be finite for τ=1 clipping")
    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for τ=1 clipping")
    if not np.isfinite(kappa_eff):
        raise PhysicsError("effective opacity 'kappa_eff' must be finite for τ=1 clipping")

    sigma_val = float(sigma_surf)
    kappa_val = float(kappa_eff)

    if kappa_val <= 0.0:
        if sigma_val < 0.0:
            logger.info(
                "Clamped Σ_surf from %e to 0 due to non-positive κ_eff=%e",
                sigma_val,
                kappa_val,
            )
        return max(0.0, sigma_val)

    if sigma_val < 0.0:
        logger.info(
            "Clamped Σ_surf from %e to 0 with κ_eff=%e",
            sigma_val,
            kappa_val,
        )
        return 0.0

    sigma_tau1_limit = sigma_tau1(kappa_val)
    if sigma_val > sigma_tau1_limit:
        logger.info(
            "Clamped Σ_surf from %e to τ=1 limit %e with κ_eff=%e",
            sigma_val,
            sigma_tau1_limit,
            kappa_val,
        )
        return float(sigma_tau1_limit)

    return sigma_val
\end{Verbatim}

### B.3 衝突カーネルとサブブローアウト生成（C1–C2）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/collide.py

def compute_collision_kernel_C1(
    N: Iterable[float],
    s: Iterable[float],
    H: Iterable[float],
    v_rel: float | np.ndarray,
    workspace: CollisionKernelWorkspace | None = None,
    *,
    use_numba: bool | None = None,
) -> np.ndarray:
    """Return the symmetric collision kernel :math:`C_{ij}`.

    Parameters
    ----------
    N:
        Number surface densities for each size bin.
    s:
        Characteristic sizes of the bins in metres.
    H:
        Vertical scale height of each bin in metres.
    v_rel:
        Mutual relative velocity between bins.  A scalar applies the same
        velocity to all pairs while a matrix of shape ``(n, n)`` provides
        pair-specific values.
    workspace:
        Optional size-only precomputations from
        :func:`prepare_collision_kernel_workspace`. When provided, ``s_sum``
        and the identity matrix reuse these buffers across calls.

    Returns
    -------
    numpy.ndarray
        Collision kernel matrix with shape ``(n, n)``.
    """

    global _NUMBA_FAILED

    N_arr = np.asarray(N, dtype=np.float64)
    s_arr = np.asarray(s, dtype=np.float64)
    H_arr = np.asarray(H, dtype=np.float64)
    if N_arr.ndim != 1 or s_arr.ndim != 1 or H_arr.ndim != 1:
        raise MarsDiskError("inputs must be one-dimensional")
    if not (len(N_arr) == len(s_arr) == len(H_arr)):
        raise MarsDiskError("array lengths must match")
    if np.any(N_arr < 0.0) or np.any(s_arr <= 0.0) or np.any(H_arr <= 0.0):
        raise MarsDiskError("invalid values in N, s or H")

    n = N_arr.size
    if workspace is not None:
        if workspace.s_sum_sq.shape != (n, n) or workspace.delta.shape != (n, n):
            raise MarsDiskError("workspace has incompatible shape for collision kernel")
        workspace_s_sum_sq = workspace.s_sum_sq
        workspace_delta = workspace.delta
        if workspace.v_mat_full is None or workspace.v_mat_full.shape != (n, n):
            workspace.v_mat_full = np.zeros((n, n), dtype=np.float64)
        if workspace.N_outer is None or workspace.N_outer.shape != (n, n):
            workspace.N_outer = np.zeros((n, n), dtype=np.float64)
        if workspace.H_sq is None or workspace.H_sq.shape != (n, n):
            workspace.H_sq = np.zeros((n, n), dtype=np.float64)
        if workspace.H_ij is None or workspace.H_ij.shape != (n, n):
            workspace.H_ij = np.zeros((n, n), dtype=np.float64)
        if workspace.kernel is None or workspace.kernel.shape != (n, n):
            workspace.kernel = np.zeros((n, n), dtype=np.float64)
    else:
        workspace_s_sum_sq = None
        workspace_delta = None
    use_matrix_velocity = False
    if np.isscalar(v_rel):
        v_scalar = float(v_rel)
        if not np.isfinite(v_scalar) or v_scalar < 0.0:
            raise MarsDiskError("v_rel must be finite and non-negative")
        v_mat = np.zeros((n, n), dtype=np.float64)
    else:
        v_mat = np.asarray(v_rel, dtype=np.float64)
        if v_mat.shape != (n, n):
            raise MarsDiskError("v_rel has wrong shape")
        if not np.all(np.isfinite(v_mat)) or np.any(v_mat < 0.0):
            raise MarsDiskError("v_rel matrix must be finite and non-negative")
        use_matrix_velocity = True
        v_scalar = 0.0

    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    kernel: np.ndarray | None = None
    if use_jit:
        try:
            kernel = collision_kernel_numba(
                N_arr, s_arr, H_arr, float(v_scalar), v_mat, bool(use_matrix_velocity)
            )
        except Exception as exc:  # pragma: no cover - fallback path
            _NUMBA_FAILED = True
            kernel = None
            warnings.warn(
                f"compute_collision_kernel_C1: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )

    if kernel is None:
        if workspace is not None:
            v_mat_full = workspace.v_mat_full
            if not use_matrix_velocity:
                v_mat_full.fill(float(v_scalar))
            else:
                v_mat_full[:] = v_mat
            N_outer = workspace.N_outer
            np.multiply(N_arr[:, None], N_arr[None, :], out=N_outer)
            s_sum_sq = workspace_s_sum_sq
            delta = workspace_delta
            H_sq = workspace.H_sq
            H2 = H_arr * H_arr
            np.add(H2[:, None], H2[None, :], out=H_sq)
            H_ij = workspace.H_ij
            np.sqrt(H_sq, out=H_ij)
            kernel = workspace.kernel
            kernel[:] = N_outer / (1.0 + delta)
            kernel *= np.pi
            kernel *= s_sum_sq
            kernel *= v_mat_full
            kernel /= (np.sqrt(2.0 * np.pi) * H_ij)
        else:
            v_mat_full = (
                np.full((n, n), float(v_scalar), dtype=np.float64)
                if not use_matrix_velocity
                else v_mat
            )
            N_outer = np.outer(N_arr, N_arr)
            s_sum_sq = np.add.outer(s_arr, s_arr) ** 2
            delta = np.eye(n)
            H_sq = np.add.outer(H_arr * H_arr, H_arr * H_arr)
            H_ij = np.sqrt(H_sq)
            kernel = (
                N_outer / (1.0 + delta)
                * np.pi
                * s_sum_sq
                * v_mat_full
                / (np.sqrt(2.0 * np.pi) * H_ij)
            )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_collision_kernel_C1: n_bins=%d use_numba=%s", n, use_jit)
    return kernel


def compute_prod_subblow_area_rate_C2(
    C: np.ndarray, m_subblow: np.ndarray
) -> float:
    """Return the production rate of sub-blowout material.

    The rate is defined as ``sum_{i<=j} C_ij * m_subblow_ij``.

    Parameters
    ----------
    C:
        Collision kernel matrix with shape ``(n, n)``.
    m_subblow:
        Matrix of sub-blowout mass generated per collision pair.

    Returns
    -------
    float
        Production rate of sub-blowout mass.
    """

    global _NUMBA_FAILED
    if C.shape != m_subblow.shape:
        raise MarsDiskError("shape mismatch between C and m_subblow")
    if C.ndim != 2 or C.shape[0] != C.shape[1]:
        raise MarsDiskError("C must be a square matrix")
    n = C.shape[0]
    use_jit = _USE_NUMBA and not _NUMBA_FAILED
    if use_jit:
        try:
            rate = float(compute_prod_subblow_area_rate_C2_numba(np.asarray(C, dtype=np.float64), np.asarray(m_subblow, dtype=np.float64)))
        except Exception:  # pragma: no cover - exercised by fallback
            use_jit = False
            _NUMBA_FAILED = True
            warnings.warn("compute_prod_subblow_area_rate_C2: numba kernel failed; falling back to NumPy.", NumericalWarning)
    if not use_jit:
        idx = np.triu_indices(n)
        rate = float(np.sum(C[idx] * m_subblow[idx]))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_prod_subblow_area_rate_C2: rate=%e", rate)
    return rate
\end{Verbatim}

### B.4 Smoluchowski の IMEX-BDF(1) 更新（C3–C4）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/smol.py

def step_imex_bdf1_C3(
    N: Iterable[float],
    C: np.ndarray,
    Y: np.ndarray,
    S: Iterable[float] | None,
    m: Iterable[float],
    prod_subblow_mass_rate: float | None,
    dt: float,
    *,
    source_k: Iterable[float] | None = None,
    S_external_k: Iterable[float] | None = None,
    S_sublimation_k: Iterable[float] | None = None,
    extra_mass_loss_rate: float = 0.0,
    mass_tol: float = 5e-3,
    safety: float = 0.1,
    diag_out: MutableMapping[str, float] | None = None,
    workspace: ImexWorkspace | None = None,
) -> tuple[np.ndarray, float, float]:
    """Advance the Smoluchowski system by one time step.

    The integration employs an IMEX-BDF(1) scheme: loss terms are treated
    implicitly while the gain terms and sink ``S`` are explicit.  In the
    sublimation-only configuration used by :func:`marsdisk.run.run_zero_d`,
    this reduces to a pure sink update with ``C=0``, ``Y=0`` and non-zero
    ``S_sublimation_k``.

    Parameters
    ----------
    N:
        Array of number surface densities for each size bin.
    C:
        Collision kernel matrix ``C_{ij}``.
    Y:
        Fragment distribution where ``Y[k, i, j]`` is the fraction of mass
        from a collision ``(i, j)`` placed into bin ``k``.
    S:
        Explicit sink term ``S_k`` for each bin.  ``None`` disables the
        legacy sink input.
    S_external_k:
        Optional additional sink term combined with ``S`` (1/s).
    S_sublimation_k:
        Optional sublimation sink (1/s) summed with ``S``.  This is the
        preferred entrypoint for the pure-sink mode.
    m:
        Particle mass associated with each bin.
    prod_subblow_mass_rate:
        Nominal mass source rate (kg/m^2/s) associated with external supply.
        When ``source_k`` is provided the per-bin source is mapped back to a
        mass rate via ``sum(m_k * source_k)`` for the mass budget check.  A
        ``None`` value defers entirely to that computed rate.
    source_k:
        Optional explicit source vector ``F_k`` (1/s) that injects particles
        into the Smol system.  A zero vector preserves the legacy behaviour.
    extra_mass_loss_rate:
        Additional mass flux leaving the system (kg m^-2 s^-1) that should be
        included in the mass budget check (e.g. sublimation sinks handled
        outside the explicit ``S`` vector).  This feeds directly into
        :func:`compute_mass_budget_error_C4`.
    dt:
        Initial time step.
    mass_tol:
        Tolerance on the relative mass conservation error.
    safety:
        Safety factor controlling the maximum allowed step size relative to
        the minimum collision time.
    diag_out:
        Optional dictionary populated with diagnostic mass rates (gain, loss,
        sink, source) after the step is accepted.
    workspace:
        Optional reusable buffers for ``gain`` and ``loss`` vectors to reduce
        allocations when calling the solver repeatedly.

    Returns
    -------
    tuple of ``(N_new, dt_eff, mass_error)``
        Updated number densities, the actual time step used and the relative
        mass conservation error as defined in (C4).
    """

    global _NUMBA_FAILED
    N_arr = np.asarray(N, dtype=float)
    S_base = np.zeros_like(N_arr) if S is None else np.asarray(S, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if N_arr.ndim != 1 or S_base.ndim != 1 or m_arr.ndim != 1:
        raise MarsDiskError("N, S and m must be one-dimensional")
    if not (len(N_arr) == len(S_base) == len(m_arr)):
        raise MarsDiskError("array lengths must match")
    if C.shape != (N_arr.size, N_arr.size):
        raise MarsDiskError("C has incompatible shape")
    if Y.shape != (N_arr.size, N_arr.size, N_arr.size):
        raise MarsDiskError("Y has incompatible shape")
    if dt <= 0.0:
        raise MarsDiskError("dt must be positive")

    def _optional_sink(arr: Iterable[float] | None, name: str) -> np.ndarray:
        if arr is None:
            return np.zeros_like(N_arr)
        arr_np = np.asarray(arr, dtype=float)
        if arr_np.shape != N_arr.shape:
            raise MarsDiskError(f"{name} has incompatible shape")
        return arr_np

    source_arr = _optional_sink(source_k, "source_k")
    S_external_arr = _optional_sink(S_external_k, "S_external_k")
    S_sub_arr = _optional_sink(S_sublimation_k, "S_sublimation_k")
    S_arr = S_base + S_external_arr + S_sub_arr

    gain_out = None
    loss_out = None
    if workspace is not None:
        gain_buf = getattr(workspace, "gain", None)
        loss_buf = getattr(workspace, "loss", None)
        if isinstance(gain_buf, np.ndarray) and gain_buf.shape == N_arr.shape:
            gain_out = gain_buf
        if isinstance(loss_buf, np.ndarray) and loss_buf.shape == N_arr.shape:
            loss_out = loss_buf

    try_use_numba = _USE_NUMBA and not _NUMBA_FAILED
    if try_use_numba:
        try:
            loss = loss_sum_numba(np.asarray(C, dtype=np.float64))
        except Exception as exc:  # pragma: no cover - fallback
            try_use_numba = False
            _NUMBA_FAILED = True
            warnings.warn(f"loss_sum_numba failed ({exc!r}); falling back to NumPy.", NumericalWarning)
    if not try_use_numba:
        if loss_out is not None:
            np.sum(C, axis=1, out=loss_out)
            loss = loss_out
        else:
            loss = np.sum(C, axis=1)
    # C_ij already halves the diagonal, so add it back for the loss coefficient.
    if C.size:
        loss = loss + np.diagonal(C)
    # Convert summed collision rate (includes N_i) to the loss coefficient.
    safe_N = np.where(N_arr > 0.0, N_arr, 1.0)
    loss = np.where(N_arr > 0.0, loss / safe_N, 0.0)
    t_coll = 1.0 / np.maximum(loss, 1e-30)
    dt_max = safety * float(np.min(t_coll))
    dt_eff = min(float(dt), dt_max)

    source_mass_rate = float(np.sum(m_arr * source_arr))
    if prod_subblow_mass_rate is None:
        prod_mass_rate_budget = source_mass_rate
    else:
        prod_mass_rate_budget = float(prod_subblow_mass_rate)

    gain = _gain_tensor(C, Y, m_arr, out=gain_out, workspace=workspace)

    while True:
        N_new = (N_arr + dt_eff * (gain + source_arr - S_arr * N_arr)) / (1.0 + dt_eff * loss)
        if np.any(N_new < 0.0):
            dt_eff *= 0.5
            continue
        mass_err = compute_mass_budget_error_C4(
            N_arr,
            N_new,
            m_arr,
            prod_mass_rate_budget,
            dt_eff,
            extra_mass_loss_rate=float(extra_mass_loss_rate),
        )
        if not np.isfinite(mass_err):
            raise MarsDiskError("mass budget error is non-finite; check PSD or kernel inputs")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("step_imex_bdf1_C3: dt=%e mass_err=%e", dt_eff, mass_err)
        if mass_err <= mass_tol:
            break
        dt_eff *= 0.5

    if diag_out is not None:
        diag_out["gain_mass_rate"] = float(np.sum(m_arr * gain))
        diag_out["loss_mass_rate"] = float(np.sum(m_arr * loss * N_new))
        diag_out["sink_mass_rate"] = float(np.sum(m_arr * S_arr * N_arr))
        diag_out["source_mass_rate"] = float(np.sum(m_arr * source_arr))

    return N_new, dt_eff, mass_err


def compute_mass_budget_error_C4(
    N_old: Iterable[float],
    N_new: Iterable[float],
    m: Iterable[float],
    prod_subblow_mass_rate: float,
    dt: float,
    *,
    extra_mass_loss_rate: float = 0.0,
) -> float:
    """Return the relative mass budget error according to (C4).

    The budget compares the initial mass to the combination of retained mass
    and explicit source/sink fluxes:

    ``M_old + dt * prod_subblow_mass_rate = M_new + dt * extra_mass_loss_rate``.
    """

    global _NUMBA_FAILED
    N_old_arr = np.asarray(N_old, dtype=float)
    N_new_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if not (N_old_arr.shape == N_new_arr.shape == m_arr.shape):
        raise MarsDiskError("array shapes must match")

    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            err = float(
                mass_budget_error_numba(
                    m_arr * 0.0 + N_old_arr,  # ensure contiguous copies
                    m_arr * 0.0 + N_new_arr,
                    m_arr,
                    float(prod_subblow_mass_rate),
                    float(dt),
                    float(extra_mass_loss_rate),
                )
            )
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"compute_mass_budget_error_C4: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
            err = None
    else:
        err = None

    if err is None:
        M_before = float(np.sum(m_arr * N_old_arr))
        M_after = float(np.sum(m_arr * N_new_arr))
        prod_term = dt * float(prod_subblow_mass_rate)
        sink_term = dt * float(extra_mass_loss_rate)
        if M_before > 0.0:
            err = abs((M_after + sink_term) - (M_before + prod_term)) / M_before
        else:
            err = float("inf")
    return float(err)
\end{Verbatim}

### B.5 表層密度の更新と流出（S1）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/surface.py

def step_surface_density_S1(
    sigma_surf: float,
    prod_subblow_area_rate: float,
    dt: float,
    Omega: float,
    *,
    t_blow: float | None = None,
    t_coll: float | None = None,
    t_sink: float | None = None,
    sigma_tau1: float | None = None,
    enable_blowout: bool = True,
) -> SurfaceStepResult:
    """Advance the surface density by one implicit Euler step (S1).

    Parameters
    ----------
    sigma_surf:
        Current surface mass density ``Σ_surf``.
        prod_subblow_area_rate:
        Production rate of sub--blow-out material per unit area after mixing.
    dt:
        Time step.
    Omega:
        Keplerian angular frequency; sets ``t_blow = 1/Ω``.
    t_blow:
        Optional blow-out time-scale. When provided this overrides ``1/Ω``.
    t_coll:
        Optional collisional time-scale ``t_coll``.  When provided the
        loss term ``Σ_surf/t_coll`` is treated implicitly.
    t_sink:
        Optional additional sink time-scale representing sublimation or
        gas drag.  ``None`` disables the term.
    sigma_tau1:
        Diagnostic Σ_{τ=1} value passed through for logging; no clipping
        is applied in the surface ODE.
    enable_blowout:
        Toggle for the radiation-pressure loss term.  Disable to remove the
        ``1/t_blow`` contribution and force the returned outflux to zero.

    Returns
    -------
    SurfaceStepResult
        dataclass holding the updated density and associated fluxes.
    """

    global _SURFACE_ODE_WARNED
    if not _SURFACE_ODE_WARNED:
        warnings.warn(SURFACE_ODE_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        _SURFACE_ODE_WARNED = True

    if dt <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("dt and Omega must be positive")

    if t_blow is None:
        t_blow = 1.0 / Omega
    elif t_blow <= 0.0 or not np.isfinite(t_blow):
        raise MarsDiskError("t_blow must be positive and finite")
    loss = 0.0
    if enable_blowout:
        loss += 1.0 / t_blow
    if t_coll is not None and t_coll > 0.0:
        loss += 1.0 / t_coll
    if t_sink is not None and t_sink > 0.0:
        loss += 1.0 / t_sink

    numerator = sigma_surf + dt * prod_subblow_area_rate
    sigma_new = numerator / (1.0 + dt * loss)

    outflux = sigma_new / t_blow if enable_blowout else 0.0
    sink_flux = sigma_new / t_sink if (t_sink is not None and t_sink > 0.0) else 0.0
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "step_surface_density_S1: dt=%e sigma=%e sigma_tau1=%e t_blow=%e t_coll=%e t_sink=%e outflux=%e blowout=%s",
            dt,
            sigma_new,
            sigma_tau1 if sigma_tau1 is not None else float("nan"),
            t_blow,
            t_coll if t_coll is not None else float("nan"),
            t_sink if t_sink is not None else float("nan"),
            outflux,
            enable_blowout,
        )
    return SurfaceStepResult(sigma_new, outflux, sink_flux)
\end{Verbatim}
