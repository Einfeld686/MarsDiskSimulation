"""Numba カーネルとフォールバック経路の一致性を確認するユニットテスト。"""

from __future__ import annotations

import importlib
import os
from typing import Iterable

import numpy as np


def _reload_with_env(module_name: str, disable_numba: bool = False):
    if disable_numba:
        os.environ["MARSDISK_DISABLE_NUMBA"] = "1"
    else:
        os.environ.pop("MARSDISK_DISABLE_NUMBA", None)
    module = importlib.import_module(module_name)
    return importlib.reload(module)


def _mass_budget_python(N_old: Iterable[float], N_new: Iterable[float], m: Iterable[float], prod: float, dt: float, extra: float) -> float:
    N_old_arr = np.asarray(N_old, dtype=float)
    N_new_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    M_before = float(np.sum(m_arr * N_old_arr))
    M_after = float(np.sum(m_arr * N_new_arr))
    prod_term = dt * float(prod)
    extra_term = dt * float(extra)
    diff = M_after + extra_term - (M_before + prod_term)
    baseline = M_before if M_before > 0.0 else max(M_before + prod_term, 1.0e-30)
    return abs(diff) / baseline


def test_compute_prod_subblow_area_rate_numba_matches_numpy(monkeypatch) -> None:
    collide = _reload_with_env("marsdisk.physics.collide", disable_numba=False)
    C = np.array([[1.0, 2.0], [2.0, 3.0]])
    m_sub = np.array([[0.1, 0.2], [0.2, 0.4]])
    expected = float(np.sum(C[np.triu_indices(2)] * m_sub[np.triu_indices(2)]))
    got = collide.compute_prod_subblow_area_rate_C2(C, m_sub)
    assert np.isclose(got, expected)


def test_loss_sum_numba_matches_numpy(monkeypatch) -> None:
    smol = _reload_with_env("marsdisk.physics.smol", disable_numba=False)
    C = np.array([[1.0, 2.0], [4.0, 8.0]], dtype=float)
    expected = np.sum(C, axis=1)
    got = smol.loss_sum_numba(C)
    np.testing.assert_allclose(got, expected)


def test_mass_budget_error_numba_matches_python(monkeypatch) -> None:
    smol = _reload_with_env("marsdisk.physics.smol", disable_numba=False)
    N_old = np.array([1.0, 2.0], dtype=float)
    N_new = np.array([0.9, 2.2], dtype=float)
    m = np.array([0.5, 1.5], dtype=float)
    prod = 0.01
    dt = 2.0
    extra = 0.03
    expected = _mass_budget_python(N_old, N_new, m, prod, dt, extra)
    got = smol.mass_budget_error_numba(N_old, N_new, m, prod, dt, extra)
    assert np.isclose(got, expected)


def test_gain_tensor_fallback_numba_matches_einsum(monkeypatch) -> None:
    kernels = _reload_with_env("marsdisk.physics._numba_kernels", disable_numba=False)
    C = np.array([[1.0, 0.5], [0.5, 2.0]], dtype=float)
    Y = np.zeros((2, 2, 2), dtype=float)
    Y[0, 0, 0] = 0.1
    Y[0, 0, 1] = 0.2
    Y[1, 1, 1] = 0.3
    expected = 0.5 * np.einsum("ij,kij->k", C, Y)
    got = kernels.gain_tensor_fallback_numba(C, Y)
    np.testing.assert_allclose(got, expected)


def test_fragment_tensor_fallback_numba_simple_consistency(monkeypatch) -> None:
    kernels = _reload_with_env("marsdisk.physics._numba_kernels", disable_numba=False)
    sizes = np.array([1.0, 2.0], dtype=float)
    valid_pair = np.ones((2, 2), dtype=bool)
    f_lr_matrix = np.full((2, 2), 0.5, dtype=float)
    k_lr_matrix = np.zeros((2, 2), dtype=np.int64)
    alpha = 3.5
    Y_numba = kernels.fragment_tensor_fallback_numba(sizes, valid_pair, f_lr_matrix, k_lr_matrix, alpha)

    # Python reference using同一ロジック
    weights_table = np.zeros((2, 2), dtype=float)
    for k_lr in range(2):
        weights = sizes[: k_lr + 1] ** (-alpha)
        s = float(np.sum(weights))
        if s > 0.0:
            weights_table[k_lr, : k_lr + 1] = weights / s
    Y_py = np.zeros((2, 2, 2), dtype=float)
    for i in range(2):
        for j in range(2):
            if not valid_pair[i, j]:
                continue
            k_lr = int(k_lr_matrix[i, j])
            f_lr = float(f_lr_matrix[i, j])
            Y_py[k_lr, i, j] += f_lr
            rem = 1.0 - f_lr
            if rem <= 0.0:
                continue
            Y_py[: k_lr + 1, i, j] += rem * weights_table[k_lr, : k_lr + 1]

    np.testing.assert_allclose(Y_numba, Y_py)


def test_blowout_sink_vector_numba_matches_numpy(monkeypatch) -> None:
    collisions_smol = _reload_with_env("marsdisk.physics.collisions_smol", disable_numba=False)
    sizes = np.array([0.1, 1.0, 2.0], dtype=float)
    expected = np.where(sizes <= 1.0, 2.5, 0.0)
    got = collisions_smol.blowout_sink_vector_numba(sizes, 1.0, 2.5, True)
    np.testing.assert_allclose(got, expected)


def test_kernel_minimum_tcoll_numba_matches_numpy(monkeypatch) -> None:
    collisions_smol = _reload_with_env("marsdisk.physics.collisions_smol", disable_numba=False)
    C = np.array([[1.0, 0.0], [2.0, 3.0]], dtype=float)
    expected = 1.0 / np.max(np.sum(C, axis=1))
    got = collisions_smol.kernel_minimum_tcoll_numba(C)
    assert np.isclose(got, expected)


def test_supply_mass_rate_powerlaw_numba_matches_python(monkeypatch) -> None:
    collisions_smol = _reload_with_env("marsdisk.physics.collisions_smol", disable_numba=False)
    sizes = np.array([1.0, 2.0, 3.0], dtype=float)
    widths = np.array([0.5, 0.5, 0.5], dtype=float)
    masses = np.array([1.0, 2.0, 3.0], dtype=float)
    prod = 0.6
    inj_floor = 1.0
    inj_ceiling = 3.0
    q = 3.0

    # NumPy reference from powerlaw branch in supply_mass_rate_to_number_source
    left_edges = np.maximum(sizes - 0.5 * widths, 0.0)
    right_edges = left_edges + widths
    overlap_left = np.maximum(left_edges, inj_floor)
    overlap_right = np.minimum(right_edges, inj_ceiling)
    mask = overlap_right > overlap_left
    weights = np.zeros_like(sizes, dtype=float)
    if np.any(mask):
        power = 1.0 - q
        weights[mask] = (overlap_right[mask] ** power - overlap_left[mask] ** power) / power
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
    weights_sum = float(np.sum(weights))
    expected = np.zeros_like(sizes, dtype=float)
    if weights_sum > 0.0:
        mass_alloc = (weights / weights_sum) * prod
        positive = (mass_alloc > 0.0) & (masses > 0.0)
        expected[positive] = mass_alloc[positive] / masses[positive]

    got = collisions_smol.supply_mass_rate_powerlaw_numba(
        sizes.astype(np.float64),
        masses.astype(np.float64),
        widths.astype(np.float64),
        float(prod),
        float(inj_floor),
        float(inj_ceiling),
        float(q),
    )

    np.testing.assert_allclose(got, expected)
