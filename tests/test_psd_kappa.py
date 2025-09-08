"""Tests for PSD opacity and wavy correction."""
from __future__ import annotations

import numpy as np

from marsdisk.physics.psd import compute_kappa, update_psd_state


def test_kappa_decreases_with_smin() -> None:
    """Opacity should decrease when the minimum size increases."""
    state_small = update_psd_state(
        s_min=1e-6, s_max=3.0, alpha=1.83, wavy_strength=0.0
    )
    state_large = update_psd_state(
        s_min=1e-4, s_max=3.0, alpha=1.83, wavy_strength=0.0
    )
    kappa_small = compute_kappa(state_small)
    kappa_large = compute_kappa(state_large)
    assert kappa_small > kappa_large


def test_wavy_correction_creates_oscillation() -> None:
    """Non-zero ``wavy_strength`` should introduce oscillations in ``n``."""
    state_wavy = update_psd_state(
        s_min=1e-6, s_max=3.0, alpha=1.83, wavy_strength=0.3
    )
    n = state_wavy["number"]
    diffs = np.diff(n)
    sign_changes = np.sum(np.diff(np.sign(diffs)) != 0)
    assert sign_changes > 0
