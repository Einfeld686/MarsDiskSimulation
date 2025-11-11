"""Tests for IMEX-BDF(1) mass conservation behaviour."""

from __future__ import annotations

import numpy as np

from marsdisk.physics import smol


def test_imex_bdf1_limits_timestep_and_preserves_mass() -> None:
    """The integrator should cap dt and keep the mass budget tight."""

    n_bins = 4
    N = np.full(n_bins, 1.0e-6)
    masses = np.logspace(-9, -6, n_bins)
    C = np.diag([0.5, 1.0, 2.0, 5.0])
    Y = np.zeros((n_bins, n_bins, n_bins))
    for i in range(n_bins):
        Y[i, i, i] = 2.0  # redistributes mass back into the source bin
    S = np.zeros(n_bins)

    dt_trial = 10.0
    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        N,
        C,
        Y,
        S,
        masses,
        prod_subblow_mass_rate=0.0,
        dt=dt_trial,
        safety=0.1,
    )

    loss = np.sum(C, axis=1)
    t_coll_min = 1.0 / np.min(loss)
    dt_cap = 0.1 * t_coll_min
    assert dt_eff <= dt_cap + 1e-12

    rel_diff = np.max(np.abs(N_new - N) / N)
    assert rel_diff < 5e-3
    assert mass_err < 5e-3
