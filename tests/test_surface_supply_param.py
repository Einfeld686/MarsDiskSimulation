import math
import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, grid
from marsdisk.physics import collisions_smol, psd, supply
from marsdisk.physics.surface import step_surface_density_S1
from marsdisk.schema import (
    Supply,
    SupplyConst,
    SupplyPowerLaw,
    SupplyTable,
    SupplyMixing,
)


def test_const_mode():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=5.0),
        mixing=SupplyMixing(epsilon_mix=0.5),
    )
    rate = supply.get_prod_area_rate(0.0, 1.0, cfg)
    assert rate == 2.5


def test_powerlaw_mode():
    cfg = Supply(
        mode="powerlaw",
        powerlaw=SupplyPowerLaw(A_kg_m2_s=2.0, t0_s=1.0, index=-1.0),
    )
    rate = supply.get_prod_area_rate(2.0, 1.0, cfg)
    assert rate == pytest.approx(2.0 * ((2.0 - 1.0) + 1.0e-12) ** -1.0)


def test_table_mode(tmp_path):
    path = tmp_path / "rate.csv"
    pd.DataFrame({"t": [0.0, 10.0], "rate": [1.0, 3.0]}).to_csv(path, index=False)
    cfg = Supply(mode="table", table=SupplyTable(path=path))
    rate = supply.get_prod_area_rate(5.0, 1.0, cfg)
    assert rate == pytest.approx(2.0)


MASS_TOL = 5e-3


def _surface_mass_budget_error(
    sigma_prev: float,
    sigma_next: float,
    prod_rate: float,
    outflux: float,
    sink_flux: float,
    dt: float,
    Omega: float,
    *,
    t_coll: float | None = None,
    t_sink: float | None = None,
) -> float:
    """Return the relative mass-budget error for a single surface step."""

    loss = Omega
    if t_coll is not None and t_coll > 0.0:
        loss += 1.0 / t_coll
    if t_sink is not None and t_sink > 0.0:
        loss += 1.0 / t_sink
    sigma_candidate = (sigma_prev + dt * prod_rate) / (1.0 + dt * loss)
    clip_loss = max(0.0, sigma_candidate - sigma_next)
    effective_out = outflux + sink_flux + clip_loss / dt
    rhs = sigma_prev + dt * prod_rate
    lhs = sigma_next + dt * effective_out
    return abs(lhs - rhs) / max(rhs, 1.0e-12)


def _run_surface(
    cfg: Supply,
    *,
    Omega: float,
    sigma_tau1: float,
    dt: float,
    steps: int,
    sigma0: float = 0.0,
) -> list[dict[str, float]]:
    """Integrate the surface layer for a fixed supply specification."""

    sigma = sigma0
    t = 0.0
    records: list[dict[str, float]] = []
    for _ in range(steps):
        prod_rate = supply.get_prod_area_rate(t, 0.0, cfg)
        res = step_surface_density_S1(
            sigma,
            prod_rate,
            dt,
            Omega,
            sigma_tau1=sigma_tau1,
        )
        err = _surface_mass_budget_error(
            sigma,
            res.sigma_surf,
            prod_rate,
            res.outflux,
            res.sink_flux,
            dt,
            Omega,
        )
        records.append(
            {
                "time": t,
                "sigma": res.sigma_surf,
                "outflux": res.outflux,
                "prod": prod_rate,
                "mass_error": err,
            }
        )
        sigma = res.sigma_surf
        t += dt
    return records


def test_surface_const_supply_loss_limited():
    Omega = 1.0e-4
    sigma_tau1 = 1.0e-3
    dt = 100.0
    cfg = Supply(mode="const", const=SupplyConst(prod_area_rate_kg_m2_s=5.0e-7))

    records = _run_surface(cfg, Omega=Omega, sigma_tau1=sigma_tau1, dt=dt, steps=400)
    errors = [rec["mass_error"] for rec in records]
    assert max(errors) < MASS_TOL

    expected_outflux = sigma_tau1 * Omega
    tail_out = np.array([rec["outflux"] for rec in records[-40:]])
    tail_sigma = np.array([rec["sigma"] for rec in records[-40:]])
    assert np.allclose(tail_out, expected_outflux, rtol=1e-2)
    assert np.allclose(tail_sigma, sigma_tau1, rtol=1e-3)


def test_surface_no_supply_decay():
    Omega = 1.0e-4
    sigma_tau1 = 1.0e-3
    dt = 1000.0
    sigma_init = 5.0e-4
    cfg = Supply(mode="const", const=SupplyConst(prod_area_rate_kg_m2_s=0.0))

    records = _run_surface(
        cfg,
        Omega=Omega,
        sigma_tau1=sigma_tau1,
        dt=dt,
        steps=120,
        sigma0=sigma_init,
    )
    errors = [rec["mass_error"] for rec in records]
    assert max(errors) < MASS_TOL

    start_outflux = records[0]["outflux"]
    end_outflux = records[-1]["outflux"]
    assert end_outflux < start_outflux * 1.0e-3
    assert records[-1]["sigma"] < sigma_init * 1.0e-3


def test_surface_table_supply_tracks_changes(tmp_path):
    path = tmp_path / "supply_table.csv"
    times = [0.0, 30000.0, 60000.0, 90000.0, 120000.0]
    rates = [0.0, 5.0e-8, 0.0, 2.0e-8, 4.0e-8]
    pd.DataFrame({"t": times, "rate": rates}).to_csv(path, index=False)
    cfg = Supply(mode="table", table=SupplyTable(path=path))

    Omega = 1.0e-4
    sigma_tau1 = 1.0e-3
    dt = 500.0
    records = _run_surface(cfg, Omega=Omega, sigma_tau1=sigma_tau1, dt=dt, steps=320)
    errors = [rec["mass_error"] for rec in records]
    assert max(errors) < MASS_TOL

    def avg_slice(start: int) -> dict[str, float]:
        subset = records[start : start + 10]
        return {
            "prod": float(np.mean([rec["prod"] for rec in subset])),
            "outflux": float(np.mean([rec["outflux"] for rec in subset])),
            "sigma": float(np.mean([rec["sigma"] for rec in subset])),
        }

    avg_high_initial = avg_slice(50)
    avg_zero = avg_slice(110)
    avg_moderate = avg_slice(170)
    avg_high_final = avg_slice(230)

    assert avg_high_initial["prod"] > 1.0e-8
    assert avg_zero["prod"] < 1.0e-8
    assert avg_moderate["prod"] > avg_zero["prod"]
    assert avg_high_final["prod"] > avg_moderate["prod"]

    assert avg_high_initial["outflux"] > avg_zero["outflux"]
    assert avg_zero["outflux"] > avg_moderate["outflux"]
    assert avg_high_final["outflux"] > avg_moderate["outflux"]

    assert avg_high_initial["sigma"] > avg_zero["sigma"]
    assert avg_zero["sigma"] > avg_moderate["sigma"]
    assert avg_high_final["sigma"] > avg_moderate["sigma"]


def test_smol_helper_respects_tau_clip_and_budget():
    r = constants.R_MARS
    Omega = grid.omega_kepler(r)
    psd_state = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=1.0e-3,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=16,
        rho=3000.0,
    )
    prod_rate = 5.0e-7
    dt = 25.0
    sigma_tau1 = 1.0e-4

    res = collisions_smol.step_collisions_smol_0d(
        psd_state,
        sigma_surf=0.0,
        dt=dt,
        prod_subblow_area_rate=prod_rate,
        r=r,
        Omega=Omega,
        a_blow=5.0e-6,
        rho=3000.0,
        e_value=0.01,
        i_value=0.005,
        sigma_tau1=sigma_tau1,
        enable_blowout=True,
        t_sink=None,
        ds_dt_val=None,
    )

    assert res.sigma_for_step <= sigma_tau1 + 1e-12
    assert res.sigma_after > 0.0
    assert math.isfinite(res.mass_error)
    assert res.mass_error <= 5e-3
