import copy
import json
import math
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, run, schema
from marsdisk.physics import surface
from marsdisk.physics.surface import SURFACE_ODE_DEPRECATION_MSG


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_collision_solver_smol_mass_budget(tmp_path: Path) -> None:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=1800.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=12),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-9, dt_init=1.0, eval_per_step=False),
        io=schema.IO(outdir=tmp_path),
        blowout=schema.Blowout(enabled=True),
    )
    cfg.disk = schema.Disk(geometry=schema.DiskGeometry(r_in_RM=1.5, r_out_RM=2.5, r_profile="uniform", p_index=0.0))
    cfg.inner_disk_mass = schema.InnerDiskMass(use_Mmars_ratio=True, M_in_ratio=1.0e-8)
    cfg.surface.collision_solver = "smol"
    cfg.sinks.mode = "none"
    cfg.physics_mode = "collisions_only"

    run.run_zero_d(cfg)

    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    mass_budget = pd.read_csv(Path(cfg.io.outdir) / "checks" / "mass_budget.csv")

    assert summary["collision_solver"] == "smol"
    assert mass_budget["error_percent"].max() <= 0.5
    assert summary["mass_budget_max_error_percent"] <= 0.5


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
@pytest.mark.filterwarnings("ignore:surface_ode solver is deprecated")
def test_surface_and_smol_series_columns_match(tmp_path: Path) -> None:
    base_cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        material=schema.Material(rho=2500.0),
        radiation=schema.Radiation(TM_K=1700.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=10),
        initial=schema.Initial(mass_total=5.0e-10, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-8, dt_init=1.0),
        supply=schema.Supply(const=schema.SupplyConst(prod_area_rate_kg_m2_s=1e-7)),
        io=schema.IO(outdir=tmp_path / "base"),
    )
    base_cfg.disk = schema.Disk(geometry=schema.DiskGeometry(r_in_RM=1.5, r_out_RM=2.5, r_profile="uniform", p_index=0.0))
    base_cfg.inner_disk_mass = schema.InnerDiskMass(use_Mmars_ratio=True, M_in_ratio=1.0e-8)
    base_cfg.sinks.mode = "none"
    base_cfg.physics_mode = "collisions_only"

    cfg_surface = copy.deepcopy(base_cfg)
    cfg_surface.io = schema.IO(outdir=tmp_path / "surface")
    cfg_surface.surface.collision_solver = "surface_ode"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=SURFACE_ODE_DEPRECATION_MSG, category=DeprecationWarning)
        run.run_zero_d(cfg_surface)

    cfg_smol = copy.deepcopy(base_cfg)
    cfg_smol.io = schema.IO(outdir=tmp_path / "smol")
    cfg_smol.surface.collision_solver = "smol"
    run.run_zero_d(cfg_smol)

    df_surface = pd.read_parquet(Path(cfg_surface.io.outdir) / "series" / "run.parquet")
    df_smol = pd.read_parquet(Path(cfg_smol.io.outdir) / "series" / "run.parquet")

    assert set(df_surface.columns) == set(df_smol.columns)
    key_cols = ["prod_subblow_area_rate", "M_out_dot", "mass_lost_by_blowout", "M_sink_dot"]
    for col in key_cols:
        assert df_surface[col].notna().all()
        assert df_smol[col].notna().all()
        assert np.isfinite(df_surface[col]).all()
        assert np.isfinite(df_smol[col]).all()

    summary = json.loads((Path(cfg_smol.io.outdir) / "summary.json").read_text())
    mass_budget = pd.read_csv(Path(cfg_smol.io.outdir) / "checks" / "mass_budget.csv")
    csv_max = float(mass_budget["error_percent"].abs().max())
    assert math.isclose(summary["mass_budget_max_error_percent"], csv_max, rel_tol=1e-9, abs_tol=1e-12)


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_surface_ode_emits_deprecation_warning(tmp_path: Path) -> None:
    """surface_ode モードが非推奨警告を出すことを検証する。"""

    surface._SURFACE_ODE_WARNED = False  # reset for deterministic warning capture

    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        material=schema.Material(rho=2500.0),
        radiation=schema.Radiation(TM_K=1700.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-4, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-10, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-9, dt_init=1.0),
        supply=schema.Supply(const=schema.SupplyConst(prod_area_rate_kg_m2_s=1e-7)),
        io=schema.IO(outdir=tmp_path),
    )
    cfg.disk = schema.Disk(geometry=schema.DiskGeometry(r_in_RM=1.5, r_out_RM=2.5, r_profile="uniform", p_index=0.0))
    cfg.inner_disk_mass = schema.InnerDiskMass(use_Mmars_ratio=True, M_in_ratio=1.0e-8)
    cfg.surface.collision_solver = "surface_ode"
    cfg.sinks.mode = "none"
    cfg.physics_mode = "collisions_only"

    with pytest.warns(DeprecationWarning, match="surface_ode solver is deprecated"):
        run.run_zero_d(cfg)
