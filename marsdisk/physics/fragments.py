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

__all__ = ["s_sub_boundary", "compute_s_min_F2"]


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
