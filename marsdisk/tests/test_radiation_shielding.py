import pytest

from marsdisk.physics import radiation, shielding


def test_blowout_radius_monotonic_T():
    rho = 3000.0
    temps = [2000.0, 2200.0, 2400.0]
    vals = [radiation.blowout_radius(rho, T) for T in temps]
    assert vals[0] < vals[1] < vals[2]


def test_clip_to_tau1_non_negative():
    kappa_eff = 10.0
    sigma = shielding.clip_to_tau1(0.2, kappa_eff)
    assert sigma == pytest.approx(0.1)
    sigma_neg = shielding.clip_to_tau1(-1e-9, kappa_eff)
    assert sigma_neg == 0.0
