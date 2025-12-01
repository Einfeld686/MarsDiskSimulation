import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, run, schema


def _build_fast_blowout_config(
    outdir: Path,
    *,
    correct: bool,
    substep: bool = False,
    substep_ratio: float = 1.0,
) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.5 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
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
