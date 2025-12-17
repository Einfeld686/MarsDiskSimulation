import math

import numpy as np
import pytest

from marsdisk import schema
from marsdisk.physics import psd, smol


def _mass_profile(psd_state: dict) -> np.ndarray:
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
    rho = float(psd_state["rho"])
    m_bin = (4.0 / 3.0) * math.pi * rho * sizes**3
    return m_bin * number * widths


def _mass_peak(psd_state: dict) -> float:
    masses = _mass_profile(psd_state)
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    if masses.size == 0:
        return math.nan
    return float(sizes[int(np.argmax(masses))])


def test_melt_lognormal_mixture_mass_and_cut():
    melt_cfg = schema.Initial.MeltPSD(
        mode="lognormal_mixture",
        f_fine=0.25,
        s_fine=1.0e-4,
        s_meter=1.5,
        width_dex=0.3,
        s_cut_condensation=5.0e-6,
    )
    state = psd.update_psd_state(
        s_min=1.0e-7,
        s_max=3.0,
        alpha=3.5,
        wavy_strength=0.0,
        n_bins=40,
        rho=3000.0,
    )
    weights = psd.mass_weights_lognormal_mixture(
        state["sizes"],
        state["widths"],
        f_fine=melt_cfg.f_fine,
        s_fine=melt_cfg.s_fine,
        s_meter=melt_cfg.s_meter,
        width_dex=melt_cfg.width_dex,
        s_cut=melt_cfg.s_cut_condensation,
    )
    state = psd.apply_mass_weights(state, weights, rho=state["rho"])
    mass_profile = _mass_profile(state)
    expected_mass_norm = (4.0 / 3.0) * math.pi * state["rho"]
    assert np.isclose(np.sum(mass_profile), expected_mass_norm, rtol=1e-10, atol=1e-8)
    assert np.all(mass_profile[state["sizes"] < melt_cfg.s_cut_condensation] == 0.0)

    sigma_target = 12.5
    sizes_arr, widths_arr, m_k, N_k, scale = smol.psd_state_to_number_density(
        state,
        sigma_target,
        rho_fallback=state["rho"],
    )
    assert sizes_arr.size == state["sizes"].size
    assert np.isclose(np.sum(m_k * N_k), sigma_target, rtol=1e-10, atol=1e-12)
    assert scale > 0.0


def test_melt_lognormal_extremes_follow_components():
    s_fine = 1.0e-4
    s_meter = 1.5
    s_cut = 1.0e-6
    base_kwargs = dict(s_min=1.0e-7, s_max=3.0, alpha=3.5, wavy_strength=0.0, n_bins=40, rho=3000.0)

    state_fine = psd.update_psd_state(**base_kwargs)
    weights_fine = psd.mass_weights_lognormal_mixture(
        state_fine["sizes"],
        state_fine["widths"],
        f_fine=1.0,
        s_fine=s_fine,
        s_meter=s_meter,
        width_dex=0.25,
        s_cut=s_cut,
    )
    state_fine = psd.apply_mass_weights(state_fine, weights_fine, rho=state_fine["rho"])
    peak_fine = _mass_peak(state_fine)
    assert abs(math.log10(peak_fine) - math.log10(s_fine)) < 0.3

    state_meter = psd.update_psd_state(**base_kwargs)
    weights_meter = psd.mass_weights_lognormal_mixture(
        state_meter["sizes"],
        state_meter["widths"],
        f_fine=0.0,
        s_fine=s_fine,
        s_meter=s_meter,
        width_dex=0.25,
        s_cut=s_cut,
    )
    state_meter = psd.apply_mass_weights(state_meter, weights_meter, rho=state_meter["rho"])
    peak_meter = _mass_peak(state_meter)
    assert abs(math.log10(peak_meter) - math.log10(s_meter)) < 0.3
    assert peak_meter > peak_fine


def test_truncated_powerlaw_respects_bounds():
    cfg = schema.Initial.MeltPSD(
        mode="truncated_powerlaw",
        s_min_solid=1.0e-4,
        s_max_solid=1.0,
        s_cut_condensation=5.0e-5,
        alpha_solid=3.5,
    )
    state = psd.update_psd_state(
        s_min=1.0e-7,
        s_max=3.0,
        alpha=3.5,
        wavy_strength=0.0,
        n_bins=50,
        rho=3000.0,
    )
    weights = psd.mass_weights_truncated_powerlaw(
        state["sizes"],
        state["widths"],
        alpha_solid=cfg.alpha_solid,
        s_min_solid=cfg.s_min_solid,
        s_max_solid=cfg.s_max_solid,
        s_cut=cfg.s_cut_condensation,
    )
    state = psd.apply_mass_weights(state, weights, rho=state["rho"])
    mass_profile = _mass_profile(state)
    sizes = np.asarray(state["sizes"], dtype=float)
    expected_mass_norm = (4.0 / 3.0) * math.pi * state["rho"]
    assert np.isclose(np.sum(mass_profile), expected_mass_norm, rtol=1e-10, atol=1e-8)
    assert np.all(mass_profile[sizes < cfg.s_cut_condensation] == 0.0)
    assert np.all(mass_profile[sizes > cfg.s_max_solid] == 0.0)
    high_fraction = np.sum(mass_profile[sizes >= 0.3 * cfg.s_max_solid])
    assert high_fraction > 0.25
