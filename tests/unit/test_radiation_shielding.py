import pytest

from marsdisk.physics import radiation, shielding


radiation.load_qpr_table("data/qpr_table.csv")


def test_blowout_radius_scales_with_temperature():
    rho = 3000.0
    temps = [1500.0, 3000.0, 5000.0]
    vals = [radiation.blowout_radius(rho, T, Q_pr=1.0) for T in temps]
    assert vals[0] < vals[1] < vals[2]
    expected = vals[0] * (temps[2] / temps[0]) ** 4
    assert vals[2] == pytest.approx(expected)


def test_beta_inverse_size_scaling():
    rho = 3000.0
    T_M = 3000.0
    sizes = [1.0e-7, 2.0e-7, 4.0e-7]
    betas = [radiation.beta(s, rho, T_M, Q_pr=1.0) for s in sizes]
    assert betas[0] > betas[1] > betas[2]
    ratio = betas[0] / betas[1]
    assert ratio == pytest.approx(sizes[1] / sizes[0])


def test_beta_respects_qpr_override():
    rho = 3000.0
    T_M = 3000.0
    s = 1.0e-6
    beta_default = radiation.beta(s, rho, T_M)
    beta_high = radiation.beta(s, rho, T_M, Q_pr=1.2)
    beta_low = radiation.beta(s, rho, T_M, Q_pr=0.8)
    assert beta_high > beta_default > beta_low


def test_planck_mean_qpr_uses_table():
    s = 1.0e-6
    T = 2000.0
    table_value = radiation.qpr_lookup(s, T)
    value = radiation.planck_mean_qpr(s, T)
    assert value == pytest.approx(table_value)


def test_clip_to_tau1_non_negative():
    kappa_eff = 10.0
    sigma = shielding.clip_to_tau1(0.2, kappa_eff)
    assert sigma == pytest.approx(0.1)
    sigma_neg = shielding.clip_to_tau1(-1e-9, kappa_eff)
    assert sigma_neg == 0.0
