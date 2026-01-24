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

本節では，1D モデルで用いる計算領域（環状領域近似），粒子の力学的励起度（速度分散），および表層の質量収支（再供給・衝突破砕）を規定する基準パラメータを整理する．基準計算の採用値を表\ref{tab:method-param}に，衝突破砕の破壊閾値比エネルギー $Q_D^*(s)$ の係数を表\ref{tab:methods_qdstar_coeffs}に示す．感度解析で変更する追加パラメータとその範囲は付録 A にまとめる．

計算領域は $r\in[r_{\rm in},r_{\rm out}]$ の環状領域とし，巨大衝突により形成されるロッシュ限界内側のデブリ円盤成分を代表させる．火星のロッシュ限界はおよそ $3\,R_{\rm Mars}$ に位置し，巨大衝突起源モデルではロッシュ限界内側に質量の集中した内側円盤が形成されることが示されている \citep{Rosenblatt2016_NatGeo9_8,Hyodo2017b_ApJ851_122}．基準計算では $r_{\rm out}=2.7\,R_{\rm Mars}$ としてロッシュ限界のやや内側に計算領域を取り，外側円盤での衛星胚形成過程は本研究の対象外とする．内側円盤の総質量 $M_{\rm in}$ はロッシュ限界内側の中層（厚い円盤成分）に対応する量として与え，基準値 $M_{\rm in}=3\times10^{-5}\,M_{\rm Mars}$ は，火星周回円盤の初期質量に対する制約と整合する値として採用する \citep{CanupSalmon2018_SciAdv4_eaar6887}．

粒子の力学状態は代表離心率 $e_0$ と傾斜角 $i_0$ で与える．巨大衝突直後の粒子は高離心率の軌道にあり，歳差運動により軌道が乱された後に衝突が卓越し，相対衝突速度は $1$--$5\,\mathrm{km\,s^{-1}}$ 程度に達し得ることが報告されている \citep{Hyodo2017a_ApJ845_125}．また，傾斜した円盤は衝突を通じて赤道面へ減衰し得る \citep{Hyodo2017b_ApJ851_122}．本研究ではこれらを踏まえ，基準計算として $e_0=0.5$，$i_0=0.05$ を採用する．円盤のスケールハイトは小傾斜角近似に基づき $H=H_{\rm factor} i r$ と表す．

表層面密度の初期規格化には，火星方向の有効光学的厚さ $\tau_{\rm eff}$ を用いる（式\ref{eq:sigma_surf0_from_tau0}）．$\tau_{\rm eff}$ は線視方向光学的厚さ $\tau_{\rm los}$ に遮蔽係数を適用した量として定義され（式\ref{eq:tau_eff_definition}），本研究では表層を一様なシートとして表現し，実効不透明度 $\kappa_{\rm eff}$ と表層面密度 $\Sigma_{\rm surf}$ により閉じた形で与える（2.2節，および式\ref{eq:tau_los_definition}）．基準計算では $\tau_0=1$ を目標値として初期 $\Sigma_{\rm surf}$ を定めるが，これは放射場に対して光学的厚さが 1 程度の表層が円盤の放射応答を支配し得るという表層モデルの考え方と対応する．ただし，本研究の $\tau_{\rm los}$ は入射角分布や散乱を含む厳密な放射輸送を平均化した近似であり，この近似の影響は（必要に応じて）感度解析で確認する．

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
$r_{\rm out}$ & 2.7 & $R_{\rm Mars}$ & 外端半径（ロッシュ限界内側） \\
$N_r$ & 32 & -- & 半径方向セル数（リング分割） \\
$M_{\rm in}$ & $3.0\times10^{-5}$ & $M_{\rm Mars}$ & 内側円盤質量（中層） \\
$s_{\min,\rm cfg}$ & $1.0\times10^{-7}$ & m & 粒径ビン下限（数値下限） \\
$s_{\max}$ & $3.0$ & m & 粒径ビン上限 \\
$n_{\rm bins}$ & 40 & -- & サイズビン数（対数ビン） \\
$f_{\rm los}$ & 1.0 & -- & LOS 幾何因子（式\ref{eq:tau_los_definition}） \\
$\tau_0$ & 1.0 & -- & 初期 $\tau_{\rm eff}$ 目標値（式\ref{eq:sigma_surf0_from_tau0}） \\
$\tau_{\rm stop}$ & 2.302585 & -- & 停止判定（$=\ln 10$） \\
$e_0$ & 0.5 & -- & 代表離心率 \\
$i_0$ & 0.05 & rad & 代表傾斜角 \\
$H_{\rm factor}$ & 1.0 & -- & $H=H_{\rm factor} i r$ \\
$\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数 \\
$\mu_{\rm sup}$ & 1.0 & -- & 供給スケール（式\ref{eq:R_base_definition}） \\
$f_{\rm orb}$ & 0.05 & -- & $\mu_{\rm sup}=1$ のときの 1 軌道あたり供給比率 \\
$\tau_{\rm ref}$ & 1.0 & -- & 供給スケール参照光学的厚さ \\
$\alpha_{\rm frag}$ & 3.5 & -- & 破片分布指数 \\
$\rho$ & 3270 & kg\,m$^{-3}$ & 粒子密度（表\ref{tab:method-phys}） \\
\hline
\end{tabular}
\end{table}

初期 PSD は，巨大衝突後に形成されるメートル級固体粒子と，蒸気の凝縮により生じるサブミクロン粒子が共存し得るという二段階進化の描像に基づき，対数正規分布の混合（melt lognormal mixture）で与える \citep{Hyodo2017a_ApJ845_125}．\citet{Hyodo2017a_ApJ845_125} は，噴出時のせん断と表面張力によりメートル級滴が形成され得ること，その後の高速度衝突で最小 $\sim100\,\mu\mathrm{m}$ 程度まで微細化され得ること，さらに蒸気の凝縮により $\sim0.1\,\mu\mathrm{m}$ 粒子が形成され得ることを示している．一方で，サブミクロン粒子は質量は小さいが断面積で卓越し得るため \citep{Hyodo2017a_ApJ845_125}，不透明度や放射圧応答に対する寄与が大きい可能性がある．本研究では，凝縮由来の最微細粒子の寄与を制御するためのカットオフとして $s_{\rm cut}$ を導入し，$s<s_{\rm cut}$ の領域を初期 PSD から除外する（式\ref{eq:initial_psd_lognormal_mixture}）．$s_{\rm min,solid}$ と $s_{\rm max,solid}$ は固相 PSD の参照範囲を定め，${\rm width}_{\rm dex}$ は両成分に共通の対数幅（dex）である．また，$\alpha_{\rm frag}=3.5$ は自己相似な破壊カスケードで得られる Dohnanyi 型のサイズ分布（$n(s)\propto s^{-3.5}$）に対応する代表値として採用する \citep{Dohnanyi1969_JGR74_2531,Birnstiel2011_AA525_A11}．

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
${\rm width}_{\rm dex}$ & 0.3 & dex \\
$s_{\rm cut}$ & $1.0\times10^{-7}$ & m \\
$s_{\rm min,solid}$ & $1.0\times10^{-4}$ & m \\
$s_{\rm max,solid}$ & 3.0 & m \\
$\alpha_{\rm solid}$ & 3.5 & -- \\
\hline
\end{tabular}
\end{table}

衝突破砕の破壊閾値比エネルギー $Q_D^*(s)$ は，強度支配項と重力支配項の和として表現し，係数は \citet{BenzAsphaug1999_Icarus142_5} に基づく（この形式は衝突カスケードの標準的取り扱いとして用いられている；例えば \citealt{Thebault2003_AA408_775,Krivov2006_AA455_509}）．衝突速度依存性を取り込むため，基準計算では $v_{\rm ref}=1$--$7\,\mathrm{km\,s^{-1}}$ の離散点で係数を与え，実際の衝突速度に対しては後述の補間則により係数を連続化する．表\ref{tab:methods_qdstar_coeffs}の係数は $f_{Q^*}=5.574$ のスケールを適用した値であり，$Q_s$ と $B$ に反映されている（$f_{Q^*}$ の設定理由と掃引範囲は付録 A に示す）．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\caption{基準計算の $Q_D^*$ 係数（$v_{\rm ref}$ は $\mathrm{km,s^{-1}}$，$Q_s$ と $B$ は BA99 cgs 単位）}
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
