"""Supply mass flux → Smol number source mappingの検証。"""

from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import collisions_smol, smol


def test_supply_injected_into_first_valid_bin() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6, 3.0e-6])
    m_bin = np.array([1.0, 2.0, 3.0])
    prod_rate = 5.0
    s_min_eff = 1.5e-6

    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate, s_bin, m_bin, s_min_eff
    )

    assert np.count_nonzero(source) == 1
    assert source[1] == pytest.approx(prod_rate / m_bin[1])
    assert np.isclose(source @ m_bin, prod_rate)
    assert np.all(source >= 0.0)


def test_supply_zero_rate_returns_zero_vector() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6])
    m_bin = np.array([1.0, 2.0])

    source = collisions_smol.supply_mass_rate_to_number_source(
        0.0, s_bin, m_bin, 1.0e-6
    )

    assert np.allclose(source, 0.0)


def test_supply_injects_into_last_bin_when_floor_above_max() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6, 3.0e-6])
    m_bin = np.array([1.0, 2.0, 4.0])
    prod_rate = 1.2

    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate, s_bin, m_bin, 5.0e-6
    )

    assert np.count_nonzero(source) == 1
    assert source[-1] == pytest.approx(prod_rate / m_bin[-1])
    assert np.isclose(source @ m_bin, prod_rate)


def test_smol_source_mass_budget_matches_supply() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6, 3.0e-6])
    m_bin = np.array([1.0, 2.0, 4.0])
    prod_rate = 2.5
    dt = 1.0

    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate, s_bin, m_bin, 1.0e-6
    )
    n_bins = s_bin.size
    zeros_kernel = np.zeros((n_bins, n_bins))
    zeros_frag = np.zeros((n_bins, n_bins, n_bins))
    zeros_sink = np.zeros(n_bins)

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


def test_powerlaw_injection_distributes_mass() -> None:
    s_bin = np.array([1.0e-6, 2.0e-6, 4.0e-6])
    widths = np.array([0.5e-6, 1.0e-6, 2.0e-6])
    m_bin = np.array([1.0, 8.0, 64.0])
    prod_rate = 3.0

    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate,
        s_bin,
        m_bin,
        s_min_eff=1.0e-6,
        widths=widths,
        mode="powerlaw_bins",
        s_inj_min=1.0e-6,
        s_inj_max=4.0e-6,
        q=3.5,
    )

    assert np.count_nonzero(source) >= 2
    assert np.isclose(np.sum(source * m_bin), prod_rate)
    assert (source >= 0.0).all()
