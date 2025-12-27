from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from marsdisk import run
from tools import evaluation_system


def test_base_config_smol_mass_budget_and_eval(tmp_path: Path) -> None:
    """Run the base.yml in Smol mode and validate mass budget + evaluation system."""

    outdir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    qpr_path = repo_root / "data" / "qpr_table.csv"
    overrides = [
        f"io.outdir={outdir}",
        "numerics.t_end_orbits=1.0",
        "numerics.t_end_years=null",
        "numerics.dt_init=100.0",
        "numerics.dt_over_t_blow_max=null",
        "dynamics.e_profile.mode=off",
    ]

    cfg = run.load_config(repo_root / "configs" / "base.yml", overrides=overrides)
    cfg.surface.collision_solver = "smol"
    cfg.sinks.mode = "none"
    cfg.sinks.enable_sublimation = False
    cfg.radiation.qpr_table_path = qpr_path
    run.run_zero_d(cfg)

    summary = json.loads((outdir / "summary.json").read_text())
    mass_budget = pd.read_csv(outdir / "checks" / "mass_budget.csv")
    max_error = float(mass_budget["error_percent"].abs().max())

    assert summary["collision_solver"] == "smol"
    assert max_error <= run.MASS_BUDGET_TOLERANCE_PERCENT
    assert summary["mass_budget_max_error_percent"] <= run.MASS_BUDGET_TOLERANCE_PERCENT

    system = evaluation_system.EvaluationSystem(outdir)
    results = system.run()
    assert all(result.passed for result in results)
