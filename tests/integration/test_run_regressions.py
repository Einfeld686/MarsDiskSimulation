"""Regression tests for 0D run diagnostics and overrides."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from ruamel.yaml import YAML
from marsdisk.run import load_config, run_zero_d

BASE_CONFIG = Path("configs/innerdisk_base.yml")
TOL_MLOSS_PERCENT = 0.5


def _run_case(overrides: list[str]) -> tuple[dict, pd.DataFrame]:
    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.debug_sinks = False
    with TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        cfg.io.outdir = outdir
        run_zero_d(cfg)
        with (outdir / "summary.json").open("r", encoding="utf-8") as fh:
            summary = json.load(fh)
        diag_path = outdir / "series" / "diagnostics.parquet"
        diag = pd.read_parquet(diag_path) if diag_path.exists() else pd.DataFrame()
    return summary, diag


def _run_case_with_series(overrides: list[str]) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.debug_sinks = False
    with TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        cfg.io.outdir = outdir
        run_zero_d(cfg)
        with (outdir / "summary.json").open("r", encoding="utf-8") as fh:
            summary = json.load(fh)
        run_df = pd.read_parquet(outdir / "series" / "run.parquet")
        rollup_path = outdir / "orbit_rollup.csv"
        rollup = pd.read_csv(rollup_path) if rollup_path.exists() else pd.DataFrame()
    return summary, run_df, rollup


def test_mass_budget_and_timestep_overrides() -> None:
    overrides = [
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "io.debug_sinks=false",
    ]
    summary, diagnostics = _run_case(overrides)

    assert summary["mass_budget_max_error_percent"] <= 0.5
    assert summary["dt_over_t_blow_median"] <= 0.1

    qpr_path = Path(summary["qpr_table_path"]).as_posix()
    assert Path(qpr_path).name in {
        "qpr_table.csv",
        "qpr_planck_sio2_abbas_calibrated_lowT.csv",
    }

    required_cols = {
        "sigma_surf",
        "kappa_Planck",
        "tau_eff",
        "psi_shield",
        "s_peak",
        "M_out_cum",
        "M_sink_cum",
        "M_loss_cum",
    }
    assert required_cols.issubset(set(diagnostics.columns))


def test_sublimation_not_double_counted() -> None:
    overrides = [
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=10.0",
        "sinks.enable_sublimation=true",
        "sinks.mode=sublimation",
        "radiation.TM_K=2500.0",
        "io.debug_sinks=false",
        "physics_mode=sublimation_only",
    ]
    summary, diagnostics = _run_case(overrides)

    # sinks may be negligible at very short runtime; ensure we at least do not double count
    assert summary["M_sink_cum"] >= 0.0
    diff = abs(summary["M_sink_cum"] - summary["M_loss_from_sublimation"])
    assert diff <= 1e-10

    if not diagnostics.empty:
        delta = diagnostics["mass_loss_sinks_step"] - diagnostics["mass_loss_sublimation_step"]
        assert np.nanmax(np.abs(delta.values)) <= 1e-12


def test_extended_diagnostics_toggle() -> None:
    common_overrides = [
        "numerics.t_end_orbits=1.0",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "io.debug_sinks=false",
    ]

    summary_off, run_off, rollup_off = _run_case_with_series(
        common_overrides + ["diagnostics.extended_diagnostics.enable=false"]
    )
    assert "max_mloss_rate" not in summary_off
    assert "median_gate_factor" not in summary_off
    assert "tau_gate_blocked_time_fraction" not in summary_off
    assert "mloss_total_rate" not in set(run_off.columns)
    assert rollup_off.empty or "mloss_total_rate_mean" not in set(rollup_off.columns)

    summary_on, run_on, rollup_on = _run_case_with_series(
        common_overrides + ["diagnostics.extended_diagnostics.enable=true"]
    )
    required_cols = {
        "mloss_blowout_rate",
        "mloss_sink_rate",
        "mloss_total_rate",
        "cum_mloss_total",
        "t_coll",
        "ts_ratio",
        "beta_eff",
        "kappa_eff",
        "tau_eff",
    }
    assert required_cols.issubset(set(run_on.columns))
    assert "max_mloss_rate" in summary_on
    assert summary_on.get("extended_diagnostics_version") == "extended-minimal-v1"
    assert "median_gate_factor" in summary_on
    assert "tau_gate_blocked_time_fraction" in summary_on
    assert summary_on["median_gate_factor"] <= 1.0
    if not rollup_on.empty:
        assert {
            "mloss_total_rate_mean",
            "mloss_total_rate_peak",
            "ts_ratio_median",
            "gate_factor_median",
        }.issubset(set(rollup_on.columns))


def test_tau_gate_blocks_blowout() -> None:
    overrides = [
        "diagnostics.extended_diagnostics.enable=true",
        "radiation.tau_gate.enable=true",
        "radiation.tau_gate.tau_max=1e-6",
        "initial.mass_total=1e-3",
        "material.rho=1500.0",
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=20.0",
    ]
    summary, run_df, _ = _run_case_with_series(overrides)

    assert summary["tau_gate_blocked_time_fraction"] > 0.5
    assert run_df["outflux_surface"].abs().max() == 0.0
    assert run_df["mloss_blowout_rate"].abs().max() == 0.0


def test_gate_factor_collision_competition_reduces_flux() -> None:
    overrides = [
        "diagnostics.extended_diagnostics.enable=true",
        "blowout.gate_mode=collision_competition",
        "initial.mass_total=1e-1",
        "material.rho=1200.0",
        "radiation.TM_K=4000.0",
        "numerics.t_end_orbits=0.1",
        "numerics.t_end_years=null",
        "numerics.dt_init=20.0",
    ]
    summary, run_df, _ = _run_case_with_series(overrides)

    assert summary["median_gate_factor"] < 1.0
    assert run_df["blowout_gate_factor"].median() < 1.0


def _write_inline_combined_config(config_path: Path, outdir: Path) -> None:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    r_rm = 1.3
    config = {
        "geometry": {"mode": "0D"},
        "disk": {
            "geometry": {
                "r_in_RM": r_rm,
                "r_out_RM": r_rm,
                "r_profile": "uniform",
                "p_index": 0.0,
            }
        },
        "material": {"rho": 3000.0},
        "radiation": {"TM_K": 4000.0},
        "sizes": {"s_min": 1.0e-7, "s_max": 1.0e-3, "n_bins": 24},
        "initial": {"mass_total": 1.0e-8, "s0_mode": "upper"},
        "dynamics": {
            "e0": 0.05,
            "i0": 0.01,
            "t_damp_orbits": 5.0,
            "f_wake": 1.0,
            "rng_seed": 9876,
            "e_mode": "fixed",
            "i_mode": "fixed",
        },
        "psd": {"alpha": 1.8, "wavy_strength": 0.05},
        "qstar": {"Qs": 1.0e5, "a_s": 0.1, "B": 0.3, "b_g": 1.36, "v_ref_kms": [1.0, 2.0]},
        "supply": {
            "mode": "const",
            "const": {"prod_area_rate_kg_m2_s": 1.0e-5},
            "mixing": {"epsilon_mix": 1.0},
        },
        "sinks": {
            "mode": "sublimation",
            "enable_sublimation": True,
            "enable_gas_drag": False,
            "T_sub": 1300.0,
            "sub_params": {
                "mode": "hkl",
                "psat_model": "clausius",
                "alpha_evap": 0.02,
                "mu": 0.0440849,
                "A": 13.613,
                "B": 17850.0,
                "eta_instant": 0.2,
                "dT": 50.0,
                "P_gas": 0.0,
            },
        },
        "numerics": {
            "t_end_orbits": 0.25,
            "t_end_years": None,
            "dt_init": 5.0,
            "eval_per_step": False,
            "orbit_rollup": False,
        },
        "io": {"outdir": outdir.as_posix(), "debug_sinks": False},
    }
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh)


def test_combined_mass_flux_balance(tmp_path: Path) -> None:
    outdir = tmp_path / "combined_mass_balance"
    config_path = tmp_path / "combined_config.yml"
    _write_inline_combined_config(config_path, outdir)

    cfg = load_config(config_path)
    run_zero_d(cfg)

    summary_path = outdir / "summary.json"
    series_path = outdir / "series" / "run.parquet"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    series = pd.read_parquet(series_path)

    assert summary["primary_scenario"] == "combined"
    blowout_loss = float(series["mass_lost_by_blowout"].iloc[-1])
    sink_loss = float(series["mass_lost_by_sinks"].iloc[-1])
    total_loss = float(summary["M_loss"])
    assert blowout_loss >= 0.0
    assert sink_loss >= 0.0
    if total_loss > 0.0:
        rel_err_percent = abs(total_loss - (blowout_loss + sink_loss)) / total_loss * 100.0
        assert rel_err_percent <= TOL_MLOSS_PERCENT
    else:
        assert blowout_loss == 0.0
        assert sink_loss == 0.0


def test_gate_factor_sublimation_competition_reduces_flux() -> None:
    overrides = [
        "diagnostics.extended_diagnostics.enable=true",
        "blowout.gate_mode=sublimation_competition",
        "sinks.enable_sublimation=true",
        "sinks.mode=sublimation",
        "sinks.sub_params.mode=hkl",
        "radiation.TM_K=3000.0",
        "material.rho=1200.0",
        "initial.mass_total=1e-3",
        "numerics.t_end_orbits=0.2",
        "numerics.t_end_years=null",
        "numerics.dt_init=20.0",
    ]

    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.debug_sinks = False
    with TemporaryDirectory() as tmp:
        outdir = Path(tmp)
        cfg.io.outdir = outdir
        run_zero_d(cfg)
        with (outdir / "summary.json").open("r", encoding="utf-8") as fh:
            summary = json.load(fh)
        run_df = pd.read_parquet(outdir / "series" / "run.parquet")

    assert summary["median_gate_factor"] < 1.0
    assert run_df["blowout_gate_factor"].median() < 1.0
