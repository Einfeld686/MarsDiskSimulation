# 玄武岩相別（液体/固体）モード作成プラン（Phase 1）

> **作成日**: 2026-01-02  
> **ステータス**: 立案（未着手）  
> **対象**: 0D 標準設定（`configs/base.yml`）の相別物性設計  
> **旧称**: 玄武岩統一モード（Phase 1）

---

## 背景

現行の `configs/base.yml` は「玄武岩密度/破壊強度 × SiO2 光学 × SiO 蒸気圧」という混在状態です。  
詳細な整理は `docs/plan/20251226_material_properties_current_defaults.md` を参照。

玄武岩は固相では昇華しないため、HKL の固相係数が無いのは自然です。一方、液相（溶融）では玄武岩の蒸発を考えるのは妥当です。  
そこで「玄武岩で全物性を統一する」よりも、**液体と固体で使う前提を分離し、2系統の成果物を作る**方針に更新します。

---

## 目的

- **Basalt-Liquid（基準）**と**Basalt + Solid-Proxy（上限）**の2系統を明示し、実装と再現性の軸を分ける。
- Q_pr 用 n,k の**連結ルール**と、HKL の**固液切替**を記録可能にする。
- 固相係数が無いことを「欠落」ではなく**計画上の分岐**として扱う。

---

## スコープ

- 0D 標準設定（`configs/base.yml`）に対する**相別モードの設定セット**を作成する。
- 物理式や数値スキームは変更しない（係数・テーブル・閾値の差し替えのみ）。

---

## 非スコープ

- 1D 拡張や既存テストの大規模改修
- 液相フィットの固相への外挿（原則禁止）
- 玄武岩固相の新規実験式の導入（文献確定後に別計画で対応）

---

## Phase 1 成果物（2系統）

### Basalt-Liquid（基準）
- **液相 HKL のみ適用**（固相は無効化、または温度範囲外扱い）。
- 玄武岩の液相蒸気圧は **Schaefer & Fegley (2004) Table 7** を採用。
- 出力の provenance に **液相のみ**であることを明示。
- overrides: `material_basalt_liq.override`

### Basalt + Solid-Proxy（上限）
- 固相は **Solid-Proxy**（SiO2 / forsterite / enstatite / metal Fe / FeS など）から選ぶ。
- 玄武岩固相ではないことを `run_config.json` に必ず記録。
- 液相は Basalt-Liquid と同じ設定を踏襲。
- overrides: `material_basalt_solid_proxy_<material>.override`

---

## 実装方針

### 方針 A（推奨）
`configs/base.yml` に対する **overrides ファイル**を用意し、実行時に適用する。

```
python -m marsdisk.run \
  --config configs/base.yml \
  --overrides-file configs/<overrides/material_basalt_liq.override>
```

```
python -m marsdisk.run \
  --config configs/base.yml \
  --overrides-file configs/<overrides/material_basalt_solid_proxy_<material>.override>
```

**理由**: ベース設定の差分が明確になり、2系統を並列管理できる。

### 方針 B（代替）
`material_basalt_liq.yml` / `material_basalt_solid_proxy_<material>.yml` を新規作成し、  
`configs/` 配下で `base.yml` 相当を複製して差分を上書きする。

---

## 相別ロールの割り当て（固体/液体）

| ロール | 設定キー | Basalt-Liquid（基準） | Basalt + Solid-Proxy（上限） |
|---|---|---|---|
| 固体（密度） | `material.rho` | 玄武岩想定 | 玄武岩想定 |
| 固体（破壊強度） | `qstar.*` | 玄武岩向け係数 | 玄武岩向け係数 |
| 光学 | `radiation.qpr_table_path` | n,k 連結で生成した Q_pr | 同左 |
| 相判定 | `phase.thresholds.*` | 液相/固相の切替に使用 | 同左 |
| HKL（液相） | `sinks.sub_params.*` | 玄武岩液相（Table 7） | 同左 |
| HKL（固相） | `sinks.sub_params.*` | **無効** | **Solid-Proxy** |

---

## 依存データ・準備タスク

1) **玄武岩 ⟨Q_pr⟩ テーブルの生成**
- 既存ユーティリティ（`marsdisk/ops/make_qpr_table.py`）で作成。
- 出力先候補: `marsdisk/io/data/` の `qpr_planck_basalt_<source>.csv`
- **波長グリッド定義**: 0.1–1000 µm の log 等間隔を基本とする。
- **入力 n,k の欠損処理**: NaN は補間/除外/近傍値置換のどれを採るかを明記する。
- **ソース連結の優先順位と接続波長**: UV→可視/赤外→遠赤外の順で接続。例:  
  - Lamy (0.10–0.44 µm) → ARIA (0.21–50 µm) の欠損補完  
  - ARIA (0.21–50 µm) → STOPCODA (50–1000 µm) のブレンド接続
- **連結点の連続性チェック**: n,k のジャンプ量をログに出す。
- 0.1–1000 µm が埋め切れない場合は**影響評価**を実施し、未充足域と影響を記録する。

2) **HKL（液相/固相）の方針**
- **基準（Basalt-Liquid）**: Schaefer & Fegley (2004) Table 7 を液相にのみ適用し、固相は無効化。
- **上限（Solid-Proxy）**: SiO2 / forsterite / enstatite / metal Fe / FeS など、固相データが厚い材料を選ぶ。
- **外挿は禁止**: 液相フィットを固相に外挿しない（行う場合は参考計算扱い）。

3) **相変化閾値**
- 液相/固相の切替温度（Tliq）を設定し、HKL の適用範囲と整合させる。
- Tliq の出典・運用は `run_config.json` に記録する。

---

## 検証済み一覧

### A. Q_pr 用 n,k（検証済み）

| データセット | 材料 | 波長範囲 | 取得先URL | ファイル名 | 数表/図 | 備考 |
|---|---|---|---|---|---|---|
| Lamy 1978 Table II | Basaltic glass / Basalt | 0.100–0.44 µm | https://doi.org/10.1016/0019-1035(78)90126-4 | Table II (PDF) | 数表 | 短波長補完 |
| ARIA Pollack 1973 | Basaltic glass | 0.21–50 µm | https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basaltic_glass_(Pollack_et_al._1973)/interpolated/basaltic_glass_Pollack_1973.ri | basaltic_glass_Pollack_1973.ri | 数表 | NaN処理が必要 |
| ARIA Pollack 1973 | Basalt | 0.21–50 µm | https://eodg.atm.ox.ac.uk/ARIA/data_files/Rocks_and_Conglomerates/Basalt/Basalt_(Pollack_et_al._1973)/interpolated/basalt_Pollack_1973_R.ri | basalt_Pollack_1973_R.ri | 数表 | 代替候補 |
| Demyk 2022 (STOPCODA) | Mg-Fe silicate proxy | 5–800/1000 µm | https://doi.org/10.1051/0004-6361/202243815 | OptCte_Mg(1-x)FexSiO3_E20_5-1000mic_300K_extrapol.data.txt | 数表 | 長波長プロキシ |

### B. HKL（液相・検証済み）

| 文献 | 対象 | 係数 | 適用温度 | 数表/図 | 備考 |
|---|---|---|---|---|---|
| Schaefer & Fegley 2004 Table 7 | Basalt (Tholeiites/Alkalis) | log10 P(bar)=A+B/T | 1700–2400 K（図示範囲） | 数表 | 液相のみ。Tliq を下限に適用 |

### C. 固相プロキシ候補（検証済み）

| 文献 | 対象 | 式/係数 | 取得先URL | 数表/図 | 注意 |
|---|---|---|---|---|---|
| Love & Brownlee 1991 | stony micrometeoroids | log Pv = A − B/T（A=10.6,B=13500, dyn/cm^2） | https://doi.org/10.1016/0019-1035(91)90085-8 | 数表 | 固相プロキシ |
| Kobayashi 2011 | obsidian / pyroxene / olivine | Eq.5 + Table 1 | https://doi.org/10.5047/eps.2011.03.012 | 数表 | 固相プロキシ |
| Kimura 1997 | silicate dust | Eq.6 + Table 1 | https://ui.adsabs.harvard.edu/abs/1997A%26A...326..263K/abstract | 数表 | 固相プロキシ |
| Genge 2017 | basaltic micrometeorites | exp(A − B/T), A=9.6, B=26700 | https://doi.org/10.1111/maps.12830 | 数表 | 固相プロキシ |

---

## Appendix A: 未検証候補一覧（貼り付けメモ）

| データセット | 材料 | 波長範囲 | 取得先URL | ファイル名 | 数表/図 | 注意 |
|---|---|---|---|---|---|---|
| Arakawa 1991 | Basaltic glass | 0.0173–50 µm | https://doi.org/10.1017/S0252921100066574 | PDFのみ | 図のみ | 数表未取得 |
| Egan 1975 (ARIA 内記載) | Basalt | 不明 | https://doi.org/10.1016/0019-1035(75)90029-9 | 未取得 | 未確認 | 波長範囲未確認 |

---

## Appendix B: 検証メモ（詳細）

### STOPCODA 実データ点検（抜粋）
- 測定域: 5–1000 µm（サンプル依存）、外挿込みで 0.024–100000 µm を含む。
- 列定義: `wavelength(micron)`, `real_intensity`, `imaginary_intensity` ほか。
- E20（非R）は 500–1000 µm が連続で欠損なし。

### Table 7 の単位換算メモ
- `log10 P_sat(bar) = A + B/T` → `log10 P_sat(Pa) = (A+5) + B/T`

---

## 実装タスク（チェックリスト）

- [ ] `material_basalt_liq.override` を作成し、液相 HKL のみ有効化  
- [ ] `material_basalt_solid_proxy_<material>.override` を作成し、固相プロキシを選択  
- [ ] Q_pr 連結ルール（波長グリッド、欠損処理、連結点）を明文化し、run_card に記録  
- [ ] `run_config.json` に Q_pr 連結点と HKL 固液切替条件を記録する  
- [ ] 0D 最小検証を実行し、`summary.json` / `checks/mass_budget.csv` を確認  
- [ ] `docs/plan/20251226_material_properties_current_defaults.md` に相別モード追加の追記  

---

## 受入条件（相別モード）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内  
- `series/run.parquet` の主要列（`a_blow`, `beta_at_smin_*`, `M_out_dot`）が生成される  
- `run_config.json` に **Q_pr の連結点**と **HKL の固液切替条件（または無効化条件）**が記録される  
- Basalt-Liquid 実行では **固相 HKL が無効**である  
- Basalt + Solid-Proxy 実行では **プロキシ材料名**が明示される  

---

## リスクと注意点

- Q_pr 連結の補間方針が結果に直接影響するため、連結ルールのログが必須  
- 固相プロキシは玄武岩固相ではないため、**上限評価**として扱う  

---

## 次フェーズ

- 玄武岩の光学定数や固相蒸気圧の文献確定が進んだら、統一モードの再検討を行う。
