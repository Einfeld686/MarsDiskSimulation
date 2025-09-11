from __future__ import annotations

"""Smoluchowski coagulation/fragmentation solver (C3--C4)."""

import logging
from typing import Iterable

import numpy as np

from ..errors import MarsDiskError
from .collide import compute_collision_kernel_C1, compute_prod_subblow_area_rate_C2

__all__ = ["step_imex_bdf1_C3", "compute_mass_budget_error_C4", "compute_collision_kernel_C1", "compute_prod_subblow_area_rate_C2"]

logger = logging.getLogger(__name__)


def step_imex_bdf1_C3(
    N: Iterable[float],
    C: np.ndarray,
    Y: np.ndarray,
    S: Iterable[float],
    m: Iterable[float],
    prod_subblow_mass_rate: float,
    dt: float,
    *,
    mass_tol: float = 5e-3,
    safety: float = 0.1,
) -> tuple[np.ndarray, float, float]:
    """Advance the Smoluchowski system by one time step.

    The integration employs an IMEX-BDF(1) scheme: loss terms are treated
    implicitly while the gain terms and sink ``S`` are explicit.

    Parameters
    ----------
    N:
        Array of number surface densities for each size bin.
    C:
        Collision kernel matrix ``C_{ij}``.
    Y:
        Fragment distribution where ``Y[k, i, j]`` is the fraction of mass
        from a collision ``(i, j)`` placed into bin ``k``.
    S:
        Explicit sink term ``S_k`` for each bin.
    m:
        Particle mass associated with each bin.
    prod_subblow_mass_rate:
        Rate at which mass below the blow-out limit is produced.
    dt:
        Initial time step.
    mass_tol:
        Tolerance on the relative mass conservation error.
    safety:
        Safety factor controlling the maximum allowed step size relative to
        the minimum collision time.

    Returns
    -------
    tuple of ``(N_new, dt_eff, mass_error)``
        Updated number densities, the actual time step used and the relative
        mass conservation error as defined in (C4).
    """

    N_arr = np.asarray(N, dtype=float)
    S_arr = np.asarray(S, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if N_arr.ndim != 1 or S_arr.ndim != 1 or m_arr.ndim != 1:
        raise MarsDiskError("N, S and m must be one-dimensional")
    if not (len(N_arr) == len(S_arr) == len(m_arr)):
        raise MarsDiskError("array lengths must match")
    if C.shape != (N_arr.size, N_arr.size):
        raise MarsDiskError("C has incompatible shape")
    if Y.shape != (N_arr.size, N_arr.size, N_arr.size):
        raise MarsDiskError("Y has incompatible shape")
    if dt <= 0.0:
        raise MarsDiskError("dt must be positive")

    loss = np.sum(C, axis=1)
    t_coll = 1.0 / np.maximum(loss, 1e-30)
    dt_max = safety * float(np.min(t_coll))
    dt_eff = min(float(dt), dt_max)

    gain = 0.5 * np.einsum("ij,kij->k", C, Y)

    while True:
        N_new = (N_arr + dt_eff * (gain - S_arr)) / (1.0 + dt_eff * loss)
        if np.any(N_new < 0.0):
            dt_eff *= 0.5
            continue
        mass_err = compute_mass_budget_error_C4(
            N_arr, N_new, m_arr, prod_subblow_mass_rate, dt_eff
        )
        logger.info(
            "step_imex_bdf1_C3: dt=%e mass_err=%e", dt_eff, mass_err
        )
        if mass_err <= mass_tol:
            break
        dt_eff *= 0.5

    return N_new, dt_eff, mass_err


def compute_mass_budget_error_C4(
    N_old: Iterable[float],
    N_new: Iterable[float],
    m: Iterable[float],
    prod_subblow_mass_rate: float,
    dt: float,
) -> float:
    """Return the relative mass budget error according to (C4)."""

    N_old_arr = np.asarray(N_old, dtype=float)
    N_new_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if not (N_old_arr.shape == N_new_arr.shape == m_arr.shape):
        raise MarsDiskError("array shapes must match")
    M_before = float(np.sum(m_arr * N_old_arr))
    M_after = float(np.sum(m_arr * N_new_arr))
    if M_before <= 0.0:
        raise MarsDiskError("total mass must be positive")
    diff = M_after + dt * prod_subblow_mass_rate - M_before
    err = abs(diff) / M_before
    logger.info(
        "compute_mass_budget_error_C4: M_before=%e M_after=%e diff=%e err=%e",
        M_before,
        M_after,
        diff,
        err,
    )
    return err
