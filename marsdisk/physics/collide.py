from __future__ import annotations

"""Collision kernel and sub-blowout production rate (C1--C2)."""

import os
import logging
import warnings
from typing import Iterable

import numpy as np

from ..errors import MarsDiskError
from ..warnings import NumericalWarning
from .dynamics import v_ij as v_ij_D1  # alias to the relative velocity (D1)
try:
    from ._numba_kernels import (
        NUMBA_AVAILABLE,
        collision_kernel_bookkeeping_numba,
        collision_kernel_numba,
        compute_prod_subblow_area_rate_C2_numba,
    )

    _NUMBA_AVAILABLE = NUMBA_AVAILABLE()
except ImportError:  # pragma: no cover - optional dependency
    _NUMBA_AVAILABLE = False

_NUMBA_DISABLED_ENV = os.environ.get("MARSDISK_DISABLE_NUMBA", "").lower() in {"1", "true", "yes", "on"}
_USE_NUMBA = _NUMBA_AVAILABLE and not _NUMBA_DISABLED_ENV
_NUMBA_FAILED = False

__all__ = ["compute_collision_kernel_C1", "compute_prod_subblow_area_rate_C2", "v_ij_D1"]
__all__ += ["compute_collision_kernel_bookkeeping"]

logger = logging.getLogger(__name__)


def compute_collision_kernel_C1(
    N: Iterable[float],
    s: Iterable[float],
    H: Iterable[float],
    v_rel: float | np.ndarray,
    *,
    use_numba: bool | None = None,
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

    global _NUMBA_FAILED

    N_arr = np.asarray(N, dtype=np.float64)
    s_arr = np.asarray(s, dtype=np.float64)
    H_arr = np.asarray(H, dtype=np.float64)
    if N_arr.ndim != 1 or s_arr.ndim != 1 or H_arr.ndim != 1:
        raise MarsDiskError("inputs must be one-dimensional")
    if not (len(N_arr) == len(s_arr) == len(H_arr)):
        raise MarsDiskError("array lengths must match")
    if np.any(N_arr < 0.0) or np.any(s_arr <= 0.0) or np.any(H_arr <= 0.0):
        raise MarsDiskError("invalid values in N, s or H")

    n = N_arr.size
    use_matrix_velocity = False
    if np.isscalar(v_rel):
        v_scalar = float(v_rel)
        v_mat = np.zeros((n, n), dtype=np.float64)
    else:
        v_mat = np.asarray(v_rel, dtype=np.float64)
        if v_mat.shape != (n, n):
            raise MarsDiskError("v_rel has wrong shape")
        use_matrix_velocity = True
        v_scalar = 0.0

    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    kernel: np.ndarray | None = None
    if use_jit:
        try:
            kernel = collision_kernel_numba(
                N_arr, s_arr, H_arr, float(v_scalar), v_mat, bool(use_matrix_velocity)
            )
        except Exception as exc:  # pragma: no cover - fallback path
            _NUMBA_FAILED = True
            kernel = None
            warnings.warn(
                f"compute_collision_kernel_C1: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )

    if kernel is None:
        v_mat_full = np.full((n, n), float(v_scalar), dtype=np.float64) if not use_matrix_velocity else v_mat
        N_outer = np.outer(N_arr, N_arr)
        s_sum = np.add.outer(s_arr, s_arr)
        H_sq = np.add.outer(H_arr * H_arr, H_arr * H_arr)
        H_ij = np.sqrt(H_sq)
        delta = np.eye(n)
        kernel = (
            N_outer / (1.0 + delta)
            * np.pi
            * (s_sum ** 2)
            * v_mat_full
            / (np.sqrt(2.0 * np.pi) * H_ij)
        )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_collision_kernel_C1: n_bins=%d use_numba=%s", n, use_jit)
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

    global _NUMBA_FAILED
    if C.shape != m_subblow.shape:
        raise MarsDiskError("shape mismatch between C and m_subblow")
    if C.ndim != 2 or C.shape[0] != C.shape[1]:
        raise MarsDiskError("C must be a square matrix")
    n = C.shape[0]
    use_jit = _USE_NUMBA and not _NUMBA_FAILED
    if use_jit:
        try:
            rate = float(compute_prod_subblow_area_rate_C2_numba(np.asarray(C, dtype=np.float64), np.asarray(m_subblow, dtype=np.float64)))
        except Exception:  # pragma: no cover - exercised by fallback
            use_jit = False
            _NUMBA_FAILED = True
            warnings.warn("compute_prod_subblow_area_rate_C2: numba kernel failed; falling back to NumPy.", NumericalWarning)
    if not use_jit:
        idx = np.triu_indices(n)
        rate = float(np.sum(C[idx] * m_subblow[idx]))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_prod_subblow_area_rate_C2: rate=%e", rate)
    return rate


def compute_collision_kernel_bookkeeping(
    N: Iterable[float],
    s: Iterable[float],
    H: Iterable[float],
    m: Iterable[float],
    v_rel: float | np.ndarray,
    f_ke_matrix: np.ndarray,
    F_lf_matrix: np.ndarray,
    *,
    use_numba: bool | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return collision kernel with energy bookkeeping statistics.

    Parameters mirror :func:`compute_collision_kernel_C1` with additional
    per-bin masses ``m`` and matrices ``f_ke_matrix`` / ``F_lf_matrix``.
    Statistics vector layout:
    ``(E_rel_step, E_dissipated_step, E_retained_step,
       f_ke_mean_C, f_ke_energy, F_lf_mean,
       n_cratering_rate, n_fragmentation_rate,
       frac_cratering, frac_fragmentation)``.
    """

    global _NUMBA_FAILED

    N_arr = np.asarray(N, dtype=np.float64)
    s_arr = np.asarray(s, dtype=np.float64)
    H_arr = np.asarray(H, dtype=np.float64)
    m_arr = np.asarray(m, dtype=np.float64)
    f_ke_arr = np.asarray(f_ke_matrix, dtype=np.float64)
    F_lf_arr = np.asarray(F_lf_matrix, dtype=np.float64)

    if N_arr.ndim != 1 or s_arr.ndim != 1 or H_arr.ndim != 1 or m_arr.ndim != 1:
        raise MarsDiskError("inputs N, s, H, m must be one-dimensional")
    if not (len(N_arr) == len(s_arr) == len(H_arr) == len(m_arr)):
        raise MarsDiskError("N, s, H, m lengths must match")
    if np.any(N_arr < 0.0) or np.any(s_arr <= 0.0) or np.any(H_arr <= 0.0) or np.any(m_arr <= 0.0):
        raise MarsDiskError("invalid values in N, s, H or m")

    n = N_arr.size
    use_matrix_velocity = False
    if np.isscalar(v_rel):
        v_scalar = float(v_rel)
        v_mat = np.zeros((n, n), dtype=np.float64)
    else:
        v_mat = np.asarray(v_rel, dtype=np.float64)
        if v_mat.shape != (n, n):
            raise MarsDiskError("v_rel has wrong shape")
        use_matrix_velocity = True
        v_scalar = 0.0

    if f_ke_arr.shape != (n, n) or F_lf_arr.shape != (n, n):
        raise MarsDiskError("f_ke_matrix and F_lf_matrix must be (n, n)")

    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    kernel: np.ndarray | None = None
    stats: np.ndarray | None = None
    if use_jit:
        try:
            kernel, stats = collision_kernel_bookkeeping_numba(
                N_arr,
                s_arr,
                H_arr,
                m_arr,
                float(v_scalar),
                v_mat,
                bool(use_matrix_velocity),
                f_ke_arr,
                F_lf_arr,
            )
        except Exception as exc:  # pragma: no cover - fallback path
            _NUMBA_FAILED = True
            kernel = None
            stats = None
            warnings.warn(
                f"compute_collision_kernel_bookkeeping: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )

    if kernel is None or stats is None:
        v_mat_full = np.full((n, n), float(v_scalar), dtype=np.float64) if not use_matrix_velocity else v_mat
        N_outer = np.outer(N_arr, N_arr)
        s_sum = np.add.outer(s_arr, s_arr)
        H_sq = np.add.outer(H_arr * H_arr, H_arr * H_arr)
        H_ij = np.sqrt(H_sq)
        delta = np.eye(n)
        kernel = (
            N_outer / (1.0 + delta)
            * np.pi
            * (s_sum ** 2)
            * v_mat_full
            / (np.sqrt(2.0 * np.pi) * H_ij)
        )

        idx = np.triu_indices(n)
        C_triu = kernel[idx]
        sum_C = float(np.sum(C_triu))
        v_vals = v_mat_full[idx]
        m_i = m_arr[idx[0]]
        m_j = m_arr[idx[1]]
        m_tot = m_i + m_j
        with np.errstate(divide="ignore", invalid="ignore"):
            mu = np.where(m_tot > 0.0, m_i * m_j / m_tot, 0.0)
        E_rel = 0.5 * mu * v_vals * v_vals

        f_ke = f_ke_arr[idx]
        F_lf = F_lf_arr[idx]

        E_rel_step = float(np.sum(C_triu * E_rel))
        E_ret_step = float(np.sum(C_triu * f_ke * E_rel))
        E_diss_step = E_rel_step - E_ret_step

        f_ke_mean_C = float(np.sum(C_triu * f_ke) / sum_C) if sum_C > 0.0 else 0.0
        f_ke_energy = E_ret_step / E_rel_step if E_rel_step > 0.0 else 0.0
        F_lf_mean = float(np.sum(C_triu * F_lf) / sum_C) if sum_C > 0.0 else 0.0

        crat_mask = F_lf > 0.5
        n_crat = float(np.sum(C_triu[crat_mask]))
        n_frag = float(np.sum(C_triu[~crat_mask]))
        denom_frac = n_crat + n_frag
        frac_crat = n_crat / denom_frac if denom_frac > 0.0 else 0.0
        frac_frag = n_frag / denom_frac if denom_frac > 0.0 else 0.0

        stats = np.array(
            [
                E_rel_step,
                E_diss_step,
                E_ret_step,
                f_ke_mean_C,
                f_ke_energy,
                F_lf_mean,
                n_crat,
                n_frag,
                frac_crat,
                frac_frag,
            ],
            dtype=np.float64,
        )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "compute_collision_kernel_bookkeeping: n_bins=%d use_numba=%s E_rel=%e",
            n,
            use_jit,
            stats[0] if stats is not None and stats.size > 0 else -1.0,
        )
    return kernel, stats
