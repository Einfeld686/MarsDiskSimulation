"""Additional unit tests for numerical anomaly watchlist items."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import schema
from pydantic import ValidationError

from marsdisk.errors import MarsDiskError, PhysicsError
from marsdisk.physics import collisions_smol, psd, smol, sublimation
from marsdisk.io import tables
from marsdisk.run import load_config
from marsdisk.warnings import NumericalWarning, TableWarning

BASE_CONFIG = Path("configs/base.yml")


def test_imex_mass_error_nonfinite_raises(monkeypatch) -> None:
    def _nan_mass_error(*_args, **_kwargs) -> float:
        return float("nan")

    monkeypatch.setattr(smol, "compute_mass_budget_error_C4", _nan_mass_error)

    N = np.array([1.0, 1.0], dtype=float)
    C = np.zeros((2, 2), dtype=float)
    Y = np.zeros((2, 2, 2), dtype=float)
    S = np.zeros(2, dtype=float)
    m = np.array([1.0, 2.0], dtype=float)

    with pytest.raises(MarsDiskError):
        smol.step_imex_bdf1_C3(
            N,
            C,
            Y,
            S,
            m,
            prod_subblow_mass_rate=0.0,
            dt=1.0,
        )


def test_sizes_validation_rejects_nonpositive() -> None:
    with pytest.raises(ValidationError):
        load_config(BASE_CONFIG, overrides=["sizes.s_min=0.0"])
    with pytest.raises(ValidationError):
        load_config(BASE_CONFIG, overrides=["sizes.s_max=-1.0"])
    with pytest.raises(ValidationError):
        load_config(BASE_CONFIG, overrides=["sizes.s_min=1.0", "sizes.s_max=0.5"])


def test_psd_sanitize_reset_warns() -> None:
    psd_state = {
        "sizes": np.array([1.0e-6, 2.0e-6], dtype=float),
        "widths": np.array([1.0e-6, 1.0e-6], dtype=float),
        "number": np.array([0.0, np.nan], dtype=float),
        "rho": 3000.0,
    }
    with pytest.warns(NumericalWarning):
        psd.sanitize_and_normalize_number(psd_state, normalize=True)
    assert psd_state.get("sanitize_reset_count", 0) >= 1


def test_kernel_scale_height_warns_on_small_H_over_a(monkeypatch) -> None:
    monkeypatch.setattr(collisions_smol, "_USE_NUMBA", False, raising=False)

    dynamics_cfg = schema.Dynamics(
        e0=0.1,
        i0=0.05,
        t_damp_orbits=1.0,
        kernel_H_mode="fixed",
        H_fixed_over_a=1.0e-12,
    )
    sizes = np.array([1.0e-3, 2.0e-3], dtype=float)
    with pytest.warns(NumericalWarning):
        collisions_smol.compute_kernel_e_i_H(
            dynamics_cfg,
            tau_eff=1.0e-3,
            a_orbit_m=1.0,
            v_k=1.0,
            sizes=sizes,
        )


def test_psat_temperature_guard() -> None:
    params = sublimation.SublimationParams()
    with pytest.raises(PhysicsError):
        sublimation.p_sat_clausius(0.0, params)
    with pytest.raises(PhysicsError):
        sublimation.mass_flux_hkl(-1.0, params)


@pytest.mark.skipif(
    not getattr(tables, "_NUMBA_AVAILABLE", False),
    reason="Numba unavailable; qpr numba fallback path not applicable",
)
def test_qpr_numba_failure_falls_back(monkeypatch) -> None:
    df = pd.DataFrame(
        {
            "s": [1.0e-6, 1.0e-6, 1.0e-5, 1.0e-5],
            "T_M": [1200.0, 1300.0, 1200.0, 1300.0],
            "Q_pr": [0.1, 0.2, 0.3, 0.4],
        }
    )
    table = tables.QPrTable.from_frame(df)

    monkeypatch.setattr(tables, "_USE_NUMBA", True, raising=False)
    monkeypatch.setattr(tables, "_NUMBA_FAILED", False, raising=False)

    def _boom(*_args, **_kwargs) -> float:
        raise RuntimeError("boom")

    monkeypatch.setattr(tables, "qpr_interp_scalar_numba", _boom, raising=False)

    with pytest.warns(TableWarning):
        val = table.interp(1.0e-6, 1200.0)
    assert np.isclose(val, 0.1)
    assert tables._NUMBA_FAILED is True

    val2 = table.interp(1.0e-6, 1200.0)
    assert np.isclose(val2, 0.1)
