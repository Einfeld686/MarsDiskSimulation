# Changelog

## [Unreleased]
- Added explicit `radiation.use_mars_rp` / `use_solar_rp` toggles and new `blowout.target_phase`/`layer`
  configuration keys to make the Mars-only surface blow-out contract explicit.
- Tightened the runtime blow-out gating (β threshold, Σ_{τ≤1} skin, solid-only phase guard) and
  recorded the step-level decisions in the series/diagnostics outputs together with the cumulative
  `M_loss_surface_solid_marsRP` tracking.
- Extended the I/O metadata (Parquet units/definitions, summary, mass budget) and shipped a sample
  `configs/phase3_mars_blowout_solid_surface.yaml` plus regression tests covering the new switches.
- Added Phase 6 surface gate support: `blowout.gate_mode` (`none`/`sublimation_competition`/`collision_competition`)
  scales blow-out outflux via `f_gate=t_solid/(t_solid+t_blow)`; defaults to `none` for bitwise compatibility and
  emits new diagnostics (`t_solid_s`, `blowout_gate_factor`) and summary stats.

## [2025-12-11] Documentation Pipeline & Phase Logic Refinement
- **Document Synchronization**: Integrated `DocSyncAgent` with `analysis-doc-tests` and `coverage-guard` targets (`make analysis-sync`, `make analysis-coverage-guard`).
- **Temperature Driver**: Introduced `mars_temperature_driver` to decouple T_M source logic; deprecated `temps.T_M` in favor of `radiation.TM_K` or driver tables.
- **Phase Evaluation**: Centralized phase state logic into `PhaseEvaluator`. `checks_psat_auto_01` validates `psat_model="auto"` behavior (tabulated/local-fit/Clausius fallback).
- **Visualization Docs**: Updated `analysis/tools/visualizations.md` to reflect `tools/plotting/` structure.
