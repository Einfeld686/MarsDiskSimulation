<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/io/tables.py, marsdisk/physics/psd.py, marsdisk/physics/sizes.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/initfields.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @Avdellidou2016_MNRAS464_734 -> paper/references/Avdellidou2016_MNRAS464_734.pdf | 用途: Q_D* スケーリングの proxy（peridot projectile）
- @BenzAsphaug1999_Icarus142_5 -> paper/references/BenzAsphaug1999_Icarus142_5.pdf | 用途: Q_D* の基準（BA99 係数）
- @Birnstiel2011_AA525_A11 -> paper/references/Birnstiel2011_AA525_A11.pdf | 用途: PSDビン分解能の指針（隣接粒径比）
- @BohrenHuffman1983_Wiley -> paper/references/BohrenHuffman1983_Wiley.pdf | 用途: Mie理論に基づくQ_pr平均の背景
- @CanupSalmon2018_SciAdv4_eaar6887 -> paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf | 用途: 火星円盤の背景条件（軸対称1Dの前提）
- @Dohnanyi1969_JGR74_2531 -> paper/references/Dohnanyi1969_JGR74_2531.pdf | 用途: 自己相似PSDの基準
- @Hyodo2017a_ApJ845_125 -> paper/references/Hyodo2017a_ApJ845_125.pdf | 用途: 初期PSDの溶融滴成分と円盤前提
- @Jutzi2010_Icarus207_54 -> paper/pdf_extractor/outputs/Jutzi2010_Icarus207_54/result.md | 用途: 初期PSDのべき指数（衝突起源）
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: PSD離散化とSmoluchowski解法
- @LeinhardtStewart2012_ApJ745_79 -> paper/references/LeinhardtStewart2012_ApJ745_79.pdf | 用途: Q_D*補間（LS12）
- @Olofsson2022_MNRAS513_713 -> paper/references/Olofsson2022_MNRAS513_713.pdf | 用途: 高密度デブリ円盤の文脈
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: 光学的厚さと表層t_coll定義
- @TakeuchiLin2003_ApJ593_524 -> paper/references/TakeuchiLin2003_ApJ593_524.pdf | 用途: gas-rich表層ODEの参照枠（既定無効）
- @WyattClarkeBooth2011_CeMDA111_1 -> paper/references/WyattClarkeBooth2011_CeMDA111_1.pdf | 用途: s_min床・供給注入の基準
<!-- TEX_EXCLUDE_END -->

## 2. 円盤表層状態の評価

本章の目的は，巨大衝突後に形成される火星周回デブリ円盤のうち，放射圧および昇華に直接曝される表層成分を対象として，数値モデルで用いる状態変数と表層質量損失過程の定式化を整理することである．ここでは，まず PSD と光学的厚さの定義（2.1）を与え，次に放射圧ブローアウトと昇華を中心とする表層損失過程（2.2）を導入する．

本研究では，表層の時間発展を（i）表層面密度の常微分方程式（表層 ODE）として近似する経路と，（ii）粒径分布を Smoluchowski 型方程式で追跡する経路（Smol 経路）のいずれかで扱い，採用した経路に応じて同一の記号体系で記述する．標準設定では Smol 経路を用い，gas-rich 想定の感度試験でのみ表層 ODE を有効化する（付録B）．

### 2.1 状態変数と定義

本節の目的は，粒径分布（PSD）の離散化と光学的厚さの定義を与え，後続節で用いる記号体系を確定させることである．以後，粒径は粒子半径 $s$ として表す．

#### 2.1.1 粒径分布 (PSD) グリッド

PSD は衝突カスケードの統計的記述に基づき，自己相似分布の枠組み [@Dohnanyi1969_JGR74_2531] と離散化の実装例 [@Krivov2006_AA455_509] を踏まえて対数ビンで表現する．隣接粒径比 $s_{k+1}/s_k \lesssim 1.1$–1.2 を目安に分解能を調整し（[@Birnstiel2011_AA525_A11]），ブローアウト近傍の波状構造（wavy）が数値的に解像できるようにする．

粒径ビン $k$ の代表半径を $s_k$，その粒子質量を $m_k$ とし，数面密度（単位面積当たり個数）を $N_k(t)$（m$^{-2}$）で表す．粒子のバルク密度を $\rho$ とすると，
\begin{equation}
\label{eq:mk_definition}
m_k=\frac{4\pi}{3}\rho s_k^3
\end{equation}
である．表層面密度 $\Sigma_{\rm surf}(t)$ は
\begin{equation}
\label{eq:sigma_surf_definition}
\Sigma_{\rm surf}(t)=\sum_k m_k N_k(t)
\end{equation}
で定義する．

PSD の「形状」と「規格化」を分離して扱うため，必要に応じて質量分率
\begin{equation}
\label{eq:nk_massfrac_definition}
n_k(t)=\frac{m_k N_k(t)}{\Sigma_{\rm surf}(t)}
\end{equation}
を導入する．このとき $\sum_k n_k=1$ が成り立ち，総質量変化（供給・昇華・ブローアウト）と，衝突による分布形状の再配分を明示的に分けて解釈できる（[@Krivov2006_AA455_509]）．

PSD 下限は有効最小粒径 $s_{\min,\mathrm{eff}}$ により与える．
\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\mathrm{eff}}=\max\!\left(s_{\min,\mathrm{cfg}},\,s_{\mathrm{blow,eff}}\right)
\end{equation}
ここで $s_{\min,\mathrm{cfg}}$ は計算設定で与える下限，$s_{\mathrm{blow,eff}}$ は放射圧により非束縛となる境界粒径である（後述の式\ref{eq:s_blow_definition}）．標準設定では，昇華境界 $s_{\rm sub}$ によって PSD 床を自動的に切り上げず，粒径収縮（$ds/dt$）として扱う（必要時のみ動的床を導入；設定は付録Bを参照）．

供給注入は PSD 下限より大きい最小ビンへ集約し，質量保存と面積率の一貫性を保つ（[@WyattClarkeBooth2011_CeMDA111_1; @Krivov2006_AA455_509]）．PSD グリッドのサイズ範囲・ビン境界・代表値定義などの既定値は付録B（表\ref{tab:psd_grid_defaults}）にまとめる．

#### 2.1.2 光学的厚さ $\tau$ の定義

光学的厚さは，衝突頻度の見積りに用いる量と，火星から粒子へ到達する放射場の遮蔽判定に用いる量とが一般に一致しないため，円盤面に垂直な方向（$\tau_\perp$）と火星視線方向（$\tau_{\rm los}$）を用途に応じて区別する（[@StrubbeChiang2006_ApJ648_652]）．

まず，表層の質量不透明度（質量消散係数）$\kappa_{\rm surf}$（単位：m$^{2}$ kg$^{-1}$）を
\begin{equation}
\label{eq:kappa_surf_definition}
\kappa_{\rm surf}
=\frac{1}{\Sigma_{\rm surf}}\sum_k \pi s_k^2\,N_k
\end{equation}
で定義する．以下では光学的厚さの診断として幾何断面積近似（$Q_{\rm ext}=1$）を採用し，$\kappa_{\rm surf}$ を表層粒子の幾何断面積/質量として評価する．このとき垂直方向の光学的厚さは
\begin{equation}
\label{eq:tau_perp_definition}
\tau_\perp=\kappa_{\rm surf}\Sigma_{\rm surf}
\end{equation}
で与えられる．

次に，火星中心から粒子を見込む視線方向（line of sight; los 方向）の光学的厚さ $\tau_{\rm los}$ は，幾何学的補正因子 $f_{\rm los}$ を用いて
\begin{equation}
\label{eq:tau_los_definition}
\tau_{\rm los}=f_{\rm los}\tau_\perp
\end{equation}
と近似する．$f_{\rm los}$ は，垂直方向の代表光路長に対する los 方向の代表光路長の比を表す無次元量であり，円盤の厚みと視線幾何に依存する．本研究で用いる $f_{\rm los}$ の定義と採用値は付録Bに示す．

表層 ODE を用いる場合，衝突時間は $t_{\rm coll}=1/(\Omega\tau_\perp)$ とおく．ここで $\Omega$ は対象セル（半径 $r$）でのケプラー角速度である．一方，Smol 経路では衝突頻度を衝突カーネルから直接評価するため，$\tau_\perp$ と $\tau_{\rm los}$ は主として診断量として参照する．このうち $\tau_{\rm los}$ は，遮蔽係数 $\Phi$ の評価（式\ref{eq:phi_definition}）および放射圧流出の抑制判定に用いる．

$\tau$ に関する閾値・診断量は，目的を混同しないために次の4種に分類して扱う．
- **遮蔽判定閾値 $\tau_{\rm gate}$**：$\tau_{\rm los}\ge\tau_{\rm gate}$ のとき，放射圧による流出項を抑制する（計算は継続する）．標準設定では無効化し，感度試験でのみ導入する．
- **計算停止閾値 $\tau_{\rm stop}$**：$\tau_{\rm los}>\tau_{\rm stop}$ のとき，シミュレーションを終了する．
- **診断量 $\Sigma_{\tau_{\rm los}=1}$**：有効不透明度と視線補正因子から導く参照面密度であり（式\ref{eq:sigma_tau1_definition}），初期化および診断に参照するが，標準の時間発展で $\Sigma_{\rm surf}$ を直接クリップしない．
- **規格化目標 $\tau_0(=1)$**：初期化の目標光学的厚さであり，初期 PSD を $\tau_{\rm los}=\tau_0$ に規格化して開始する場合に用いる．
これらのうち $\tau_{\rm gate}$ と $\tau_{\rm stop}$ は，光学的に厚い領域で表層近似や遮蔽の簡略化などの適用が不確かになることを避けるために導入する適用範囲判定である．したがって結果の議論は，$\tau_{\rm los}\le\tau_{\rm stop}$ を満たすケースに限定する．

以上により，本節では PSD と光学的厚さの定義，および $\tau$ に関する閾値・診断量の役割を整理した．次節では，これらの状態量を用いて放射圧ブローアウトと昇華による表層損失を定式化する．

---
### 2.2 熱・放射・表層損失

本節では，火星からの放射を駆動源とする放射圧ブローアウトと，昇華による粒径縮小・追加損失を定式化する．放射圧は古典的定式化 [@Burns1979_Icarus40_1] に基づき，光学特性は Mie 理論の整理 [@BohrenHuffman1983_Wiley] を踏まえて $\langle Q_{\rm pr}\rangle$ テーブルを用いる．遮蔽の参照枠は gas-rich 表層流出の議論 [@TakeuchiLin2003_ApJ593_524] を踏まえるが，本研究の標準設定は gas-poor 条件である．

#### 2.2.1 温度ドライバ

火星表面温度 $T_M(t)$ は，固定値・外部テーブル補間・解析的冷却モデルのいずれかで与える．分類を表\ref{tab:temp_driver_modes}に示す（[@Hyodo2018_ApJ860_150]）．

\begin{table}[t]
  \centering
  \caption{火星温度 $T_M(t)$ の与え方}
  \label{tab:temp_driver_modes}
  \begin{tabular}{p{0.22\textwidth} p{0.52\textwidth} p{0.18\textwidth}}
    \hline
    種別 & 内容 & 備考 \\
    \hline
    固定値 & 一定の $T_M$ を与える & 感度試験用 \\
    テーブル補間 & 外部テーブル $T_M(t)$ を補間する & 任意の冷却曲線 \\
    解析的冷却モデル & Stefan--Boltzmann 型（slab）または Hyodo 型の冷却を用いる & 文献ベース \\
    \hline
  \end{tabular}
\end{table}

温度は放射圧効率 $\langle Q_{\rm pr}\rangle$，昇華フラックス，相判定に入力される．採用した温度履歴と出典は再現実行ログ（付録A）に保存する．本研究では $T_M(t)$ を外部ドライバとして与えるため，遮蔽による温度ドライバのフィードバックは扱わない．相判定および昇華で用いる粒子平衡温度も光学的に薄い近似（遮蔽無視）で与えるため，光学的に厚い条件では昇華損失を過大評価し，放射圧ブローアウトを過小評価し得る．ただし本研究の基準ケースは光学的に薄い表層を主対象とする．

#### 2.2.2 放射圧・ブローアウト

粒子半径 $s$ に対する軽さ指標 $\beta(s)$ は
\begin{equation}
\label{eq:beta_definition}
\beta(s) = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}(s)\rangle}{4\,G\,M_{\mathrm{M}}\,c\,\rho\,s}
\end{equation}
で定義し，$\beta\ge 0.5$ を非束縛条件（ブローアウト）とする．$\langle Q_{\rm pr}\rangle$ は粒径と温度に依存するため，事前に Mie 計算で得た $Q_{\rm pr}(s,\lambda)$ を火星温度 $T_M$ の Planck 関数で平均し，
\[
\langle Q_{\rm pr}(s)\rangle=\frac{\int Q_{\rm pr}(s,\lambda)\,B_\lambda(T_M)\,d\lambda}{\int B_\lambda(T_M)\,d\lambda}
\]
として $(s,T_M)$ の格子上にテーブル化した値を補間して用いる．採用した光学定数データとテーブルの有効範囲は付録Cおよび再現実行ログ（付録A）に記録する．

ブローアウト境界粒径 $s_{\rm blow}$ は $\beta(s_{\rm blow})=0.5$ を満たす粒径として定義する（離散ビンでは，$\beta\ge 0.5$ のビンをブローアウト対象とする）．便宜上，$\langle Q_{\rm pr}\rangle$ を与えたときの形式解は
\begin{equation}
\label{eq:s_blow_definition}
s_{\mathrm{blow}} = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{2\,G\,M_{\mathrm{M}}\,c\,\rho}
\end{equation}
である．

ブローアウトによる流出の代表時間は
\begin{equation}
\label{eq:t_blow_definition}
t_{\rm blow}=\chi_{\rm blow}\Omega^{-1}
\end{equation}
とし，$\chi_{\rm blow}=1$ を既定とする（感度試験で調整）．
基準ケースでは $\chi_{\rm blow}$ を 0.5–2 の範囲で変更しても主要診断量（$\Delta M_{\rm in}$ など）が数値丸め誤差以下であることを確認した（表\ref{tab:approx_sensitivity}）．ただし放射圧損失が支配的な条件では $\dot{\Sigma}_{\mathrm{out}}\propto t_{\rm blow}^{-1}$ となるため，$\chi_{\rm blow}$ は感度試験パラメータとして扱う．

放射圧ブローアウトによる表層流出（面密度フラックス）$\dot{\Sigma}_{\rm out}$ は，採用する表層更新方式に応じて
\begin{equation}
\label{eq:surface_outflux}
\dot{\Sigma}_{\mathrm{out}} =
\begin{cases}
 \Sigma_{\mathrm{surf}}/t_{\rm blow}, & \text{表層 ODE}, \\
 \sum_k m_k S_{{\rm blow},k} N_k, & \text{Smol 経路}.
\end{cases}
\end{equation}
ここで $S_{{\rm blow},k}$ はブローアウト対象ビンに適用する一次シンクであり，$S_{{\rm blow},k}=1/t_{\rm blow}$（$s_k\le s_{\rm blow}$）とする．遮蔽判定閾値 $\tau_{\rm gate}$ を有効化した場合は，$\tau_{\rm los}$ に基づいて流出を抑制する．

円盤全体の質量流出率 $\dot{M}_{\rm out}$ は，$\dot{\Sigma}_{\rm out}$ を計算領域で面積積分して
\begin{equation}
\label{eq:mdot_out_definition}
\dot{M}_{\rm out}(t)=\int_{r_{\rm in}}^{r_{\rm out}}2\pi r\,\dot{\Sigma}_{\rm out}(r,t)\,dr
\end{equation}
で定義する．0D では対象領域の面積 $A$（式\ref{eq:annulus_area_definition}）を用いて $\dot{M}_{\rm out}\simeq A\,\dot{\Sigma}_{\rm out}$ と近似する．

#### 2.2.3 遮蔽 (Shielding)

遮蔽は，表層が光学的に厚い場合に火星からの放射場が弱められる効果を表す．本研究では吸収減衰の近似として
\begin{equation}
\label{eq:phi_definition}
\Phi=\exp(-\tau_{\rm los})
\end{equation}
を採用する．実装ではこの関数をテーブルとして保持し，補間により評価する．散乱を含むより一般の放射輸送（$\Phi(\tau,\omega_0,g)$ のテーブル化；例：二流・δ-Eddington 近似）は本研究のスコープ外とし，将来拡張として位置づける．

有効不透明度と，火星視線方向の光学的厚さ1に相当する参照面密度を
\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\mathrm{eff}} = \Phi\,\kappa_{\mathrm{surf}}
\end{equation}
\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau_{\rm los}=1} =
\begin{cases}
 (\kappa_{\mathrm{eff}} f_{\rm los})^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0
\end{cases}
\end{equation}
で定義し，$\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する．垂直方向の参照面密度は $\Sigma_{\tau_\perp=1}=f_{\rm los}\Sigma_{\tau_{\rm los}=1}$ として与える．標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない．

遮蔽の取り扱いは（i）$\Phi=\exp(-\tau_{\rm los})$ を適用する方法，（ii）$\Sigma_{\tau_{\rm los}=1}$ を固定する近似，（iii）遮蔽を無視する近似（$\Phi=1$）から選ぶ（設定は付録B）．基準ケースでは遮蔽の有無による $\Delta M_{\rm in}$ の差が数値丸め誤差以下であることを確認した（表\ref{tab:approx_sensitivity}）．停止条件は $\tau_{\rm los}>\tau_{\rm stop}$ とし，停止と状態量クリップは区別する．

\begin{table}[t]
  \centering
  \caption{主要近似パラメータの簡易感度確認（0D 基準ケース）}
  \label{tab:approx_sensitivity}
  \begin{tabular}{p{0.34\textwidth} p{0.24\textwidth} p{0.32\textwidth}}
    \hline
    近似・パラメータ & 変更範囲 & 代表ケースでの影響（主要診断量） \\
    \hline
    ブローアウト滞在時間係数 $\chi_{\rm blow}$ &
    0.5–2 &
    $\Delta M_{\rm in}$ の変化は数値丸め誤差以下 \\
    遮蔽の有無（$\Phi=1$ vs $\Phi=\exp(-\tau_{\rm los})$） &
    on/off &
    $\Delta M_{\rm in}$ の変化は数値丸め誤差以下 \\
    \hline
  \end{tabular}
\end{table}

#### 2.2.4 相判定 (Phase)

相（phase）は，表層が固体優勢か蒸気優勢かを判定し，支配的な損失経路（放射圧ブローアウト／昇華・追加シンク）の適用範囲を制御するために導入する．本研究では温度閾値に基づく判定（threshold）を標準とし，温度入力は火星照射の灰色体近似に基づく粒子平衡温度 $T_p$ とする．すなわち
\begin{equation}
\label{eq:grain_temperature_definition}
T_p = T_M\,\langle Q_{\rm abs}\rangle^{1/4}\sqrt{\frac{R_M}{2r}}
\end{equation}
を用い，$T_p\le T_{\rm condense}$ を固体，$T_p\ge T_{\rm vaporize}$ を蒸気として分類する（閾値は付録Aの表\ref{tab:run_sweep_material_properties}）．遷移領域では $\tau_{\rm los}$（LOS）により蒸気分率の増加を緩和するが，基準ケースでは温度条件が支配的である．

固体相では放射圧ブローアウトが主要な損失経路となる．相判定は表層 ODE とシンク選択の適用条件として機能し，同一ステップ内でブローアウトと追加シンクは併用しない．

#### 2.2.5 昇華 (Sublimation) と追加シンク

昇華は HKL（Hertz--Knudsen--Langmuir）フラックスにより評価する（[@Markkanen2020_AA643_A16]）．飽和蒸気圧 $P_{\rm sat}(T)$ は Clausius 型の解析式またはテーブル補間で与える．使用したパラメータと出典は付録Aの表\ref{tab:run_sweep_material_properties}にまとめる．

HKL による質量フラックス $J(T)$（単位：kg m$^{-2}$ s$^{-1}$）は
\begin{equation}
\label{eq:hkl_flux}
J(T) =
 \alpha_{\mathrm{evap}}\max\!\bigl(P_{\mathrm{sat}}(T) - P_{\mathrm{gas}},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}
\end{equation}
で与える．ここで $\alpha_{\rm evap}$ は蒸発係数，$\mu$ はモル質量，$R$ は気体定数，$P_{\rm gas}$ は周囲ガスの分圧である．本研究の基準設定では $P_{\rm gas}=0$ として扱う．

飽和蒸気圧は
\begin{equation}
\label{eq:psat_definition}
P_{\mathrm{sat}}(T) =
\begin{cases}
 10^{A - B/T}, & \text{Clausius 型},\\
 10^{\mathrm{PCHIP}_{\log_{10}P}(T)}, & \text{テーブル補間}.
\end{cases}
\end{equation}
で定義する．

粒径縮小は，球対称昇華を仮定して
\begin{equation}
\label{eq:dsdt_definition}
\frac{ds}{dt}=-\frac{J(T)}{\rho}
\end{equation}
として扱う．質量保存型の処理では $ds/dt$ を適用し，$s<s_{\rm blow}$ を跨いだ分はブローアウト損失へ振り替えて損失の二重計上を避ける．

昇華は PSD をサイズ方向にドリフトさせる過程として実装し，必要に応じて再ビニング（rebinning）を行う．損失項は IMEX 法の陰的ロスに含め，衝突ロスと同様に時間積分の安定性を確保する．HKL を無効化した場合は昇華を適用せず，$ds/dt=0$ とする．

以上により，本章では表層の状態変数（PSD，$\tau$）と，放射圧ブローアウトおよび昇華に基づく損失過程を定義した．次章では，表層への再供給と輸送を導入し，供給注入項を定式化する．
