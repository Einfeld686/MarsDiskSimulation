"""Scaling relations for collisional time-scales."""

from __future__ import annotations

import math

import pytest

from marsdisk.physics import surface


@pytest.mark.parametrize("tau", [5.0e-4, 2.0e-3, 1.0e-2])
def test_wyatt_collisional_timescale_matches_orbit_scaling(tau: float) -> None:
    """Wyatt (2008) scaling should match T_orb/(4π τ)."""

    Omega = 1.7e-4  # s^-1 representative of inner disk
    t_coll = surface.wyatt_tcoll_S1(tau, Omega)
    t_orb = 2.0 * math.pi / Omega
    expected = t_orb / (4.0 * math.pi * tau)
    assert math.isclose(t_coll, expected, rel_tol=1e-12, abs_tol=0.0)
