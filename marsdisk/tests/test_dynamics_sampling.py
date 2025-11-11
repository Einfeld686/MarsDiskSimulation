import json

import numpy as np

from marsdisk import constants, run as run_module
from marsdisk import schema


def _make_config(outdir):
    geometry = schema.Geometry(mode="0D", r=1.3558e7)
    dynamics = schema.Dynamics(
        e0=0.1,
        i0=0.05,
        t_damp_orbits=100.0,
        f_wake=1.0,
        e_mode="mars_clearance",
        dr_min_m=1.0,
        dr_max_m=10.0,
        dr_dist="uniform",
        i_mode="obs_tilt_spread",
        obs_tilt_deg=30.0,
        i_spread_deg=5.0,
        rng_seed=42,
    )
    return schema.Config(
        geometry=geometry,
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1e-6, s_max=1e-2, n_bins=32),
        initial=schema.Initial(mass_total=1e-8, s0_mode="upper"),
        dynamics=dynamics,
        psd=schema.PSD(alpha=3.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1000.0, a_s=1.0, B=1.0, b_g=1.0, v_ref_kms=[1.0]),
        numerics=schema.Numerics(t_end_years=1e-6, dt_init=1e-6),
        io=schema.IO(outdir=outdir),
        sinks=schema.Sinks(mode="none", enable_sublimation=False),
    )


def test_stochastic_ei_sampling(tmp_path):
    outdir = tmp_path / "run_out"
    cfg = _make_config(outdir)

    run_module.run_zero_d(cfg)

    rng = np.random.default_rng(42)
    delta_r = rng.uniform(1.0, 10.0)
    a_m = cfg.geometry.r
    expected_e0 = 1.0 - (constants.R_MARS + delta_r) / a_m
    assert np.isclose(cfg.dynamics.e0, expected_e0, atol=1e-12)

    i_lower = np.deg2rad(25.0)
    i_upper = np.deg2rad(35.0)
    assert i_lower <= cfg.dynamics.i0 <= i_upper

    run_config = json.loads((outdir / "run_config.json").read_text(encoding="utf-8"))
    init_block = run_config.get("init_ei", {})
    assert init_block.get("e_formula_SI")
    assert init_block.get("a_m_source") == "geometry.r"
