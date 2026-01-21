## 2. 円盤表層状態の評価

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

### 2.1 状態変数と定義

#### 2.1.1 粒径分布 (PSD) グリッド

PSD は衝突カスケードの統計的記述に基づき，自己相似分布の枠組み [@Dohnanyi1969_JGR74_2531] と離散化の実装例 [@Krivov2006_AA455_509] を踏まえて対数ビンで表す．ビン分解能は隣接粒径比 $a_{i+1}/a_i \lesssim 1.1$–1.2 を目安に調整する（[@Birnstiel2011_AA525_A11]）．ブローアウト近傍の波状構造（wavy）はビン幅に敏感であるため，数値的に解像できる分解能を確保する．
初期 PSD の既定は，衝突直後の溶融滴優勢と微粒子尾を持つ分布 [@Hyodo2017a_ApJ845_125] を反映し，溶融滴由来のべき分布は衝突起源の傾きを [@Jutzi2010_Icarus207_54] に合わせて設定する．

PSD は $n(s)$ を対数等間隔のサイズビンで離散化し，面密度・光学的厚さ・衝突率の評価を一貫したグリッド上で行う．隣接比 $s_{i+1}/s_i \lesssim 1.2$ を推奨し，供給注入と破片分布の双方がビン分解能に依存しないように設計する．PSD グリッドの既定値は付録B（表\ref{tab:psd_grid_defaults}）にまとめる．

有効最小粒径 $s_{\min,\mathrm{eff}}$ は次式で定義し，PSD の下限として用いる．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\mathrm{eff}}=\max\!\left(s_{\min,\mathrm{cfg}},\,s_{\mathrm{blow,eff}}\right)
\end{equation}

PSD は正規化分布 $n_k$ を保持し，表層面密度 $\Sigma_{\rm surf}$ を用いて実数の数密度 $N_k$（#/m$^2$）へスケールする．スケーリングは式\ref{eq:sigma_surf_definition}を満たすように行う．

\begin{equation}
\label{eq:sigma_surf_definition}
\Sigma_{\rm surf}(t)=\sum_k m_k N_k(t)
\end{equation}

- 時間積分は数密度 $N_k$ を状態として IMEX 更新し，形状情報として正規化分布 $n_k$ を併用する．
- PSD 下限は式\ref{eq:smin_eff_definition}の $s_{\min,\mathrm{eff}}$ を標準とする．昇華境界 $s_{\rm sub}$ は粒径収縮（ds/dt）として扱い，標準設定では PSD 床を自動的に切り上げない（必要時のみ動的床を用いる；設定は付録Bを参照）．
- 供給注入は PSD 下限（$s_{\min}$）より大きい最小ビンに集約し，質量保存と面積率の一貫性を保つ（[@WyattClarkeBooth2011_CeMDA111_1; @Krivov2006_AA455_509]）．
- ブローアウト近傍の波状構造（wavy）はビン幅に敏感であるため，必要に応じて補正を導入しつつ定性的に再現する（設定は付録Bを参照）．
- 本研究の基準設定は 40 ビンとし，wavy の再現や収束性が必要な場合は隣接粒径比が十分小さくなるようビン数を増やす（[@Birnstiel2011_AA525_A11]）．

PSD は形状（$n_k$）と規格化（$\Sigma_{\rm surf}$）を分離して扱うため，衝突解法と供給注入は同一のビン定義を共有しつつ，面密度の時間発展は独立に制御できる．これにより，供給・昇華・ブローアウトによる総質量変化と，衝突による分布形状の再配分を明示的に分離する（[@Krivov2006_AA455_509]）．

#### 2.1.2 光学的厚さ $\tau$ の定義

光学的厚さは用途ごとに以下を使い分ける（[@StrubbeChiang2006_ApJ648_652]）．

- **垂直方向**: $\tau_{\perp}$ は表層 ODE の $t_{\rm coll}=1/(\Omega\tau_{\perp})$ に用いる．必要に応じて $\tau_{\perp}=\tau_{\rm los}/f_{\rm los}$ を用いて評価する．
- **火星視線方向**: $\tau_{\rm los}=f_{\rm los}\tau_{\perp}$ を遮蔽（有効時）・停止判定・供給フィードバックに用いる．
- Smol 経路では $t_{\rm coll}$ をカーネル側で評価し，$\tau_{\rm los}$ は遮蔽とゲート判定の診断量として扱う．

$\tau$ に関するゲート・停止・診断量は次のように区別する．

- **$\tau_{\rm gate}$**: 放射圧アウトフロー抑制のゲート．$\tau_{\rm los}\ge\tau_{\rm gate}$ の場合は放射圧アウトフローを抑制する（停止しない）．本研究の標準設定ではこのゲートは用いず，感度試験でのみ導入する．
- **$\tau_{\rm stop}$**: 計算停止の閾値．$\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する．
- **$\Sigma_{\tau_{\perp}=1}$**: 有効不透明度 $\kappa_{\rm eff}$ から導出する診断量（式\ref{eq:sigma_tau1_definition}）．初期化や診断の参照に使うが，標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない．
- **$\tau_0=1$**: 初期化のスケーリング目標で，初期 PSD を $\tau=1$ に規格化して開始する場合に用いる．

なお，視線方向の $\tau_{\rm los}=1$ に対応する面密度は $\Sigma_{\tau_{\rm los}=1}=\Sigma_{\tau_{\perp}=1}/f_{\rm los}$ で与えられる．

$\tau_{\rm los}$ は遮蔽（$\Phi$）の入力として使われるほか，放射圧ゲート（$\tau_{\rm gate}$）や停止条件（$\tau_{\rm stop}$）の判定に用いる．$\Sigma_{\tau_{\perp}=1}$ は診断量として保存し，初期化や診断に参照するが，標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない．標準設定では遮蔽を無視し，$\Phi=1$（すなわち $\kappa_{\rm eff}=\kappa_{\rm surf}$）として扱う．

---
### 2.2 熱・放射・表層損失

放射圧と昇華は粒子の軽さ指標 β と表層質量の時間変化を通じて短期損失を支配する．放射圧の整理は古典的な定式化 [@Burns1979_Icarus40_1] に基づき，光学特性は Mie 理論の整理 [@BohrenHuffman1983_Wiley] を踏まえて $\langle Q_{\rm pr}\rangle$ テーブルを用いる．遮蔽の参照枠は gas-rich 表層流出の議論 [@TakeuchiLin2003_ApJ593_524] に置きつつ，gas-poor 条件を既定とする．

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

温度は放射圧効率 $\langle Q_{\rm pr}\rangle$，昇華フラックス，相判定に同時に入力される．温度ドライバの出典と採用した温度履歴は再現実行ログに保存する（付録A）．遮蔽係数 $\Phi$ は温度ドライバにはフィードバックしない．遮蔽は $\kappa_{\rm eff}$ と $\Sigma_{\tau_{\perp}=1}$ の評価，供給フィードバック，停止判定に用いる．

#### 2.2.2 放射圧・ブローアウト

軽さ指標 β とブローアウト粒径 $s_{\rm blow}$ を $\langle Q_{\rm pr}\rangle$ テーブルから評価する．固体相では β=0.5 を閾値として非束縛条件を与え，ブローアウト損失を適用する．ブローアウト滞在時間は $t_{\rm blow}=1/\Omega$（式\ref{eq:t_blow_definition}）を基準とし，感度試験では係数 $\chi_{\rm blow}$ により調整する．時間刻みの制約と補正は 4.2 節で述べる．

放射圧の軽さ指標とブローアウト粒径は式\ref{eq:beta_definition}と式\ref{eq:s_blow_definition}で定義する．

\begin{equation}
\label{eq:beta_definition}
\beta = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{4\,G\,M_{\mathrm{M}}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\mathrm{blow}} = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{2\,G\,M_{\mathrm{M}}\,c\,\rho}
\end{equation}

表層の外向流束は表層 ODE の場合に式\ref{eq:surface_outflux}で評価する．Smol 経路では $s \le s_{\rm blow}$ のビンに対して $S_{\rm blow}=1/t_{\rm blow}$ のシンクを適用し，$\dot{\Sigma}_{\rm out}=\sum_k m_k S_{{\rm blow},k} N_k$ を流出率として評価する．

\begin{equation}
\label{eq:surface_outflux}
\dot{\Sigma}_{\mathrm{out}} = \frac{\Sigma_{\mathrm{surf}}}{t_{\mathrm{blow}}}
\end{equation}

$\dot{\Sigma}_{\mathrm{out}}$ は面密度フラックス（$\mathrm{kg\,m^{-2}\,s^{-1}}$）であり，円盤全体の質量流出率（$\mathrm{kg\,s^{-1}}$）は面積要素で積分して定義する．

\begin{equation}
\label{eq:mdot_out_definition}
\dot{M}_{\mathrm{out}}(t)=\int_{r_{\mathrm{in}}}^{r_{\mathrm{out}}}2\pi r\,\dot{\Sigma}_{\mathrm{out}}(r,t)\,dr
\end{equation}

0D では，式\ref{eq:annulus_area_definition}の面積 $A$ を用いて $\dot{M}_{\mathrm{out}}=A\,\dot{\Sigma}_{\mathrm{out}}$ と簡略化する．

ブローアウト境界は β=0.5 を閾値とする非束縛条件に対応し，$s_{\rm blow}$ と $s_{\min,\mathrm{eff}}$ の関係が PSD 形状と流出率を支配する．ゲート有効時は $\tau_{\rm los}$ によって outflux が抑制される．

#### 2.2.3 遮蔽 (Shielding)

$\Phi(\tau,\omega_0,g)$ テーブル補間で有効不透明度を評価し，$\Sigma_{\tau_{\perp}=1}=1/\kappa_{\rm eff}$ を診断として記録する．本研究では遮蔽入力の $\tau$ は $\tau_{\rm los}$ を用いる．表層が光学的に厚くなり $\tau_{\rm los}>\tau_{\rm stop}$ となった場合は停止し，クリップは行わない．Φ テーブルの基礎近似は二流・δ-Eddington 系の解析解に基づく（[@Joseph1976_JAS33_2452; @HansenTravis1974_SSR16_527; @CogleyBergstrom1979_JQSRT21_265]）．

遮蔽係数は $\Phi=\Phi(\tau,\omega_0,g)$ として与えられ，有効不透明度と光学的厚さ 1 の表層面密度は次式で定義する．

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\mathrm{eff}} = \Phi(\tau)\,\kappa_{\mathrm{surf}}
\end{equation}

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau_{\perp}=1} =
\begin{cases}
 \kappa_{\mathrm{eff}}^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0.
\end{cases}
\end{equation}

\begin{equation}
\label{eq:phi_definition}
\Phi=\Phi(\tau,\omega_0,g)
\end{equation}

- Φテーブルは既定で外部入力とし，双線形補間で $\Phi$ を評価する．
- 遮蔽の扱いは，$\Phi(\tau)$ による有効不透明度評価，$\Sigma_{\tau_{\perp}=1}$ を固定する近似，または遮蔽を無視する近似（$\Phi=1$）から選ぶ（設定は付録Bを参照）．
- **停止条件**: $\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する（停止とクリップは別物として扱う）．
- **$\Sigma_{\tau_{\perp}=1}$ の扱い**: $\Sigma_{\tau_{\perp}=1}$ は診断量であり，初期化ポリシーに用いるが，標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない．

遮蔽係数は放射圧評価と供給フィードバックに入るため，$\tau_{\rm los}$ の定義とゲート順序は実装上の重要な仕様となる．$\tau_{\rm stop}$ は停止判定のみを担い，供給抑制や状態量クリップとは区別する．

#### 2.2.4 相判定 (Phase)

フォルステライト冷却マップまたは閾値から相（phase）を固体相/蒸気相に分類し，支配的な損失経路を選択する．判定には火星温度と光学的厚さを用いる．

固体相では放射圧ブローアウトが主要な損失経路となる．相判定は表層 ODE とシンク選択のゲートとして機能し，同一ステップ内でブローアウトと追加シンクが併用されることはない．

#### 2.2.5 昇華 (Sublimation) と追加シンク

HKL（Hertz–Knudsen–Langmuir）フラックスと飽和蒸気圧で質量損失を評価する（[@Markkanen2020_AA643_A16]）．Clausius 係数は [@Kubaschewski1974_Book] を基準とし，液相枝は [@FegleySchaefer2012_arXiv; @VisscherFegley2013_ApJL767_L12] を採用する．フォルステライトの蒸気圧パラメータはモデル入力として与え，今回の設定では $P_{\mathrm{gas}}=0$ として扱う．昇華フラックスの適用範囲は [@Pignatale2018_ApJ853_118] を参照する．

HKL フラックスは式\ref{eq:hkl_flux}で与える．HKL を用いない感度試験では簡略式に置き換える．飽和蒸気圧は式\ref{eq:psat_definition}で定義し，Clausius 型の解析式またはテーブル補間のいずれかを用いる．

\begin{equation}
\label{eq:hkl_flux}
J(T) =
\begin{cases}
 \alpha_{\mathrm{evap}}\max\!\bigl(P_{\mathrm{sat}}(T) - P_{\mathrm{gas}},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}, &
 \text{if HKL enabled},\\[10pt]
 \exp\!\left(\dfrac{T - T_{\mathrm{sub}}}{\max(dT, 1)}\right), & \text{otherwise.}
\end{cases}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\mathrm{sat}}(T) =
\begin{cases}
 10^{A - B/T}, & \text{if clausius},\\[6pt]
 10^{\mathrm{PCHIP}_{\log_{10}P}(T)}, & \text{if tabulated}.
\end{cases}
\end{equation}

- 質量保存型の処理では ds/dt だけを適用し，$s<s_{\rm blow}$ を跨いだ分をブローアウト損失へ振り替えて損失量の二重計上を避ける．
- 追加シンクを無効化した場合は，表層 ODE/Smol への追加シンクのロス項を停止する．
- ガス抗力は追加シンクのオプションとして扱い，gas-poor 既定では無効とする．
- 昇華境界 $s_{\rm sub}$ は PSD 床を直接変更せず，粒径収縮（ds/dt）と診断量として扱う．

昇華は PSD をサイズ方向にドリフトさせる過程として実装し，必要に応じて再ビニング（rebinning）を行う．損失項は IMEX の陰的ロスに含め，衝突ロスと同様に時間積分の安定性を確保する．
