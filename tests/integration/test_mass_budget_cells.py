"""Per-cell mass budget checks for 1D runs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from one_d_helpers import run_one_d_case


def test_mass_budget_cells_within_tolerance(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.05",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "supply.enabled=false",
        "io.streaming.enable=false",
    ]
    _, _, outdir = run_one_d_case(tmp_path, overrides)

    cells = pd.read_csv(outdir / "checks" / "mass_budget_cells.csv")
    assert not cells.empty
    assert cells["error_percent"].abs().max() <= 0.5

    mass_budget = pd.read_csv(outdir / "checks" / "mass_budget.csv")
    assert not mass_budget.empty

    last_time = cells["time"].max()
    cells_last = cells[cells["time"] == last_time]
    mass_lost_cells = float(cells_last["mass_lost"].sum())

    global_last = mass_budget.loc[mass_budget["time"].idxmax()]
    assert np.isclose(mass_lost_cells, float(global_last["mass_lost"]), rtol=1e-6, atol=1e-12)
