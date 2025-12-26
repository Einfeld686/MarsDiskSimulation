"""Numba カーネルとフォールバック経路の一致性を確認するユニットテスト。"""

from __future__ import annotations

import importlib
import os
from typing import Iterable

import numpy as np
import pytest

from marsdisk import constants, grid, schema


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
    m = np.array([1.0, 3.0], dtype=float)
    m_sum = m[:, None] + m[None, :]
    weighted = np.triu(C * m_sum)
    expected = np.einsum("ij,kij->k", weighted, Y)
    expected = np.where(m > 0.0, expected / m, 0.0)
    got = kernels.gain_tensor_fallback_numba(C, Y, m)
    np.testing.assert_allclose(got, expected)


def test_fragment_tensor_fallback_numba_simple_consistency(monkeypatch) -> None:
    kernels = _reload_with_env("marsdisk.physics._numba_kernels", disable_numba=False)
    sizes = np.array([1.0, 2.0], dtype=float)
    widths = np.array([0.5, 1.5], dtype=float)
    edges = np.empty(sizes.size + 1, dtype=float)
    edges[:-1] = np.maximum(sizes - 0.5 * widths, 0.0)
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    valid_pair = np.ones((2, 2), dtype=bool)
    f_lr_matrix = np.full((2, 2), 0.5, dtype=float)
    k_lr_matrix = np.zeros((2, 2), dtype=np.int64)
    alpha = 3.5
    Y_numba = kernels.fragment_tensor_fallback_numba(
        edges, valid_pair, f_lr_matrix, k_lr_matrix, alpha
    )

    # Python reference using同一ロジック
    weights_table = np.zeros((2, 2), dtype=float)
    for k_lr in range(2):
        left = np.maximum(edges[: k_lr + 1], 1.0e-30)
        right = np.maximum(edges[1 : k_lr + 2], left)
        power = 1.0 - alpha
        if abs(power) < 1.0e-12:
            weights = np.log(right / left)
        else:
            weights = (right**power - left**power) / power
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
    monkeypatch.setattr(collisions_smol, "_USE_NUMBA", False, raising=False)
    collisions_smol._NUMBA_FAILED = False
    expected = collisions_smol.supply_mass_rate_to_number_source(
        prod,
        sizes,
        masses,
        s_min_eff=0.0,
        widths=widths,
        mode="powerlaw_bins",
        s_inj_min=inj_floor,
        s_inj_max=inj_ceiling,
        q=q,
    )

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


def test_compute_kernel_e_i_H_numba_matches_python(monkeypatch) -> None:
    collisions_smol = _reload_with_env("marsdisk.physics.collisions_smol", disable_numba=False)
    dyn = schema.Dynamics(
        e0=2.0e-4,
        i0=1.0e-4,
        t_damp_orbits=1.0e3,
        f_wake=1.0,
        kernel_ei_mode="wyatt_eq",
        kernel_H_mode="ia",
        H_factor=0.1,
    )
    r = constants.R_MARS
    Omega = grid.omega_kepler(r)
    v_k = r * Omega
    sizes = np.array([1.0e-6, 2.0e-6], dtype=float)

    monkeypatch.setattr(collisions_smol, "_NUMBA_FAILED", False, raising=False)
    e_numba, i_numba, H_numba = collisions_smol.compute_kernel_e_i_H(
        dyn,
        tau_eff=1.0e-3,
        a_orbit_m=r,
        v_k=v_k,
        sizes=sizes,
    )

    monkeypatch.setattr(collisions_smol, "_NUMBA_FAILED", True, raising=False)
    e_py, i_py, H_py = collisions_smol.compute_kernel_e_i_H(
        dyn,
        tau_eff=1.0e-3,
        a_orbit_m=r,
        v_k=v_k,
        sizes=sizes,
    )

    np.testing.assert_allclose(e_numba, e_py)
    np.testing.assert_allclose(i_numba, i_py)
    np.testing.assert_allclose(H_numba, H_py)


def test_qpr_interp_scalar_numba_matches_numpy(monkeypatch) -> None:
    tables = _reload_with_env("marsdisk.io.tables", disable_numba=False)
    numba_tables = _reload_with_env("marsdisk.io._numba_tables", disable_numba=False)
    if not numba_tables.NUMBA_AVAILABLE():
        pytest.skip("Numba unavailable; qpr interp numba path not applicable")

    s_vals = np.array([1.0, 2.0], dtype=float)
    T_vals = np.array([100.0, 200.0], dtype=float)
    q_vals = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=float)
    s = 1.5
    T = 150.0

    table = tables.QPrTable(s_vals, T_vals, q_vals)
    monkeypatch.setattr(tables, "_USE_NUMBA", False, raising=False)
    monkeypatch.setattr(tables, "_NUMBA_FAILED", False, raising=False)
    expected = table.interp(s, T)
    got = numba_tables.qpr_interp_scalar_numba(s_vals, T_vals, q_vals, s, T)
    assert np.isclose(got, expected)


def test_qpr_interp_array_numba_matches_numpy(monkeypatch) -> None:
    numba_tables = _reload_with_env("marsdisk.io._numba_tables", disable_numba=False)
    if not numba_tables.NUMBA_AVAILABLE():
        pytest.skip("Numba unavailable; qpr interp numba path not applicable")

    s_vals = np.array([1.0, 2.0, 4.0], dtype=float)
    T_vals = np.array([100.0, 200.0], dtype=float)
    q_vals = np.array(
        [
            [0.1, 0.2, 0.4],
            [0.3, 0.5, 0.8],
        ],
        dtype=float,
    )
    s_arr = np.array([1.2, 1.8, 3.1], dtype=float)
    T = 150.0

    i = np.clip(np.searchsorted(s_vals, s_arr) - 1, 0, len(s_vals) - 2)
    j = int(np.clip(np.searchsorted(T_vals, T) - 1, 0, len(T_vals) - 2))
    s1 = s_vals[i]
    s2 = s_vals[i + 1]
    T1 = T_vals[j]
    T2 = T_vals[j + 1]
    q11 = q_vals[j, i]
    q12 = q_vals[j + 1, i]
    q21 = q_vals[j, i + 1]
    q22 = q_vals[j + 1, i + 1]
    ws = np.where(s2 == s1, 0.0, (s_arr - s1) / (s2 - s1))
    wT = 0.0 if T2 == T1 else (T - T1) / (T2 - T1)
    q1 = q11 * (1.0 - ws) + q21 * ws
    q2 = q12 * (1.0 - ws) + q22 * ws
    expected = q1 * (1.0 - wT) + q2 * wT

    got = numba_tables.qpr_interp_array_numba(s_vals, T_vals, q_vals, s_arr, T)
    np.testing.assert_allclose(got, expected)


def test_qpr_interp_numba_fallback(monkeypatch) -> None:
    tables = _reload_with_env("marsdisk.io.tables", disable_numba=False)
    numba_tables = _reload_with_env("marsdisk.io._numba_tables", disable_numba=False)
    if not numba_tables.NUMBA_AVAILABLE():
        pytest.skip("Numba unavailable; qpr interp numba path not applicable")

    s_vals = np.array([1.0, 2.0], dtype=float)
    T_vals = np.array([100.0, 200.0], dtype=float)
    q_vals = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=float)
    table = tables.QPrTable(s_vals, T_vals, q_vals)
    s = 1.25
    T = 175.0

    monkeypatch.setattr(tables, "_USE_NUMBA", False, raising=False)
    monkeypatch.setattr(tables, "_NUMBA_FAILED", False, raising=False)
    expected = table.interp(s, T)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(tables, "_USE_NUMBA", True, raising=False)
    monkeypatch.setattr(tables, "_NUMBA_FAILED", False, raising=False)
    monkeypatch.setattr(tables, "qpr_interp_scalar_numba", _boom, raising=False)

    got = table.interp(s, T)
    assert np.isclose(got, expected)
    assert tables._NUMBA_FAILED is True


def test_blowout_radius_numba_matches_numpy(monkeypatch) -> None:
    radiation_numba = _reload_with_env("marsdisk.physics._numba_radiation", disable_numba=False)
    if not radiation_numba.NUMBA_AVAILABLE():
        pytest.skip("Numba unavailable; blowout radius numba path not applicable")

    rho = 2500.0
    T = 2000.0
    qpr = 1.1
    expected = (
        3.0 * constants.SIGMA_SB * (T**4) * (constants.R_MARS**2) * qpr
        / (2.0 * constants.G * constants.M_MARS * constants.C * rho)
    )
    got = radiation_numba.blowout_radius_numba(rho, T, qpr)
    assert np.isclose(got, expected)


def test_blowout_radius_numba_fallback(monkeypatch) -> None:
    radiation = _reload_with_env("marsdisk.physics.radiation", disable_numba=False)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(radiation, "_USE_NUMBA_RADIATION", True, raising=False)
    monkeypatch.setattr(radiation, "_NUMBA_FAILED", False, raising=False)
    monkeypatch.setattr(radiation, "blowout_radius_numba", _boom, raising=False)

    rho = 2500.0
    T = 2000.0
    qpr = 1.1
    expected = (
        3.0 * constants.SIGMA_SB * (T**4) * (constants.R_MARS**2) * qpr
        / (2.0 * constants.G * constants.M_MARS * constants.C * rho)
    )
    got = radiation.blowout_radius(rho, T, Q_pr=qpr)
    assert np.isclose(got, expected)
    assert radiation._NUMBA_FAILED is True


def test_blowout_radius_numba_env_disabled(monkeypatch) -> None:
    radiation = _reload_with_env("marsdisk.physics.radiation", disable_numba=True)
    assert radiation._USE_NUMBA_RADIATION is False

    rho = 2500.0
    T = 2000.0
    qpr = 1.1
    expected = (
        3.0 * constants.SIGMA_SB * (T**4) * (constants.R_MARS**2) * qpr
        / (2.0 * constants.G * constants.M_MARS * constants.C * rho)
    )
    got = radiation.blowout_radius(rho, T, Q_pr=qpr)
    assert np.isclose(got, expected)
