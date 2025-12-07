"""Numba-accelerated kernels for performance-critical physics computations.

This module provides JIT-compiled implementations of computationally intensive
routines used in the Smoluchowski collision/fragmentation solver.  The functions
are designed as drop-in replacements for pure-Python/NumPy loops and are
activated automatically when :mod:`numba` is available.

The main acceleration targets are:

1. **Fragment tensor construction** (`_fragment_tensor`): The O(n²) loop that
   fills `Y[k, i, j]` is replaced with a parallelised Numba kernel using
   `prange` over the outer index.

2. **Weights table precomputation**: Power-law fragment weights are computed
   once and reused across all (i, j) pairs.

Usage
-----
These functions are not meant to be called directly.  Instead, the parent
module :mod:`marsdisk.physics.collisions_smol` checks for the availability
of the Numba implementations and uses them transparently when possible.

Notes
-----
* All kernels use ``cache=True`` to persist compiled bytecode across runs.
* ``parallel=True`` enables automatic threading via ``prange``; the number
  of threads respects ``NUMBA_NUM_THREADS`` (default: all cores).
* Fallback to pure NumPy is automatic if Numba is unavailable or compilation
  fails at import time.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit, prange
    _NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMBA_AVAILABLE = False

    # Provide dummy decorators so the module can still be imported
    def njit(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])

    def prange(*args, **kwargs):  # type: ignore[misc]
        return range(*args)

__all__ = [
    "NUMBA_AVAILABLE",
    "compute_weights_table_numba",
    "fill_fragment_tensor_numba",
]


def NUMBA_AVAILABLE() -> bool:
    """Return True if Numba JIT compilation is available."""
    return _NUMBA_AVAILABLE


# ---------------------------------------------------------------------------
# Weights table for power-law fragment distribution
# ---------------------------------------------------------------------------


@njit(cache=True)
def compute_weights_table_numba(
    sizes: np.ndarray,
    alpha_frag: float,
) -> np.ndarray:
    """Precompute normalised power-law weights for fragment distribution.

    For each largest-remnant bin index ``k_lr``, the weights are:

        w_k = s_k^{-alpha_frag} / Σ_{k'≤k_lr} s_{k'}^{-alpha_frag}

    Parameters
    ----------
    sizes : ndarray
        Array of particle sizes (bin centres) with shape ``(n,)``.
    alpha_frag : float
        Power-law exponent for the fragment size distribution.

    Returns
    -------
    ndarray
        Weights table with shape ``(n, n)`` where ``table[k_lr, k]`` gives
        the normalised weight for bin ``k`` when the largest remnant falls
        into bin ``k_lr``.
    """
    n = sizes.shape[0]
    table = np.zeros((n, n), dtype=np.float64)

    for k_lr in range(n):
        total = 0.0
        for k in range(k_lr + 1):
            total += sizes[k] ** (-alpha_frag)
        if total > 0.0:
            inv_total = 1.0 / total
            for k in range(k_lr + 1):
                table[k_lr, k] = (sizes[k] ** (-alpha_frag)) * inv_total
    return table


# ---------------------------------------------------------------------------
# Fragment tensor Y[k, i, j] construction
# ---------------------------------------------------------------------------


@njit(cache=True, parallel=True)
def fill_fragment_tensor_numba(
    Y: np.ndarray,
    n: int,
    valid_pair: np.ndarray,
    f_lr_matrix: np.ndarray,
    k_lr_matrix: np.ndarray,
    weights_table: np.ndarray,
) -> None:
    """Fill the fragment distribution tensor in-place using parallel loops.

    This kernel replaces the pure-Python double loop in ``_fragment_tensor``.
    The outer loop over ``i`` is parallelised with ``prange``.

    Parameters
    ----------
    Y : ndarray
        Output tensor of shape ``(n, n, n)`` to fill in-place.  Should be
        initialised to zeros before calling.
    n : int
        Number of size bins.
    valid_pair : ndarray
        Boolean mask of shape ``(n, n)`` indicating valid (i, j) pairs.
    f_lr_matrix : ndarray
        Largest-remnant mass fraction for each (i, j) pair, shape ``(n, n)``.
    k_lr_matrix : ndarray
        Bin index of the largest remnant for each (i, j) pair, shape ``(n, n)``.
        Values are integers cast to ``np.int64``.
    weights_table : ndarray
        Precomputed weights from :func:`compute_weights_table_numba`.
    """
    for i in prange(n):
        for j in range(n):
            if not valid_pair[i, j]:
                continue

            k_lr = k_lr_matrix[i, j]
            f_lr = f_lr_matrix[i, j]

            # Assign largest remnant fraction
            Y[k_lr, i, j] += f_lr

            # Distribute remainder according to power-law weights
            remainder = 1.0 - f_lr
            if remainder > 0.0:
                for k in range(k_lr + 1):
                    w = weights_table[k_lr, k]
                    if w > 0.0:
                        Y[k, i, j] += remainder * w
