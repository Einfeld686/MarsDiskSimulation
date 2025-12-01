"""Output helper utilities.

The routines in this module provide thin wrappers around :mod:`pandas`
functionality to serialise simulation results.  Parquet is used for time
series data, JSON for run summaries and CSV for diagnostic mass budget
checks.  All functions ensure that destination directories are created when
necessary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to a Parquet file using ``pyarrow``.

    Parameters
    ----------
    df:
        Table to serialise.
    path:
        Destination file path.
    """
    _ensure_parent(path)
    units = {
        "time": "s",
        "dt": "s",
        "T_M_used": "K",
        "rad_flux_Mars": "W m^-2",
        "Omega_s": "s^-1",
        "t_orb_s": "s",
        "t_blow_s": "s",
        "t_blow": "s",
        "t_coll": "s",
        "t_solid_s": "s",
        "t_sink_total_s": "s",
        "t_sink_surface_s": "s",
        "t_sink_sublimation_s": "s",
        "t_sink_gas_drag_s": "s",
        "r_m": "m",
        "r_RM": "R_M",
        "r_m_used": "m",
        "r_RM_used": "R_M",
        "a_blow_at_smin": "m",
        "Q_pr_used": "dimensionless",
        "Q_pr_blow": "dimensionless",
        "Q_pr_at_smin": "dimensionless",
        "beta_at_smin": "dimensionless",
        "beta_eff": "dimensionless",
        "dt_over_t_blow": "dimensionless",
        "ts_ratio": "dimensionless",
        "a_blow_step": "m",
        "prod_subblow_area_rate": "kg m^-2 s^-1",
        "M_out_dot": "M_Mars s^-1",
        "M_sink_dot": "M_Mars s^-1",
        "dM_dt_surface_total": "M_Mars s^-1",
        "mloss_blowout_rate": "M_Mars s^-1",
        "mloss_sink_rate": "M_Mars s^-1",
        "mloss_total_rate": "M_Mars s^-1",
        "M_out_dot_avg": "M_Mars s^-1",
        "M_sink_dot_avg": "M_Mars s^-1",
        "dM_dt_surface_total_avg": "M_Mars s^-1",
        "fast_blowout_factor_avg": "dimensionless",
        "dSigma_dt_blowout": "kg m^-2 s^-1",
        "dSigma_dt_sinks": "kg m^-2 s^-1",
        "dSigma_dt_total": "kg m^-2 s^-1",
        "dSigma_dt_sublimation": "kg m^-2 s^-1",
        "n_substeps": "count",
        "chi_blow_eff": "dimensionless",
        "mass_lost_by_blowout": "M_Mars",
        "mass_lost_by_sinks": "M_Mars",
        "mass_lost_sinks_step": "M_Mars",
        "mass_lost_sublimation_step": "M_Mars",
        "mass_lost_hydro_step": "M_Mars",
        "mass_lost_surface_solid_marsRP_step": "M_Mars",
        "M_loss_rp_mars": "M_Mars",
        "M_loss_surface_solid_marsRP": "M_Mars",
        "M_loss_hydro": "M_Mars",
        "M_hydro_cum": "M_Mars",
        "cum_mloss_blowout": "M_Mars",
        "cum_mloss_sink": "M_Mars",
        "cum_mloss_total": "M_Mars",
        "fast_blowout_ratio": "dimensionless",
        "fast_blowout_factor": "dimensionless",
        "fast_blowout_corrected": "bool",
        "bin_index": "count",
        "s_bin_center": "m",
        "N_bin": "dimensionless",
        "fast_blowout_flag_gt3": "bool",
        "fast_blowout_flag_gt10": "bool",
        "s_min_evolved": "m",
        "ds_dt_sublimation": "m s^-1",
        "blowout_gate_factor": "dimensionless",
        "F_abs_geom": "W m^-2",
        "F_abs_geom_qpr": "W m^-2",
        "F_abs": "W m^-2",
        "sigma_tau1": "kg m^-2",
        "Sigma_tau1": "kg m^-2",
        "Sigma_tau1_active": "kg m^-2",
        "sigma_tau1_active": "kg m^-2",
        "tau_vertical": "dimensionless",
        "kappa_eff": "m^2 kg^-1",
        "kappa_surf": "m^2 kg^-1",
        "kappa_Planck": "m^2 kg^-1",
        "tau_eff": "dimensionless",
        "phi_effective": "dimensionless",
        "psi_shield": "dimensionless",
        "area_m2": "m^2",
        "prod_subblow_area_rate": "kg m^-2 s^-1",
        "s_min_effective": "m",
        "s_min": "m",
        "s_peak": "m",
        "qpr_mean": "dimensionless",
        "chi_blow_eff": "dimensionless",
        "ds_step_uniform": "m",
        "mass_ratio_uniform": "dimensionless",
        "sigma_surf": "kg m^-2",
        "M_out_cum": "M_Mars",
        "M_sink_cum": "M_Mars",
        "M_loss_cum": "M_Mars",
        "phase_state": "category",
        "phase_method": "category",
        "phase_reason": "category",
        "phase_f_vap": "dimensionless",
        "tau_mars_line_of_sight": "dimensionless",
        "tau_gate_blocked": "bool",
        "blowout_beta_gate": "bool",
        "blowout_phase_allowed": "bool",
        "blowout_layer_mode": "category",
        "blowout_target_phase": "category",
        "sink_selected": "category",
        "hydro_timescale_s": "s",
        "mass_loss_surface_solid_step": "M_Mars",
    }
    definitions = {
        "time": "Cumulative elapsed time at the end of each step [s].",
        "dt": "Step size used for the current advance [s].",
        "T_M_used": "Mars-facing surface temperature applied during the step [K].",
        "rad_flux_Mars": "Instantaneous Mars blackbody flux σ_SB T_M^4 at the current step [W m^-2].",
        "Omega_s": "Keplerian angular frequency evaluated at the run radius [s^-1].",
        "t_orb_s": "Orbital period corresponding to the local Keplerian frequency [s].",
        "t_blow_s": "Nominal radiation-induced blow-out clearing timescale (1/Omega) [s].",
        "t_blow": "Alias of t_blow_s retained for backward compatibility [s].",
        "t_coll": "Wyatt/Strubbe–Chiang collisional time-scale 1/(Omega τ) used in the surface layer when collisions are active [s].",
        "t_solid_s": "Characteristic solid survival time used by the blow-out gate; derived from ds/dt or τ-dependent t_coll [s].",
        "t_sink_total_s": "Combined sink timescale returned by total_sink_timescale (shortest active component) [s].",
        "t_sink_surface_s": "Sink timescale actually applied to the surface ODE after removing duplicative sublimation terms [s].",
        "t_sink_sublimation_s": "Sublimation-specific sink timescale component [s] when active.",
        "t_sink_gas_drag_s": "Gas-drag sink timescale component [s] when active.",
        "r_m": "Representative orbital radius adopted for the zero-dimensional column [m].",
        "r_RM": "Orbital radius expressed in Mars radii (dimensionless multiple of R_Mars).",
        "r_m_used": "Alias of r_m stored for diagnostics downstream [m].",
        "r_RM_used": "Alias of r_RM stored for diagnostics downstream.",
        "a_blow_at_smin": "Blow-out radius evaluated at the effective minimum grain size [m].",
        "Q_pr_used": "Planck-averaged ⟨Q_pr⟩ evaluated at the effective minimum size (dimensionless).",
        "Q_pr_blow": "⟨Q_pr⟩ value used when evaluating the blow-out radius (dimensionless).",
        "Q_pr_at_smin": "⟨Q_pr⟩ corresponding to the active minimum grain size.",
        "beta_at_smin": "β ratio evaluated at the active minimum grain size.",
        "beta_eff": "Alias for β evaluated at the effective minimum size; mirrors beta_at_smin_effective.",
        "dt_over_t_blow": "Ratio dt/t_blow measuring how well the timestep resolves the blow-out timescale.",
        "ts_ratio": "Diagnostic ratio t_blow/t_coll comparing radiation clearing and collisional erosion time-scales (dimensionless).",
        "a_blow_step": "Instantaneous blow-out grain size evaluated for the current step [m].",
        "prod_subblow_area_rate": "Mixed sub-blow-out production rate per unit area.",
        "M_out_dot": "Radiation-driven mass outflow rate expressed in Mars masses per second.",
        "M_sink_dot": "Additional sink-driven mass loss rate expressed in Mars masses per second.",
        "dM_dt_surface_total": "Total surface-layer mass-loss rate (radiation plus sinks) in Mars masses per second.",
        "mloss_blowout_rate": "Instantaneous blow-out mass-loss rate recorded for Phase7 diagnostics (Mars masses per second).",
        "mloss_sink_rate": "Instantaneous sink-driven mass-loss rate (sublimation, gas drag, hydrodynamic escape) for Phase7 diagnostics [M_Mars s^-1].",
        "mloss_total_rate": "Sum of blow-out and sink loss rates recorded for Phase7 diagnostics (Mars masses per second).",
        "M_out_dot_avg": "Average blow-out mass-loss rate over the step in Mars masses per second.",
        "M_sink_dot_avg": "Average sink mass-loss rate over the step in Mars masses per second.",
        "dM_dt_surface_total_avg": "Average total mass-loss rate (blow-out plus sinks) over the step in Mars masses per second.",
        "fast_blowout_factor_avg": "Time-averaged blow-out correction factor applied within the step (dimensionless).",
        "dSigma_dt_blowout": "Surface mass-loss rate per unit area contributed by blow-out (kg m^-2 s^-1).",
        "dSigma_dt_sinks": "Surface mass-loss rate per unit area contributed by additional sinks (kg m^-2 s^-1).",
        "dSigma_dt_total": "Total surface mass-loss rate per unit area (blow-out plus sinks) in kg m^-2 s^-1.",
        "dSigma_dt_sublimation": "Per-area sublimation depletion rate inferred from the ds/dt erosion (kg m^-2 s^-1).",
        "n_substeps": "Number of sub-steps used to resolve the current interval (1 when substepping is inactive).",
        "chi_blow_eff": "Effective blow-out timescale multiplier used for the step (t_blow = chi_blow_eff / Omega).",
        "mass_lost_by_blowout": "Cumulative mass lost through blow-out removal (Mars masses).",
        "mass_lost_by_sinks": "Cumulative mass lost through additional sinks such as sublimation (Mars masses).",
        "mass_lost_sinks_step": "Total mass removed by non-blow-out sinks during the step (Mars masses).",
        "mass_lost_sublimation_step": "Portion of the step sink mass attributed to sublimation erosion (Mars masses).",
        "mass_lost_hydro_step": "Portion of the sink loss attributed to hydrodynamic escape during the step (Mars masses).",
        "mass_lost_surface_solid_marsRP_step": "Mass removed from the Σ_{τ≤1} solid surface layer by Mars radiation pressure during the step (Mars masses).",
        "M_loss_rp_mars": "Cumulative blow-out loss traced solely to Mars radiation pressure (Mars masses).",
        "M_loss_surface_solid_marsRP": "Cumulative Mars radiation-pressure loss from the Σ_{τ≤1} solid surface reservoir (Mars masses).",
        "M_loss_hydro": "Cumulative hydrodynamic escape loss (Mars masses).",
        "M_hydro_cum": "Alias for the integrated hydrodynamic escape loss (Mars masses).",
        "cum_mloss_blowout": "Cumulative blow-out loss mirrored for Phase7 diagnostics (Mars masses).",
        "cum_mloss_sink": "Cumulative sink-driven loss mirrored for Phase7 diagnostics (Mars masses).",
        "cum_mloss_total": "Cumulative total mass loss (blow-out plus sinks) mirrored for Phase7 diagnostics (Mars masses).",
        "fast_blowout_ratio": "Legacy alias for dt_over_t_blow maintained for compatibility (rows with case_status!='blowout' store 0.0).",
        "fast_blowout_factor": "Effective loss fraction f_fast = 1 - exp(-dt/t_blow); applied when io.correct_fast_blowout is true and dt/t_blow > threshold (rows with case_status!='blowout' store 0.0).",
        "fast_blowout_corrected": "Boolean flag noting whether the fast blow-out correction factor was applied on this step.",
        "fast_blowout_flag_gt3": "Diagnostic flag marking dt/t_blow greater than 3.",
        "fast_blowout_flag_gt10": "Diagnostic flag marking dt/t_blow greater than 10.",
        "s_min_evolved": "Minimum size returned by the optional evolution hook (m).",
        "bin_index": "Zero-based bin index for PSD histogram outputs.",
        "s_bin_center": "Logarithmic bin center used in the PSD histogram (m).",
        "N_bin": "Number surface density (arbitrary normalisation) recorded per PSD bin.",
        "ds_dt_sublimation": "Uniform size-change rate applied to each bin from the HKL sublimation model (m s^-1).",
        "blowout_gate_factor": "Gate coefficient f_gate=t_solid/(t_solid+t_blow) applied to blow-out outflux (dimensionless).",
        "F_abs_geom": "Unattenuated geometric absorbed flux σ T_M^4 (R_M/r)^2 [W m^-2].",
        "F_abs_geom_qpr": "Absorbed flux scaled by ⟨Q_pr⟩ for the effective minimum size [W m^-2].",
        "F_abs": "Absorbed flux including ⟨Q_pr⟩ scaling [W m^-2]; alias of F_abs_geom_qpr.",
        "sigma_tau1": "Optical depth unity cap applied to the surface density (kg m^-2).",
        "Sigma_tau1": "Same as sigma_tau1 but emitted with the capitalised naming convention used in the main series output.",
        "Sigma_tau1_active": "Σ_{τ=1} actually enforced for the blow-out layer on the step (kg m^-2).",
        "sigma_tau1_active": "Alias for Sigma_tau1_active saved in the diagnostics table (kg m^-2).",
        "tau_vertical": "Instantaneous vertical optical depth τ used for shielding diagnostics.",
        "kappa_eff": "Effective opacity after shielding adjustments [m^2 kg^-1].",
        "kappa_surf": "Surface opacity direct from the PSD prior to shielding corrections [m^2 kg^-1].",
        "kappa_Planck": "Planck-mean opacity derived from the PSD prior to shielding corrections [m^2 kg^-1].",
        "tau_eff": "Effective τ = κ_eff Σ_surf used for shielding diagnostics (dimensionless).",
        "phi_effective": "Effective shielding multiplier Φ such that κ_eff = Φ κ_surf (dimensionless).",
        "psi_shield": "Alias of Φ used in shielding diagnostics (dimensionless).",
        "area_m2": "Geometric area associated with the surface column [m^2].",
        "prod_subblow_area_rate": "Sub-blow-out production rate evaluated during the last sub-step (kg m^-2 s^-1).",
        "s_min_effective": "Effective PSD minimum size applied during the step (m).",
        "s_min": "Minimum size recorded in diagnostics for convenience (m).",
        "s_peak": "Grain size at which the PSD mass distribution peaks (m).",
        "qpr_mean": "Planck-averaged ⟨Q_pr⟩ evaluated at the effective minimum size (dimensionless).",
        "chi_blow_eff": "Effective blow-out scaling factor χ used for t_blow (dimensionless).",
        "ds_step_uniform": "Uniform PSD shift ds applied over the size grid during the sublimation drift (m).",
        "mass_ratio_uniform": "Mass ratio retained after applying the uniform size drift (dimensionless).",
        "sigma_surf": "Surface density used for diagnostics after optional freezing (kg m^-2).",
        "M_out_cum": "Cumulative mass lost to blow-out in Mars masses.",
        "M_sink_cum": "Cumulative mass lost to sinks in Mars masses.",
        "M_loss_cum": "Total cumulative mass lost (blow-out plus sinks) in Mars masses.",
        "phase_state": "Phase branch applied to the step ('solid' or 'vapor').",
        "phase_method": "Phase inference mode used on the step (map/threshold/disabled).",
        "phase_reason": "Short note describing why a particular branch was selected (e.g. tau gating).",
        "phase_f_vap": "Estimated vapour fraction returned by the phase evaluator (dimensionless).",
        "tau_mars_line_of_sight": "Optical depth along the Mars line of sight used for gating (dimensionless).",
        "tau_gate_blocked": "Indicates that the optical-depth gate suppressed radiation-pressure blow-out on the step.",
        "blowout_beta_gate": "Boolean showing whether β ≥ 0.5 at the active minimum size (True when blow-out is energetically allowed).",
        "blowout_phase_allowed": "Boolean that records whether the configured blow-out layer allows the current phase branch (e.g. solid-only runs disable blow-out in the vapor branch).",
        "blowout_layer_mode": "Selected blow-out layer identifier (e.g. Σ_{τ≤1}).",
        "blowout_target_phase": "Configured phase targeting mode for the blow-out sink (currently 'solid_only').",
        "sink_selected": "Sink branch chosen for the step (rp_blowout, hydro_escape or none).",
        "hydro_timescale_s": "Hydrodynamic escape timescale applied when the vapor branch is active [s].",
        "mass_loss_surface_solid_step": "Step-level mass removed from the Σ_{τ≤1} surface reservoir regardless of whether it is counted as a sink or as radiation loss (Mars masses).",
    }
    table = pa.Table.from_pandas(df, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata.update(
        {
            b"units": json.dumps(units, sort_keys=True).encode("utf-8"),
            b"definitions": json.dumps(definitions, sort_keys=True).encode("utf-8"),
        }
    )
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, path)


def write_summary(summary: Mapping[str, Any], path: Path) -> None:
    """Write a summary dictionary to ``summary.json``.

    The JSON file is formatted with a small indentation for human
    readability.
    """
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)


def write_run_config(config: Mapping[str, Any], path: Path) -> None:
    """Persist the deterministic run configuration metadata."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)


def write_mass_budget(records: Iterable[Mapping[str, Any]], path: Path) -> None:
    """Write mass conservation diagnostics to a CSV file."""
    _ensure_parent(path)
    df = pd.DataFrame(list(records))
    df.to_csv(path, index=False)


def write_orbit_rollup(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    """Serialise orbit-by-orbit loss diagnostics."""

    rows = list(rows)
    if not rows:
        return
    df = pd.DataFrame(rows)
    _ensure_parent(path)
    df.to_csv(path, index=False)


def write_step_diagnostics(
    rows: Iterable[Mapping[str, Any]],
    path: Path,
    *,
    fmt: Literal["csv", "jsonl"] = "csv",
) -> None:
    """Serialise per-step loss channel diagnostics."""

    rows = list(rows)
    _ensure_parent(path)
    fmt_lower = str(fmt).lower()
    if fmt_lower == "csv":
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
    elif fmt_lower == "jsonl":
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True))
                fh.write("\n")
    else:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported step diagnostics format: {fmt}")
