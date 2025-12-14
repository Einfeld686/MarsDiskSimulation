import math

import numpy as np

from marsdisk.physics import shielding
from marsdisk.run import KAPPA_MIN


def test_phi_const_table_does_not_zero_opacity():
    """Φ=const テーブル適用でも κ がゼロ付近に落ちないことを確認する簡易テスト."""

    # tau=5 で κ≈2.1e-5 のケース（実走で問題化した周辺値）を想定。
    kappa_surf = 2.1e-5
    tau = 5.0
    phi_fn = shielding.load_phi_table("tables/phi_const_0p20.csv")

    kappa_eff = shielding.effective_kappa(kappa_surf, tau, phi_fn)

    # Φ=0.2 なので κ_eff は約 4.2e-6 になるはずで、極端な 1e-13 には落ちない。
    assert math.isfinite(kappa_eff)
    assert kappa_eff > 1e-7
    np.testing.assert_allclose(kappa_eff, 0.2 * kappa_surf, rtol=1e-3)


def test_phi_table_clamps_tau_but_keeps_positive_opacity():
    """テーブル範囲外の τ でも κ_eff が正のままクラップされることを確認."""

    kappa_surf = 1e-4
    tau_far_outside = 1e3  # テーブル外側にクリップされる想定
    phi_fn = shielding.load_phi_table("tables/phi_const_0p20.csv")

    kappa_eff = shielding.effective_kappa(kappa_surf, tau_far_outside, phi_fn)
    assert kappa_eff > 0.0
    np.testing.assert_allclose(kappa_eff, 0.2 * kappa_surf, rtol=1e-3)


def test_sigma_tau1_extremely_large_when_kappa_tiny():
    """κ が 1e-13 オーダーまで落ちると Σ_tau1 が 1e12 以上に跳ね上がることを明示的に再現."""

    kappa_tiny = 2.0e-13  # 実走の崩壊時に近い値
    sigma_tau1 = shielding.sigma_tau1(kappa_tiny)

    assert sigma_tau1 > 1e12
    # κ を KAPPA_MIN までクリップすれば Σ_tau1 は約 1e12 で頭打ちになることを参考値として示す
    sigma_tau1_clipped = shielding.sigma_tau1(KAPPA_MIN)
    assert sigma_tau1 >= sigma_tau1_clipped


def _make_psd_state(s_min=1e-6, s_max=3.0, n_bins=40, q=3.5, rho=3000.0):
    sizes = np.logspace(np.log10(s_min), np.log10(s_max), n_bins)
    edges = np.empty(n_bins + 1, dtype=float)
    # geometric spacing for edges
    ratio = sizes[1] / sizes[0]
    edges[1:-1] = np.sqrt(sizes[:-1] * sizes[1:])
    edges[0] = sizes[0] / ratio
    edges[-1] = sizes[-1] * ratio
    widths = np.diff(edges)
    number = sizes ** (-q)
    return {
        "sizes": sizes,
        "widths": widths,
        "number": number,
        "rho": rho,
    }


def test_kappa_within_spec_size_range_stays_far_above_floor():
    """公称サイズ範囲（1e-6–3 m）のPSDでは κ が床（1e-12）には落ちないことを確認。"""

    from marsdisk.physics import psd

    psd_state = _make_psd_state()
    kappa_val = psd.compute_kappa(psd_state)
    assert kappa_val > 1e-6  # 6桁以上の余裕で床を回避


def test_kappa_not_temperature_dependent_proxy():
    """Planck Q_pr や温度に依存しない compute_kappa が一定になることを簡易確認。"""

    from marsdisk.physics import psd

    psd_state_cold = _make_psd_state()
    psd_state_hot = _make_psd_state()
    kappa_cold = psd.compute_kappa(psd_state_cold)
    kappa_hot = psd.compute_kappa(psd_state_hot)
    np.testing.assert_allclose(kappa_cold, kappa_hot, rtol=1e-12)


def test_kappa_all_mass_in_largest_bin_still_above_floor():
    """全質量が最大径3 mに集中しても κ は 1e-12 に達しないことを確認。"""

    from marsdisk.physics import psd

    psd_state = {
        "sizes": np.array([3.0]),
        "widths": np.array([0.1]),
        "number": np.array([1.0]),
        "rho": 3000.0,
    }
    kappa_val = psd.compute_kappa(psd_state)
    assert kappa_val > 1e-5  # 大径支配でも 1e-12 には落ちない


def test_huge_sigma_tau1_from_tiny_kappa_allows_tau_to_stay_small():
    """κ が極小だと Σ_tau1 が膨張し、供給を積んでも τ が小さいままになるケースを再現。"""

    from marsdisk.physics import surface

    kappa_surf = 2.0e-13  # 実走で観測された極小値
    tau_los = kappa_surf * 1.0e6  # Σ_surf=1e6 を仮定した光学的厚さ ~2e-7
    phi_fn = shielding.load_phi_table("tables/phi_const_0p20.csv")
    kappa_eff = shielding.effective_kappa(kappa_surf, tau_los, phi_fn)
    sigma_tau1_limit = shielding.sigma_tau1(kappa_eff)

    assert sigma_tau1_limit > 1e12  # ヘッドルームが実質無限大になることを確認

    # Surface step with moderate production; sigma_tau1 が巨大なのでクリップされない
    sigma_surf = 1.0e6
    prod = 1.0e4  # kg m^-2 s^-1
    dt = 20.0
    Omega = 4.17e-4  # ~15075 s 公転を想定
    res = surface.step_surface(
        sigma_surf,
        prod,
        dt,
        Omega,
        tau=tau_los,
        sigma_tau1=sigma_tau1_limit,
        enable_blowout=False,
    )
    # 供給で表層は増えるが、tau は κ が極小なので依然として極小のまま
    tau_new = kappa_surf * res.sigma_surf
    assert res.sigma_surf > sigma_surf
    assert tau_new < 1e-3
