# Surface Thickness Parameter Study Plan (2026-01-12)

Purpose
-------
Clarify how "surface thickness" is represented in the model and treat it as a
sensitivity parameter rather than a fixed physical quantity. Provide a compact,
two-pattern inclination study that is feasible under the time constraint.

Decision summary
----------------
- Treat "surface thickness" as a sensitivity parameter, not a single physical thickness.
- Define optical_depth.tau0_target as tau_los at initialization (policy below).
- Vary only dynamics.i0; keep H_factor and h_over_r fixed.
- Use kernel_ei_mode="config" so i_used equals i0.
- Two-pattern study only (A/B).

Background and definitions
--------------------------
The model does not define a single geometric surface thickness. Instead, three
separate proxies contribute to thickness-like effects:

1) Collision-kernel scale height (Smol kernel geometry)
   - Used only in the collision kernel construction.
   - For kernel_H_mode="ia", the scale height is:
     H = H_factor * i_used * a
   - i_used is the inclination used by the kernel:
     - kernel_ei_mode="config": i_used = dynamics.i0
     - kernel_ei_mode="wyatt_eq": i_used derived from c_eq
   - a is orbital radius:
     - 0D: representative radius from disk.geometry (midpoint of r_in_RM/r_out_RM)
     - 1D: per-cell radius from the radial grid

2) Optical-depth skin selection (blowout reservoir)
   - blowout.layer=surface_tau_le_1 selects the tau<=1 surface skin.
   - This is a reservoir definition, not a geometric thickness.

3) Line-of-sight (LOS) geometry scaling for tau
   - tau_los = tau_vert * (path_multiplier / h_over_r)
   - h_over_r is a geometric aspect ratio proxy; it affects optical depth
     diagnostics and shielding, but does not directly set the collision kernel H.

Optical-depth initialization policy (2026-01-12 update)
-------------------------------------------------------
Define tau0_target as the line-of-sight optical depth tau_los at initialization.

Initialization rules:
- tau_los = kappa_surf * Sigma_surf * los_factor
- Sigma_surf0 = tau0_target / (kappa_surf * los_factor)
- This guarantees tau_los_init == tau0_target by construction.

Shielding usage:
- Shielding uses tau_los as the input argument; tau_eff = phi(tau_los) * tau_los is derived.
- Treat tau_eff as an outcome, not a target.

Out of scope:
- If a future study needs tau0_target to represent tau_eff, solve the implicit equation in tau_los.

Note: mu_reference_tau for supply normalization should be interpreted as a
tau_los reference to stay consistent with the above definition.

Current defaults
----------------
(run_sweep uses scripts/runsets/common/base.yml)
- dynamics.i0 = 0.05 rad
- dynamics.H_factor = 1.0
- shielding.los_geometry.h_over_r = 1.0

There is no explicit literature anchor in analysis for the specific choice
of i0=0.05; it is currently a working assumption.

Study scope and constraints
---------------------------
- Two patterns total (time constraint).
- Focus the study on inclination (i0) to avoid conflating multiple proxies.
- Keep H_factor=1.0 and h_over_r=1.0 fixed to isolate i0.
- Keep kernel_ei_mode="config" so i_used equals i0.
- Keep optical_depth.tau0_target fixed across A/B.

Inclination parameter study (two patterns only)
-----------------------------------------------
Pattern A (control): dynamics.i0 = 0.05 rad; dynamics.H_factor = 1.0; h_over_r = 1.0.
Pattern B (thicker disk test): dynamics.i0 = 0.10 rad; dynamics.H_factor = 1.0; h_over_r = 1.0.

Rationale:
- H scales linearly with i; doubling i0 doubles H and reduces midplane number
  density, which should weaken collision rates and alter sub-blowout supply.
- Pattern B is fixed at i0=0.10 rad to keep the study to two runs.

Execution options
-----------------
Choose one and keep it consistent across A/B.
1) run_sweep pipeline:
   - Base config: scripts/runsets/common/base.yml
   - Overrides: apply dynamics.i0 only
2) Direct CLI:
   - Use configs/base.yml (or a dedicated copy)
   - Apply overrides: --override dynamics.i0=0.05 or 0.10

Keep all other parameters identical to baseline to isolate i0 effects
(including optical_depth.tau0_target, tables, and physics toggles).

Safety checklist (for a safe, reproducible two-run study)
--------------------------------------------------------
- Do not edit the baseline config; change only dynamics.i0 via overrides.
- Keep dynamics.rng_seed fixed across A/B (set dynamics.rng_seed=0 for both runs).
- Keep kernel_ei_mode="config", i_mode="fixed", H_factor=1.0, h_over_r=1.0.
- Use separate outdir per pattern (follow the out/<timestamp>... rule).
- Keep IO streaming settings consistent across both runs.
- Run evaluation_system on the per-run outdir (avoid pointing at the global out/).
- Record run_card metadata and a short comparison note.
- Preserve TODO(REF:i0_default_0p05_origin_v1) until a literature anchor is found.
- Confirm i0_unit is rad (or explicitly set i0_unit=deg when using degrees).
- Ensure i_mode is not obs_tilt_spread and no RNG sampling overrides i0.
- Keep geometry mode and radial bounds identical (0D vs 1D, r_in_RM/r_out_RM).
- Avoid changing e_profile/e0 unless the study explicitly targets those effects.
- Verify shielding, blowout, sinks, and supply toggles stay identical between runs.
- Keep dt_init, dt_over_t_blow_max, and substep_fast_blowout settings identical.
- Fix the same Q_pr/phi/temperature tables and paths across both runs.
- Avoid implicit overrides from environment variables (IO_STREAMING, FORCE_STREAMING_OFF).
- If using Windows .cmd runsets, execute preflight_checks.py before the sweep.
- Confirm mass_budget.csv parses and max error stays within 0.5%.
- Update run_card.md with evaluation results and tool versions.

Implementation checklist (checkboxes)
------------------------------------
- [x] Decide execution path (run_sweep pipeline or direct CLI) and keep it consistent.
- [x] Confirm baseline config and record its path (do not edit it).
- [x] Lock i0_unit (rad), kernel_ei_mode="config", i_mode="fixed".
- [x] Fix geometry (0D/1D, r_in_RM/r_out_RM, Nr) and keep it identical.
- [x] Fix tables and physics toggles (Q_pr, Phi, sinks, shielding, blowout, supply).
- [x] Fix numerics (dt_init, dt_over_t_blow_max, substep_fast_blowout).
- [x] Fix RNG seed (set dynamics.rng_seed=0).
- [x] Confirm optical_depth.tau0_target is unchanged across A/B.
- [x] Prepare two overrides: i0=0.05 (A) and i0=0.10 (B).
- [x] Assign distinct outdir per run (follow out/<timestamp>... rule).
- [ ] (Windows only) Run preflight_checks.py before launching.
- [x] Execute Pattern A, then Pattern B (same environment).
- [x] Run evaluation_system on each run’s outdir (not on global out/).
- [x] Verify mass_budget.csv parses and |error|<0.5%.
- [x] Record run_card.md metadata and evaluation results.
- [x] Compare metrics (M_out_dot, M_loss, t_coll, tau_los_mars, sigma_tau1).
- [x] Write a short A/B comparison note and link to run outputs.
- [ ] Keep TODO(REF:i0_default_0p05_origin_v1) until a source is identified.

Execution commands (direct CLI, short trial)
--------------------------------------------
Short trial uses numerics.t_end_years=0.1. Remove that override for the full
2-year run. These commands use configs/base.yml and set the outdir to the
required naming format while keeping all physics identical except for
dynamics.i0 (and a fixed rng_seed).

```bash
RUN_TS=$(date +%Y%m%d-%H%M)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)
SEED=0
SHORT_YEARS=0.1
OUT_A="out/${RUN_TS}_surface_thickness_i0_0p05__${GIT_SHA}__seed${SEED}"
OUT_B="out/${RUN_TS}_surface_thickness_i0_0p10__${GIT_SHA}__seed${SEED}"

python -m marsdisk.run --config configs/base.yml \
  --override dynamics.i0=0.05 \
  --override dynamics.rng_seed=${SEED} \
  --override numerics.t_end_years=${SHORT_YEARS} \
  --override io.outdir="${OUT_A}"

python -m marsdisk.run --config configs/base.yml \
  --override dynamics.i0=0.10 \
  --override dynamics.rng_seed=${SEED} \
  --override numerics.t_end_years=${SHORT_YEARS} \
  --override io.outdir="${OUT_B}"

python -m tools.evaluation_system --outdir "${OUT_A}"
python -m tools.evaluation_system --outdir "${OUT_B}"
```

Outputs and comparison metrics
------------------------------
Compare between Pattern A and B:
- M_out_dot, M_loss (summary.json and series output)
- t_coll diagnostics (if available)
- tau_los_mars, sigma_tau1, kappa (series diagnostics)
- mass budget error (checks/mass_budget.csv)
- tau_los_mars at t=0 should equal tau0_target (sanity check).

Short trial results (0.1 years)
-------------------------------
Runs:
- A: out/20260112-1824_surface_thickness_i0_0p05__cdfe878f8__seed0
- B: out/20260112-1824_surface_thickness_i0_0p10__cdfe878f8__seed0

Evaluation:
- evaluation_system: PASS (both)
- mass_budget_max_error_percent: 1.1868e-13 (both)

Key metrics (A vs B):
- M_loss: 1.361590775e-05 vs 1.361464429e-05 (Δ=-1.263e-09, ratio=0.999907)
- M_out_dot (sum mean): 4.31463e-12 vs 4.31423e-12 (sum max: 5.45295e-12 vs 5.45244e-12)
- t_coll_kernel_min (median): 1.80044e-08 vs 3.60090e-08 (B ~2x A)
- tau_los_mars mean: init 1.00011 vs 1.00011, final 1.18232 vs 1.18231
- Sigma_tau1 mean: 3623.164 vs 3623.180

Documentation updates
---------------------
- Add an explicit statement in analysis/thesis/introduction.md or
  analysis/thesis_sections/02_related_work/00_prior_work.md that surface thickness is a
  sensitivity parameter and is represented via the proxies above.
- If needed, state explicitly that tau0_target refers to tau_los (not tau_eff).
- If needed, register i0=0.05 as an unknown reference in
  analysis/UNKNOWN_REF_REQUESTS.jsonl.

Deliverables
------------
- Two-run inclination study (Pattern A/B).
- Short summary of impacts on M_out_dot and M_loss.
- Documentation note about thickness proxies and parameter-study treatment.

Risks / open questions
----------------------
- "Surface thickness" can be interpreted as collision-kernel H, tau<=1 skin,
  or LOS geometry; the study focuses only on H via i0.
- The i0 baseline is a modeling choice rather than a documented literature value.
