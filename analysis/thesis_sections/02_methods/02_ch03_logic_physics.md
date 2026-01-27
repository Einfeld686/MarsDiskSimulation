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
w_{\rm melt}(s)\propto
(1-f_{\rm fine})\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm meter})}{\sigma_{\ln}}\right)^2\right]
+f_{\rm fine}\exp\!\left[-\frac{1}{2}\left(\frac{\ln(s/s_{\rm fine})}{\sigma_{\ln}}\right)^2\right],
\qquad
\sigma_{\ln}={\rm width}_{\rm dex}\ln 10
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
  \setlength{\tabcolsep}{4pt}
  \caption{物理定数・惑星定数・粒子物性（基準計算）}
  \label{tab:method-phys}
  \begin{tabular}{p{0.30\textwidth} p{0.22\textwidth} p{0.12\textwidth} p{0.26\textwidth}}
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
