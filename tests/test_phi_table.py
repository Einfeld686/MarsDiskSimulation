import math

import numpy as np
import pandas as pd
import pytest

from marsdisk.io import tables
from marsdisk.physics import shielding


@pytest.fixture()
def mock_phi_table(tmp_path):
    tau_values = np.array([0.0, 0.25, 0.5, 1.0, 2.0, 4.0], dtype=float)

    def phi_exact(tau: float) -> float:
        return 1.0 if tau == 0.0 else (1.0 - math.exp(-tau)) / tau

    phi_values = np.array([phi_exact(tau) for tau in tau_values], dtype=float)
    path = tmp_path / "phi_mock.csv"
    pd.DataFrame({"tau": tau_values, "phi": phi_values}).to_csv(path, index=False)
    return tables.load_phi_table(path), tau_values, phi_values


def test_phi_table_monotonic_effects(mock_phi_table):
    phi_fn, tau_grid, phi_values = mock_phi_table

    kappa_base = 5.0
    tau_samples = np.array([0.0, 0.3, 0.6, 1.5, 3.0, 6.0], dtype=float)
    kappa_eff = np.array(
        [shielding.effective_kappa(kappa_base, tau, phi_fn) for tau in tau_samples],
        dtype=float,
    )
    assert np.all(np.diff(kappa_eff) <= 1.0e-12)

    sigma_tau1 = np.array([shielding.sigma_tau1(val) for val in kappa_eff], dtype=float)
    assert np.all(np.diff(sigma_tau1) >= -1.0e-12)

    assert phi_fn(-0.5) == pytest.approx(phi_values[0])
    assert phi_fn(10.0) == pytest.approx(phi_values[-1])
    assert shielding.sigma_tau1(kappa_eff[0]) == pytest.approx(1.0 / kappa_base)

    interp_phi = np.array([phi_fn(tau) for tau in tau_grid], dtype=float)
    assert np.allclose(interp_phi, phi_values)
