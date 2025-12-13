from __future__ import annotations

"""Specific disruption energy model (F1).

References
----------
- [@BenzAsphaug1999_Icarus142_5] catastrophic disruption thresholds for basalt-like material
- [@LeinhardtStewart2012_ApJ745_79] velocity interpolation between reference laws
"""

import logging
from typing import Dict, Tuple, Literal

import numpy as np

from ..errors import MarsDiskError

__all__ = [
    "compute_q_d_star_F1",
    "compute_q_d_star_array",
    "get_coeff_unit_system",
    "get_coefficient_table",
    "get_velocity_clamp_stats",
    "reset_velocity_clamp_stats",
    "set_coeff_unit_system",
]

# Coefficients from [@BenzAsphaug1999_Icarus142_5] evaluated at reference velocities in km/s.
# Basalt-like material parameters follow [@LeinhardtStewart2012_ApJ745_79].
# The keys represent the impact velocity in km/s.
_COEFFS: Dict[float, Tuple[float, float, float, float]] = {
    3.0: (3.5e7, 0.38, 0.3, 1.36),  # Qs, a_s, B, b_g at 3 km/s
    5.0: (7.0e7, 0.38, 0.5, 1.36),  # Qs, a_s, B, b_g at 5 km/s
}

_V_MIN = min(_COEFFS.keys())
_V_MAX = max(_COEFFS.keys())

CoeffUnits = Literal["ba99_cgs", "si"]

logger = logging.getLogger(__name__)
_COEFF_UNIT_CHOICES: set[CoeffUnits] = {"ba99_cgs", "si"}
_COEFF_UNIT_SYSTEM: CoeffUnits = "ba99_cgs"
_CM_PER_M = 1.0e2
_RHO_GCM3_FROM_SI = 1.0e-3
_ERG_PER_G_TO_J_PER_KG = 1.0e-4
_VEL_CLAMP_COUNTS: dict[str, int] = {"below": 0, "above": 0}
_VEL_CLAMP_WARNED = False


def set_coeff_unit_system(units: CoeffUnits) -> CoeffUnits:
    """Set the coefficient unit system used during :math:`Q_D^*` evaluation."""

    global _COEFF_UNIT_SYSTEM
    if units not in _COEFF_UNIT_CHOICES:
        raise MarsDiskError(f"unknown coeff_units={units!r}; expected one of {_COEFF_UNIT_CHOICES}")
    _COEFF_UNIT_SYSTEM = units
    return _COEFF_UNIT_SYSTEM


def get_coeff_unit_system() -> CoeffUnits:
    """Return the active coefficient unit system."""

    return _COEFF_UNIT_SYSTEM


def get_coefficient_table() -> Dict[float, Tuple[float, float, float, float]]:
    """Return the coefficient lookup keyed by reference velocity [km/s]."""

    return dict(_COEFFS)


def reset_velocity_clamp_stats() -> None:
    """Reset counters that track impact-velocity clamping events."""

    global _VEL_CLAMP_COUNTS, _VEL_CLAMP_WARNED
    _VEL_CLAMP_COUNTS = {"below": 0, "above": 0}
    _VEL_CLAMP_WARNED = False


def get_velocity_clamp_stats() -> Dict[str, int]:
    """Return a copy of the clamp counters for diagnostics."""

    return dict(_VEL_CLAMP_COUNTS)


def _track_velocity_clamp(v_values: np.ndarray) -> None:
    """Record and optionally warn when v_kms falls outside the tabulated range."""

    global _VEL_CLAMP_WARNED
    v_flat = np.asarray(v_values, dtype=float).ravel()
    below = int(np.sum(v_flat < _V_MIN))
    above = int(np.sum(v_flat > _V_MAX))
    if below or above:
        _VEL_CLAMP_COUNTS["below"] += below
        _VEL_CLAMP_COUNTS["above"] += above
        if not _VEL_CLAMP_WARNED:
            logger.warning(
                "Impact velocity outside [%.1f, %.1f] km/s; clamping to bounds (further warnings suppressed).",
                _V_MIN,
                _V_MAX,
            )
            _VEL_CLAMP_WARNED = True


def _q_d_star(
    s: np.ndarray,
    rho: float,
    coeffs: Tuple[float, float, float, float],
    coeff_units: CoeffUnits,
) -> np.ndarray:
    """Vectorised :math:`Q_D^*` evaluation for scalar or array inputs."""

    if rho <= 0.0:
        raise MarsDiskError("density must be positive")
    s_arr = np.asarray(s, dtype=float)
    if np.any(s_arr <= 0.0):
        raise MarsDiskError("size must be positive")

    Qs, a_s, B, b_g = coeffs
    if coeff_units == "ba99_cgs":
        s_ratio = s_arr * _CM_PER_M  # convert s[m] to s/1 cm
        rho_use = rho * _RHO_GCM3_FROM_SI
        q_val = Qs * np.power(s_ratio, -a_s) + B * rho_use * np.power(s_ratio, b_g)
        return q_val * _ERG_PER_G_TO_J_PER_KG
    s_ratio = s_arr / 1.0
    rho_use = rho
    return Qs * np.power(s_ratio, -a_s) + B * rho_use * np.power(s_ratio, b_g)


def compute_q_d_star_array(s: np.ndarray, rho: float, v_kms: np.ndarray) -> np.ndarray:
    """Return :math:`Q_D^*` for array inputs with velocity interpolation."""

    s_arr = np.asarray(s, dtype=float)
    v_raw = np.asarray(v_kms, dtype=float)
    _track_velocity_clamp(v_raw)
    v_arr = np.asarray(v_raw, dtype=float)
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
    coeff_units = _COEFF_UNIT_SYSTEM
    q_lo = _q_d_star(s_arr, rho, coeff_lo, coeff_units)
    q_hi = _q_d_star(s_arr, rho, coeff_hi, coeff_units)

    weight = (v_arr - _V_MIN) / (_V_MAX - _V_MIN)
    weight = np.clip(weight, 0.0, 1.0)
    return q_lo * (1.0 - weight) + q_hi * weight


def compute_q_d_star_F1(s: float, rho: float, v_kms: float) -> float:
    """Return the catastrophic disruption threshold ``Q_D^*``.

    The size-dependent law from [@BenzAsphaug1999_Icarus142_5] is evaluated and
    then linearly interpolated in velocity between the 3 and 5 km/s reference
    values following [@LeinhardtStewart2012_ApJ745_79]. Velocities outside this
    range adopt the nearest reference value.

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

    _track_velocity_clamp(np.asarray([v_kms], dtype=float))

    coeff_lo = _COEFFS[_V_MIN]
    coeff_hi = _COEFFS[_V_MAX]
    coeff_units = _COEFF_UNIT_SYSTEM
    q_lo = _q_d_star(np.asarray(s, dtype=float), rho, coeff_lo, coeff_units)
    q_hi = _q_d_star(np.asarray(s, dtype=float), rho, coeff_hi, coeff_units)

    if v_kms <= _V_MIN:
        return float(q_lo)
    if v_kms >= _V_MAX:
        return float(q_hi)

    # linear interpolation between the two reference velocities
    weight = (v_kms - _V_MIN) / (_V_MAX - _V_MIN)
    return float(q_lo * (1.0 - weight) + q_hi * weight)
