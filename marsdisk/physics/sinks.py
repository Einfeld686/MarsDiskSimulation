from __future__ import annotations

"""Additional sink time-scales for sublimation and gas drag.

The helper functions in this module provide crude estimates for
non-collisional loss mechanisms affecting surface material.  Only the
functionality required by the unit tests is implemented; the expressions
are intentionally simple but preserve the qualitative behaviour: enabling
a sink leads to a shorter effective lifetime of surface particles.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

from ..errors import MarsDiskError
from .sublimation import (
    SublimationParams,
    s_sink_from_timescale,
    mass_flux_hkl,
)

__all__ = [
    "SinkOptions",
    "gas_drag_timescale",
    "total_sink_timescale",
]

logger = logging.getLogger(__name__)


@dataclass
class SinkOptions:
    """Configuration switches for sink processes."""

    enable_sublimation: bool = False
    sub_params: SublimationParams = field(default_factory=SublimationParams)
    enable_gas_drag: bool = False
    rho_g: float = 0.0  # ambient gas density [kg m^-3]


def gas_drag_timescale(s: float, rho_p: float, rho_g: float, c_s: float = 500.0) -> float:
    """Return an order-of-magnitude gas drag stopping time-scale.

    A simple Epstein-like relation ``t_drag ≈ ρ_p s / (ρ_g c_s)`` is used
    with a fiducial sound speed ``c_s``.  The constant is not critical for
    the tests which only probe qualitative behaviour.
    """

    if rho_p <= 0.0 or rho_g <= 0.0 or s <= 0.0:
        raise MarsDiskError("s, rho_p and rho_g must be positive")
    return rho_p * s / (rho_g * c_s)


def total_sink_timescale(
    T: float,
    rho_p: float,
    Omega: float,
    opts: SinkOptions,
    *,
    s_ref: float = 1e-6,
) -> Optional[float]:
    """Return the combined sink time-scale.

    The function evaluates the configured sinks and returns the shortest
    time-scale.  ``None`` is returned when all sinks are disabled.  The
    parameter ``s_ref`` denotes the representative grain size used for the
    sublimation lifetime (when ``mode='hkl_timescale'``) and for the
    gas-drag estimate.
    """

    times: list[float] = []
    t_ref = 1.0 / Omega

    if opts.enable_sublimation:
        mode = opts.sub_params.mode.lower()
        if mode == "hkl_timescale":
            J = mass_flux_hkl(T, opts.sub_params)
            if J > 0.0:
                times.append(rho_p * s_ref / J)
        else:
            s_sink = s_sink_from_timescale(T, rho_p, t_ref, opts.sub_params)
            if s_sink > 0.0:
                times.append(opts.sub_params.eta_instant * t_ref)

    if opts.enable_gas_drag and opts.rho_g > 0.0:
        times.append(gas_drag_timescale(s_ref, rho_p, opts.rho_g))

    if not times:
        logger.info("total_sink_timescale: no active sinks")
        return None
    t_min = float(min(times))
    logger.info("total_sink_timescale: t_sink=%e", t_min)
    return t_min
