"""Numba-accelerated helpers for radiation-pressure relations."""
from __future__ import annotations

from .. import constants

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
    "blowout_radius_numba",
]

_BLOWOUT_COEFF = float(
    3.0 * constants.SIGMA_SB * (constants.R_MARS**2)
    / (2.0 * constants.G * constants.M_MARS * constants.C)
)


def NUMBA_AVAILABLE() -> bool:
    """Return True if Numba JIT compilation is available."""
    return _NUMBA_AVAILABLE


@njit(cache=True)
def blowout_radius_numba(rho: float, T_M: float, qpr: float) -> float:
    """Evaluate the blow-out grain size for beta=0.5 using R3."""
    return _BLOWOUT_COEFF * (T_M**4) * qpr / rho
