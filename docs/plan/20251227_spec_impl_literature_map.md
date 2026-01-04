# 仕様・実装・先行研究（DOI付き）整理メモ

## 0. 目的 / 対象 / 期待する成果

この文書は、外部の読者が **この1ファイルだけ**で以下を理解できることを目的とします。

- 仕様（analysis）と実装（code）がどこで対応しているか
- どの先行研究（DOI付き）がどの機能に結び付くか
- 既知の問題点や未確定事項がどこにあるか
- どの出力を見れば検証できるか

対象は **0D（半径無次元）** の衝突円盤シミュレーションを主とし、1D 拡張は補助扱いです。

## 1. 前提とスコープ

- gas-poor 円盤が既定であり、TL2003 の gas-rich 表層流は `ALLOW_TL2003=false` を標準とします。
- 仕様の一次ソースは `analysis/` であり、この文書は **計画・整理用途**です。
- 実行再現性は `configs/` と `analysis/run-recipes.md` を起点に行います。

## 2. 読み方（最短手順）

1. **仕様の正**として `analysis/equations.md` を開き、E.ID を確認する。
2. **実装の正**として `marsdisk/...` にある対応モジュールを確認する。
3. **文献の正**として `analysis/references.registry.json` を見て DOI を確認する。
4. 本文の「問題点・ギャップ」セクションで、既知の差分や未確定事項を把握する。

## 3. 記法と対応ルール

- E.xxx: `analysis/equations.md` の式ID
- Key: `analysis/references.registry.json` の文献キー
- DOI: レジストリ上の DOI 文字列
- `marsdisk/...`: 実装コードのパス

## 4. 仕様・実装の全体像（0D パイプライン）

0D 経路の主要な処理フローは以下です。

1. YAML 設定読み込み（`configs/*.yml`）
2. 代表半径から `Omega`, `v_K` を計算
3. Q_pr テーブル読み込み → beta 計算 → blow-out 半径 a_blow
4. s_min を設定（config, blow-out, surface-energy, sublimation 由来の候補から決定）
5. 供給率を設定し、表層/内部へ配分
6. 衝突カーネル C_ij を計算し、Smoluchowski で PSD を更新
7. 表層 ODE で outflux（M_out_dot）とシンクを評価
8. 出力ファイルと質量保存ログを生成

## 5. 仕様 ↔ 実装 トレーサビリティ（概要表）

**状態定義**
- 一致: 仕様と実装が一致することを確認済み
- 不一致: 差分を確認済み

| 領域 | 仕様（式ID） | 実装（コード） | 状態 | 備考 |
| --- | --- | --- | --- | --- |
| 放射圧・ブローアウト | `E.005, E.008, E.012-E.014` | `marsdisk/physics/radiation.py`, `marsdisk/io/tables.py`, `marsdisk/run_zero_d.py` | 一致（仕様更新済み） | E.014 に「Q_pr(s) を数値的に解く」旨を明記し整合 |
| 表層 ODE・アウトフロー | `E.006-E.009` | `marsdisk/physics/surface.py` | 一致 | S1 の式・符号・outflux を確認済み |
| Smol 解法（IMEX-BDF1） | `E.010-E.011` | `marsdisk/physics/smol.py` | 一致（仕様更新済み） | E.010/E.011/E.044/E.046 を実装定義に合わせて更新 |
| 衝突カーネル | `E.024` | `marsdisk/physics/collide.py` | 一致 | 1+δ_ij の扱いと H_ij 定義を確認済み |
| 破砕・残骸分率 | `E.026, E.032-E.033` | `marsdisk/physics/qstar.py`, `marsdisk/physics/fragments.py` | 一致 | Q_D* 補間・Q_R 定義・f_lr 分岐を確認済み |
| PSD 形状・最小粒径 | `E.008, E.053` | `marsdisk/run_zero_d.py`, `marsdisk/physics/psd.py` | 一致 | s_min ロジックと surface-energy floor 一般式を確認済み |
| 昇華シンク | `E.018-E.019` | `marsdisk/physics/sublimation.py`, `marsdisk/physics/sinks.py` | 一致（実装修正済み） | HKL 分岐でも eta_instant を適用 |
| 速度分散・相対速度 | `E.020-E.021` | `marsdisk/physics/dynamics.py` | 一致 | v_ij と c_eq の定義・単位を確認済み |
| 0D 統合ループ | `analysis/run-recipes.md` | `marsdisk/run_zero_d.py` | 一致 | 出力列・mass_budget ログ整合を確認済み |

## 6. 領域別の詳細マップ（仕様・実装・設定・出力・文献）

### A. 放射圧・ブローアウト
- **仕様**: `E.005`（Q_pr 表ロード）, `E.012`（Planck 平均 Q_pr）, `E.013`（beta）, `E.014`（a_blow）, `E.008`（s_min と beta 診断）
- **実装**: `marsdisk/io/tables.py`, `marsdisk/physics/radiation.py`, `marsdisk/run_zero_d.py`
- **主な設定**: `radiation.qpr_strict`, `radiation.qpr_override`, `physics.blowout.enabled`, `psd.floor.mode`
- **主な出力**: `Qpr_mean`, `beta_at_smin_config`, `beta_at_smin_effective`, `a_blow`, `s_min`, `beta_threshold`, `case_status`
- **文献**: Burns1979_Icarus40_1 (10.1016/0019-1035(79)90050-2), StrubbeChiang2006_ApJ648_652 (10.1086/505736), PawellekKrivov2015_MNRAS454_3207 (10.1093/mnras/stv2142)
- **検証観点**: `beta_at_smin_config` と `beta_threshold` の比較が `case_status` と整合するか

### B. 表層 ODE・アウトフロー（S1）
- **仕様**: `E.006`（t_coll）, `E.007`（表層 ODE）, `E.009`（outflux）
- **実装**: `marsdisk/physics/surface.py`（step_surface_density_S1, wyatt_tcoll_S1, compute_surface_outflux）
- **主な設定**: `surface.collision_solver`, `ALLOW_TL2003`, `sinks.mode`, `physics.blowout.enabled`
- **主な出力**: `Sigma_surf`, `M_out_dot`, `t_blow`, `tau`, `Sigma_tau1`
- **文献**: StrubbeChiang2006_ApJ648_652 (10.1086/505736), Wyatt2008 (10.1146/annurev.astro.45.051806.110525), TakeuchiLin2003_ApJ593_524 (10.1086/376496)
- **検証観点**: `surface.collision_solver="surface_ode"` 時のみ TL2003 系を使うこと

### C. Smoluchowski（C3/C4）
- **仕様**: `E.010`（IMEX-BDF1）, `E.011`（質量保存 C4）, `E.024`（衝突カーネル）
- **実装**: `marsdisk/physics/smol.py`, `marsdisk/physics/collide.py`
- **主な設定**: `surface.collision_solver="smol"`, `time_step.safety`, `mass_tol`
- **主な出力**: `out/<run_id>/checks/mass_budget.csv`（C4）, `out/<run_id>/series/run.parquet`
- **文献**: Krivov2006_AA455_509 (10.1051/0004-6361:20064907), Wyatt2008 (10.1146/annurev.astro.45.051806.110525), Birnstiel2011_AA525_A11 (10.1051/0004-6361/201015228)
- **注意**: E.010/E.011/E.044/E.046 は仕様更新済みで実装と整合済み

### D. 破砕・残骸分率（F1/F2）
- **仕様**: `E.026`（Q_D*）, `E.032`（Q_R）, `E.033`（最大残骸分率）
- **実装**: `marsdisk/physics/qstar.py`, `marsdisk/physics/fragments.py`
- **主な設定**: `qstar.mu_grav`, `fragments.alpha_frag`, `fragments.f_ke_fragmentation`
- **主な出力**: 破砕テンソル Y, PSD 生成フラックス
- **文献**: BenzAsphaug1999_Icarus142_5 (10.1006/icar.1999.6204), LeinhardtStewart2012_ApJ745_79 (10.1088/0004-637X/745/1/79), StewartLeinhardt2009_ApJ691_L133 (10.1088/0004-637X/691/2/L133)

### E. PSD 形状・最小粒径
- **仕様**: `E.008`（s_min）, `E.053`（surface-energy floor）
- **実装**: `marsdisk/run_zero_d.py`（_surface_energy_floor）, `marsdisk/physics/psd.py`
- **主な設定**: `psd.alpha`, `psd.wavy_strength`, `surface_energy.*`
- **主な出力**: `s_min_effective`, `s_min_surface_energy`, `out/<run_id>/series/psd_hist.parquet`
- **文献**: Dohnanyi1969_JGR74_2531 (10.1029/JB074i010p02531), ThebaultAugereau2007_AA472_169 (10.1051/0004-6361:20077709), KrijtKama2014_AA566_L2 (10.1051/0004-6361/201423862)

### F. 昇華シンク
- **仕様**: `E.018`（HKL 質量フラックス）, `E.019`（sink timescale）
- **実装**: `marsdisk/physics/sublimation.py`, `marsdisk/physics/sinks.py`
- **主な設定**: `sinks.mode`, `sinks.sub_params.psat_model`, `sinks.sub_params.P_gas`, `sinks.sub_params.enable_liquid_branch`, `sinks.sub_params.mass_conserving`
- **主な出力**: `mass_lost_by_sinks`, `t_sink`, `s_min` の昇華由来変化
- **文献**: Pignatale2018_ApJ853_118 (10.3847/1538-4357/aaa5b2), Ronnet2016_ApJ828_109 (10.3847/0004-637X/828/2/109), VisscherFegley2013_ApJL767_L12 (10.1088/2041-8205/767/1/L12)

### G. 速度分散・相対速度
- **仕様**: `E.020`（v_ij）, `E.020b`（近点速度）, `E.021`（c_eq）
- **実装**: `marsdisk/physics/dynamics.py`, `marsdisk/physics/collisions_smol.py`
- **主な設定**: `dynamics.v_rel_mode`, `dynamics.f_wake`, `dynamics.e0`, `dynamics.i0`
- **主な出力**: `v_rel`, `c_eq`, `t_coll` 関連診断
- **文献**: Ohtsuki2002_Icarus155_436 (10.1006/icar.2001.6741), WetherillStewart1993_Icarus106_190 (10.1006/icar.1993.1161)

### H. gas-poor 前提と Mars 円盤の背景
- **仕様**: `analysis/overview.md`, `analysis/AI_USAGE.md`
- **実装**: `configs/base.yml`, `marsdisk/run_zero_d.py` のデフォルト
- **文献**: Hyodo2017a_ApJ845_125 (10.3847/1538-4357/aa80e4), Hyodo2017b_ApJ851_122 (10.3847/1538-4357/aa9cec), Hyodo2018_ApJ860_150 (10.3847/1538-4357/aac024), CanupSalmon2018_SciAdv4_eaar6887 (10.1126/sciadv.aar6887), Kuramoto2024 (10.1146/annurev-earth-031621-064742)

## 7. 主要な出力と検証基準

### 出力ファイル
- `out/<run_id>/series/run.parquet`
  - 必須列の例: `time`, `dt`, `tau`, `a_blow`, `s_min`, `prod_subblow_area_rate`, `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks`
- `out/<run_id>/summary.json`
  - 必須キーの例: `M_loss`, `case_status`, `dt_over_t_blow_median`, `mass_budget_max_error_percent`
- `out/<run_id>/checks/mass_budget.csv`
  - 主要列: `time`, `mass_initial`, `mass_remaining`, `mass_lost`, `mass_diff`, `error_percent`, `tolerance_percent`

### 検証基準（代表）
- `out/<run_id>/checks/mass_budget.csv` の `error_percent <= 0.5%` を満たすこと
- `sinks.mode="none"` の場合、`mass_lost_by_sinks` が 0 になること
- `case_status` が `beta_at_smin_config` と `beta_threshold` の比較に一致すること

### ストリーミング I/O
- 既定はオン（`io.streaming`）
- 軽量ケースでは `IO_STREAMING=off` または `FORCE_STREAMING_OFF=1` で明示的にオフ

## 8. 再現・確認のための実行例

- 代表例（0D）:
  - `python -m marsdisk.run --config configs/base.yml`
- 既定の確認ポイント:
  - `out/<run_id>/checks/mass_budget.csv` の `error_percent` を確認
  - `out/<run_id>/summary.json` の `M_loss`, `case_status` を確認

## 9. 問題点・ギャップ（この文書だけで把握できる一覧）

### 9.1 仕様更新・実装修正で解消済み

| ID | 内容 | 対応 | 実施内容 | 影響 |
| --- | --- | --- | --- | --- |
| C3-Gain | Smol gain 項の質量重み | 仕様更新済み | `E.010/E.046` を `(m_i+m_j)/m_k` + 上三角和に統一 | 生成項定義が実装と一致 |
| C3-Loss | Smol loss の対角補正 | 仕様更新済み | `E.010` に `+C_kk` を明記し `Lambda_i` を更新 | 自己衝突の損失率定義が一致 |
| C4-Budget | 質量保存式に追加損失項 | 仕様更新済み | `E.011` に `extra_mass_loss_rate` を追加 | mass budget ログの意味が一致 |
| E44-Diag | t_coll_min の対角補正 | 仕様更新済み | `E.044` を `sum C_ij + C_ii` 形に更新 | t_coll_min の評価が一致 |
| E19-Eta | s_sink の eta_instant 取扱い | 実装修正済み | HKL 分岐でも `eta_instant` を適用 | HKL 分岐での s_sink が仕様に一致 |
| E14-Iter | blowout 半径の Q_pr 取扱い | 仕様更新済み | `E.014` を `Q_pr(s)` を含む数値解として明記 | s_blow の定義が実装と一致 |

補足: E.027 は `evaluate_supply` 内で `rate=max(rate,0)` を行っており、非負クリップは仕様通りに一致を確認済み。

#### 9.1.1 E14-Iter の詳細（仕様更新済み）

**何が論点か（簡潔）**  
`s_blow` は「放射圧/重力比 `β=0.5` となる粒径」だが、`β` の式に入る `Q_pr` が粒径依存のため、**`s_blow` を閉形式で一発評価するか、反復で自己整合させるか**で値が変わる。

**仕様（analysis/equations.md: E.014, 更新後）**  
- `Q_pr(s)` を含めた `β(s)=0.5` の **数値解**として `s_blow` を求める。  
- アルゴリズムは固定しない（固定点反復・root finding などを許容）。  
- `Q_pr` が定数指定される場合は閉形式を許容する。

**実装（marsdisk/physics/radiation.py: blowout_radius）**  
- `Q_pr` が明示指定された場合は、**閉形式**で `s_blow` を返す（仕様と一致）。  
- `Q_pr` が未指定の場合は、**固定点反復**で `s_blow` を自己整合させる。  
  - 初期値: `s=1 m` の `Q_pr` から `s_blow` を仮置き  
  - 更新式: `s_new = coef * Q_pr(s_old)`（`coef` は定数係数）  
  - 反復: 最大 8 回、相対差が十分小さければ停止  
  - `Q_pr(s)` はテーブル補間またはフォールバック値から取得

**差分が出る条件（過去の不一致原因）**  
- `Q_pr` テーブルが **粒径依存**である場合に差が顕在化していた。  
- 仕様を数値解に更新したため、この差分は **解消済み**。

**影響範囲（外部に見える変化）**  
- 出力列: `a_blow`, `s_min`, `beta_at_smin_effective`, `case_status`  
- 物理挙動: `s_min` が変わるため、`prod_subblow_area_rate`、`M_out_dot`、`M_loss`、wavy PSD の強弱に波及しうる  
- どちらの方向に変化するかは **`Q_pr(s)` のテーブル形状次第**

**決定した方針（採用済み）**  
- 仕様を **「`Q_pr(s)` を含む数値解」**に更新し、実装（固定点反復）と整合させる。  
- 具体的な数値アルゴリズムは仕様で拘束しない。

### 9.2 仕様と実装の差分（未解消）

現時点で未解消の差分はなし。

### 9.3 文献整備の欠落（DOIまたはレジストリ）

| Key | 現状 | 影響 |
| --- | --- | --- |
| FegleySchaefer2012_arXiv | DOI 未登録 | 溶融 SiO2 蒸気圧の根拠が曖昧になる |
| LissauerStewart1993_PP3 | DOI 空欄 | 低 e, i 速度スケーリングの引用が曖昧になる |
| Thebault2003_AA408_775 | レジストリ登録済み | PSD/エネルギー簿記の引用整合を回復 |

### 9.4 仕様と文献の整合が未確定（要確認）

現時点で未確定の項目はなし（調査完了済み）。

### 9.5 進捗まとめ（チェックリストの運用ルール）

本ドキュメントは「**仕様と実装の一致/不一致を網羅的に監査する台帳**」として運用する。  
チェックボックスは **“監査完了”** を示し、**一致/不一致の結果は各項目の末尾に明記**する。

### 9.6 監査チェックリスト（結果: 一致/不一致）

**監査完了（一致）**
- [x] 放射圧・ブローアウト（`E.005, E.008, E.012–E.014`）: 一致（仕様更新済み）
- [x] 表層 ODE・アウトフロー（`E.006–E.009`）: 一致
- [x] 衝突カーネル（`E.024`）: 一致
- [x] 破砕・残骸分率（`E.026, E.032–E.033`）: 一致
- [x] PSD 形状・最小粒径（`E.008, E.053`）: 一致
- [x] 速度分散・相対速度（`E.020–E.021`）: 一致
- [x] 0D 統合ループ（`analysis/run-recipes.md`）: 一致

**監査完了（不一致: 文献レジストリ）**
- [x] 文献レジストリの DOI 欠落補完: `FegleySchaefer2012_arXiv`, `LissauerStewart1993_PP3`, `Thebault2003_AA408_775`

## 10. テストと検証の入口

代表的な試験は以下に集約されています（詳細は各テストファイルを参照）。

- `tests/unit/test_wyatt_scaling.py`: Wyatt スケールの t_coll 比例関係
- `tests/integration/test_surface_outflux_wavy.py`: blow-out 由来の wavy PSD 指標
- `tests/integration/test_smol_consistency_checks.py`: Smol 質量保存や dt 制約の整合

## 11. 文献一覧（DOI付き）

### 放射圧・ブローアウト
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Burns1979_Icarus40_1 | [@Burns1979_Icarus40_1] *Radiation forces on small particles in the solar system* | 10.1016/0019-1035(79)90050-2 | beta, a_blow（E.012-E.014） |
| StrubbeChiang2006_ApJ648_652 | [@StrubbeChiang2006_ApJ648_652] *Dust Dynamics in Debris Disks* | 10.1086/505736 | t_coll, beta=0.5（E.006-E.007） |
| PawellekKrivov2015_MNRAS454_3207 | [@PawellekKrivov2015_MNRAS454_3207] *Dust grain size-luminosity trend* | 10.1093/mnras/stv2142 | Q_pr テーブルの使用例 |

### 衝突・Smoluchowski
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Krivov2006_AA455_509 | [@Krivov2006_AA455_509] *Dust distributions in debris disks* | 10.1051/0004-6361:20064907 | C_ij と IMEX（E.010-E.011, E.024） |
| Wyatt2008 | [@Wyatt2008] *Evolution of Debris Disks* | 10.1146/annurev.astro.45.051806.110525 | t_coll スケール |
| Birnstiel2011_AA525_A11 | [@Birnstiel2011_AA525_A11] *Dust size distributions in coagulation/fragmentation equilibrium* | 10.1051/0004-6361/201015228 | ビン分解能 |

### 破砕・残骸分率
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| BenzAsphaug1999_Icarus142_5 | [@BenzAsphaug1999_Icarus142_5] *Catastrophic Disruptions Revisited* | 10.1006/icar.1999.6204 | Q_D* 係数 |
| LeinhardtStewart2012_ApJ745_79 | [@LeinhardtStewart2012_ApJ745_79] *Collisions between gravity-dominated bodies* | 10.1088/0004-637X/745/1/79 | 破壊スケーリング |
| StewartLeinhardt2009_ApJ691_L133 | [@StewartLeinhardt2009_ApJ691_L133] *Velocity-dependent catastrophic disruption criteria* | 10.1088/0004-637X/691/2/L133 | Q_R / 残骸分率 |

### PSD 形状・最小粒径
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Dohnanyi1969_JGR74_2531 | [@Dohnanyi1969_JGR74_2531] *Collisional Model of Asteroids and Their Debris* | 10.1029/JB074i010p02531 | PSD スロープ |
| ThebaultAugereau2007_AA472_169 | [@ThebaultAugereau2007_AA472_169] *Collisional processes and size distribution in debris discs* | 10.1051/0004-6361:20077709 | wavy PSD |
| KrijtKama2014_AA566_L2 | [@KrijtKama2014_AA566_L2] *A dearth of small particles in debris disks* | 10.1051/0004-6361/201423862 | s_min 上昇 |

### 昇華・熱物性
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Pignatale2018_ApJ853_118 | [@Pignatale2018_ApJ853_118] *On the Impact Origin of Phobos and Deimos III* | 10.3847/1538-4357/aaa5b2 | SiO 蒸気優勢 |
| Ronnet2016_ApJ828_109 | [@Ronnet2016_ApJ828_109] *Reconciling the orbital and physical properties of the Martian moons* | 10.3847/0004-637X/828/2/109 | gas-poor 条件 |
| VisscherFegley2013_ApJL767_L12 | [@VisscherFegley2013_ApJL767_L12] *Chemistry of impact-generated silicate melt-vapor debris disks* | 10.1088/2041-8205/767/1/L12 | 溶融 SiO2 蒸気圧 |
| Bruning2003_JNCS330_13 | [@Bruning2003_JNCS330_13] *On the glass transition in vitreous silica* | 10.1016/j.jnoncrysol.2003.08.051 | ガラス転移 |
| Ojovan2021_Materials14_5235 | [@Ojovan2021_Materials14_5235] *On Structural Rearrangements Near the Glass Transition Temperature in Amorphous Silica* | 10.3390/ma14185235 | 融解温度 |

## 12. 調査結果に基づく実装タスク（動的更新）

### 12.1 運用方針
- ここに載せる実装タスクは **調査結果で「実装修正が必要」と判断された項目のみ**とする。
- 「仕様修正で解決」「定義差を許容」の場合は、この節から削除し、該当セクションの記録だけを更新する。
- 各タスクには必ず §9 の ID を付け、判断根拠（文献・仕様・実装）を明記する。

### 12.2 現時点の実装タスク（候補）
現時点で実装修正を要する差分はなし。

## 13. 調査対象外の将来拡張（別管理）

この節は **不一致調査とは独立**の将来拡張案であり、進捗管理は別途行う。

### 13.1 目的と範囲
- **目的**: 半径依存の離心率 `e(r)` を設定し、衝突カーネルの相対速度に反映する。
- **対象**: 0D/1D の両方。0D でも `e_profile` を評価して `dynamics.e0` を置き換える。
- **非対象**: `i(r)` の導入は行わない（`i0` は固定）。

### 13.2 仕様案（設定と入力）
- `dynamics.e_profile` を新設（mode とパラメータ指定）。
- **既定は `mode="mars_pericenter"`** とし、`off` と `table` は非推奨（警告を出す）。
- `mode="table"` の場合は CSV 固定（列: `r_RM` または `r_m`, `e`）。単調増加を要求し、範囲外は端値でクランプ。
- `mode="mars_pericenter"` の場合は **各セル半径 r** から `e=1-R_Mars/r` を計算する（0D も同様に r で評価）。
- `r<=R_Mars` の場合は **警告** を出し、`e=0` にクランプする。
- `e_mode="mars_clearance"` との併用は不可（衝突回避のためエラー）。

### 13.3 実装タスク（別管理）
- [x] `marsdisk/schema.py` に `DynamicsEccentricityProfile` を追加し、`Dynamics` に `e_profile` を持たせる。
- [x] `e_profile.mode` を `off|table|mars_pericenter` とし、既定は `mars_pericenter`。`off` と `table` を非推奨扱い（警告ログ）。
- [x] `e_profile.mode="table"` は `table_path` 必須、`r_kind=r_RM|r_m`、`clip_min/clip_max` を導入。
- [x] 0D/1D 共通のロード関数を `marsdisk/io/tables.py` か `marsdisk/physics/dynamics.py` に追加する。
- [x] テーブル読込: `pandas.read_csv` → 列名検証 → `r` 昇順チェック → 線形補間関数を返す。
- [x] `mars_pericenter` 計算: `e=1-R_Mars/r` を評価し、`[0, 0.999999]` にクランプする（`r<=R_Mars` は警告）。
- [x] 0D: `marsdisk/run_zero_d.py` で参照半径 `r` 計算後に `e_profile` を評価し `e0_effective` を上書き。
- [x] 0D: `e_profile` 有効時は `e_mode="fixed"` のみ許可し、他は `ConfigurationError`。
- [x] 1D: `marsdisk/run_one_d.py` のセル半径配列から `e_cells` を事前計算。
- [x] 1D: 各セルで `cfg.dynamics.model_copy(update={"e0": e_cell})` を用意し、`CollisionStepContext` に渡す。
- [x] 1D: `out/<run_id>/series/run.parquet` に `e_value`（セルごとの適用値）を追加する。
- [x] `out/<run_id>/run_config.json` の `init_ei` に以下を記録する: `e_profile_mode`, `e_profile_r_kind`, `e_profile_table_path`, `e_profile_formula`（`mars_pericenter` 時のみ）, `e_profile_applied`
- [x] テスト: テーブル補間の一致、0D で `e_profile` が `e0` を置換、1D でセルごとに `e_kernel_base` が変わることを確認。
- [x] ドキュメント: `analysis/overview.md` と `analysis/run-recipes.md` に設定例を追加（本変更実装後に更新）。

### gas-poor 前提・火星円盤背景
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Hyodo2017a_ApJ845_125 | [@Hyodo2017a_ApJ845_125] *On the Impact Origin of Phobos and Deimos I* | 10.3847/1538-4357/aa80e4 | 初期条件 |
| Hyodo2017b_ApJ851_122 | [@Hyodo2017b_ApJ851_122] *On the Impact Origin of Phobos and Deimos II* | 10.3847/1538-4357/aa9cec | 円盤緩和 |
| Hyodo2018_ApJ860_150 | [@Hyodo2018_ApJ860_150] *On the Impact Origin of Phobos and Deimos IV* | 10.3847/1538-4357/aac024 | 放射冷却 |
| CanupSalmon2018_SciAdv4_eaar6887 | [@CanupSalmon2018_SciAdv4_eaar6887] *Origin of Phobos and Deimos...* | 10.1126/sciadv.aar6887 | 低質量円盤 |
| Kuramoto2024 | [@Kuramoto2024] *Origin of Phobos and Deimos Awaiting Direct Exploration* | 10.1146/annurev-earth-031621-064742 | 総説 |

### 軌道力学・速度スケーリング
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| Ohtsuki2002_Icarus155_436 | [@Ohtsuki2002_Icarus155_436] *Evolution of Planetesimal Velocities...* | 10.1006/icar.2001.6741 | v_rel, c_eq |
| WetherillStewart1993_Icarus106_190 | [@WetherillStewart1993_Icarus106_190] *Formation of planetary embryos* | 10.1006/icar.1993.1161 | v_rel レイリー |

### gas-rich 参考（既定は無効）
| Key | 文献 | DOI | 主な関係先 |
| --- | --- | --- | --- |
| TakeuchiLin2003_ApJ593_524 | [@TakeuchiLin2003_ApJ593_524] *Dust Outflows in Optically Thick Gas Disks* | 10.1086/376496 | TL2003 表層 ODE |

## 14. 更新時の注意

- 文献キーと DOI は `analysis/references.registry.json` を正として更新する。
- `analysis/equations.md` に新しい E.ID を追加した場合は、この文書の対応表と問題点を必ず再点検する。
- 本文の「問題点・ギャップ」は、検証後に必ず更新して状態を反映する。
