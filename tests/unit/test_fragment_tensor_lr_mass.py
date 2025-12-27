from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import collisions_smol, fragments, qstar


def _find_midrange_pair(f_lr: np.ndarray, low: float = 0.1, high: float = 0.9) -> tuple[int, int] | None:
    indices = np.argwhere((f_lr > low) & (f_lr < high))
    if indices.size == 0:
        return None
    for idx in indices:
        i, j = (int(idx[0]), int(idx[1]))
        if max(i, j) > 0:
            return i, j
    return None


def test_fragment_tensor_lr_bin_preserves_mass(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = np.array([1.0e-6, 2.0e-6, 4.0e-6])
    widths = np.array([0.6e-6, 1.0e-6, 2.0e-6])
    edges = np.empty(sizes.size + 1)
    edges[:-1] = np.maximum(sizes - 0.5 * widths, 0.0)
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    rho = 3000.0
    masses = (4.0 / 3.0) * np.pi * rho * sizes**3

    monkeypatch.setattr(collisions_smol, "_USE_NUMBA", False)
    collisions_smol._NUMBA_FAILED = False

    candidates = [3000.0, 5000.0, 7000.0, 10000.0]
    chosen = None
    v_rel_use = None
    v_matrix_use = None
    f_lr_use = None
    for v_rel in candidates:
        v_matrix = np.full((sizes.size, sizes.size), float(v_rel))
        q_star = qstar.compute_q_d_star_array(np.maximum.outer(sizes, sizes), rho, v_matrix / 1.0e3)
        q_r = fragments.q_r_array(masses[:, None], masses[None, :], v_matrix)
        f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)
        match = _find_midrange_pair(f_lr)
        if match is not None:
            chosen = match
            v_rel_use = v_rel
            v_matrix_use = v_matrix
            f_lr_use = f_lr
            break

    assert chosen is not None, "Failed to find mid-range f_lr pair for the test setup."
    i, j = chosen

    Y = collisions_smol._fragment_tensor(
        sizes, masses, edges, float(v_rel_use), rho, alpha_frag=3.5, use_numba=False
    )
    m_tot = masses[i] + masses[j]
    f_lr_val = float(f_lr_use[i, j])
    s_lr = (3.0 * f_lr_val * m_tot / (4.0 * np.pi * rho)) ** (1.0 / 3.0)
    k_lr = int(np.searchsorted(edges, s_lr, side="right") - 1)
    k_lr = max(0, min(k_lr, sizes.size - 1))
    assert v_matrix_use is not None
    assert f_lr_use is not None
    y_lr = float(Y[k_lr, i, j])
    y_sum = float(np.sum(Y[:, i, j]))

    assert y_sum == pytest.approx(1.0, rel=1e-6, abs=1e-12)
    assert y_lr >= f_lr_val - 1.0e-12
    assert y_lr <= 1.0 + 1.0e-12
