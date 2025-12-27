from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import run


_BASE_OVERRIDES = [
    "numerics.t_end_orbits=0.1",
    "numerics.t_end_years=null",
    "io.streaming.enable=false",
    "dynamics.e_profile.mode=off",
    "phase.enabled=false",
    "surface.collision_solver=smol",
    "sinks.mode=\"none\"",
    "sinks.enable_sublimation=false",
    "sinks.enable_gas_drag=false",
    "blowout.enabled=false",
]


def _run_case(tmp_path: Path, name: str, overrides: list[str]) -> Path:
    outdir = tmp_path / name
    cfg = run.load_config(
        Path("configs/base.yml"),
        overrides=[f"io.outdir={outdir}", *_BASE_OVERRIDES, *overrides],
    )
    run.run_zero_d(cfg)
    return outdir


def test_default_supply_pipeline_smol(tmp_path: Path) -> None:
    outdir = _run_case(
        tmp_path,
        "default_supply",
        overrides=[
            "supply.enabled=true",
            "supply.mode=const",
        ],
    )

    series_path = outdir / "series" / "run.parquet"
    run_cfg_path = outdir / "run_config.json"
    assert series_path.exists()
    assert run_cfg_path.exists()

    df = pd.read_parquet(
        series_path,
        columns=[
            "t_orb_s",
            "prod_subblow_area_rate",
            "prod_subblow_area_rate_raw",
            "supply_rate_nominal",
            "supply_rate_scaled",
            "supply_rate_applied",
        ],
    )
    assert len(df) >= 2

    run_cfg = json.loads(run_cfg_path.read_text())
    supply_cfg = run_cfg["supply"]
    mu_orbit = float(supply_cfg["mu_orbit10pct"])
    orbit_fraction = float(supply_cfg["orbit_fraction_at_mu1"])
    epsilon_mix = float(supply_cfg["epsilon_mix"])
    sigma_ref = float(run_cfg["sigma_surf_mu_reference"])
    t_orb = float(df["t_orb_s"].iloc[0])

    expected_scaled = mu_orbit * orbit_fraction * sigma_ref / t_orb
    expected_raw = expected_scaled / epsilon_mix

    first = df.iloc[0]
    assert first["supply_rate_nominal"] == pytest.approx(0.0)
    assert first["supply_rate_scaled"] == pytest.approx(0.0)
    assert first["supply_rate_applied"] == pytest.approx(0.0)
    assert first["prod_subblow_area_rate"] == pytest.approx(0.0)
    assert first["prod_subblow_area_rate_raw"] == pytest.approx(expected_raw, rel=1e-6)

    after = df.iloc[1:]
    active = after["supply_rate_scaled"] > 0.0
    assert active.any()

    scaled = after.loc[active, "supply_rate_scaled"]
    nominal = after.loc[active, "supply_rate_nominal"]
    applied = after.loc[active, "supply_rate_applied"]
    prod = after.loc[active, "prod_subblow_area_rate"]
    raw = df["prod_subblow_area_rate_raw"]

    assert np.isfinite(scaled).all()
    assert np.isfinite(nominal).all()
    assert np.isfinite(applied).all()
    assert np.isfinite(prod).all()
    assert np.isfinite(raw).all()

    assert scaled.median() == pytest.approx(expected_scaled, rel=1e-3)
    assert nominal.median() == pytest.approx(expected_scaled, rel=1e-3)
    assert applied.median() == pytest.approx(expected_scaled, rel=1e-3)
    assert prod.median() == pytest.approx(expected_scaled, rel=1e-3)
    assert raw.median() == pytest.approx(expected_raw, rel=1e-3)
    assert np.allclose(applied, prod, rtol=1e-6)


def test_supply_disabled_zeroes_rates(tmp_path: Path) -> None:
    outdir = _run_case(
        tmp_path,
        "supply_disabled",
        overrides=[
            "supply.enabled=false",
        ],
    )

    cols = [
        "prod_subblow_area_rate",
        "prod_subblow_area_rate_raw",
        "supply_rate_nominal",
        "supply_rate_scaled",
        "supply_rate_applied",
    ]
    df = pd.read_parquet(
        outdir / "series" / "run.parquet",
        columns=cols,
    )
    assert np.isfinite(df[cols]).all().all()
    values = df[cols].fillna(0.0).to_numpy()
    assert np.all(np.abs(values) <= 1e-18)
