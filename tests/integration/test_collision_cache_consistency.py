from __future__ import annotations

import importlib
import os

import numpy as np

from marsdisk.physics import psd


def _run_collision_step(*, disable_cache: bool) -> dict[str, object]:
    if disable_cache:
        os.environ["MARSDISK_DISABLE_COLLISION_CACHE"] = "1"
    else:
        os.environ.pop("MARSDISK_DISABLE_COLLISION_CACHE", None)

    import marsdisk.physics.collisions_smol as collisions_smol

    collisions_smol = importlib.reload(collisions_smol)

    psd_state = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=3.0e-4,
        alpha=3.5,
        wavy_strength=0.1,
        n_bins=12,
        rho=3000.0,
    )
    ctx = collisions_smol.CollisionStepContext(
        time_orbit=collisions_smol.TimeOrbitParams(
            dt=100.0,
            Omega=1.0e-4,
            r=1.0e7,
            t_blow=1.0e4,
        ),
        material=collisions_smol.MaterialParams(
            rho=3000.0,
            a_blow=1.0e-6,
            s_min_effective=1.0e-6,
        ),
        dynamics=collisions_smol.DynamicsParams(
            e_value=0.02,
            i_value=0.01,
            dynamics_cfg=None,
            tau_eff=1.0e-3,
        ),
        supply=collisions_smol.SupplyParams(
            prod_subblow_area_rate=1.0e-8,
            supply_injection_mode="powerlaw_bins",
            supply_s_inj_min=1.0e-6,
            supply_s_inj_max=5.0e-6,
            supply_q=3.5,
            supply_mass_weights=None,
            supply_velocity_cfg=None,
        ),
        control=collisions_smol.CollisionControlFlags(
            enable_blowout=True,
            collisions_enabled=True,
            mass_conserving_sublimation=False,
            headroom_policy="clip",
            sigma_tau1=None,
            t_sink=None,
            ds_dt_val=None,
        ),
        sigma_surf=1.0e-3,
    )
    result = collisions_smol.step_collisions(ctx, psd_state)
    return {
        "sigma_after": float(result.sigma_after),
        "sigma_loss": float(result.sigma_loss),
        "mass_error": float(result.mass_error),
        "mass_loss_rate_blowout": float(result.mass_loss_rate_blowout),
        "number": np.array(result.psd_state["number"], copy=True),
    }


def test_collision_cache_consistency() -> None:
    original_env = os.environ.get("MARSDISK_DISABLE_COLLISION_CACHE")
    try:
        cached = _run_collision_step(disable_cache=False)
        uncached = _run_collision_step(disable_cache=True)
    finally:
        if original_env is None:
            os.environ.pop("MARSDISK_DISABLE_COLLISION_CACHE", None)
        else:
            os.environ["MARSDISK_DISABLE_COLLISION_CACHE"] = original_env

    for key in ("sigma_after", "sigma_loss", "mass_error", "mass_loss_rate_blowout"):
        assert np.isclose(cached[key], uncached[key], rtol=1.0e-12, atol=1.0e-12), key
    assert np.allclose(
        cached["number"],
        uncached["number"],
        rtol=1.0e-12,
        atol=1.0e-12,
    )
