import math

import pandas as pd
import pytest

from marsdisk.io import tables
from marsdisk.physics import shielding


def _phi_exact(tau: float) -> float:
    if tau == 0.0:
        return 1.0
    return (1.0 - math.exp(-tau)) / tau


def test_phi_table_interpolation_and_effect(tmp_path):
    path = tmp_path / "phi_mock.csv"
    tau_values = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
    phi_values = [_phi_exact(tau) for tau in tau_values]
    pd.DataFrame({"tau": tau_values, "phi": phi_values}).to_csv(path, index=False)

    phi_fn = tables.load_phi_table(path)

    kappa_base = 5.0
    tau_samples = [0.0, 0.3, 0.6, 1.5, 3.0, 6.0]
    kappa_eff_values = [shielding.effective_kappa(kappa_base, tau, phi_fn) for tau in tau_samples]

    for left, right in zip(kappa_eff_values, kappa_eff_values[1:]):
        assert left >= right - 1.0e-12

    sigma_tau1_values = [shielding.sigma_tau1(val) for val in kappa_eff_values]
    for left, right in zip(sigma_tau1_values, sigma_tau1_values[1:]):
        assert left <= right + 1.0e-12

    assert phi_fn(-0.5) == pytest.approx(phi_values[0])
    assert phi_fn(10.0) == pytest.approx(phi_values[-1])
    assert shielding.sigma_tau1(kappa_eff_values[0]) == pytest.approx(1.0 / kappa_base)
