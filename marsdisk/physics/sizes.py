"""Size-evolution helper functions."""

from __future__ import annotations

from typing import Optional

from ..errors import PhysicsError
from . import sublimation


def eval_ds_dt_sublimation(
    T: float,
    rho_bulk: float,
    params: sublimation.SublimationParams,
) -> float:
    """Return ``ds/dt`` (m/s) for sublimation-driven erosion of a grain.

    The Hertz–Knudsen–Langmuir mass flux ``J`` (kg m⁻² s⁻¹) yields
    ``t_sub = ρ s / J`` for a spherical grain.  Differentiating gives
    ``ds/dt = -J / ρ``.  Negative values therefore *increase* the lower
    size threshold when integrated.
    """

    if rho_bulk <= 0.0:
        raise PhysicsError("rho_bulk must be positive")
    J = sublimation.mass_flux_hkl(T, params)
    if J <= 0.0:
        return 0.0
    return -J / rho_bulk


__all__ = ["eval_ds_dt_sublimation"]
