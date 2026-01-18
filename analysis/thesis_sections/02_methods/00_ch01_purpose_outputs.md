文書種別: リファレンス（Diátaxis: Reference）

<!--
NOTE: このファイルは analysis/thesis_sections/02_methods/*.md の結合で生成する。
編集は分割ファイル側で行い、統合は `python -m analysis.tools.merge_methods_sections --write` を使う。
-->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @CanupSalmon2018_SciAdv4_eaar6887 -> paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf | 用途: 火星円盤の物理的前提（低質量円盤の文脈）
- @Hyodo2017a_ApJ845_125 -> paper/references/Hyodo2017a_ApJ845_125.pdf | 用途: 衝突起源円盤の前提条件と対象設定
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: Smoluchowski衝突カスケードの枠組み
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: 表層ブローアウトと衝突寿命の整理
<!-- TEX_EXCLUDE_END -->

# シミュレーション手法

## 1. シミュレーションの全体像

### 1.1 目的・出力・問いとの対応

本節では、火星のロッシュ限界内に形成される高温ダスト円盤を対象として、本研究で用いる数値シミュレーション手法の目的と出力を定義する。序論で掲げた研究課題に対し、本手法が直接算出する物理量と出力ファイルの対応を明確にする。

本手法はガスが希薄な条件（gas-poor）を仮定する（[@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887]）。粒径分布（particle size distribution; PSD）の時間発展と、表層の放射圧起因アウトフロー（outflux）を、同一のタイムループで結合して計算する。これにより、2 年スケールでの質量流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}$ を評価する。放射圧に起因する粒子運動と粒径分布進化は、既存の枠組みに従う（[@Krivov2006_AA455_509; @StrubbeChiang2006_ApJ648_652]）。

数式と記号の定義は付録にまとめた式番号 (E.###) を正とする。本文では、計算手順と出力仕様の理解に必要な範囲で、主要式のみを再掲する。以降では、離散化、数値解法、運用フロー、ならびに検証条件を、物理過程の因果関係が追える順序で記述する。

序論で提示した 3 つの問いと、本手法が直接生成する量・出力の対応を次の表に示す。

\begin{table}[t]
  \centering
  \caption{序論の問いと手法で直接生成する量の対応}
  \label{tab:methods_questions_outputs}
  \begin{tabular}{p{0.20\textwidth} p{0.32\textwidth} p{0.38\textwidth}}
    \hline
    序論の問い & 手法で直接生成する量 & 対応する出力 \\
    \hline
    問1: 高温期（1000 K まで／固定地平 2 年）の総損失量 &
    時間依存の流出率と累積損失 &
    \texttt{series/run.parquet} の\newline
    \texttt{M\_out\_dot}\newline
    \texttt{mass\_lost\_by\_blowout}\newline
    \texttt{mass\_lost\_by\_sinks}\newline
    \texttt{summary.json} の \texttt{M\_loss} \\
    問2: 粒径分布の時間変化と吹き飛びやすい粒径帯 &
    粒径ビンごとの数密度履歴と下限粒径 &
    \texttt{series/psd\_hist.parquet} の\newline
    \texttt{bin\_index}\newline
    \texttt{s\_bin\_center}\newline
    \texttt{N\_bin}\newline
    \texttt{Sigma\_surf}\newline
    \texttt{series/run.parquet} の \texttt{s\_min} \\
    問3: 短期損失を踏まえた残存質量の評価 &
    累積損失と質量収支の時系列 &
    \texttt{summary.json} の \texttt{M\_loss}\newline
    （初期条件との差分で残存量を評価）\newline
    \texttt{series/run.parquet} の\newline
    \texttt{mass\_lost\_by\_blowout}\newline
    \texttt{mass\_lost\_by\_sinks} \\
    \hline
  \end{tabular}
\end{table}

手法の記述は、まず入力パラメータと出力（時系列・要約量）を明確にする。次に 1 ステップの処理順序を示す。続いて、放射圧、物質供給、衝突、昇華、遮蔽を順に定式化する。最後に、一括実行（`run_sweep`）と再現性確保のための出力・検証手続きを述べる。

設定キーや実装パスのような実装依存の情報は付録に整理し、本文では物理モデルと時間発展の説明を優先する。本文で頻出する略語は次の表にまとめる。

\begin{table}[t]
  \centering
  \caption{本文で用いる主要略語}
  \label{tab:methods_abbrev}
  \begin{tabular}{p{0.18\textwidth} p{0.76\textwidth}}
    \hline
    略語・記号 & 意味 \\
    \hline
    $\tau$ & 光学的厚さ（optical depth） \\
    LOS & 視線方向（line of sight） \\
    ODE & 常微分方程式（ordinary differential equation） \\
    IMEX & implicit--explicit 法 \\
    BDF & backward differentiation formula \\
    $Q_{\rm pr}$ & 放射圧効率（radiation pressure efficiency） \\
    $Q_D^*$ & 破壊閾値（critical specific energy） \\
    HKL & Hertz--Knudsen--Langmuir フラックス \\
    1D & one-dimensional \\
    \hline
  \end{tabular}
\end{table}

以上により、本節では研究課題と出力の対応を定義した。次節以降では、これらの出力を規定する物理過程と数値解法を順に述べる。

---
### 1.2 研究対象と基本仮定

本モデルは gas-poor 条件下の**軸対称ディスク**を対象とし、鉛直方向は面密度へ積分して扱う。半径方向に分割した 1D 計算を基準とし（[@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887; @Olofsson2022_MNRAS513_713]）、光学的厚さは主に火星視線方向の $\tau_{\rm los}$ を用いる。必要に応じて $\tau_{\rm los}=\tau_{\perp}\times\mathrm{los\_factor}$ から $\tau_{\perp}$ を導出し、表層 ODE の $t_{\rm coll}$ 評価に使う。粒径分布 $n(s)$ をサイズビンで離散化し、Smoluchowski 衝突カスケード（collisional cascade）と表層の放射圧・昇華による流出を同一ループで結合する（[@Dohnanyi1969_JGR74_2531; @Krivov2006_AA455_509; @StrubbeChiang2006_ApJ648_652]）。

- 標準の物理経路は Smoluchowski 経路（C3/C4）を各半径セルで解く 1D 手法で、実装の計算順序は図 3.2 に従う。放射圧〜流出の依存関係のみを抜粋すると ⟨$Q_{\rm pr}$⟩→β→$s_{\rm blow}$→遮蔽Φ→供給→Smol IMEX→外向流束となる。半径方向の粘性拡散（radial viscous diffusion; C5）は演算子分割で追加可能とする（[@Krivov2006_AA455_509]）。  
  > **参照**: analysis/overview.md §1, analysis/physics_flow.md §2「各タイムステップの物理計算順序」
- 運用スイープの既定は 1D とし、C5 は必要時のみ有効化する。具体的な run_sweep 手順と環境変数は付録 A、設定→物理対応は付録 B を参照する。
- [@TakeuchiLin2003_ApJ593_524] に基づく gas-rich 表層 ODE は `ALLOW_TL2003=false` が既定で無効。gas-rich 感度試験では環境変数を `true` にして `surface.collision_solver=surface_ode` を選ぶ。\newline 例: `configs/scenarios/gas_rich.yml`。\newline **参照**: analysis/equations.md（冒頭注記）, analysis/overview.md §1「gas-poor 既定」

1D は $r_{\rm in}$–$r_{\rm out}$ を $N_r$ セルに分割し、各セルの代表半径 $r_i$ で局所量を評価する。角速度 $\Omega(r_i)$ とケプラー速度 $v_K(r_i)$ は (E.001)–(E.002) に従い、$t_{\rm blow}$ や $t_{\rm coll}$ の基準時間に用いる。C5 を無効化した場合はセル間結合を行わず、半径方向の流束を解かない局所進化として扱う。

#### 1.2.1 物性モデル (フォルステライト)

物性は **フォルステライト** を基準として与える。密度・放射圧効率 $\langle Q_{\rm pr}\rangle$・昇華（HKL）の係数はフォルステライト値を採用する。一方、破壊閾値 $Q_D^*$ は BA99 の基準則を LS12 の速度補間で扱い、フォルステライト直系の $Q_D^*$ が未確定なため peridot projectile 実験の $Q^*$ を参照した係数スケーリングで proxy 化している（[@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79; @Avdellidou2016_MNRAS464_734]）。$\rho$ と $\langle Q_{\rm pr}\rangle$ の感度掃引を想定し、実行時の採用値は `run_config.json` に保存する。

$\langle Q_{\rm pr}\rangle$ はテーブル入力（CSV/NPZ）を標準とし、Planck 平均の評価に用いる（[@BohrenHuffman1983_Wiley]）。遮蔽係数 $\Phi(\tau,\omega_0,g)$ もテーブル入力を基本とし、双線形補間で適用する（[@Joseph1976_JAS33_2452; @HansenTravis1974_SSR16_527; @CogleyBergstrom1979_JQSRT21_265]）。これらのテーブルは `run_config.json` にパスが保存され、再現実行時の参照点となる。

- **参照**: analysis/equations.md（物性前提）

---
### 1.3 時間発展アルゴリズム

時間発展ループの全体像と処理順序を整理し、主要な依存関係を示す。実装順序は analysis/physics_flow.md を正とし、ここでは概念図として示す。

#### 1.3.0 支配方程式の位置づけ

本書では主要式を抜粋して再掲し、式番号・記号定義は analysis/equations.md を正とする。

- **軌道力学と時間尺度**: (E.001)–(E.002) で $\Omega$, $v_K$ を定義し、$t_{\rm blow}$ の基準は (E.007) に従う。放射圧の整理は [@Burns1979_Icarus40_1] を採用する。
- **衝突カスケード**: PSD の時間発展は Smoluchowski 方程式 (E.010) を用い、質量収支は (E.011) で検査する。枠組みは [@Krivov2006_AA455_509; @Dohnanyi1969_JGR74_2531] に基づく。
- **破砕強度と破片生成**: 破壊閾値 $Q_D^*$ の補間 (E.026) は [@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79] を参照する。
- **放射圧ブローアウト**: β と $s_{\rm blow}$ の定義は (E.013)–(E.014)、表層流出は (E.009) に依拠する。
- **昇華と追加シンク**: HKL フラックス (E.018) と飽和蒸気圧 (E.036) に基づき、昇華モデルの位置づけは [@Markkanen2020_AA643_A16] を参照する。
- **遮蔽と表層**: 自遮蔽係数 $\Phi$ は (E.015)–(E.017) により表層に適用し、gas-rich 条件の参照枠は [@TakeuchiLin2003_ApJ593_524] で位置づける。

以下の図は、入力（YAML/テーブル）から初期化・時間発展・診断出力に至る主経路を示す。**実装順序は analysis/physics_flow.md を正**とし、ここでは概念的な依存関係の整理として示す。

#### 1.3.1 シミュレーション全体像

```mermaid
flowchart TB
    subgraph INPUT["入力"]
        CONFIG["YAML 設定ファイル"]
        TABLES["テーブルデータ<br/>Qpr, Φ, 温度"]
    end

    subgraph INIT["初期化"]
        PSD0["初期 PSD 生成"]
        TEMP0["火星温度 T_M"]
        TAU1["τ0=1 表層定義"]
    end

    subgraph LOOP["時間発展ループ"]
        direction TB
        DRIVER["温度ドライバ更新"]
        RAD["放射圧評価<br/>β, s_blow"]
        PSDSTEP["PSD/κ 評価<br/>κ_surf, τ_los"]
        PHASE["相判定/τゲート"]
        SUBL["昇華 ds/dt 評価"]
        SINKTIME["シンク時間 t_sink"]
        SHIELD["遮蔽 Φ 適用<br/>κ_eff, Σ_tau1"]
        SUPPLY["表層再供給/輸送"]
        EVOLVE["表層/Smol 更新<br/>IMEX-BDF(1)"]
        CHECK["質量収支・停止判定"]
    end

    subgraph OUTPUT["出力"]
        SERIES["series/run.parquet"]
        PSDHIST["series/psd_hist.parquet"]
        SUMMARY["summary.json"]
        BUDGET["checks/mass_budget.csv"]
        CKPT["checkpoint/"]
    end

    CONFIG --> INIT
    TABLES --> INIT
    INIT --> LOOP
    DRIVER --> RAD --> PSDSTEP --> PHASE --> SUBL --> SINKTIME --> SHIELD --> SUPPLY --> EVOLVE --> CHECK
    CHECK -->|"t < t_end"| DRIVER
    CHECK -->|"t ≥ t_end or T_M ≤ T_stop"| OUTPUT
```

#### 1.3.2 メインループ詳細

```mermaid
flowchart LR
    subgraph STEP["1ステップの処理（3ブロック）"]
        direction TB

        subgraph A["円盤表層状態の更新"]
            direction TB
            S1["1. 温度ドライバ更新（global）<br/>T_M(t)"]
            S2["2. 放射圧計算（global）<br/>⟨Q_pr⟩ → β → s_blow"]
            S3["3. PSD/κ 評価（cell）<br/>κ_surf, τ_los"]
            S4["4. 相判定/ゲート（cell）<br/>phase, τ_gate, allow_supply"]
            S5["5. 昇華 ds/dt 評価（cell）<br/>HKL → ds/dt"]
            S6["6. シンク時間（cell）<br/>t_sink"]
        end

        subgraph B["表層への質量供給"]
            direction TB
            S7["7. 遮蔽 Φ 適用（cell）<br/>κ_eff, Σ_tau1"]
            S8["8. 表層再供給/輸送（cell）<br/>prod_rate_applied, deep mixing"]
        end

        subgraph C["微細化シミュレーション"]
            direction TB
            S9["9. Smol/Surface 積分（cell）<br/>衝突 + 供給 + 損失"]
            S10["10. 診断・停止判定・出力"]
        end

        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10
    end
```

補足: 損失項（ブローアウト・追加シンク）は S9 の IMEX 更新に含まれる。S4 は相判定とゲート（$\\tau_{\\rm gate}$, `allow_supply`）を決め、S6 は $t_{\\rm sink}$ を評価し、S10 は診断集計と出力を担当する。

図 3.2 は run_sweep 既定（1D + Smol）の順序に合わせ、analysis/physics_flow.md §2 と整合するように記述する。まず「円盤表層状態の更新」（S1–S6）で $T_M$、β、$s_{\rm blow}$、$\\kappa_{\\rm surf}$、$\\tau_{\\rm los}$、相状態、昇華 ds/dt、$t_{\\rm sink}$ を評価する。次に「表層への質量供給」（S7–S8）で遮蔽係数 $\\Phi$ から $\\kappa_{\\rm eff}$ と $\\Sigma_{\\tau=1}$ を得て、供給を表層/深層へ配分し `prod_rate_applied` を確定する。最後に「微細化シミュレーション」（S9–S10）で Smol/Surface の更新により PSD と $\\Sigma_{\\rm surf}$ を $\\Delta t$ だけ進め、損失と診断を集約する。

図 3.2 の手順と実装の対応は次の通りである。S1 は温度ドライバの評価と $T_M$ の更新、S2 は $Q_{\rm pr}$ テーブルから β と $s_{\rm blow}$ を評価する。S3 は PSD から $\\kappa_{\\rm surf}$ を評価して $\\tau_{\\rm los}$ を計算する。S4 は相判定とゲート（$\\tau_{\\rm gate}$、液相ブロック、`allow_supply`）により有効な経路を選択する。S5 は HKL に基づく昇華 ds/dt を評価する。S6 は追加シンクの代表時間 $t_{\\rm sink}$ を評価する。S7 は $\\Phi$ を適用して $\\kappa_{\\rm eff}$ と $\\Sigma_{\\tau=1}$ を評価する。S8 は供給率の名目値を計算し、温度スケール・$\\tau$ フィードバック・有限リザーバ・深層輸送を適用して `prod_rate_applied` を決定する。S9 は衝突カーネルに基づく gain/loss と供給・シンクを含めた IMEX 更新を行う。S10 は $\\dot{M}_{\\rm out}$ などの診断集計、$\\tau_{\\rm stop}$ 超過の停止判定、C4 質量収支検査、および出力書き込みに対応する。

#### 1.3.3 物理過程の相互作用

```mermaid
graph LR
    subgraph SURFACE["表層 (Surface)"]
        PSD["粒径分布 n(s)"]
        SIGMA["面密度 Σ_surf"]
    end
    
    subgraph RADIATION["放射"]
        TM["火星温度 T_M"]
        BETA["軽さ指標 β"]
        BLOW["ブローアウト s_blow"]
    end
    
    subgraph COLLISIONS["衝突"]
        KERNEL["衝突カーネル C_ij"]
        QSTAR["破壊閾値 Q_D*"]
        FRAG["破片分布"]
    end
    
    subgraph SINKS["損失"]
        BLOWOUT["ブローアウト流出"]
        SUBL["昇華 ds/dt"]
    end
    
    subgraph SUPPLY_BOX["供給"]
        EXT["表層再供給率"]
        DEEP["深層リザーバ"]
        FB["τフィードバック"]
    end
    
    TM --> BETA --> BLOW
    BLOW --> PSD
    PSD --> KERNEL --> FRAG --> PSD
    PSD --> SIGMA
    SIGMA -->|"τ"| FB --> EXT --> DEEP --> SIGMA
    PSD --> BLOWOUT
    TM --> SUBL --> PSD
    QSTAR --> KERNEL
```

主要状態変数は PSD 形状 $n_k$（`psd_state.number`）、表層面密度 $\Sigma_{\rm surf}$、深層リザーバ面密度 $\Sigma_{\rm deep}$、累積損失量 $M_{\rm out}$/$M_{\rm sink}$ であり、時間発展ごとに同時更新される（[@Krivov2006_AA455_509]）。Smol 更新では $N_k$ を一時的に構成して積分し、更新後に $n_k$ へ写像して `psd_state` に戻す。計算順序と依存関係は analysis/physics_flow.md の結合順序図に従う。

#### 1.3.4 供給・衝突・昇華の時系列因果

供給（supply）・衝突（collision）・昇華（sublimation）は同一ステップ内で相互依存するため、因果順序を図 3.2 の 3 ブロックに沿って固定する。すなわち「円盤表層状態の更新」（S1–S6）で $\\tau_{\\rm los}$・相状態・昇華 ds/dt・$t_{\\rm sink}$ を評価し、「表層への質量供給」（S7–S8）で遮蔽 $\\Phi$ と深層輸送を含む `prod_rate_applied` を確定し、最後に「微細化シミュレーション」（S9–S10）で IMEX 更新と診断集計を行う（[@WyattClarkeBooth2011_CeMDA111_1; @Krivov2006_AA455_509; @Markkanen2020_AA643_A16]）。

```mermaid
flowchart TB
    A["円盤表層状態の更新<br/>S1–S6"] --> B["表層への質量供給<br/>S7–S8"] --> C["微細化シミュレーション<br/>S9–S10"]
```

セル内の評価順序（概念）は次の通りである。

```mermaid
flowchart TB
    S3["S3: κ_surf, τ_los"] --> S4["S4: phase / gates"] --> S5["S5: ds/dt"] --> S6["S6: t_sink"]
    S6 --> S7["S7: shielding Φ"] --> S8["S8: supply split"] --> S9["S9: Smol IMEX"] --> S10["S10: diagnostics"]
```

S3〜S10 の要点は次の通りである。

- S3: PSD から $\\kappa_{\\rm surf}$ を評価し、$\\tau_{\\rm los}$ を計算する。
- S4: 相判定とゲート（$\\tau_{\\rm gate}$、液相ブロック、`allow_supply`）を評価し、各経路を有効化する。
- S5: HKL に基づく昇華 ds/dt を評価する。
- S6: シンク時間 $t_{\\rm sink}$ を評価する。
- S7: 遮蔽 $\\Phi$ を適用して $\\kappa_{\\rm eff}$ と $\\Sigma_{\\tau=1}$ を評価する。
- S8: 名目供給に温度スケール・$\\tau$ フィードバック・有限リザーバ・深層輸送を適用し、表層への注入量 `prod_rate_applied` を決定する。
- S9: 衝突カーネルから loss/gain を構成し、供給と損失を含めた IMEX 更新を実施する。
- S10: 診断列は `smol_gain_mass_rate`, `smol_loss_mass_rate`, `ds_dt_sublimation`, `M_out_dot` を含む。質量収支を保存する。

##### 1.3.4.1 供給フロー（Supply）

```mermaid
flowchart TB
    BASE["R_base(t,r)"] --> MIX["mixing ε_mix"]
    MIX --> TEMP["temperature coupling (optional)"]
    TEMP --> FB["τ-feedback (optional)"]
    FB --> RES["reservoir clip (optional)"]
    RES --> RATE["prod_rate_raw (allow_supply gate)"]

    TAU1["Σ_tau1 from shielding"] --> SPLIT["split: surface vs deep (transport)"]
    RATE --> SPLIT
    SPLIT --> SURF["prod_rate_applied_to_surf"]
    SPLIT --> DEEP["sigma_deep / deep_to_surf_flux"]
```

- 診断列は `supply_rate_nominal` → `supply_rate_scaled` → `supply_rate_applied` に記録する（[@WyattClarkeBooth2011_CeMDA111_1]）。
- 深層経路は `prod_rate_diverted_to_deep`\newline `deep_to_surf_flux`\newline `prod_rate_applied_to_surf` に記録する。
- 供給の有効化は phase（solid）と液相ブロックで決まり、$\\tau_{\\rm gate}$ はブローアウトのみをゲートする。供給側のフィードバックは $\\tau_{\\rm los}$ を参照し、停止判定（$\\tau_{\\rm stop}$）とは区別して扱う。

##### 1.3.4.2 衝突フロー（Collision）

```mermaid
flowchart TB
    A["compute v_rel"] --> B["kernel C_ij"]
    B --> C["loss term"]
    B --> D["fragment yield Y"]
    D --> E["gain term"]
    C & E --> F["assemble Smol RHS"]
    F --> G["IMEX update"]
```

- 相対速度は $e,i$ と $c_{\\rm eq}$ から評価し、カーネル $C_{ij}$ を構成する（[@Ohtsuki2002_Icarus155_436; @WetherillStewart1993_Icarus106_190]）。
- loss は `smol_loss_mass_rate`、gain は `smol_gain_mass_rate` として診断される。
- 最小衝突時間 $t_{\\rm coll,\\,min}$ が $\\Delta t$ の上限に用いられる。
- 破片分布 $Y$ は PSD グリッド上で再配分され、質量保存は C4 により検査される（[@Krivov2006_AA455_509; @Thebault2003_AA408_775]）。

##### 1.3.4.3 昇華フロー（Sublimation）

```mermaid
flowchart TB
    A["evaluate HKL flux"] --> B["compute ds/dt"]
    B --> C["size drift / rebin"]
    B --> D["sink timescale"]
    C & D --> E["merge into loss term"]
    E --> F["IMEX update"]
```

- HKL フラックスから ds/dt を評価し、必要に応じて再ビニングで PSD を更新する（[@Markkanen2020_AA643_A16; @Pignatale2018_ApJ853_118]）。
- `sub_params.mass_conserving=true` の場合は $s<s_{\\rm blow}$ を跨いだ質量をブローアウトへ振り替える。
- 昇華由来の損失は `ds_dt_sublimation` と `mass_lost_sublimation_step` に出力される。
