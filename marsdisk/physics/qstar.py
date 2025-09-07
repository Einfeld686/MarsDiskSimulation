from __future__ import annotations

"""Specific disruption energy model (F1)."""

from typing import Dict, Tuple

from ..errors import MarsDiskError

__all__ = ["compute_q_d_star_F1"]

# Coefficients for Benz & Asphaug (1999) power-law at reference velocities in km/s
# Values correspond to basalt-like material as in Leinhardt & Stewart (2012).
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


def compute_q_d_star_F1(s: float, rho: float, v_kms: float) -> float:
    """Return the catastrophic disruption threshold ``Q_D^*``.

    The Benz & Asphaug (1999) size-dependent law is evaluated and then
    linearly interpolated in velocity between the 3 and 5 km/s reference
    values following Leinhardt & Stewart (2012).  Velocities outside this
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
