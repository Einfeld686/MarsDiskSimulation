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
import math

from ..errors import MarsDiskError
from .sublimation import (
    SublimationParams,
    grain_temperature_graybody,
    s_sink_from_timescale,
)

__all__ = [
    "SinkOptions",
    "SinkTimescaleResult",
    "gas_drag_timescale",
    "total_sink_timescale",
]

logger = logging.getLogger(__name__)


@dataclass
class SinkOptions:
    """Configuration switches for sink processes."""

    enable_sublimation: bool = False
    sub_params: SublimationParams = field(default_factory=SublimationParams)
    # Gas drag is disabled by default.  In gas-poor debris disks the
    # dynamics are governed primarily by radiation pressure and
    # collisions, making drag a secondary effect (see Takeuchi & Lin
    # 2003; Strubbe & Chiang 2006).
    enable_gas_drag: bool = False
    rho_g: float = 0.0  # ambient gas density [kg m^-3]


@dataclass
class SinkTimescaleResult:
    """Return value capturing the combined sink diagnostics."""

    t_sink: Optional[float]
    components: dict[str, Optional[float]]
    dominant_sink: Optional[str]
    T_eval: float
    s_ref: float

    @property
    def sublimation_fraction(self) -> float:
        """Fraction of the sink flux attributable to sublimation."""

        if self.t_sink is None:
            return 0.0
        sub_timescale = self.components.get("sublimation")
        if sub_timescale is None:
            return 0.0
        return 1.0 if self.dominant_sink == "sublimation" else 0.0


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
    T_use: float,
    rho_p: float,
    Omega: float,
    opts: SinkOptions,
    *,
    s_ref: float = 1e-6,
) -> SinkTimescaleResult:
    """Return the combined sink time-scale.

    The function evaluates the configured sinks and returns the shortest
    time-scale.  ``None`` is returned when all sinks are disabled.  ``T_use``
    is the resolved Mars-facing temperature fed into radiation (either the
    YAML override ``radiation.TM_K`` or ``temps.T_M``).  The parameter
    ``s_ref`` denotes the representative grain size used for the sublimation
    lifetime (when ``mode='hkl_timescale'``) and for the gas-drag estimate.
    """

    if Omega <= 0.0:
        raise MarsDiskError("Omega must be positive")
    if s_ref <= 0.0:
        raise MarsDiskError("s_ref must be positive")

    components: dict[str, Optional[float]] = {"sublimation": None, "gas_drag": None}
    entries: list[tuple[str, float]] = []
    t_orb = 2.0 * math.pi / Omega
    params = opts.sub_params
    radius_m = getattr(params, "runtime_orbital_radius_m", None)
    if radius_m is not None:
        try:
            T_eval = grain_temperature_graybody(T_use, radius_m)
        except ValueError as exc:
            logger.warning(
                "total_sink_timescale: invalid runtime_orbital_radius_m (%s); using planet temperature. (%s)",
                radius_m,
                exc,
            )
            T_eval = T_use
    else:
        T_eval = T_use

    if opts.enable_sublimation:
        s_sink = s_sink_from_timescale(T_eval, rho_p, t_orb, params)
        if s_sink > 0.0:
            sub_timescale = t_orb * s_ref / s_sink
            components["sublimation"] = sub_timescale
            entries.append(("sublimation", sub_timescale))

    if opts.enable_gas_drag and opts.rho_g > 0.0:
        drag_timescale = gas_drag_timescale(s_ref, rho_p, opts.rho_g)
        components["gas_drag"] = drag_timescale
        entries.append(("gas_drag", drag_timescale))

    if not entries:
        logger.info("total_sink_timescale: no active sinks")
        return SinkTimescaleResult(
            t_sink=None,
            components=components,
            dominant_sink=None,
            T_eval=T_eval,
            s_ref=s_ref,
        )
    dominant_sink, t_min = min(entries, key=lambda item: item[1])
    logger.info(
        "total_sink_timescale: T_use=%f T_eval=%f t_orb=%e -> t_sink=%e (dominant=%s)",
        T_use,
        T_eval,
        t_orb,
        t_min,
        dominant_sink,
    )
    return SinkTimescaleResult(
        t_sink=float(t_min),
        components=components,
        dominant_sink=dominant_sink,
        T_eval=T_eval,
        s_ref=s_ref,
    )
