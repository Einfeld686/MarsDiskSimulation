"""Targeted checks for Smol mass/width/dt consistency concerns."""

from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import collisions_smol, fragments, qstar, smol


def test_fragment_tensor_weights_include_widths(monkeypatch) -> None:
    monkeypatch.setattr(collisions_smol, "_USE_NUMBA", False, raising=False)
    sizes = np.array([1.0e-6, 2.0e-6, 5.0e-6], dtype=float)
    widths = np.array([0.4e-6, 0.9e-6, 2.2e-6], dtype=float)
    edges = np.empty(sizes.size + 1, dtype=float)
    edges[:-1] = np.maximum(sizes - 0.5 * widths, 0.0)
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    rho = 3000.0
    masses = (4.0 / 3.0) * np.pi * rho * sizes**3
    v_rel = 1.0e6  # m/s, force catastrophic fragmentation (f_lr -> 0)

    v_matrix = np.full((sizes.size, sizes.size), v_rel, dtype=float)
    size_ref = np.maximum.outer(sizes, sizes)
    q_star = qstar.compute_q_d_star_array(size_ref, rho, v_matrix / 1.0e3)
    q_r = fragments.q_r_array(masses[:, None], masses[None, :], v_matrix)
    f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)
    assert float(np.max(f_lr)) < 1.0e-6

    Y = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel, rho, alpha_frag=3.5, use_numba=False
    )

    i, j = 0, 2
    m_tot = masses[i] + masses[j]
    f_lr_val = float(f_lr[i, j])
    s_lr = (3.0 * f_lr_val * m_tot / (4.0 * np.pi * rho)) ** (1.0 / 3.0)
    k_lr = int(np.searchsorted(edges, s_lr, side="right") - 1)
    k_lr = max(0, min(k_lr, sizes.size - 1))
    left = np.maximum(edges[: k_lr + 1], 1.0e-30)
    right = np.maximum(edges[1 : k_lr + 2], left)
    power = 1.0 - 3.5
    weights = (right**power - left**power) / power
    weights /= weights.sum()
    np.testing.assert_allclose(Y[: k_lr + 1, i, j], weights, rtol=1.0e-6, atol=1.0e-12)
    np.testing.assert_allclose(Y[k_lr + 1 :, i, j], 0.0, atol=1.0e-12)


def test_dt_eff_balance_matches_mass_rates() -> None:
    N = np.array([1.0], dtype=float)
    m = np.array([1.0], dtype=float)
    C = np.array([[0.5]], dtype=float)
    Y = np.zeros((1, 1, 1), dtype=float)
    Y[0, 0, 0] = 1.0
    S = np.zeros(1, dtype=float)
    diag = {}

    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        N,
        C,
        Y,
        S,
        m,
        prod_subblow_mass_rate=0.0,
        dt=10.0,
        safety=0.1,
        diag_out=diag,
    )

    assert dt_eff < 10.0
    M_before = float(np.sum(m * N))
    M_after = float(np.sum(m * N_new))
    net_rate = (
        diag["gain_mass_rate"]
        + diag["source_mass_rate"]
        - diag["loss_mass_rate"]
        - diag["sink_mass_rate"]
    )
    assert np.isclose(M_after - M_before, net_rate * dt_eff, rtol=1.0e-10, atol=1.0e-12)
    assert mass_err < 1.0e-10


def test_source_mass_budget_no_double_count() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6, 3.0e-6])
    m_bin = np.array([1.0, 2.0, 4.0])
    prod_rate = 2.5
    dt = 1.0
    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate, s_bin, m_bin, 1.0e-6
    )

    zeros_kernel = np.zeros((s_bin.size, s_bin.size))
    zeros_frag = np.zeros((s_bin.size, s_bin.size, s_bin.size))
    zeros_sink = np.zeros(s_bin.size)

    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        np.zeros_like(s_bin),
        zeros_kernel,
        zeros_frag,
        zeros_sink,
        m_bin,
        prod_subblow_mass_rate=prod_rate,
        dt=dt,
        source_k=source,
        extra_mass_loss_rate=0.0,
    )
    assert dt_eff == pytest.approx(dt)
    assert mass_err == pytest.approx(0.0)
    assert np.isclose(np.sum(m_bin * N_new), prod_rate * dt_eff)

    N_new2, dt_eff2, mass_err2 = smol.step_imex_bdf1_C3(
        np.zeros_like(s_bin),
        zeros_kernel,
        zeros_frag,
        zeros_sink,
        m_bin,
        prod_subblow_mass_rate=None,
        dt=dt,
        source_k=source,
        extra_mass_loss_rate=0.0,
    )
    assert dt_eff2 == pytest.approx(dt)
    assert mass_err2 == pytest.approx(0.0)
    assert np.isclose(np.sum(m_bin * N_new2), prod_rate * dt_eff2)
