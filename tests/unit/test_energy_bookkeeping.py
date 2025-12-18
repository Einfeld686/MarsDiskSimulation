import numpy as np

from marsdisk.physics.collide import compute_collision_kernel_bookkeeping
from marsdisk.physics._numba_kernels import collision_kernel_bookkeeping_numba, NUMBA_AVAILABLE


def test_energy_bookkeeping_consistency_numpy():
    # Simple 2-bin case with symmetric inputs; force NumPy path.
    N = np.array([1.0, 2.0])
    s = np.array([1.0, 2.0])
    H = np.ones_like(N)
    m = np.array([1.0, 1.0])
    v_rel = 1.0
    f_ke_matrix = np.full((2, 2), 0.5)
    F_lf_matrix = np.array([[1.0, 0.4], [0.4, 0.4]])

    C, stats = compute_collision_kernel_bookkeeping(
        N, s, H, m, v_rel, f_ke_matrix, F_lf_matrix, use_numba=False
    )
    # Stats layout:
    # (E_rel_step, E_dissipated_step, E_retained_step,
    #  f_ke_mean_C, f_ke_energy, F_lf_mean,
    #  n_cratering_rate, n_fragmentation_rate,
    #  frac_cratering, frac_fragmentation)
    E_rel, E_diss, E_ret, f_ke_mean, f_ke_energy, F_lf_mean, n_crat, n_frag, frac_crat, frac_frag = stats

    # Energy consistency
    assert np.isclose(E_rel, E_diss + E_ret)
    if E_rel > 0:
        assert np.isclose(f_ke_energy, E_ret / E_rel)

    # f_ke_mean should reflect the input value (all 0.5)
    assert np.isclose(f_ke_mean, 0.5)

    # Largest remnant mean should be between 0 and 1
    assert 0.0 <= F_lf_mean <= 1.0

    # Cratering vs fragmentation split should be well-defined
    total_rate = n_crat + n_frag
    if total_rate > 0:
        assert np.isclose(frac_crat + frac_frag, 1.0)

    # Kernel is symmetric and positive
    assert C.shape == (2, 2)
    assert np.all(C >= 0.0)


def test_energy_bookkeeping_numba_vs_numpy():
    # Skip if numba not available
    if not NUMBA_AVAILABLE():
        return

    N = np.array([1.0, 2.0, 3.0])
    s = np.array([1.0, 2.0, 3.0])
    H = np.ones_like(N)
    m = np.array([1.0, 1.0, 1.0])
    v_rel = np.array([[1.0, 1.2, 1.4], [1.2, 1.0, 1.1], [1.4, 1.1, 1.0]])
    f_ke_matrix = np.full((3, 3), 0.4)
    F_lf_matrix = np.full((3, 3), 0.6)

    C_np, stats_np = compute_collision_kernel_bookkeeping(
        N, s, H, m, v_rel, f_ke_matrix, F_lf_matrix, use_numba=False
    )
    C_nb, stats_nb = collision_kernel_bookkeeping_numba(
        N,
        s,
        H,
        m,
        0.0,
        v_rel,
        True,
        f_ke_matrix,
        F_lf_matrix,
    )

    # Kernel and stats should match within tight tolerance
    assert np.allclose(C_np, C_nb, rtol=1e-10, atol=1e-12)
    assert np.allclose(stats_np, stats_nb, rtol=1e-10, atol=1e-12)
