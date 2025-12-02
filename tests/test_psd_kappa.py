"""Sanity checks for PSD-derived mass opacity."""

from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import psd


def test_compute_kappa_single_bin_matches_geometry() -> None:
    """Single-bin opacity should follow the analytic 3/(4 rho s) scaling."""

    s = 5.0e-4
    width = 1.0e-4
    number = 2.5
    rho = 3100.0
    state = {
        "sizes": np.array([s]),
        "widths": np.array([width]),
        "number": np.array([number]),
        "rho": rho,
    }

    expected = 3.0 / (4.0 * rho * s)
    assert psd.compute_kappa(state) == pytest.approx(expected)


def test_compute_kappa_stays_finite_with_wavy_modulation() -> None:
    """Wavy PSD modulation should not produce non-physical opacity values."""

    smooth = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=3.0,
        alpha=1.83,
        wavy_strength=0.0,
    )
    wavy = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=3.0,
        alpha=1.83,
        wavy_strength=0.3,
    )

    kappa_smooth = psd.compute_kappa(smooth)
    kappa_wavy = psd.compute_kappa(wavy)

    assert np.isfinite(kappa_smooth) and kappa_smooth > 0.0
    assert np.isfinite(kappa_wavy) and kappa_wavy > 0.0
