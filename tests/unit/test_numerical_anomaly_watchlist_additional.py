"""Additional unit tests for numerical anomaly watchlist items."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import run_one_d, schema
from pydantic import ValidationError

from marsdisk.errors import MarsDiskError, PhysicsError
from marsdisk.physics import (
    collisions_smol,
    collide,
    dynamics,
    initfields,
    psd,
    smol,
    sublimation,
    supply,
    surface,
    viscosity,
)
from marsdisk import grid
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


def test_supply_powerlaw_t_before_t0_returns_zero() -> None:
    spec = schema.Supply(
        mode="powerlaw",
        powerlaw=schema.SupplyPowerLaw(A_kg_m2_s=1.0, t0_s=10.0, index=0.5),
        mixing=schema.SupplyMixing(epsilon_mix=1.0),
    )
    result = supply.evaluate_supply(
        t=0.0,
        r=1.0,
        dt=1.0,
        spec=spec,
        area=1.0,
        state=None,
        apply_reservoir=False,
    )
    assert result.rate == 0.0
    assert result.raw_rate == 0.0


@pytest.mark.parametrize(
    "temps,values",
    [
        ([1000.0, np.nan], [1.0, 2.0]),
        ([1000.0, -5.0], [1.0, 2.0]),
        ([1000.0, 1200.0], [1.0, np.nan]),
    ],
)
def test_temperature_table_rejects_invalid_values(tmp_path: Path, temps: list[float], values: list[float]) -> None:
    table_path = tmp_path / "temp_table.csv"
    df = pd.DataFrame({"T": temps, "value": values})
    df.to_csv(table_path, index=False)
    with pytest.raises(ValueError):
        supply._TemperatureTable.load(table_path, "T", "value")


def test_supply_temperature_negative_raises() -> None:
    spec = schema.Supply(
        mode="const",
        temperature=schema.SupplyTemperature(enabled=True, mode="scale"),
    )
    state = supply.init_runtime_state(spec, area=1.0)
    with pytest.raises(MarsDiskError):
        supply.evaluate_supply(
            t=0.0,
            r=1.0,
            dt=1.0,
            spec=spec,
            area=1.0,
            state=state,
            temperature_K=-1.0,
        )


def test_solve_c_eq_rejects_nan_eps() -> None:
    with pytest.raises(MarsDiskError):
        dynamics.solve_c_eq(1.0, 0.1, eps_model=lambda _c: float("nan"))


def test_collision_kernel_rejects_negative_vrel() -> None:
    N = np.array([1.0, 1.0], dtype=float)
    s = np.array([1.0e-3, 2.0e-3], dtype=float)
    H = np.array([1.0, 1.0], dtype=float)
    with pytest.raises(MarsDiskError):
        collide.compute_collision_kernel_C1(N, s, H, v_rel=-1.0)
    with pytest.raises(MarsDiskError):
        collide.compute_collision_kernel_C1(N, s, H, v_rel=float("nan"))


def test_uniform_size_drift_warns_on_all_zero_rebin() -> None:
    psd_state = {
        "sizes": np.array([1.0e-6, 2.0e-6], dtype=float),
        "widths": np.array([1.0e-6, 1.0e-6], dtype=float),
        "number": np.zeros(2, dtype=float),
        "rho": 3000.0,
    }
    with pytest.warns(NumericalWarning):
        sigma_new, delta_sigma, diag = psd.apply_uniform_size_drift(
            psd_state,
            ds_dt=-1.0e-6,
            dt=1.0,
            floor=1.0e-6,
            sigma_surf=1.0,
        )
    assert sigma_new == 1.0
    assert delta_sigma == 0.0
    assert diag.get("rebin_zeroed") is True


def test_psd_state_to_number_density_warns_on_zero_mass() -> None:
    psd_state = {
        "sizes": np.array([1.0e-6, 2.0e-6], dtype=float),
        "widths": np.array([1.0e-6, 1.0e-6], dtype=float),
        "number": np.zeros(2, dtype=float),
        "rho": 3000.0,
    }
    with pytest.warns(NumericalWarning):
        sizes, widths, masses, N_k, scale = smol.psd_state_to_number_density(psd_state, 1.0)
    assert np.allclose(N_k, 0.0)
    assert scale == 0.0


def test_sigma_from_Minner_rejects_singular() -> None:
    with pytest.raises(PhysicsError):
        initfields.sigma_from_Minner(1.0, 1.0, 1.0 + 1.0e-15, 2.0)


def test_orbital_frequency_rejects_nonpositive_r() -> None:
    with pytest.raises(ValueError):
        grid.omega_kepler(0.0)
    with pytest.raises(ValueError):
        grid.v_kepler(-1.0)


def test_tridiagonal_solver_rejects_zero_diag() -> None:
    a = np.array([1.0], dtype=float)
    b = np.array([0.0, 1.0], dtype=float)
    c = np.array([1.0], dtype=float)
    d = np.array([1.0, 1.0], dtype=float)
    with pytest.raises(MarsDiskError):
        viscosity._solve_tridiagonal(a, b, c, d)


def test_safe_tcoll_rejects_nan_tau() -> None:
    with pytest.raises(MarsDiskError):
        surface._safe_tcoll(1.0, float("nan"))


def test_supply_table_rejects_missing_grid(tmp_path: Path) -> None:
    table_path = tmp_path / "supply_grid.csv"
    df = pd.DataFrame(
        {
            "t": [0.0, 0.0, 1.0],
            "r": [1.0, 2.0, 1.0],
            "rate": [1.0, 2.0, 3.0],
        }
    )
    df.to_csv(table_path, index=False)
    with pytest.raises(ValueError):
        supply._TableData.load(table_path)


def test_phi_table_rejects_incomplete_grid() -> None:
    df = pd.DataFrame(
        {
            "tau": [0.1, 0.1, 0.2, 0.2],
            "w0": [0.5, 0.7, 0.5, 0.7],
            "g": [0.2, 0.2, 0.2, 0.3],
            "Phi": [0.9, 0.8, 0.85, 0.75],
        }
    )
    with pytest.raises(ValueError):
        tables.PhiTable.from_frame(df)


def test_dynamics_rejects_invalid_e0_i0() -> None:
    with pytest.raises(ValidationError):
        schema.Dynamics(e0=1.0, i0=0.1, t_damp_orbits=1.0)
    with pytest.raises(ValidationError):
        schema.Dynamics(e0=-0.1, i0=0.1, t_damp_orbits=1.0)
    with pytest.raises(ValidationError):
        schema.Dynamics(e0=0.1, i0=-0.1, t_damp_orbits=1.0)


def test_evolve_min_size_requires_temperature() -> None:
    params = sublimation.SublimationParams()
    s_prev = 1.0e-6
    s_new = psd.evolve_min_size(
        s_prev,
        dt=1.0,
        model="sublimation_min",
        rho=3000.0,
        sublimation_params=params,
    )
    assert s_new == s_prev


def test_clamp_sigma_surf_returns_zero_for_invalid() -> None:
    assert run_one_d._clamp_sigma_surf(-1.0) == 0.0
    assert run_one_d._clamp_sigma_surf(float("nan")) == 0.0
