"""Sublimation utilities based on the Hertz–Knudsen–Langmuir law.

This module provides tools to estimate sublimation mass fluxes and the
corresponding instantaneous-sink size for dust grains.  When saturation
vapour pressure data are unavailable a logistic placeholder is used as a
smooth approximation, allowing the interface to remain stable until
proper tables are supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math
import warnings

__all__ = [
    "SublimationParams",
    "p_sat_clausius",
    "mass_flux_hkl",
    "s_sink_from_timescale",
]

# local gas constant to avoid importing an external constants module
_R_GAS = 8.314462618  # J mol^-1 K^-1


@dataclass
class SublimationParams:
    """Parameters governing sublimation calculations.

    Parameters
    ----------
    mode:
        ``"hkl"`` to evaluate the full Hertz–Knudsen–Langmuir expression
        using saturation vapour pressure.  Any other value activates the
        logistic placeholder.
    alpha_evap:
        Evaporation coefficient :math:`\alpha` (0 < ``alpha_evap`` \le 1).
    mu:
        Molar mass in kg/mol.
    A, B:
        Clausius–Clapeyron coefficients such that
        ``log10(P_sat/Pa) = A - B/T``.  If either is ``None`` the logistic
        placeholder is used.
    T_sub:
        Nominal sublimation threshold for the logistic placeholder (K).
    s_ref:
        Reference size used to calibrate the placeholder (m).
    eta_instant:
        Fraction defining the "instantaneous" criterion.
    dT:
        Temperature width controlling the steepness of the logistic model.
    P_gas:
        Ambient vapour pressure (Pa); defaults to vacuum.
    """

    mode: str = "logistic"
    alpha_evap: float = 1.0
    mu: float = 0.1
    A: Optional[float] = None
    B: Optional[float] = None
    T_sub: float = 1300.0
    s_ref: float = 1e-6
    eta_instant: float = 0.1
    dT: float = 50.0
    P_gas: float = 0.0


def p_sat_clausius(T: float, params: SublimationParams) -> float:
    """Return the saturation vapour pressure ``P_sat`` in Pascals.

    The relation ``log10(P_sat/Pa) = A - B/T`` is used.  When the required
    parameters are missing a :class:`UserWarning` is emitted and ``nan`` is
    returned.
    """

    if params.A is None or params.B is None:
        warnings.warn(
            "P_sat parameters (A,B) missing; using logistic placeholder for J(T)."
        )
        return float("nan")
    return 10.0 ** (params.A - params.B / float(T))


def mass_flux_hkl(T: float, params: SublimationParams) -> float:
    """Return the sublimation mass flux ``J(T)`` in kg m^-2 s^-1.

    If ``params.mode`` is ``"hkl"`` *and* Clausius–Clapeyron coefficients
    are supplied, the Hertz–Knudsen–Langmuir expression is used:

    ``J = α (P_sat - P_gas) * sqrt( μ / (2π R T) )``.

    Otherwise a logistic placeholder ``J = exp((T - T_sub)/dT)`` is returned,
    providing a monotonic and differentiable approximation suitable for
    testing.
    """

    use_hkl = (
        params.mode.lower() == "hkl" and params.A is not None and params.B is not None
    )
    if use_hkl:
        P_sat = p_sat_clausius(T, params)
        P_ex = max(0.0, P_sat - params.P_gas)
        if P_ex <= 0.0:
            return 0.0
        root = math.sqrt(params.mu / (2.0 * math.pi * _R_GAS * T))
        return params.alpha_evap * P_ex * root

    # logistic placeholder: J0 * exp((T - T_sub)/dT)
    J0 = 1.0
    return J0 * math.exp((T - params.T_sub) / max(params.dT, 1.0))


def s_sink_from_timescale(
    T: float, rho: float, t_ref: float, params: SublimationParams
) -> float:
    """Return the instantaneous-sink size :math:`s_{\rm sink}`.

    The sublimation lifetime of a spherical grain of radius ``s`` is
    ``t_sub = ρ s / J(T)``.  Requiring ``t_sub \le η t_ref`` yields the
    expression ``s_sink = η t_ref J(T) / ρ`` implemented here.
    """

    if rho <= 0.0 or t_ref <= 0.0:
        raise ValueError("rho and t_ref must be positive")
    J = mass_flux_hkl(T, params)
    return params.eta_instant * t_ref * J / rho
