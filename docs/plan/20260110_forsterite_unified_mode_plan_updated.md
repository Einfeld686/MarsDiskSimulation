# フォルステライト統一モード作成プラン（Phase 1）

> **作成日**: 2026-01-02  
> **更新日**: 2026-01-10  
> **ステータス**: 更新（HKL: van Lieshout+2014 [solid] / Fegley+2012 [liquid] / α: van Lieshout Table 3 / n,k: FOR2285）  
> **対象**: 0D 標準設定（`configs/base.yml`）の相別物性設計（フォルステライト一本化）  

---

## 背景

現行の `configs/base.yml` は、密度・破壊強度・光学・蒸気圧（Hertz–Knudsen–Langmuir; HKL）などの物性が、別々の前提（材料・相・温度域）から来ている混在状態です。  
今回のシミュレーション時間制約とデータ取得性の観点から、**材料をフォルステライト（Mg2SiO4）に寄せ、固相・液相を同一材料で扱う**ことを Phase 1 の目標にします。

---

## 目的（Phase 1 で確定させること）

1. **光学（⟨Q_pr⟩）**  
   フォルステライトの光学定数（n,k）を 0.08–1000 µm で読み込み、粒径 a ごとに ⟨Q_pr⟩ を生成できる状態にする。

2. **質量フラックス（HKL）**  
   フォルステライトの **固相・液相**それぞれについて、全蒸気圧の温度依存式を HKL 計算に載せる。  
   固相は `log10 P(Pa)=A−B/T` 形式への変換係数まで確定済み。  
   液相は `log` の底が未明示のため、A/B 変換は「log=log10 と仮定する場合のみ」採用する。

3. **相判定（固/液の切替）**  
   固相↔液相の切替温度を、文献の根拠つきで `run_config.json` に記録できる形にする。

---

## 依存データ・準備タスク（Phase 1）

- **n,k（FOR2285）**  
  Jena の FOR2285 データ（a/b/c 軸、295 K）を取得し、3列テキストとして読み込む。  
  等方化（異方性の扱い）は「軸ごとの光学計算を行い、1/3 平均する」方針で確定する（根拠は下記の検証済み一覧）。

- **HKL（全蒸気圧）**  
  `data/forsterite_material_data/forsterite_material_properties.json` の値を正として、  
  固相は van Lieshout et al. (2014) Eq.(13)、液相は Fegley & Schaefer (2012) Eq.(5) を採用する。  
  固相は `log10 P(Pa)=A−B/T` への変換係数（A_fit/B_fit）まで確定済み。  
  液相は `log` の底が本文で未明示のため、`log_base=UNKNOWN` を provenance に残し、  
  変換は「log=log10 とみなす運用」を採用する場合のみ A_fit/B_fit を使う（Appendix B 参照）。
- **α（蒸発/凝縮係数）**  
  van Lieshout et al. (2014) Table 3 の α=0.1 を採用し、Phase 1 は **α=0.1 一定**で運用する（同表では Gail 2010 を参照）。
- **密度（ρ）**  
  `forsterite_material_properties.json` の `rho_kg_m3=3270` を採用する（van Lieshout et al. 2014, Table 2）。

---

## 検証済み一覧（確定データの詳細）

### 1) FOR2285 forsterite optical constants（n,k）

|項目|内容|
|---|---|
|出典/URL|Jena FOR2285 “Forsterite – Optical Constants”（配布ページ）: https://www2.astro.uni-jena.de/FOR2285/en/forsterite_optical.php|
|ファイル名|`fors_a_295_nk.dat`, `fors_b_295_nk.dat`, `fors_c_295_nk.dat`（各 a/b/c 軸）|
|波長範囲|実データで **0.08–1000 µm**（a/b/c の各ファイル）|
|数表 or 図|**数表**（3列のASCIIデータ）|
|形式|3列（λ[µm], n, k）。ヘッダなし。|
|ローカル配置|`data/forsterite_material_data/nk_FOR2285/` に `fors_{a,b,c}_{50,75,100,150,200,295}_nk.dat` を保存済み（空白区切り3列）。統合表は `data/forsterite_material_data/FOR2285_forsterite_nk_long.csv`、マニフェストは `data/forsterite_material_data/FOR2285_forsterite_nk_manifest.json`。|
|等方化の根拠|異方性結晶の吸収断面積（または効率）を **a/b/c 軸で計算して 1/3 平均**する考え方が、Zeidler et al. (2015) の式（Eq.(7)）で明示されている。Phase 1 は「軸別に Mie を回して Q_pr を 1/3 平均」を採用する。|
|利用条件（明文化されている範囲）|FOR2285 配布ページ本文には明示ライセンス条文が見当たらない。Jena の OCDB 一般ページでは「please cite ...」の引用要請があるため、**配布ページURLと原典論文の引用**を provenance に残す（ライセンス条文は未確認）。|

補足（温度依存）: FOR2285 は 50–295 K の温度グリッド（50/75/100/150/200/295 K）を提供しているが、**溶融域（>295 K）の光学定数は直接与えない**。高温依存の光学定数（例: Zeidler et al. 2015）は存在するが、対象が「低Feオリビン/エンスタタイト」かつ 5–50 µm・10–928 K の範囲であり、Phase 1 の統一データ（0.08–1000 µm, forsterite）を直接置換はしない。

---

### 2) 固相：全蒸気圧（HKL用）

**原典**: van Lieshout et al. (2014) arXiv:1410.3494

|項目|内容|
|---|---|
|原式（本文）|Eq.(13): `pv = exp( −A/T + B )`（pv: dyn cm−2）|
|係数（固相）|A=65308, B=34.1（Table 3: crystalline forsterite）|
|valid_K（根拠）|1673–2133 K（Table 3 の係数決定範囲）|
|HKL用の式（質量フラックス）|Eq.(12): `J(T)=α pv(T) sqrt( μ m_u / (2π k_B T) )`|
|α（蒸発/凝縮係数）|α=0.1（Table 3; Gail 2010 を参照と注記）|
|μ（kg/mol）|μ=0.140694 kg/mol（Table 3; 分子量近似と本文注記）|
|実装用 A/B（log10 P(Pa)）|`log10 P(Pa)=13.809441833 − 28362.904024 / T`（dyn cm−2→Pa 変換を含む）|
|ローカル参照|`data/forsterite_material_data/forsterite_material_properties.json`|

---

### 3) 液相：全蒸気圧（HKL用）

**原典**: Fegley & Schaefer (2012) arXiv:1210.0270（Treatise on Geochemistry 章の可能性あり）

|項目|内容|
|---|---|
|原式（本文）|Eq.(5): `log Pvap(bar) = 6.08 − 22409/T`（molten forsterite, total pressure）|
|valid_K（根拠）|2163–3690 K（Eq.(5) の適用範囲）|
|log の底|本文で明示されていないため `UNKNOWN` として provenance に残す|
|実装用 A/B（log10 P(Pa)）|`log` を log10 と仮定する場合のみ `log10 P(Pa)=11.08 − 22409 / T`（bar→Pa 変換を含む）|
|μ（kg/mol）|Phase 1 は固相と同じ μ=0.140694 kg/mol を採用|
|ローカル参照|`data/forsterite_material_data/forsterite_material_properties.json`|

---

### 4) 相判定温度（solid↔liquid）

**原典**: Fegley & Schaefer (2012) の molten forsterite の適用下限（2163 K）を採用

|項目|内容|
|---|---|
|根拠|Eq.(5) の適用温度下限が 2163 K（融点として使用）|
|運用値（Phase 1）|`T_switch = 2163 K`|
|補足|固相の係数決定範囲は 2133 K までで、液相の下限 2163 K との 30 K ギャップがある。`T_condense_solid_K=1673 K` は固相フィットの下限であり、相境界ではない。運用ルールは run_config に記録する。|

---

### 5) α（蒸発/凝縮係数）

**原典**: van Lieshout et al. (2014) arXiv:1410.3494（Table 3）

|項目|内容|
|---|---|
|記述|Table 3 に α=0.1（Gail 2010 を参照と注記）|
|運用値（Phase 1）|`α = 0.1`（一定）|
|注意|温度依存や相依存は Phase 2 以降で検討する|

---

## 実装方針（run_config.json への反映）

### キー整合（run_config.json）

- 実際の出力キーは `run_config.json.radiation_provenance` と `run_config.json.sublimation_provenance` を正とする。  
  以下の例にある `optical_constants` / `sublimation (HKL)` は**概念スキーマ**であり、実装では次の対応で記録する。
- 対応の方針:
  - `optical_constants.*` → `run_config.json.radiation_provenance.nk.*`
  - `sublimation (HKL).pvap_solid` → `run_config.json.sublimation_provenance.solid_pvap.*`
  - `sublimation (HKL).pvap_liquid` → `run_config.json.sublimation_provenance.liquid_pvap.*`
  - `sublimation (HKL).alpha` / `mu_kg_mol` → `run_config.json.sublimation_provenance.alpha` / `mu_kg_mol`
- もし既存スキーマで上記のサブキーが未定義の場合は、`run_config.json` 側で追加し、**run_card にも同じ provenance を併記**して冗長化する。

---

## 役割分担とデータ受け渡し

- **Codex（本リポジトリ担当）**: 具体値は外部文献にアクセスせず、**ChatGPT が提供した値・式・表の根拠をそのまま実装**し、既存スキーマとの整合を担保する。  
- **ChatGPT（文献調査担当）**: 文献・公式ページから数値・式・適用範囲を確定し、**再現可能な形でデータを提供**する。推測は禁止。未確定は `UNKNOWN` と明記する。  

**受け渡しフォーマット（いずれかで提出）**
- **CSV（推奨）**: 実装に必要な値・単位・条件・根拠位置を1行で提供する。  
  ヘッダー: `item_id,parameter,value,value_min,value_max,value_uncertainty,units,conditions,phase,target_path,source_authors_year,doi_or_url,exact_location,evidence_quote,status,notes`
- **run_config.json 用ブロック**: `radiation_provenance.nk.*` / `sublimation_provenance.*` に対応する JSON 断片として提出する。  

**未確定の扱い**
- ChatGPT 側で確定できない場合は `status=unknown` として提出し、Codex 側で `UNKNOWN_REF_REQUESTS` に登録して運用する。  

### 推奨する run_config.json の provenance 記録項目（例）

- **optical_constants**
  - dataset: `"FOR2285"`
  - url: `"https://www2.astro.uni-jena.de/FOR2285/en/forsterite_optical.php"`
  - retrieved_utc: `"YYYY-MM-DD"`
  - files:
    - `"data/forsterite_material_data/nk_FOR2285/fors_a_295_nk.dat"`, `"data/forsterite_material_data/nk_FOR2285/fors_b_295_nk.dat"`, `"data/forsterite_material_data/nk_FOR2285/fors_c_295_nk.dat"`
  - file_manifest: `"data/forsterite_material_data/FOR2285_forsterite_nk_manifest.json"`
  - combined_table: `"data/forsterite_material_data/FOR2285_forsterite_nk_long.csv"`
  - columns: `["wavelength_um","n","k"]`
  - wavelength_um_min/max: `0.08 / 1000.0`
  - anisotropy_handling:
    - method: `"axis-wise Mie then 1/3 average"`
    - evidence: `"Zeidler et al. (2015) Eq.(7), DOI:10.1088/0004-637X/798/2/125"`

- **sublimation (HKL)**
  - pvap_solid:
    - equation_printed: `"van Lieshout+2014 Eq.(13): pv = exp( −A/T + B ) dyn cm−2"`
    - A: `65308`
    - B: `34.1`
    - A_log10_Pa: `13.809441833`
    - B_over_T: `28362.904024`
    - valid_K: `[1673,2133]`
    - unit: `"dyn cm−2"` (converted to Pa in code)
    - doi_or_url: `"arXiv:1410.3494"`
  - pvap_liquid:
    - equation_printed: `"Fegley+Schaefer 2012 Eq.(5): log Pvap(bar) = 6.08 − 22409/T"`
    - log_base: `"UNKNOWN"`
    - A_log10_Pa_assuming_log10: `11.08`
    - B_over_T: `22409`
    - valid_K: `[2163, 3690]`
    - doi_or_url: `"arXiv:1210.0270"`
    - note: `"log base is not explicit; conversion is conditional"`
  - alpha:
    - value: `0.1`
    - evidence: `"van Lieshout+2014 Table 3 (note: Gail 2010)"`
  - mu_kg_mol:
    - value: `0.140694`
    - evidence: `"van Lieshout+2014 Table 3 (compound molecular weight approximation)"`

---

## 実装タスク（チェックリスト）

- [ ] `configs/base.yml` に対する overrides（例: `configs/overrides/material_forsterite.override`）を用意し、`forsterite_material_properties.json` の ρ・HKL・α・μ・相判定温度・Q_pr テーブルを差し替える  
- [ ] FOR2285 の a/b/c 軸 n,k を読み込み、**軸別 Mie → 1/3 平均**で ⟨Q_pr⟩ テーブルを生成  
- [ ] `run_config.json.radiation_provenance.nk` に、URL・ファイル名・波長範囲・等方化手順・採用温度を記録  
- [ ] `run_config.json.sublimation_provenance` に、van Lieshout 2014（solid）/ Fegley 2012（liquid）の式・係数、α、μ、valid_K、`log_base=UNKNOWN` を記録  
- [ ] 0D 実行を行い、`series/run.parquet` / `summary.json` / `checks/mass_budget.csv` を確認  

---

## 受入条件（Phase 1）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内  
- `series/run.parquet` に `a_blow`, `beta_at_smin_config`, `beta_at_smin_effective`, `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks` が出力される  
- `run_config.json.radiation_provenance.nk` に provenance（URL/ファイル名/波長範囲/等方化/採用温度）が記録される  
- `run_config.json.sublimation_provenance` に HKL の式/係数、α、μ、valid_K、log_base の根拠が記録される  
- `checks/mass_budget.csv` が生成され、`error_percent` が 0.5% 以内  

---

## 次に埋めるべき内容（実装前に明文化すべき項目）

### 文献参照が必要な項目（確定待ち）

- **Q_D*（qstar.*）の専用値**：forsterite 専用の破壊強度スケーリングを採用する場合は文献確定が必要  
- **FOR2285 利用条件**：明示ライセンス条項が見当たらないため、配布元/README の確認が必要  
- **液相 Eq.(5) の log 底**：Fegley & Schaefer (2012) の `log` の底が本文で未明示のため確認が必要  

### 文献参照なしで確定できる項目（今回確定）

- **overrides とキーの具体マッピング**：`configs/overrides/material_forsterite.override` を用意し、`configs/base.yml` を上書きする  
- **密度（ρ）**：`forsterite_material_properties.json` の `rho_kg_m3=3270` を採用する  
- **相判定の運用**：`phase.thresholds.T_condense_K` は `phase.thresholds.T_vaporize_K` と同値に固定し、ヒステリシスなしで運用する  
- **液相スイッチ**：`sinks.sub_params.psat_liquid_switch_K` は `phase.thresholds.T_vaporize_K` と同値に固定する  
- **Q_D*（qstar.*）の運用**：forsterite 専用値が未確定の間は **base 値を維持**し、run_card に「forsterite 専用値は未反映」と明記する  
- **HKL パラメータの具体キー**：`sinks.sub_params.A/B/A_liq/B_liq/alpha_evap/mu/valid_K/valid_liquid_K/psat_liquid_switch_K` に割り当てる  
- **run_config provenance の実キー**：`radiation_provenance.nk.*` と `sublimation_provenance.*` に記録する（概念スキーマではなく実キーで運用）  
- **FOR2285 の運用処理**：ライセンスが未確認のため `UNKNOWN_REF_REQUESTS` へ登録し、run_card に「引用要請のみ確認」と明記する  

---

## リスクと注意点（Phase 1 の範囲）

1. **液相蒸気圧式の log 底が未定義**  
   Fegley & Schaefer (2012) Eq.(5) の `log` の底が本文で明示されていないため、`log_base=UNKNOWN` を provenance に残す。  
   実装で log10 を仮定する場合は、**仮定であること**を run_config/run_card に明記する。

2. **固相/液相の valid_K ギャップ（2133–2163 K）**  
   固相の係数決定範囲は 2133 K、液相の下限は 2163 K で 30 K の空白がある。  
   Phase 1 は `T_switch=2163 K` を優先し、ギャップは補間せず run_config に運用ルールを残す。

3. **α の温度依存**  
   van Lieshout et al. (2014) の α=0.1 は定数採用であり、温度依存は未導入。Phase 2 で感度解析の対象にする。

4. **光学定数の温度依存・組成依存**  
   FOR2285 は 50–295 K の純 forsterite（a/b/c 軸）。高温・不純物（Fe含有）での光学定数は別途扱いが必要。

---

## 未確定（UNKNOWN）一覧（Phase 1 実装に残るギャップ）

|項目|状況|次に確認するもの|
|---|---|---|
|FOR2285 の明示ライセンス条文|配布ページ本文に明示条文は見当たらない。OCDB 一般ページの「please cite」要請のみ確認済み|Jena 側の利用条件ページ/README があるか、または配布元へ確認（現状は「引用要請のみ確認」を provenance に残す）|
|Fegley & Schaefer (2012) Eq.(5) の log 底|本文で log の底が明示されていないため UNKNOWN|出版社版の章や本文で log の底が明示されているか確認|
|forsterite の Q_D*（破壊強度）|専用値の文献確定が未完|Q_D*(R) 形式に落とせる文献の確認（必要なら proxy を明示）|

---

## Appendix B. A/B 変換メモ（van Lieshout 2014 / Fegley 2012 → run_config 用）

### B1. van Lieshout et al. (2014) 固相（exp 形式 → log10 Pa）

出発点（dyn cm−2）  
`pv = exp( −A/T + B )`

1 dyn cm−2 = 0.1 Pa より、

`log10 P(Pa) = (B/ln10 − 1) − (A/ln10)/T`

計算結果（Phase 1）:
- `A_fit = 13.8094418329`
- `B_fit = 28362.904024`

### B2. Fegley & Schaefer (2012) 液相（log 表記）

出発点（bar）  
`log Pvap(bar) = 6.08 − 22409/T`

log の底が本文で明示されていないため、**log=log10 と仮定する場合のみ**:

`log10 P(Pa) = 11.08 − 22409/T`（1 bar = 1e5 Pa）

log=ln の場合は別換算が必要であり、Phase 1 では仮定を run_config に明記する。

---

## Appendix C. 参考（将来用・今回の統一に直接は使わない）

- Costa et al. (Icarus, Eq.(33)) は Fo95Fa5 について、融点以下での全蒸気圧近似式 `log P_T(bar)=6.9908−22519/T` を提示している。純 forsterite ではないため Phase 1 の主パラメータには採用しないが、同温度域でのオーダー確認に利用できる。
