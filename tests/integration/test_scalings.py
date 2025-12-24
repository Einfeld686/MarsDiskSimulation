"""Scaling relations for collisional time-scales."""

from __future__ import annotations

import math

import pytest

import numpy as np

from marsdisk import constants, grid, schema
from marsdisk.physics import collide, collisions_smol, dynamics, surface


@pytest.mark.parametrize("tau", [5.0e-4, 2.0e-3, 1.0e-2])
def test_strubbe_chiang_collisional_timescale_matches_orbit_scaling(tau: float) -> None:
    """Strubbe–Chiang scaling should match T_orb/(2π τ)."""

    Omega = 1.7e-4  # s^-1 representative of inner disk
    t_coll = surface.wyatt_tcoll_S1(tau, Omega)
    t_orb = 2.0 * math.pi / Omega
    expected = t_orb / (2.0 * math.pi * tau)
    assert math.isclose(t_coll, expected, rel_tol=1e-12, abs_tol=0.0)


def _expected_smol_to_wyatt_ratio(e_kernel: float, i_kernel: float, H_factor: float) -> float:
    """Return analytic ratio for the single-bin kernel geometry."""

    denom = math.sqrt(1.25 * e_kernel * e_kernel + i_kernel * i_kernel)
    if denom <= 0.0:
        return math.inf
    return math.sqrt(math.pi) * H_factor * i_kernel / (2.0 * denom)


def _smol_to_wyatt_ratio(kernel_mode: str, H_factor: float) -> tuple[float, float, float]:
    tau = 1.0e-3
    s = 0.1
    sizes = np.array([s])
    dyn = schema.Dynamics(
        e0=2.0e-4,
        i0=1.0e-4,
        t_damp_orbits=1.0e3,
        f_wake=1.0,
        kernel_ei_mode=kernel_mode,  # config or wyatt_eq
        kernel_H_mode="ia",
        H_factor=H_factor,
    )
    r = constants.R_MARS
    Omega = grid.omega_kepler(r)
    v_k = r * Omega
    e_kernel, i_kernel, H_k = collisions_smol.compute_kernel_e_i_H(
        dyn,
        tau_eff=tau,
        a_orbit_m=r,
        v_k=v_k,
        sizes=sizes,
    )
    N = tau / (np.pi * s * s)
    v_rel = dynamics.v_ij(e_kernel, i_kernel, v_k=v_k)
    C = collide.compute_collision_kernel_C1(np.array([N]), sizes, H_k, v_rel)
    t_coll_smol = collisions_smol.kernel_minimum_tcoll(C, np.array([N]))
    t_coll_wyatt = surface.wyatt_tcoll_S1(tau, Omega)
    return t_coll_smol / t_coll_wyatt, e_kernel, i_kernel


def test_smol_tcoll_matches_wyatt_config_mode() -> None:
    ratio, e_kernel, i_kernel = _smol_to_wyatt_ratio("config", H_factor=0.05)
    expected = _expected_smol_to_wyatt_ratio(e_kernel, i_kernel, H_factor=0.05)
    assert 0.5 * expected <= ratio <= 2.0 * expected


def test_smol_tcoll_matches_wyatt_wyatt_eq_mode() -> None:
    ratio, e_kernel, i_kernel = _smol_to_wyatt_ratio("wyatt_eq", H_factor=0.1)
    expected = _expected_smol_to_wyatt_ratio(e_kernel, i_kernel, H_factor=0.1)
    assert 0.5 * expected <= ratio <= 2.0 * expected
