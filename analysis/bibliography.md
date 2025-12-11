# 参考文献一覧 (Bibliography)

本ファイルは、火星月形成円盤シミュレーション (marsdisk) で使用している全ての参考文献を網羅的に整理したものです。論文執筆時の引用漏れ防止と、コード・数式との対応関係の明確化を目的としています。

> **更新方法**: `python -m tools.reference_tracker report` で現在のコード引用状況を確認し、新規文献追加時は `references.registry.json` と本ファイルの両方を更新してください。
> **数式の扱い**: 式と係数は `analysis/equations.md` の (E.xxx) を唯一のソースとし、本ファイルでは再掲しない。必要箇所は (E.xxx) 参照で示す。

---

## 目次

1. [火星衛星形成・衝突起源](#1-火星衛星形成衝突起源)
2. [放射圧・Blow-out・デブリディスク物理](#2-放射圧blow-outデブリディスク物理)
3. [衝突カスケード・粒径分布](#3-衝突カスケード粒径分布)
4. [破砕強度・衝突破壊](#4-破砕強度衝突破壊)
5. [速度分散・相対速度](#5-速度分散相対速度)
6. [粘性進化・リング力学](#6-粘性進化リング力学)
7. [昇華・蒸気圧](#7-昇華蒸気圧)
8. [光学特性・Mie理論](#8-光学特性mie理論)
9. [輻射輸送・遮蔽](#9-輻射輸送遮蔽)
10. [相転移・SiO₂物性](#10-相転移sio物性)
11. [軌道力学・基礎](#11-軌道力学基礎)
12. [ガスドラッグ・大気捕獲](#12-ガスドラッグ大気捕獲)

---

## 1. 火星衛星形成・衝突起源

火星衛星 (Phobos/Deimos) の巨大衝突起源仮説に関する論文群。初期条件、円盤構造、ガス希薄仮定の根拠を提供する。
**Analysis参照**: 背景・前提は `analysis/overview.md` の起源シナリオ節を参照。

### Hyodo et al. (2017a)
- **Key**: `Hyodo2017a_ApJ845_125`
- **Title**: On the Impact Origin of Phobos and Deimos I: Thermodynamic and Physical Aspects
- **Journal**: ApJ, 845, 125
- **DOI**: [10.3847/1538-4357/aa81c4](https://doi.org/10.3847/1538-4357/aa81c4)
- **使用箇所**: 初期条件設定、gas-poor前提の根拠
- **主張**:
  - 巨大衝突直後の円盤は >95 wt% 溶融物、<5 wt% 蒸気（~2000 K）
  - メートルスケール破片から 100 µm–0.1 µm 粒子へのカスケード過程

### Hyodo et al. (2017b)
- **Key**: `Hyodo2017b_ApJ851_122`
- **Title**: On the Impact Origin of Phobos and Deimos II: True Polar Wander and Disk Evolution
- **Journal**: ApJ, 851, 122
- **DOI**: [10.3847/1538-4357/aa9984](https://doi.org/10.3847/1538-4357/aa9984)
- **使用箇所**: 円盤進化シナリオ
- **主張**:
  - J2歳差と非弾性衝突による円盤の円形化
  - 内側高密度・外側低密度の放射方向コントラスト

### Hyodo et al. (2018) ⭐
- **Key**: `Hyodo2018_ApJ860_150`
- **Title**: On the Impact Origin of Phobos and Deimos IV: Volatile Depletion
- **Journal**: ApJ, 860, 150
- **DOI**: [10.3847/1538-4357/aac024](https://doi.org/10.3847/1538-4357/aac024)
- **使用箇所**: `radiation.grain_temperature_graybody()`, `sublimation.py`
- **コード引用**: ✅ `[@Hyodo2018_ApJ860_150]`
- **数式**: E.042, E.043
- **主張**:
  - 放射スラブ冷却と灰色体温度の希釈因子を (E.042–E.043) に委譲
  - 数公転での揮発成分脱出と β 閾値

### Pignatale et al. (2018) ⭐
- **Key**: `Pignatale2018_ApJ853_118`
- **Title**: On the Impact Origin of Phobos and Deimos III: Resulting Composition from Different Impactors
- **Journal**: ApJ, 853, 118
- **DOI**: [10.3847/1538-4357/aaa23e](https://doi.org/10.3847/1538-4357/aaa23e)
- **使用箇所**: `sublimation.mass_flux_hkl()`
- **コード引用**: ✅ `[@Pignatale2018_ApJ853_118]`
- **主張**:
  - 蒸気凝縮物と溶融固化粒子の組成差
  - 昇華パラメータと SiO-rich シンクの熱化学的動機付け

### Ronnet et al. (2016) ⭐
- **Key**: `Ronnet2016_ApJ828_109`
- **Title**: Reconciling the orbital and physical properties of the Martian moons with a giant impact origin
- **Journal**: ApJ, 828, 109
- **DOI**: [10.3847/0004-637X/828/2/109](https://doi.org/10.3847/0004-637X/828/2/109)
- **使用箇所**: `sublimation.s_sink_from_timescale()`
- **コード引用**: ✅ `[@Ronnet2016_ApJ828_109]`
- **主張**:
  - 外縁ガス層での凝縮がPhobos/Deimosスペクトルと整合
  - マグマオーシャン由来物質だけでは観測制約を再現不可

### Canup & Salmon (2018)
- **Key**: `CanupSalmon2018_SciAdv4_eaar6887`
- **Title**: Origin of Phobos and Deimos by the impact of a Vesta-to-Ceres-sized body with Mars
- **Journal**: Science Advances, 4, eaar6887
- **DOI**: [10.1126/sciadv.aar6887](https://doi.org/10.1126/sciadv.aar6887)
- **使用箇所**: gas-poor標準設定の根拠
- **主張**:
  - M_disk ≤ 3×10⁻⁵ M_Mars かつ Q/k₂ < 80 で小衛星生存
  - 低質量・低ガス円盤の必要性

### Kuramoto (2024)
- **Key**: `Kuramoto2024`
- **Title**: MMX-era review of Martian satellite origin scenarios
- **Journal**: Space Science Reviews (in press)
- **使用箇所**: 総説・シナリオ整理
- **主張**:
  - 捕獲 vs 衝突仮説の観測要件整理
  - gas-poor vs gas-rich の位置付け

---

## 2. 放射圧・Blow-out・デブリディスク物理

放射圧による粒子排出（blow-out）とデブリディスクの力学を扱う論文群。
**Analysis参照**: `analysis/equations.md` (E.012–E.014) の β・blow-out、(E.006) の Wyatt 型 t_coll、(E.015–E.017, E.028, E.031) の遮蔽・Φ を参照。

### Strubbe & Chiang (2006) ⭐⭐
- **Key**: `StrubbeChiang2006_ApJ648_652`
- **Title**: Dust Dynamics, Surface Brightness Profiles, and Thermal Spectra of Debris Disks: The Case of AU Mic
- **Journal**: ApJ, 648, 652–665
- **DOI**: [10.1086/505736](https://doi.org/10.1086/505736)
- **使用箇所**: `radiation.beta()`, `radiation.blowout_radius()`, `surface.wyatt_tcoll_S1()`
- **コード引用**: ✅ `[@StrubbeChiang2006_ApJ648_652]`
- **数式**: E.006 (衝突時間)
- **主張**:
  - 衝突時間と Type A/B レジームの参照源（t_coll は E.006 を採用）
  - β 閾値 0.5 の根拠（E.013, E.014 と整合）
  - **gas-poor 標準設定の主要参照文献**

### Burns et al. (1979)
- **Key**: `Burns1979_Icarus40_1`
- **Title**: Radiation forces on small particles in the solar system
- **Journal**: Icarus, 40, 1–48
- **DOI**: [10.1016/0019-1035(79)90050-2](https://doi.org/10.1016/0019-1035(79)90050-2)
- **使用箇所**: β(s) 基本定義
- **主張**:
  - 放射圧/重力比 β の古典的定義
  - Q_pr と blow-out サイズの関係

### Wyatt (2008)
- **Key**: `Wyatt2008`
- **Title**: Evolution of Debris Disks
- **Journal**: ARA&A, 46, 339–383
- **DOI**: [10.1146/annurev.astro.45.051806.110525](https://doi.org/10.1146/annurev.astro.45.051806.110525)
- **使用箇所**: 衝突時間スケーリング検証
- **主張**:
  - Wyatt型 t_coll スケーリング (E.006) の検証ベンチマーク
  - IMEX安定性テストの参照

### Wyatt, Clarke & Booth (2011)
- **Key**: `WyattClarkeBooth2011_CeMDA111_1`
- **Title**: Debris disk size distributions: steady state collisional evolution with Poynting-Robertson drag and other loss processes
- **Journal**: Celestial Mechanics and Dynamical Astronomy, 111, 1–28
- **DOI**: [10.1007/s10569-011-9345-3](https://doi.org/10.1007/s10569-011-9345-3)
- **使用箇所**: supply.mode実装
- **主張**:
  - サイズビンごとの供給-損失バランス方程式
  - blow-out、PR drag、衝突除去の競合による最小粒径決定
  - epsilon_mix と外部フラックスの導入テンプレート

### Krijt & Kama (2014)
- **Key**: `KrijtKama2014_AA566_L2`
- **Title**: A dearth of small particles in debris disks
- **Journal**: A&A, 566, L2
- **DOI**: [10.1051/0004-6361/201423862](https://doi.org/10.1051/0004-6361/201423862)
- **使用箇所**: gate_mode選択の動機
- **主張**:
  - 衝突研削やドラッグが blow-out より優勢な条件
  - 最小粒径の上方シフト

---

## 3. 衝突カスケード・粒径分布

衝突カスケードと粒径分布 (PSD) の理論的基盤。
**Analysis参照**: `analysis/equations.md` (E.010–E.011, E.024, E.035) の Smol/カーネル、(E.032–E.033) の破片分布を参照。

### Dohnanyi (1969)
- **Key**: `Dohnanyi1969_JGR74_2531`
- **Title**: Collisional Model of Asteroids and Their Debris
- **Journal**: J. Geophys. Res., 74, 2531–2554
- **DOI**: [10.1029/JB074i010p02531](https://doi.org/10.1029/JB074i010p02531)
- **使用箇所**: PSD基準勾配
- **主張**:
  - 定常カスケードの基準傾き（Dohnanyi slope）の出典
  - α 初期値設定の根拠

### Thébault & Augereau (2007)
- **Key**: `ThebaultAugereau2007_AA472_169`
- **Title**: Collisional processes and size distribution in spatially extended debris discs
- **Journal**: A&A, 472, 169–185
- **DOI**: [10.1051/0004-6361:20077709](https://doi.org/10.1051/0004-6361:20077709)
- **使用箇所**: wavy PSD 構造
- **主張**:
  - blow-out カットオフによる振動的 "wavy" パターン
  - 細かいビニングの必要性

### Birnstiel et al. (2011)
- **Key**: `Birnstiel2011_AA525_A11`
- **Title**: Dust size distributions in coagulation/fragmentation equilibrium: numerical solutions and analytical fits
- **Journal**: A&A, 525, A11
- **DOI**: [10.1051/0004-6361/201015228](https://doi.org/10.1051/0004-6361/201015228)
- **使用箇所**: グリッド解像度要件
- **主張**:
  - a_{i+1}/a_i ≲ 1.1–1.2 の対数間隔推奨
  - 粗いビニングは小粒子生成を抑制 → ≥40 ビン

### Krivov et al. (2006)
- **Key**: `Krivov2006_AA455_509`
- **Title**: Dust distributions in debris disks: effects of gravity, radiation pressure and collisions
- **Journal**: A&A, 455, 509–519
- **DOI**: [10.1051/0004-6361:20064907](https://doi.org/10.1051/0004-6361:20064907)
- **使用箇所**: Smoluchowskiソルバー
- **主張**:
  - nσv スタイルの衝突カーネル
  - 適応時間刻みと質量保存チェック

---

## 4. 破砕強度・衝突破壊

衝突による破壊閾値 Q*_D と破片分布の理論。
**Analysis参照**: `analysis/equations.md` (E.026, E.032–E.033) の Q*_D 補間と最大残留体分率を参照。

### Benz & Asphaug (1999) ⭐
- **Key**: `BenzAsphaug1999_Icarus142_5`
- **Title**: Catastrophic Disruptions Revisited
- **Journal**: Icarus, 142, 5–20
- **DOI**: [10.1006/icar.1999.6204](https://doi.org/10.1006/icar.1999.6204)
- **使用箇所**: `qstar.py`
- **コード引用**: ⚠️ 非正式 → `[@BenzAsphaug1999_Icarus142_5]` に統一推奨
- **主張**:
  - 玄武岩の Q*_D 係数（3, 5 km/s 衝突）

### Leinhardt & Stewart (2012) ⭐
- **Key**: `LeinhardtStewart2012_ApJ745_79`
- **Title**: Collisions between gravity-dominated bodies. I. Outcome regimes and scaling laws
- **Journal**: ApJ, 745, 79
- **DOI**: [10.1088/0004-637X/745/1/79](https://doi.org/10.1088/0004-637X/745/1/79)
- **使用箇所**: `qstar.py`, `fragments.py`
- **コード引用**: ⚠️ 非正式 → `[@LeinhardtStewart2012_ApJ745_79]` に統一推奨
- **数式**: Q*_D(s, ρ, v) 補間
- **主張**:
  - 強度支配 ↔ 重力支配の遷移スケーリング則

### Stewart & Leinhardt (2009)
- **Key**: `StewartLeinhardt2009_ApJ691_L133`
- **Title**: Velocity-dependent catastrophic disruption criteria for planetesimals
- **Journal**: ApJ, 691, L133–L137
- **DOI**: [10.1088/0004-637X/691/2/L133](https://doi.org/10.1088/0004-637X/691/2/L133)
- **使用箇所**: F2 破片モデル
- **主張**:
  - Q_R に基づく最大残留体分率の枝分け根拠（破片分布は (E.032–E.033) へ委譲）

---

## 5. 速度分散・相対速度

衝突速度と速度分散の計算根拠。
**Analysis参照**: `analysis/equations.md` (E.020–E.022) の相対速度・c_eq・e ダンピングを参照。

### Ohtsuki et al. (2002)
- **Key**: `Ohtsuki2002_Icarus155_436`
- **Title**: Evolution of Planetesimal Velocities Based on Three-Body Orbital Integrations and Growth of Protoplanets
- **Journal**: Icarus, 155, 436–453
- **DOI**: [10.1006/icar.2001.6741](https://doi.org/10.1006/icar.2001.6741)
- **使用箇所**: c_eq 固定点反復
- **主張**:
  - レイリー近似の相対速度式 (E.020) の出典
  - 衝突冷却 vs シア加熱のスケール比較

### Lissauer & Stewart (1993)
- **Key**: `LissauerStewart1993_PP3`
- **Title**: Growth of Planets from Planetesimals
- **Journal**: Protostars and Planets III (eds. Levy & Lunine)
- **Publisher**: University of Arizona Press
- **ISBN**: 0-8165-1334-1
- **使用箇所**: 相対速度スケーリング
- **主張**:
  - Rayleigh分布を仮定した相対速度スケーリングの根拠 (E.020)

### Wetherill & Stewart (1993)
- **Key**: `WetherillStewart1993_Icarus106_190`
- **Title**: Formation of planetary embryos: efficiencies of accretion and fragmentation
- **Journal**: Icarus, 106, 190–209
- **DOI**: [10.1006/icar.1993.1161](https://doi.org/10.1006/icar.1993.1161)
- **使用箇所**: 衝突率計算
- **主張**:
  - 低 e, i での衝突率スケール設定の参照

---

## 6. 粘性進化・リング力学

ロッシュ限界内の円盤粘性拡散と衛星形成。
**Analysis参照**: C5 拡張の位置づけは `analysis/overview.md` の粘性拡散節を参照。

### Crida & Charnoz (2012) ⭐
- **Key**: `CridaCharnoz2012_Science338_1196`
- **Title**: Formation of Regular Satellites from Ancient Massive Rings
- **Journal**: Science, 338, 1196–1199
- **DOI**: [10.1126/science.1226477](https://doi.org/10.1126/science.1226477)
- **使用箇所**: `viscosity.step_viscous_diffusion_C5()`
- **コード引用**: ✅ `[@CridaCharnoz2012_Science338_1196]`
- **主張**:
  - 遅い拡散 → 複数衛星列
  - 速い拡散 → 単一主衛星

### Salmon & Canup (2010)
- **Key**: `SalmonCanup2010_Icarus208_33`
- **Title**: Long-term and large-scale viscous evolution of dense planetary rings
- **Journal**: Icarus, 208, 33–48
- **DOI**: [10.1016/j.icarus.2010.05.030](https://doi.org/10.1016/j.icarus.2010.05.030)
- **使用箇所**: 粘性拡散モデル
- **主張**:
  - 高密度リングの粘性拡散スケーリングと時間尺度の出典
  - Σ(r) 初期条件と拡散時間

### Salmon & Canup (2012)
- **Key**: `SalmonCanup2012_ApJ760_83`
- **Title**: Lunar accretion from a Roche-interior fluid disk
- **Journal**: ApJ, 760, 83
- **DOI**: [10.1088/0004-637X/760/1/83](https://doi.org/10.1088/0004-637X/760/1/83)
- **使用箇所**: Σ(r) 設定
- **主張**:
  - 円盤質量 → 衛星形成フラックスの関係

---

## 7. 昇華・蒸気圧

高温円盤での昇華損失の熱化学的基盤。
**Analysis参照**: `analysis/equations.md` (E.018–E.019, E.036–E.038) の HKL フラックス・蒸気圧・シンク尺度を参照。

### Fegley & Schaefer (2012)
- **Key**: `FegleySchaefer2012_arXiv`
- **Title**: Chemistry of impact-generated silicate vapors (MAGMA calculations)
- **Journal**: arXiv
- **使用箇所**: HKL液体枝
- **主張**:
  - 溶融SiO₂の平衡蒸気圧フィット（HKL 液体枝、(E.018) に集約）

### Visscher & Fegley (2013)
- **Key**: `VisscherFegley2013_ApJL767_L12`
- **Title**: Chemistry of Impact-Generated Silicate Melt-Vapor Debris Disks
- **Journal**: ApJL, 767, L12
- **DOI**: [10.1088/2041-8205/767/1/L12](https://doi.org/10.1088/2041-8205/767/1/L12)
- **使用箇所**: HKL液体枝の独立検証
- **主張**:
  - 溶融SiO₂蒸気圧フィットの追試（HKL 液体枝の係数確認）
  - SiO 支配の蒸気組成とクラウジウス型近似の妥当性を示す

### Visscher & Fegley (2013, arXiv)
- **Key**: `VisscherFegley2013_arXiv`
- **Title**: Chemistry of impact-generated silicate melt-vapor debris disks
- **Journal**: arXiv:1303.3905
- **使用箇所**: ApJL 版の予備・閲覧用
- **主張**:
  - ApJL 掲載版と同一内容のプレプリント

---

## 8. 光学特性・Mie理論

粒子の吸収・散乱効率とプランク平均の理論。
**Analysis参照**: `analysis/equations.md` (E.004–E.005, E.039) の ⟨Q_pr⟩ 補間・テーブル読込を参照。

### Bohren & Huffman (1983)
- **Key**: `BohrenHuffman1983_Wiley`
- **Title**: Absorption and Scattering of Light by Small Particles
- **Publisher**: Wiley
- **ISBN**: 0-471-05772-X
- **使用箇所**: Q_abs, Q_pr テーブル生成の理論基盤
- **主張**:
  - Mie理論による Q_abs(λ,a) 計算式
  - プランク平均効率の定義


### Blanco et al. (1976)
- **Key**: `Blanco1976_ApSS41_447`
- **Title**: Planck mean efficiency factors for six material candidates for interstellar grains
- **Journal**: Ap&SS, 41, 447–463
- **DOI**: [10.1007/BF00640752](https://doi.org/10.1007/BF00640752)
- **使用箇所**: Q_abs テーブル参照値
- **主張**:
  - 複数組成のプランク平均 Q_abs テーブル

### Draine (2003)
- **Key**: `Draine2003_SaasFee32`
- **Title**: Astrophysics of Dust in Cold Clouds
- **Journal**: Saas-Fee Advanced Course 32 (The Cold Universe)
- **DOI**: [10.48550/arXiv.astro-ph/0304488](https://doi.org/10.48550/arXiv.astro-ph/0304488)
- **使用箇所**: 光学定数
- **主張**:
  - 天文学的シリケイト/グラファイトの Q_abs データ


### Hocuk et al. (2017)
- **Key**: `Hocuk2017_AA604_A58`
- **Title**: Parameterizing the interstellar dust temperature
- **Journal**: A&A, 604, A58
- **DOI**: [10.1051/0004-6361/201629944](https://doi.org/10.1051/0004-6361/201629944)
- **使用箇所**: ⟨Q_abs⟩ パラメタリゼーション
- **主張**:
  - サイズ・組成依存の温度フィット

---

## 9. 輻射輸送・遮蔽

光学的深さと遮蔽効果の計算。
**Analysis参照**: `analysis/equations.md` (E.015–E.017, E.028, E.031) の Φ 適用と τ=1 クリップを参照。

### Chandrasekhar (1960)
- **Key**: `Chandrasekhar1960_RadiativeTransfer`
- **Title**: Radiative Transfer
- **Publisher**: Dover Publications
- **ISBN**: 978-0-486-60590-6
- **使用箇所**: τ≈1 光球面クリッピングの背景
- **主張**:
  - 有効光球面を τ≈1 とみなす古典的扱い（E.017 の基盤）


### Joseph et al. (1976)
- **Key**: `Joseph1976_JAS33_2452`
- **Title**: The delta-Eddington approximation for radiative flux transfer
- **Journal**: J. Atmos. Sci., 33, 2452–2459
- **DOI**: [10.1175/1520-0469(1976)033<2452:TDEAFR>2.0.CO;2](https://doi.org/10.1175/1520-0469(1976)033<2452:TDEAFR>2.0.CO;2)
- **使用箇所**: Φ(τ,ω₀,g) テーブル
- **主張**:
  - Delta-Eddington 近似のフラックス解

### Hansen & Travis (1974)
- **Key**: `HansenTravis1974_SSR16_527`
- **Title**: Light scattering in planetary atmospheres
- **Journal**: Space Science Reviews, 16, 527–610
- **DOI**: [10.1007/BF00168069](https://doi.org/10.1007/BF00168069)
- **使用箇所**: Φ テーブル生成
- **主張**:
  - Henyey-Greenstein 位相関数による多重散乱

### Cogley & Bergstrom (1979)
- **Key**: `CogleyBergstrom1979_JQSRT22_267`
- **Title**: Numerical results for the thermal scattering functions
- **Journal**: J. Quant. Spectrosc. Radiat. Transf., 22, 267–280
- **DOI**: [10.1016/0022-4073(79)90017-7](https://doi.org/10.1016/0022-4073(79)90017-7)
- **使用箇所**: Φ(τ,ω₀,g) 数値テーブル
- **主張**:
  - 高光学的厚さでの直達光透過飽和を定量化

---

## 10. 相転移・SiO₂物性

SiO₂ の相転移温度と物性パラメータ。
**Analysis参照**: 放射冷却と粒子温度は `analysis/equations.md` (E.042–E.043) を参照。

### Bruning (2003)
- **Key**: `Bruning2003_JNCS330_13`
- **Title**: On the glass transition in vitreous silica by differential thermal analysis measurements
- **Journal**: Journal of Non-Crystalline Solids, 330, 13–22
- **DOI**: [10.1016/j.jnoncrysol.2003.08.051](https://doi.org/10.1016/j.jnoncrysol.2003.08.051)
- **使用箇所**: T_glass ≈ 1475 K
- **主張**:
  - ガラス転移開始 ~1247 K、緩和 ~1475 K

### Ojovan (2021)
- **Key**: `Ojovan2021_Materials14_5235`
- **Title**: On Structural Rearrangements Near the Glass Transition Temperature in Amorphous Silica
- **Journal**: Materials, 14, 5235
- **DOI**: [10.3390/ma14185235](https://doi.org/10.3390/ma14185235)
- **使用箇所**: SiO₂ 融点
- **主張**:
  - 低圧での融点 ~1986 K

### Melosh (2007)
- **Key**: `Melosh2007_MPS42_2079`
- **Title**: A Hydrocode Equation of State for SiO2
- **Journal**: Meteoritics & Planetary Science, 42, 2079–2098
- **DOI**: [10.1111/j.1945-5100.2007.tb01009.x](https://doi.org/10.1111/j.1945-5100.2007.tb01009.x)
- **使用箇所**: SiO₂ 状態方程式
- **主張**:
  - ~2000 K での溶融/蒸気境界

### Lesher & Spera (2015)
- **Key**: `LesherSpera2015_EncyclopediaVolcanoes`
- **Title**: Thermodynamic and Transport Properties of Silicate Melts and Magma
- **Journal**: The Encyclopedia of Volcanoes, 2nd ed., 113–141
- **使用箇所**: 熱物性パラメータ
- **主張**:
  - ρ ≈ 2600 kg/m³、c_p ≈ 1450 J/(kg·K)、k ≈ 0.6 W/(m·K)

### Robertson (1988)
- **Key**: `Robertson1988_USGS_OFR88_441`
- **Title**: Thermal Properties of Rocks
- **Publisher**: U.S. Geological Survey, Open-File Report 88-441
- **使用箇所**: 熱容量
- **主張**:
  - 玄武岩〜超苦鉄質岩の ρ, c_p

---

## 11. 軌道力学・基礎

ケプラー運動と軌道パラメータの標準参照。
**Analysis参照**: `analysis/equations.md` (E.001–E.003) の v_K・Ω 定義を参照。

### Murray & Dermott (1999)
- **Key**: `MurrayDermott1999_SSD`
- **Title**: Solar System Dynamics
- **Publisher**: Cambridge University Press
- **DOI**: [10.1017/CBO9781139174817](https://doi.org/10.1017/CBO9781139174817)
- **使用箇所**: v_K, Ω の定義（E.001–E.002）
- **主張**:
  - ケプラー速度・角速度の標準式の参照元（E.001–E.002）

---

## 12. ガスドラッグ・大気捕獲

（gas-poor 標準では無効化されているが、感度試験用に参照）
**Analysis参照**: gas-rich 感度や TL2003 トグルの位置づけは `analysis/overview.md` と `analysis/equations.md` (E.028) の遮蔽テーブル読込節を参照。

### Takeuchi & Lin (2002)
- **Key**: `TakeuchiLin2002_ApJ581_1344`
- **Title**: Radial Flow of Dust Particles in Accretion Disks
- **Journal**: ApJ, 581, 1344–1355
- **DOI**: [10.1086/344437](https://doi.org/10.1086/344437)
- **使用箇所**: TL2003の前提
- **主張**:
  - ガスドラッグによる半径方向ドリフト

### Takeuchi & Lin (2003)
- **Key**: `TakeuchiLin2003_ApJ593_524`
- **Title**: Surface Outflow in Optically Thick Dust Disks by Radiation Pressure
- **Journal**: ApJ, 593, 524–533
- **DOI**: [10.1086/376496](https://doi.org/10.1086/376496)
- **使用箇所**: ALLOW_TL2003=true 時のみ
- **主張**:
  - 光学的に厚いガス円盤表層での外向きフロー
  - **gas-poor 標準では適用しない**

### Pollack, Burns & Tauber (1979)
- **Key**: `PollackBurnsTauber1979_Icarus37_587`
- **Title**: Gas drag in primordial circumplanetary envelopes
- **Journal**: Icarus, 37, 587–611
- **DOI**: [10.1016/0019-1035(79)90016-2](https://doi.org/10.1016/0019-1035(79)90016-2)
- **使用箇所**: ガスドラッグ上限
- **主張**:
  - 空気力学的捕獲に必要な高ガス密度

### Hunten (1979)
- **Key**: `Hunten1979_Icarus37_113`
- **Title**: Capture of Phobos and Deimos by protoatmospheric drag
- **Journal**: Icarus, 37, 113–123
- **DOI**: [10.1016/0019-1035(79)90119-2](https://doi.org/10.1016/0019-1035(79)90119-2)
- **使用箇所**: ガスドラッグ感度試験
- **主張**:
  - 高密度原始大気でのみ捕獲可能

### Olofsson et al. (2022)
- **Key**: `Olofsson2022_MNRAS513_713`
- **Title**: The vertical structure of debris discs and the impact of gas
- **Journal**: MNRAS, 513, 713–731
- **DOI**: [10.1093/mnras/stac455](https://doi.org/10.1093/mnras/stac455)
- **使用箇所**: enable_gas_drag=false の根拠
- **主張**:
  - 低ガス密度ではドラッグ時間 > 衝突時間

### Shadmehri (2008)
- **Key**: `Shadmehri2008_ApSS314_217`
- **Title**: Dynamics of charged dust particles in protoplanetary discs
- **Journal**: Ap&SS, 314, 217–223
- **DOI**: [10.1007/s10509-008-9762-2](https://doi.org/10.1007/s10509-008-9762-2)
- **使用箇所**: TL2002/TL2003 のレビュー
- **主張**:
  - 外向き表層ドリフトは光学的に厚いガス円盤に限定

### Estrada & Durisen (2015)
- **Key**: `EstradaDurisen2015_Icarus252_415`
- **Title**: Combined structural and compositional evolution of planetary rings due to micrometeoroid impacts and ballistic transport
- **Journal**: Icarus, 252, 415–439
- **DOI**: [10.1016/j.icarus.2015.02.005](https://doi.org/10.1016/j.icarus.2015.02.005)
- **使用箇所**: epsilon_mix
- **主張**:
  - 弾道輸送による混合効率

### Cuzzi & Estrada (1998)
- **Key**: `CuzziEstrada1998_Icarus132_1`
- **Title**: Compositional Evolution of Saturn's Rings Due to Meteoroid Bombardment
- **Journal**: Icarus, 132, 1–35
- **DOI**: [10.1006/icar.1997.5863](https://doi.org/10.1006/icar.1997.5863)
- **使用箇所**: 外部フラックス
- **主張**:
  - 隕石供給と再分配係数

---

## BibTeX エクスポート

論文執筆用の BibTeX ファイルを生成するには：

```bash
python -m tools.reference_tracker export-bibtex -o paper/references.bib
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2025-12-11 | ISBN/DOI 情報の補完、重複行の削除、PDF との整合性確認 |
| 2025-12-09 | 初版作成。references.registry.json の全49件を網羅 |

---

## 凡例

- ⭐ = コードで `[@Key]` 形式で明示的に引用されている文献
- ⭐⭐ = 複数モジュールで中核的に参照される最重要文献
- ⚠️ = 非正式引用（`Author et al.` 形式）→ 正式化推奨
