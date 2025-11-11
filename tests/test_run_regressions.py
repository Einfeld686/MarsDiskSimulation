"""Regression tests for 0D run diagnostics and overrides."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from marsdisk.run import load_config, run_zero_d

BASE_CONFIG = Path("configs/base.yml")


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
    assert qpr_path.endswith("data/qpr_table.csv")

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
        "temps.T_M=2500.0",
        "io.debug_sinks=false",
    ]
    summary, diagnostics = _run_case(overrides)

    assert summary["M_sink_cum"] > 0.0
    diff = abs(summary["M_sink_cum"] - summary["M_loss_from_sublimation"])
    assert diff <= 1e-10

    if not diagnostics.empty:
        delta = diagnostics["mass_loss_sinks_step"] - diagnostics["mass_loss_sublimation_step"]
        assert np.nanmax(np.abs(delta.values)) <= 1e-12
