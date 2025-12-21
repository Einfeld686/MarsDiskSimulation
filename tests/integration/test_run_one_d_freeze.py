"""Freeze behavior for tau_stop in 1D runs."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from one_d_helpers import run_one_d_case


def test_run_one_d_tau_stop_freeze(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "optical_depth.tau_stop=0.99",
        "optical_depth.tau_stop_tol=0.0",
        "supply.const.mu_orbit10pct=10.0",
        "io.streaming.enable=false",
    ]
    _, run_df, _ = run_one_d_case(tmp_path, overrides)

    stopped = run_df[run_df["cell_stop_time"].notna()]
    assert not stopped.empty

    for cell_index in stopped["cell_index"].unique():
        stop_time = float(
            stopped.loc[stopped["cell_index"] == cell_index, "cell_stop_time"].iloc[0]
        )
        post = run_df[(run_df["cell_index"] == cell_index) & (run_df["time"] >= stop_time)]
        assert not post.empty
        sigma_vals = post["Sigma_surf"].to_numpy()
        prod_vals = post["prod_subblow_area_rate"].to_numpy()
        assert np.allclose(sigma_vals, sigma_vals[0], rtol=0.0, atol=1e-12)
        assert np.allclose(prod_vals, prod_vals[0], rtol=0.0, atol=1e-12)
