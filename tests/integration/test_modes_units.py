import math
from pathlib import Path

import numpy as np
import pytest

from marsdisk import config_utils, constants, run, schema


def _base_config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=1.4,
                r_out_RM=1.4,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=2000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=16),
        initial=schema.Initial(mass_total=2.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=10.0,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
            rng_seed=98765,
            e_mode="mars_clearance",
            dr_min_m=1.0e4,
            dr_max_m=1.0e4,
            dr_dist="uniform",
            i_mode="obs_tilt_spread",
            obs_tilt_deg=12.0,
            i_spread_deg=3.0,
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-7, dt_init=1.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.0e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False),
    )
    cfg.sinks.mode = "none"
    return cfg


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_mars_clearance_uses_meter_offsets(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "units_case")

    run.run_zero_d(cfg)

    a_m, _, _ = config_utils.resolve_reference_radius(cfg)
    delta_r = cfg.dynamics.dr_min_m  # deterministic because min == max
    expected_e = 1.0 - (constants.R_MARS + delta_r) / a_m
    assert cfg.dynamics.e0 == pytest.approx(expected_e)

    seed = cfg.dynamics.rng_seed
    rng = np.random.default_rng(seed)
    # first call consumed by mars_clearance sampling even when bounds are equal
    _ = rng.uniform(cfg.dynamics.dr_min_m, cfg.dynamics.dr_max_m)
    lower = max(math.radians(cfg.dynamics.obs_tilt_deg - cfg.dynamics.i_spread_deg), 0.0)
    upper = min(math.radians(cfg.dynamics.obs_tilt_deg + cfg.dynamics.i_spread_deg), 0.5 * math.pi)
    expected_i = float(rng.uniform(lower, upper))
    assert cfg.dynamics.i0 == pytest.approx(expected_i)
