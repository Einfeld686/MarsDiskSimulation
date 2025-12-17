"""Diagnostics for surface outflux signatures."""

from __future__ import annotations

import numpy as np

from marsdisk.physics import psd


def test_blowout_driven_wavy_pattern_emerges() -> None:
    """Efficient blow-out should imprint a wavy modulation near s_min."""

    s_min = 1.0e-6
    state_smooth = psd.update_psd_state(
        s_min=s_min,
        s_max=3.0,
        alpha=1.83,
        wavy_strength=0.0,
    )
    state_wavy = psd.update_psd_state(
        s_min=s_min,
        s_max=3.0,
        alpha=1.83,
        wavy_strength=0.3,
    )

    n_smooth = np.asarray(state_smooth["number"], dtype=float)
    n_wavy = np.asarray(state_wavy["number"], dtype=float)
    ratio = n_wavy / n_smooth

    head = ratio[:20]
    curvature = np.diff(np.sign(np.diff(head)))
    turning_points = np.count_nonzero(curvature != 0)
    assert turning_points >= 1

    amplitude = 0.5 * (np.nanmax(head) - np.nanmin(head))
    assert amplitude > 0.1
