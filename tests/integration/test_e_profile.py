from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, run, schema
from marsdisk.physics import eccentricity


def test_e_profile_mars_pericenter_clamps(caplog: pytest.LogCaptureFixture) -> None:
    profile = schema.DynamicsEccentricityProfile(mode="mars_pericenter")
    r_vals = np.array([0.5 * constants.R_MARS, 2.0 * constants.R_MARS], dtype=float)
    r_rm = r_vals / constants.R_MARS

    caplog.set_level("WARNING")
    e_vals, meta = eccentricity.evaluate_e_profile(profile, r_m=r_vals, r_RM=r_rm, log=eccentricity.logger)

    assert meta["mode"] == "mars_pericenter"
    assert e_vals[0] == pytest.approx(0.0)
    assert e_vals[1] == pytest.approx(0.5)
    assert "clamping e to 0" in caplog.text


def test_e_profile_table_interpolates(tmp_path: Path) -> None:
    table_path = tmp_path / "e_profile.csv"
    df = pd.DataFrame({"r_RM": [1.0, 2.0], "e": [0.2, 0.6]})
    df.to_csv(table_path, index=False)

    profile = schema.DynamicsEccentricityProfile(
        mode="table",
        table_path=table_path,
        r_kind="r_RM",
    )
    r_rm = np.array([1.0, 1.5, 2.0], dtype=float)
    r_vals = r_rm * constants.R_MARS
    e_vals, meta = eccentricity.evaluate_e_profile(profile, r_m=r_vals, r_RM=r_rm)

    expected = np.interp(r_rm, [1.0, 2.0], [0.2, 0.6])
    assert meta["mode"] == "table"
    assert meta["table_path"] == str(table_path)
    assert np.allclose(e_vals, expected)


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
def test_run_zero_d_applies_e_profile(tmp_path: Path) -> None:
    outdir = tmp_path / "e_profile_zero_d"
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.0,
                r_out_RM=2.0,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.1,
            i0=0.01,
            t_damp_orbits=1.0,
            f_wake=1.0,
            e_mode="fixed",
            i_mode="fixed",
            e_profile=schema.DynamicsEccentricityProfile(mode="mars_pericenter"),
        ),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0]),
        numerics=schema.Numerics(t_end_years=1.0e-9, dt_init=1.0),
        io=schema.IO(outdir=outdir),
        sinks=schema.Sinks(mode="none", enable_sublimation=False),
    )

    run.run_zero_d(cfg)

    r_m = cfg.disk.geometry.r_in_RM * constants.R_MARS
    expected_e = 1.0 - constants.R_MARS / r_m
    assert cfg.dynamics.e0 == pytest.approx(expected_e)

    run_cfg = json.loads((outdir / "run_config.json").read_text(encoding="utf-8"))
    init_ei = run_cfg.get("init_ei", {})
    assert init_ei.get("e_profile_mode") == "mars_pericenter"
    assert init_ei.get("e_profile_applied") is True


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
def test_run_one_d_records_e_value(tmp_path: Path) -> None:
    table_path = tmp_path / "e_profile_table.csv"
    df = pd.DataFrame({"r_RM": [1.5, 2.5], "e": [0.2, 0.4]})
    df.to_csv(table_path, index=False)

    outdir = tmp_path / "e_profile_one_d"
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "supply.enabled=false",
        f"io.outdir={outdir}",
        "io.streaming.enable=false",
        "dynamics.e_mode=fixed",
        "dynamics.e_profile.mode=table",
        "dynamics.e_profile.r_kind=r_RM",
        f"dynamics.e_profile.table_path={table_path}",
        "disk.geometry.r_in_RM=1.5",
        "disk.geometry.r_out_RM=2.5",
    ]

    cfg = run.load_config(Path("configs/base.yml"), overrides=overrides)
    import marsdisk.run_one_d as run_one_d_module
    run_one_d_module.run_one_d(cfg)

    run_df = pd.read_parquet(outdir / "series" / "run.parquet", columns=["r_RM", "e_value"])
    expected = np.interp(run_df["r_RM"].to_numpy(), [1.5, 2.5], [0.2, 0.4])
    assert np.allclose(run_df["e_value"].to_numpy(), expected)
