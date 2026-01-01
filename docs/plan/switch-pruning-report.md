# Switch Pruning Report

This report inventories boolean/enum-style switches in the YAML schema and flags removal candidates without changing runtime behavior.

## Scope
- Report-only: no deletions, no behavior changes.
- Switch definition: bool fields or Literal/Union-with-Literal fields in `marsdisk/schema.py`.
- Usage scan: fixed-string `rg` against the repo (schema excluded; report file excluded).
- Output: Markdown report at `docs/plan/switch-pruning-report.md`.

## Summary
- Total schema switches: 106
- keep: 69
- review (config/test-only): 7
- docs-only: 16
- candidate-remove (no usage found): 14
- legacy/deprecated wording in schema: 7
- manual review (below): confirm-remove=2, reclassify-to-keep=12

## Classification criteria
- keep: referenced in `marsdisk/`, `scripts/`, or `tools/`.
- review: referenced only in `configs/` or `tests/` (no code hit found).
- docs-only: referenced only in `analysis/`, `docs/`, or `README.md`.
- candidate-remove: no references outside `marsdisk/schema.py`.

## Notes on references
- Definition reference points to the class block in `marsdisk/schema.py`.
- Usage references show the first match per category (code/config/test/docs).
- Absence of a code match does not prove dead code; dynamic access may exist.

## Candidate-remove review (manual)
- Confirmed removal candidates (unused in runtime; config/test updates required):
- `disk.geometry.r_profile` only appears in configs/<tests>/, no runtime usage found. Example refs: [configs/base.yml:53-53], [tests/integration/test_phase_branching_run.py:24-24].
- `supply.table.interp` is set in configs but the supply table always uses linear interpolation in code. Example refs: [configs/base.yml:86-86], [marsdisk/physics/supply.py:51-59].
- Reclassify to keep (runtime usage confirmed):
- `dynamics.enable_e_damping` [marsdisk/run_zero_d.py:2502-2502], [marsdisk/physics/collisions_smol.py:904-904]
- `dynamics.kernel_H_mode` [marsdisk/physics/collisions_smol.py:555-559]
- `dynamics.kernel_ei_mode` [marsdisk/physics/collisions_smol.py:536-536]
- `dynamics.v_rel_mode` [marsdisk/physics/collisions_smol.py:893-899]
- `io.psd_history` [marsdisk/run_zero_d.py:1649-1650], [marsdisk/run_one_d.py:713-714]
- `io.streaming.cleanup_chunks` [marsdisk/run_zero_d.py:1648-1648], [marsdisk/io/streaming.py:146-146]
- `numerics.resume.enabled` [marsdisk/run_zero_d.py:1490-1490]
- `process.state_tagging.enabled` [marsdisk/run_zero_d.py:349-350]
- `radiation.mars_temperature_driver.autogenerate.model` [marsdisk/physics/tempdriver.py:230-234]
- `radiation.qpr_cache.enabled` [marsdisk/run_zero_d.py:438-441]
- `radiation.use_solar_rp` [marsdisk/run_zero_d.py:360-370]
- `sinks.hydro_escape.enable` [marsdisk/run_zero_d.py:3947-3947]

## Inventory
| key | type | default | allowed | purpose | definition | usage refs | class | status | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blowout.enabled | bool | True | true/false | - | [marsdisk/schema.py:1448-1463] | [marsdisk/run_zero_d.py:4868-4868] [tests/integration/test_supply_positive.py:160-160] [README.md:395-395] | Blowout | keep | - |
| blowout.gate_mode | literal | none | none,sublimation_competition,collision_competition | Optional surface gate to suppress blow-out when other solid-loss processes are faster. | [marsdisk/schema.py:1448-1463] | [marsdisk/run_zero_d.py:744-744] [tests/integration/test_run_regressions.py:169-169] [analysis/assumption_registry.jsonl:2-2] | Blowout | keep | - |
| blowout.layer | literal | surface_tau_le_1 | surface_tau_le_1,full_surface | Select the surface reservoir feeding blow-out (default: Σ_{τ≤1} skin). | [marsdisk/schema.py:1448-1463] | [docs/plan/20251219_supply_path_overview.md:94-94] | Blowout | docs-only | - |
| blowout.target_phase | literal | solid_only | solid_only,any | Select which phase states participate in the surface blow-out calculation. | [marsdisk/schema.py:1448-1463] | [analysis/CHANGELOG.md:31-31] | Blowout | docs-only | - |
| chi_blow | literal | 1.0 | auto or float | Blow-out timescale multiplier (float) or 'auto' to estimate from β and Q_pr. | [marsdisk/schema.py:1783-1906] | [marsdisk/physics_step.py:393-393] [configs/temp_supply_sweep.yml:7-7] [tests/fixtures/baseline_summary.json:42-42] [analysis/equation_code_map.json:2969-2969] | Config | keep | - |
| diagnostics.energy_bookkeeping.enabled | bool | False | true/false | Enable collision energy bookkeeping (E_rel/E_diss/f_ke/F_lf statistics). | [marsdisk/schema.py:1763-1773] | [analysis/methods.md:202-202] | EnergyBookkeeping | docs-only | - |
| diagnostics.energy_bookkeeping.stream | bool | True | true/false | Allow streaming writes for energy_budget outputs (FORCE_STREAMING_OFF overrides). | [marsdisk/schema.py:1763-1773] | [analysis/methods.md:202-202] | EnergyBookkeeping | docs-only | - |
| diagnostics.extended_diagnostics.enable | bool | False | true/false | Enable extended diagnostics (additional series columns and rollup keys). | [marsdisk/schema.py:1750-1760] | [tests/integration/test_run_regressions.py:111-111] [analysis/run-recipes.md:154-154] | ExtendedDiagnostics | review | - |
| disk.geometry.r_profile | literal | uniform | uniform,powerlaw | Radial surface density profile: 'uniform' or 'powerlaw' (Σ ∝ r^-p) | [marsdisk/schema.py:47-74] | (none) | DiskGeometry | candidate-remove | - |
| dynamics.dr_dist | literal | uniform | uniform,loguniform | Distribution for Δr sampling; interpreted in meters | [marsdisk/schema.py:696-794] | [marsdisk/run_zero_d.py:481-481] | Dynamics | keep | - |
| dynamics.e_mode | literal | fixed | fixed,mars_clearance | Initial eccentricity mode; 'mars_clearance' samples Δr in meters | [marsdisk/schema.py:696-794] | [marsdisk/run_zero_d.py:472-472] [analysis/overview.md:135-135] | Dynamics | keep | - |
| dynamics.enable_e_damping | bool | False | true/false | Enable post-collision e/i damping (off by default; formula selected in run-time logic). | [marsdisk/schema.py:696-794] | (none) | Dynamics | candidate-remove | - |
| dynamics.i_mode | literal | fixed | fixed,obs_tilt_spread | Initial inclination mode; 'obs_tilt_spread' samples i0 in radians | [marsdisk/schema.py:696-794] | [marsdisk/run_zero_d.py:513-513] [analysis/overview.md:135-135] | Dynamics | keep | - |
| dynamics.kernel_H_mode | literal | ia | ia,fixed | Scale height prescription for collision kernels | [marsdisk/schema.py:696-794] | (none) | Dynamics | candidate-remove | - |
| dynamics.kernel_ei_mode | literal | config | config,wyatt_eq | How to choose e/i for collision kernels: 'config' uses e0/i0, 'wyatt_eq' solves for c_eq | [marsdisk/schema.py:696-794] | (none) | Dynamics | candidate-remove | - |
| dynamics.v_rel_mode | literal | pericenter | ohtsuki,pericenter | Relative speed prescription for collision kernels. 'pericenter' (default) uses v_rel=v_K*sqrt((1+e)/(1-e)) near periapsis and is recommended for high-e discs; 'ohtsuki' (legacy, discouraged for e≳0.1) uses v_rel=v_K*sqrt(1.25 e^2+i^2). | [marsdisk/schema.py:696-794] | (none) | Dynamics | candidate-remove | legacy/deprecated wording |
| geometry.mode | literal | 0D | 0D,1D | Spatial dimension: '0D' (radially uniform) or '1D' | [marsdisk/schema.py:24-44] | [scripts/sweeps/sweep_massloss_heatmap_gif.py:100-100] [tests/integration/test_run_one_d_output_parity.py:29-29] [docs/plan/20251208_los_geometry_extension.md:17-17] | Geometry | keep | - |
| init_tau1.enabled | bool | False | true/false | When true, set σ_surf (and derived mass_total) to the Σ_τ=1 value at start-up. | [marsdisk/schema.py:885-903] | [marsdisk/run_zero_d.py:960-960] [docs/plan/20251211_optical_depth_unity_init.md:15-15] | InitTau1 | keep | - |
| init_tau1.scale_to_tau1 | bool | False | true/false | If true, clamp the initial surface density to the chosen Σ_τ=1 cap to avoid headroom=0. | [marsdisk/schema.py:885-903] | [marsdisk/run_zero_d.py:1082-1082] [analysis/run-recipes.md:90-90] | InitTau1 | keep | - |
| init_tau1.tau_field | literal | los | los | Optical-depth field to target when setting Σ_τ=1 (LOS only). | [marsdisk/schema.py:885-903] | [analysis/methods.md:382-382] | InitTau1 | docs-only | - |
| initial.melt_psd.mode | literal | lognormal_mixture | lognormal_mixture,truncated_powerlaw | Shape applied when s0_mode starts with melt_. | [marsdisk/schema.py:637-688] | [marsdisk/run_zero_d.py:876-876] | MeltPSD | keep | - |
| initial.s0_mode | literal | upper | mono,upper,melt_lognormal_mixture,melt_truncated_powerlaw | Initial PSD mode. 'upper' keeps the default cascade, 'mono' forces a mono-disperse bin, and melt_* variants initialise solids with melt-derived grains while removing condensation dust. | [marsdisk/schema.py:621-693] | [marsdisk/run_zero_d.py:886-886] | Initial | keep | - |
| inner_disk_mass.map_to_sigma | literal | analytic | analytic | - | [marsdisk/schema.py:100-119] | [analysis/config_guide.md:190-190] | InnerDiskMass | docs-only | - |
| inner_disk_mass.use_Mmars_ratio | bool | True | true/false | - | [marsdisk/schema.py:100-119] | [marsdisk/run_zero_d.py:977-977] [analysis/config_guide.md:190-190] | InnerDiskMass | keep | - |
| io.correct_fast_blowout | bool | False | true/false | Apply a correction factor when dt greatly exceeds the blow-out timescale. | [marsdisk/schema.py:1710-1747] | [marsdisk/io/writer.py:270-270] [analysis/AI_USAGE.md:141-141] | IO | keep | - |
| io.debug_sinks | bool | False | true/false | Enable verbose sink logging to out/<run_id>/debug/sinks_trace.jsonl | [marsdisk/schema.py:1710-1747] | [tests/integration/test_run_regressions.py:21-21] [docs/modeling-notes.md:41-41] | IO | review | - |
| io.progress.enable | bool | False | true/false | Enable a lightweight progress bar with ETA on the CLI. | [marsdisk/schema.py:1649-1660] | [marsdisk/run_zero_d.py:4912-4912] | Progress | keep | - |
| io.psd_history | bool | True | true/false | Write per-bin PSD history to series/psd_hist.parquet. | [marsdisk/schema.py:1710-1747] | (none) | IO | candidate-remove | - |
| io.quiet | bool | False | true/false | Suppress INFO logging and Python warnings for cleaner CLI output. | [marsdisk/schema.py:1710-1747] | [marsdisk/run_zero_d.py:4902-4902] | IO | keep | - |
| io.step_diagnostics.enable | bool | False | true/false | Write per-step loss diagnostics to disk (CSV or JSONL). | [marsdisk/schema.py:1632-1646] | [marsdisk/analysis/inner_disk_runner.py:268-268] [tests/integration/test_sublimation_phase_gate.py:37-37] | StepDiagnostics | keep | - |
| io.step_diagnostics.format | literal | csv | csv,jsonl | Serialisation format for the per-step diagnostics table. | [marsdisk/schema.py:1632-1646] | [marsdisk/run_zero_d.py:1593-1593] [tests/integration/test_sublimation_phase_gate.py:38-38] | StepDiagnostics | keep | - |
| io.streaming.cleanup_chunks | bool | True | true/false | Delete Parquet chunk files after a successful merge_at_end. | [marsdisk/schema.py:1663-1707] | (none) | Streaming | candidate-remove | - |
| io.streaming.compression | literal | snappy | snappy,zstd,brotli,gzip,none | Compression codec for Parquet chunk outputs. | [marsdisk/schema.py:1663-1707] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:37-37] [docs/plan/20251207_memory_streaming_flush.md:26-26] | Streaming | keep | - |
| io.streaming.enable | bool | True | true/false | Enable chunked streaming writes when memory usage exceeds thresholds (default: on). | [marsdisk/schema.py:1663-1707] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:34-34] [tests/integration/test_supply_headroom_policy.py:76-76] [README.md:52-52] | Streaming | keep | - |
| io.streaming.merge_at_end | bool | True | true/false | Merge Parquet chunks into single files at the end of the run. | [marsdisk/schema.py:1663-1707] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:38-38] [docs/plan/20251207_memory_streaming_flush.md:27-27] | Streaming | keep | - |
| io.streaming.opt_out | bool | False | true/false | Force-disable streaming even if enable=true (safety valve). | [marsdisk/schema.py:1663-1707] | [docs/plan/20251207_memory_streaming_flush.md:28-28] | Streaming | docs-only | - |
| io.substep_fast_blowout | bool | False | true/false | Subdivide steps when dt/t_blow exceeds substep_max_ratio. | [marsdisk/schema.py:1710-1747] | [scripts/admin/analyze_radius_trend.py:225-225] [docs/plan/20251218_temp_supply_env_vars.md:25-25] | IO | keep | - |
| numerics.checkpoint.enabled | bool | False | true/false | Enable periodic checkpoints of the 0D state. | [marsdisk/schema.py:1466-1490] | [scripts/research/run_temp_supply.sh:192-192] [docs/plan/20251215_checkpoint_restart_segmented_sim.md:147-147] | Checkpoint | keep | - |
| numerics.checkpoint.format | literal | pickle | pickle,json | Checkpoint serialisation format. | [marsdisk/schema.py:1466-1490] | [scripts/research/run_temp_supply.sh:195-195] | Checkpoint | keep | - |
| numerics.dt_init | literal | 60000.0 | auto or float | Initial time-step size in seconds or 'auto' for heuristic selection. | [marsdisk/schema.py:1506-1628] | [marsdisk/orchestrator.py:259-259] [tests/integration/test_supply_headroom_policy.py:75-75] [docs/plan/20251221_temp_supply_external_supply.md:80-80] | Numerics | keep | - |
| numerics.eval_per_step | bool | True | true/false | Recompute blow-out size, sinks and ds/dt on every step. | [marsdisk/schema.py:1506-1628] | [marsdisk/analysis/beta_sampler.py:143-143] [tests/integration/test_phase_map_fallback.py:23-23] | Numerics | keep | - |
| numerics.orbit_rollup | bool | True | true/false | Enable per-orbit aggregation of mass loss diagnostics. | [marsdisk/schema.py:1506-1628] | [marsdisk/analysis/beta_sampler.py:144-144] [analysis/overview.md:87-87] | Numerics | keep | - |
| numerics.resume.enabled | bool | False | true/false | Resume a run from an existing checkpoint. | [marsdisk/schema.py:1493-1503] | (none) | Resume | candidate-remove | - |
| numerics.stop_on_blowout_below_smin | bool | False | true/false | Stop the run early if the blow-out grain size falls below the configured minimum size. | [marsdisk/schema.py:1506-1628] | [scripts/research/run_temp_supply.sh:301-301] [docs/plan/20251222_qpr_settings_background.md:93-93] | Numerics | keep | - |
| optical_depth.tau_field | literal | tau_los | tau_los | Optical-depth field used for tau0_target and stop checks (v1 supports tau_los only). | [marsdisk/schema.py:906-927] | [marsdisk/run_zero_d.py:904-904] | OpticalDepth | keep | - |
| phase.allow_liquid_hkl | bool | False | true/false | Allow HKL sublimation when the bulk phase is liquid-dominated | [marsdisk/schema.py:1122-1197] | [tests/integration/test_sublimation_phase_gate.py:57-57] | PhaseConfig | review | - |
| phase.enabled | bool | False | true/false | Enable phase state branching | [marsdisk/schema.py:1122-1197] | [scripts/research/run_temp_supply_sweep.cmd:219-219] [tests/integration/test_sublimation_phase_gate.py:24-24] [README.md:264-264] | PhaseConfig | keep | - |
| phase.source | literal | threshold | map,threshold | Phase source: 'threshold' (simple T-based) or 'map' (external lookup) | [marsdisk/schema.py:1122-1197] | [tests/integration/test_sublimation_phase_gate.py:25-25] [README.md:265-265] | PhaseConfig | review | - |
| phase.tau_field | literal | los | los | Optical-depth field forwarded to phase evaluation (LOS only). | [marsdisk/schema.py:1122-1197] | [marsdisk/run_zero_d.py:641-641] [analysis/methods.md:417-417] | PhaseConfig | keep | - |
| phase.temperature_input | literal | mars_surface | mars_surface,particle | Select temperature passed into the phase map: 'mars_surface' keeps the Mars driver, 'particle' uses the grain equilibrium temperature. | [marsdisk/schema.py:1122-1197] | [marsdisk/run_zero_d.py:636-636] [tests/integration/test_particle_temperature_equilibrium.py:35-35] [analysis/methods.md:415-415] | PhaseConfig | keep | - |
| physics_mode | literal | default | default,full,sublimation_only,collisions_only | Primary physics mode selector. 'default'/'full' runs combined collisions+sinks; 'sublimation_only' disables collisions/blow-out; 'collisions_only' disables sublimation sinks. | [marsdisk/schema.py:1783-1906] | [marsdisk/config_utils.py:143-143] [configs/table_supply_R_sweep.yml:1-1] [tests/fixtures/baseline_summary.json:80-80] [analysis/equation_code_map.json:1293-1293] | Config | keep | - |
| process.state_tagging.enabled | bool | False | true/false | Enable the preliminary state-tagging hook (Phase 0 returns 'solid'). | [marsdisk/schema.py:1075-1081] | (none) | ProcessStateTagging | candidate-remove | - |
| psd.floor.mode | literal | fixed | fixed,evolve_smin,none | - | [marsdisk/schema.py:853-854] | [docs/plan/20251209_assumption_autotrace_plan.md:18-18] | Floor | docs-only | - |
| qstar.coeff_units | literal | ba99_cgs | ba99_cgs,si | Unit system for Qs/B coefficients: 'ba99_cgs' treats sizes in cm, rho in g/cm^3 and converts erg/g→J/kg; 'si' uses inputs as-is. | [marsdisk/schema.py:797-845] | [scripts/research/run_temp_supply.sh:309-309] [docs/plan/20251213_run_temp_supply_sweep_current_settings.md:34-34] | QStar | keep | - |
| qstar.override_coeffs | bool | False | true/false | Use Q_D* coefficient table from config instead of the built-in defaults. | [marsdisk/schema.py:797-845] | [marsdisk/run_zero_d.py:416-416] [docs/plan/20251216_qstar_sio2_mismatch.md:86-86] | QStar | keep | - |
| radiation.freeze_kappa | bool | False | true/false | - | [marsdisk/schema.py:1327-1384] | [analysis/AI_USAGE.md:53-53] | Radiation | docs-only | - |
| radiation.mars_temperature_driver.autogenerate.enabled | bool | False | true/false | Toggle automatic generation of Mars temperature tables. | [marsdisk/schema.py:1233-1262] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:51-51] | MarsTemperatureAutogen | keep | - |
| radiation.mars_temperature_driver.autogenerate.model | literal | slab | slab,hyodo | Cooling model used for auto-generated temperature tables. | [marsdisk/schema.py:1233-1262] | (none) | MarsTemperatureAutogen | candidate-remove | - |
| radiation.mars_temperature_driver.autogenerate.time_unit | literal | day | s,day,yr,orbit | Unit of the generated time column. | [marsdisk/schema.py:1233-1262] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:56-56] | MarsTemperatureAutogen | keep | - |
| radiation.mars_temperature_driver.enabled | bool | False | true/false | Toggle the Mars temperature driver. | [marsdisk/schema.py:1265-1301] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:45-45] [tests/integration/test_particle_temperature_equilibrium.py:37-37] | MarsTemperatureDriverConfig | keep | - |
| radiation.mars_temperature_driver.extrapolation | literal | hold | hold,error | Out-of-sample behaviour for the table driver. | [marsdisk/schema.py:1265-1301] | [scripts/research/run_temp_supply.sh:325-325] | MarsTemperatureDriverConfig | keep | - |
| radiation.mars_temperature_driver.mode | literal | constant | constant,table,hyodo | Driver mode: constant value, external table interpolation, or Hyodo linear cooling. | [marsdisk/schema.py:1265-1301] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:46-46] | MarsTemperatureDriverConfig | keep | - |
| radiation.mars_temperature_driver.table.time_unit | literal | s | s,day,yr,orbit | Unit of the time column; 'orbit' scales with the representative orbital period. | [marsdisk/schema.py:1213-1222] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:48-48] | MarsTemperatureDriverTable | keep | - |
| radiation.qpr_cache.enabled | bool | True | true/false | - | [marsdisk/schema.py:1311-1324] | (none) | QPrCache | candidate-remove | - |
| radiation.source | literal | mars | mars,off,none | Origin of the radiation field driving blow-out (restricted to Mars or off). | [marsdisk/schema.py:1327-1384] | [scripts/runsets/mac/legacy/run_sublim_cooling_mac_6months.sh:43-43] [README.md:212-212] | Radiation | keep | - |
| radiation.tau_gate.enable | bool | False | true/false | - | [marsdisk/schema.py:1304-1308] | [tests/integration/test_run_regressions.py:151-151] [analysis/assumption_registry.jsonl:2-2] | RadiationTauGate | review | - |
| radiation.use_mars_rp | bool | True | true/false | Enable Mars radiation-pressure forcing. Disabled automatically when source='off'. | [marsdisk/schema.py:1327-1384] | [analysis/assumption_registry.jsonl:5-5] | Radiation | docs-only | - |
| radiation.use_solar_rp | bool | False | true/false | Legacy solar radiation toggle retained for logging (always forced off in gas-poor mode). | [marsdisk/schema.py:1327-1384] | (none) | Radiation | candidate-remove | legacy/deprecated wording |
| scope.region | literal | inner | inner | Spatial scope selector. Phase 0 restricts runs to the inner disk. | [marsdisk/schema.py:86-97] | [marsdisk/run_zero_d.py:346-346] [tests/integration/test_phase9_usecases.py:120-120] [analysis/adr/0003-zero-dimensional-model.md:41-41] | Scope | keep | - |
| shielding.fixed_tau1_sigma | literal | null | auto,auto_max or float | Direct specification of Σ_{τ=1} when shielding.mode='fixed_tau1'. Use 'auto' to set Σ_{τ=1}=1/κ_eff at t=0; 'auto_max' takes max(1/κ_eff, Σ_init)×(1+margin). | [marsdisk/schema.py:1387-1445] | [scripts/research/run_temp_supply.sh:371-371] [tests/integration/test_supply_transport_velocity.py:61-61] [README.md:246-246] | Shielding | keep | - |
| shielding.los_geometry.mode | literal | aspect_ratio_factor | aspect_ratio_factor,none | How to scale τ from vertical to Mars line-of-sight; 'aspect_ratio_factor' multiplies by path_multiplier/h_over_r. | [marsdisk/schema.py:1390-1406] | [docs/plan/20251208_los_geometry_extension.md:17-17] | LOSGeometry | docs-only | - |
| shielding.mode | literal | psitau | off,psitau,fixed_tau1,table | - | [marsdisk/schema.py:1387-1445] | [marsdisk/run_zero_d.py:599-599] [tests/integration/test_supply_transport_velocity.py:60-60] [docs/plan/20251216_temp_supply_sigma_tau1_headroom.md:23-23] | Shielding | keep | - |
| sinks.enable_gas_drag | bool | False | true/false | Enable gas drag on surface grains. Disabled by default as gas-poor disks are dominated by radiation and collisions (Takeuchi & Lin 2003; Strubbe & Chiang 2006). | [marsdisk/schema.py:1051-1072] | [tools/diagnostics/beta_map.py:603-603] [tests/integration/test_sublimation_smol_sink.py:33-33] [analysis/assumption_registry.jsonl:5-5] | Sinks | keep | - |
| sinks.enable_sublimation | bool | True | true/false | - | [marsdisk/schema.py:1051-1072] | [tools/diagnostics/beta_map.py:602-602] [tests/integration/test_sublimation_phase_gate.py:21-21] [analysis/assumption_registry.jsonl:5-5] | Sinks | keep | - |
| sinks.hydro_escape.enable | bool | False | true/false | - | [marsdisk/schema.py:1028-1048] | (none) | HydroEscapeConfig | candidate-remove | - |
| sinks.mode | literal | sublimation | none,sublimation | - | [marsdisk/schema.py:1051-1072] | [tools/diagnostics/beta_map.py:601-601] [tests/integration/test_reproducibility.py:43-43] [analysis/AI_USAGE.md:54-54] | Sinks | keep | - |
| sinks.rp_blowout.enable | bool | True | true/false | - | [marsdisk/schema.py:1022-1025] | [docs/devnotes/phase7_minimal_diagnostics.md:47-47] | RPBlowoutConfig | docs-only | - |
| sinks.sub_params.enable_liquid_branch | bool | True | true/false | Enable HKL Clausius liquid branch when temperatures exceed psat_liquid_switch_K | [marsdisk/schema.py:930-1019] | [tests/integration/test_sublimation_phase_gate.py:58-58] [analysis/equations.md:531-531] | SublimationParamsModel | review | - |
| sinks.sub_params.mass_conserving | bool | False | true/false | If true, ds/dt-driven shrinkage does not remove mass except when grains cross the blow-out size within a step; crossing mass is treated as blow-out instead of a sublimation sink. | [marsdisk/schema.py:930-1019] | [analysis/run-recipes.md:183-183] | SublimationParamsModel | docs-only | - |
| sinks.sub_params.mode | literal | logistic | logistic,hkl,hkl_timescale | Sublimation model: 'logistic' (simple), 'hkl' (Hertz-Knudsen-Langmuir), 'hkl_timescale' | [marsdisk/schema.py:930-1019] | [marsdisk/run_zero_d.py:616-616] [tests/integration/test_sublimation_phase_gate.py:22-22] [analysis/AI_USAGE.md:54-54] | SublimationParamsModel | keep | - |
| sinks.sub_params.psat_model | literal | auto | auto,clausius,tabulated | Saturation pressure model: 'auto' (default), 'clausius', or 'tabulated' | [marsdisk/schema.py:930-1019] | [tests/integration/test_sublimation_phase_gate.py:92-92] [README.md:458-458] | SublimationParamsModel | review | - |
| sinks.sublimation_location | literal | surface | surface,smol,both | Select whether sublimation acts via the surface ODE, the Smol solver, or both. | [marsdisk/schema.py:1051-1072] | [marsdisk/run_zero_d.py:1151-1151] [tests/integration/test_sublimation_smol_sink.py:34-34] [analysis/config_guide.md:237-237] | Sinks | keep | - |
| sizes.apply_evolved_min_size | bool | False | true/false | If true, the evolved minimum size participates in s_min_effective. | [marsdisk/schema.py:597-618] | [analysis/assumption_registry.jsonl:3-3] | Sizes | docs-only | - |
| sizes.evolve_min_size | bool | False | true/false | Enable dynamic evolution of the minimum grain size. | [marsdisk/schema.py:597-618] | [marsdisk/analysis/massloss_sampler.py:70-70] [tests/integration/test_min_size_evolution_hook.py:41-41] [analysis/assumption_registry.jsonl:3-3] | Sizes | keep | - |
| supply.enabled | bool | True | true/false | Master switch for external supply; false forces zero production. | [marsdisk/schema.py:446-552] | [scripts/research/run_temp_supply.sh:328-328] [tests/integration/test_supply_headroom_policy.py:67-67] [docs/plan/20251221_temp_supply_external_supply.md:79-79] | Supply | keep | - |
| supply.feedback.enabled | bool | False | true/false | - | [marsdisk/schema.py:233-277] | [scripts/research/run_temp_supply.sh:210-210] [tests/integration/test_supply_positive.py:107-107] [analysis/methods.md:294-294] | SupplyFeedback | keep | - |
| supply.feedback.tau_field | literal | tau_los | tau_los | Optical-depth field to monitor for feedback control (LOS only). | [marsdisk/schema.py:233-277] | [scripts/research/run_temp_supply.sh:216-216] [tests/integration/test_supply_positive.py:113-113] [analysis/methods.md:301-301] | SupplyFeedback | keep | - |
| supply.headroom_policy | literal | clip | clip,spill | clip: limit applied supply by Σ_tau1 headroom. spill: always apply supply then remove any τ>1 overflow. Legacy knob; non-default use is deprecated. | [marsdisk/schema.py:446-552] | [marsdisk/config_validator.py:338-338] [tests/integration/test_supply_headroom_policy.py:68-68] [analysis/glossary.md:31-31] | Supply | keep | legacy/deprecated wording |
| supply.injection.mode | literal | min_bin | min_bin,powerlaw_bins | Injection mapping: 'min_bin' targets the smallest valid bin; 'powerlaw_bins' spreads mass across a size range. | [marsdisk/schema.py:396-434] | [scripts/research/run_temp_supply.sh:236-236] [analysis/methods.md:338-338] | SupplyInjection | keep | - |
| supply.injection.velocity.blend_mode | literal | rms | rms,linear | Blend effective e/i via RMS or linear mixing. | [marsdisk/schema.py:353-393] | [scripts/research/run_temp_supply.sh:269-269] [tests/integration/test_supply_transport_velocity.py:67-67] | SupplyInjectionVelocity | keep | - |
| supply.injection.velocity.mode | literal | inherit | inherit,fixed_ei,factor | inherit: use kernel baseline. fixed_ei: override with e_inj/i_inj. factor: scale baseline v_rel. | [marsdisk/schema.py:353-393] | [scripts/research/run_temp_supply.sh:259-259] [tests/integration/test_supply_transport_velocity.py:64-64] [analysis/methods.md:341-341] | SupplyInjectionVelocity | keep | - |
| supply.injection.velocity.weight_mode | literal | delta_sigma | delta_sigma,sigma_ratio | delta_sigma: ΔΣ/(Σ+ΔΣ). sigma_ratio: ΔΣ/max(Σ,eps). | [marsdisk/schema.py:353-393] | [scripts/research/run_temp_supply.sh:270-270] | SupplyInjectionVelocity | keep | - |
| supply.mode | literal | const | const,table,powerlaw,piecewise | Supply mode: 'const' (default), 'table', 'powerlaw', or 'piecewise'. Non-default modes are deprecated removal candidates. | [marsdisk/schema.py:446-552] | [scripts/research/run_temp_supply.sh:330-330] [tests/integration/test_supply_positive.py:23-23] [analysis/config_guide.md:444-444] | Supply | keep | legacy/deprecated wording |
| supply.reservoir.depletion_mode | literal | hard_stop | hard_stop,taper | When 'taper', linearly ramp the rate down once the remaining mass falls below taper_fraction of the total. | [marsdisk/schema.py:188-230] | [scripts/research/run_temp_supply.sh:205-205] [tests/integration/test_supply_positive.py:60-60] | SupplyReservoir | keep | - |
| supply.reservoir.enabled | bool | False | true/false | Enable finite reservoir accounting; false keeps the legacy infinite reservoir behaviour. | [marsdisk/schema.py:188-230] | [scripts/research/run_temp_supply.sh:203-203] [tests/integration/test_supply_positive.py:58-58] [analysis/methods.md:322-322] | SupplyReservoir | keep | legacy/deprecated wording |
| supply.table.interp | literal | linear | linear | - | [marsdisk/schema.py:161-163] | (none) | SupplyTable | candidate-remove | - |
| supply.temperature.enabled | bool | False | true/false | - | [marsdisk/schema.py:290-320] | [scripts/research/run_temp_supply.sh:221-221] [tests/integration/test_supply_positive.py:157-157] [analysis/methods.md:309-309] | SupplyTemperature | keep | - |
| supply.temperature.mode | literal | scale | scale,table | Temperature coupling mode: analytic scale or table-driven lookup. | [marsdisk/schema.py:290-320] | [scripts/research/run_temp_supply.sh:222-222] | SupplyTemperature | keep | - |
| supply.temperature.table.value_kind | literal | scale | scale,rate | Whether the table values represent a dimensionless scale or an absolute rate. | [marsdisk/schema.py:280-287] | [scripts/research/run_temp_supply.sh:230-230] | SupplyTemperatureTable | keep | - |
| supply.transport.headroom_gate | literal | hard | hard,soft | Headroom limiter applied to deep→surface flux; 'soft' is reserved for future smoothing. | [marsdisk/schema.py:323-350] | [scripts/research/run_temp_supply.sh:256-256] [docs/plan/20251221_temp_supply_external_supply.md:81-81] | SupplyTransport | keep | - |
| supply.transport.mode | literal | direct | direct,deep_mixing | direct: legacy headroom-gated surface injection. deep_mixing: send supply into deep then mix up. deep_mixing is non-default and a deprecated removal candidate. | [marsdisk/schema.py:323-350] | [scripts/research/run_temp_supply.sh:246-246] [tests/integration/test_supply_transport_velocity.py:62-62] [docs/plan/20250305_optical_depth_mitigation.md:124-124] | SupplyTransport | keep | legacy/deprecated wording |
| surface.collision_solver | literal | smol | surface_ode,smol | Collision/outflux update scheme. 'surface_ode' preserves the legacy Wyatt-style implicit step (suited to e<<0.1), while 'smol' routes collisions through the Smoluchowski operator. Default is 'smol' to avoid overestimating t_coll in high-eccentricity (e~0.1–0.5) regimes. | [marsdisk/schema.py:867-882] | [marsdisk/run_zero_d.py:781-781] [tests/integration/test_supply_positive.py:158-158] [docs/plan/20251212_simulation_methodology_cleanup.md:113-113] | Surface | keep | legacy/deprecated wording |
| surface.freeze_sigma | bool | False | true/false | - | [marsdisk/schema.py:867-882] | [analysis/AI_USAGE.md:53-53] | Surface | docs-only | - |
| surface.init_policy | literal | clip_by_tau1 | clip_by_tau1,none | - | [marsdisk/schema.py:867-882] | [marsdisk/run_zero_d.py:999-999] [docs/plan/20251219_tau_clip_gate_review.md:72-72] | Surface | keep | - |
| surface.use_tcoll | bool | True | true/false | - | [marsdisk/schema.py:867-882] | [marsdisk/run_zero_d.py:759-759] [tests/integration/test_blowout_gate.py:103-103] [analysis/assumption_registry.jsonl:4-4] | Surface | keep | - |
| surface_energy.enabled | bool | False | true/false | - | [marsdisk/schema.py:859-864] | [analysis/CHANGELOG.md:14-14] | SurfaceEnergy | docs-only | - |

## Env/CLI toggles (non-schema)
### Environment variables
| name | defaults seen | refs | status | notes |
| --- | --- | --- | --- | --- |
| `ALLOW_TL2003` | (none) | [AGENTS.md:27-27] | docs-only | doc-only mention; no os.environ read found |
| `FORCE_STREAMING_OFF` | (none) | [marsdisk/run_one_d.py:690-690] | keep | - |
| `FORCE_STREAMING_ON` | (none) | [marsdisk/run_one_d.py:691-691] | keep | - |
| `IO_STREAMING` | (none) | [marsdisk/run_one_d.py:685-685] | keep | - |
| `MARSDISK_DISABLE_NUMBA` | "" | [marsdisk/io/tables.py:30-30] | keep | - |
| `MARSDISK_THREAD_GUARD` | "1" | [marsdisk/analysis/beta_sampler.py:32-32] | keep | - |
| `MARS_DISK_EPSILON_MIX` | (none) | [tools/derive_supply_rate.py:172-172] | keep | - |
| `MARS_DISK_SIGMA_TAU1` | (none) | [tools/derive_supply_rate.py:171-171] | keep | - |
| `MKL_NUM_THREADS` | "1" | [marsdisk/analysis/beta_sampler.py:36-36] | keep | - |
| `NUMBA_NUM_THREADS` | "1" | [marsdisk/analysis/beta_sampler.py:38-38] | keep | - |
| `OMP_NUM_THREADS` | "1" | [marsdisk/analysis/beta_sampler.py:35-35] | keep | - |
| `OPENBLAS_NUM_THREADS` | "1" | [marsdisk/analysis/beta_sampler.py:37-37] | keep | - |
| `PYTHONPATH` | (none) | [scripts/sweeps/sweep_heatmaps.py:1219-1219] | keep | - |
- Note: shell-based scripts may reference env vars not captured here (e.g., RUN_DIR, PLOT_MAX_ROWS).

### CLI flags (run_zero_d)
- Definitions: [marsdisk/run_zero_d.py:4819-4874]
- `--config` (required)
- `--progress` (enable progress bar)
- `--quiet/--no-quiet` (override logging quiet mode)
- `--enforce-mass-budget` (abort when tolerance exceeded)
- `--sinks` (override `sinks.mode`)
- `--physics-mode` (override `physics_mode`)
- `--override` (dotted-path overrides)
- `--auto-tune` (enable runtime auto-tuning)
- `--auto-tune-profile` (select auto-tune profile)
