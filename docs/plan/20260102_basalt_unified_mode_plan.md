# 玄武岩統一モード作成プラン（Phase 1）

> **作成日**: 2026-01-02  
> **ステータス**: 立案（未着手）  
> **対象**: 0D 標準設定（`configs/base.yml`）の物性統一

---

## 背景

現行の `configs/base.yml` は「玄武岩密度/破壊強度 × SiO2 光学 × SiO 蒸気圧」という混在状態です。  
詳細な整理は `docs/plan/20251226_material_properties_current_defaults.md` を参照。

## 目的

- **玄武岩で物性を一貫させた設定モード**を用意し、実行結果の解釈を明確化する。
- SiO2 統一モードは次フェーズに回し、まずは玄武岩モードの定義と再現性確保に集中する。

## スコープ

- 0D 標準設定（`configs/base.yml`）に対する玄武岩統一の **設定セット**を作成する。
- 物理式や数値スキームは変更しない（係数・テーブル・閾値の差し替えのみ）。

## 非スコープ

- SiO2 統一モードの実装（Phase 2）
- 物理モデルの新規追加、式の変更
- 1D 拡張や既存テストの大規模改修

---

## 玄武岩統一で揃える対象

| 物性カテゴリ | 設定キー | 玄武岩モードでの扱い |
|---|---|---|
| バルク密度 | `material.rho` | 玄武岩想定の密度で固定 |
| 破壊強度 | `qstar.*` | 玄武岩向け係数を維持 or 明示 |
| 放射圧効率 | `radiation.qpr_table_path` | 玄武岩の ⟨Q_pr⟩ テーブルへ切替 |
| 相変化閾値 | `phase.thresholds.*` | 玄武岩の固液境界に合わせて設定 |
| 吸収効率 | `phase.q_abs_mean` | 玄武岩想定値へ設定 |
| 昇華 | `sinks.sub_params.*` / `sinks.T_sub` | 玄武岩蒸気圧パラメータへ切替 |

---

## 実装方針

### 方針 A（推奨）
`configs/base.yml` に対する **overrides ファイル**を用意し、実行時に適用する。

```
python -m marsdisk.run \
  --config configs/base.yml \
  --overrides-file configs/overrides/material_basalt.override
```

**理由**: ベース設定の差分が明確になり、SiO2 モード追加時も差分管理が容易。

### 方針 B（代替）
`configs/material_basalt.yml` を新規作成し、`base.yml` 相当を複製して差分を上書きする。  
（重複が増えるため原則は方針 A を採用）

---

## 依存データ・準備タスク

1) **玄武岩 ⟨Q_pr⟩ テーブルの生成**
- 既存ユーティリティ（`marsdisk/ops/make_qpr_table.py`）で作成。
- 出力先候補: `marsdisk/io/data/qpr_planck_basalt_<source>.csv`

2) **玄武岩の蒸気圧（HKL）パラメータ**
- `sinks.sub_params` の `mu`, `A`, `B`, `A_liq`, `B_liq`, `valid_K` を確定する。
- 参照文献が未決の場合は、決定時にプロジェクト標準の参照管理手順へ従う。

3) **相変化閾値**
- `phase.thresholds.T_condense_K` / `T_vaporize_K` を玄武岩に合わせる。

---

## 出典候補の洗い出し（Q_pr / HKL）

### ⟨Q_pr⟩ テーブル（玄武岩）
- **Mie 理論の基礎**: Bohren & Huffman (1983)  
  参考キー: `BohrenHuffman1983_Wiley`（`analysis/references.registry.json`）
- **Planck 平均の参考値**: Blanco et al. (1976)  
  参考キー: `Blanco1976_ApSS41_447`（`analysis/references.registry.json`）
- **光学定数のプロキシ候補**: Draine (2003) の astronomical silicate  
  参考キー: `Draine2003_SaasFee32`（`analysis/references.registry.json`）
- **ギャップ**: 玄武岩（basaltic glass/rock）の **n,k データセット**がリポジトリ内に未登録。  
  ⟨Q_pr⟩作成のために、玄武岩の複素屈折率データ（波長依存）が必要。

### HKL パラメータ（玄武岩蒸気圧）
- **既存の HKL 立て付け（SiO/SiO2 系）**:
  - Kubaschewski (1974) の Clausius 係数（`analysis/equations.md`）
  - Fegley & Schaefer (2012), Visscher & Fegley (2013) の液相蒸気圧フィット  
    参考キー: `FegleySchaefer2012_arXiv`, `VisscherFegley2013_ApJL767_L12`
  - Melosh (2007) の SiO 蒸気優勢の位置付け  
    参考キー: `Melosh2007_MPS42_2079`
  - Pignatale et al. (2018) の衝突円盤組成  
    参考キー: `Pignatale2018_ApJ853_118`
- **HKL フラックスの一般形**: Markkanen & Agarwal (2020)  
  参考キー: `Markkanen2020_AA643_A16`
- **ギャップ**: 玄武岩組成に特化した **蒸気圧（P_sat）と支配蒸気種**の出典が未登録。  
  玄武岩モードでは SiO/SiO2 の既存係数を **暫定プロキシ** とするか、  
  玄武岩蒸気の文献係数を新規に導入する必要がある。

---

## ChatGPT 調査依頼に必要な情報（要件定義）

### 1) 玄武岩 ⟨Q_pr⟩ テーブルの作成要件
ChatGPT に求める情報:
- **光学定数 n,k の出典**: 玄武岩（basaltic glass/rock）の波長依存の複素屈折率
- **波長範囲/解像度**: 0.1–1000 μm など、T_M=1500–6000 K の Planck 平均に十分な範囲
- **粒子モデル**: 球形（Mie）、多孔質、混合組成（必要なら）
- **温度レンジ**: 本プロジェクトの T_M 範囲（1000–6500 K）で Planck 平均を定義できること
- **粒径レンジ**: `sizes.s_min`～`sizes.s_max` に対応するサイズ範囲

期待する成果物:
- 文献またはデータベース名（著者/年/DOI/URL）
- 玄武岩 n,k テーブルの具体的な取得先と形式（CSV/HDF/論文付録）
- 既存の SiO2 テーブルとの差分として採用可否のコメント

実装側で必要となる記録:
- `analysis/references.registry.json` への追加エントリ
- Q_pr テーブル生成に使った n,k データのファイル名と元URL
- run_card への provenance 記録（`qpr_table_path`, `n_k_source`, `mie_code`, `wavelength_grid`）

### 2) 玄武岩 HKL パラメータの作成要件
ChatGPT に求める情報:
- **支配蒸気種**: 玄武岩蒸気の主要成分（例: SiO, MgO, FeO など）
- **有効分子量 μ**: HKL 用の molar mass [kg/mol]
- **飽和蒸気圧の式**: Clausius 型 `log10 P_sat = A - B/T` の A,B
- **液相/固相の切替温度**: T_liq switch と valid_K 範囲

期待する成果物:
- 玄武岩（または玄武岩系溶融物）蒸気圧の文献（著者/年/DOI/URL）
- A,B,valid_K の係数セット（固相/液相の両方が望ましい）
- 係数の適用温度範囲と注意点（組成依存性や蒸気種の前提）

実装側で必要となる記録:
- `analysis/references.registry.json` への追加エントリ
- `sinks.sub_params` に反映する値（`mu`, `A`, `B`, `A_liq`, `B_liq`, `valid_K`）
- `run_config.json` の `sublimation_provenance` へ記録

### 3) まとめの形式（ChatGPT への依頼仕様）
ChatGPT には以下の形式でまとめさせる:
- **Q_pr 用**: n,k データの出典 → 波長範囲 → 提供形式 → 利用制約
- **HKL 用**: 蒸気種 → μ → A/B/valid_K → 温度域 → 文献
- **引用情報**: DOI/URL/図表番号（可能なら）

---

## 調査結果（候補一覧: 検証メモ）

添付 `.md` の「調査結果（候補一覧: 未検証）」に載っている候補について、**公開されている情報と実データの取得可否**を基準に、実在性・取得性を検証しました。以下では、**確認できた事実**と、現時点で**未確認**の点を分けて書きます。

---

### A. ⟨Q_pr⟩候補一覧（検証済み/未検証を明示）

> 要件の「0.1–1000 μm」を満たすかどうかは、各行の「不足波長域」に明記しました。

| 検証状況 | データセット名 | 著者/年 | DOI/URL | 材料 | 波長範囲と分解能 | 提供形式 | データが「数表」か「図のみ」か | 不足波長域（0.1–1000 μm 要件） | 使用上の注意 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **検証済み（取得可）** | ARIA: **Basalt** n,k（Pollack et al. 1973） | Pollack et al., 1973 | DOI: 10.1016/0019-1035(73)90115-2<br>ARIAデータ（原データ）: `https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basalt_(Pollack_et_al._1973)/original/basalt_Pollack_1973.ri`<br>ARIAデータ（補間版）: `https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basalt_(Pollack_et_al._1973)/interpolated/basalt_Pollack_1973_R.ri` | Basalt（岩石） | **0.21–50 μm**（離散点。Δλは不均一で、ARIAファイルの波長リスト依存） | **ARIAの .ri（テキスト）**。ヘッダに `#FORMAT=WAVL N K` とあり、以降は「波長 n k」の反復並び（1行に詰めて記載） | **数表（ARIAの数値テーブルとして取得可）** | **短波長側** 0.10–0.21 μm が欠ける。<br>**長波長側** 50–1000 μm が欠ける。 | **欠損（NaN）が残る**：原データでは 0.21–0.30 μm 付近で k が NaN。補間版でも NaN が残る箇所があるため、前処理（補間・除外・外挿方針）が必要。 |
| **検証済み（取得可）** | ARIA: **Basaltic glass** n,k（Pollack et al. 1973） | Pollack et al., 1973 | DOI: 10.1016/0019-1035(73)90115-2<br>ARIAデータ（原データ）: `https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basaltic_glass_(Pollack_et_al._1973)/original/basaltic_glass_Pollack_1973_R.ri`<br>ARIAデータ（補間版）: `https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basaltic_glass_(Pollack_et_al._1973)/interpolated/basaltic_glass_Pollack_1973.ri` | Basaltic glass（玄武岩質ガラス） | **0.21–50 μm**（離散点。Δλは不均一） | **ARIAの .ri（テキスト）**。`#FORMAT=WAVL N K`。 | **数表（ARIAの数値テーブルとして取得可）** | **短波長側** 0.10–0.21 μm が欠ける。<br>**長波長側** 50–1000 μm が欠ける。 | 原データは n に NaN が散見され、補間版は n を埋めている一方、短波長側の k に NaN が残る（例: 0.21–0.38 μm 付近）。どちらを使うかは欠損処理方針次第。 |
| **一部検証（論文実在は確認、ただし数表は未取得）** | “Optical Constants of Basaltic Glass from 0.0173 to 50 μm” | Arakawa et al., 1991 | DOI: 10.1017/S0252921100066574<br>PDF: `https://resolve.cambridge.org/core/services/aop-cambridge-core/content/view/1B4FCE2DEE719CEDB23A0249FD04464B/S0252921100066574a.pdf/optical_constants_of_basaltic_glass_from_00173_to_50_m.pdf` | Basaltic glass | **0.0173–50 μm**（タイトル表記） | 論文PDF（Cambridge Core） | **図のみ（Fig.1）**：本文中に「Table」を確認できず、少なくとも公開PDFでは **数表が見当たらない**。したがって取り込みには digitize が必要になる可能性が高い。 | **長波長側** 50–1000 μm が欠ける。 | 本文から、短波長側は Lamy(1978)、長波長側は Pollack(1973) を参照して「つないだ」構成である可能性が高い（独立測定の単独セットではない点に注意）。 |
| **検証済み（本文/表確認）** | “Optical properties of silicates in the far ultraviolet” | Lamy, 1978 | DOI: 10.1016/0019-1035(78)90126-4 | Obsidian / **Basaltic glass** / **Basalt** / Andesite | **0.100–0.44 μm**（Table II の n,k） | 論文PDF（Icarus） | **数表（Table II）**（図は Figs. 3-4） | **短波長側** 0.10 μm 未満が欠ける。<br>**長波長側** 0.44–1000 μm が欠ける。 | Table II は Basaltic glass と Basalt を**別列**で提示。短波長専用で、長波長側は他データで補完が必要。 |

---

### B. HKL候補一覧（検証済み/未検証を明示）

> ここでは「HKL（Hertz–Knudsen–Langmuir）で使う A,B,μ,valid_K」を、**出典が示す式・単位・温度域**として確認する。未確認は未確認と書く。

| 検証状況 | 蒸気種（支配成分） | μ（kg/mol） | log10 P_sat = A + B/T の A,B（P in bar） | 有効温度域（valid_K） | 固相/液相の区別と切替温度 | DOI/URL（Table/Eq 番号） |
| --- | --- | ---: | --- | --- | --- | --- |
| **検証済み（Table 7）** | Basalt（Tholeiites、**全蒸気圧**・溶融系） | **未確定**（全蒸気圧のため単一 μ はモデル仮定） | **A=4.719, B=-16761**（`log10 Pvap(bar)=A+B/T`） | **1700–2400 K（図示範囲）**<br>※フィット適用域の明示なし | **液相前提**（MAGMA code が完全溶融系を仮定）。**Tliq=1433 K**（Table 5） | DOI: 10.1016/j.icarus.2003.06.016（Table 7） |
| **検証済み（Table 7）** | Basalt（Alkalis、**全蒸気圧**・溶融系） | **未確定**（全蒸気圧のため単一 μ はモデル仮定） | **A=4.716, B=-16037**（`log10 Pvap(bar)=A+B/T`） | **1700–2400 K（図示範囲）**<br>※フィット適用域の明示なし | **液相前提**（MAGMA code が完全溶融系を仮定）。**Tliq=1504 K**（Table 5） | DOI: 10.1016/j.icarus.2003.06.016（Table 7） |
| **不成立（提示URLが別文書）** | （tektite相関のはず、という md 記載） | 未確認 | 未確認 | 未確認 | 未確認 | 添付.md が示す NASA NTRS `20200001785` は、実際には **隕石（chassignites/nakhlites）のSnに関するLPSC要旨**で、蒸気圧相関（Eq.(29)）とは一致しない。 |

**注意（Schaefer & Fegley 2004 Table 10）**
- Table 10 は **蒸発（蒸気化）係数 αs** の一覧で、**P_sat(T) の A/B フィットではない**。  
  HKL の前係数（蒸発係数）としては参考になるが、**固相の蒸気圧フィットの代替にはならない**。

### B2. 固相/簡略モデル候補（PDF確認済み、玄武岩直系ではない）

| 文献 | DOI/URL | 対象 | 相 | 式（本文記載） | 係数・単位・注意 |
| --- | --- | --- | --- | --- | --- |
| Love & Brownlee (1991, Icarus) | DOI: 10.1016/0019-1035(91)90085-8 | stony micrometeoroids（chondritic 想定） | 固相ベース（固液で近いと記述） | **log Pv = A − B/T** | A=10.6, B=13500。Pv は **dyn/cm^2**。**log の底は本文で明示なし**。mmol=45 g/mol（chondritic）を推定。 |
| Briani et al. (2013, arXiv) | https://arxiv.org/abs/1302.3666 | micrometeoroid（石質想定） | ―（蒸発モデル） | **log10(psat) = A − B/T** | A=10.6, B=13500、μ=45 amu。Love & Brownlee 由来の係数を **log10 として運用**。玄武岩固相の実測ではない。 |
| Genge (2017, MAPS) | DOI: 10.1111/maps.12830 | basaltic micrometeorites | 固体→部分溶融→溶融（蒸発は簡略） | **exp(A − B/T)** を含む蒸発項 | A=9.6, B=26700、mmol=45。**dimensionless Langmuir constants** と表記。玄武岩固相の実測フィットではない。 |
| Kobayashi et al. (2011, EPS) | DOI: 10.5047/eps.2011.03.012 | obsidian / pyroxene / olivine / iron | 固相（昇華） | **Pv = P0(T) exp( − μ m_u H / (kB T) )**（Eq. 5） | Table 1 に μ(m_u), H(K), P0(dyn/cm^2)。例：Obsidian μ=37, H=34690, P0=8.18e11。**固相プロキシ候補**。 |
| Kimura et al. (1997, A&A 326) | https://ui.adsabs.harvard.edu/abs/1997A%26A...326..263K/abstract | silicate / carbon dust | 固相（昇華） | **pi(T) = exp( − μ_i m_u/(kB T) · L_i + b_i )**（Eq. 6） | Table 1 に ρ, μ, L, b。例：Silicate ρ=3.5, μ=169, L=3.2e10, b=35（単位定義は本文に従う）。**玄武岩の直接値ではない**。 |

#### 単位と Pa 換算（一般式としての整理）

- **Table 7** は `log10 P_sat(bar) = A + B/T`（B は負）なので、`P(Pa)=P(bar)×10^5` より **`log10 P_sat(Pa) = (A+5) + B/T`**。
- **もし** `ln P_sat(atm) = a − b/T` 型なら、`log10` への変換は **`log10 P = (ln P)/ln(10)`**、さらに Pa 化は `P(Pa)=P(atm)×101325`（= `log10 P(Pa) = log10 P(atm) + log10(101325)`）。
  ※Table 7 は bar 表記。ln/atm 形式の文献を使う場合は個別に単位確認が必要。

---

### C. 追加の補完候補（ギャップ埋め）

#### ⟨Q_pr⟩の波長ギャップ（0.10 μm 未満と 50–1000 μm）

- **短波長側の補完候補（0.10 μm 未満）**として、ARIA 内に **Egan et al. (1975)** を出典とする「Basalt」の屈折率データがあることは確認できる（DOI あり）。ただし、**波長範囲とデータファイル名はこの場で未取得**。  
  DOI: 10.1016/0019-1035(75)90029-9（ARIA の記載）
- **長波長側（50–1000 μm）**は、玄武岩直系の一次データが未確定だが、**Demyk 2022 STOPCODA（Mg-Fe silicate proxy）**の数表で埋められることを確認済み。方針は次の2段構え。  
  1. **basalt/basaltic glass で 50 μm 超の n,k を持つ一次データ**を引き続き探索（未確認）。  
  2. 当面は **Demyk 2022 STOPCODA をプロキシ採用**し、プロキシであることを明文化する。

---

### D. 依然残るギャップと、次に確認すべきポイント

#### 1) 玄武岩 n,k（⟨Q_pr⟩）側のギャップ

1. **0.10 μm 未満**: Lamy(1978) Table II で **0.100–0.44 μm** の n,k は確認済み。**0.10 μm 未満**は別データが必要。
2. **50–1000 μm**: Demyk 2022 STOPCODA（Mg-Fe silicate proxy）で埋められるが、**玄武岩直系の一次データは未確定**。
3. **欠損値（NaN）処理**: ARIA の basalt/basaltic glass いずれも NaN が残るため、補間方針（除外・線形補間・端点外挿など）を決める必要がある。

#### 2) HKL（A,B,μ,valid_K）側のギャップ

1. **valid_K（係数の適用温度域）**: Table 7 に明示が無いため、**運用上 1700–2400 K（図示範囲）を採用**し、根拠が図示範囲であることを明記する。
2. **μ（有効分子量）**: 論文は「全蒸気圧」計算の文脈なので、HKL で単一 μ を置くなら、その定義（代表種で置くか、混合で平均するか）を明示する必要がある。
3. **固相側の扱い**: MAGMA code は完全溶融系を仮定し、Table 7 に固相係数は無い。固相側の扱い（無効化/外挿/別文献）を決める必要がある。
4. **Tliq しきい値の運用**: Table 5 の Tliq（tholeiite 1433 K / alkali 1504 K）を使うか、別の切替温度を採用するかを決める必要がある。
5. **固相プロキシの式の整合**: Love & Brownlee / Briani / Genge / Kobayashi / Kimura で **式形・単位・log の底が異なる**ため、採用する場合は統一変換と前提を明記する必要がある。

---

### 長波長 (>50 µm) 代替データ探索（検証メモ）

以下、添付 `.md` の要件（例：⟨Q_pr⟩ 用に「n,k の出典・波長範囲・提供形式」を確定し、0.1–1000 µm のギャップを明示する）に沿って、指定 3 点（Demyk 2022 / Schaefer & Fegley 2004 / Lamy 1978）を **本文・Table を根拠に**確認したうえで、**最終採用セット（n,k + HKL）と連結ルール**を推奨確定案として整理する。

---

#### 1) Demyk et al. 2022（STOPCODA/SSHADE）

**1.1 論文側レンジ・外挿方針**

- 測定 MAC から m=n+ik を導出し、**5–800 または 5–1000 µm**（サンプル依存）で得ると明記。
- 天文モデル用途として、**短波長・長波長側は外挿して 0.01–10^5 µm の k を作り、K–K で n を計算**すると明記。
- 長波長側は **500–1000 µm 帯（サンプル依存）からスペクトル指数を決め、べき則で外挿**する方針。

**結論**: 500–1000 µm は **外挿係数決定帯域としてカバー**される。800–1000 の「測定そのまま」はサンプル依存。

**1.2 STOPCODA/SSHADE 側のレンジ・分解能**

- **測定域**: 5–1000 µm（2000–10 cm⁻¹）
- **分解能**: 300 cm⁻¹ より上は 2 cm⁻¹、下は 1 cm⁻¹
- “valid spectral range” は外挿込みで広く設定

※ 分解能と出力ファイルの実際の刻みは一致しない可能性があるため、**エクスポート実ファイルの確認が必須**。

**1.3 実データ形式**

- SSHADE のチュートリアルでは **Export は zip**、**スペクトルは ASCII** と説明。
- 実ファイルの列構成は `wavelength(micron)`, `real_intensity`, `imaginary_intensity` ほか（**1.5 で確認済み**）。
- **ダウンロードはログイン必須**（登録運用）。

**1.4 500–1000 µm 埋めの可否（結論）**

- **埋めることは可**（測定域 or 外挿で 500–1000 µm を取得可能）。
- 1000 µm まで「測定を強く期待」するなら **λ_FIR=1000 のサンプルを選ぶ**。

---

#### 1.5 STOPCODA 実データ点検（列定義・500–1000 µm 埋まり・E20優先）

**対象ファイル（実データ）**
- `paper/STOPCODA/EXPERIMENT_KD_20220525/OptCte_Mg(1-x)FexSiO3_E20_5-1000mic_300K_extrapol/OptCte_Mg(1-x)FexSiO3_E20_5-1000mic_300K_extrapol.data.txt`
- `paper/STOPCODA/EXPERIMENT_KD_20220525_002/OptCte_Mg(1-x)FexSiO3_E20R_5-1000mic_300K_extrapol/OptCte_Mg(1-x)FexSiO3_E20R_5-1000mic_300K_extrapol.data.txt`

**列定義（共通）**
- `wavelength(micron)`, `real_intensity`, `imaginary_intensity`, `real_intensity_error_minus`, `imaginary_intensity_error_minus`, `real_intensity_error_plus`, `imaginary_intensity_error_plus`
- ヘッダに `spectrum type: optical constants` を明記。列名は n/k ではなく Re/Im として扱う前提。

**500–1000 µm 埋まり状況（機械点検）**
- E20（非R）:
  - min/max: **0.024–100000 µm**（外挿込み、単調増加）
  - 500–1000 µm: **83 点**, **502.832–999.607 µm**, NaN/Inf **なし**
  - Δλ は非等間隔（500–1000 µm帯で約 3.07–11.90 µm）
- E20R:
  - min/max: **0.024–100000 µm**（外挿込み、単調増加）
  - 500–1000 µm: **82 点**, **502.832–987.707 µm**, NaN/Inf **なし**
  - Δλ は非等間隔（500–1000 µm帯で約 3.07–11.62 µm）

**判定と採用方針**
- **E20（非R）を優先**（1000 µm 近傍まで到達し、500–1000 µm が連続で欠損なし）。
- 1000 µm 到達が不要なら E20R でも可だが、最大波長が 987.7 µm で止まる点を明記。
- 外挿域（<5 µm / >1000 µm）はヘッダに明記されるが、行ごとの外挿フラグは無いため、波長で領域を分けて扱う。

---

#### 2) Schaefer & Fegley (2004) Table 7（HKL）

**2.1 Table 7 の式・単位（確定）**

- Table 7 脚注: **log10(P_vap [bars]) = A + B/T**
- Tholeiites / Alkalis の A,B が表形式で提示。
- Table 7 は **1900 K の蒸気圧と近似式**を列挙する構成。

**Table 7（bar 表記）**

- **Tholeiites**: A = 4.719, B = −16761
- **Alkalis**: A = 4.716, B = −16037

**Pa 表記への変換**

- 1 bar = 10^5 Pa → **A_Pa = A_bar + 5**、B は同じ。
- Tholeiites: **log10(P[Pa]) = 9.719 − 16761/T**
- Alkalis: **log10(P[Pa]) = 9.716 − 16037/T**

**2.2 valid_K の扱い（未確認）**

- 係数の適用温度域は **明記されていない**。
- 本文の計算温度域は **1700–3000 K**、図の主範囲は **1700–2400 K**。  
  **運用上は 1700–2400 K を valid_K として採用**し、根拠が「図示範囲」であることを明記する。
- **液相線温度（Tliq）**は Table 5 に記載（tholeiite 1433 K / alkali basalt 1504 K）。  
  **Tliq を下限として液相のみ適用**する運用案が現実的。

**2.3 μ の決め方（参考）**

- Table 9 の molecular flux をフラックス重みで平均 → **μ_eff ≈ 0.024–0.025 kg/mol**（1700–1900 K）。
- 実装簡素化なら **μ=0.0245 kg/mol** または **μ=0.02299 kg/mol（Na）**固定が現実的。

---

#### 3) Lamy (1978)（短波長補完）

- 試料: **Obsidian / Basaltic glass / Basalt / Andesite** を扱う。
- **Table II** に Basaltic glass / Basalt / Obsidian の **n,k 数表**が掲載。
- 波長域: **0.100–0.44 µm**（短波長補完に直接使用可能）。
- DOI: **10.1016/0019-1035(78)90126-4**

---

#### 4) 最終採用セット（n,k + HKL）と連結ルール（推奨確定案）

**(A) 光学定数 n,k（0.10–1000 µm）**

- **短波長（0.10–0.21 µm）**: Lamy 1978 **Basaltic glass** Table II
- **重複域（0.21–0.44 µm）**: 基本は **ARIA basaltic glass**、ARIA の NaN は **Lamy で置換**
- **中赤外（0.44–50 µm）**: ARIA basaltic glass
- **遠赤外（50–1000 µm）**: Demyk 2022 STOPCODA の **Fe-rich 系（例：E20/E20R 相当、300 K）**
  - λ_FIR=1000 のサンプルを優先（測定域の最大化を優先）

**(B) HKL（蒸気圧近似）**

- **Schaefer & Fegley 2004 Table 7** を採用  
  Basalt 組成は **Tholeiites** をデフォルトとする。

**連結ルール（実装仕様）**

1. **最終波長グリッド**: 0.10–1000 µm を **log 等間隔**（例: Δlog10λ = 0.002〜0.005）
2. **補間**: n(λ) は線形、k(λ) は **log(k)** 線形補間
3. **接続**:
   - 0.21–0.44 µm: **ARIA の NaN を Lamy で置換**（ブレンド不要）
   - 50 µm 付近: **[40, 60] µm ブレンド窓**で連結  
     n = (1−w) n_ARIA + w n_Demyk  
     log k = (1−w) log k_ARIA + w log k_Demyk

**HKL 側の固相/液相**

- **推奨**: 液相温度域のみ適用（T ≥ T_on）、固相は別モデル or 0 扱い。
- **代替**: Table 7 を低温へ外挿し、valid_K 外フラグを立てる。

---

#### 5) DOI/URL（まとめ）

```
Demyk et al. 2022 (A&A) doi:10.1051/0004-6361/202243815
https://doi.org/10.1051/0004-6361/202243815

STOPCODA / SSHADE (data landing)
doi:10.26302/SSHADE/STOPCODA
https://doi.org/10.26302/SSHADE/STOPCODA

SSHADE experiment (Demyk optical constants)
doi:10.26302/SSHADE/EXPERIMENT_KD_20220525_002
https://doi.org/10.26302/SSHADE/EXPERIMENT_KD_20220525_002

Schaefer & Fegley 2004 (Icarus) doi:10.1016/j.icarus.2003.06.016
https://doi.org/10.1016/j.icarus.2003.06.016

Lamy 1978 (Icarus) doi:10.1016/0019-1035(78)90126-4
https://doi.org/10.1016/0019-1035(78)90126-4

Love & Brownlee 1991 (Icarus) doi:10.1016/0019-1035(91)90085-8
https://doi.org/10.1016/0019-1035(91)90085-8

Briani et al. 2013 (arXiv)
https://arxiv.org/abs/1302.3666

Genge 2017 (MAPS) doi:10.1111/maps.12830
https://doi.org/10.1111/maps.12830

Kobayashi et al. 2011 (EPS) doi:10.5047/eps.2011.03.012
https://doi.org/10.5047/eps.2011.03.012

Kimura et al. 1997 (A&A 326) ADS
https://ui.adsabs.harvard.edu/abs/1997A%26A...326..263K/abstract
```

---

#### 6) 追加で確定が必要な点

- STOPCODA の列定義は確認済みだが、`real_intensity` / `imaginary_intensity` を **m の実部/虚部（= n/k 相当）として扱う前提**を run_card に明記する運用を決める。
- Schaefer & Fegley (2004) Table 7 の **valid_K は明示されていない**ため、**運用上 1700–2400 K（図示範囲）を採用**したことと、根拠が図示範囲である点を記録する。
- HKL の **μ（有効分子量）**を単一値で置く場合の定義（Na 代表 or 混合平均）を確定する。
- **固相側の扱い**（液相のみ/外挿/別文献）を仕様として固定する。
- **Tliq 運用**（Table 5 の 1433 K / 1504 K を採用するか）を決めて run_card に明記する。
- 固相プロキシを使う場合は、**式形・単位・log の底の統一変換**と適用範囲を明記する。

---

## 運用メモ（methods.md への将来記載想定）

- 固相側の昇華係数に直接対応する文献式が無いため、**液相の蒸気圧フィットを固相へ外挿した「上限評価」**を事前にプロットし、影響の大きさのみ確認する。  
- 本文の基準結果は **固相昇華を無効化**したケースを採用し、外挿ケースは **不確実性の参考**として扱う。  
- 外挿ケースで使う前提（液相 A/B の外挿、Tliq の扱い、valid_K の根拠）は必ず明記する。

---

## 実装タスク（チェックリスト）

- [ ] 固相昇華の運用方針（基準ケース/上限評価）を確定し、run_card への記録方針を決める  
- [ ] HKL パラメータを確定（`valid_K=1700–2400 K` の運用、`Tliq=1433/1504 K` の扱い、`μ` の固定）  
- [ ] 確定事項を本プランの「確定仕様」へ昇格し、未決事項を整理する  
- [ ] 玄武岩モードの設定スイッチ設計（固相昇華 ON/OFF、valid_K 外フラグ、Tliq 判定）を YAML 仕様として定義する  
- [ ] ⟨Q_pr⟩ テーブル生成の実行計画を確定（Lamy + ARIA + Demyk の連結ルール、E20 優先）  
- [ ] 0D 最小検証の準備と実行（`configs/overrides/material_basalt.override` 作成、`summary.json` / `checks/mass_budget.csv` の確認）
- [ ] `docs/plan/20251226_material_properties_current_defaults.md` に「玄武岩統一モード追加」の追記  

---

## 受入条件（玄武岩モード）

- `run_config.json` に **玄武岩の Q_pr テーブルパス**と **HKL パラメータ**が記録される  
- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内  
- `series/run.parquet` の主要列（`a_blow`, `beta_at_smin_*`, `M_out_dot`）が生成される  
- SiO2/SiO の設定値が混在していない（`run_config.json` の値で確認）

---

## リスクと注意点

- 玄武岩の光学定数・蒸気圧データが未確定な場合、**見かけの統一に留まる**可能性がある  
- ⟨Q_pr⟩ や HKL パラメータは `a_blow` / `M_out_dot` に直結するため、感度試験が必須  
- gas-poor 前提（`enable_gas_drag=false`）は維持する

---

## 次フェーズ（SiO2 統一モード）

玄武岩モードの完了後に、SiO2 統一モードを追加する。  
作業内容は本ドキュメントの構造を流用し、物性セットのみ差し替える。
