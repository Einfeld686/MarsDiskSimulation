# Sublimation Audit

## Context
- End-to-end wiring for sublimation is captured in `docs/_tmp/sinks_callgraph.txt`.
- All references below use the current working tree (line numbers are 1-based).

## Static Wiring Observations
- Temperature precedence: `marsdisk/run.py:303-308` prefers `cfg.radiation.TM_K` when present, falling back to `cfg.temps.T_M`. Base sweeps (`configs/base.yml`, `configs/mars_0d_baseline.yaml`) set `radiation.TM_K`, so varying `temps.T_M` has no effect on sublimation, β, or blow-out metrics.
- Sink gating: `marsdisk/run.py:411-423` drops all sink processing (`t_sink=None`, `s_sub_component=0`) when `sinks.mode == "none"`, regardless of `enable_sublimation`.
- Sink time-scale path: `marsdisk/physics/sinks.py:52-116` evaluates sublimation via `grain_temperature_graybody` and `s_sink_from_timescale`; negative gas drag toggles leave only sublimation in play.
- Surface losses: `marsdisk/physics/surface.py:108-169` shows sink flux (`Σ/t_sink`) entering the IMEX step and feeding cumulative loss (`M_sink_cum`) in `marsdisk/run.py:458-487`.
- Output accounting: `summary.json` now records both total and sink-specific loss terms (`marsdisk/run.py:591-605`).

## Checklist Highlights
| Check | Result | Evidence |
| --- | --- | --- |
| `sinks.mode: "none"` kills sinks | ✅ No sublimation processing when mode is `"none"` | `marsdisk/run.py:417-487` |
| Temperature source | ⚠️ Still defaults to `radiation.TM_K`; `temps.T_M` ignored when override present | `marsdisk/run.py:303-308`; configs with `radiation.TM_K` |
| Units (K, m, s) | ✅ All core routines expect SI; no Celsius conversions observed | `marsdisk/physics/radiation.py:221-268`, `marsdisk/grid.py:20-52` |
| Time-scale reasonableness | ✅ Logistic model yields `t_sink ~ 0.09 T_orb` at 4 R_M for 2000 K (manual probe) |
| Output plumbing | ✅ `M_loss` aggregates blow-out and sinks; sink-only term exposed as `M_loss_from_sinks` | `marsdisk/run.py:551-569` |
| Temperature response of β, `s_blow` | ✅ Functions depend on `T_M` (see probe in audit) but inherit the override bias | `marsdisk/physics/radiation.py:221-268` |
| Reproducibility | ✅ RNG seeded via `cfg.dynamics.rng_seed or DEFAULT_SEED` | `marsdisk/run.py:205-214` |

## Minimal Reproduction Suite
- Assets live in `diagnostics/minimal/`:
  - `run_minimal_matrix.py` sweeps `T = {1800, 3000, 4500, 6000}` K and `r/R_M = {3.3, 6.0}` across three sink toggles, writing configs, run products, and plots.
  - Results: `diagnostics/minimal/results/summary.csv`, logical checks in `diagnostics/minimal/results/conditions.json` (`A`–`E` all `true`), and plots `diagnostics/minimal/plots/M_loss_vs_T.png`, `diagnostics/minimal/plots/M_loss_vs_r.png`.
- Usage:
  ```bash
  python diagnostics/minimal/run_minimal_matrix.py
  ```
  Produces 24 case directories under `diagnostics/minimal/runs/…` with each `summary.json` preserving `T_M_source == "temps.T_M"`.
- Behavioural takeaways:
  - With `sinks.mode="sublimation"` and `enable_sublimation=true`, `M_loss` rises monotonically with temperature (`B`) and is larger at 3.3 R_M than 6.0 R_M (`C`).
  - The control (`enable_sublimation=false`) consistently yields the minimum loss for every `(T, r)` pair (`A`).
  - β and `s_blow_m` vary strongly with T and r (`E`), confirming the physical scaling once the temperature override is removed.

## Debug Logging Extension
- Added opt-in sink tracing via `io.debug_sinks` (default `false`) in the configuration schema (`marsdisk/schema.py:271-277`).
- When enabled, `marsdisk/run.py:432-503` records per-step diagnostics to `out/debug/sinks_trace.jsonl`, covering:
  - `T_M` and grey-body `T_d`
  - Instantaneous sublimation mass loss rate (`total_sublimation_dm_dt_kg_s`)
  - Cumulative sink/blow-out mass inventories (kg and M_Mars)
  - Active sink mode flags and the `t_sink` applied
- `summary.json` now exposes `M_loss_from_sinks`/`M_loss_from_sublimation` for quick post-run attribution.

## Root Cause & Fix Recommendation
- **Problem**: Sweeps kept `radiation.TM_K` fixed (often 2500 K) while varying `temps.T_M`. Because the runtime prioritises `radiation.TM_K`, all sublimation, β, and `s_blow` calculations stayed locked to 2500 K, producing the observed flat response.
- **Minimal Fix Options**:
  1. Remove or null out `radiation.TM_K` in standard configs (`configs/base.yml`, `configs/mars_0d_baseline.yaml`) so that `temps.T_M` is actually used.
  2. Or, change the precedence in `marsdisk/run.py:303-308` to honour `temps.T_M` unless an explicit gas-rich toggle (`ALLOW_TL2003`) is enabled. Example patch:
     ```diff
       if cfg.radiation and cfg.radiation.TM_K is not None:
     -    T_M = cfg.radiation.TM_K
     -    T_M_source = "radiation.TM_K"
     +    if getattr(cfg.sinks, "allow_TM_override", False):
     +        T_M = cfg.radiation.TM_K
     +        T_M_source = "radiation.TM_K"
     +    else:
     +        T_M = cfg.temps.T_M
     +        T_M_source = "temps.T_M"
       else:
         T_M = cfg.temps.T_M
         T_M_source = "temps.T_M"
     ```
  - Either approach restores the expected temperature dependence under the gas-poor default scenario.

## Next Steps
1. Decide on preferred override policy (config clean-up vs. code guard) and implement.
2. Re-run the minimal matrix to confirm `M_loss` trends remain monotonic post-fix.
3. If sweeps require gas-rich scenarios, add an explicit configuration field to re-enable `radiation.TM_K` with documentation explaining its impact.
