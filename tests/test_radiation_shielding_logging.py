import logging

import numpy as np
import pandas as pd
import pytest

from marsdisk.physics import radiation, shielding
from marsdisk.io.tables import PhiTable


@pytest.fixture()
def restore_qpr_lookup():
    original = radiation._QPR_LOOKUP
    try:
        yield
    finally:
        radiation._QPR_LOOKUP = original


def test_beta_density_validation():
    with pytest.raises(ValueError) as exc:
        radiation.beta(s=1.0e-6, rho=0.0, T_M=150.0)
    message = str(exc.value)
    assert "rho" in message
    assert "greater" in message


def test_blowout_radius_density_validation():
    with pytest.raises(ValueError) as exc:
        radiation.blowout_radius(rho=0.0, T_M=1500.0)
    assert "rho" in str(exc.value)


def test_load_phi_table_logs(tmp_path, caplog):
    tau_vals = np.array([0.0, 1.0, 2.0], dtype=float)
    phi_vals = np.array([1.0, 0.5, 0.2], dtype=float)
    table_path = tmp_path / "phi.csv"
    pd.DataFrame({"tau": tau_vals, "phi": phi_vals}).to_csv(table_path, index=False)

    with caplog.at_level(logging.INFO):
        fn = shielding.load_phi_table(table_path)
    assert callable(fn)
    assert any("Loaded Φ(τ) table" in rec.message for rec in caplog.records)


def test_apply_shielding_clamp_logs(caplog):
    tau_vals = np.array([0.1, 1.0], dtype=float)
    w0_vals = np.array([0.2, 0.8], dtype=float)
    g_vals = np.array([-0.5, 0.5], dtype=float)
    phi_vals = np.full((2, 2, 2), 0.6, dtype=float)
    phi_table = PhiTable(tau_vals=tau_vals, w0_vals=w0_vals, g_vals=g_vals, phi_vals=phi_vals)

    with caplog.at_level(logging.INFO):
        kappa_eff, sigma_tau1_limit = shielding.apply_shielding(
            kappa_surf=5.0,
            tau=2.5,
            w0=1.2,
            g=-0.9,
            interp=phi_table.interp,
        )
    assert any("Φ lookup clamped" in rec.message for rec in caplog.records)
    expected_phi = phi_table.interp(1.0, 0.8, -0.5)
    assert kappa_eff == pytest.approx(expected_phi * 5.0)
    assert sigma_tau1_limit == pytest.approx(1.0 / (expected_phi * 5.0))


def test_effective_kappa_phi_clamp_logs(caplog):
    def phi_fn(_: float) -> float:
        return 1.5

    with caplog.at_level(logging.INFO):
        result = shielding.effective_kappa(2.0, 0.1, phi_fn)
    assert result == pytest.approx(2.0)
    assert any("Clamped Φ value" in rec.message for rec in caplog.records)


def test_clip_to_tau1_logging(caplog):
    with caplog.at_level(logging.INFO):
        result = shielding.clip_to_tau1(-0.5, 0.3)
    assert result == pytest.approx(0.0)
    assert any("Clamped Σ_surf" in rec.message for rec in caplog.records)
