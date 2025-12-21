"""1D (Nr=1) vs 0D consistency checks."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from one_d_helpers import run_one_d_case, run_zero_d_case


def _interpolate(values: np.ndarray, x: np.ndarray, x_new: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return np.full_like(x_new, np.nan, dtype=float)
    return np.interp(x_new, x, values)


def test_run_one_d_matches_zero_d(tmp_path: Path) -> None:
    common_overrides = [
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.streaming.enable=false",
    ]

    _, one_d_df, _ = run_one_d_case(
        tmp_path / "one_d",
        ["geometry.mode=1D", "geometry.Nr=1"] + common_overrides,
    )
    _, zero_d_df, _ = run_zero_d_case(tmp_path / "zero_d", common_overrides)

    one_d = one_d_df.sort_values("time")
    zero_d = zero_d_df.sort_values("time")

    times_one = one_d["time"].to_numpy()
    times_zero = zero_d["time"].to_numpy()

    sigma_zero = zero_d["Sigma_surf"].to_numpy()
    mout_zero = zero_d["M_out_dot"].to_numpy()

    if np.array_equal(times_one, times_zero):
        sigma_ref = sigma_zero
        mout_ref = mout_zero
    else:
        sigma_ref = _interpolate(sigma_zero, times_zero, times_one)
        mout_ref = _interpolate(mout_zero, times_zero, times_one)

    sigma_one = one_d["Sigma_surf"].to_numpy()
    mout_one = one_d["M_out_dot"].to_numpy()

    denom_sigma = np.maximum(np.abs(sigma_ref), 1e-12)
    denom_mout = np.maximum(np.abs(mout_ref), 1e-12)
    sigma_rel = np.max(np.abs(sigma_one - sigma_ref) / denom_sigma)
    mout_rel = np.max(np.abs(mout_one - mout_ref) / denom_mout)

    assert sigma_rel <= 0.05
    assert mout_rel <= 0.05
