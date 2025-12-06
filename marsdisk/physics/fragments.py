"""Fragmentation helpers and sublimation boundary utilities (F2).

The routines in this module now focus on exposing the sublimation boundary
``s_sub`` for use in the grain-size evolution (:math:`ds/dt`).  The legacy
``compute_s_min_F2`` helper is retained for compatibility but no longer
participates in the minimum-size selection at run time.
"""
from __future__ import annotations

import logging
import warnings

import numpy as np

from ..errors import MarsDiskError
from .sublimation import (
    SublimationParams,
    grain_temperature_graybody,
    s_sink_from_timescale,
)

logger = logging.getLogger(__name__)

__all__ = [
    "compute_q_r_F2",
    "compute_largest_remnant_mass_fraction_F2",
    "q_r_array",
    "largest_remnant_fraction_array",
    "s_sub_boundary",
    "compute_s_min_F2",
]


def q_r_array(m1: np.ndarray, m2: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Vectorised reduced specific kinetic energy ``Q_R``."""

    m1_arr, m2_arr, v_arr = np.broadcast_arrays(
        np.asarray(m1, dtype=float),
        np.asarray(m2, dtype=float),
        np.asarray(v, dtype=float),
    )
    if np.any(v_arr < 0.0):
        raise MarsDiskError("velocity must be non-negative")
    m_tot = m1_arr + m2_arr
    valid = (m1_arr > 0.0) & (m2_arr > 0.0) & (m_tot > 0.0)
    q_r = np.zeros_like(m1_arr, dtype=float)
    if not np.any(valid):
        return q_r
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = np.where(valid, m1_arr * m2_arr / m_tot, 0.0)
        q_r = np.where(valid, 0.5 * mu * v_arr * v_arr / m_tot, 0.0)
    return q_r


def largest_remnant_fraction_array(q_r: np.ndarray, q_rd_star: np.ndarray) -> np.ndarray:
    """Vectorised largest-remnant fraction ``M_LR/M_tot``."""

    q_r_arr, q_star_arr = np.broadcast_arrays(
        np.asarray(q_r, dtype=float),
        np.asarray(q_rd_star, dtype=float),
    )
    valid = q_star_arr > 0.0
    frac = np.zeros_like(q_r_arr, dtype=float)
    if not np.any(valid):
        return frac
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = 0.5 * (2.0 - q_r_arr / q_star_arr)
    frac_valid = np.clip(raw, 0.0, 1.0, out=np.zeros_like(raw), where=valid)
    frac[valid] = frac_valid[valid]
    return frac


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
    logger.debug("compute_q_r_F2: m1=%e m2=%e v=%e -> Q_R=%e", m1, m2, v, q_r)
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
    logger.debug(
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
    params = sub_params or SublimationParams()
    radius_m = getattr(params, "runtime_orbital_radius_m", None)
    if radius_m is None:
        warnings.warn(
            "s_sub_boundary: runtime_orbital_radius_m not set on SublimationParams; reverting to planet temperature."
        )
        T_eval = T
    else:
        try:
            T_eval = grain_temperature_graybody(T, radius_m)
        except ValueError as exc:
            warnings.warn(
                f"s_sub_boundary: failed to evaluate grey-body temperature ({exc}); using planet temperature."
            )
            T_eval = T
    if T_eval < T_sub:
        boundary = 0.0
    else:
        if t_ref is not None and rho is not None:
            boundary = s_sink_from_timescale(T_eval, rho, t_ref, params)
        else:
            warnings.warn(
                "s_sub_boundary: t_ref or rho not provided; using fixed s_sink=1e-3 m as a conservative fallback."
            )
            boundary = 1e-3
    boundary = max(0.0, float(boundary))
    logger.info(
        "s_sub_boundary: T_M=%f T_d=%f T_sub=%f r=%s -> s_sub=%s",
        T,
        T_eval,
        T_sub,
        radius_m,
        boundary,
    )
    return boundary


def compute_s_min_F2(
    a_blow: float,
    T: float,
    T_sub: float = 1300.0,
    *,
    t_ref: float | None = None,
    rho: float | None = None,
    sub_params: SublimationParams | None = None,
) -> float:
    """Legacy helper that now returns the blow-out size only.

    Notes
    -----
    This routine previously combined ``a_blow`` with the sublimation boundary
    ``s_sub``.  The disk model now defines the effective minimum exclusively as
    ``max(s_min_cfg, a_blow)`` (E.008), leaving sublimation to act through the
    :math:`ds/dt` evolution path.  Callers should therefore stop relying on
    this helper and apply the configured minimum grain size together with
    :func:`marsdisk.physics.radiation.blowout_radius` directly.
    """

    _ = (T, T_sub, t_ref, rho, sub_params)
    if a_blow <= 0.0:
        raise MarsDiskError("a_blow must be positive")
    warnings.warn(
        "compute_s_min_F2 is deprecated; use max(s_min_cfg, blowout_radius) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    s_min = max(a_blow, 0.0)
    logger.info("compute_s_min_F2: a_blow=%e -> s_min=%s", a_blow, s_min)
    return float(s_min)
