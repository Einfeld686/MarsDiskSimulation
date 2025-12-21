"""1D timestep floor checks using the per-step collision-kernel minimum."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from one_d_helpers import run_one_d_case


def test_dt_floor_uses_kernel_min(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=1",
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "numerics.dt_min_tcoll_ratio=0.5",
        "phase.enabled=false",
    ]
    summary, run_df, _ = run_one_d_case(tmp_path, overrides)

    assert "t_coll_kernel_min" in run_df.columns

    dt_nominal = float(summary["time_grid"]["dt_nominal_s"])
    dt_ratio = float(summary["time_grid"]["dt_min_tcoll_ratio"])

    step_info = (
        run_df.groupby("time", as_index=False)[["dt", "t_coll_kernel_min"]]
        .first()
        .sort_values("time")
        .reset_index(drop=True)
    )
    assert np.isfinite(step_info["t_coll_kernel_min"].to_numpy()).any()

    prev_tcoll = step_info["t_coll_kernel_min"].shift(1).to_numpy()
    dt_values = step_info["dt"].to_numpy()
    mask = np.isfinite(prev_tcoll) & (dt_values >= dt_nominal * 0.999)
    expected_floor = np.maximum(dt_nominal, dt_ratio * prev_tcoll)

    assert np.all(dt_values[mask] + 1e-12 >= expected_floor[mask])
