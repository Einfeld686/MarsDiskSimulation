from __future__ import annotations

"""Specific disruption energy model (F1).

References
----------
- [@BenzAsphaug1999_Icarus142_5] catastrophic disruption thresholds for basalt-like material
- [@LeinhardtStewart2012_ApJ745_79] velocity interpolation between reference laws
"""

from typing import Dict, Tuple

import numpy as np

from ..errors import MarsDiskError

__all__ = ["compute_q_d_star_F1", "compute_q_d_star_array"]

# Coefficients for Benz & Asphaug (1999) power-law at reference velocities in km/s
# Values correspond to basalt-like material as in Leinhardt & Stewart (2012)
# [@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79].
# The keys represent the impact velocity in km/s.
_COEFFS: Dict[float, Tuple[float, float, float, float]] = {
    3.0: (3.5e7, 0.38, 0.3, 1.36),  # Qs, a_s, B, b_g at 3 km/s
    5.0: (7.0e7, 0.38, 0.5, 1.36),  # Qs, a_s, B, b_g at 5 km/s
}

_V_MIN = min(_COEFFS.keys())
_V_MAX = max(_COEFFS.keys())


def _q_d_star(s: float, rho: float, coeffs: Tuple[float, float, float, float]) -> float:
    """Evaluate :math:`Q_D^*` using a single coefficient set."""

    Qs, a_s, B, b_g = coeffs
    s_ratio = s / 1.0  # metres; explicit for clarity
    return Qs * s_ratio ** (-a_s) + B * rho * s_ratio ** b_g


def _q_d_star_array(
    s: np.ndarray,
    rho: float,
    coeffs: Tuple[float, float, float, float],
) -> np.ndarray:
    """Vectorised :math:`Q_D^*` evaluation for array inputs."""

    if rho <= 0.0:
        raise MarsDiskError("density must be positive")
    s_arr = np.asarray(s, dtype=float)
    if np.any(s_arr <= 0.0):
        raise MarsDiskError("size must be positive")
    Qs, a_s, B, b_g = coeffs
    s_ratio = s_arr / 1.0
    return Qs * np.power(s_ratio, -a_s) + B * rho * np.power(s_ratio, b_g)


def compute_q_d_star_array(s: np.ndarray, rho: float, v_kms: np.ndarray) -> np.ndarray:
    """Return :math:`Q_D^*` for array inputs with velocity interpolation."""

    s_arr = np.asarray(s, dtype=float)
    v_arr = np.asarray(v_kms, dtype=float)
    try:
        s_arr, v_arr = np.broadcast_arrays(s_arr, v_arr)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise MarsDiskError(f"cannot broadcast s and v_kms: {exc}") from exc
    if np.any(s_arr <= 0.0):
        raise MarsDiskError("size must be positive")
    if rho <= 0.0:
        raise MarsDiskError("density must be positive")
    if np.any(v_arr <= 0.0):
        raise MarsDiskError("velocity must be positive")

    coeff_lo = _COEFFS[_V_MIN]
    coeff_hi = _COEFFS[_V_MAX]
    q_lo = _q_d_star_array(s_arr, rho, coeff_lo)
    q_hi = _q_d_star_array(s_arr, rho, coeff_hi)

    weight = (v_arr - _V_MIN) / (_V_MAX - _V_MIN)
    weight = np.clip(weight, 0.0, 1.0)
    return q_lo * (1.0 - weight) + q_hi * weight


def compute_q_d_star_F1(s: float, rho: float, v_kms: float) -> float:
    """Return the catastrophic disruption threshold ``Q_D^*``.

    The Benz & Asphaug (1999) size-dependent law[@BenzAsphaug1999_Icarus142_5]
    is evaluated and then linearly interpolated in velocity between the 3 and
    5 km/s reference values following Leinhardt & Stewart (2012)
    [@LeinhardtStewart2012_ApJ745_79]. Velocities outside this range adopt the
    nearest reference value.

    Parameters
    ----------
    s:
        Characteristic size of the body in metres.
    rho:
        Material density in kg/m^3.
    v_kms:
        Impact velocity in km/s.

    Returns
    -------
    float
        Catastrophic disruption threshold in J/kg.
    """

    if s <= 0.0:
        raise MarsDiskError("size must be positive")
    if rho <= 0.0:
        raise MarsDiskError("density must be positive")
    if v_kms <= 0.0:
        raise MarsDiskError("velocity must be positive")

    coeff_lo = _COEFFS[_V_MIN]
    coeff_hi = _COEFFS[_V_MAX]
    q_lo = _q_d_star(s, rho, coeff_lo)
    q_hi = _q_d_star(s, rho, coeff_hi)

    if v_kms <= _V_MIN:
        return float(q_lo)
    if v_kms >= _V_MAX:
        return float(q_hi)

    # linear interpolation between the two reference velocities
    weight = (v_kms - _V_MIN) / (_V_MAX - _V_MIN)
    return float(q_lo * (1.0 - weight) + q_hi * weight)
