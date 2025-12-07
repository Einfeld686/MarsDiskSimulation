"""Regression tests for time grid provenance and mass budget bookkeeping."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import run as run_module, schema


def _tiny_config(outdir: Path, dt_init: float, n_steps: int) -> schema.Config:
    """Return a minimal 0D configuration for rapid implicit-Euler runs."""

    t_end_s = dt_init * n_steps
    geometry = schema.Geometry(mode="0D")
    material = schema.Material(rho=3000.0)
    disk = schema.Disk(
        geometry=schema.DiskGeometry(
            r_in_RM=4.13,
            r_out_RM=4.13,
            r_profile="uniform",
            p_index=0.0,
        )
    )
    radiation = schema.Radiation(TM_K=2000.0)
    sizes = schema.Sizes(s_min=1.0e-6, s_max=1.0e-2, n_bins=32)
    initial = schema.Initial(mass_total=1.0e-8, s0_mode="upper")
    dynamics = schema.Dynamics(
        e0=0.01,
        i0=0.01,
        t_damp_orbits=100.0,
        f_wake=1.0,
        e_mode="fixed",
        i_mode="fixed",
    )
    psd = schema.PSD(alpha=3.5, wavy_strength=0.0)
    qstar = schema.QStar(Qs=1e3, a_s=1.0, B=1.0, b_g=1.0, v_ref_kms=[1.0])
    numerics = schema.Numerics(
        t_end_years=t_end_s / run_module.SECONDS_PER_YEAR,
        dt_init=dt_init,
    )
    io = schema.IO(outdir=outdir)
    sinks = schema.Sinks(mode="none", enable_sublimation=False)

    return schema.Config(
        geometry=geometry,
        disk=disk,
        material=material,
        radiation=radiation,
        sizes=sizes,
        initial=initial,
        dynamics=dynamics,
        psd=psd,
        qstar=qstar,
        numerics=numerics,
        io=io,
        sinks=sinks,
    )


def test_time_grid_and_mass_budget(tmp_path):
    outdir = tmp_path / "tiny_run"
    dt_init = 600.0
    n_steps = 4
    cfg = _tiny_config(outdir, dt_init, n_steps)

    run_module.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    series = pd.read_parquet(series_path)
    diffs = np.diff(series["time"].to_numpy())
    assert np.allclose(diffs, dt_init, atol=1e-9)

    t_end_s = dt_init * n_steps
    expected_len = math.ceil(t_end_s / dt_init)
    assert len(series) == expected_len
    assert len(series) <= run_module.MAX_STEPS

    checks_path = outdir / "checks" / "mass_budget.csv"
    checks = pd.read_csv(checks_path)
    assert np.all(checks["error_percent"].to_numpy() <= 0.5)

    run_config_path = outdir / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    time_grid = run_config.get("time_grid", {})
    assert time_grid.get("scheme") == "fixed-step implicit-Euler (S1)"
