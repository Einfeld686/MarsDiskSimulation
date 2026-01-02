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
| **一部検証（論文実在は確認、basalt含有・数表有無は未確認）** | “Optical properties of silicates in the far ultraviolet” | Lamy, 1978 | DOI: 10.1016/0019-1035(78)90126-4 | 「4種のsilicates（Pollack 1973で扱ったもの）」と記載（**basaltが含まれるか未確認**） | 抄録上は **1026–1640 Å**（=0.1026–0.1640 μm）で反射率測定、さらに **2500–4500 Å**（=0.25–0.45 μm）で透過測定により k を改善、とある | ScienceDirect掲載（全文は要アクセス） | **未確認**（抄録だけでは「表」か「図」か断定できない） | （basaltを含むなら）0.10–0.21 μm を補える可能性。<br>ただし **basalt含有が未確認**、かつ 0.17–0.25 μm などにギャップが出る可能性。 | 抄録に「Kramers-Kronig解析で m=n−ik を計算」とあるが、数値出力の形（表/図/別資料）は未確認。 |

---

### B. HKL候補一覧（検証済み/未検証を明示）

> ここでは「HKL（Hertz–Knudsen–Langmuir）で使う A,B,μ,valid_K」を、**出典が示す式・単位・温度域**として確認する。未確認は未確認と書く。

| 検証状況 | 蒸気種（支配成分） | μ（kg/mol） | log10 P_sat = A − B/T の A,B | 有効温度域（valid_K） | 固相/液相の区別と切替温度 | DOI/URL（Table/Eq 番号） |
| --- | --- | ---: | --- | --- | --- | --- |
| **一部検証（論文実在と温度域は確認、A,B・単位・Table番号は未確認）** | （論文概要上）**Na などの揮発性成分や O, O2, SiO 等が重要**と示唆されるが、「支配成分」を Table から確定できていない | **未確認**（論文は「全蒸気圧」を扱うため、HKLの単一 μ はモデル側の仮定になる可能性が高い） | **未確認**（添付.md には tholeiitic basalt: `A=4.719, B=16761` とあるが、Table 7 原文を直接見ていない） | **1700–2400 K**（論文要旨の範囲として確認） | **未確認**（少なくとも要旨では「溶融状態の平衡蒸気」を扱う文脈。固相係数の有無・切替温度は本文確認が必要） | DOI: 10.1016/j.icarus.2003.08.023（Icarus 169(1) 216–241）<br>※ Table 7 記載は md 由来で未確認 |
| **一部検証（同上）** | 同上 | 同上 | **未確認**（添付.md には alkali basalt: `A=4.716, B=16037` とあるが未確認） | **1700–2400 K** | 同上 | 同上 |
| **不成立（提示URLが別文書）** | （tektite相関のはず、という md 記載） | 未確認 | 未確認 | 未確認 | 未確認 | 添付.md が示す NASA NTRS `20200001785` は、実際には **隕石（chassignites/nakhlites）のSnに関するLPSC要旨**で、蒸気圧相関（Eq.(29)）とは一致しない。 |

#### 単位と Pa 換算（一般式としての整理）

- **もし** `log10 P_sat(bar) = A − B/T` なら、`P(Pa)=P(bar)×10^5` なので **`log10 P_sat(Pa) = (A+5) − B/T`**。
- **もし** `ln P_sat(atm) = a − b/T` 型なら、`log10` への変換は **`log10 P = (ln P)/ln(10)`**、さらに Pa 化は `P(Pa)=P(atm)×101325`（= `log10 P(Pa) = log10 P(atm) + log10(101325)`）。
  ※ここは数学的換算であり、「どの文献が bar/atm を使っているか」は本文の確認が必要（上表では未確認扱い）。

---

### C. 追加の補完候補（ギャップ埋め）

#### ⟨Q_pr⟩の波長ギャップ（0.10–0.21 μm と 50–1000 μm）

- **短波長側の補完候補（0.10–0.21 μm）**として、ARIA 内に **Egan et al. (1975)** を出典とする「Basalt」の屈折率データがあることは確認できる（DOI あり）。ただし、**波長範囲とデータファイル名はこの場で未取得**。  
  DOI: 10.1016/0019-1035(75)90029-9（ARIA の記載）
- **長波長側の補完（50–1000 μm）**は、現時点の候補（Pollack/ARIA、Arakawa、Lamy）だけでは埋まらない。したがって次の2段構えが現実的。  
  1. **まず「basalt/basaltic glass で 50 μm 超の n,k」を持つ一次データ**があるかを探す（未確認）。  
  2. 見つからない場合は、**プロキシ（代表的なシリケート鉱物やガラス）**で遠赤外を代用し、その前提（「遠赤外の応答が類似」など）を明文化する。  
     ※このプロキシ選定は、現時点では **具体データセット（DOI/URL付き）を確定できていない**ため、次節Dで「次に確認すべきポイント」に落とす。

---

### D. 依然残るギャップと、次に確認すべきポイント

#### 1) 玄武岩 n,k（⟨Q_pr⟩）側のギャップ

1. **0.10–0.21 μm**: Arakawa(1991) は Fig.1 から数値化が必要な可能性が高い。Lamy(1978) は basalt を含むか、数表があるかが未確認。
2. **50–1000 μm**: 今回の候補だけでは埋まらない。一次データの有無を別途探索する必要がある。
3. **欠損値（NaN）処理**: ARIA の basalt/basaltic glass いずれも NaN が残るため、補間方針（除外・線形補間・端点外挿など）を決める必要がある。

#### 2) HKL（A,B,μ,valid_K）側のギャップ

1. Schaefer & Fegley (2004) の **Table 7 を直接確認できていない**ため、A,B、圧力単位（bar か等）、Table番号の確定が未完。
2. **μ（有効分子量）**: 論文は「全蒸気圧」計算の文脈なので、HKL で単一 μ を置くなら、その定義（代表種で置くか、混合で平均するか）を明示する必要がある（現時点で未確認）。
3. Palmer 2020 の候補は、提示 URL が別文書であることを確認したため、**出典候補として差し替えが必要**。

---

### 長波長 (>50 μm) 代替データ探索（検証メモ）

以下、添付 `.md` の要件（「0.1–1000 µm を目標」「>50 µm のギャップが重要」「未確認は未確認と書く」など）に沿って、指定 4 件を**本文・実データの“実在性/取得性”の観点で検証**した結果。

---

#### A. Perry et al. (1972) 検証結果

**結論（検証済み）**:

- **玄武岩（basalt）試料は含まれる**（月試料の “Ophitic basalt / Olivine basalt Type B / Variolitic basalt / Basaltic cryst. rock” が Table IV に明示）。
- **n,k は数表では提示されない**（「光学定数を直接は示さない」と本文で明記）。
- **波長は 5–500 µm をカバー**（本文に明記）。
- Springer の**記事ページは購読表示**だが、**PDF 直リンクは存在**（ただし「誰でも常に無料か」は未確認）。

**書誌・取得先**:

- 論文：*Infrared and Raman spectra of lunar samples from Apollo 11, 12 and 14*
- DOI：`10.1007/BF00562000`
- URL（記事）：`https://link.springer.com/article/10.1007/BF00562000`
- URL（PDF 直リンク）：`https://link.springer.com/content/pdf/10.1007/BF00562000.pdf`

**補足**:

- これは「月の basalt（玄武岩質岩石）」であり、「地球産 basalt」ではない。
- **反射率スペクトル**は Figures 2–9、**誘電関数の分散（e′, e″）**は Figures 10–17 に提示されるが、n,k の数表はないため **digitize + 復元**が必要。
- 測定レンジは 20–2000 cm⁻¹ と明記され、波長換算で **5–500 µm**（>50 µm を含む）。
- n,k 復元では **e′=n²−k², e″=2nk** を用いる前提になるため、図の数値化精度が支配的。

---

#### B. Dorschner et al. (1995) 検証結果

**結論（検証済み）**:

- HEJDOC（MPIA Heidelberg）に **n,k の標準データファイルが実在**し、**直接リンクで取得可能**。
- 標準データファイル（`.ric`）は **最小 0.2 µm、最大 500 µm**。
- 形式は **テキストの数表**（wavelength / n / k / dielectric など複数列）。

**取得先（直接リンク）**:

- HEJDOC（olivin.html）：`https://www2.mpia-hd.mpg.de/HJPDOC/PAPERS/DORSCHN.95/olivin.html`
- y=0.4（standard data file）：`olmg40.ric`
- y=0.5（standard data file）：`olmg50.ric`
- y=0.4（initial data table）：`olmg40.lnk`
- y=0.5（initial data table）：`olmg50.lnk`

**補足**:

- `.ric` の先頭/末尾は **2.0000E−05 cm**〜**5.0000E−02 cm**（= 0.2–500 µm）。
- `.lnk` は **wavelength[µm], n, k** の連結表（数表）で、波長端 **0.2–500 µm** を含む。
- 論文側では光学定数の提示レンジとして **0.19–500 µm** が記載されている。

---

#### C. Demyk et al. (2022) 検証結果

**結論（検証済み）**:

- **データ置き場は STOPCODA（SSHADE インフラ）**であることが明示され、**DOI でデータセットに到達できる**。
- **5–800/1000 µm（試料により差）**が明示され、**500–1000 µm 埋めに使える試料がある**。
- **配布ファイル形式（CSV/HDF等）は未確認**（STOPCODA 側の各エントリで要確認）。
- **ダウンロードはログインが必要**（SSHADE 側で登録が必要な運用）。

**書誌**:

- arXiv：`https://arxiv.org/abs/2209.06513`
- A&A DOI：`10.1051/0004-6361/202243815`

**data availability**:

- STOPCODA（DB）：`10.26302/SSHADE/STOPCODA`
- データセット DOI：`10.26302/SSHADE/EXPERIMENT_KD_20220525_002` ほか

**補足**:

- Table 1 に **1000 µm まで到達する試料**が記載（例：X35=5–1000、E20=5–1000）。
- SSHADE 側では **0.024–5 µm** と **1000–100000 µm** への外挿も記載されるため、測定域（5–1000 µm）と外挿域の境界整理が必要。

---

#### D. Lamy (1978) 検証結果

**結論（部分的に検証／重要点は未確認あり）**:

- **測定レンジ（遠紫外 1026–1640 Å）と、Kramers–Kronig で m=n−ik を計算したこと**は抄録から確認できる。
- ただし **basalt が含まれるか**、**n,k が数表か図のみか**は **未確認**。

**取得先**:

- ScienceDirect（抄録）：`https://www.sciencedirect.com/science/article/abs/pii/0019103578901264`
- NASA NTRS（文献レコード）：`https://ntrs.nasa.gov/citations/19780050703`

**補足**:

- 抄録には「Pollack et al. (1973) が可視〜赤外で扱った “4 silicates”」とあるが、試料名は列挙されない。
- Arakawa et al. (1991) 側の要旨では **obsidian / basalt / basaltic glass** を Lamy (1978) が扱ったと示唆されるが、**一次文献本文での確認は未実施**。
- Lamy (1978) は **0.10–0.44 µm** の短波長領域であり、>50 µm のギャップ埋めには使えない。

---

#### E. 依然残るギャップと次のアクション

- **玄武岩（basalt）直系の >50 µm n,k 数表**: Perry et al. (1972) は 5–500 µm で basalt を含むが、n,k の数表がないためそのまま使えない（digitize + 復元が必要）。
- **Dorschner (1995)**: 最大 500 µm で止まるため、**500–1000 µm** を埋めるには Demyk 2022 の採用が有力。
- **Demyk (2022)**: STOPCODA 側のファイル形式・波長グリッド、ログイン要件を確認する必要がある。
- **Lamy (1978)**: basalt 含有と数表/図の確認が必要（本文確認）。Lamy は短波長補完であり、長波長ギャップには寄与しない。

---

## 実装タスク（チェックリスト）

- [ ] 玄武岩の物性セット（密度・Q_pr テーブル・HKL パラメータ・相変化閾値）を確定する  
- [ ] `configs/overrides/material_basalt.override` を作成（方針 A）  
- [ ] 玄武岩の ⟨Q_pr⟩ テーブルを生成し、リポジトリ内へ配置  
- [ ] 最小検証（0D 短時間）で `summary.json` / `checks/mass_budget.csv` を確認  
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
