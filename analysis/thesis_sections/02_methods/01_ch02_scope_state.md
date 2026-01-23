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

表層への供給率（面密度注入率）を $\dot{\Sigma}_{\rm in}(t,r)$ とし，混合係数 $\epsilon_{\rm mix}$ と入力関数 $R_{\rm base}$ から式\ref{eq:prod_rate_definition}で与える\citep{Wyatt2008}．本研究の基準ケースでは，$R_{\rm base}$ を「参照面密度の一定割合を 1 軌道あたり供給する」定常供給として次で定義する．

\begin{equation}
\label{eq:R_base_definition}
R_{\rm base}(t,r)=
\frac{\mu_{\rm sup}\,f_{\rm orb}}{\epsilon_{\rm mix}}
\frac{\Sigma_{\tau_{\rm ref}}(t_0,r)}{T_{\rm orb}(r)},
\qquad
\Sigma_{\tau_{\rm ref}}(t_0,r)=\frac{\tau_{\rm ref}}{f_{\rm los}\kappa_{\rm eff}(t_0,\tau_{\rm ref})}
\end{equation}

ここで $\mu_{\rm sup}$ は供給スケール（無次元），$f_{\rm orb}$ は $\mu_{\rm sup}=1$ のとき 1 軌道あたりに供給する面密度の比率（無次元），$\tau_{\rm ref}$ は参照有効光学的厚さ（既定 1）である．$\Sigma_{\tau_{\rm ref}}$ は初期 PSD から評価した $\kappa_{\rm eff}$ に基づく参照面密度であり，$\tau_0$ の掃引と独立に「同じ $\mu_{\rm sup}$ が同じ供給量」を指すよう規格化している．供給率は PSD のソース項 $F_k$ として式\ref{eq:supply_injection_definition}で注入し，質量保存条件 $\sum_k m_k F_k=\dot{\Sigma}_{\rm in}$ を満たすよう重み $w_k$ を正規化する．本研究では再供給される表層物質の代表として，注入重みを初期 PSD の質量分率に比例させ（$w_k=n_k(t_0)$），供給によって分布形状は直接は変えずに規格化のみを更新する近似を採用する．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\rm in}(t,r) = \max\!\left(\epsilon_{\rm mix}\;R_{\rm base}(t,r),\,0\right)
\end{equation}

\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},\qquad \sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}

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
