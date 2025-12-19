"""Numba-accelerated interpolation helpers for table lookups."""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])

__all__ = [
    "NUMBA_AVAILABLE",
    "qpr_interp_scalar_numba",
]


def NUMBA_AVAILABLE() -> bool:
    """Return True if Numba JIT compilation is available."""
    return _NUMBA_AVAILABLE


@njit(cache=True)
def qpr_interp_scalar_numba(
    s_vals: np.ndarray,
    T_vals: np.ndarray,
    q_vals: np.ndarray,
    s: float,
    T: float,
) -> float:
    """Bilinear interpolation for the Planck-mean Q_pr table."""
    n_s = s_vals.shape[0]
    n_T = T_vals.shape[0]

    i = np.searchsorted(s_vals, s) - 1
    if i < 0:
        i = 0
    elif i > n_s - 2:
        i = n_s - 2

    j = np.searchsorted(T_vals, T) - 1
    if j < 0:
        j = 0
    elif j > n_T - 2:
        j = n_T - 2

    s1 = s_vals[i]
    s2 = s_vals[i + 1]
    T1 = T_vals[j]
    T2 = T_vals[j + 1]

    q11 = q_vals[j, i]
    q12 = q_vals[j + 1, i]
    q21 = q_vals[j, i + 1]
    q22 = q_vals[j + 1, i + 1]

    ws = 0.0 if s2 == s1 else (s - s1) / (s2 - s1)
    wT = 0.0 if T2 == T1 else (T - T1) / (T2 - T1)

    q1 = q11 * (1.0 - ws) + q21 * ws
    q2 = q12 * (1.0 - ws) + q22 * ws
    return q1 * (1.0 - wT) + q2 * wT
