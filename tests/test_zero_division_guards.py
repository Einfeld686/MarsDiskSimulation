from pathlib import Path
import math

import pandas as pd
import pytest

from marsdisk.physics import supply
from marsdisk import run, schema


def test_run_zero_d_tau_zero_no_error(tmp_path: Path):
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.5,
                r_out_RM=2.5,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=4),
        initial=schema.Initial(mass_total=1.0e-12, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=1e-4, i0=1e-4, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-10, dt_init=1.0),
        io=schema.IO(outdir=tmp_path),
    )
    cfg.surface.collision_solver = "smol"
    cfg.sinks.mode = "none"
    cfg.shielding = schema.Shielding(mode="off")
    run.run_zero_d(cfg)
    df = pd.read_parquet(tmp_path / "series" / "run.parquet")
    assert math.isfinite(df["Sigma_surf"].iloc[-1])


def test_supply_powerlaw_t0_zero():
    cfg = schema.Supply(
        mode="powerlaw",
        powerlaw=schema.SupplyPowerLaw(A_kg_m2_s=1.0, t0_s=0.0, index=0.0),
    )
    rate = supply.get_prod_area_rate(10.0, 1.0, cfg)
    assert rate == pytest.approx(0.05)


def test_run_zero_d_no_zerodivision(monkeypatch, tmp_path):
    cfg = run.load_config(Path("configs/base.yml"))
    monkeypatch.setattr(run, "MAX_STEPS", 1)
    monkeypatch.setattr(cfg.io, "outdir", tmp_path)
    cfg.surface.collision_solver = "smol"
    cfg.sinks.mode = "none"
    cfg.shielding = schema.Shielding(mode="off")
    run.run_zero_d(cfg)
