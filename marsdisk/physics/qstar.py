from __future__ import annotations

"""Specific disruption energy model (F1).

References
----------
- [@BenzAsphaug1999_Icarus142_5] catastrophic disruption thresholds for basalt-like material
- [@LeinhardtStewart2012_ApJ745_79] velocity interpolation between reference laws
"""

import logging
from collections import OrderedDict
from typing import Dict, Tuple, Literal

import numpy as np

from ..errors import MarsDiskError

__all__ = [
    "compute_q_d_star_F1",
    "compute_q_d_star_array",
    "get_coeff_unit_system",
    "get_coefficient_table",
    "get_gravity_velocity_mu",
    "get_velocity_clamp_stats",
    "reset_coefficient_table",
    "reset_velocity_clamp_stats",
    "set_coefficient_table",
    "set_coeff_unit_system",
    "set_gravity_velocity_mu",
]

# Coefficients from [@BenzAsphaug1999_Icarus142_5] evaluated at reference velocities in km/s.
# Basalt-like material parameters follow [@LeinhardtStewart2012_ApJ745_79].
# The keys represent the impact velocity in km/s.
_DEFAULT_COEFFS: Dict[float, Tuple[float, float, float, float]] = {
    3.0: (3.5e7, 0.38, 0.3, 1.36),  # Qs, a_s, B, b_g at 3 km/s
    5.0: (7.0e7, 0.38, 0.5, 1.36),  # Qs, a_s, B, b_g at 5 km/s
}

_COEFFS: Dict[float, Tuple[float, float, float, float]] = dict(_DEFAULT_COEFFS)

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
# Gravitational-regime velocity exponent μ from LS09; used as v^{-3μ+2} outside [v_min, v_max].
_GRAVITY_VELOCITY_MU = 0.45
_QDSTAR_CACHE_MAXSIZE = 8
_QDSTAR_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()


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


def _normalise_coeff_table(
    table: Dict[float, Tuple[float, float, float, float]] | Dict[float, Tuple[float, ...]] | Dict[float, Dict[str, float]]
) -> Dict[float, Tuple[float, float, float, float]]:
    """Coerce coefficient table values to ``(Qs, a_s, B, b_g)`` tuples."""

    if not table:
        raise MarsDiskError("coefficient table must not be empty")
    cleaned: Dict[float, Tuple[float, float, float, float]] = {}
    for raw_v, raw_coeffs in table.items():
        v_ref = float(raw_v)
        if v_ref <= 0.0:
            raise MarsDiskError("reference velocity must be positive")
        if isinstance(raw_coeffs, dict):
            Qs = float(raw_coeffs.get("Qs", float("nan")))
            a_s = float(raw_coeffs.get("a_s", float("nan")))
            B = float(raw_coeffs.get("B", float("nan")))
            b_g = float(raw_coeffs.get("b_g", float("nan")))
            coeffs = (Qs, a_s, B, b_g)
        else:
            coeffs = tuple(float(val) for val in raw_coeffs)
        if len(coeffs) != 4:
            raise MarsDiskError("coefficient table entries must have 4 values (Qs, a_s, B, b_g)")
        Qs, a_s, B, b_g = coeffs
        if Qs <= 0.0 or B <= 0.0:
            raise MarsDiskError("Qs and B must be positive in the coefficient table")
        cleaned[v_ref] = (float(Qs), float(a_s), float(B), float(b_g))
    return cleaned


def set_coefficient_table(
    table: Dict[float, Tuple[float, float, float, float]] | Dict[float, Tuple[float, ...]] | Dict[float, Dict[str, float]],
) -> Dict[float, Tuple[float, float, float, float]]:
    """Replace the active coefficient table and return the normalised copy."""

    global _COEFFS, _V_MIN, _V_MAX
    cleaned = _normalise_coeff_table(table)
    _COEFFS = dict(cleaned)
    _V_MIN = min(_COEFFS.keys())
    _V_MAX = max(_COEFFS.keys())
    _QDSTAR_CACHE.clear()
    return dict(_COEFFS)


def reset_coefficient_table() -> Dict[float, Tuple[float, float, float, float]]:
    """Restore the built-in basalt coefficient table."""

    return set_coefficient_table(_DEFAULT_COEFFS)


def reset_velocity_clamp_stats() -> None:
    """Reset counters that track impact-velocity clamping events."""

    global _VEL_CLAMP_COUNTS, _VEL_CLAMP_WARNED
    _VEL_CLAMP_COUNTS = {"below": 0, "above": 0}
    _VEL_CLAMP_WARNED = False


def get_velocity_clamp_stats() -> Dict[str, int]:
    """Return a copy of the clamp counters for diagnostics."""

    return dict(_VEL_CLAMP_COUNTS)


def set_gravity_velocity_mu(mu: float) -> float:
    """Set the LS09 gravitational-regime exponent μ used for velocity scaling."""

    global _GRAVITY_VELOCITY_MU
    if mu <= 0.0:
        raise MarsDiskError("gravity velocity exponent mu must be positive")
    _GRAVITY_VELOCITY_MU = float(mu)
    return _GRAVITY_VELOCITY_MU


def get_gravity_velocity_mu() -> float:
    """Return the active LS09 gravitational-regime exponent μ."""

    return _GRAVITY_VELOCITY_MU


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
                "Impact velocity outside [%.1f, %.1f] km/s; extrapolating gravity term with v^{-3mu+2} while clamping coefficient lookup to bounds (further warnings suppressed).",
                _V_MIN,
                _V_MAX,
            )
            _VEL_CLAMP_WARNED = True


def _qdstar_cache_key(s: np.ndarray, rho: float, v_kms: float) -> tuple | None:
    """Return an immutable cache key for scalar-velocity lookups."""

    if s.ndim != 1:
        return None
    return ("scalar_v", float(rho), float(v_kms), tuple(np.asarray(s, dtype=float).tolist()))


def _qdstar_cache_get(key: tuple | None) -> np.ndarray | None:
    if key is None:
        return None
    cached = _QDSTAR_CACHE.get(key)
    if cached is None:
        return None
    _QDSTAR_CACHE.move_to_end(key)
    return np.array(cached, copy=True)


def _qdstar_cache_put(key: tuple | None, value: np.ndarray) -> None:
    if key is None:
        return
    _QDSTAR_CACHE[key] = np.array(value, copy=True)
    _QDSTAR_CACHE.move_to_end(key)
    while len(_QDSTAR_CACHE) > _QDSTAR_CACHE_MAXSIZE:
        _QDSTAR_CACHE.popitem(last=False)


def _q_d_star(
    s: np.ndarray,
    rho: float,
    coeffs: Tuple[float, float, float, float],
    coeff_units: CoeffUnits,
) -> Tuple[np.ndarray, np.ndarray]:
    """Vectorised :math:`Q_D^*` split into strength and gravity terms."""

    if rho <= 0.0:
        raise MarsDiskError("density must be positive")
    s_arr = np.asarray(s, dtype=float)
    if np.any(s_arr <= 0.0):
        raise MarsDiskError("size must be positive")

    Qs, a_s, B, b_g = coeffs
    if coeff_units == "ba99_cgs":
        s_ratio = s_arr * _CM_PER_M  # convert s[m] to s/1 cm
        rho_use = rho * _RHO_GCM3_FROM_SI
        q_strength = Qs * np.power(s_ratio, -a_s)
        q_gravity = B * rho_use * np.power(s_ratio, b_g)
        return q_strength * _ERG_PER_G_TO_J_PER_KG, q_gravity * _ERG_PER_G_TO_J_PER_KG
    s_ratio = s_arr / 1.0
    rho_use = rho
    q_strength = Qs * np.power(s_ratio, -a_s)
    q_gravity = B * rho_use * np.power(s_ratio, b_g)
    return q_strength, q_gravity


def _gravity_velocity_scale(v_kms: np.ndarray) -> np.ndarray:
    """Return multiplicative scaling for the gravity term outside [v_min, v_max]."""

    exponent = -3.0 * _GRAVITY_VELOCITY_MU + 2.0
    v_arr = np.asarray(v_kms, dtype=float)
    scale = np.ones_like(v_arr, dtype=float)
    scale = np.where(v_arr < _V_MIN, np.power(v_arr / _V_MIN, exponent), scale)
    scale = np.where(v_arr > _V_MAX, np.power(v_arr / _V_MAX, exponent), scale)
    return scale


def compute_q_d_star_array(s: np.ndarray, rho: float, v_kms: np.ndarray) -> np.ndarray:
    """Return :math:`Q_D^*` for array inputs with velocity interpolation."""

    s_arr = np.asarray(s, dtype=float)
    v_raw = np.asarray(v_kms, dtype=float)
    cache_key = None
    if v_raw.ndim == 0 or (v_raw.size == 1 and v_raw.shape == ()):
        cache_key = _qdstar_cache_key(s_arr, rho, float(v_raw))
        cached = _qdstar_cache_get(cache_key)
        if cached is not None:
            return cached
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
    strength_lo, gravity_lo = _q_d_star(s_arr, rho, coeff_lo, coeff_units)
    strength_hi, gravity_hi = _q_d_star(s_arr, rho, coeff_hi, coeff_units)

    weight = (v_arr - _V_MIN) / (_V_MAX - _V_MIN)
    weight = np.clip(weight, 0.0, 1.0)
    strength = strength_lo * (1.0 - weight) + strength_hi * weight
    gravity = gravity_lo * (1.0 - weight) + gravity_hi * weight
    gravity_scale = _gravity_velocity_scale(v_arr)
    result = strength + gravity * gravity_scale
    _qdstar_cache_put(cache_key, result)
    return result


def compute_q_d_star_F1(s: float, rho: float, v_kms: float) -> float:
    """Return the catastrophic disruption threshold ``Q_D^*``.

    The size-dependent law from [@BenzAsphaug1999_Icarus142_5] is evaluated and
    then linearly interpolated in velocity between the 3 and 5 km/s reference
    values following [@LeinhardtStewart2012_ApJ745_79]. Outside this range the
    strength term is held fixed at the nearest reference value, while the
    gravity term is scaled by :math:`(v/v_{\\mathrm{ref}})^{-3\\mu+2}` with
    :math:`\\mu` taken from LS09 and configurable via :func:`set_gravity_velocity_mu`.

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
    strength_lo, gravity_lo = _q_d_star(np.asarray(s, dtype=float), rho, coeff_lo, coeff_units)
    strength_hi, gravity_hi = _q_d_star(np.asarray(s, dtype=float), rho, coeff_hi, coeff_units)

    if v_kms <= _V_MIN:
        gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
        return float(strength_lo + gravity_lo * gravity_scale)
    if v_kms >= _V_MAX:
        gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
        return float(strength_hi + gravity_hi * gravity_scale)

    # linear interpolation between the two reference velocities
    weight = (v_kms - _V_MIN) / (_V_MAX - _V_MIN)
    strength = strength_lo * (1.0 - weight) + strength_hi * weight
    gravity = gravity_lo * (1.0 - weight) + gravity_hi * weight
    gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
    return float(strength + gravity * gravity_scale)
