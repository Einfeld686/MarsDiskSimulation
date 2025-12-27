import numpy as np
import pytest

from marsdisk.physics import fragments


def test_largest_remnant_fraction_reference_points() -> None:
    q_star = np.ones(2, dtype=float)
    phi = np.array([1.0, 1.8], dtype=float)
    q_r = phi * q_star
    f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)
    assert f_lr[0] == pytest.approx(0.5)
    assert f_lr[1] == pytest.approx(0.1)


def test_largest_remnant_fraction_continuity() -> None:
    q_star = np.ones(2, dtype=float)
    phi = np.array([1.8 - 1.0e-6, 1.8 + 1.0e-6], dtype=float)
    q_r = phi * q_star
    f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)
    assert f_lr[0] == pytest.approx(f_lr[1], rel=1.0e-6, abs=1.0e-6)


def test_largest_remnant_fraction_monotonic() -> None:
    q_star = np.ones(4, dtype=float)
    phi = np.array([0.2, 1.0, 1.8, 5.0], dtype=float)
    q_r = phi * q_star
    f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)
    assert np.all(np.diff(f_lr) < 0.0)


def test_largest_remnant_fraction_scalar_matches_piecewise() -> None:
    m1 = 1.0
    m2 = 1.0
    q_rd_star = 1.0
    v_phi1 = np.sqrt(8.0 * 1.0)
    v_phi18 = np.sqrt(8.0 * 1.8)
    f_phi1 = fragments.compute_largest_remnant_mass_fraction_F2(m1, m2, v_phi1, q_rd_star)
    f_phi18 = fragments.compute_largest_remnant_mass_fraction_F2(m1, m2, v_phi18, q_rd_star)
    assert f_phi1 == pytest.approx(0.5)
    assert f_phi18 == pytest.approx(0.1)
