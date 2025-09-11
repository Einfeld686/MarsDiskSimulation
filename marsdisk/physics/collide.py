from __future__ import annotations

"""Collision kernel and sub-blowout production rate (C1--C2)."""

import logging
from typing import Iterable

import numpy as np

from ..errors import MarsDiskError
from .dynamics import v_ij as v_ij_D1  # alias to the relative velocity (D1)

__all__ = ["compute_collision_kernel_C1", "compute_prod_subblow_area_rate_C2", "v_ij_D1"]

logger = logging.getLogger(__name__)


def compute_collision_kernel_C1(
    N: Iterable[float],
    s: Iterable[float],
    H: Iterable[float],
    v_rel: float | np.ndarray,
) -> np.ndarray:
    """Return the symmetric collision kernel :math:`C_{ij}`.

    Parameters
    ----------
    N:
        Number surface densities for each size bin.
    s:
        Characteristic sizes of the bins in metres.
    H:
        Vertical scale height of each bin in metres.
    v_rel:
        Mutual relative velocity between bins.  A scalar applies the same
        velocity to all pairs while a matrix of shape ``(n, n)`` provides
        pair-specific values.

    Returns
    -------
    numpy.ndarray
        Collision kernel matrix with shape ``(n, n)``.
    """

    N_arr = np.asarray(N, dtype=float)
    s_arr = np.asarray(s, dtype=float)
    H_arr = np.asarray(H, dtype=float)
    if N_arr.ndim != 1 or s_arr.ndim != 1 or H_arr.ndim != 1:
        raise MarsDiskError("inputs must be one-dimensional")
    if not (len(N_arr) == len(s_arr) == len(H_arr)):
        raise MarsDiskError("array lengths must match")
    if np.any(N_arr < 0.0) or np.any(s_arr <= 0.0) or np.any(H_arr <= 0.0):
        raise MarsDiskError("invalid values in N, s or H")

    n = N_arr.size
    N_outer = np.outer(N_arr, N_arr)
    s_sum = np.add.outer(s_arr, s_arr)
    H_sq = np.add.outer(H_arr * H_arr, H_arr * H_arr)
    H_ij = np.sqrt(H_sq)
    delta = np.eye(n)

    if np.isscalar(v_rel):
        v_mat = np.full((n, n), float(v_rel), dtype=float)
    else:
        v_mat = np.asarray(v_rel, dtype=float)
        if v_mat.shape != (n, n):
            raise MarsDiskError("v_rel has wrong shape")

    kernel = (
        N_outer / (1.0 + delta)
        * np.pi
        * (s_sum ** 2)
        * v_mat
        / (np.sqrt(2.0 * np.pi) * H_ij)
    )
    logger.info("compute_collision_kernel_C1: n_bins=%d", n)
    return kernel


def compute_prod_subblow_area_rate_C2(
    C: np.ndarray, m_subblow: np.ndarray
) -> float:
    """Return the production rate of sub-blowout material.

    The rate is defined as ``sum_{i<=j} C_ij * m_subblow_ij``.

    Parameters
    ----------
    C:
        Collision kernel matrix with shape ``(n, n)``.
    m_subblow:
        Matrix of sub-blowout mass generated per collision pair.

    Returns
    -------
    float
        Production rate of sub-blowout mass.
    """

    if C.shape != m_subblow.shape:
        raise MarsDiskError("shape mismatch between C and m_subblow")
    if C.ndim != 2 or C.shape[0] != C.shape[1]:
        raise MarsDiskError("C must be a square matrix")
    n = C.shape[0]
    idx = np.triu_indices(n)
    rate = float(np.sum(C[idx] * m_subblow[idx]))
    logger.info("compute_prod_subblow_area_rate_C2: rate=%e", rate)
    return rate
