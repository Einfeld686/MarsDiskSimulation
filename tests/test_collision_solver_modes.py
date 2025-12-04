import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_collision_solver_smol_mass_budget(tmp_path: Path) -> None:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.2 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=1800.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=12),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-9, dt_init=1.0, eval_per_step=False),
        io=schema.IO(outdir=tmp_path),
        blowout=schema.Blowout(enabled=True),
        radiation=schema.Radiation(Q_pr=1.0),
    )
    cfg.disk = schema.Disk(geometry=schema.DiskGeometry(r_in_RM=1.5, r_out_RM=2.5, r_profile="uniform", p_index=0.0))
    cfg.inner_disk_mass = schema.InnerDiskMass(use_Mmars_ratio=True, M_in_ratio=1.0e-8)
    cfg.surface.collision_solver = "smol"
    cfg.sinks.mode = "none"
    cfg.process.primary = "collisions_only"

    run.run_zero_d(cfg)

    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    mass_budget = pd.read_csv(Path(cfg.io.outdir) / "checks" / "mass_budget.csv")

    assert summary["collision_solver"] == "smol"
    assert mass_budget["error_percent"].max() <= 0.5
    assert summary["mass_budget_max_error_percent"] <= 0.5
