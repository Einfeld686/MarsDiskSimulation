from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pandas as pd
import pytest

from tools import evaluation_system


def _build_series_frame() -> pd.DataFrame:
    data = {
        "time": [0.0, 1.0],
        "dt": [1.0, 1.0],
        "T_M_used": [2500.0, 2490.0],
        "rad_flux_Mars": [1.0, 1.0],
        "tau": [0.01, 0.01],
        "tau_los_mars": [0.01, 0.01],
        "a_blow": [1e-6, 1e-6],
        "a_blow_at_smin": [1e-6, 1.0e-6],
        "s_min": [1e-6, 1.1e-6],
        "kappa": [0.1, 0.1],
        "Qpr_mean": [0.9, 0.9],
        "Q_pr_at_smin": [0.9, 0.9],
        "beta_at_smin_config": [0.4, 0.4],
        "beta_at_smin_effective": [0.4, 0.4],
        "beta_at_smin": [0.4, 0.4],
        "Sigma_surf": [1.0, 0.9],
        "Sigma_tau1": [1.0, 0.9],
        "outflux_surface": [0.0, 0.0],
        "t_blow": [10.0, 10.0],
        "prod_subblow_area_rate": [0.0, 0.0],
        "M_out_dot": [0.0, 0.0],
        "M_loss_cum": [0.0, 0.0],
        "mass_total_bins": [1e-5, 1e-5],
        "mass_lost_by_blowout": [0.0, 0.0],
        "mass_lost_by_sinks": [0.0, 0.0],
        "dt_over_t_blow": [0.1, 0.1],
        "fast_blowout_factor": [0.0, 0.0],
        "fast_blowout_flag_gt3": [False, False],
        "fast_blowout_flag_gt10": [False, False],
        "fast_blowout_corrected": [False, False],
        "a_blow_step": [1e-6, 1e-6],
        "dSigma_dt_sublimation": [0.0, 0.0],
        "mass_lost_sinks_step": [0.0, 0.0],
        "mass_lost_sublimation_step": [0.0, 0.0],
        "ds_dt_sublimation": [0.0, 0.0],
    }
    return pd.DataFrame(data)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prepare_outdir(tmp_path: Path, *, drop_series_columns: Sequence[str] | None = None) -> Path:
    outdir = tmp_path / "out"
    (outdir / "series").mkdir(parents=True)
    (outdir / "checks").mkdir(parents=True)

    df = _build_series_frame()
    if drop_series_columns:
        df = df.drop(columns=list(drop_series_columns))
    df.to_parquet(outdir / "series" / "run.parquet")

    summary = {
        "case_status": "ok",
        "beta_at_smin_config": 0.4,
        "beta_at_smin_effective": 0.4,
        "beta_threshold": 0.5,
        "M_out_cum": 0.0,
        "M_sink_cum": 0.0,
        "M_out_mean_per_orbit": 0.0,
        "M_sink_mean_per_orbit": 0.0,
        "M_loss": 0.0,
        "M_loss_from_sinks": 0.0,
        "M_loss_from_sublimation": 0.0,
        "orbits_completed": 10,
        "chi_blow_eff": 1.0,
        "s_min_components": {"config": 1e-6, "blowout": 2e-6, "effective": 2e-6},
        "s_min_effective": 2e-6,
        "time_grid": {"n_steps": 2},
        "mass_budget_max_error_percent": 0.0,
        "qpr_table_path": "data/qpr.csv",
        "rho_used": 3000.0,
        "T_M_used": 2500.0,
        "T_M_source": "radiation.TM_K",
        "T_M_initial": 2500.0,
        "T_M_final": 2490.0,
        "T_M_min": 2490.0,
        "T_M_median": 2495.0,
        "T_M_max": 2500.0,
        "beta_at_smin_min": 0.4,
        "beta_at_smin_median": 0.4,
        "beta_at_smin_max": 0.4,
        "a_blow_min": 1e-6,
        "a_blow_median": 1e-6,
        "a_blow_max": 1e-6,
        "temperature_driver": {"source": "radiation.TM_K", "mode": "constant", "enabled": False},
        "solar_radiation": {"enabled": False},
    }
    _write_json(outdir / "summary.json", summary)

    mass_budget = pd.DataFrame(
        {
            "time": [1.0, 2.0],
            "mass_initial": [1e-5, 1e-5],
            "mass_remaining": [0.999e-5, 0.998e-5],
            "mass_lost": [1e-8, 2e-8],
            "mass_diff": [0.0, 0.0],
            "error_percent": [0.1, 0.2],
            "tolerance_percent": [0.5, 0.5],
        }
    )
    mass_budget.to_csv(outdir / "checks" / "mass_budget.csv", index=False)

    orbit_rollup = pd.DataFrame(
        {
            "time_s_end": [100.0, 200.0],
            "M_out_orbit": [0.0, 0.0],
            "M_sink_orbit": [0.0, 0.0],
            "M_loss_per_orbit": [0.0, 0.0],
        }
    )
    orbit_rollup.to_csv(outdir / "orbit_rollup.csv", index=False)

    run_config = {
        "sublimation_provenance": {
            "psat_model": "clausius",
            "alpha_evap": 1.0,
            "mu": 1.0,
            "P_gas": 0.0,
        },
        "beta_formula": "test",
        "T_M_used": 2500.0,
        "rho_used": 3000.0,
        "Q_pr_used": 0.9,
        "temperature_driver": {"source": "radiation.TM_K", "mode": "constant", "enabled": False},
        "solar_radiation": {"enabled": False},
    }
    _write_json(outdir / "run_config.json", run_config)
    return outdir


def test_evaluation_system_with_complete_outputs(tmp_path: Path) -> None:
    outdir = _prepare_outdir(tmp_path)
    system = evaluation_system.EvaluationSystem(outdir)

    results = system.run()

    assert all(result.passed for result in results)


def test_evaluation_system_detects_missing_series_columns(tmp_path: Path) -> None:
    outdir = _prepare_outdir(tmp_path, drop_series_columns=["mass_lost_by_sinks"])
    system = evaluation_system.EvaluationSystem(outdir)

    results = system.run()
    lookup = {result.name: result for result in results}

    assert not lookup["series_columns"].passed
    assert "mass_lost_by_sinks" in lookup["series_columns"].details
