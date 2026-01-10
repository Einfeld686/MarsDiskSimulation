# フォルステライト相別（液体/固体）モード作成プラン（Phase 1）

> **作成日**: 2026-01-02  
> **更新日**: 2026-01-10  
> **ステータス**: 更新（フォルステライト寄せ）  
> **対象**: 0D 標準設定（`configs/base.yml`）の相別物性設計  

---

## 背景

現行の `configs/base.yml` は、密度・破壊強度・光学・蒸気圧（HKL）などの物性が、別々の前提（材料・相・温度域）から来ている混在状態です。  
詳細な整理は `docs/plan/20251226_material_properties_current_defaults.md` を参照します。

今回のシミュレーション時間制約と、データ取得性の観点から、**材料をフォルステライト（Mg2SiO4）に寄せて、固相・液相の両方で質量フラックス（HKL）を説明する**方針に切り替えます。  
フォルステライトについては、固相の相平衡蒸気圧の近似式（van Lieshout et al., 2014, Eq.13 + Table 3）と、液相（溶融）の全蒸気圧の近似式（Fegley, 2012, Eq.5）が、ともに明示されています。

---

## 目的

- **Forsterite（固相+液相）**の1系統を基準として、物性の provenance（出典・式・温度域・単位）を `run_config.json` に記録可能にする。
- ⟨Q_pr⟩ 用の光学定数（n,k）と、HKL（固相/液相）の**切替条件**を、実装ルールとして固定する。
- 「固相係数が無い/不明」を例外扱いせず、**未確定点は未確定として管理**する。

---

## スコープ

- 0D 標準設定（`configs/base.yml`）に対する**相別モードの設定セット**（overrides）を作成する。
- 物理式や数値スキームは変更しない（係数・テーブル・閾値の差し替えのみ）。

---

## 非スコープ

- フォルステライト以外の材料ケース（比較・上限見積もり等）は Phase 1 では扱わない。
- 気相種の化学平衡（成分別蒸気圧、反応式ベースの蒸発）は Phase 1 では導入しない（全蒸気圧フィットを使用）。
- 高温（>300 K）での光学定数の温度依存を Phase 1 ではモデル化しない（後述の未確定項目として扱う）。

---

## Phase 1 成果物（2系統）

### Forsterite（基準：固相+液相）
- 固相 HKL: **van Lieshout et al. (2014)** の相平衡蒸気圧（Eq.13）と Table 3 の係数を使用。
- 液相 HKL: **Fegley (2012)** の溶融フォルステライト全蒸気圧（Eq.5）を使用。
- ⟨Q_pr⟩: FOR2285 のフォルステライト光学定数データ（0.08–1000 µm）を使用。
- overrides: `material_forsterite.override`

### Forsterite（比較：液相のみ）
- 基準と同じ液相 HKL を使用し、固相 HKL を無効化して比較する（「固相寄与の有無」を見るため）。
- overrides: `material_forsterite_liq_only.override`

---

## 実装方針

### 方針 A（推奨）
`configs/base.yml` に対する **overrides ファイル**を用意し、実行時に適用します。

```
python -m marsdisk.run \
  --config configs/base.yml \
  --overrides-file configs/<overrides/material_forsterite.override>
```

```
python -m marsdisk.run \
  --config configs/base.yml \
  --overrides-file configs/<overrides/material_forsterite_liq_only.override>
```

---

## 相別ロールの割り当て（config キーの差し替え範囲）

| config key | Forsterite（固相+液相） | Forsterite（液相のみ） | メモ |
|---|---|---|---|
| `material.rho` | 3270.0 | 同左 | van Lieshout et al. (2014) Table 2 の 3.27 g/cm^3 を kg/m^3 に換算 |
| `qstar.*` | 既存値を維持 | 同左 | **未確定**：フォルステライト専用の破壊強度パラメータは Phase 1 では探索しない |
| `radiation.qpr_table_path` | forsterite | forsterite | ⟨Q_pr⟩テーブルを生成して差し替える |
| `phase.thresholds.T_vaporize_K` | 2163 K | 2163 K | 液相スイッチ温度に合わせる（phase 有効時のみ） |
| `phase.thresholds.T_condense_K` | 1673 K（未確定: 暫定運用） | 同左 | 固相 fit の下限に合わせた運用値 |
| `sinks.sub_params.mode` | `hkl` | `hkl` | HKL を使用 |
| `sinks.sub_params.enable_liquid_branch` | true | true | 液相分岐を有効化 |
| `sinks.sub_params.A/B/valid_K` | 有効（固相） | 無効（A/B=null） | 固相 HKL（van Lieshout） |
| `sinks.sub_params.A_liq/B_liq/valid_liquid_K` | 有効 | 有効 | 液相 HKL（Fegley） |
| `sinks.sub_params.psat_liquid_switch_K` | 2163 K | 0.0 K | 液相のみは常時液相を選ぶ |
| `run_config.json.radiation_provenance` / `sublimation_provenance` | 記録 | 記録 | Q_pr と HKL の provenance を記録 |

> 注：実際のキー名は `configs/base.yml` の実装に依存します。  
> 固相を無効化する場合は `sinks.sub_params.A/B=null` とし、`psat_liquid_switch_K=0` で液相分岐を常時有効化する。

---

## 依存データ・準備タスク

1) **⟨Q_pr⟩（0.08–1000 µm）**
- フォルステライトの光学定数（n,k）を **単一データセットで取得**し、0.08–1000 µm を埋める。
- 結晶の異方性（a/b/c 軸）は **Fabian et al. (2001) Eq.(8)** の 1/3 平均（`C_ext` の軸平均）を **暫定採用**し、`run_config.json.radiation_provenance.nk.anisotropy_handling` に記録する。  
  ただし **FOR2285 配布元の推奨手順は不明**なため、根拠の出どころ（Fabian 2001）と「配布元推奨は未確認」を run_card に明記する。

2) **HKL（固相/液相）**
- `sinks.sub_params.mode="hkl"`、`sinks.sub_params.psat_model="clausius"` を明示する。
- `sinks.sub_params.alpha_evap=0.1`、`sinks.sub_params.mu=0.140694`（Table 3 の µ=140.694 g/mol を kg/mol に換算）。
- 固相：van Lieshout et al. (2014) Eq.13 を **log10 P(Pa) = A − B/T** 形式に変換して使用。  
  A=13.809441833, B=28362.904024、`valid_K=(1673, 2133)` を設定。
- 液相：Fegley (2012) Eq.5 を **log10 P(Pa) = A − B/T** 形式で使用。  
  A=11.08, B=22409、`valid_liquid_K=(2163, 3690)`、`psat_liquid_switch_K=2163` を設定。
- **外挿は原則しない**。固相 valid 上限（2133 K）と液相 valid 下限（2163 K）の 30 K ギャップは、  
  **「固相を 2133 K まで、液相を 2163 K から」**の運用で記録し、補間は行わない。
- 液相のみケースでは `A/B=null` とし、`psat_liquid_switch_K=0` で液相分岐を常時有効化する。

3) **相変化閾値（Tliq）**
- Phase 1 の切替温度は 2163 K を採用（液相フィットの下限温度に合わせる）。
- `phase.thresholds.T_vaporize_K=2163`、`phase.thresholds.T_condense_K=1673`（未確定: 暫定運用）を設定する。
- `run_config.json.sublimation_provenance` に、切替温度と valid_K の扱いを記録する。

---

## 検証済み一覧（確定データの詳細）

### 1) FOR2285 forsterite optical constants (n,k)

| 出典/URL | ファイル名 | 波長範囲 | 数表or図 | 等方化（a/b/c→等方）の根拠 |
|---|---|---:|---|---|
| FOR2285 “New optical constants of forsterite” 配布ページ（AIU Jena） | `fors_{a,b,c}_{50,75,100,150,200,295}_nk.dat`（例：`fors_a_295_nk.dat`, `fors_b_295_nk.dat`, `fors_c_295_nk.dat`） | **0.08–1000 µm**（50K と 295K の a/b/c を実ファイル確認：先頭 0.080 µm、末尾 1000.00 µm） | **数表**（3列 ASCII：λ(µm), n, k） | Fabian et al. (2001) Eq.(8) の 1/3 平均を暫定採用（配布ページに推奨手順の明示なし） |

**補足（取得性・形式・列定義の確定）**
- 配布ページに「Data tables (3-column, ASCII): λ(µm), n, k」と明記されている。
- 実ファイルはヘッダなしの空白区切り 3 列（`λ_um, n, k`）。
- データは **Mutschke & Mohr (2019)** の新規透過測定と、**Suto et al. (2006) / Zeidler et al. (2011) / Huffman & Stapp (1973)** などの「modified literature data」に基づくと記載されているが、**どの波長域が実測/接続かの内訳は未記載**。

**利用条件（確認できた範囲）**
- OCDB 側には「原典論文を cite してほしい」との注意書きがあるが、明確なライセンス条文は確認できていない（**ライセンスは UNKNOWN**）。

**run_config.json に残すべき provenance（最低限）**
- `run_config.json.radiation_provenance.nk.source_url`: FOR2285 配布ページ URL
- `run_config.json.radiation_provenance.nk.files`: 使用ファイル名（例：`fors_a_295_nk.dat` / `fors_b_295_nk.dat` / `fors_c_295_nk.dat`）
- `run_config.json.radiation_provenance.nk.columns`: `wavelength_um, n, k`
- `run_config.json.radiation_provenance.nk.wavelength_range_um`: `[0.08, 1000.0]`
- `run_config.json.radiation_provenance.nk.temperature_grid_K`: `[50, 75, 100, 150, 200, 295]`
- `run_config.json.radiation_provenance.nk.anisotropy_handling`: **Fabian et al. (2001) Eq.(8)** に基づく 1/3 平均（`C_ext` の軸平均）。**FOR2285 配布元の推奨手順は未確認**のため、その旨も併記する。

**等方化ルール（文献根拠）**
- Fabian et al. (2001) の異方性材料に対する消衰断面積の平均化（Eq.(8)）を採用する：  
  `C_ext = (1/3) * [C_ext(ε_x) + C_ext(ε_y) + C_ext(ε_z)]`  
  （FOR2285 の配布ページ自体には等方化の推奨が書かれていないため、**配布元推奨は未確認**として併記する）

---

### 2) van Lieshout et al. (2014) 固相蒸気圧

| 原式 | 係数（Table 3: forsterite） | 単位 | valid_K | log10 P(Pa) = A − B/T への変換後A/B | 式/表番号 |
|---|---|---|---:|---|---|
| `p_v = exp(-A/T + B)` | μ=140.694, α=0.1, A=65308±3969, B=34.1±2.5 | `p_v`: **dyn cm^-2** | **1673–2133 K** | **A = (B/ln10) − 1 = 13.809441833** / **B = A/ln10 = 28362.904024** | Eq.(13), Table 3 ([A&A][1]) |

**確認ポイント（本文根拠）**
- 固相からの質量損失フラックス `J(T)` は Langmuir 型（Eq.(12)）で、その相平衡蒸気圧 `p_v` の近似が Eq.(13)。
- forsterite の係数は Table 3 に数表として掲載（温度範囲は「AとBを決めた温度範囲」）。
- DOI: **10.1051/0004-6361/201424876**。

**変換（係数変換の根拠）**
- Eq.(13) は自然指数 `exp`：
  - `log10 p_v(dyn/cm^2) = (B - A/T) / ln 10`
  - `1 dyn/cm^2 = 0.1 Pa` より `log10 p_v(Pa) = log10 p_v(dyn/cm^2) - 1`
  - よって `log10 p_v(Pa) = (B/ln10 - 1) - (A/ln10)/T`

**run_config.json に残すべき provenance**
- `run_config.json.sublimation_provenance.solid_pvap.source`: van Lieshout et al. 2014（DOI/URL）
- `run_config.json.sublimation_provenance.solid_pvap.eq`: Eq.(13)（exp, dyn cm^-2）
- `run_config.json.sublimation_provenance.solid_pvap.table`: Table 3（A,B,μ,α, temp range）
- `run_config.json.sublimation_provenance.solid_pvap.valid_K`: `[1673, 2133]`
- `run_config.json.sublimation_provenance.solid_pvap.convert_to_log10Pa`: 変換式と係数（上表の A,B）
- `run_config.json.sublimation_provenance.solid_pvap.note_total_or_component`: 相平衡蒸気圧（単一 pv）

---

### 3) Fegley (2012) 液相蒸気圧

| 原式 | valid_K | 単位 | log10 P(Pa) = A − B/T への変換後A/B | 式番号 | 査読原典の有無 |
|---|---:|---|---|---|---|
| `log P_vap(Mg2SiO4,liq) = 6.08 - 22409/T` | **2163–3690 K** | `P`: **bar**（かつ **total pressure** と明記） | **A = 11.08, B = 22409**（bar→Pa は +5）※ただし log の底は本文で明示なし | Eq.(5) | arXiv 版に加え、Treatise on Geochemistry 章に DOI あり：**10.1016/B978-0-08-095975-7.01303-6**（査読形態は未確認） |

**確認ポイント（本文根拠）**
- Eq.(5) は「molten forsterite の derived vapor pressure equation (2163–3690 K)」として提示。
- 直後に「Eq.(5) は molten forsterite と平衡な飽和蒸気の **total pressure (bar)**」と明記。
- arXiv 版は **Treatise on Geochemistry, Chapter 13.3** として配布されており、出版社版の存在が示唆される（出版社版 PDF で最終書誌情報と式表記を確認予定）。

**log の底について（推測禁止の扱い）**
- 本文では Eq.(5) が **“log”** 表記で、**底（10 か e か）は未定義** → **UNKNOWN**。
- 同章の Clausius–Clapeyron 導出では `ln` が別途使われている（Eq.(3)〜(4) 近辺）。

**bar→Pa の変換（確認できる範囲）**
- `1 bar = 1e5 Pa` なので、**log10** を採用する運用なら `log10 P(Pa) = log10 P(bar) + 5`。
- よって A は +5（6.08→11.08）、B は不変（22409）。

**run_config.json に残すべき provenance**
- `run_config.json.sublimation_provenance.liquid_pvap.source`: arXiv 1210.0270v1 URL（Eq.(5) 確認）
- `run_config.json.sublimation_provenance.liquid_pvap.eq`: Eq.(5)（log 表記、bar、total pressure 明記）
- `run_config.json.sublimation_provenance.liquid_pvap.valid_K`: `[2163, 3690]`
- `run_config.json.sublimation_provenance.liquid_pvap.log_base`: **UNKNOWN**（本文に定義なし）
- `run_config.json.sublimation_provenance.liquid_pvap.convert_to_log10Pa_assumption`: 「log=log10 を採用する」等の運用前提と、その場合の `A=11.08, B=22409`
- `run_config.json.sublimation_provenance.liquid_pvap.peer_reviewed_source`: Treatise on Geochemistry の DOI（存在確認）

---

### 4) 相判定温度（T_vaporize / T_condense）

| 値 (K) | 何を意味させる値か | 根拠の有無 | 根拠（文献/式/表） |
|---:|---|---|---|
| 2163 | forsterite の融点（solid→melt の境界として liquidus 扱い） | 根拠あり（本文で融点 2163 K 明記、かつ molten の式の適用下限が 2163 K） | Fegley & Schaefer: 融点 2163 K 記載、および Eq.(5) の適用範囲 2163–3690 K |
| 1673 | 固相蒸気圧フィットの適用下限（運用下限として使うなら） | 「フィットの valid 下限」としては根拠あり／「相境界温度」としては根拠なし → **UNKNOWN** | van Lieshout Table 3: forsterite の温度範囲 1673–2133 K |

**run_config.json に残すべき provenance**
- `run_config.json.sublimation_provenance.phase_T_liq_K`（`phase.thresholds.T_vaporize_K` 相当）: 2163 K の根拠（融点・液相式の下限）
- `run_config.json.sublimation_provenance.phase_T_sol_min_valid_K`（`phase.thresholds.T_condense_K` の運用下限）: 1673 K は「固相係数の適用下限」であり相境界ではない旨
- 固相 valid 上限 2133 K と液相 valid 下限 2163 K の 30 K ギャップの扱いは **運用ルールとして明文化**（補間せず、run_card にも残す）

---

### 5) フォルステライトの Q_D*（破壊強度）

| 文献有無 | 係数 | 適用範囲 | 備考 |
|---|---|---|---|
| **UNKNOWN** | UNKNOWN | UNKNOWN | forsterite 専用の Q_D*（サイズ・速度依存の破壊強度スケーリング）は表・式とも未特定 |

**run_config.json に残すべき provenance**
- `run_config.json` の `qstar.*` には「forsterite 専用値の根拠は未特定（UNKNOWN）」を明記（暫定値を置く場合は出典と材料名を必ず固定）

**候補（本文確認待ち）**
- Avdellidou et al. (2016) に peridot / basalt の **catastrophic disruption threshold (Q*im)** が数値提示されている。  
  ただし **純フォルステライトではない**ため、proxy として採用する場合は材料定義と係数形の整合（`qstar.*` で要求されるスケーリング則）を本文で確認する必要がある。

---

## 未確定（UNKNOWN）一覧

1. **FOR2285 配布元が推奨する等方化手順**：配布ページに推奨が明記されていないため **UNKNOWN**（暫定的に Fabian et al. 2001 Eq.(8) を採用）。
2. **Fegley Eq.(5) の “log” の底**：本文に定義がなく **UNKNOWN**（Treatise on Geochemistry 出版社版で確認が必要）。
3. **固相 valid 上限 2133 K と液相 valid 下限 2163 K の 30 K ギャップ運用**：文献で明記されておらず **UNKNOWN**（Costa et al. 2017 の Eq.(33) が候補だが本文確認待ち）。
4. **高温（>300 K）での n,k 温度依存の扱い**：純フォルステライトの高温データ有無が **UNKNOWN**（Temperature-dependent … の本文確認待ち）。
5. **forsterite 専用の Q_D***：現状 **UNKNOWN**（Avdellidou 2016 の peridot Q*im は proxy 候補だが本文確認待ち）。

## 追加調査（PDF確認待ちの候補）

1. **Costa et al. (2017) Icarus**：Eq.(33) の式形・単位・温度域・相区分（固相/液相）と、全蒸気圧として HKL に使えるかを本文で確認。
2. **Treatise on Geochemistry Chapter 13.3（出版社版）**：Fegley Eq.(5) の最終表記（log の底・式番号・ページ）を確定。
3. **Temperature-dependent Infrared Optical Constants of Olivine and Enstatite**：純フォルステライトの有無、波長域、数表提供の有無を本文で確認。
4. **Avdellidou et al. (2016)**：Q*im の定義と、`qstar.*` の係数形に落とせるかを本文で確認（peridot/basalt の適用範囲を含む）。
5. **FOR2285 “forthcoming paper”**（公開済みなら）：配布元推奨の等方化手順やデータ接続ルールが明記されているかを確認。

## 次に確認すべき優先順位（短く）

1. Costa et al. (2017) の Eq.(33) と温度域の確認（valid_K ギャップ対策の可能性）。
2. Treatise on Geochemistry 出版社版で Fegley Eq.(5) の log 底と書誌情報を確定。
3. Temperature-dependent n,k 論文の本文確認（純フォルステライトか・波長域・数表の有無）。
4. Avdellidou 2016 の Q*im 定義と `qstar.*` への適合性判断。
5. FOR2285 “forthcoming paper” が公開済みなら、配布元推奨の等方化ルール確認。

[1]: https://www.aanda.org/articles/aa/pdf/2014/12/aa24876-14.pdf?utm_source=chatgpt.com "Dusty tails of evaporating exoplanets"

## Appendix A. 未検証候補一覧（必要になった場合のみ）

> Phase 1 の採用データが不足した場合のバックアップ候補。現時点では本文確認・取得性確認が未完了のため「未検証」とする。

### A-1) 光学定数（n,k）の代替
- **未検証**：FOR2285 以外の公開 n,k（異方性の扱い、温度依存、データ形式の確認が必要）
- **未検証**：*Temperature-dependent Infrared Optical Constants of Olivine and Enstatite*（10–973 K）。純フォルステライトか、波長域、数表提供の有無が本文確認待ち。

### A-2) 液相の全蒸気圧フィットの代替
- **未検証**：Fegley (2012) と同等の式を、査読付き論文（原典）から直接引用できるか（出典の置換）

### A-3) 蒸気圧ギャップ（2133–2163 K）への代替
- **未検証**：Costa et al. (2017) Icarus（forsterite-rich olivine, Fo95Fa5）の Eq.(33) が total vapor pressure として使える可能性。式形・単位・温度域の本文確認が必要。

### A-4) Q_D*（破壊強度）の proxy
- **未検証**：Avdellidou et al. (2016) の peridot/basalt Q*im。`qstar.*` に落とせる係数形か本文確認が必要。

---

## 実装タスク（チェックリスト）

- [ ] `material_forsterite.override` を作成し、固相/液相の HKL を設定  
- [ ] `material_forsterite_liq_only.override` を作成し、固相 HKL を無効化  
- [ ] ⟨Q_pr⟩生成スクリプトを用意し、FOR2285 の n,k（a/b/c）を等方化して Q_pr テーブルを出力  
- [ ] ⟨Q_pr⟩生成時の等方化ルールは **Fabian et al. (2001) Eq.(8) の 1/3 平均**を採用し、`run_config.json.radiation_provenance.nk` に記録（FOR2285 推奨手順は未確認である旨を run_card に補足）  
- [ ] HKL の係数（A/B, A_liq/B_liq, valid_K/valid_liquid_K）は `run_config.json.sublimation_provenance` に記録  
- [ ] 固液切替温度と valid_K ギャップ（2133–2163 K）の運用は run_card に記録  
- [ ] 0D 最小検証を実行し、`summary.json` / `checks/mass_budget.csv` を確認  
- [ ] `docs/plan/20251226_material_properties_current_defaults.md` にフォルステライト版の導入を追記  

---

## 受入条件（相別モード）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内  
- `series/run.parquet` の主要列（`a_blow`, `beta_at_smin_*`, `M_out_dot`）が生成される  
- `run_config.json.radiation_provenance.nk` に ⟨Q_pr⟩のテーブルパスと provenance（source_url, files, columns, wavelength_range, temperature_grid, anisotropy_handling）が記録される  
- `run_config.json.sublimation_provenance` に HKL の固相/液相係数、valid_K、log_base/変換前提、相判定温度の provenance が記録される  
- run_card に ⟨Q_pr⟩の等方化ルール・波長グリッド・固液切替条件（valid_K ギャップ運用）が記録される  

---

## リスクと注意点

- **異方性**：Fabian et al. (2001) Eq.(8) の 1/3 平均を暫定採用するが、FOR2285 配布元が推奨する等方化手順は未確認のため感度差のリスクが残る。
- **温度依存**：FOR2285 の n,k は 50–295 K の提供であり、高温域の光学定数は含まれない。Temperature-dependent n,k の候補はあるが本文確認待ち。
- **valid_K ギャップ**：固相の実験温度上限（2133 K）と液相フィット下限（2163 K）の間に空白があるため、補間・clamp の方針が必要。Costa et al. (2017) Eq.(33) が候補だが本文確認待ち。

---

## 次フェーズ（Phase 2 の候補）

- （必要なら）光学定数の高温依存や、等方化方法の感度評価を追加する。
- （必要なら）液相全蒸気圧の原典（査読付き）への出典差し替えを行う。
