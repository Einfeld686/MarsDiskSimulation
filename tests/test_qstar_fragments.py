import numpy as np

from marsdisk.physics.qstar import compute_q_d_star_F1
from marsdisk.physics.fragments import (
    compute_q_r_F2,
    compute_largest_remnant_mass_fraction_F2,
    compute_s_min_F2,
)


def test_qdstar_velocity_interpolation_monotonic():
    s = 1.0
    rho = 3000.0
    q3 = compute_q_d_star_F1(s, rho, 3.0)
    q4 = compute_q_d_star_F1(s, rho, 4.0)
    q5 = compute_q_d_star_F1(s, rho, 5.0)
    assert q3 < q4 < q5


def test_largest_remnant_fraction_continuity():
    m1 = m2 = 1.0
    q_rd_star = 1.0
    # velocities giving Q_R/Q_RD* = 0, 0.5, 1, 2
    v_vals = [0.0, np.sqrt(4.0 / 0.5), np.sqrt(8.0 / 0.5), np.sqrt(16.0 / 0.5)]
    q_r_vals = [compute_q_r_F2(m1, m2, v) for v in v_vals]
    fracs = [
        compute_largest_remnant_mass_fraction_F2(m1, m2, v, q_rd_star)
        for v in v_vals
    ]
    # physically reasonable range and monotonic decrease
    assert fracs[0] == 1.0
    assert fracs[-1] == 0.0
    assert all(0.0 <= f <= 1.0 for f in fracs)
    assert all(fracs[i] > fracs[i + 1] for i in range(len(fracs) - 1))
    assert q_r_vals == sorted(q_r_vals)


def test_compute_s_min_bounds_and_monotonic():
    a_blow = 1e-6
    t_ref = 10.0
    rho = 3000.0
    T_vals = [1000.0, 1300.0, 1400.0, 1500.0]
    s_vals = [
        compute_s_min_F2(a_blow, T, t_ref=t_ref, rho=rho) for T in T_vals
    ]
    assert all(s >= a_blow for s in s_vals)
    assert s_vals == sorted(s_vals)
