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

### Rosenblatt (2011)
- **Key**: `Rosenblatt2011_ApARv19_44`
- **Title**: The origin of the Martian moons revisited
- **Journal**: Astron. Astrophys. Rev., 19, 44
- **DOI**: [10.1007/s00159-011-0044-6](https://doi.org/10.1007/s00159-011-0044-6)
- **使用箇所**: 起源仮説の総説整理
- **主張**:
  - 捕獲説と巨大衝突説の整理と観測制約の概観

### Rosenblatt & Charnoz (2012)
- **Key**: `Rosenblatt2012_Icarus221_806`
- **Title**: On the formation of the martian moons from a circum-martian accretion disk
- **Journal**: Icarus, 221, 806–815
- **DOI**: [10.1016/j.icarus.2012.09.009](https://doi.org/10.1016/j.icarus.2012.09.009)
- **使用箇所**: 火星衛星形成の円盤進化モデルの背景整理
- **主張**:
  - ロッシュ限界内円盤の粘性拡散と衛星形成の関係を整理
  - 初期円盤条件の違いが形成効率に影響することを示す

### Citron et al. (2015)
- **Key**: `Citron2015_Icarus252_334`
- **Title**: Formation of Phobos and Deimos via a giant impact
- **Journal**: Icarus, 252, 334–338
- **DOI**: [10.1016/j.icarus.2015.02.011](https://doi.org/10.1016/j.icarus.2015.02.011)
- **使用箇所**: 火星衛星巨大衝突起源の補強文献
- **主張**:
  - 巨大衝突由来の周回円盤から小衛星が形成されるシナリオを提示
  - ディスク質量と角運動量の制約を整理

### Rosenblatt et al. (2016)
- **Key**: `Rosenblatt2016_NatGeo9_8`
- **Title**: Accretion of Phobos and Deimos in an extended debris disc stirred by transient moons
- **Journal**: Nature Geoscience, 9, 581–583
- **DOI**: [10.1038/ngeo2742](https://doi.org/10.1038/ngeo2742)
- **使用箇所**: 外側ディスク攪乱シナリオの参照
- **主張**:
  - 一時的に形成された内側衛星が外側デブリを攪乱して小衛星を成長させる
  - 拡張ディスクモデルがPhobos/Deimosの形成に有効であることを示す

### Canup & Salmon (2018)
- **Key**: `CanupSalmon2018_SciAdv4_eaar6887`
- **Title**: Origin of Phobos and Deimos by the impact of a Vesta-to-Ceres-sized body with Mars
- **Journal**: Science Advances, 4, eaar6887
- **DOI**: [10.1126/sciadv.aar6887](https://doi.org/10.1126/sciadv.aar6887)
- **使用箇所**: gas-poor標準設定の根拠
- **主張**:
  - M_disk ≤ 3×10⁻⁵ M_Mars かつ Q/k₂ < 80 で小衛星生存
  - 低質量・低ガス円盤の必要性

### Rosenblatt et al. (2019)
- **Key**: `Rosenblatt2019_arXiv`
- **Title**: The formation of the Martian moons
- **Journal**: arXiv
- **Online**: [arXiv:1909.03996](https://arxiv.org/abs/1909.03996)
- **使用箇所**: 火星衛星形成の総説
- **主張**:
  - 捕獲 vs 巨大衝突のシナリオ整理と観測制約の概観
  - 巨大衝突起源ディスクの進化シナリオをまとめる

### Kuramoto (2024)
- **Key**: `Kuramoto2024`
- **Title**: Origin of Phobos and Deimos Awaiting Direct Exploration
- **Journal**: Annual Review of Earth and Planetary Sciences, 52, 495–519
- **DOI**: [10.1146/annurev-earth-031621-064742](https://doi.org/10.1146/annurev-earth-031621-064742)
- **使用箇所**: 総説・シナリオ整理
- **主張**:
  - 捕獲 vs 衝突仮説の観測要件整理
  - gas-poor vs gas-rich の位置付け

### Fraeman et al. (2012)
- **Key**: `Fraeman2012_JGR117_E00J15`
- **Title**: Analysis of disk-resolved OMEGA and CRISM spectral observations of Phobos and Deimos
- **Journal**: J. Geophys. Res. Planets, 117, E00J15
- **DOI**: [10.1029/2012JE004137](https://doi.org/10.1029/2012JE004137)
- **使用箇所**: VIS-NIR 反射スペクトル・2.8 um 帯の弱吸収
- **主張**:
  - CRISM/OMEGA の反射スペクトルを整理し、弱い吸収帯と赤いスペクトル傾斜を報告

### Fraeman et al. (2014)
- **Key**: `Fraeman2014_Icarus229_196`
- **Title**: Spectral absorptions on Phobos and Deimos in the visible/near infrared wavelengths and their compositional constraints
- **Journal**: Icarus, 229, 196–205
- **DOI**: [10.1016/j.icarus.2013.11.021](https://doi.org/10.1016/j.icarus.2013.11.021)
- **使用箇所**: VIS-NIR 吸収帯の検出と組成制約
- **主張**:
  - 0.6–0.7 um と 2.8 um 付近の弱い吸収を報告し、含水鉱物の可能性を議論

### Pajola et al. (2013)
- **Key**: `Pajola2013_ApJ777_127`
- **Title**: Phobos as a D-type captured asteroid, spectral modeling from 0.25 to 4.0 microns
- **Journal**: ApJ, 777, 127
- **DOI**: [10.1088/0004-637X/777/2/127](https://doi.org/10.1088/0004-637X/777/2/127)
- **使用箇所**: D 型小惑星とのスペクトル整合
- **主張**:
  - Phobos スペクトルが D 型小惑星モデルで再現可能であることを示す

### Pieters et al. (2014)
- **Key**: `Pieters2014_PSS102_144`
- **Title**: Composition of surface materials on the moons of Mars
- **Journal**: Planetary and Space Science, 102, 144–151
- **DOI**: [10.1016/j.pss.2014.02.008](https://doi.org/10.1016/j.pss.2014.02.008)
- **使用箇所**: 低アルベド・スペクトル解釈・空間風化の整理
- **主張**:
  - 低アルベドとスペクトル解釈の不確かさを整理し、空間風化の影響を議論

### Andert et al. (2010)
- **Key**: `Andert2010_GRL37_9`
- **Title**: Precise mass determination and the nature of Phobos
- **Journal**: Geophysical Research Letters, 37(9)
- **DOI**: [10.1029/2009GL041829](https://doi.org/10.1029/2009GL041829)
- **使用箇所**: Phobos の低密度・高空隙率の根拠
- **主張**:
  - 追跡データから Phobos の低密度を示し、内部の高空隙率を示唆

### Giuranna et al. (2011)
- **Key**: `Giuranna2011_PSS59_1308`
- **Title**: Compositional interpretation of PFS/MEx and TES/MGS thermal infrared spectra of Phobos
- **Journal**: Planetary and Space Science, 59, 1308–1325
- **DOI**: [10.1016/j.pss.2011.01.019](https://doi.org/10.1016/j.pss.2011.01.019)
- **使用箇所**: MID-IR 放射率スペクトルの解釈
- **主張**:
  - 炭素質隕石と一致しない放射率を示し、シリケート成分を示唆

### Glotch et al. (2018)
- **Key**: `Glotch2018_JGRPlanets123_2467`
- **Title**: MGS-TES spectra suggest a basaltic component in the regolith of Phobos
- **Journal**: J. Geophys. Res. Planets, 123, 2467–2484
- **DOI**: [10.1029/2018JE005647](https://doi.org/10.1029/2018JE005647)
- **使用箇所**: MID-IR 放射率の玄武岩成分の根拠
- **主張**:
  - TES スペクトルに玄武岩成分が含まれる可能性を示す

### Kuzmin & Zabalueva (2003)
- **Key**: `KuzminZabalueva2003_SSR37_480`
- **Title**: The temperature regime of the surface layer of the Phobos regolith in the region of the potential Fobos-Grunt space station landing site
- **Journal**: Solar System Research, 37, 480–488
- **DOI**: [10.1023/b:sols.0000007946.02888.bd](https://doi.org/10.1023/b:sols.0000007946.02888.bd)
- **使用箇所**: 低熱慣性・表層温度の根拠
- **主張**:
  - Phobos 表層の温度・熱慣性が低いことを示す

### Wada et al. (2018)
- **Key**: `Wada2018_PEPS5_82`
- **Title**: Asteroid Ryugu before the Hayabusa2 encounter
- **Journal**: Progress in Earth and Planetary Science, 5, 82
- **DOI**: [10.1186/s40645-018-0237-y](https://doi.org/10.1186/s40645-018-0237-y)
- **使用箇所**: 熱慣性と粒径の関係（細粒レゴリス）
- **主張**:
  - 低熱慣性がサブミリ粒径のレゴリスと整合することを示す

### Thomas (1989)
- **Key**: `Thomas1989_Icarus77_248`
- **Title**: The shapes of small satellites
- **Journal**: Icarus, 77, 248–274
- **DOI**: [10.1016/0019-1035(89)90089-4](https://doi.org/10.1016/0019-1035(89)90089-4)
- **使用箇所**: 小衛星の形状・不規則形状の根拠
- **主張**:
  - 小衛星の不規則形状と形状パラメータを整理

### Hu et al. (2020)
- **Key**: `Hu2020_GRL47_e2019GL085958`
- **Title**: Equipotential figure of Phobos suggests its late accretion near 3.3 Mars radii
- **Journal**: Geophysical Research Letters, 47, e2019GL085958
- **DOI**: [10.1029/2019GL085958](https://doi.org/10.1029/2019GL085958)
- **使用箇所**: ロシュ限界近傍での集積形状の根拠
- **主張**:
  - Phobos の形状が 3.3 R_M 近傍の等ポテンシャル形状と整合することを示す

---

## 2. 放射圧・Blow-out・デブリディスク物理

放射圧による粒子排出（blow-out）とデブリディスクの力学を扱う論文群。
**Analysis参照**: `analysis/equations.md` (E.012–E.014) の β・blow-out、(E.006) の Wyatt 型 t_coll を参照。遮蔽・Φ は §9 で整理。

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

### Kimura et al. (2002)
- **Key**: `KimuraOkamotoMukai2002_Icarus157_349`
- **Title**: Radiation Pressure and the Poynting–Robertson Effect for Fluffy Dust Particles
- **Journal**: Icarus, 157, 349–361
- **DOI**: [10.1006/icar.2002.6849](https://doi.org/10.1006/icar.2002.6849)
- **使用箇所**: β の材質・構造依存の根拠
- **主張**:
  - ポーラス粒子の放射圧/PR 効果を整理し、β の粒径依存を示す

### Pawellek & Krivov (2015)
- **Key**: `PawellekKrivov2015_MNRAS454_3207`
- **Title**: The dust grain size–stellar luminosity trend in debris discs
- **Journal**: MNRAS, 454, 3207–3221
- **DOI**: [10.1093/mnras/stv2142](https://doi.org/10.1093/mnras/stv2142)
- **使用箇所**: β=0.5 を用いた a_blow 計算と Q_pr テーブル適用の実装例
- **主張**:
  - Burns 式 (β=0.5) と Q_pr を用いた blow-out 粒径の評価を観測と付き合わせ、星光度と最小粒径の関係を示す
  - デブリ円盤の下限粒径が β=0.5 境界で決まることを実装レベルで示した実例

### Wyatt (2008)
- **Key**: `Wyatt2008`
- **Title**: Evolution of Debris Disks
- **Journal**: ARA&A, 46, 339–383
- **DOI**: [10.1146/annurev.astro.45.051806.110525](https://doi.org/10.1146/annurev.astro.45.051806.110525)
- **使用箇所**: 衝突時間スケーリング検証
- **主張**:
  - Wyatt型 t_coll スケーリング (E.006) の検証ベンチマーク
  - IMEX安定性テストの参照

### Krivov (2010)
- **Key**: `Krivov2010_arXiv`
- **Title**: Debris Disks: Seeing Dust, Thinking of Planetesimals and Planets
- **Journal**: arXiv
- **Online**: [arXiv:1003.5229](https://arxiv.org/abs/1003.5229)
- **使用箇所**: デブリ円盤の総説（衝突カスケードとブローアウトの一般論）
- **主張**:
  - 衝突カスケードと放射圧ブローアウトの基本的枠組みを整理
  - 最小粒径近傍のカットオフがPSD形状に影響することを概説

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

### Thébault et al. (2003)
- **Key**: `Thebault2003_AA408_775`
- **Title**: Dust production from collisions in extrasolar planetary systems
- **Journal**: A&A, 408, 775–788
- **DOI**: [10.1051/0004-6361:20031017](https://doi.org/10.1051/0004-6361:20031017)
- **使用箇所**: Smoluchowski 実装の参照文脈、衝突・破砕・エネルギー簿記の背景
- **主張**:
  - 衝突カスケードの定式化と破砕・侵食の分類指標
  - デブリディスクにおける粒径分布の時間発展

### Thébault & Augereau (2007)
- **Key**: `ThebaultAugereau2007_AA472_169`
- **Title**: Collisional processes and size distribution in spatially extended debris discs
- **Journal**: A&A, 472, 169–185
- **DOI**: [10.1051/0004-6361:20077709](https://doi.org/10.1051/0004-6361:20077709)
- **使用箇所**: wavy PSD 構造
- **主張**:
  - blow-out カットオフによる振動的 "wavy" パターン
  - 細かいビニングの必要性

### Campo Bagatin et al. (1994)
- **Key**: `CampoBagatin1994_PSS42_1079`
- **Title**: Wavy size distributions for collisional systems with a small-size cutoff
- **Journal**: Planet. Space Sci., 42, 1079–1092
- **DOI**: [10.1016/0032-0633(94)90008-6](https://doi.org/10.1016/0032-0633(94)90008-6)
- **使用箇所**: wavy PSD の基本根拠
- **主張**:
  - 最小サイズのカットオフが PSD の波状構造を生むことを示す

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

### Ida & Makino (1992)
- **Key**: `IdaMakino1992_Icarus96_107`
- **Title**: N-body simulation of gravitational interaction between planetesimals and a protoplanet
- **Journal**: Icarus, 96, 107–120
- **DOI**: [10.1016/0019-1035(92)90008-U](https://doi.org/10.1016/0019-1035(92)90008-U)
- **使用箇所**: 相対速度の $e$–$i$ 関係（$\langle e^{2}\rangle=2\langle i^{2}\rangle$）の仮定根拠
- **主張**:
  - 低 e, i 系での速度分散関係の採用根拠

### Lissauer & Stewart (1993)
- **Key**: `LissauerStewart1993_PP3`
- **Title**: Growth of Planets from Planetesimals
- **Journal**: Protostars and Planets III (eds. Levy & Lunine)
- **Publisher**: University of Arizona Press
- **ISBN**: 0-8165-1334-1
- **使用箇所**: 相対速度スケーリング
- **主張**:
  - Rayleigh分布を仮定した相対速度スケーリングの根拠 (E.020)

### Mustill & Wyatt (2009)
- **Key**: `MustillWyatt2009_MNRAS399_1403`
- **Title**: Debris disc stirring by secular perturbations from giant planets
- **Journal**: MNRAS, 399, 1403–1414
- **DOI**: [10.1111/j.1365-2966.2009.15360.x](https://doi.org/10.1111/j.1365-2966.2009.15360.x)
- **使用箇所**: 相対速度係数 c の補助根拠
- **主張**:
  - レイリー分布の相対速度で c=√(5/4) を採用する根拠

### Wetherill & Stewart (1993)
- **Key**: `WetherillStewart1993_Icarus106_190`
- **Title**: Formation of planetary embryos: efficiencies of accretion and fragmentation
- **Journal**: Icarus, 106, 190–209
- **DOI**: [10.1006/icar.1993.1161](https://doi.org/10.1006/icar.1993.1161)
- **Online**: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S001910358371161X)
- **使用箇所**: 衝突率計算
- **主張**:
  - 低 e, i での衝突率スケール設定の参照

### Imaz Blanco et al. (2023)
- **Key**: `ImazBlanco2023_MNRAS522_6150`
- **Title**: Inner edges of planetesimal belts: collisionally eroded or truncated?
- **Journal**: MNRAS, 522, 6150–6169
- **DOI**: [10.1093/mnras/stad1221](https://doi.org/10.1093/mnras/stad1221)
- **使用箇所**: 相対速度スケーリングの係数 1.25 の採用例 (E.020)
- **主張**:
  - 衝突進化による内縁位置の再評価
  - 低 e, i 系での相対速度近似の採用例

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

### Charnoz et al. (2011)
- **Key**: `CharnozCridaCastilloRogez2011_Icarus216_535`
- **Title**: Accretion of Saturn's mid-sized moons during the viscous spreading of young massive rings: Solving the paradox of silicate-poor rings versus silicate-rich moons
- **Journal**: Icarus, 216, 535–550
- **DOI**: [10.1016/j.icarus.2011.09.017](https://doi.org/10.1016/j.icarus.2011.09.017)
- **使用箇所**: ロッシュ限界内リング拡散の比較事例
- **主張**:
  - 高密度リングの粘性拡散が衛星形成を駆動する
  - リング組成と生成衛星の組成差の解釈を提示

### Salmon, Charnoz & Brahic (2010)
- **Key**: `SalmonCharnozBrahic2010_Icarus209_771`
- **Title**: Long-term and large-scale viscous evolution of dense planetary rings
- **Journal**: Icarus, 209, 771–785
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
- **Online**: [arXiv:1303.3905](https://arxiv.org/abs/1303.3905)
- **使用箇所**: HKL液体枝
- **主張**:
  - 溶融SiO₂の平衡蒸気圧フィット（HKL 液体枝、(E.018) に集約）

### Schaefer & Fegley (2004)
- **Key**: `SchaeferFegley2004_Icarus169_216`
- **Title**: A thermodynamic model of high temperature lava vaporization on Io
- **Journal**: Icarus, 169, 216–241
- **DOI**: [10.1016/j.icarus.2003.08.023](https://doi.org/10.1016/j.icarus.2003.08.023)
- **使用箇所**: `docs/plan/20260102_basalt_unified_mode_plan.md` の HKL 候補（Table 7/10 の適用範囲整理）
- **主張**:
  - MAGMA コードで溶融物-蒸気平衡を計算し、1700–2400 K の蒸気圧・組成を評価
  - SiO など主要ガス種の温度依存性を示す

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

### Markkanen & Agarwal (2020)
- **Key**: `Markkanen2020_AA643_A16`
- **Title**: Thermophysical model for icy cometary dust particles
- **Journal**: A&A, 643, A16
- **DOI**: [10.1051/0004-6361/202039092](https://doi.org/10.1051/0004-6361/202039092)
- **使用箇所**: ヘルツ＝クヌーセン型昇華フラックスと昇華駆動の質量損失の例
- **主張**:
  - Hertz-Knudsen 式を熱収支と結合し、mm–cm 粒子の昇華・破砕時間を算出
  - 昇華が支配的な場合の ds/dt 床や outflux 設定のアナログとして利用

### Kubaschewski (1974)
- **Key**: `Kubaschewski1974_Book`
- **Title**: Thermochemical data compilation (Clausius–Clapeyron coefficients)
- **Publisher**: 未確認
- **使用箇所**: Clausius 型蒸気圧係数の既定値
- **主張**:
  - SiO の Clausius 係数を与え、P_sat の既定値に利用する

### Love & Brownlee (1991)
- **Key**: `LoveBrownlee1991_Icarus89_26`
- **Title**: Heating and thermal transformation of micrometeoroids entering the Earth's atmosphere
- **Journal**: Icarus, 89, 26–43
- **DOI**: [10.1016/0019-1035(91)90085-8](https://doi.org/10.1016/0019-1035(91)90085-8)
- **使用箇所**: 固相蒸気圧のプロキシ
- **主張**:
  - log P = A − B/T の係数を micrometeoroid の近似として提示

### Genge (2017)
- **Key**: `Genge2017_MAPS52_1000`
- **Title**: The entry heating and abundances of basaltic micrometeorites
- **Journal**: Meteoritics & Planetary Science, 52, 1000–1013
- **DOI**: [10.1111/maps.12830](https://doi.org/10.1111/maps.12830)
- **使用箇所**: `docs/plan/20260102_basalt_unified_mode_plan.md` の参考文献候補
- **主張**:
  - 大気突入に伴う玄武岩質 micrometeorite の加熱過程と存在量を整理
  - 玄武岩質粒子の残存・損失議論の補助に利用

### Kimura et al. (1997)
- **Key**: `KimuraIshimotoMukai1997_AA326_263`
- **Title**: A study on solar dust ring formation based on fractal dust models
- **Journal**: A&A, 326, 263
- **使用箇所**: 固相蒸気圧の参考（silicate/carbon）
- **主張**:
  - silicate/carbon dust の昇華パラメータ整理（Eq.6 の形）

### Kobayashi et al. (2011)
- **Key**: `Kobayashi2011_EPS63_1067`
- **Title**: Sublimation temperature of circumstellar dust particles and its importance for dust ring formation
- **Journal**: Earth, Planets and Space, 63, 1067–1075
- **DOI**: [10.5047/eps.2011.03.012](https://doi.org/10.5047/eps.2011.03.012)
- **使用箇所**: 固相の昇華温度整理
- **主張**:
  - 組成別の昇華温度と温度依存の整理を提供

### Ferguson & Nuth (2012)
- **Key**: `FergusonNuth2012_JCED57_721`
- **Title**: Vapor Pressure and Evaporation Coefficient of Silicon Monoxide over a Mixture of Silicon and Silica
- **Journal**: J. Chem. Eng. Data, 57, 721–728
- **DOI**: [10.1021/je200693d](https://doi.org/10.1021/je200693d)
- **使用箇所**: 蒸発係数 α_evap の既定値
- **主張**:
  - SiO の蒸気圧と蒸発係数を実験的に評価

### Briani et al. (2013)
- **Key**: `Briani2013_arXiv`
- **Title**: Simulations of micrometeoroid interactions with the Earth atmosphere
- **Journal**: arXiv:1302.3666
- **使用箇所**: micrometeoroid 蒸気圧係数の補助
- **主張**:
  - Love & Brownlee 係数の log10 運用例を示す

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
- **DOI**: [10.1007/BF00640498](https://doi.org/10.1007/BF00640498)
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


### Lamy (1978)
- **Key**: `Lamy1978_Icarus34_68`
- **Title**: Optical Properties of Silicates in the Far Ultraviolet
- **Journal**: Icarus, 34, 68–75
- **使用箇所**: `docs/plan/20260102_basalt_unified_mode_plan.md` の UV 側 n,k 補完候補（Table II）
- **主張**:
  - 1026–1640 A の反射率と Kramers-Kronig 解析から n, k を推定
  - シリケート試料の UV 光学特性を整理

### Egan et al. (1975)
- **Key**: `Egan1975_Icarus25_344`
- **Title**: Ultraviolet complex refractive index of Martian dust: Laboratory measurements of terrestrial analogs
- **Journal**: Icarus, 25, 344–355
- **DOI**: [10.1016/0019-1035(75)90029-9](https://doi.org/10.1016/0019-1035(75)90029-9)
- **使用箇所**: 0.10 μm 未満の UV n,k 補完候補
- **主張**:
  - Martian dust の UV 屈折率（地上アナログ測定）を提供

### Pollack et al. (1973)
- **Key**: `PollackToonKhare1973_Icarus19_372`
- **Title**: Optical properties of some terrestrial rocks and glasses
- **Journal**: Icarus, 19, 372–389
- **DOI**: [10.1016/0019-1035(73)90115-2](https://doi.org/10.1016/0019-1035(73)90115-2)
- **使用箇所**: 玄武岩/玄武岩質ガラスの n,k 補完候補
- **主張**:
  - 岩石・ガラスの光学定数を可視〜中赤外で整理

### Arakawa et al. (1991)
- **Key**: `Arakawa1991_IAUC126_102`
- **Title**: Optical Constants of Basaltic Glass from 0.0173 To 50 μm
- **Journal**: IAU Colloquium 126, 102–104
- **DOI**: [10.1017/S0252921100066574](https://doi.org/10.1017/S0252921100066574)
- **使用箇所**: 玄武岩質ガラスの n,k 補完候補
- **主張**:
  - 0.0173–50 μm の光学定数を示す（数表の有無は要確認）

### Demyk et al. (2022)
- **Key**: `Demyk2022_AA666_A192`
- **Title**: Low-temperature optical constants of amorphous silicate dust analogues
- **Journal**: A&A, 666, A192
- **DOI**: [10.1051/0004-6361/202243815](https://doi.org/10.1051/0004-6361/202243815)
- **使用箇所**: `docs/plan/20260102_basalt_unified_mode_plan.md` の長波長 n,k 補完候補、`paper/STOPCODA/EXPERIMENT_KD_20220331` / `paper/STOPCODA/EXPERIMENT_KD_20220525_002` のデータ収録
- **主張**:
  - 10–300 K の光学定数を 5–800/1000 um で提供
  - 組成別の温度依存性を整理

### Hocuk et al. (2017)
- **Key**: `Hocuk2017_AA604_A58`
- **Title**: Parameterizing the interstellar dust temperature
- **Journal**: A&A, 604, A58
- **DOI**: [10.1051/0004-6361/201629944](https://doi.org/10.1051/0004-6361/201629944)
- **Online**: [A&A Open Access](https://www.aanda.org/articles/aa/abs/2017/08/aa29944-16/aa29944-16.html)
- **使用箇所**: ⟨Q_abs⟩ パラメタリゼーション
- **主張**:
  - サイズ・組成依存の温度フィット


---

## 9. 輻射輸送・遮蔽

光学的深さと遮蔽効果の計算。
**Analysis参照**: `analysis/equations.md` (E.015–E.017, E.028, E.031) の Φ 適用と τ=1 クリップを参照。

### Chandrasekhar (1960)
- **Key**: `Chandrasekhar1960_Book`
- **Title**: Radiative Transfer
- **Publisher**: 未確認
- **使用箇所**: 放射輸送の基本式（Φ テーブルの前提）
- **主張**:
  - 伝達方程式の古典的定式化を与える

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
- **Key**: `CogleyBergstrom1979_JQSRT21_265`
- **Title**: Numerical results for the thermal scattering functions
- **Journal**: J. Quant. Spectrosc. Radiat. Transf., 21, 265–276
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
| 2025-12-15 | WEB検索に基づく精度向上: Kuramoto 2024 の掲載誌、Salmon 2010 の著者、Cogley 1979 の DOI を修正 |
| 2025-12-11 | ISBN/DOI 情報の補完、重複行の削除、PDF との整合性確認 |
| 2025-12-09 | 初版作成。references.registry.json の全49件を網羅 |

---

## 凡例

- ⭐ = コードで `[@Key]` 形式で明示的に引用されている文献
- ⭐⭐ = 複数モジュールで中核的に参照される最重要文献
- ⚠️ = 非正式引用（`Author et al.` 形式）→ 正式化推奨
