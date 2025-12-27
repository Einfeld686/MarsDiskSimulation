"""Deep-mixing mass budget consistency checks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import constants, grid
from marsdisk.run import load_config
from one_d_helpers import run_one_d_case

BASE_CONFIG = Path("configs/base.yml")


def test_deep_mixing_mass_budget_with_supply(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "dynamics.e_profile.mode=off",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "supply.enabled=true",
        "supply.mode=const",
        "supply.const.prod_area_rate_kg_m2_s=1e-10",
        "supply.transport.mode=deep_mixing",
        "supply.transport.t_mix_orbits=5.0",
        "io.streaming.enable=false",
    ]
    _, run_df, _ = run_one_d_case(tmp_path, overrides)
    cfg = load_config(BASE_CONFIG, overrides=overrides)

    r_in_m = float(cfg.disk.geometry.r_in_RM) * constants.R_MARS
    r_out_m = float(cfg.disk.geometry.r_out_RM) * constants.R_MARS
    n_cells = int(cfg.geometry.Nr)
    radial_grid = grid.RadialGrid.linear(r_in_m, r_out_m, n_cells)
    area_vals = np.asarray(radial_grid.areas, dtype=float)
    area_map = {idx: area_vals[idx] for idx in range(n_cells)}

    run_df = run_df.sort_values(["time", "cell_index"])
    run_df["cell_area"] = run_df["cell_index"].map(area_map)
    run_df["deep_mass"] = run_df["sigma_deep"].fillna(0.0) * run_df["cell_area"] / constants.M_MARS
    run_df["expected_delta_mass"] = (
        (run_df["prod_subblow_area_rate"].fillna(0.0) - run_df["dSigma_dt_total"].fillna(0.0))
        * run_df["smol_dt_eff"].fillna(0.0)
        + run_df["prod_rate_into_deep"].fillna(0.0) * run_df["dt"].fillna(0.0)
    ) * run_df["cell_area"] / constants.M_MARS

    grouped = (
        run_df.groupby("time", as_index=False)
        .agg(
            mass_surface=("mass_total_bins", "sum"),
            mass_deep=("deep_mass", "sum"),
            total_mass=("mass_total_bins", "sum"),
            deep_mass=("deep_mass", "sum"),
            expected_delta=("expected_delta_mass", "sum"),
        )
        .sort_values("time")
    )
    assert not grouped.empty
    grouped["mass_total"] = grouped["total_mass"] + grouped["deep_mass"]
    grouped["mass_total_prev"] = grouped["mass_total"].shift(1)
    grouped["mass_delta_actual"] = grouped["mass_total"] - grouped["mass_total_prev"]
    grouped = grouped.dropna()

    baseline = float(grouped["mass_total"].iloc[0])
    assert baseline > 0.0
    residual = (grouped["mass_delta_actual"] - grouped["expected_delta"]).abs()
    rel_error = residual / baseline
    assert rel_error.max() <= 5.0e-3
