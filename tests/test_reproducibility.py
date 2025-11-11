import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from marsdisk import constants, run, schema


def _config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=1.3 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2100.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=12),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.02,
            t_damp_orbits=5.0,
            f_wake=1.0,
            rng_seed=None,
        ),
        psd=schema.PSD(alpha=1.6, wavy_strength=0.1),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-7, dt_init=2.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=2.5e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir),
    )
    cfg.sinks.mode = "none"
    return cfg


def _run_once(outdir: Path):
    cfg = _config(outdir)
    run.run_zero_d(cfg)
    summary = json.loads((outdir / "summary.json").read_text())
    series = pd.read_parquet(outdir / "series" / "run.parquet")
    return summary, series


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_repeated_runs_match(tmp_path: Path) -> None:
    summary_a, series_a = _run_once(tmp_path / "run_a")
    summary_b, series_b = _run_once(tmp_path / "run_b")

    assert summary_a["M_loss"] == pytest.approx(summary_b["M_loss"])
    assert summary_a["s_blow_m"] == pytest.approx(summary_b["s_blow_m"])
    assert_frame_equal(series_a, series_b)
