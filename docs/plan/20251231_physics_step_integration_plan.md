# physics_step 実務統合プラン（0D優先）

> **作成日**: 2025-12-31  
> **ステータス**: フェーズ1完了（2026-01-01更新）  
> **対象**: `marsdisk/run_zero_d.py`, `marsdisk/physics_step.py`, `marsdisk/physics/*`, `marsdisk/io/*`, `marsdisk/runtime/*`

---

## 目的

- `run_zero_d` の巨大化を止め、**物理更新とI/O/制御を分離**して保守性を上げる
- `physics_step.py` を**実運用の1ステップAPI**として段階的に導入する
- 高〜中のボトルネック（巨大ループ、グローバル状態、二重実装、cfgの破壊更新、I/O密結合）を優先的に緩和する

---

## 背景

- `run_zero_d` は設定解決〜物理計算〜診断〜出力まで同一関数に集中しており、変更時の影響範囲が広い
- `physics_step.py` は分割方針を示すが、実行経路で未使用のため二重実装の状態
- 放射・Q* などのグローバル状態更新が実行経路に埋め込まれており、再実行/テスト分離が難しい
- 物理ロジックとストリーミングI/Oが密結合で、物理変更が出力経路に波及しやすい

---

## スコープ

- 0D のみを対象（`run_one_d` は非スコープ）
- 物理式・出力列・単位・YAMLスキーマの互換性は維持
- `physics_step.py` を**実務寄りに段階導入**し、最初は4系（放射・遮蔽・昇華・表層）を対象

## 非スコープ

- 新しい物理式やパラメータ導入
- 出力フォーマットの破壊的変更
- 1Dのロジック統合（別プラン）

---

## 短期スコープ / 優先度（確定）

**短期（直近実装対象）**: フェーズ0〜1  
**中期（安定化フェーズ）**: フェーズ2  
**長期（設計改善）**: フェーズ3〜5

短期は「数値パリティを保ったまま `physics_step` を実運用へ導入する」ことに集中し、\n中期以降は重複実装の削減と状態管理/I/O結合の整理に進む。

---

## 方針（実務寄り）

- `run_zero_d` はオーケストレーションに集中し、**計算の「まとまり」だけを `physics_step` に移す**
- I/Oやストリーミングは現状維持し、**数値差分が出ない範囲**から置換
- 置換前後でパリティ確認（タイムシリーズ/summary/質量収支）を必ず行う

---

## 段階計画

### フェーズ0: ベースライン固定

- 既存の0D基準ケースの出力を固定（summary/mass_budget/series）
- 差分比較のためのスモーク検証スクリプトを用意

#### フェーズ0ベースライン対象ケース（確定）

1) **collisions_only**  
   - config: `configs/innerdisk_collisions_only.yml`  
   - 目的: ブローアウト主体（昇華・ガス抗力なし）の最小系

2) **sublimation_only**  
   - config: `configs/innerdisk_sublimation_only.yml`  
   - 目的: 昇華のみ（ブローアウト無効）の損失パス確認

3) **fiducial_combined**  
   - config: `configs/innerdisk_fiducial.yml`  
   - 目的: 衝突 + ブローアウト + 昇華 + 相状態分岐の統合ケース

#### フェーズ0ベースライン実行コマンド（確定）

共通ルール:
- `FORCE_STREAMING_OFF=1` でストリーミングを明示的にOFF
- outdirは `out/plan/physics_step_baseline/<case-id>/<ref|new>` で分離
- 参照実行は「現行実装」、`new` は置換後の候補で実行

例:
- collisions_only
  - ref: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_collisions_only.yml --override io.outdir=out/plan/physics_step_baseline/collisions_only/ref`
  - new: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_collisions_only.yml --override io.outdir=out/plan/physics_step_baseline/collisions_only/new`
- sublimation_only
  - ref: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_sublimation_only.yml --override io.outdir=out/plan/physics_step_baseline/sublimation_only/ref`
  - new: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_sublimation_only.yml --override io.outdir=out/plan/physics_step_baseline/sublimation_only/new`
- fiducial_combined
  - ref: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_fiducial.yml --override io.outdir=out/plan/physics_step_baseline/fiducial_combined/ref`
  - new: `FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/innerdisk_fiducial.yml --override io.outdir=out/plan/physics_step_baseline/fiducial_combined/new`

注: 既定のストリーミングONを避けるため、CI/ローカル双方で `FORCE_STREAMING_OFF=1` を固定する。

#### フェーズ0差分比較ツール仕様（確定）

- **ツール配置**: `scripts/tools/compare_zero_d_outputs.py`（新規）
- **入力**: `--ref <outdir> --new <outdir> --case-id <id> --outdir <dir>`  
  - `--outdir` 省略時は `out/plan/physics_step_baseline/<case-id>` を自動使用
  - 追加オプション: `--summary-keys`, `--summary-rtol`, `--summary-atol`, `--series-rtol`, `--series-atol`, `--series-include`, `--series-exclude`, `--include-non-numeric`
- **前提実行**: `FORCE_STREAMING_OFF=1` で実行し、`--override io.outdir=<outdir>` で出力先を分離
- **比較対象**:
  - `out/<run_id>/summary.json`
  - `out/<run_id>/series/run.parquet`
  - `out/<run_id>/checks/mass_budget.csv`
- **比較ルール（合格条件）**:
  - `out/<run_id>/summary.json`: 指定キーが全て存在し、数値は `rtol=1e-6, atol=1e-12` 以内  
    対象キー: `M_loss`, `M_out_cum`, `M_sink_cum`, `mass_budget_max_error_percent`, `dt_over_t_blow_median`, `beta_at_smin_config`, `beta_at_smin_effective`
  - `out/<run_id>/series/run.parquet`: 行数が一致し、列は union に欠落がないこと（欠落があれば fail）  
    数値列は `rtol=1e-6, atol=1e-10` 以内（最大差分で評価）  
    非数値列はデフォルトで比較対象外（`--include-non-numeric` または `--series-include` で比較可）
  - `out/<run_id>/checks/mass_budget.csv`: 両者とも `error_percent <= 0.5` を満たすこと
- **出力**:
  - `out/plan/physics_step_baseline/<case-id>/compare.json`
    - `status`: `pass` / `fail`
    - `case_id`, `ref_dir`, `new_dir`
    - `missing_files`: list
    - `summary_diff_max`: dict（キーごとの最大差分）
    - `series_diff_max`: dict（列ごとの最大差分）
    - `summary_keys_compared`: list（実際に比較した summary キー）
    - `series_columns_compared`: list（比較対象の series 列）
    - `series_columns_skipped`: list（スキップした非数値列）
    - `tolerances`: dict（summary/series の rtol/atol）
    - `mass_budget_max_error_percent`: dict（ref/new）
  - `out/plan/physics_step_baseline/<case-id>/compare.md`（要約）
- **終了コード**:
  - 0: pass
  - 2: 入力不足（ファイル欠落）
  - 3: 数値差分超過

### フェーズ1: 物理ステップの分割（最小置換）

- `physics_step.compute_radiation_parameters`
- `physics_step.compute_shielding`
- `physics_step.compute_sublimation`
- `physics_step.step_surface_layer`

この4関数に**同じ入出力を渡すアダプタ**を `run_zero_d` 側で作り、結果を現行の記録/診断/集計に反映する。

#### フェーズ1 置換対象ブロック範囲（確定）

**置換するブロック（run_zero_d内の計算単位）**
- 放射圧パラメータ: ⟨Q_pr⟩, β, a_blow の算出（`compute_radiation_parameters`）
- 自遮蔽/光学厚さ: τ, Φ, κ_eff, Σ_τ=1 の算出（`compute_shielding`）
- 昇華・粒径ドリフト: 粒子温度, ds/dt, PS D 床更新の入力値（`compute_sublimation`）
- 表層更新: Σ_surf, outflux, sink_flux, t_blow, t_coll の算出（`step_surface_layer`）

**置換しないブロック（フェーズ1の非対象）**
- 供給・混合・spill（supply/mixing/feedback/reservoir）
- Smoluchowski IMEX/BDF と破砕カスケード（C1–C4）
- 相状態評価/温度ドライバ/ゲート係数（phase/temperature/tau_gate）
- 質量収支/エネルギー収支の集計とI/O（streaming/summary/checks）

**適用方針**
- `run_zero_d` 側で「元の入力 → `physics_step` 呼び出し → 同じ記録列へ反映」のみ行う
- 置換前後で `out/<run_id>/series/run.parquet` と `out/<run_id>/summary.json` の主要列の一致を必須条件にする

#### フェーズ1 アダプタ差し込み位置（確定）

**放射圧アダプタ（step毎）**
- 差し込み位置: `if eval_requires_step or step_no == 0:` ブロック内で、`_resolve_blowout` / `qpr_mean_step` / `beta_at_smin_effective` を算出している箇所を置換  
  - 目安: `marsdisk/run_zero_d.py` の `2102` 付近（`_resolve_blowout` 呼び出しと `beta_at_smin_effective` の更新）
- 置換範囲: blowout半径の反復計算 + Q_pr/βの評価のみ  
- 既存ロジック保持: `s_min_effective` のクリップと `s_min_components` の更新順序は維持

**昇華アダプタ（step毎）**
- 差し込み位置: `ds_dt_raw`/`ds_dt_val` を計算して `psd.apply_uniform_size_drift` を呼ぶ直前  
  - 目安: `marsdisk/run_zero_d.py` の `2218` 付近（`grain_temperature_graybody`〜`ds_dt_val`）
- 置換範囲: ds/dt の算出と相状態ブロック判定のみ  
- 既存ロジック保持: `s_min_floor_dynamic` 更新と `psd.apply_uniform_size_drift` の順序は維持

**遮蔽アダプタ（surface_ode: substep/非substep共通）**
- 差し込み位置: `collision_solver_mode == "surface_ode"` の `for _sub_idx` ループ内  
  - 目安: `marsdisk/run_zero_d.py` の `2457` 付近（`sigma_for_tau` 計算直後）
- 置換範囲: `tau_los` / `kappa_eff` / `sigma_tau1_limit` / `phi_effective` の算出
- 既存ロジック保持: `tau_los_last` と `phi_effective_last` の更新位置は維持

**遮蔽アダプタ（non-surface_ode / smol）**
- 差し込み位置: `collision_solver_mode != "surface_ode"` の `if surface_active:` ブロック内  
  - 目安: `marsdisk/run_zero_d.py` の `2589` 付近（`sigma_for_tau` 計算直後）
- 置換範囲: `tau_los` / `kappa_eff` / `sigma_tau1_limit` / `phi_effective` の算出
- 既存ロジック保持: `tau_eval_los` は衝突カスケードへ渡す値として維持

**表層アダプタ（surface_odeのみ）**
- 差し込み位置: `surface.step_surface(...)` を呼ぶ箇所を置換  
  - 目安: `marsdisk/run_zero_d.py` の `2556` 付近
- 置換範囲: `sigma_surf` 更新 / `outflux_surface` / `sink_flux_surface` の算出
- 既存ロジック保持: smol経路（`collision_solver_mode == "smol"`）は対象外

#### フェーズ1 アダプタ引数組み立て表（確定）

**放射圧アダプタ（eval_requires_step or step_no==0）**

| アダプタ引数 | run_zero_d の元データ | 補足 |
| --- | --- | --- |
| `s_min_config` | `s_min_config` | サイズ床（固定） |
| `s_min_effective` | `s_min_effective` | クリップ後の下限 |
| `s_min_guess` | `psd_state.get("s_min", s_min_effective)` | 反復初期値 |
| `rho` | `rho_used` | 物質密度 |
| `T_M` | `T_use` | Mars温度 |
| `qpr_override` | `qpr_override` | `radiation.Q_pr` 指定時のみ |
| `size_floor` | `s_min_config` | `a_blow_effective = max(size_floor, a_blow_raw)` 用 |

**昇華アダプタ（step毎）**

| アダプタ引数 | run_zero_d の元データ | 補足 |
| --- | --- | --- |
| `T_M` | `T_use` | Mars温度 |
| `r_m` | `r` | 軌道半径 |
| `rho` | `rho_used` | 物質密度 |
| `sub_params` | `sub_params` | runtime_* を注入済み |
| `phase_state` | `phase_bulk_step.state` + `allow_liquid_hkl` | 液相ブロック判定に使用 |
| `enabled` | `sublimation_active` | フラグで即時無効化 |

**遮蔽アダプタ（surface_ode: substep）**

| アダプタ引数 | run_zero_d の元データ | 補足 |
| --- | --- | --- |
| `kappa_surf` | `kappa_surf` | PSDから計算済み |
| `sigma_surf` | `sigma_surf` or `sigma_surf_reference` | `freeze_sigma` を優先 |
| `mode` | `shielding_mode` | `off` / `fixed_tau1` / `psitau` |
| `phi_tau_fn` | `phi_tau_fn` | テーブル補間関数 |
| `tau_fixed` | `tau_fixed_target` | fixed_tau1用 |
| `sigma_tau1_fixed` | `sigma_tau1_fixed_target` | fixed_tau1用 |
| `los_factor` | `los_factor` | τ_LOS変換 |
| `collisions_active` | `collisions_active_step` | 無効時は `kappa_eff=kappa_surf`, `sigma_tau1=None` |

**遮蔽アダプタ（non-surface_ode / smol）**

| アダプタ引数 | run_zero_d の元データ | 補足 |
| --- | --- | --- |
| `kappa_surf` | `kappa_surf` | PSDから計算済み |
| `sigma_surf` | `sigma_surf` or `sigma_surf_reference` | `freeze_sigma` を優先 |
| `mode` | `shielding_mode` | `off` / `fixed_tau1` / `psitau` |
| `phi_tau_fn` | `phi_tau_fn` | テーブル補間関数 |
| `tau_fixed` | `tau_fixed_target` | fixed_tau1用 |
| `sigma_tau1_fixed` | `sigma_tau1_fixed_target` | fixed_tau1用 |
| `los_factor` | `los_factor` | τ_LOS変換 |
| `collisions_active` | `collisions_active_step` | 無効時は `kappa_eff=kappa_surf`, `sigma_tau1=None` |

**表層アダプタ（surface_odeのみ）**

| アダプタ引数 | run_zero_d の元データ | 補足 |
| --- | --- | --- |
| `sigma_surf` | `sigma_surf` | 入力表層密度 |
| `prod_rate` | `prod_rate` | 供給を適用した値 |
| `dt` | `dt_sub` | substep 時は `dt_sub` |
| `Omega` | `Omega_step` | Kepler角速度 |
| `tau` | `tau_for_coll` | `tau_eval_los / los_factor`（`use_tcoll`時のみ） |
| `t_sink` | `t_sink_current` | sink 有効時のみ |
| `sigma_tau1` | `sigma_tau1_active` | クリップ上限 |
| `enable_blowout` | `enable_blowout_sub` | blowoutスイッチ |
| `chi_blow` | `chi_blow_eff` | `t_blow` 用 |

#### 不足戻り値の扱い方針（確定）

- **qpr_blow**: アダプタ側で `radiation.qpr_lookup(a_blow_raw, T_use)` を評価して補完（`qpr_override` がある場合はそれを優先）。`physics_step` の戻り値拡張はフェーズ1では行わない。
- **qpr_at_smin_config / beta_at_smin_config**: `_lookup_qpr(s_min_config)` と `radiation.beta` で従来定義を維持。
- **qpr_at_smin_effective / beta_at_smin_effective**: `_lookup_qpr(s_min_effective)` と `radiation.beta` で算出し、`case_status` 判定と一致させる。
- **a_blow_effective**: `max(s_min_config, a_blow_raw)` をアダプタで生成し、`s_blow_m_effective` に反映。
- **phi_effective**: `kappa_eff / kappa_surf`（`kappa_surf<=0` の場合は `None`）で算出し、衝突無効時は `sigma_tau1=None` を強制。
- **t_coll**: surface_ode 経路では `step_surface_layer` の `t_coll` を採用し、smol 経路は従来の `t_coll_kernel_last` を維持。

#### 実装タスク分割（issue化）

- [x] **Issue P1-01: 放射圧アダプタ実装と差し込み**  
  - `eval_requires_step` ブロックにアダプタを導入  
  - `qpr_blow` / `beta_at_smin_*` の補完ロジックを実装
- [x] **Issue P1-02: 昇華アダプタ実装と差し込み**  
  - `ds_dt_raw` / `ds_dt_val` 算出部を置換  
  - `s_min_floor_dynamic` 更新順序を保持
- [x] **Issue P1-03: 遮蔽アダプタ実装（surface_ode substep）**  
  - substep ループ内の τ/Φ/κ_eff を置換  
  - `tau_los_last` / `phi_effective_last` 更新位置を維持
- [x] **Issue P1-04: 遮蔽アダプタ実装（non-surface_ode / smol）**  
  - non-substep 経路の τ/Φ/κ_eff を置換  
  - `tau_eval_los` を衝突計算へ渡す流れを保持
- [x] **Issue P1-05: 表層アダプタ実装（surface_odeのみ）**  
  - `surface.step_surface` 呼び出しを置換  
  - 高速ブローアウト補正適用順序を維持
- [x] **Issue P1-06: フェーズ0ベースライン差分比較**  
  - 3ケースで `compare_zero_d_outputs.py` を実行し、差分ゼロを確認

#### 実装順序と依存関係（確定）

**推奨順序**: P1-01 → P1-02 → P1-03 → P1-04 → P1-05 → P1-06

| Issue | 依存 | 理由 |
| --- | --- | --- |
| P1-01 | なし | 放射圧は全経路の前提（a_blow/β/ゲート判定の基礎） |
| P1-02 | P1-01 | ds/dt のブロックが `s_min`/温度/β判定と同一フェーズにあるため |
| P1-03 | P1-01, P1-02 | substep経路は放射/昇華の値を参照する |
| P1-04 | P1-03 | non-substepも同じ遮蔽APIに合わせるため段階移行 |
| P1-05 | P1-03, P1-04 | 表層更新は遮蔽（τ/κ_eff/Σ_τ=1）の結果に依存 |
| P1-06 | P1-05 | 置換が完了した状態で差分比較を実施するため |

#### ブランチ分割と検証タイミング（確定）

**ブランチ方針（推奨）**
- `feat/physics-step-p1-01-radiation`
- `feat/physics-step-p1-02-sublimation`
- `feat/physics-step-p1-03-shielding-substep`
- `feat/physics-step-p1-04-shielding-nonsubstep`
- `feat/physics-step-p1-05-surface-ode`
- `feat/physics-step-p1-06-baseline-compare`

**検証タイミング**

1) **P1-01〜P1-02 完了時（最小検証）**  
   - `pytest tests/integration/test_scalings.py -q`  
   - `python -m marsdisk.run --config configs/innerdisk_collisions_only.yml --override io.outdir=out/plan/physics_step_baseline/collisions_only/new`  
   - `python -m marsdisk.run --config configs/innerdisk_sublimation_only.yml --override io.outdir=out/plan/physics_step_baseline/sublimation_only/new`

2) **P1-03〜P1-05 完了時（全面検証）**  
   - 3ケースのベースラインを実行（ref/new）  
   - `scripts/tools/compare_zero_d_outputs.py --case-id <id> --ref <ref> --new <new>`

3) **P1-06 完了時（受入確認）**  
   - `compare.json` が全ケース `status=pass`  
   - `out/<run_id>/checks/mass_budget.csv` が `error_percent<=0.5` を満たすこと

#### 数学・物理の骨子維持（非回帰ガード）

- **結合順序**: ⟨Q_pr⟩ → β → a_blow → ds/dt → τ/Φ → 表層S1 の順序を保持
- **同一式**: 既存の反復解（`_resolve_blowout` と同等の反復回数・クリップ）を維持
- **床径ロジック**: `s_min_effective` の更新・`s_min_components` の記録順は変更しない
- **衝突カスケード**: smolの入出力や質量収支の計算は一切変更しない
- **ゲート/補正**: 高速ブローアウト補正・ゲート係数の適用順序は維持
#### フェーズ1 アダプタ入出力（確定）

**放射圧アダプタ**

入力（run_zero_d から渡す値）:
- `s_min_config`, `s_min_effective`
- `rho_used`, `T_M_used`
- `qpr_override`（指定時のみ）
- `size_floor`（`s_min_config` 由来。`a_blow_effective` のクリップに使用）

戻り値:
- `qpr_at_smin_config`, `qpr_at_smin_effective`
- `beta_at_smin_config`, `beta_at_smin_effective`
- `a_blow_raw`, `a_blow_effective`
- `qpr_blow`（既存の `Q_pr_blow` 出力互換用）

**遮蔽アダプタ**

入力:
- `kappa_surf`, `sigma_surf`
- `shielding_mode`（`off` / `fixed_tau1` / `psitau`）
- `phi_tau_fn`（テーブル補間関数）
- `tau_fixed`, `sigma_tau1_fixed`
- `los_factor`
- `collisions_active_step`（無効時は kappa_eff = kappa_surf）

戻り値:
- `tau_los`
- `kappa_eff`
- `sigma_tau1`
- `phi_effective`

**昇華アダプタ**

入力:
- `T_M_used`, `r_m`, `rho_used`, `sub_params`
- `phase_state_for_sublimation`（`allow_liquid_hkl` を反映した状態）
- `sublimation_enabled`

戻り値:
- `T_grain`
- `ds_dt_raw`
- `ds_dt`
- `blocked_by_phase`

**表層アダプタ**

入力:
- `sigma_surf`, `prod_rate`, `dt`, `Omega`
- `tau_for_coll`（`tau_los / los_factor`）
- `t_sink`（有効時のみ）
- `sigma_tau1`（上限クリップ用）
- `enable_blowout`, `chi_blow_eff`

戻り値:
- `sigma_surf_new`
- `outflux_surface`
- `sink_flux_surface`
- `t_blow`
- `t_coll`

#### 既存記録列へのマッピング（フェーズ1対象）

| アダプタ出力 | series/run.parquet への反映 | diagnostics.parquet への反映 | 備考 |
| --- | --- | --- | --- |
| `qpr_at_smin_effective` | `Qpr_mean`, `Q_pr_at_smin`, `Q_pr_used` | `qpr_mean`, `Q_pr_at_smin` | `qpr_at_smin_config` は `beta_at_smin_config` の算出に使用 |
| `beta_at_smin_effective` | `beta_at_smin_effective`, `beta_at_smin` | `beta_at_smin_effective`, `beta_at_smin` | `blowout_beta_gate` 判定に使用 |
| `beta_at_smin_config` | `beta_at_smin_config` | - | `case_status` 判定に使用 |
| `a_blow_raw` | `a_blow_step`, `a_blow`, `a_blow_at_smin`, `s_blow_m` | `a_blow_at_smin` | 既存ロジックの `a_blow_step` と同義 |
| `a_blow_effective` | `s_blow_m_effective`, `s_min_effective` | `s_min_effective` | `s_min_components` 更新に使用 |
| `qpr_blow` | `Q_pr_blow` | - | 既存互換のため保持 |
| `tau_los` | `tau`, `tau_los_mars`, `tau_mars_line_of_sight` | `tau_los_mars` | `tau_phase_*` は別ブロックで決定 |
| `kappa_eff` | `kappa`, `kappa_eff` | `kappa_eff` | `kappa_surf` は既存計算を維持 |
| `sigma_tau1` | `Sigma_tau1`, `sigma_tau1` | `sigma_tau1` | `Sigma_tau1_last_finite` は既存追跡を維持 |
| `phi_effective` | `phi_effective`, `phi_used` | `phi_effective`, `psi_shield` | - |
| `ds_dt` | `ds_dt_sublimation` | `ds_dt_sublimation` | `dSigma_dt_sublimation` の算出に使用 |
| `ds_dt_raw` | `ds_dt_sublimation_raw` | `ds_dt_sublimation_raw` | - |
| `blocked_by_phase` | `sublimation_blocked_by_phase` | `sublimation_blocked_by_phase` | - |
| `sigma_surf_new` | `Sigma_surf`, `sigma_surf` | `sigma_surf` | `Sigma_surf0` は別ロジック |
| `outflux_surface` | `outflux_surface` | - | `M_out_dot` 算出に使用 |
| `sink_flux_surface` | `sink_flux_surface` | - | `M_sink_dot` 算出に使用 |
| `t_blow` | `t_blow`, `t_blow_s`, `dt_over_t_blow` | `t_blow_s`, `dt_over_t_blow` | 高速ブローアウト判定に使用 |
| `t_coll` | `t_coll`, `ts_ratio` | - | `ts_ratio = t_blow / t_coll` |

### フェーズ2: 二重実装の整理

- `run_zero_d` 内の同等ロジックを**段階的に削減**
- `physics_step` を**唯一の実装**に寄せ、結果のみを上位に返す
- `collision_solver_mode` 分岐（surface_ode / smol）で重複する計算ブロックを共通化し、差分の責務を明確化
- `psd_state` の暗黙契約（必須キー/単位/キャッシュキー）を明文化し、辞書の寿命管理を整理する

#### フェーズ2: 共通化の対象関数/ブロック（詳細）

| 対象ブロック | 現在の主要呼び出し | 共通化で揃えるI/O（案） |
| --- | --- | --- |
| 供給+deep buffer | `supply.evaluate_supply`, `supply.split_supply_with_deep_buffer`, `_mark_reservoir_depletion` | `prod_rate`, `prod_rate_diverted`, `prod_rate_into_deep`, `deep_to_surf_rate`, `headroom`, `supply_diag` |
| 遮蔽/tau | `physics_step.compute_shielding` + `tau_for_coll` 計算 | `tau_los`, `kappa_eff`, `sigma_tau1`, `phi_effective`, `tau_for_coll` |
| 表層更新 | `surface.step_surface_layer`, `surface.step_surface_sink_only`, `collisions_smol.step_collisions` | `sigma_surf`, `outflux_surface`, `sink_flux_surface`, `t_blow`, `t_coll`, `prod_rate_effective`, `mass_error` |
| blowout補正/ゲート | `_fast_blowout_correction_factor`, `_compute_gate_factor` | `outflux_surface`, `blow_surface_total`, `fast_blowout_applied`, `gate_factor` |
| 質量収支集計 | `blow_surface_total`, `sink_surface_total`, `M_out_dot`, `M_sink_dot`, `dSigma_dt_*` | `M_out_dot`, `M_sink_dot`, `dSigma_dt_blowout`, `dSigma_dt_sinks`, `M_loss_cum` |

#### psd_state 契約（必須キー/推奨キーの明文化）

必須キー（計算に必要）
| key | type | unit | 用途 |
| --- | --- | --- | --- |
| sizes | np.ndarray | m | サイズビン中心 |
| widths | np.ndarray | m | ビン幅 |
| number | np.ndarray | unitless | 正規化された分布形状 |
| rho | float | kg/m^3 | 粒子密度 |

推奨キー（互換/再計算防止）
| key | type | unit | 用途 |
| --- | --- | --- | --- |
| s | np.ndarray | m | sizes のエイリアス（同期必須） |
| n | np.ndarray | unitless | number のエイリアス（同期必須） |
| s_min | float | m | PSD下限 |
| s_max | float | m | PSD上限 |
| edges | np.ndarray | m | ビン境界 |
| sizes_version | int | - | サイズ変更の世代管理 |
| edges_version | int | - | edges変更の世代管理 |

内部キャッシュ/診断（runtimeのみ）
| key | type | unit | 用途 |
| --- | --- | --- | --- |
| _mk_cache_key | tuple | - | m_k キャッシュのキー |
| _mk_cache | np.ndarray | kg | m_k キャッシュ |
| sanitize_reset_count | int | - | 正規化リセット回数 |

補足（不変条件/更新ルール）
- `sizes`/`widths`/`number` は同一長、`sizes` は単調増加、`widths == diff(edges)`、`edges` は `len(sizes)+1`
- `s`/`n` は `sizes`/`number` のエイリアスとして常に同期（配列差し替え時に必ず更新）
- `sizes_version` はサイズ配列更新時にインクリメント（`edges` 変更時は `edges_version` も更新）
- `_mk_cache_key/_mk_cache` は `sizes_version/edges_version` 変更時に無効化（再計算）
- `sanitize_and_normalize_number` は `number` を直接更新した後に必ず呼び、`n` の同期と `sanitize_reset_count` の更新を担う

更新責務の所在（主要関数）
- `update_psd_state`: 必須キーの初期化、`sizes_version/edges_version` の初期値設定、`s/n` の同期
- `_set_psd_edges`: `edges` 更新時の `edges_version` のインクリメント
- `ensure_psd_state_contract`: `s/n` 同期と `sizes_version/edges_version` の存在保証
- `sanitize_and_normalize_number`: `number` の健全化/正規化と `sanitize_reset_count` の更新

#### 調査メモ（中期実装の前提確認）

共通化の重複箇所（surface_ode / smol の両経路でほぼ同じ処理）
- 供給+deep buffer: `supply.evaluate_supply` → `supply.split_supply_with_deep_buffer` の連鎖
- 遮蔽/tau: `physics_step.compute_shielding` の呼び出しと `tau_for_coll` の派生
- 表層更新の出力: `sigma_surf`, `outflux_surface`, `sink_flux_surface` の集計と mass-budget への反映
- blowout補正/ゲート: `_fast_blowout_correction_factor` と `_compute_gate_factor` の適用箇所

psd_state の実参照（現行コードが触っているキー）
- 必須: `sizes`, `widths`, `number`, `rho`
- 互換エイリアス: `s`, `n`
- 境界/世代管理: `s_min`, `s_max`, `edges`, `sizes_version`, `edges_version`
- 内部キャッシュ: `_mk_cache_key`, `_mk_cache`, `sanitize_reset_count`

#### 追記候補（中期計画の明文化ポイント）

- 共通I/O契約の定義: surface_ode / smol が共通で返す `sigma_surf`, `outflux_surface`, `sink_flux_surface`, `t_blow`, `t_coll`, `prod_rate_effective`, `mass_error` を固定し、結果コンテナで受ける
- psd_state 更新ポリシー: `sizes/number` と `s/n` の同期規約、`sizes_version/edges_version` の更新責務、`sanitize_and_normalize_number` を呼ぶ責任箇所を明記
- 供給/リザーバ状態の責務: `SupplyRuntimeState` と `sigma_deep` の更新タイミングと責任者を統一し、surface_ode / smol で同一経路に寄せる
- blowout補正/ゲートの共通化: 補正適用を「表層更新後の共通ポスト処理」に移す方針を明記
- キャッシュ/Numba寿命管理: run 境界でのキャッシュ初期化/リセットと `MARSDISK_DISABLE_NUMBA` / `MARSDISK_DISABLE_COLLISION_CACHE` の扱いを中期前提として明記

#### 中期実装の明示タスク（追加）

- [x] **M2-01 共通I/O契約の設計**: surface_ode / smol で共通に返すフィールドを固定し、結果コンテナ（仮称 `SurfaceUpdateResult`）を定義
- [x] **M2-02 供給/リザーバ更新の共通化**: `evaluate_supply`→`split_supply_with_deep_buffer` の経路を共通関数化し、surface_ode/smol 両経路で同じ出力を受ける
- [x] **M2-03 遮蔽/tau の共通化**: `compute_shielding` と `tau_for_coll` 計算を単一ユーティリティにまとめる
- [x] **M2-04 表層更新の共通ポスト処理**: blowout補正/ゲート係数を共通ポスト処理に移し、適用順序を固定
- [x] **M2-05 t_coll の扱い統一**: surface_ode の `tau_for_coll` と smol の `t_coll_kernel` の優先順位を確定
- [x] **M2-06 psd_state 契約の固定**: 必須/推奨/内部キャッシュの一覧と更新責務をドキュメント化し、同期規約を明記
- [x] **M2-07 キャッシュ/Numba寿命管理の明文化**: run 境界での reset/clear の実行箇所と環境変数の取り扱いを決める

#### 中期実装チェックリスト

- [x] surface_ode / smol の共通I/O契約が文書化され、呼び出し側が同一インターフェースを使用している（SurfaceUpdateResultで統一）
- [x] 供給/リザーバ更新が単一経路になり、substep/非substepで積分粒度の差が意図どおり説明できる（surface_ode: dt_sub / smol: dt）
- [x] blowout補正/ゲート係数の適用位置が一貫し、二重適用/適用漏れがない（helpersで共通化）
- [x] `t_coll` の定義が統一され、系列出力に混乱がない（`_resolve_t_coll_step`）
- [ ] psd_state の `sizes/number` と `s/n` が常に同期され、`sizes_version/edges_version` の更新責務が明確
- [ ] Numba/キャッシュの寿命管理が run 境界で明確化され、A/B テスト時に再現性が確保される
- [ ] streaming ON/OFF の両方で `out/<run_id>/series/run.parquet` と `out/<run_id>/checks/mass_budget.csv` が同等に出力される
- [ ] `energy_bookkeeping` 有効時の系列/予算出力が共通I/O後も一致する
- [ ] `sinks.mode` の主要分岐（none/sublimation/hydro_escape）で sink 系集計が破綻しない
- [ ] blowout 無効時に `outflux_surface` が確実に 0 になる
- [ ] psd_state の `sizes_version/edges_version` が smol 経路でも破綻せず更新される
- [ ] 乱数シード固定時に供給/混合の乱数が再現される
- [ ] `out/<run_id>/run_config.json` の provenance（`blowout_provenance` / `sublimation_provenance`）が共通化後も維持される
- [ ] `out/<run_id>/summary.json` の主要キー（`M_loss`, `M_out_cum`, `M_sink_cum`, `mass_budget_max_error_percent`）がパリティを保つ
- [ ] `out/<run_id>/series/diagnostics.parquet` の列スキーマが streaming ON/OFF で一致する
- [ ] `qpr_table` 未指定時の fallback / `qpr_strict=true` の例外挙動が維持される
- [ ] Wyatt スケーリングの `t_coll` オーダー感が崩れていない
- [ ] substep 多発時の性能/メモリ退行がない

#### 中期実装チェックリスト（追加項目）

- [ ] `s_min` の決定順序（config/吹き飛び/昇華床/表面エネルギー床）が変わっていない
- [ ] `beta_at_smin_config` / `beta_at_smin_effective` と `case_status` 判定が一致する
- [ ] 遮蔽モード（`off`/`fixed_tau1`/`psitau`）で `tau_los`/`kappa_eff`/`phi` の意味が揺れない
- [ ] sink 分岐（昇華/ガス抗力/水蒸気逃避）で `M_sink_cum` と内訳の整合が保たれる
- [ ] `dt <= 0.1 * min(t_coll)` の収束条件が surface_ode / smol 両方で守られる
- [ ] substep 分割時の質量収支が per-step と一致する（`dt_over_t_blow` 周辺）
- [ ] IMEX-BDF1 で負の `N_k` / `sigma_surf` が出ない
- [ ] `t_blow=1/Ω` の既定と override が同じ意味で扱われる
- [ ] エネルギー収支ログの誤差閾値（warning/error）が共通化後も維持される
- [ ] `psd_state` の内部キャッシュ（`_mk_cache*`）がサイズ変更時に再計算される
- [ ] `cfg` の破壊更新が拡大しない（runtime params への移管方針を維持）
- [ ] `SupplyRuntimeState` / `sigma_deep` の更新が substep でも一貫する
- [ ] `out/<run_id>/checks/mass_budget.csv` が streaming 有無に関係なく必ず生成される
- [ ] `energy_bookkeeping` の CSV/Parquet 出力が ON/OFF で同等に動作する
- [ ] `--override` の適用順序と型変換が従来どおり
- [ ] `FORCE_STREAMING_OFF` / `IO_STREAMING` の優先順位が変わらない
- [ ] `geometry` / `temperature` / `tau_stop` のバリデーションが維持される
- [ ] `ALLOW_TL2003=false` の既定が変わらない
- [ ] Numba 無効時の性能退行が急増しない
- [ ] Qpr/Q* キャッシュ利用率が低下しない
- [ ] Smol kernel の再計算頻度がサイズ変更時のみになる
- [ ] streaming merge が過剰に重くならない
- [ ] `sigma_surf<=0` / `kappa_surf<=0` / `tau<=0` でも NaN/inf を出さない
- [ ] `s_min >= s_max` / `rho<=0` などの入力で明示的にエラーになる
- [ ] 温度テーブル境界外の評価が意図どおり（clamp/例外）
- [ ] pytest（`test_scalings`/mass conservation/surface outflux/wavy PSD）が通る
- [ ] 3ケース baseline compare が共通I/O契約でも一致する

### フェーズ3: グローバル状態の隔離

- Q* テーブル/放射テーブル/衝突キャッシュの初期化を**RunContext化**
- `run_zero_d` の開始/終了で状態を明示的に設定・リセット
- `psd_state` の契約を型で固定化（dataclass / TypedDict など）し、キャッシュの初期化/破棄をRunContext側で統一

### フェーズ4: cfg 破壊更新の解消

- `cfg` から派生した**runtime params**を別オブジェクトに集約
- `cfg` 自体は不変扱いとし、run_config に「effective_*」を記録

### フェーズ5: I/O結合の低減

- 物理ステップの返り値を**DiagnosticsPayload**に集約
- ストリーミング出力は payload からのみ生成する設計に変更

---

## 実装タスク（チェックボックス）

- [x] [短期] フェーズ0: 0Dベースラインの出力スナップショットを確定
- [x] [短期] フェーズ0: 差分比較（series/summary/mass_budget）の簡易ツールを用意
- [x] [短期] フェーズ1: `run_zero_d` に4系のアダプタ導入（放射・遮蔽・昇華・表層）
- [x] [短期] フェーズ1: 既存の記録列を保持したまま新経路に接続
- [x] [短期] フェーズ1: パリティチェック（数値差分が許容範囲内）
- [x] [中期] フェーズ2: 旧ロジックの削除・重複コードの整理
- [x] [中期] フェーズ2: blowout補正/ゲート係数の共通化（helpers集約）
- [x] [中期] フェーズ2: `physics_step` のI/F安定化（引数・返り値固定）
- [x] [中期] フェーズ2: `collision_solver_mode` 分岐の共通化（surface_ode/smol の重複削減）
- [x] [中期] フェーズ2: `psd_state` の暗黙契約を明文化（必須キー/単位/キャッシュキー）
- [ ] [長期] フェーズ3: RunContext でグローバル状態の初期化/復元
- [ ] [長期] フェーズ3: `psd_state` の型固定とRunContext内での寿命管理
- [ ] [長期] フェーズ4: cfgの破壊更新を排除（runtime paramsへ移管）
- [ ] [長期] フェーズ5: DiagnosticsPayload でI/O接続を一本化
- [ ] ドキュメント更新（必要時のみ）: `analysis/overview.md` と関連プランの追記
- [ ] DocSyncAgent + analysis-doc-tests 実施（analysis変更が発生した場合）

---

## リスクと緩和策

- **数値差分の混入**: フェーズ1では最小置換に留め、差分検知を自動化
- **性能劣化**: dataclass生成や関数分割のオーバーヘッドを測定し、必要なら最適化
- **I/O互換性破壊**: 出力列と単位は現行を優先し、schemaの変更は後回し
- **グローバル状態の副作用**: RunContextでの初期化/復元を必須化

---

## 受入条件（最小）

- 0D基準ケースで `out/<run_id>/series/run.parquet` と `out/<run_id>/summary.json` の主要列が一致
- `out/<run_id>/checks/mass_budget.csv` の誤差が 0.5% を超えない
- 既存pytestが通る

---

## 参考（関連プラン）

- `docs/plan/run_zero_d.md`
- `docs/plan/20251216_code_reorganization_for_collision_physics.md`
- `docs/plan/20251230_columnar_buffer_plan.md`
