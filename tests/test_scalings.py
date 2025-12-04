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


def _smol_to_wyatt_ratio(kernel_mode: str, H_factor: float) -> float:
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
    t_coll_smol = collisions_smol.kernel_minimum_tcoll(C)
    t_coll_wyatt = surface.wyatt_tcoll_S1(tau, Omega)
    return t_coll_smol / t_coll_wyatt


def test_smol_tcoll_matches_wyatt_config_mode() -> None:
    ratio = _smol_to_wyatt_ratio("config", H_factor=0.05)
    assert 0.1 <= ratio <= 10.0


def test_smol_tcoll_matches_wyatt_wyatt_eq_mode() -> None:
    ratio = _smol_to_wyatt_ratio("wyatt_eq", H_factor=0.1)
    assert 0.1 <= ratio <= 10.0
