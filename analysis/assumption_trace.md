> **文書種別**: 解説（Diátaxis: Explanation）

## 0. はじめに
現行の火星ロッシュ円盤モデルに含まれる「前提→式」のひも付けを集約するハブとして、このファイルを設ける。フェーズ1は**手動メモのみ**で、`analysis/equations.md` に定義済みの式番号を参照しつつ、`out/plan/assumption_trace_gap_list.md`・`out/plan/assumption_trace_schema.md`・`out/plan/assumption_trace_data_sources.md` に列挙された曖昧な仮定をスケルトン化する。式 (E.xxx) の定義は引き続き `analysis/equations.md` が唯一のソースであり、出典管理は `analysis/UNKNOWN_REF_REQUESTS.*` と `analysis/references.registry.json` に従う。フェーズ2以降で `assumption_trace_schema.md` と `assumption_trace_data_sources.md` に沿った自動スキャナを追加する前提で、ここではクラスタ別のラベルと参照位置だけを固定する。

## 1. フェーズ1の範囲（docs-only）
- eq_id は未確定のまま `TODO(REF:slug)` で立て、式本文や自動抽出ロジックは導入しない。
- 各クラスタに対して slug・仮称ラベル・主要な config トグルを記し、将来の自動ツールが `code_path` や `run_stage` を補完できる「置き場」を準備する。
- 未解決参照は必ず `TODO(REF:<slug>)` を使い、`analysis/UNKNOWN_REF_REQUESTS.jsonl` の運用（AI_USAGE.md に記載）で扱う。場当たり的な TODO コメントは書かない。

## 2. 曖昧な仮定クラスタのメモ
各節は `out/plan/assumption_trace_gap_list.md` の粒度に対応し、`assumption_trace_schema.md` のフィールドを YAML 例で示す（未完フィールドは TODO のまま保持）。

### 2.1 ブローアウト関連（β, a_blow, t_blow） — assumption cluster "blowout_core_v1"
gas-poor かつ火星放射のみを前提に β・ブローアウト境界・`t_blow=1/Ω` を評価するが、Q_pr テーブルの出典と `fast_blowout` 補正の適用条件が式レベルで未整理。`radiation.source="mars"` 固定や `io.correct_fast_blowout` のオン/オフが挙動を変えるため、設定依存の揺らぎを明示する必要がある。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `blowout_core_eid_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:blowout_core_eid_v1)
source_doc: analysis/equations.md
paper_ref: Hyodo2018_ApJ860_150
assumption_tags:
  - gas-poor
  - 0D
  - rp_mars_only
  - t_blow_eq_1_over_Omega
config_keys:
  - blowout.enabled
  - radiation.source
  - radiation.TM_K
  - radiation.qpr_table_path
  - io.correct_fast_blowout
  - numerics.dt_init
code_path:
  - [marsdisk/physics/radiation.py:179–288]
  - [marsdisk/grid.py:17–49]
run_stage:
  - surface loop
inputs:
  - Omega [1/s]  # from [marsdisk/grid.py:17–49]
  - Q_pr         # from tables via [marsdisk/io/tables.py:259–295]
outputs:
  - series.a_blow
  - series.t_blow
  - summary.beta_at_smin_config
tests:
  - tests/test_scalings.py
  - tests/test_fast_blowout.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: β と a_blow の参照式 (E.xxx)、`fast_blowout` 補正式の根拠、`use_solar_rp` 無効時の取り扱い。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル出典、`analysis/equations.md` の R1–R3 節、`analysis/UNKNOWN_REF_REQUESTS.jsonl`（未登録なら追加）。

### 2.2 遮蔽・ゲート（Φ(τ, ω0, g), τ=1 クリップ, gate_mode） — assumption cluster "shielding_gate_order_v1"
Φテーブルの補間と τ=1 クリップの適用順が `shielding.mode` と `blowout.gate_mode` の組み合わせに依存し、τゲート（`radiation.tau_gate.enable`）との重ねがけ順序がコード依存のまま。ゲート係数 `f_gate` が衝突・昇華どちらと競合するかも明文化が不足している。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `shielding_gate_order_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:shielding_gate_order_v1)
source_doc: analysis/equations.md
paper_ref: TODO(REF:shielding_gate_order_v1)
assumption_tags:
  - gas-poor
  - tau_gate_optional
  - surface_tau_le_1
config_keys:
  - shielding.mode
  - shielding.table_path
  - shielding.fixed_tau1_tau
  - shielding.fixed_tau1_sigma
  - radiation.tau_gate.enable
  - blowout.gate_mode
  - surface.freeze_sigma
code_path:
  - [marsdisk/physics/shielding.py:81–216]
  - [marsdisk/run.py:968–1116]
  - [marsdisk/run.py:1475–1518]
run_stage:
  - shielding application
  - surface loop (gate evaluation)
inputs:
  - tau  # from PSD κ and Σ_surf
  - Phi(τ, w0, g) table  # from [marsdisk/io/tables.py:273–340]
outputs:
  - series.kappa_eff
  - series.sigma_tau1
  - diagnostics.tau_gate_blocked
  - summary.radiation_tau_gate
tests:
  - tests/test_radiation_shielding_logging.py
  - tests/test_blowout_gate.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: Φテーブル出典の正式引用、ゲート適用順序の図式化、`tau_gate_block_time` の式番号。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル節、`analysis/equations.md` の遮蔽式、`analysis/overview.md` Provenance セクション。

### 2.3 PSD と wavy 補正（s_min_effective, psd.floor.mode） — assumption cluster "psd_wavy_floor_scope_v1"
`wavy_strength` と最小粒径のクリップ（ブローアウト／設定／動的床）が混在しており、どの PSD 式 (P1) と結び付けるかが未指定。`psd.floor.mode` 切替と `sizes.evolve_min_size` の同時使用時の優先順位も曖昧なままである。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `psd_wavy_floor_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:psd_wavy_floor_scope_v1)
source_doc: analysis/equations.md
assumption_tags:
  - gas-poor
  - wavy_optional
  - smin_clipped_by_blowout
config_keys:
  - psd.wavy_strength
  - psd.floor.mode
  - sizes.s_min
  - sizes.evolve_min_size
  - sizes.dsdt_model
  - sizes.apply_evolved_min_size
code_path:
  - [marsdisk/physics/psd.py:30–146]
  - [marsdisk/physics/psd.py:149–219]
  - [marsdisk/run.py:1075–1109]
run_stage:
  - PSD initialisation
  - PSD evolution hooks
inputs:
  - s_min_config [m]
  - wavy_strength [-]
  - ds/dt model  # if evolve_min_size enabled
outputs:
  - series.kappa
  - series.s_min_effective
  - series.s_min_floor_dynamic
  - diagnostics.wavy_params
tests:
  - tests/test_psd_kappa.py
  - tests/test_surface_outflux_wavy.py
  - tests/test_min_size_evolution_hook.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: wavy 振幅とフェーズの式番号、`s_min_effective` 算定の優先順位、`apply_evolved_min_size` の適用条件。
- 次に確認する資料: `assumption_trace_data_sources.md` の PSD ソース一覧、`analysis/equations.md` の P1 節。

### 2.4 衝突時間スケール（Wyatt / Ohtsuki regime） — assumption cluster "tcoll_regime_switch_v1"
表層 ODE の `t_coll` は Wyatt スケーリング（Ωτ⁻¹）を既定にする一方、Smol カーネルや `surface.use_tcoll` フラグで無効化される経路が混在する。`f_wake` や e/i ダンピングの仮定により τ 推定が揺れるため、どの regime でどの式を使うかが明確でない。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `tcoll_regime_switch_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:tcoll_regime_switch_v1)
source_doc: analysis/equations.md
assumption_tags:
  - wyatt_scaling
  - optional_collisions
  - 0D
config_keys:
  - surface.use_tcoll
  - dynamics.f_wake
  - dynamics.e0
  - dynamics.i0
  - numerics.dt_init
code_path:
  - [marsdisk/physics/surface.py:46–219]
  - [marsdisk/run.py:1036–1109]
run_stage:
  - surface loop
inputs:
  - tau  # from PSD/Σ_surf
  - Omega [1/s]
outputs:
  - series.t_coll
  - diagnostics.ts_ratio
  - summary.phase_branching.t_coll_stats
tests:
  - tests/test_scalings.py
  - tests/test_phase3_surface_blowout.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: Ohtsuki regime への切替条件、`f_wake` の式番号、Smol カーネルと表層 t_coll の整合性。
- 次に確認する資料: `assumption_trace_data_sources.md` のコード走査ターゲット、`analysis/equations.md` の C1–C4 節。

### 2.5 昇華・ガス抗力（sinks.mode, rp_blowout.enable, TL2003） — assumption cluster "sublimation_gasdrag_scope_v1"
gas-poor 既定で昇華のみを有効にし、TL2003（gas-rich 前提）は `ALLOW_TL2003=false` で無効化する運用だが、設定 YAML とドキュメントの整合が未確認。`sinks.mode` や `rp_blowout.enable`、`sinks.enable_gas_drag` の組み合わせが式参照なしに切り替わる点が曖昧。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `sublimation_gasdrag_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:sublimation_gasdrag_scope_v1)
source_doc: analysis/equations.md
assumption_tags:
  - gas-poor
  - TL2003_disabled
  - sublimation_default
config_keys:
  - sinks.mode
  - sinks.enable_sublimation
  - sinks.enable_gas_drag
  - sinks.rho_g
  - sinks.rp_blowout.enable
  - radiation.use_mars_rp
code_path:
  - [marsdisk/physics/sinks.py:34–160]
  - [marsdisk/physics/sublimation.py:386–496]
  - [marsdisk/run.py:986–1109]
run_stage:
  - sink selection
  - surface loop
inputs:
  - T_use [K]
  - rho_p [kg/m^3]
  - Omega [1/s]
outputs:
  - series.t_sink
  - diagnostics.sink_selected
  - summary.sublimation_provenance
tests:
  - tests/test_sinks_none.py
  - tests/test_sublimation_phase_gate.py
  - tests/test_phase_branching_run.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: 昇華式の (E.xxx) ひも付け、TL2003 無効の根拠引用位置、gas-rich 感度試験時の手順。
- 次に確認する資料: `assumption_trace_data_sources.md` の設定パース手順、`analysis/equations.md` の昇華式、`analysis/UNKNOWN_REF_REQUESTS.jsonl` での TL2003 slug 登録。

### 2.6 半径・幾何の固定（0D vs disk.geometry） — assumption cluster "radius_fix_0d_scope_v1"
0D 実行では `disk.geometry`（r_in_RM, r_out_RM）が必須入力で、legacy `geometry.r` / `runtime_orbital_radius_rm` は無効化済み。半径固定のまま 1D 拡張へ式を持ち越す際に、どの E.xxx が 0D 前提かをタグ付けできていない。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `radius_fix_0d_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: TODO(REF:radius_fix_0d_scope_v1)
source_doc: analysis/equations.md
assumption_tags:
  - 0D
  - fixed_radius
  - inner_disk_scope
config_keys:
  - disk.geometry.r_in_RM
  - disk.geometry.r_out_RM
  - geometry.mode
  - geometry.r  # legacy (disallowed)
  - geometry.runtime_orbital_radius_rm  # legacy (disallowed)
run_stage:
  - config loading
  - orbital grid initialisation
code_path:
  - [marsdisk/schema.py:22–75]
  - [marsdisk/grid.py:17–49]
  - [marsdisk/run.py:966–1016]
inputs:
  - r_in_RM / r_out_RM  # runtime radius is derived from disk.geometry
outputs:
  - summary.runtime_orbital_radius_m
  - run_config.runtime_orbital_radius_rm
tests:
  - tests/test_scope_limitations_metadata.py
  - tests/test_run_regressions.py
status: draft
owner: TODO
last_checked: YYYY-MM-DD
```

- 欠落情報: 半径解像度を持たない式の一覧、1D 拡張時に再確認すべき E.xxx、`scope.region` との整合。
- 次に確認する資料: `assumption_trace_data_sources.md` の設定ファミリ、`analysis/overview.md` の geometry 記述。
