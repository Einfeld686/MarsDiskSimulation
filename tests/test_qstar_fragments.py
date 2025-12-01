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
