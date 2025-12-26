from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import psd


def _reference_rebin_counts(
    psd_state: dict[str, np.ndarray | float],
    *,
    ds_dt: float,
    dt: float,
    floor: float,
) -> tuple[np.ndarray, np.ndarray]:
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    edges = np.asarray(psd_state["edges"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)

    counts = number * widths
    ds_step = float(ds_dt * dt)
    new_counts = np.zeros_like(counts)
    accum_sizes = np.zeros_like(number)
    for idx, count in enumerate(counts):
        if count <= 0.0 or not np.isfinite(count):
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor:
            s_new = floor
        target = int(np.searchsorted(edges, s_new, side="right") - 1)
        target = max(0, min(target, new_counts.size - 1))
        new_counts[target] += count
        accum_sizes[target] += count * s_new

    new_sizes = sizes.copy()
    mask = new_counts > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_counts[mask]
    new_sizes = np.maximum(new_sizes, float(floor))
    new_number = np.zeros_like(number)
    new_number[mask] = new_counts[mask] / widths[mask]

    tmp_state = {"sizes": new_sizes, "widths": widths, "number": new_number}
    psd.sanitize_and_normalize_number(tmp_state)
    return np.asarray(tmp_state["number"], dtype=float), np.asarray(tmp_state["sizes"], dtype=float)


def test_apply_uniform_size_drift_preserves_bin_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = np.array([1.0e-6, 2.2e-6, 4.5e-6, 9.0e-6])
    widths = np.array([0.6e-6, 1.1e-6, 2.4e-6, 5.0e-6])
    edges = np.empty(sizes.size + 1)
    edges[:-1] = sizes - 0.5 * widths
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    number = np.array([0.8, 1.6, 0.7, 0.4])
    psd_state = {
        "sizes": sizes,
        "widths": widths,
        "edges": edges,
        "number": number,
        "rho": 3000.0,
    }

    ds_dt = 1.0e-6
    dt = 1.0
    floor = 5.0e-7

    monkeypatch.setattr(psd, "_USE_NUMBA", False)
    psd._NUMBA_FAILED = False

    expected_number, expected_sizes = _reference_rebin_counts(
        psd_state, ds_dt=ds_dt, dt=dt, floor=floor
    )

    working = {k: np.array(v, copy=True) if isinstance(v, np.ndarray) else v for k, v in psd_state.items()}
    psd.apply_uniform_size_drift(working, ds_dt=ds_dt, dt=dt, floor=floor, sigma_surf=1.0)

    np.testing.assert_allclose(working["sizes"], expected_sizes, rtol=1.0e-6, atol=0.0)
    np.testing.assert_allclose(working["number"], expected_number, rtol=1.0e-6, atol=0.0)
