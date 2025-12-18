"""Regression tests for the vectorised/Numba size drift rebinning."""

from __future__ import annotations

import copy
import numpy as np
import pytest

from marsdisk.physics import psd


def _reference_apply(psd_state, *, ds_dt, dt, floor, sigma_surf):
    """Mirror the legacy loop implementation for comparison."""

    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
    number_orig = number.copy()
    edges = np.asarray(psd_state["edges"], dtype=float)

    floor_val = float(floor)
    ds_step = float(ds_dt * dt)

    new_number = np.zeros_like(number)
    accum_sizes = np.zeros_like(number)
    for idx, n_val in enumerate(number):
        if n_val <= 0.0:
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor_val:
            s_new = floor_val
        target = int(np.searchsorted(edges, s_new, side="right") - 1)
        target = max(0, min(target, new_number.size - 1))
        new_number[target] += n_val
        accum_sizes[target] += n_val * s_new

    if np.allclose(new_number, 0.0):
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}, psd_state

    new_sizes = sizes.copy()
    mask = new_number > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_number[mask]
    new_sizes = np.maximum(new_sizes, floor_val)
    tmp_state = {"sizes": new_sizes, "widths": widths, "number": new_number}
    psd.sanitize_and_normalize_number(tmp_state, normalize=False)
    new_number = np.asarray(tmp_state["number"], dtype=float)
    if not np.isfinite(new_number).all() or np.sum(new_number) == 0.0:
        psd_state["number"] = number_orig
        psd_state["n"] = number_orig
        psd.sanitize_and_normalize_number(psd_state, normalize=True)
        return (
            sigma_surf,
            0.0,
            {"ds_step": ds_step, "mass_ratio": 1.0, "sigma_before": sigma_surf, "sigma_after": sigma_surf},
            psd_state,
        )

    psd_state["number"] = new_number
    psd_state["n"] = new_number
    psd_state["sizes"] = new_sizes
    psd_state["s"] = new_sizes
    psd_state["s_min"] = float(np.min(new_sizes))
    psd_state["edges"] = edges
    psd.sanitize_and_normalize_number(psd_state)

    old_mass_weight = float(np.sum(number * (sizes**3) * widths))
    new_mass_weight = float(np.sum(new_number * (new_sizes**3) * widths))
    if old_mass_weight <= 0.0 or sigma_surf <= 0.0:
        mass_ratio = 1.0
        sigma_new = sigma_surf
        delta_sigma = 0.0
    else:
        mass_ratio = new_mass_weight / old_mass_weight if old_mass_weight else 1.0
        if not np.isfinite(mass_ratio) or mass_ratio < 0.0:
            mass_ratio = 0.0
        sigma_new = sigma_surf * mass_ratio
        delta_sigma = max(sigma_surf - sigma_new, 0.0)

    diagnostics = {
        "ds_step": ds_step,
        "mass_ratio": mass_ratio,
        "sigma_before": sigma_surf,
        "sigma_after": sigma_new,
    }
    return sigma_new, delta_sigma, diagnostics, psd_state


def _base_state():
    sizes = np.array([1.0e-6, 2.0e-6, 5.0e-6, 1.0e-5])
    widths = np.array([5.0e-7, 1.2e-6, 3.0e-6, 5.0e-6])
    edges = np.empty(sizes.size + 1)
    edges[:-1] = sizes - 0.5 * widths
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    number = np.array([2.0, 5.0, 8.0, 3.0])
    return {
        "sizes": sizes,
        "widths": widths,
        "edges": edges,
        "number": number,
        "rho": 3000.0,
    }


@pytest.mark.parametrize("ds_dt", [-2.0e-7, 1.5e-7])
def test_apply_uniform_size_drift_matches_reference(ds_dt, monkeypatch):
    sigma_surf = 5.0
    dt = 10.0
    floor = 5.0e-7

    state_ref = _base_state()
    sigma_ref, delta_ref, diag_ref, state_ref = _reference_apply(
        copy.deepcopy(state_ref), ds_dt=ds_dt, dt=dt, floor=floor, sigma_surf=sigma_surf
    )

    # Force NumPy path
    monkeypatch.setattr(psd, "_USE_NUMBA", False)
    psd._NUMBA_FAILED = False
    state_np = _base_state()
    sigma_np, delta_np, diag_np = psd.apply_uniform_size_drift(
        state_np, ds_dt=ds_dt, dt=dt, floor=floor, sigma_surf=sigma_surf
    )

    np.testing.assert_allclose(sigma_np, sigma_ref)
    np.testing.assert_allclose(delta_np, delta_ref)
    np.testing.assert_allclose(state_np["number"], state_ref["number"])
    np.testing.assert_allclose(state_np["sizes"], state_ref["sizes"])
    np.testing.assert_allclose(diag_np["mass_ratio"], diag_ref["mass_ratio"])

    # Numba path (if available)
    if psd._NUMBA_AVAILABLE:
        monkeypatch.setattr(psd, "_USE_NUMBA", True)
        psd._NUMBA_FAILED = False
        state_nb = _base_state()
        sigma_nb, delta_nb, diag_nb = psd.apply_uniform_size_drift(
            state_nb, ds_dt=ds_dt, dt=dt, floor=floor, sigma_surf=sigma_surf
        )
        np.testing.assert_allclose(sigma_nb, sigma_ref)
        np.testing.assert_allclose(delta_nb, delta_ref)
        np.testing.assert_allclose(state_nb["number"], state_ref["number"])
        np.testing.assert_allclose(state_nb["sizes"], state_ref["sizes"])
        np.testing.assert_allclose(diag_nb["mass_ratio"], diag_ref["mass_ratio"])
    else:
        assert not psd._USE_NUMBA or psd._NUMBA_DISABLED_ENV
