> **文書種別**: 解説（自動生成）
> AUTO-GENERATED: DO NOT EDIT BY HAND. Run `python -m analysis.tools.render_assumptions`.

## 0. この文書の目的
仮定トレースの機械可読データ（assumption_registry.jsonl）から、タグ・設定・コードパスを人間が確認しやすい形でまとめる。
数式本文は `analysis/equations.md` が唯一のソースであり、本書では eq_id とラベルだけを参照する。UNKNOWN_REF_REQUESTS の slug は TODO(REF:slug) として維持する。

## 1. カバレッジ指標
- equation_coverage: 38/41 = 0.927
- function_reference_rate: 9/11 = 0.818
- anchor_consistency_rate: 9/23 = 0.391

## 2. レコード一覧
| id | scope | eq_ids | tags | config_keys | run_stage | provenance | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| blowout_core_eid_v1 | toggle | E.007, E.013, E.014 | gas-poor, 0D, rp_mars_only, t_blow_eq_1_over_Omega | blowout.enabled, radiation.source, radiation.TM_K, radiation.qpr_table_path, io.correct_fast_blowout, numerics.dt_init | surface loop | Burns1979_Icarus40_1 | draft |
| shielding_gate_order_v1 | toggle | E.015, E.016, E.017, E.031 | gas-poor, tau_gate_optional, surface_tau_le_1 | shielding.mode, shielding.table_path, shielding.fixed_tau1_tau, shielding.fixed_tau1_sigma, radiation.tau_gate.enable, blowout.gate_mode, surface.freeze_sigma | shielding application, surface loop (gate evaluation) | TakeuchiLin2003_ApJ593_524 | draft |
| psd_wavy_floor_scope_v1 | module_default | E.008 | gas-poor, wavy_optional, smin_clipped_by_blowout | psd.wavy_strength, psd.floor.mode, sizes.s_min, sizes.evolve_min_size, sizes.dsdt_model, sizes.apply_evolved_min_size | PSD initialisation, PSD evolution hooks | Krivov2006_AA455_509 | draft |
| tcoll_regime_switch_v1 | module_default | E.006, E.007 | wyatt_scaling, optional_collisions, 0D | surface.use_tcoll, dynamics.f_wake, dynamics.e0, dynamics.i0, numerics.dt_init | surface loop | Wyatt2008 | draft |
| sublimation_gasdrag_scope_v1 | toggle | E.018, E.019, E.036, E.037, E.038 | gas-poor, TL2003_disabled, sublimation_default | sinks.mode, sinks.enable_sublimation, sinks.enable_gas_drag, sinks.rho_g, sinks.rp_blowout.enable, radiation.use_mars_rp | sink selection, surface loop | TakeuchiLin2002_ApJ581_1344 | draft |
| radius_fix_0d_scope_v1 | module_default | E.001, E.002 | 0D, fixed_radius, inner_disk_scope | geometry.mode, disk.geometry.r_in_RM, disk.geometry.r_out_RM | config loading, orbital grid initialisation | Wyatt2008 | draft |
| ops:gas_poor_default | project_default | - | ops:gas_poor_default, geometry:thin_disk | radiation.ALLOW_TL2003, radiation.use_mars_rp, sinks.enable_gas_drag | physics_controls | Hyodo2018_ApJ860_150 | draft |
| radiative_cooling_tmars | module_default | E.042, E.043 | radiation:tmars_graybody, ops:gas_poor_default | radiation.TM_K, mars_temperature_driver.constant | physics_controls | Hyodo2018_ApJ860_150 | draft |
| viscosity_c5_optional | toggle | - | diffusion_optional, C5 | viscosity.enabled | smol_kernel | CridaCharnoz2012_Science338_1196 | draft |
| ops:qpr_table_generation | module_default | - | ops:qpr_table | radiation.qpr_table_path | prep | assumption:qpr_table_provenance | needs_ref |
| equations_unmapped_stub | module_default | E.003, E.004, E.005, E.009, E.010, E.011, E.012, E.020, E.021, E.022, E.023, E.024, E.025, E.026, E.027, E.028, E.032, E.033, E.035, E.039 | placeholder | - | - | assumption:eq_unmapped_placeholder | needs_ref |
