from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import run, schema


def _build_chi_config(outdir: Path, *, chi_blow: float) -> schema.Config:
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
        radiation=schema.Radiation(TM_K=4000.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-8, s_max=1.0e-4, n_bins=24),
        initial=schema.Initial(mass_total=1.0e-10, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=1.0e-4,
            i0=5.0e-5,
            t_damp_orbits=1.0e3,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
        ),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-4, dt_init=200.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=0.0),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, quiet=True),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = "smol"
    cfg.chi_blow = chi_blow
    return cfg


def _first_positive(series: pd.Series) -> float:
    values = series.to_numpy()
    for value in values:
        if value > 0.0 and np.isfinite(value):
            return float(value)
    return float(values[0])


def test_blowout_rate_scales_with_chi_blow(tmp_path: Path) -> None:
    cfg_fast = _build_chi_config(tmp_path / "chi_fast", chi_blow=0.5)
    cfg_slow = _build_chi_config(tmp_path / "chi_slow", chi_blow=2.0)

    run.run_zero_d(cfg_fast)
    run.run_zero_d(cfg_slow)

    series_fast = pd.read_parquet(Path(cfg_fast.io.outdir) / "series" / "run.parquet")
    series_slow = pd.read_parquet(Path(cfg_slow.io.outdir) / "series" / "run.parquet")

    rate_fast = _first_positive(series_fast["dSigma_dt_blowout"])
    rate_slow = _first_positive(series_slow["dSigma_dt_blowout"])

    assert rate_fast > 0.0
    assert rate_slow > 0.0

    expected_ratio = cfg_slow.chi_blow / cfg_fast.chi_blow
    assert rate_fast / rate_slow == pytest.approx(expected_ratio, rel=0.2)
