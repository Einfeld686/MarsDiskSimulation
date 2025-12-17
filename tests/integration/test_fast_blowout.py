import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import run, schema


def _build_fast_blowout_config(
    outdir: Path,
    *,
    correct: bool,
    substep: bool = False,
    substep_ratio: float = 1.0,
    collision_solver: str = "smol",
) -> schema.Config:
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
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-2, n_bins=16),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=10.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=5.0e-4, dt_init=1.6e4),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-10),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(
            outdir=outdir,
            debug_sinks=False,
            correct_fast_blowout=correct,
            substep_fast_blowout=substep,
            substep_max_ratio=substep_ratio,
        ),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = collision_solver
    return cfg


def test_fast_blowout_factor_samples() -> None:
    ratios = [0.1, 1.0, 10.0]
    expected = [1.0 - math.exp(-r) for r in ratios]
    for ratio, target in zip(ratios, expected):
        value = run._fast_blowout_correction_factor(ratio)
        assert value == pytest.approx(target, rel=1e-6, abs=1e-9)


def test_chi_blow_auto_range(tmp_path: Path) -> None:
    cfg = _build_fast_blowout_config(tmp_path / "auto", correct=False)
    cfg.chi_blow = "auto"
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    chi_series = df["chi_blow_eff"].to_numpy()
    assert np.all(chi_series >= 0.5)
    assert np.all(chi_series <= 2.0)
    assert 0.5 <= float(summary["chi_blow_eff"]) <= 2.0


def test_surface_ode_substeps_activate(tmp_path: Path) -> None:
    cfg = _build_fast_blowout_config(
        tmp_path / "surface_substeps",
        correct=False,
        substep=True,
        substep_ratio=0.4,
        collision_solver="surface_ode",
    )
    run.run_zero_d(cfg)

    series = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    n_substeps_max = int(series["n_substeps"].max())
    assert n_substeps_max > 1
    assert bool(series["substep_active"].any())
    assert float(series["dt_over_t_blow"].max()) > cfg.io.substep_max_ratio

    budget = pd.read_csv(Path(cfg.io.outdir) / "checks" / "mass_budget.csv")
    assert float(budget["error_percent"].max()) <= 0.5


def test_smol_ignores_substeps(tmp_path: Path) -> None:
    cfg_base = _build_fast_blowout_config(
        tmp_path / "smol_base",
        correct=False,
        substep=False,
        substep_ratio=0.4,
        collision_solver="smol",
    )
    cfg_sub = _build_fast_blowout_config(
        tmp_path / "smol_sub",
        correct=False,
        substep=True,
        substep_ratio=0.4,
        collision_solver="smol",
    )
    run.run_zero_d(cfg_base)
    run.run_zero_d(cfg_sub)

    series_base = pd.read_parquet(Path(cfg_base.io.outdir) / "series" / "run.parquet")
    series_sub = pd.read_parquet(Path(cfg_sub.io.outdir) / "series" / "run.parquet")

    assert series_sub["n_substeps"].nunique() == 1
    assert int(series_sub["n_substeps"].iloc[0]) == 1
    assert not bool(series_sub["substep_active"].any())

    pd.testing.assert_series_equal(series_base["M_out_dot"], series_sub["M_out_dot"], check_names=False)
    pd.testing.assert_series_equal(series_base["M_out_dot_avg"], series_sub["M_out_dot_avg"], check_names=False)
    pd.testing.assert_series_equal(
        series_base["fast_blowout_factor_avg"], series_sub["fast_blowout_factor_avg"], check_names=False
    )
