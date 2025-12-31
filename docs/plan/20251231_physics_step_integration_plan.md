# physics_step 実務統合プラン（0D優先）

> **作成日**: 2025-12-31  
> **ステータス**: 短期スコープ確定  
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
- **前提実行**: `FORCE_STREAMING_OFF=1` で実行し、`--override io.outdir=<outdir>` で出力先を分離
- **比較対象**:
  - `summary.json`
  - `series/run.parquet`
  - `checks/mass_budget.csv`
- **比較ルール（合格条件）**:
  - `summary.json`: 指定キーが全て存在し、数値は `rtol=1e-6, atol=1e-12` 以内  
    対象キー: `M_loss`, `M_out_cum`, `M_sink_cum`, `mass_budget_max_error_percent`, `dt_over_t_blow_median`, `beta_at_smin_config`, `beta_at_smin_effective`
  - `series/run.parquet`: 行数・列集合が一致し、数値列は `rtol=1e-6, atol=1e-12` 以内（最大差分で評価）
  - `checks/mass_budget.csv`: 両者とも `error_percent <= 0.5` を満たすこと
- **出力**:
  - `out/plan/physics_step_baseline/<case-id>/compare.json`
    - `status`: `pass` / `fail`
    - `case_id`, `ref_dir`, `new_dir`
    - `missing_files`: list
    - `summary_diff_max`: dict（キーごとの最大差分）
    - `series_diff_max`: dict（列ごとの最大差分）
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
- 置換前後で `series/run.parquet` と `summary.json` の主要列の一致を必須条件にする

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
- [ ] **Issue P1-06: フェーズ0ベースライン差分比較**  
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
   - `pytest tests/test_scalings.py -q`  
   - `python -m marsdisk.run --config configs/innerdisk_collisions_only.yml --override io.outdir=out/plan/physics_step_baseline/collisions_only/new`  
   - `python -m marsdisk.run --config configs/innerdisk_sublimation_only.yml --override io.outdir=out/plan/physics_step_baseline/sublimation_only/new`

2) **P1-03〜P1-05 完了時（全面検証）**  
   - 3ケースのベースラインを実行（ref/new）  
   - `scripts/tools/compare_zero_d_outputs.py --case-id <id> --ref <ref> --new <new>`

3) **P1-06 完了時（受入確認）**  
   - `compare.json` が全ケース `status=pass`  
   - `checks/mass_budget.csv` が `error_percent<=0.5` を満たすこと

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

### フェーズ3: グローバル状態の隔離

- Q* テーブル/放射テーブル/衝突キャッシュの初期化を**RunContext化**
- `run_zero_d` の開始/終了で状態を明示的に設定・リセット

### フェーズ4: cfg 破壊更新の解消

- `cfg` から派生した**runtime params**を別オブジェクトに集約
- `cfg` 自体は不変扱いとし、run_config に「effective_*」を記録

### フェーズ5: I/O結合の低減

- 物理ステップの返り値を**DiagnosticsPayload**に集約
- ストリーミング出力は payload からのみ生成する設計に変更

---

## 実装タスク（チェックボックス）

- [ ] [短期] フェーズ0: 0Dベースラインの出力スナップショットを確定
- [x] [短期] フェーズ0: 差分比較（series/summary/mass_budget）の簡易ツールを用意
- [x] [短期] フェーズ1: `run_zero_d` に4系のアダプタ導入（放射・遮蔽・昇華・表層）
- [x] [短期] フェーズ1: 既存の記録列を保持したまま新経路に接続
- [ ] [短期] フェーズ1: パリティチェック（数値差分が許容範囲内）
- [ ] [中期] フェーズ2: 旧ロジックの削除・重複コードの整理
- [ ] [中期] フェーズ2: `physics_step` のI/F安定化（引数・返り値固定）
- [ ] [長期] フェーズ3: RunContext でグローバル状態の初期化/復元
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

- 0D基準ケースで `series/run.parquet` と `summary.json` の主要列が一致
- `checks/mass_budget.csv` の誤差が 0.5% を超えない
- 既存pytestが通る

---

## 参考（関連プラン）

- `docs/plan/run_zero_d.md`
- `docs/plan/20251216_code_reorganization_for_collision_physics.md`
- `docs/plan/20251230_columnar_buffer_plan.md`
