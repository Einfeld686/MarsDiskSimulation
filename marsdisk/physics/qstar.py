from __future__ import annotations

"""Specific disruption energy model (F1).

References
----------
- [@BenzAsphaug1999_Icarus142_5] catastrophic disruption thresholds for basalt-like material
- [@LeinhardtStewart2012_ApJ745_79] velocity interpolation between reference laws
"""

import logging
import threading
from collections import OrderedDict
from typing import Dict, Tuple, Literal

import numpy as np

from ..errors import MarsDiskError

__all__ = [
    "compute_q_d_star_F1",
    "compute_q_d_star_array",
    "get_coeff_unit_system",
    "get_coefficient_table",
    "get_qdstar_signature",
    "get_gravity_velocity_mu",
    "get_velocity_clamp_stats",
    "reset_coefficient_table",
    "reset_velocity_clamp_stats",
    "set_coefficient_table",
    "set_coeff_unit_system",
    "set_gravity_velocity_mu",
]

# Coefficients derived from the basalt-like reference values used in this module.
#
# Notes on the built-in 1–7 km/s table
# -----------------------------------
# The original default table in this module consisted of only two reference
# velocities (3 and 5 km/s). For velocities outside that range, the module
# behaviour was:
#   - clamp the *strength* term to the nearest reference velocity, and
#   - scale the *gravity* term by (v/v_ref)^(-3μ+2), where μ is configurable.
#
# For Stage B we "bake in" that same behaviour to provide an explicit
# 1–7 km/s coefficient table so that:
#   - velocities in [1, 7] km/s no longer trigger clamp warnings, and
#   - clamp warnings are reserved for v < 1 or v > 7 km/s.
#
# Concretely:
#   - (Qs, a_s, b_g) are extended by clamping (v<=3 uses 3 km/s, v>=5 uses 5 km/s)
#   - B is extended using the same exponent (-3μ+2) with μ=0.45 that the module
#     uses by default for out-of-range scaling.
#
# The keys represent the impact velocity in km/s.
_DEFAULT_COEFFS: Dict[float, Tuple[float, float, float, float]] = {
    1.0: (3.5e7, 0.38, 0.14689007046000738, 1.36),  # derived from 3 km/s gravity scaling
    2.0: (3.5e7, 0.38, 0.23049522684371007, 1.36),  # derived from 3 km/s gravity scaling
    3.0: (3.5e7, 0.38, 0.3, 1.36),                  # anchor (existing default)
    4.0: (5.25e7, 0.38, 0.4, 1.36),                 # linear interp between 3 and 5 km/s
    5.0: (7.0e7, 0.38, 0.5, 1.36),                  # anchor (existing default)
    6.0: (7.0e7, 0.38, 0.5629085099123813, 1.36),   # derived from 5 km/s gravity scaling
    7.0: (7.0e7, 0.38, 0.6222332685311813, 1.36),   # derived from 5 km/s gravity scaling
}

_COEFFS: Dict[float, Tuple[float, float, float, float]] = dict(_DEFAULT_COEFFS)
_COEFF_VERSION = 0

# Sorted list of reference velocities used for bracketing/interpolation.
_V_KEYS = tuple(sorted(_COEFFS.keys()))
_V_MIN = _V_KEYS[0]
_V_MAX = _V_KEYS[-1]

CoeffUnits = Literal["ba99_cgs", "si"]

logger = logging.getLogger(__name__)
_COEFF_UNIT_CHOICES: set[CoeffUnits] = {"ba99_cgs", "si"}
_COEFF_UNIT_SYSTEM: CoeffUnits = "ba99_cgs"
_CM_PER_M = 1.0e2
_RHO_GCM3_FROM_SI = 1.0e-3
_ERG_PER_G_TO_J_PER_KG = 1.0e-4
_VEL_CLAMP_COUNTS: dict[str, int] = {"below": 0, "above": 0}
_VEL_CLAMP_WARNED = False
_VEL_CLAMP_LOCK = threading.Lock()
# Gravitational-regime velocity exponent μ from LS09; used as v^{-3μ+2} outside [v_min, v_max].
_GRAVITY_VELOCITY_MU = 0.45
_QDSTAR_CACHE_MAXSIZE = 8
_QDSTAR_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_QDSTAR_CACHE_LOCK = threading.Lock()


def set_coeff_unit_system(units: CoeffUnits) -> CoeffUnits:
    """Set the coefficient unit system used during :math:`Q_D^*` evaluation."""

    global _COEFF_UNIT_SYSTEM, _COEFF_VERSION
    if units not in _COEFF_UNIT_CHOICES:
        raise MarsDiskError(f"unknown coeff_units={units!r}; expected one of {_COEFF_UNIT_CHOICES}")
    _COEFF_UNIT_SYSTEM = units
    _COEFF_VERSION += 1
    with _QDSTAR_CACHE_LOCK:
        _QDSTAR_CACHE.clear()
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

    global _COEFFS, _V_KEYS, _V_MIN, _V_MAX, _COEFF_VERSION
    cleaned = _normalise_coeff_table(table)
    _COEFFS = dict(cleaned)
    _V_KEYS = tuple(sorted(_COEFFS.keys()))
    _V_MIN = _V_KEYS[0]
    _V_MAX = _V_KEYS[-1]
    _COEFF_VERSION += 1
    with _QDSTAR_CACHE_LOCK:
        _QDSTAR_CACHE.clear()
    return dict(_COEFFS)


def reset_coefficient_table() -> Dict[float, Tuple[float, float, float, float]]:
    """Restore the built-in basalt coefficient table."""

    return set_coefficient_table(_DEFAULT_COEFFS)


def reset_velocity_clamp_stats() -> None:
    """Reset counters that track impact-velocity clamping events."""

    global _VEL_CLAMP_COUNTS, _VEL_CLAMP_WARNED
    with _VEL_CLAMP_LOCK:
        _VEL_CLAMP_COUNTS = {"below": 0, "above": 0}
        _VEL_CLAMP_WARNED = False


def get_velocity_clamp_stats() -> Dict[str, int]:
    """Return a copy of the clamp counters for diagnostics."""

    with _VEL_CLAMP_LOCK:
        return dict(_VEL_CLAMP_COUNTS)


def set_gravity_velocity_mu(mu: float) -> float:
    """Set the LS09 gravitational-regime exponent μ used for velocity scaling."""

    global _GRAVITY_VELOCITY_MU, _COEFF_VERSION
    if mu <= 0.0:
        raise MarsDiskError("gravity velocity exponent mu must be positive")
    _GRAVITY_VELOCITY_MU = float(mu)
    _COEFF_VERSION += 1
    with _QDSTAR_CACHE_LOCK:
        _QDSTAR_CACHE.clear()
    return _GRAVITY_VELOCITY_MU


def get_qdstar_signature() -> tuple[int, str, float]:
    """Return a compact signature for Q_D* coefficient settings."""

    return (int(_COEFF_VERSION), str(_COEFF_UNIT_SYSTEM), float(_GRAVITY_VELOCITY_MU))


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
        with _VEL_CLAMP_LOCK:
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
    with _QDSTAR_CACHE_LOCK:
        cached = _QDSTAR_CACHE.get(key)
        if cached is None:
            return None
        _QDSTAR_CACHE.move_to_end(key)
        return np.array(cached, copy=True)


def _qdstar_cache_put(key: tuple | None, value: np.ndarray) -> None:
    if key is None:
        return
    with _QDSTAR_CACHE_LOCK:
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

    coeff_units = _COEFF_UNIT_SYSTEM
    v_keys = np.asarray(_V_KEYS, dtype=float)
    if v_keys.size == 0:
        raise MarsDiskError("coefficient table must not be empty")  # defensive
    if v_keys.size == 1:
        # Degenerate case: single reference velocity; treat as clamped everywhere.
        coeff = _COEFFS[float(v_keys[0])]
        strength, gravity = _q_d_star(s_arr, rho, coeff, coeff_units)
        result = strength + gravity * _gravity_velocity_scale(v_arr)
        _qdstar_cache_put(cache_key, result)
        return result

    v_min = float(v_keys[0])
    v_max = float(v_keys[-1])

    # Prepare output
    result = np.empty_like(s_arr, dtype=float)

    mask_below = v_arr < v_min
    mask_above = v_arr > v_max
    mask_in = ~(mask_below | mask_above)

    # Out-of-range: clamp coefficients at bounds but keep velocity scaling for gravity term.
    if np.any(mask_below):
        coeff = _COEFFS[v_min]
        strength_base, gravity_base = _q_d_star(s_arr[mask_below], rho, coeff, coeff_units)
        gravity_scale = _gravity_velocity_scale(v_arr[mask_below])
        result[mask_below] = strength_base + gravity_base * gravity_scale

    if np.any(mask_above):
        coeff = _COEFFS[v_max]
        strength_base, gravity_base = _q_d_star(s_arr[mask_above], rho, coeff, coeff_units)
        gravity_scale = _gravity_velocity_scale(v_arr[mask_above])
        result[mask_above] = strength_base + gravity_base * gravity_scale

    # In-range: bracket to the adjacent reference velocities and interpolate piecewise.
    if np.any(mask_in):
        v_in = v_arr[mask_in]
        s_in = s_arr[mask_in]

        # idx is the left bracket index: v_keys[idx] <= v < v_keys[idx+1]
        idx = np.searchsorted(v_keys, v_in, side="right") - 1
        idx = np.clip(idx, 0, v_keys.size - 2)
        v_lo = v_keys[idx]
        v_hi = v_keys[idx + 1]
        weight = (v_in - v_lo) / (v_hi - v_lo)

        strength_in = np.empty_like(v_in, dtype=float)
        gravity_in = np.empty_like(v_in, dtype=float)

        for i in range(v_keys.size - 1):
            mask_i = idx == i
            if not np.any(mask_i):
                continue

            coeff_lo = _COEFFS[float(v_keys[i])]
            coeff_hi = _COEFFS[float(v_keys[i + 1])]

            s_sub = s_in[mask_i]
            strength_lo, gravity_lo = _q_d_star(s_sub, rho, coeff_lo, coeff_units)
            strength_hi, gravity_hi = _q_d_star(s_sub, rho, coeff_hi, coeff_units)

            w = weight[mask_i]
            strength_in[mask_i] = strength_lo * (1.0 - w) + strength_hi * w
            gravity_in[mask_i] = gravity_lo * (1.0 - w) + gravity_hi * w

        # Gravity scale is 1.0 within [v_min, v_max], but we keep the expression explicit.
        gravity_scale = _gravity_velocity_scale(v_in)
        result[mask_in] = strength_in + gravity_in * gravity_scale

    _qdstar_cache_put(cache_key, result)
    return result


def compute_q_d_star_F1(s: float, rho: float, v_kms: float) -> float:
    """Return the catastrophic disruption threshold ``Q_D^*``.

    The size-dependent law from [@BenzAsphaug1999_Icarus142_5] is evaluated and
    then interpolated in velocity between the tabulated reference velocities.
    Outside the tabulated range the strength term is held fixed at the nearest
    reference value, while the gravity term is scaled by
    :math:`(v/v_{\\mathrm{ref}})^{-3\\mu+2}` with :math:`\\mu` configurable via
    :func:`set_gravity_velocity_mu`.

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

    coeff_units = _COEFF_UNIT_SYSTEM
    v_keys = np.asarray(_V_KEYS, dtype=float)
    if v_keys.size == 0:
        raise MarsDiskError("coefficient table must not be empty")  # defensive

    v_min = float(v_keys[0])
    v_max = float(v_keys[-1])

    if v_kms <= v_min:
        coeff = _COEFFS[v_min]
        strength, gravity = _q_d_star(np.asarray(s, dtype=float), rho, coeff, coeff_units)
        gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
        return float(strength + gravity * gravity_scale)

    if v_kms >= v_max:
        coeff = _COEFFS[v_max]
        strength, gravity = _q_d_star(np.asarray(s, dtype=float), rho, coeff, coeff_units)
        gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
        return float(strength + gravity * gravity_scale)

    if v_keys.size == 1:
        # unreachable due to checks above, but keep behaviour symmetric with array API
        coeff = _COEFFS[v_min]
        strength, gravity = _q_d_star(np.asarray(s, dtype=float), rho, coeff, coeff_units)
        return float(strength + gravity)

    idx = int(np.searchsorted(v_keys, v_kms, side="right") - 1)
    idx = max(0, min(idx, int(v_keys.size - 2)))
    v_lo = float(v_keys[idx])
    v_hi = float(v_keys[idx + 1])
    weight = (v_kms - v_lo) / (v_hi - v_lo)

    coeff_lo = _COEFFS[v_lo]
    coeff_hi = _COEFFS[v_hi]
    strength_lo, gravity_lo = _q_d_star(np.asarray(s, dtype=float), rho, coeff_lo, coeff_units)
    strength_hi, gravity_hi = _q_d_star(np.asarray(s, dtype=float), rho, coeff_hi, coeff_units)

    strength = strength_lo * (1.0 - weight) + strength_hi * weight
    gravity = gravity_lo * (1.0 - weight) + gravity_hi * weight
    gravity_scale = _gravity_velocity_scale(np.asarray([v_kms], dtype=float))[0]
    return float(strength + gravity * gravity_scale)
