"""Ensure per-cell mass budget output can be disabled."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from one_d_helpers import run_one_d_case


def test_mass_budget_cells_disabled(tmp_path: Path) -> None:
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
        "io.mass_budget_cells=false",
    ]
    _, _, outdir = run_one_d_case(tmp_path, overrides)

    mass_budget_path = outdir / "checks" / "mass_budget.csv"
    assert mass_budget_path.exists()
    mass_budget = pd.read_csv(mass_budget_path)
    assert not mass_budget.empty

    assert not (outdir / "checks" / "mass_budget_cells.csv").exists()
