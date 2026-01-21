### 4.2 熱・放射・表層損失

放射圧と昇華は粒子の軽さ指標 β と表層質量の時間変化を通じて短期損失を支配する．放射圧の整理は古典的な定式化 [@Burns1979_Icarus40_1] に基づき，光学特性は Mie 理論の整理 [@BohrenHuffman1983_Wiley] を踏まえて $\langle Q_{\rm pr}\rangle$ テーブルを用いる．遮蔽の参照枠は gas-rich 表層流出の議論 [@TakeuchiLin2003_ApJ593_524] に置きつつ，gas-poor 条件を既定とする．

#### 4.2.1 温度ドライバ

火星表面温度の時間変化を `constant` / `table` / `autogen` で選択する．各モードの概要は表\ref{tab:temp_driver_modes}に示す．

- `autogen` は解析的冷却（slab）や Hyodo 型などの内蔵ドライバを選択し，温度停止条件と連動する（[@Hyodo2018_ApJ860_150]）．

\begin{table}[t]
  \centering
  \caption{温度ドライバのモード}
  \label{tab:temp_driver_modes}
  \begin{tabular}{p{0.2\textwidth} p{0.4\textwidth} p{0.32\textwidth}}
    \hline
    モード & 内容 & 設定参照 \\
    \hline
    \texttt{table} & 外部 CSV テーブル補間 & \texttt{radiation.mars\_temperature\_driver.table.*} \\
    \texttt{slab} & 解析的 $T^{-3}$ 冷却 (Stefan--Boltzmann) & 内蔵式 \\
    \texttt{hyodo} & 線形熱流束に基づく冷却 & \texttt{radiation.mars\_temperature\_driver.hyodo.*} \\
    \hline
  \end{tabular}
\end{table}

温度は放射圧効率 $\langle Q_{\rm pr}\rangle$，昇華フラックス，相判定に同時に入力され，`T_M_used` と `T_M_source` が診断に記録される．遮蔽係数 $\Phi$ は温度ドライバにはフィードバックせず，放射圧評価・相判定（粒子平衡温度の推定）でのみ用いる．

> **詳細**: analysis/equations.md (E.042)–(E.043)  
> **フロー図**: analysis/physics_flow.md §3 "温度ドライバ解決フロー"  
> **設定**: analysis/config_guide.md §3.2 "mars_temperature_driver"

#### 4.2.2 放射圧・ブローアウト

軽さ指標 β (E.013) とブローアウト粒径 $s_{\rm blow}$ (E.014) を $\langle Q_{\rm pr}\rangle$ テーブルから評価する．本書では粒径を $s_{\rm blow}$ と表記し，コードや出力列では `a_blow` が同義の名称として残る．

- $\langle Q_{\rm pr}\rangle$ はテーブル入力（CSV/NPZ）を既定とし，Planck 平均から β と $s_{\rm blow}$ を導出する．
- ブローアウト（blow-out）損失は **phase=solid かつ $\tau$ ゲートが開放**（$\tau_{\rm los}<\tau_{\rm gate}$）のときのみ有効化し，それ以外は outflux=0 とする．
- 外向流束は $t_{\rm blow}=1/\Omega$（E.007）を基準とし，実装では `chi_blow_eff` を掛けた $t_{\rm blow}=\chi_{\rm blow}/\Omega$ を用いる．補正状況は `dt_over_t_blow`・`fast_blowout_flag_gt3/gt10` とともに診断列へ出力する．
- β の閾値判定により `case_status` を分類し，ブローアウト境界と PSD 床の関係を `s_min_components` に記録する．
- 表層流出率 $\dot{M}_{\rm out}$ の定義は (E.009) を参照し，表層 ODE を使う場合は $t_{\rm blow}$ を (E.007) の形で評価する．

放射圧の軽さ指標とブローアウト粒径は式\ref{eq:beta_definition}と式\ref{eq:s_blow_definition}で定義する（再掲: E.013, E.014）．

\begin{equation}
\label{eq:beta_definition}
\beta = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{4\,G\,M_{\mathrm{M}}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\mathrm{blow}} = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{2\,G\,M_{\mathrm{M}}\,c\,\rho}
\end{equation}

表層の外向流束は式\ref{eq:surface_outflux}で評価する（再掲: E.009）．

\begin{equation}
\label{eq:surface_outflux}
\dot{M}_{\mathrm{out}} = \Sigma_{\mathrm{surf}}\,\Omega
\end{equation}

ブローアウト境界は β=0.5 を閾値とする非束縛条件に対応し，$s_{\rm blow}$ と $s_{\min,\mathrm{eff}}$ の関係が PSD 形状と流出率を支配する．ゲート有効時は $\tau$ によって outflux が抑制される．

> **詳細**: analysis/equations.md (E.009), (E.012)–(E.014), (E.039)  
> **用語**: analysis/glossary.md G.A04 (β), G.A05 (s_blow)  
> **設定**: analysis/config_guide.md §3.2 "Radiation"

#### 4.2.3 遮蔽 (Shielding)

$\Phi(\tau,\omega_0,g)$ テーブル補間で有効不透明度を評価し，$\Sigma_{\tau=1}=1/\kappa_{\rm eff}$ を診断として記録する．表層が光学的に厚くなり $\tau_{\rm los}>\tau_{\rm stop}$ となった場合は停止し，クリップは行わない．Φ テーブルの基礎近似は二流・δ-Eddington 系の解析解に基づく（[@Joseph1976_JAS33_2452; @HansenTravis1974_SSR16_527; @CogleyBergstrom1979_JQSRT21_265]）．

遮蔽による有効不透明度と光学的厚さ 1 の表層面密度は式\ref{eq:kappa_eff_definition}と式\ref{eq:sigma_tau1_definition}で与える（再掲: E.015, E.016）．

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\mathrm{eff}} = \Phi(\tau)\,\kappa_{\mathrm{surf}}
\end{equation}

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau=1} =
\begin{cases}
 \kappa_{\mathrm{eff}}^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0.
\end{cases}
\end{equation}

- Φテーブルは既定で外部入力とし，双線形補間で $\Phi$ を評価する．
- `shielding.mode` により `psitau` / `fixed_tau1` / `off` を切り替える．
- **停止条件**: $\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する（停止とクリップは別物として扱う）．
- **$\Sigma_{\tau=1}$ の扱い**: $\Sigma_{\tau=1}$ は診断量であり，初期化ポリシーに用いるが，標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない．

遮蔽係数は放射圧評価と供給フィードバックに入るため，$\tau_{\rm los}$ の定義とゲート順序は実装上の重要な仕様となる．$\tau_{\rm stop}$ は停止判定のみを担い，供給抑制や状態量クリップとは区別する．

> **詳細**: analysis/equations.md (E.015)–(E.017)  
> **設定**: analysis/config_guide.md §3.4 "Shielding"

#### 4.2.4 相判定 (Phase)

SiO₂ 冷却マップまたは閾値から相（phase）を `solid`/`vapor` に分類し，シンク経路を自動選択する．

- 判定には火星温度と遮蔽後の光学的厚さを用い，`phase_state` と `sink_selected` を診断に記録する．

固体相では放射圧ブローアウトが主要な損失経路となり，蒸気相では水素流体逃亡（hydrodynamic escape）スケーリングを用いた損失に切り替わる（[@Hyodo2018_ApJ860_150; @Ronnet2016_ApJ828_109]）．蒸気相では `hydro_escape_timescale` から $t_{\rm sink}$ を評価し，`sink_selected="hydro_escape"` として記録する．相判定は表層 ODE とシンク選択のゲートとして機能し，同一ステップ内でブローアウトと流体力学的損失が併用されることはない．

> **フロー図**: analysis/physics_flow.md §4 "相判定フロー"  
> **設定**: analysis/config_guide.md §3.8 "Phase"

#### 4.2.5 昇華 (Sublimation) と追加シンク

HKL（Hertz–Knudsen–Langmuir）フラックス (E.018) と飽和蒸気圧 (E.036) で質量損失を評価する（[@Markkanen2020_AA643_A16]）．Clausius 係数は [@Kubaschewski1974_Book] を基準とし，液相枝は [@FegleySchaefer2012_arXiv; @VisscherFegley2013_ApJL767_L12] を採用する．SiO 既定パラメータと支配的蒸気種の整理は [@Melosh2007_MPS42_2079] を参照し，$P_{\mathrm{gas}}$ の扱いは [@Ronnet2016_ApJ828_109] と同様に自由パラメータとして扱う．昇華フラックスの適用範囲は [@Pignatale2018_ApJ853_118] を参照する．

HKL フラックスは式\ref{eq:hkl_flux}で与える（再掲: E.018）．飽和蒸気圧は式\ref{eq:psat_definition}で定義する（再掲: E.036）．

\begin{equation}
\label{eq:hkl_flux}
J(T) =
\begin{cases}
 \alpha_{\mathrm{evap}}\max\!\bigl(P_{\mathrm{sat}}(T) - P_{\mathrm{gas}},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}, &
 \text{if mode}\in\{\text{``hkl'', ``hkl\_timescale''}\} \text{ and HKL activated},\\[10pt]
 \exp\!\left(\dfrac{T - T_{\mathrm{sub}}}{\max(dT, 1)}\right), & \text{otherwise.}
\end{cases}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\mathrm{sat}}(T) =
\begin{cases}
 10^{A - B/T}, & \text{if }\texttt{psat\_model} = \text{``clausius''},\\[6pt]
 10^{\mathrm{PCHIP}_{\log_{10}P}(T)}, & \text{if }\texttt{psat\_model} = \text{``tabulated''}.
\end{cases}
\end{equation}

- `sub_params.mass_conserving=true` の場合は ds/dt だけを適用し，$s<s_{\rm blow}$ を跨いだ分をブローアウト損失へ振り替えてシンク質量を維持する．
- `sinks.mode` を `none` にすると追加シンクを無効化し，表層 ODE/Smol へのロス項を停止する．
- ガス抗力は `sinks.mode` のオプションとして扱い，gas-poor 既定では無効．
- 昇華境界 $s_{\rm sub}$ は PSD 床を直接変更せず，粒径収縮（ds/dt）と診断量として扱う．

昇華は PSD をサイズ方向にドリフトさせる過程として実装し，必要に応じて再ビニング（rebinning）を行う．損失項は IMEX の陰的ロスに含め，衝突ロスと同様に時間積分の安定性を確保する．

> **詳細**: analysis/equations.md (E.018)–(E.019), (E.036)–(E.038)  
> **設定**: analysis/config_guide.md §3.6 "Sinks"

---
