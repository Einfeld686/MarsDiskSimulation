"""昇華専用Smolステップが表層のds/dtドリフトと整合することを検証する。"""

import copy

import numpy as np
import pytest

from marsdisk.physics import psd, smol, sublimation


def test_smol_sublimation_matches_surface_drift() -> None:
    """ヘルパー経由の昇華Smolが旧来の手動変換と一致することを確認する。"""

    psd_state_base = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=1.0e-3,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=8,
        rho=3000.0,
    )
    sigma_surf = 2.0  # kg/m^2
    ds_dt = -5.0e-10  # m/s
    dt = 10.0  # s

    sizes_manual = np.asarray(psd_state_base["sizes"], dtype=float)
    widths_manual = np.asarray(psd_state_base["widths"], dtype=float)
    number_manual = np.asarray(psd_state_base["number"], dtype=float)
    rho_manual = float(psd_state_base["rho"])
    base_counts_manual = number_manual * widths_manual
    m_manual = (4.0 / 3.0) * np.pi * rho_manual * sizes_manual**3
    mass_density_raw = float(np.sum(m_manual * base_counts_manual))
    scale_manual = sigma_surf / mass_density_raw if mass_density_raw > 0.0 else 0.0
    N_manual = base_counts_manual * scale_manual if scale_manual > 0.0 else np.zeros_like(base_counts_manual)
    ds_dt_k = np.full_like(sizes_manual, ds_dt, dtype=float)
    S_sub_manual, mass_loss_rate_manual = sublimation.sublimation_sink_from_dsdt(
        sizes_manual,
        N_manual,
        ds_dt_k,
        m_manual,
    )
    zeros_kernel = np.zeros((sizes_manual.size, sizes_manual.size))
    zeros_frag = np.zeros((sizes_manual.size, sizes_manual.size, sizes_manual.size))
    N_new_manual, dt_eff_manual, mass_err_manual = smol.step_imex_bdf1_C3(
        N_manual,
        zeros_kernel,
        zeros_frag,
        np.zeros_like(N_manual),
        m_manual,
        prod_subblow_mass_rate=0.0,
        dt=dt,
        S_external_k=None,
        S_sublimation_k=S_sub_manual,
        extra_mass_loss_rate=mass_loss_rate_manual,
    )
    sigma_after_manual = float(np.sum(m_manual * N_new_manual))
    sigma_loss_manual = max(sigma_surf - sigma_after_manual, 0.0)

    sizes, widths, m_k, N_k, scale = smol.psd_state_to_number_density(
        copy.deepcopy(psd_state_base),
        sigma_surf,
        rho_fallback=psd_state_base.get("rho"),
    )
    ds_dt_k = np.full_like(sizes, ds_dt, dtype=float)
    S_sub_k, mass_loss_rate = sublimation.sublimation_sink_from_dsdt(
        sizes,
        N_k,
        ds_dt_k,
        m_k,
    )

    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        N_k,
        zeros_kernel,
        zeros_frag,
        np.zeros_like(N_k),
        m_k,
        prod_subblow_mass_rate=0.0,
        dt=dt,
        S_external_k=None,
        S_sublimation_k=S_sub_k,
        extra_mass_loss_rate=mass_loss_rate,
    )
    _psd_after, _sigma_after_smol, sigma_loss_smol = smol.number_density_to_psd_state(
        N_new,
        copy.deepcopy(psd_state_base),
        sigma_surf,
        widths=widths,
        m=m_k,
        scale_to_sigma=scale,
    )

    assert dt_eff == pytest.approx(dt_eff_manual)
    assert mass_err == pytest.approx(mass_err_manual)
    assert mass_loss_rate == pytest.approx(mass_loss_rate_manual)
    assert sigma_loss_smol == pytest.approx(sigma_loss_manual)
    assert np.allclose(N_manual, N_k)
