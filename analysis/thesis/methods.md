<!-- TEX_EXCLUDE_START -->
> **文書種別**: 手法（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# シミュレーション手法

本章では，ロッシュ限界内の高密度ダスト円盤を対象に，放射圧によるブローアウトと衝突カスケードを結合した 1D（リング分割）モデルを定義し，本研究で用いた初期条件・数値解法・停止条件・出力・検証基準をまとめる．

## 1. モデルの概要

本節では，計算の目的と入出力を明確にしたうえで，1D モデルで用いる状態変数（半径セルと粒径ビン）と主要診断量の意味を定義し，章全体の更新フローと参照関係を示す．具体的な支配方程式と物理過程は 2節，初期条件・パラメータは 3節，数値解法と停止条件は 4節，出力と検証基準は 5節で与える．

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
## 2. 支配方程式と物理モデル

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/io/tables.py, marsdisk/physics/psd.py, marsdisk/physics/sizes.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/initfields.py
-->

本節では，前節で定義した状態変数 $N_k$ および $\Sigma_{\rm surf}$ の時間発展を記述する支配方程式を与える．時間発展には，放射圧による除去（定式化は \citep{Burns1979_Icarus40_1} を基礎とする），遮蔽，表層への供給，衝突カスケード，およびその他の損失過程をまとめた追加シンク項を含める．以下の式は，粒径をビン $k$ に離散化した枠組みで評価される離散量として記述する．

軌道力学量は，各半径セルの中心半径 $r$（火星中心からの距離）で評価する．火星質量 $M_{\rm Mars}$ による点質量重力場を仮定し，粒子の軌道運動をケプラー運動で近似すると，ケプラー速度 $v_K(r)$，ケプラー角速度 $\Omega(r)$，および公転周期 $T_{\rm orb}(r)$ は式\ref{eq:vK_definition}–\ref{eq:torb_definition}で定義される．

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

放射圧と重力の比 $\beta(s)$ は式\ref{eq:beta_definition}で定義し，Planck 平均の $\langle Q_{\rm pr}\rangle$ は外部テーブルから与える（付録 C, 表\ref{tab:app_external_inputs}）\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．本研究では $\langle Q_{\rm pr}\rangle(s,T_M)$ を $(s,T_M)$ 格子上の双一次補間（$s$ と $T_M$ で線形補間）で評価し，テーブル範囲外では外挿を避けて端値を代表値として用いる．$\beta\ge0.5$ を非束縛条件とし，ブローアウト境界粒径 $s_{\rm blow}$ は $\beta(s_{\rm blow})=0.5$ の解として式\ref{eq:s_blow_definition}で与える\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．$\langle Q_{\rm pr}\rangle(s,T_M)$ を粒径依存のテーブル補間で与える場合，式\ref{eq:s_blow_definition}は $s_{\rm blow}$ に関する陰関数であるため，本研究では固定点反復により数値的に解く（$\langle Q_{\rm pr}\rangle$ を代表値で固定する場合は閉形式に帰着する）．ブローアウト滞在時間は式\ref{eq:t_blow_definition}とし\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}，$\chi_{\rm blow}$ は入力として与える（または \texttt{auto} により $\beta$ と $\langle Q_{\rm pr}\rangle$ から経験的に推定する）．

\begin{equation}
\label{eq:beta_definition}
\beta(s) = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}(s)\rangle}{4\,G\,M_{\rm Mars}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}(s_{\rm blow})\rangle}{2\,G\,M_{\rm Mars}\,c\,\rho}
\end{equation}

\begin{equation}
\label{eq:t_blow_definition}
t_{\rm blow}=\chi_{\rm blow}\Omega^{-1}
\end{equation}

$\chi_{\rm blow}$ はブローアウト滞在時間の係数であり，非束縛となった粒子が表層から除去されるまでの有効滞在時間を $\Omega^{-1}$ で規格化した量と解釈する．ブローアウトは公転位相や放出条件に依存し得るため，本研究では $\chi_{\rm blow}$ を order unity の不確かさを持つ入力パラメータとして扱い，極端な滞在時間を避けるため $0.5$–$2$ の範囲に制限する．\texttt{auto} を選ぶ場合は，$\beta$ と $\langle Q_{\rm pr}\rangle$ を $s=s_{\min,\rm eff}$ で評価した値から次の経験式で推定する（${\rm clip}_{[a,b]}(x)\equiv\min(\max(x,a),b)$）．

\begin{equation}
\label{eq:chi_blow_auto_definition}
\chi_{\rm blow}=
{\rm clip}_{[0.5,2.0]}\!\left[
{\rm clip}_{[0.1,\infty)}\!\left(\frac{1}{1+0.5\left(\beta/0.5-1\right)}\right)
\;{\rm clip}_{[0.5,1.5]}\!\left(\langle Q_{\rm pr}\rangle\right)
\right]
\end{equation}

表層流出は PSD に作用する一次シンクとして扱い，ブローアウト対象ビンでは $S_{{\rm blow},k}=1/t_{\rm blow}$ とする．ブローアウト対象は $\beta\ge0.5$ に対応する $s_k\le s_{\rm blow}$ のビンとする．表層からの面密度流出（局所フラックス）は式\ref{eq:surface_outflux}で与える\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}．

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

遮蔽係数 $\Phi(\tau_{\rm los})$ は，自己遮蔽により火星放射が表層へ到達しにくくなる効果を，視線方向光学的厚さ $\tau_{\rm los}$ の関数として表す無次元係数である（付録C，表\ref{tab:app_external_inputs}）．

遮蔽の効果は，表層の質量不透明度 $\kappa_{\rm surf}$（単位 $\mathrm{m^2\,kg^{-1}}$）を，有効不透明度 $\kappa_{\rm eff}$ に置き換えることで取り込む．本研究では $\kappa_{\rm eff}$ を $\Phi$ によりスケールする近似を採用し，火星方向の有効光学的厚さ $\tau_{\rm eff}$ を以下で定義する．

\begin{equation}
\label{eq:phi_definition}
\Phi=\Phi(\tau_{\rm los})
\end{equation}

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\rm eff} = \Phi\,\kappa_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:tau_eff_definition}
\tau_{\rm eff}\equiv f_{\rm los}\kappa_{\rm eff}\Sigma_{\rm surf}=\Phi(\tau_{\rm los})\,\tau_{\rm los}
\end{equation}

ここで $\Sigma_{\rm surf}$ は表層面密度（単位 $\mathrm{kg\,m^{-2}}$），$f_{\rm los}$ は視線方向に沿った幾何学補正因子である．式\ref{eq:tau_eff_definition} 右辺の等号は，$\tau_{\rm los}\equiv f_{\rm los}\kappa_{\rm surf}\Sigma_{\rm surf}$ を用いた関係式である．

$\kappa_{\rm eff}$ に基づき，光学的厚さが 1 となる参照面密度 $\Sigma_{\tau=1}$ を式\ref{eq:sigma_tau1_definition}で与える．$\kappa_{\rm eff}>0$ のとき $\Sigma_{\tau=1}$ は「$\tau\simeq1$ に対応する表層面密度」の目安であり，$\kappa_{\rm eff}\le0$ の場合は光学的に厚くならない極限として $\Sigma_{\tau=1}=\infty$ と置く．

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau=1} =
\begin{cases}
\kappa_{\rm eff}^{-1}, & \kappa_{\rm eff} > 0,\\
\infty, & \kappa_{\rm eff} \le 0
\end{cases}
\end{equation}

$\kappa_{\rm eff}$ と $\tau_{\rm eff}$ は，(i) 初期条件における光学的厚さの規格化，(ii) $\tau_{\rm stop}$ による適用範囲判定（停止判定）に用いる．

### 2.3 表層への質量供給

表層への供給率（面密度注入率）を $\dot{\Sigma}_{\rm in}(t,r)$ と定義する．ここで $r$ は半径セルの中心半径であり，$\dot{\Sigma}_{\rm in}$ は表層（$\Sigma_{\rm surf}$）へ単位面積・単位時間あたりに注入される質量を表す．供給過程は，表層と下層（あるいは外部リザーバ）との混合効率を表す無次元係数 $\epsilon_{\rm mix}$ と，基準供給率 $R_{\rm base}(t,r)$ を用いて式\ref{eq:prod_rate_definition}で与える．衝突カスケードのサイズ分布進化モデルでは，質量収支式に外部供給（source）を明示的に導入する定式化が用いられており，本節の $F_k$ はその意味でのソース項に相当する（例：\citealp{Wyatt2008,WyattClarkeBooth2011_CeMDA111_1}）．

本研究の基準ケースでは，$R_{\rm base}$ を「参照面密度の一定割合を 1 軌道あたり供給する」定常供給として式\ref{eq:R_base_definition}で定義する．このとき $R_{\rm base}$ 自体は初期時刻 $t_0$ の参照面密度 $\Sigma_{\tau_{\rm ref}}(t_0,r)$ と公転周期 $T_{\rm orb}(r)$ のみに依存し，時間 $t$ には陽に依存しない（ただし一般形として $R_{\rm base}(t,r)$ と記す）．

\begin{equation}
\label{eq:R_base_definition}
R_{\rm base}(t,r)=
\frac{\mu_{\rm sup}\,f_{\rm orb}}{\epsilon_{\rm mix}}
\frac{\Sigma_{\tau_{\rm ref}}(t_0,r)}{T_{\rm orb}(r)},
\qquad
\Sigma_{\tau_{\rm ref}}(t_0,r)=\frac{\tau_{\rm ref}}{f_{\rm los}\kappa_{\rm eff}(t_0,\tau_{\rm ref})}
\end{equation}

ここで $\mu_{\rm sup}$ は供給強度を定める無次元パラメータであり，$f_{\rm orb}$ は $\mu_{\rm sup}=1$ のときに「1 軌道あたりに供給される表層面密度」が参照面密度 $\Sigma_{\tau_{\rm ref}}$ に対して占める比率（無次元）である．$\tau_{\rm ref}$ は参照有効光学的厚さ（既定値 1）であり，$\Sigma_{\tau_{\rm ref}}$ は初期 PSD から評価した $\kappa_{\rm eff}$ に基づく参照面密度である．本研究では初期光学的厚さ $\tau_0$ を掃引して初期状態を変えるため，$\Sigma_{\tau_{\rm ref}}(t_0,r)$ を用いて供給率を規格化し，「同じ $\mu_{\rm sup}$ が同程度の供給量」を指すように定義する．なお，式\ref{eq:R_base_definition}に $\epsilon_{\rm mix}$ を含めたのは，式\ref{eq:prod_rate_definition}と合わせて $\dot{\Sigma}_{\rm in}$ が $\mu_{\rm sup}$ と $f_{\rm orb}$ により一意に決まり，$\epsilon_{\rm mix}$ の値に依存しない（$\dot{\Sigma}_{\rm in}=\mu_{\rm sup}f_{\rm orb}\Sigma_{\tau_{\rm ref}}/T_{\rm orb}$ に帰着する）ようにするためである．

供給率は式\ref{eq:supply_injection_definition}により PSD のソース項 $F_k$ として粒径ビン $k$ に注入する．ここで $F_k$ は「単位面積あたりの粒子数密度 $N_k$ の増加率」であり，質量保存条件 $\sum_k m_kF_k=\dot{\Sigma}_{\rm in}$ を満たすよう，無次元重み $w_k$ を $\sum_kw_k=1$ となるように正規化する．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\rm in}(t,r) = \max\!\left(\epsilon_{\rm mix}R_{\rm base}(t,r),\,0\right)
\end{equation}

\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},
\qquad
\sum_k w_k=1,
\qquad
\sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}

供給される表層物質の粒径分布は，下層からの混合が初期表層と同程度の組成・粒径分布を持つという近似の下で，初期 PSD の質量分率に比例すると仮定する．具体的には $w_k\propto m_kN_k(t_0,r)$ と置き，$\sum_kw_k=1$ となるように正規化して用いる．この仮定により，供給は分布形状を直接には変えず，規格化（全量）を更新する操作として実装される．

### 2.4 衝突カスケード

PSD の時間発展は Smoluchowski 方程式（式\ref{eq:smoluchowski}）で与え，注入 $F_k$ と一次シンク $S_k$（ブローアウト・昇華）を含める\citep{Krivov2006_AA455_509,Thebault2003_AA408_775,Wyatt2008}．破片生成テンソル $Y_{kij}$ は質量保存条件 $\sum_k Y_{kij}=1$ を満たすよう定義する．

\begin{equation}
\label{eq:smoluchowski}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

\begin{equation}
\label{eq:fragment_yield_normalization}
\sum_k Y_{kij}=1
\end{equation}

衝突イベント率 $C_{ij}$ は式\ref{eq:collision_kernel}で与える\citep{Krivov2006_AA455_509}．スケールハイトは小傾斜近似の $z\sim ir$ に基づき $H_k=H_{\rm factor}\,i\,r$ とし，$H_{\rm factor}$ は分布形状や定義差を吸収する order unity の幾何因子として扱う（基準値は表\ref{tab:method-param}）．

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

本研究の基準値 $e_0=0.5$ は厳密な「低離心率」域を超えるが，衝突速度の代表スケールを与える簡略式として式\ref{eq:vrel_pericenter_definition}を用い，$e,i$ を時間一定・サイズ非依存とする近似の影響は感度として評価する．

ビンの衝突寿命は式\ref{eq:t_coll_definition}とし，時間刻みの上限に用いる\citep{Wyatt2008,StrubbeChiang2006_ApJ648_652}．

\begin{equation}
\label{eq:t_coll_definition}
t_{{\rm coll},k}=\left(\frac{\sum_j C_{kj}+C_{kk}}{N_k}\right)^{-1}
\end{equation}

破壊閾値 $Q_D^*$ は式\ref{eq:qdstar_definition}で与える\citep{BenzAsphaug1999_Icarus142_5,LeinhardtStewart2012_ApJ745_79,StewartLeinhardt2009_ApJ691_L133}．係数 $Q_s,B$ は BA99 の cgs 系（$s$ は cm，$\rho$ は g\,cm$^{-3}$，$Q_D^*$ は erg\,g$^{-1}$）で与えられるため，本研究では $s$ と $\rho$ を cgs へ変換して評価したのち $1\,{\rm erg\,g^{-1}}=10^{-4}\,{\rm J\,kg^{-1}}$ により SI へ換算する．

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

を用いる．速度依存は参照速度 $v_{\rm ref}$ の表（3.3節）に基づき，$v_{ij}$ が表の範囲内では隣接する 2 点の $v_{\rm ref}$ で評価した $Q_D^*$ を線形補間し，範囲外では最近接の係数を採用したうえで重力項のみ $v^{-3\mu_{\rm LS}+2}$ のべきでスケールする（$\mu_{\rm LS}=0.45$）\citep{StewartLeinhardt2009_ApJ691_L133}．これは参照表の範囲外に対する外挿仮定である．

衝突の比エネルギーは reduced specific kinetic energy $Q_R$ を用い，

\begin{equation}
\label{eq:q_r_definition}
Q_R=\frac{1}{2}\frac{\mu_{ij}v_{ij}^{2}}{m_i+m_j},\qquad \mu_{ij}=\frac{m_i m_j}{m_i+m_j}
\end{equation}

と定義する．最大残存率 $F_{LF}$ は $\phi\equiv Q_R/Q_D^*$ の関数として，Leinhardt \& Stewart (2012) の近似を採用する\citep{LeinhardtStewart2012_ApJ745_79}．

\begin{equation}
\label{eq:F_LF_definition}
F_{LF}(\phi)=
\begin{cases}
1-\frac12\phi, & \phi<\phi_{\rm tr},\\
0.1\left(\dfrac{\phi}{\phi_{\rm tr}}\right)^{-1.5}, & \phi\ge\phi_{\rm tr},
\end{cases}
\qquad \phi_{\rm tr}=1.8
\end{equation}

最大残存体の粒径は $m_{\rm LR}=F_{LF}(m_i+m_j)$ に対応する $s_{\rm LR}=(3m_{\rm LR}/4\pi\rho)^{1/3}$ とし，$s_{\rm LR}$ を含むビンを $k_{\rm LR}$ として割り当てる（$s_{\rm LR}$ が粒径グリッド範囲外に出た場合は，本研究の解像範囲の境界に代表させる）．

最大残存率 $F_{LF}$ と破片分布 $w^{\rm frag}_k$ を通じて式\ref{eq:fragment_tensor_definition}で $Y_{kij}$ を構成する\citep{StewartLeinhardt2009_ApJ691_L133,Thebault2003_AA408_775}．

\begin{equation}
\label{eq:fragment_weights}
w^{\rm frag}_k(k_{\rm LR})=\frac{\int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\rm frag}}\,ds}{\sum_{\ell\le k_{\rm LR}}\int_{s_{\ell-}}^{s_{\ell+}} s^{-\alpha_{\rm frag}}\,ds}
\end{equation}

\begin{equation}
\label{eq:fragment_tensor_definition}
Y_{kij}=F_{LF}\delta_{k k_{\rm LR}}+(1-F_{LF})\,w^{\rm frag}_k(k_{\rm LR})
\end{equation}

### 2.5 昇華と追加シンク

昇華は HKL フラックス $J(T)$ を用い\citep{VanLieshoutMinDominik2014_AA572_A76}，粒径縮小を式\ref{eq:dsdt_definition}で与える．昇華で用いる粒子温度は灰色体近似で式\ref{eq:grain_temperature_definition}とし\citep{BohrenHuffman1983_Wiley}，飽和蒸気圧は Clausius 形を用いる（式\ref{eq:psat_definition}）\citep{Kubaschewski1974_Book,VisscherFegley2013_ApJL767_L12}．基準ケースの係数は付録 Aに示す．

\begin{equation}
\label{eq:grain_temperature_definition}
T_p = T_M\,\langle Q_{\rm abs}\rangle^{1/4}\sqrt{\frac{R_{\rm Mars}}{2r}}
\end{equation}

灰色体近似として，本研究の基準ケースでは $\langle Q_{\rm abs}\rangle=1$ を既定値とする（材料依存の放射率を考慮する場合は一定値として与える）．

\begin{equation}
\label{eq:hkl_flux}
J(T) =
 \alpha_{\rm evap}\max\!\bigl(P_{\rm sat}(T) - P_{\rm gas},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\rm sat}(T)=10^{A - B/T}
\end{equation}

本研究では材料の相（固相／液相）により $P_{\rm sat}(T)$ のフィット係数 $A,B$ を切り替えて用いる．相境界近傍で温度が往復する場合に，微小な変動で相が頻繁に切り替わることを避けるため，相判定にはヒステリシスを導入し，切替温度とヒステリシス幅は付録 Aに示す採用値で与える．これは相変化の微視的過程を解かない代わりに，固相・液相の寄与を有効パラメータで表現する近似である．

このとき粒径の時間変化は，HKL フラックスと質量保存から $ds/dt=-J(T)/\rho$ と書ける\citep{VanLieshoutMinDominik2014_AA572_A76}．

\begin{equation}
\label{eq:dsdt_definition}
\frac{ds}{dt}=-\frac{J(T)}{\rho}
\end{equation}

昇華によるサイズ減少速度 $ds/dt$ を各ビンの有効寿命 $t_{{\rm sub},k}=s_k/|ds/dt|$ に写像し，一次シンクとして Smol 方程式に組み込む．すなわち $ds/dt<0$ のとき，

\begin{equation}
\label{eq:sublimation_sink_definition}
S_{{\rm sub},k}=\frac{1}{t_{{\rm sub},k}}=\frac{|ds/dt|}{s_k}
\end{equation}

とし，式\ref{eq:smoluchowski}の $S_k$ に加算する．

以上の定式化により，半径セルごとの PSD と表層面密度を，放射圧流出（ブローアウト）・遮蔽・供給・衝突カスケード・追加シンクの寄与で更新できる．次節では，初期条件・境界条件と，本論文で用いる基準パラメータをまとめる．
## 3. 初期条件・境界条件・パラメータ

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/physics/sizes.py, marsdisk/physics/psd.py, marsdisk/physics/qstar.py, marsdisk/io/tables.py
-->

本節では，1D 計算における初期条件・サイズ境界・停止条件に関わるパラメータを整理し，基準計算で採用した値を表としてまとめる．

本節は，2節で導入した支配方程式に対して，計算領域・初期状態・採用パラメータを与え，実行条件を具体化するための整理である．特に，(i) 環状領域とセル分割，(ii) 初期 PSD の形状と $\tau_0$ による表層規格化，(iii) 力学・供給・衝突パラメータの基準値，を固定し，以降の数値解法（4節）と出力・検証（5節）で共通に参照する．基準計算の採用値は表\ref{tab:method-param}，表\ref{tab:methods_initial_psd_params}，表\ref{tab:methods_qdstar_coeffs}にまとめ，感度掃引で動かす代表パラメータは付録 A（表\ref{tab:app_methods_sweep_defaults}）に整理する．

### 3.1 初期条件と境界条件

初期条件は，時刻 $t=t_0$ における粒径ビン $k$ の PSD（particle size distribution）$N_k(t_0)$ と，環状領域 $[r_{\rm in},r_{\rm out}]$ の幾何学的条件（$r_{\rm in},r_{\rm out}$ など）および温度条件（粒子温度・火星温度などの入力）によって与える．火星放射に直接さらされる表層については，火星方向の有効光学的厚さ $\tau_{\rm eff}(t_0,r)$ が規格化値 $\tau_0$ となるように，初期表層面密度 $\Sigma_{\rm surf}(t_0,r)$ を各半径セル内で一様に定める（$\tau_{\rm eff}$ の定義は式\ref{eq:tau_eff_definition}）．

本研究では $\tau_{\rm eff}=f_{\rm los}\kappa_{\rm eff}\Sigma_{\rm surf}$ とおく．ここで $f_{\rm los}$ は火星方向の経路長を鉛直方向の近似へ写像する幾何因子であり（式\ref{eq:tau_los_definition}），$\kappa_{\rm eff}$ は表層の質量不透明度 $\kappa_{\rm surf}$ を遮蔽係数 $\Phi$ で補正した有効量として $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ と定義する（2.2節）．したがって，$\tau_0$ を与えると，初期 PSD に基づいて評価される $\kappa_{\rm surf}(t_0)$ と，同一条件下で評価した $\Phi$ を通じて $\kappa_{\rm eff}(t_0,\tau_0)$ が定まり，$\Sigma_{\rm surf}(t_0,r)$ は次式で決定される．

\begin{equation}
\label{eq:sigma_surf0_from_tau0}
\Sigma_{\rm surf}(t_0,r)=\frac{\tau_0}{f_{\rm los}\kappa_{\rm eff}(t_0,\tau_0)}
\end{equation}

ここで $\kappa_{\rm eff}(t_0,\tau_0)$ は初期 PSD から評価した $\kappa_{\rm surf}(t_0)$ と遮蔽係数 $\Phi$ により与えられる初期有効不透明度である（2.2節）．なお，$\Phi$ が $\tau_{\rm eff}$（ひいては $\Sigma_{\rm surf}$）に依存する実装の場合，$\kappa_{\rm eff}(t_0,\tau_0)$ は「$\tau_{\rm eff}=\tau_0$ を満たす状態」で自己無撞着に評価した値を意味する．

基準計算では，巨大衝突直後の円盤物質に想定される「メートル級の溶融滴」成分と「サブミクロン級の微粒子」成分を簡便に表現するため，2成分の対数正規分布混合（lognormal mixture）を初期 PSD の質量分布形状として仮定する．採用値は表\ref{tab:methods_initial_psd_params}に示す．粒径（半径）を $s$ とし，初期 PSD の質量分布形状 $w_{\rm melt}(s)$ を

\begin{equation}
\label{eq:initial_psd_lognormal_mixture}
w_{\rm melt}(s)\propto
(1-f_{\rm fine})\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm meter})}{\sigma_{\ln}}\right)^2\right]
+f_{\rm fine}\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm fine})}{\sigma_{\ln}}\right)^2\right],
\qquad
\sigma_{\ln}={\rm width}_{\rm dex}\ln 10
\end{equation}

で与える．ここで $f_{\rm fine}$ は微粒子成分の（規格化前の）相対寄与を表す無次元係数であり，$s_{\rm meter}$ と $s_{\rm fine}$ はそれぞれ粗粒子・微粒子成分の代表粒径である．さらに，本研究では数値計算で追跡する最小粒径を $s_{\rm cut}$ として，$s<s_{\rm cut}$ を切断する（$w_{\rm melt}(s)=0$）．この切断は，凝縮微粒子の詳細な生成・成長過程を初期条件に直接は組み込まず，粒径下限を有限に保つためのモデル化である．\citep{Hyodo2017a_ApJ845_125}

離散化では，対数ビン $k$ の幅 $\Delta\ln s_k$ に対して $w_k\propto w_{\rm melt}(s_k)\Delta\ln s_k$ を構成し，$m_k N_k\propto w_k$ を満たすように $N_k(t_0)$ を定める．最後に，式\ref{eq:sigma_surf_definition}で定義した表層面密度 $\Sigma_{\rm surf}(t_0)$ と整合するよう，全ビンを同一係数で規格化する．

火星温度 $T_M(t)$ は外部ドライバとして与え，$\langle Q_{\rm pr}\rangle$ と $\Phi$ は外部入力として与える（付録 C，表\ref{tab:app_external_inputs}）．

サイズ境界は $s\in[s_{\min,\rm cfg},s_{\max}]$ とする．ただし，放射圧によって重力的に束縛されない領域に対応する $s_{\min,\rm eff}$ 未満の粒子は，生成されても力学的時間で系外へ除去されると近似し，PSD には保持しない（ブローアウトで即時除去）．\citep{Hyodo2018_ApJ860_150}

\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}

ここで $A$ は面密度と総質量の換算に用いる環状領域の面積である．本研究の 0D/1D（リング）近似では，環状領域（annulus）内を粒径ビンに分割して統計的に $N_k$ を扱う，いわゆる particle-in-a-box 型の取り扱いと整合させる．\citep{Wyatt2008,Thebault2003_AA408_775}

表\ref{tab:method-param}の $M_{\rm in}$ はロッシュ限界内側に存在する中層（深部）円盤の総質量を表す．一方，初期表層質量 $M_{\rm surf}(t_0)=\int 2\pi r\,\Sigma_{\rm surf}(t_0,r)\,dr$ は，式\ref{eq:sigma_surf0_from_tau0}で与えた $\tau_0$ と初期 PSD（$\kappa_{\rm eff}$）から派生する量として扱う．すなわち，$\tau_0$ を指定すると $\Sigma_{\rm surf}(t_0,r)$ が定まり，表層が各セル内で一様である近似の下では $M_{\rm surf}(t_0)\approx \Sigma_{\rm surf}(t_0)A$ が決まる．したがって $M_{\rm surf}(t_0)$ は $\tau_0$ と独立な自由度としては持たず，$M_{\rm in}$ は深部供給や中層面密度の基準として別途保持する．

### 3.2 物理定数・物性値

本研究で用いる主要な物理定数・惑星定数・粒子物性を表\ref{tab:method-phys}にまとめる．普遍定数（$G,c,\sigma_{\rm SB},R$）は CODATA 2018 の推奨値に従い，火星の質量 $M_{\rm Mars}$ と平均半径 $R_{\rm Mars}$ は公表値を採用する．材料依存パラメータは基準ケースではフォルステライト（$\mathrm{Mg_2SiO_4}$）を代表組成として近似し，密度 $\rho$ や飽和蒸気圧式の係数などは付録Aにまとめる．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\caption{物理定数・惑星定数・粒子物性（基準計算）}
\label{tab:method-phys}
\begin{tabular}{p{0.30\textwidth} p{0.22\textwidth} p{0.18\textwidth} p{0.22\textwidth}}
\hline
記号 & 値 & 単位 & 備考 \\
\hline
$G$ & $6.67430\times10^{-11}$ & $\mathrm{m^{3}\,kg^{-1}\,s^{-2}}$ & 万有引力定数 \\
$c$ & $2.99792458\times10^{8}$ & $\mathrm{m\,s^{-1}}$ & 光速（真空） \\
$\sigma_{\rm SB}$ & $5.670374419\times10^{-8}$ & $\mathrm{W\,m^{-2}\,K^{-4}}$ & ステファン・ボルツマン定数 \\
$M_{\rm Mars}$ & $6.4171\times10^{23}$ & $\mathrm{kg}$ & 火星質量 \\
$R_{\rm Mars}$ & $3.3895\times10^{6}$ & $\mathrm{m}$ & 火星平均半径 \\
$\rho$ & 3270 & $\mathrm{kg\,m^{-3}}$ & 粒子内部密度（フォルステライト） \\
$R$ & 8.314462618 & $\mathrm{J\,mol^{-1}\,K^{-1}}$ & 普遍気体定数（Hertz--Knudsen--Langmuir（HKL）式に使用） \\
\hline
\end{tabular}
\end{table}

<!-- TEX_EXCLUDE_START -->
（注）現行稿（提示文）では，表中の数値の「出典」が本文・表のいずれにも明示されていないため，修士論文としては追跡可能性の観点で不十分になりやすい．上の添削案では，普遍定数と惑星定数について最低限の出典を本文に集約して付し，材料依存値については付録Aに「値＋出典」をまとめる方針を明文化した．
<!-- TEX_EXCLUDE_END -->

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
	    $f_{\rm los}$ & 1.0 & -- & LOS 幾何因子（式\ref{eq:tau_los_definition}） \\
	    $\tau_0$ & 1.0 & -- & 初期 $\tau_{\rm eff}$ 規格化値（式\ref{eq:sigma_surf0_from_tau0}） \\
	    $\tau_{\rm stop}$ & 2.302585 & -- & 停止判定（$\ln 10$） \\
    $e_0$ & 0.5 & -- & 離心率 \\
    $i_0$ & 0.05 & -- & 傾斜角 \\
	    $H_{\rm factor}$ & 1.0 & -- & $H_k=H_{\rm factor} i r$ \\
	    $\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数 \\
	    $\mu_{\rm sup}$ & 1.0 & -- & 供給スケール（式\ref{eq:R_base_definition}） \\
	    $f_{\rm orb}$ & 0.05 & -- & $\mu_{\rm sup}=1$ のときの 1 軌道あたり供給比率 \\
		    $\tau_{\rm ref}$ & 1.0 & -- & 供給スケール参照有効光学的厚さ \\
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
## 4. 数値計算法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

本章では，支配方程式（式\ref{eq:method-smol}）を数値的に解くための「粒径分布の離散化」と「時間積分」をまとめる．特に，衝突破砕を含む Smoluchowski 型方程式は剛性を持ちやすく，単純な陽的積分では負の個数密度や質量収支の破綻が生じ得る．そこで本研究では，非負性（$N_k\ge 0$）を保ちつつ，質量収支が許容範囲に収まる解のみを採用するという方針で，時間刻み制御と停止条件を明示する．

### 4.1 離散化

**粒径空間の離散化**
サイズ空間 $s\in[s_{\min},\,s_{\max}]$ を対数等間隔グリッドで離散化する．有効下限 $s_{\min,\mathrm{eff}}$ は，設定値 $s_{\min}$ とブローアウト粒径 $a_{\mathrm{blow}}(t)$ の大きい方として定める（実装では $s_{\min,\mathrm{eff}}=\max(s_{\min},a_{\mathrm{blow}})$ を採用する）．上限は $s_{\max}$ とし，ビン数 $K=n_{\mathrm{bins}}$ を与える．

ビン境界を $s_{k\pm1/2}$，代表サイズを $s_k=\sqrt{s_{k-1/2}s_{k+1/2}}$ とする．状態量 $N_k$ はビン $k$ に含まれる粒子の面数密度（$\mathrm{m^{-2}}$）であり，各ビンの代表質量を $m_k=\frac{4}{3}\pi\rho s_k^3$ とすると，表層面密度は
\[
\Sigma(t)=\sum_{k=1}^{K} m_k N_k(t)
\]
で評価する．以後，注入（供給）・損失（ブローアウト／昇華）・破片再配分はビン上で評価する．

**粒径範囲外の取り扱い**
$s<s_{\min,\mathrm{eff}}$ の成分は本研究の解像範囲外とし，放射圧による除去等で速やかに失われる成分として明示的な損失項に含める．また，$s>s_{\max}$ の大粒子は未解像成分として直接は追跡せず，必要に応じて「上限側への質量漏れ」を診断量として集計する．

**半径方向の離散化**
半径方向は第1節で導入したセル分割に従い，各セル内では物理量を一様とみなす．粒径分布の更新はセルごとに行い，半径方向輸送（存在する場合）は別途のフラックス評価として組み込む（第2章で定義した輸送項に従う）．

### 4.2 数値解法と停止条件

**採用スキームの位置づけ**
既存研究では，collisional cascade の時間発展を一次の Euler 法と適応刻みで扱う例がある\citep{Thebault2003_AA408_775,Krivov2006_AA455_509}．一方で，Smoluchowski 型方程式の剛性に対しては陰的積分を用いることで大きな時間刻みを可能にすることが報告されている\citep{Krivov2006_AA455_509,Birnstiel2011_AA525_A11}．本研究ではこれらを踏まえ，衝突ロス項を陰的に扱い，生成・供給・一次シンクを陽的に扱う一次 IMEX（IMEX-BDF(1)）を用いる．

**IMEX-BDF(1) 更新式**
外側ステップ幅を $\Delta t$ とし，Smoluchowski 更新に実際に用いる内部ステップ幅を $dt_{\rm eff}\le\Delta t$ とする．ビン $k$ の更新は
\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}
で与える．ここで $G_k$ は衝突破砕による生成項，$F_k$ は外部供給（注入）項，$S_k$ はブローアウト・昇華等の一次シンク（$\mathrm{s^{-1}}$）である．$t_{{\rm coll},k}$ は衝突カーネルから評価したビン $k$ の衝突時間スケールであり，カーネル行列 $C_{kj}$ と $N_k$ から「単位粒子あたりの衝突ロス率」を構成し，その逆数として定義する（対角成分の扱いはカーネル定義に従う）．本スキームはロス項に起因する剛性を緩和しつつ，計算コストを抑えるために一次の時間精度を選択したものである．

**時間刻み制御（非負性・質量保存）**
内部ステップ幅 $dt_{\rm eff}$ は，最小衝突時間に対する安全率で上限を設けて初期化し，非負性と質量収支に基づいて半減調整する（実装では $dt_{\max}=0.1\min_k t_{{\rm coll},k}$ を用いる）．手順は次の通りである．

1. $dt_{\rm eff}\leftarrow\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を設定する．
2. 式\ref{eq:imex_bdf1_update}で $N_k^{n+1}$ を計算する．
3. $N_k^{n+1}<0$ を含む場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
4. 式\ref{eq:mass_budget_definition}で相対誤差 $\epsilon_{\rm mass}$ を評価し，$\epsilon_{\rm mass}>\epsilon_{\rm tol}$ の場合は $dt_{\rm eff}\leftarrow dt_{\rm eff}/2$ として 2 に戻る．
5. 条件 3–4 を満たした $dt_{\rm eff}$ を採用してステップを確定する．

ここで $\epsilon_{\rm tol}$ は質量保存誤差の許容値であり，本研究では $\epsilon_{\rm tol}=5\times10^{-3}$（0.5%）を用いる．なお，質量収支の検査は「実際に採用された $dt_{\rm eff}$」に対して行う．

**質量収支の定義**
質量保存の検査は次式で定義する．
\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
\Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
\Delta\Sigma &= \Sigma^{n+1} + dt_{\rm eff}\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + dt_{\rm eff}\,\dot{\Sigma}_{\rm in}\right),\\
\epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}
$\dot{\Sigma}_{\rm in}$ は明示的な供給項 $F_k$ が与える質量注入率であり，$\dot{\Sigma}_{\rm in}=\sum_k m_k F_k$ として評価する．$\dot{\Sigma}_{\rm extra}$ は表層から系外へ失われる明示的な損失（ブローアウト・昇華など）を質量率として合算したものである．

**積分終端**
積分終端 $t_{\rm end}$ は火星表面温度の時間発展と整合する解析対象期間として与える．本論文では，高温期の終端に対応する温度閾値 $T_{\rm end}=2000\,\mathrm{K}$ を定め，$T_M(t)=T_{\rm end}$ に到達する時刻を $t_{\rm end}$ として積分を終了する．

**光学的厚さに基づくセル停止**
本研究の放射圧評価は，「火星放射が表層へ到達する」ことを前提に組み立てている．したがって，表層が光学的に十分厚くなったセルについては，その後の時間発展を追ってもモデル仮定の下では意味が曖昧になる．そこで各セルについて，有効光学的厚さ $\tau_{\rm eff}$ が閾値 $\tau_{\rm stop}$ を超えた場合に，当該セルの進化計算を停止する．$\tau_{\rm stop}=\ln 10$ は透過率 $\exp(-\tau)$ が $0.1$ 以下となる目安に対応する．なお遮蔽が無効（$\Phi=1$）の場合には $\tau_{\rm eff}=\tau_{\rm los}$ に退化するため，遮蔽の有無にかかわらず同一の形式で停止判定を扱える．ここで重要なのは，この停止が円盤の物理的停止を意味するのではなく，あくまで「本モデルの適用範囲外に入った」ことを示すフラグとして用いる点である．

**（任意）ブローアウト粒径が解像下限を下回る場合**
温度低下により $a_{\rm blow}$ が解像下限 $s_{\min}$ を下回る場合，放射圧除去が解像範囲より小さい粒径で起きるため，モデルの解像上の前提が変化する．実装には，この条件を満たしたときに計算を停止するオプションがあり，一定の最短積分期間を経た後に停止する．本論文では，この条件の採否と採用時の解釈を結果章で明示する．

本節では，粒径分布の離散化，IMEX による時間積分，および非負性・質量収支に基づく刻み制御と停止条件を定義した．次節では，これらの設定の下で得られる進化計算の収束判定と結果の整理基準を述べる．
## 5. 出力と検証

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

本節では，計算結果を再解析可能な形で保存するための出力仕様と，本文で採用する計算の合格基準（検証）をまとめる．

### 5.1 出力と検証

本研究では，再解析可能性を担保するため，(i) 入力条件（設定・外部テーブル参照）と由来情報，(ii) 主要診断量の時系列，(iii) PSD 履歴，(iv) 終端集計，(v) 検証ログを，実行ごとに保存する（付録 A）．これらが揃えば，後段の図表生成は保存された出力を入力として再構成できる．

保存形式は JSON/Parquet/CSV であり，入力と採用値の記録（`run_config.json`），主要スカラー時系列（`series/run.parquet`），PSD 履歴（`series/psd_hist.parquet`），終端要約（`summary.json`），質量検査ログ（`checks/mass_budget.csv`）を最小セットとして保持する．補助的に，`series/diagnostics.parquet`（遮蔽などの追加診断；存在する場合）や `checks/mass_budget_cells.csv`（1D のセル別質量収支；設定により出力）を保存する．また，収束比較（時間刻み・粒径ビン）の判定結果は，別実行の比較から `checks/validation.json` として出力し，本文の合否判定に用いる．1D 計算では半径セルごとの時系列を保存するため，任意時刻の円盤全体量は半径積分（離散和）により再構成できる．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する\citep{Wyatt2008}．本論文では質量を火星質量 $M_{\rm Mars}$ で規格化して示し，$\dot{M}_{\rm out}$ と $M_{\rm loss}$ も同様の規格化量として扱う．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

検証は，質量保存，時間刻み収束，および粒径ビン収束（PSD ビン数）の 3 項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果はすべて基準を満たした計算に限定する．質量保存は式\ref{eq:mass_budget_definition}で定義する相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下であることを要求する．時間刻み収束と粒径ビン収束（PSD ビン数）に用いる相対差は $|X({\rm coarse})-X({\rm ref})|/|X({\rm ref})|$ と定義する．ref はより細かい離散化（時間刻みなら $\Delta t/2$，粒径ビンならビン数 2 倍）とする．

時間刻み収束は，$\Delta t$（coarse）と $\Delta t/2$（ref）の計算で，累積損失 $M_{\rm loss}$ の相対差が $1\%$ 以下となることにより確認する．$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で更新される累積量であり，離散化誤差が時間積分を通じて蓄積した影響を直接反映するため，収束判定の代表指標として採用する．

粒径ビン収束（PSD ビン数）は，基準の粒径ビン設定（coarse）と，粒径ビン幅を 1/2 とした設定（ref；ビン数を 2 倍にした PSD）の計算結果を比較し，時間刻み収束と同一の指標（$M_{\rm loss}$ の相対差）で $1\%$ 以下となることにより確認する．この比較により，粒径離散化に起因する系統誤差が本論文の結論に影響しない範囲であることを担保する．

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
    粒径ビン収束（PSD ビン数） & 基準ビンとビン数を 2 倍にした計算の $M_{\rm loss}$ の相対差が $1\%$ 以下 \\
    \hline
\end{tabular}
\end{table}

以上の出力仕様と検証基準により，結果の再現性（入力→出力の対応）と数値的健全性（質量保存と収束性：時間刻み・粒径ビン）を担保したうえで，本論文の結果・議論を構成する．
## 付録 A. 再現実行と保存情報

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, scripts/validate_run.py
-->

本研究の再現性は，(i) 入力（設定ファイルとテーブル）を固定し，(ii) 実行時に採用された値と条件を保存し，(iii) 時系列・要約・検証ログを保存することで担保する．本付録では，論文として最低限必要な「保存すべき情報」をまとめる．

### A.1 固定する入力（再現の前提）

- **設定**: 物理スイッチ，初期条件，時間刻み，停止条件，感度掃引の対象パラメータ．
- **外部テーブル**: $\langle Q_{\rm pr}\rangle$ や遮蔽係数 $\Phi$ などの外部入力（付録 C）．
- **乱数シード**: 乱数を用いる過程がある場合はシードを固定する．

外部入力（テーブル）の役割と本文中での参照先を付録 C（表\ref{tab:app_external_inputs}）にまとめる．実行時に採用したテーブルの出典と適用範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする．

### A.2 保存する出力（再解析の最小セット）

本論文で示す結果は，以下の情報を保存して再解析できる形で管理した．

- **採用値の記録**: $\rho$，$\langle Q_{\rm pr}\rangle$，物理スイッチ，$s_{\rm blow}$ など，実行時に採用した値と出典を機械可読形式で保存する．
- **時系列**: 主要スカラー量（$\tau_{\rm los}$，$\tau_{\rm eff}$，$s_{\rm blow}$，$\Sigma_{\rm surf}$，$\dot{M}_{\rm out}$ など）の時系列．
- **PSD 履歴**: $N_k(t)$ と $\Sigma_{\rm surf}(t)$ の履歴．
- **要約**: $t_{\rm end}$ までの累積損失 $M_{\rm loss}$ などの集約．
- **検証ログ**: 式\ref{eq:mass_budget_definition} に基づく質量検査のログ．

実際の成果物は実行ディレクトリ（`OUTDIR/`）配下に保存し，後段の解析はこれらを入力として再構成する．最小セットは次の 5 点である．

- `OUTDIR/run_config.json`（JSON）: 展開後の設定と採用値，実行環境（`python`/`platform`/`argv`/`cwd`/`timestamp_utc`），依存パッケージの版，および外部ファイル（テーブル等）のパスとハッシュ（可能な範囲）．
- `OUTDIR/series/run.parquet`（Parquet）: 主要スカラー時系列（例: `time`, `dt`, `tau`, `a_blow`, `s_min`, `Sigma_surf`, `outflux_surface`, `prod_subblow_area_rate`, `M_out_dot`, `M_loss_cum`）．
- `OUTDIR/series/psd_hist.parquet`（Parquet）: PSD 履歴（例: `time`, `bin_index`, `s_bin_center`, `N_bin`, `Sigma_bin`, `f_mass`, `Sigma_surf`）．
- `OUTDIR/summary.json`（JSON）: 終端要約（例: `M_loss`, `mass_budget_max_error_percent`）．
- `OUTDIR/checks/mass_budget.csv`（CSV）: 質量検査ログ（例: `time`, `mass_initial`, `mass_remaining`, `mass_lost`, `error_percent`, `tolerance_percent`）．

補助的に，`OUTDIR/series/diagnostics.parquet`（遮蔽などの追加診断；存在する場合）や `OUTDIR/checks/mass_budget_cells.csv`（1D のセル別質量収支；設定により出力）を保存する．また，時間刻み・粒径ビンの収束比較の合否判定は `scripts/validate_run.py` により `OUTDIR/checks/validation.json` として出力し，表\ref{tab:validation_criteria}の確認に用いる．

保存時は質量流出率と累積損失を火星質量 $M_{\rm Mars}$ で規格化した単位で記録し，数値桁を揃える．定義は付録 E（記号表）を参照する．

### A.3 感度掃引で用いる代表パラメータ（例）

\begin{table}[t]
  \centering
  \caption{感度掃引で用いる代表パラメータ（例）}
  \label{tab:app_methods_sweep_defaults}
  \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
    \hline
    変数 & 代表値 & 意味 \\
    \hline
    $T_M$ & 4000, 3000 & 火星温度 [K] \\
    $\epsilon_{\rm mix}$ & 1.0, 0.5 & 混合係数（供給の有効度） \\
	    $\tau_0$ & 1.0, 0.5 & 初期有効光学的厚さ（$\tau_{\rm eff}$ の規格化値） \\
    $i_0$ & 0.05, 0.10 & 初期傾斜角 \\
    $f_{Q^*}$ & 0.3, 1, 3（$\times$基準値） & $Q_D^*$ の係数スケール（proxy の不確かさの感度） \\
    \hline
  \end{tabular}
\end{table}

### A.4 検証結果の提示（代表ケース）

本論文では，表\ref{tab:validation_criteria}の合格基準に基づく検証を全ケースで実施し，合格した結果のみを採用する．代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列例を図\ref{fig:app_validation_mass_budget_example}に示す．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/thesis/validation_mass_budget_example.pdf}
  \caption{代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列（例）}
  \label{fig:app_validation_mass_budget_example}
\end{figure}

### A.5 基準ケースで用いる物性値

本研究の基準ケースで採用する物性値（フォルステライト基準）を表\ref{tab:run_sweep_material_properties}にまとめる．密度・放射圧効率・昇華係数はフォルステライト値を採用し，$Q_D^*$ は peridot projectile 実験の $Q^*$ を参照して BA99 係数をスケーリングした proxy を用いる．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{基準ケースで用いる物性値（フォルステライト基準）}
  \label{tab:run_sweep_material_properties}
  \begin{tabular}{L{0.16\textwidth} L{0.34\textwidth} L{0.26\textwidth} L{0.16\textwidth}}
    \hline
    記号 & 意味 & 値 & 出典 \\
    \hline
	    $\rho$ &
	    粒子密度 [kg\,m$^{-3}$] &
	    3270 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $\langle Q_{\rm pr}\rangle$ &
    Planck 平均放射圧効率（テーブル） &
    フォルステライト（Mie テーブル） &
    \citep{BohrenHuffman1983_Wiley,Zeidler2015_ApJ798_125} \\
	    $\alpha$ &
	    HKL 蒸発係数 &
	    0.1 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $\mu$ &
	    分子量 [kg\,mol$^{-1}$] &
	    0.140694 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $A_{\rm solid}$ &
	    固相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm solid}-B_{\rm solid}/T$ &
	    13.809441833 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $B_{\rm solid}$ &
	    同上（$T$ は K） &
	    28362.904024 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
	    $T_{\rm solid}^{\rm valid}$ &
	    固相フィットの適用温度範囲 [K] &
	    1673--2133 &
	    \citep{VanLieshoutMinDominik2014_AA572_A76} \\
    $A_{\rm liq}$ &
    液相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm liq}-B_{\rm liq}/T$ &
    11.08 &
    \citep{FegleySchaefer2012_arXiv} \\
    $B_{\rm liq}$ &
    同上（$T$ は K） &
    22409.0 &
    \citep{FegleySchaefer2012_arXiv} \\
    $T_{\rm liq}^{\rm valid}$ &
    液相フィットの適用温度範囲 [K] &
    2163--3690 &
    \citep{FegleySchaefer2012_arXiv} \\
    $T_{\rm switch}$ &
    固相$\to$液相フィット切替温度 [K] &
    2163 &
    \citep{FegleySchaefer2012_arXiv} \\
	    $T_{\rm condense}$, $T_{\rm vaporize}$ &
	    相判定のヒステリシス閾値 [K]（相境界の切替幅） &
	    2162, 2163 &
	    本研究（スキーマ要件），基準: \citep{FegleySchaefer2012_arXiv} \\
    $f_{Q^*}$ &
    $Q_D^*$ 係数スケール（peridot proxy） &
    5.574 &
    \citep{Avdellidou2016_MNRAS464_734,BenzAsphaug1999_Icarus142_5} \\
    \hline
  \end{tabular}
\end{table}

<!-- TEX_EXCLUDE_START -->
### A.6 再現実行コマンド（Windows: run\_sweep.cmd）

Windows 環境での感度掃引の実行入口は `scripts/runsets/windows/run_sweep.cmd` とする．代表例として，設定ファイルと上書きファイルを明示した実行は次のとおりである．

\begin{verbatim}
scripts\runsets\windows\run_sweep.cmd ^
  --config scripts\runsets\common\base.yml ^
  --overrides scripts\runsets\windows\overrides.txt ^
  --out-root out
\end{verbatim}

同スクリプトの引数は次の Usage に従う（オプション名はスクリプト内の表示と一致）．

\begin{verbatim}
run_sweep.cmd [--study <path>] [--config <path>] [--overrides <path>]
            [--out-root <path>] [--dry-run] [--no-plot] [--no-eval]
            [--quiet] [--no-quiet] [--preflight-only] [--preflight-strict]
            [--debug]
\end{verbatim}

- `--study`: スイープ定義（YAML など）のパスを指定する．
- `--config`: ベース設定（YAML）のパスを指定する．
- `--overrides`: 上書き設定（テキスト）のパスを指定する．
- `--out-root`: 出力ルートを指定する．
- `--dry-run`: 実行計画の確認用に用いる．
- `--no-plot`: 実行後フックのうち可視化を抑制する．
- `--no-eval`: 実行後フックのうち評価を抑制する．
- `--quiet`/`--no-quiet`: ログ出力を切り替える．
- `--preflight-only`: 事前チェックのみ実行して終了する．
- `--preflight-strict`: 事前チェックを厳格モードで実行する．
- `--debug`: デバッグ出力を有効にする．

なお，スクリプトは既定で `requirements.txt` から依存関係を導入し，環境変数 `SKIP_PIP=1` により導入処理を省略できる（既に導入済みの場合は `REQUIREMENTS_INSTALLED=1`）．
<!-- TEX_EXCLUDE_END -->
## 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

本付録では，本研究で使用した主要な設定キーと物理の対応を表\ref{tab:app_config_physics_map}にまとめる．完全な設定スキーマは付属するコードに含め，論文本文では必要な範囲のみを示す．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{設定キーと物理の対応}
  \label{tab:app_config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 本文参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & 3節 \\
    \texttt{radiation.mars\_temperature}\newline \texttt{\_driver}\newline \texttt{.*} & 冷却ドライバ & 3節 \\
    \texttt{sizes.*} & 粒径グリッド（$s_{\min,\rm cfg},s_{\max},n_{\rm bins}$） & 3.1節, 3.3節 \\
    \texttt{shielding.mode} & 遮蔽 $\Phi$ & 2.2節 \\
    \texttt{sinks.mode} & 昇華/ガス抗力（追加シンク） & 2.5節 \\
    \texttt{blowout.enabled} & ブローアウト損失 & 2.1節 \\
    \texttt{supply.mode} & 表層供給 & 2.3節 \\
    \texttt{supply.mixing.epsilon\_mix} & 混合係数 $\epsilon_{\rm mix}$ & 2.3節, 3.3節 \\
    \texttt{optical\_depth.*} & 初期$\tau_0$規格化と停止判定 & 3.1節, 4.2節 \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & 4.2節 \\
    \hline
  \end{tabular}
\end{table}
## 付録 C. 外部入力（テーブル）一覧

<!--
実装(.py): marsdisk/run.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/tempdriver.py
-->

本モデルは，物性や放射輸送に関する外部テーブルを読み込み，本文中の式で用いる物理量（$T_M$, $\langle Q_{\rm pr}\rangle$, $\Phi$ など）を与える．論文ではテーブルの数値そのものを列挙せず，役割と参照先を表\ref{tab:app_external_inputs}にまとめる．実行時に採用したテーブルの出典と補間範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする（付録 A）．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{外部入力（テーブル）とモデル内での役割}
  \label{tab:app_external_inputs}
  \begin{tabular}{p{0.22\textwidth} p{0.46\textwidth} p{0.24\textwidth}}
    \hline
    外部入力 & 役割 & 本文参照（代表） \\
    \hline
    火星温度履歴 $T_M(t)$ &
    放射圧（β, $s_{\rm blow}$）・昇華の入力となる温度ドライバ &
    3節 \\
    Planck 平均 $\langle Q_{\rm pr}\rangle$ &
    放射圧効率として β と $s_{\rm blow}$ を決める（灰色体近似は例外） &
    2.1節 \\
    遮蔽係数 $\Phi(\tau_{\rm los})$（テーブル補間） &
    有効不透明度 $\kappa_{\rm eff}$ を通じて遮蔽に入る &
    2.2節 \\
    \hline
  \end{tabular}
\end{table}
## 付録 D. 略語索引

<!--
実装(.py): marsdisk/physics/psd.py, marsdisk/physics/surface.py, marsdisk/physics/smol.py, marsdisk/physics/radiation.py, marsdisk/physics/qstar.py, marsdisk/physics/sublimation.py, marsdisk/physics/viscosity.py
-->

略語は次の表にまとめる．

\begin{table}[t]
  \centering
  \caption{略語索引}
  \label{tab:app_abbreviations}
  \begin{tabular}{p{0.18\textwidth} p{0.44\textwidth} p{0.28\textwidth}}
    \hline
    略語 & 日本語 / 英語 & 備考 \\
    \hline
    PSD & 粒径分布 / particle size distribution & サイズビン分布 $n(s)$ \\
    LOS & 視線方向 / line of sight & $\tau_{\rm los}$ に対応 \\
    IMEX & implicit-explicit & IMEX-BDF(1) に使用 \\
    BDF & backward differentiation formula & 一次 BDF \\
    $Q_{\rm pr}$ & 放射圧効率 / radiation pressure efficiency & テーブル入力 \\
    $Q_D^*$ & 破壊閾値 / critical specific energy & 破壊強度 \\
    HKL & Hertz--Knudsen--Langmuir & 昇華フラックス \\
    1D & one-dimensional & 半径方向セル分割（リング分割） \\
    \hline
  \end{tabular}
\end{table}
<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

## 付録 E. 記号表

本論文で用いる記号と，その意味・単位をまとめる．本文中に示す式で用いる記号の定義も，本付録を正とする．主要記号は表\ref{tab:app_symbols_main}と表\ref{tab:app_symbols_main_cont}に示す．

### E.1 主要記号（本研究のダスト円盤モデル）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（本研究で用いる記号と単位）}
  \label{tab:app_symbols_main}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
	    $t$ & 時刻 & $\mathrm{s}$ & 解析では年へ換算して表示する場合がある \\
	    $r$ & 半径（代表半径） & $\mathrm{m}$ & 0D では代表値のみを用いる \\
	    $r_{\rm in},r_{\rm out}$ & 計算領域の内端・外端半径 & $\mathrm{m}$ & 環状領域 $[r_{\rm in},r_{\rm out}]$ \\
	    $A$ & 環状領域の面積 & $\mathrm{m^{2}}$ & 式\ref{eq:annulus_area_definition} \\
	    $A_\ell$ & セル $\ell$ の面積 & $\mathrm{m^{2}}$ & 1D の半径セル（リング）ごとの面積 \\
	    $M_{\rm in}$ & ロッシュ限界内側の内側円盤質量 & $\mathrm{kg}$ & 入力（3節） \\
		    $\Delta M_{\rm in}$ & 遷移期における不可逆損失（累積） & $\mathrm{kg}$ & 本論文では $M_{\rm loss}$ と同義 \\
		    $M_{\rm in}'$ & 更新後の内側円盤質量（長期モデルへ渡す量） & $\mathrm{kg}$ & $M_{\rm in}'=M_{\rm in}(t_0)-M_{\rm loss}(t_{\rm end})$ \\
	    $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
	    $T_{\rm orb}$ & 公転周期 & $\mathrm{s}$ & 式\ref{eq:torb_definition} \\
	    $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
    $s$ & 粒子半径 & $\mathrm{m}$ & PSD の独立変数 \\
	    $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
	    $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
    $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
    $Y_{kij}$ & 衝突 $(i,j)$ による破片生成の質量分率（ビン $k$ への配分） & -- & $\sum_k Y_{kij}=1$（式\ref{eq:fragment_yield_normalization}） \\
    $F_k$ & 供給ソース項（サイズビン $k$ への注入率） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:smoluchowski} \\
		    $S_k$ & 追加シンクの実効ロス率 & $\mathrm{s^{-1}}$ & 式\ref{eq:smoluchowski} \\
				    $\Sigma_{\rm surf}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
			    $\kappa_{\rm surf}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
			    $\tau_\perp$ & 鉛直方向の光学的厚さ（近似） & -- & $\tau_\perp=\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
		    $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ \\
	    $\kappa_{\rm eff}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
			    $f_{\rm los}$ & 鉛直光学的厚さ $\tau_\perp$ を $\tau_{\rm los}$ へ写像する幾何因子 & -- & $\tau_{\rm los}=f_{\rm los}\kappa_{\rm surf}\Sigma_{\rm surf}$ \\
			    $\tau_{\rm los}$ & 火星視線方向光学的厚さ（近似） & -- & 式\ref{eq:tau_los_definition}; 遮蔽評価に用いる \\
			    $\tau_{\rm eff}$ & 火星方向の有効光学的厚さ & -- & 式\ref{eq:tau_eff_definition}; 初期規格化と停止判定に用いる \\
			    $\Sigma_{\tau_{\rm los}=1}$ & $\tau_{\rm los}=1$ に対応する参照面密度 & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau_los1_definition}（$\Sigma_{\tau_{\rm los}=1}=(f_{\rm los}\kappa_{\rm surf})^{-1}$） \\
		    $\Sigma_{\tau=1}$ & 光学的厚さ $\tau=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition} \\
		    \hline
	  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（続き）}
  \label{tab:app_symbols_main_cont}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
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
		    $\mu$ & 分子量（HKL） & $\mathrm{kg\,mol^{-1}}$ & 式\ref{eq:hkl_flux} \\
		    \hline
	  \end{tabular}
\end{table}
