"""Fragmentation helpers and sublimation boundary utilities (F2).

This module exposes helpers to determine the minimum grain size in the
particle size distribution by combining the blow-out limit with a
possible sublimation boundary.  The latter can be evaluated in a
physically consistent way when the relevant time-scale information is
provided, otherwise a conservative fixed cut-off is used.
"""
from __future__ import annotations

import logging
import warnings

from ..errors import MarsDiskError
from .sublimation import SublimationParams, s_sink_from_timescale

logger = logging.getLogger(__name__)

__all__ = [
    "compute_q_r_F2",
    "compute_largest_remnant_mass_fraction_F2",
    "s_sub_boundary",
    "compute_s_min_F2",
]


def compute_q_r_F2(m1: float, m2: float, v: float) -> float:
    """Return the reduced specific kinetic energy :math:`Q_R`.

    The quantity is defined as

    ``Q_R = 0.5 * μ * v**2 / M_tot`` with ``μ`` the reduced mass and
    ``M_tot = m1 + m2`` the total mass of the colliding bodies.

    Parameters
    ----------
    m1, m2:
        Masses of the projectile and the target in kilograms.
    v:
        Impact velocity in metres per second.

    Returns
    -------
    float
        The specific impact energy in joules per kilogram.
    """

    if m1 <= 0.0 or m2 <= 0.0:
        raise MarsDiskError("masses must be positive")
    if v < 0.0:
        raise MarsDiskError("velocity must be non-negative")
    m_tot = m1 + m2
    mu = m1 * m2 / m_tot
    q_r = 0.5 * mu * v * v / m_tot
    logger.info(
        "compute_q_r_F2: m1=%e m2=%e v=%e -> Q_R=%e", m1, m2, v, q_r
    )
    return float(q_r)


def compute_largest_remnant_mass_fraction_F2(
    m1: float, m2: float, v: float, q_rd_star: float
) -> float:
    """Return the mass fraction of the largest remnant.

    The approximation from Leinhardt & Stewart (2012) is used:

    ``M_LR/M_tot ≈ 0.5 * (2 - Q_R / Q_RD_star)``.

    Values are clipped to the physical range [0, 1].

    Parameters
    ----------
    m1, m2:
        Masses of the projectile and target in kilograms.
    v:
        Impact velocity in metres per second.
    q_rd_star:
        Catastrophic disruption threshold :math:`Q_{RD}^*` in J/kg.
    """

    if q_rd_star <= 0.0:
        raise MarsDiskError("q_rd_star must be positive")
    q_r = compute_q_r_F2(m1, m2, v)
    frac = 0.5 * (2.0 - q_r / q_rd_star)
    frac = max(0.0, min(1.0, frac))
    logger.info(
        "compute_largest_remnant_mass_fraction_F2: m1=%e m2=%e v=%e q_rd_star=%e -> frac=%f",
        m1,
        m2,
        v,
        q_rd_star,
        frac,
    )
    return float(frac)


def s_sub_boundary(
    T: float,
    T_sub: float = 1300.0,
    *,
    t_ref: float | None = None,
    rho: float | None = None,
    sub_params: SublimationParams | None = None,
) -> float:
    """Return the sublimation boundary size ``s_sub``.

    Parameters
    ----------
    T:
        Grain temperature in Kelvin.
    T_sub:
        Nominal sublimation threshold.  For ``T < T_sub`` the boundary is
        zero.  For hotter grains an instantaneous-sink size is returned when
        both ``t_ref`` and ``rho`` are supplied.  Missing information triggers
        a warning and a conservative fallback of ``1e-3`` metres.
    t_ref, rho:
        Reference time scale and material density required for the
        time-scale consistent computation.
    sub_params:
        Optional :class:`SublimationParams` instance controlling the
        sublimation model.
    """

    if T < 0.0:
        raise MarsDiskError("temperature must be non-negative")
    if T < T_sub:
        boundary = 0.0
    else:
        if t_ref is not None and rho is not None:
            params = sub_params or SublimationParams()
            boundary = s_sink_from_timescale(T, rho, t_ref, params)
        else:
            warnings.warn(
                "s_sub_boundary: t_ref or rho not provided; using fixed s_sink=1e-3 m as a conservative fallback."
            )
            boundary = 1e-3
    logger.info("s_sub_boundary: T=%f T_sub=%f -> s_sub=%s", T, T_sub, boundary)
    return float(boundary)


def compute_s_min_F2(
    a_blow: float,
    T: float,
    T_sub: float = 1300.0,
    *,
    t_ref: float | None = None,
    rho: float | None = None,
    sub_params: SublimationParams | None = None,
) -> float:
    """Return ``s_min`` as the maximum of ``a_blow`` and ``s_sub``.

    The additional keyword arguments enable time-scale consistent sublimation
    boundaries while remaining backward compatible.  When omitted, the
    function behaves as before and applies only the blow-out size.
    """

    if a_blow <= 0.0:
        raise MarsDiskError("a_blow must be positive")
    s_sub = s_sub_boundary(
        T,
        T_sub,
        t_ref=t_ref,
        rho=rho,
        sub_params=sub_params,
    )
    s_min = max(a_blow, s_sub)
    logger.info(
        "compute_s_min_F2: a_blow=%e s_sub=%s -> s_min=%s", a_blow, s_sub, s_min
    )
    return float(s_min)
