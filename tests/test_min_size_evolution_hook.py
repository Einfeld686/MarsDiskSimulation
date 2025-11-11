from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import constants, run, schema


def _base_config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.2 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-2, n_bins=20),
        initial=schema.Initial(mass_total=1.0e-7, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=5.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-6, dt_init=100.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.0e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False, correct_fast_blowout=False),
    )
    cfg.sinks.mode = "none"
    return cfg


def test_s_min_evolved_column_absent_when_disabled(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "disabled")
    cfg.sizes.evolve_min_size = False
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert "s_min_evolved" not in df.columns


def test_s_min_evolved_column_records_candidate_when_enabled(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "enabled")
    cfg.sizes.evolve_min_size = True
    cfg.sizes.dsdt_model = "noop"
    cfg.sizes.dsdt_params = {}
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert "s_min_evolved" in df.columns
    assert (df["s_min_evolved"].diff().fillna(0.0) <= 1e-12).all()


def test_s_min_evolved_monotonic_with_linear_decay(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "linear")
    cfg.sizes.evolve_min_size = True
    cfg.sizes.dsdt_model = "linear_decay"
    cfg.sizes.dsdt_params = {"k0": 5e-12}
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert "s_min_evolved" in df.columns
    series = df["s_min_evolved"].to_numpy()
    diffs = np.diff(series)
    assert np.all(diffs <= 1e-12)
    assert series[-1] >= 0.0
