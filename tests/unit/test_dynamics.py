from marsdisk.physics import dynamics


def const_eps(v: float) -> float:
    return 0.5


def test_v_ij_zero_limit():
    v = dynamics.v_ij(1e-8, 1e-8)
    assert v < 1e-6


def test_c_eq_monotonic_tau_fwake():
    c1 = dynamics.solve_c_eq(0.1, 1e-3, const_eps)
    c2 = dynamics.solve_c_eq(0.5, 1e-3, const_eps)
    assert c1 <= c2
    c3 = dynamics.solve_c_eq(0.5, 1e-3, const_eps, f_wake=2.0)
    assert c2 <= c3


def test_update_e_relaxation():
    e_new = dynamics.update_e(0.1, 0.2, 10.0, 1.0)
    assert 0.1 < e_new < 0.2
