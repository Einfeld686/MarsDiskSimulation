from __future__ import annotations

"""Surface layer evolution and outflux (S1).

This module implements a minimal zero-dimensional model for the
surface number/mass density of grains susceptible to radiation-pressure
blow-out.  Only the optically thin top layer (``\tau\lesssim1``) is
assumed to receive direct irradiation; deeper layers are treated as
self-shaded and do not participate in the radiation-driven outflow.
This follows the conceptual picture of the thin illuminated skin
discussed by Takeuchi & Lin (2003).

The governing ordinary differential equation is

``dΣ_surf/dt = prod_rate - Σ_surf/t_blow - Σ_surf/t_coll - Σ_surf/t_sink``

where ``prod_rate`` is the area production rate of sub--blow-out grains
already mixed into the optically thin surface layer.  The blow-out
time-scale is ``t_blow = 1/Ω``.  Collisional erosion can optionally be
included via the Wyatt scaling.  Additional sinks such
as sublimation or gas drag are represented by a generic time-scale
``t_sink``.

The function :func:`step_surface_density_S1` advances the surface density
by a single implicit Euler step and returns the updated surface density
along with the instantaneous outflux and sink rates.  The outflux is
computed *after* the optical-depth clipping ``Σ_surf ≤ Σ_{τ=1}`` as
required by the specification.
"""

from dataclasses import dataclass
from typing import Optional
import logging

import numpy as np

from ..errors import MarsDiskError

logger = logging.getLogger(__name__)

TAU_MIN = 1e-12


def _safe_tcoll(Omega: float, tau: float | None) -> float | None:
    """Return ``t_coll`` or ``None`` when ``tau`` is effectively zero."""

    if tau is None or tau <= TAU_MIN:
        logger.info(
            "safe_tcoll: tau=%e <= TAU_MIN=%e; collisions disabled", tau, TAU_MIN
        )
        return None
    return 1.0 / (2.0 * Omega * max(tau, TAU_MIN))

__all__ = [
    "step_surface_density_S1",
    "wyatt_tcoll_S1",
    "step_surface",
    "compute_surface_outflux",
]


def wyatt_tcoll_S1(tau: float, Omega: float) -> float:
    """Return the Wyatt (2008) collisional time-scale for the surface layer.

    The expression follows ``t_coll ≈ T_orb/(4π τ)`` where ``T_orb`` is the
    orbital period ``2π/Ω``.  Combining the two gives ``t_coll = 1/(2Ωτ)``.
    ``tau`` must be positive and typically corresponds to the vertical
    optical depth of the disk.
    """

    if tau <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("tau and Omega must be positive")
    return 1.0 / (2.0 * Omega * tau)


@dataclass
class SurfaceStepResult:
    """Container returned by :func:`step_surface_density_S1`.

    Attributes
    ----------
    sigma_surf:
        Updated surface density after clipping.
    outflux:
        Surface outflux ``Σ_surf Ω`` (kg m⁻² s⁻¹).
    sink_flux:
        Additional sink flux ``Σ_surf / t_sink``.  Zero when
        ``t_sink`` is ``None``.
    """

    sigma_surf: float
    outflux: float
    sink_flux: float


def step_surface_density_S1(
    sigma_surf: float,
    prod_subblow_area_rate: float,
    dt: float,
    Omega: float,
    *,
    t_coll: float | None = None,
    t_sink: float | None = None,
    sigma_tau1: float | None = None,
) -> SurfaceStepResult:
    """Advance the surface density by one implicit Euler step (S1).

    Parameters
    ----------
    sigma_surf:
        Current surface mass density ``Σ_surf``.
        prod_subblow_area_rate:
        Production rate of sub--blow-out material per unit area after mixing.
    dt:
        Time step.
    Omega:
        Keplerian angular frequency; sets ``t_blow = 1/Ω``.
    t_coll:
        Optional collisional time-scale ``t_coll``.  When provided the
        loss term ``Σ_surf/t_coll`` is treated implicitly.
    t_sink:
        Optional additional sink time-scale representing sublimation or
        gas drag.  ``None`` disables the term.
    sigma_tau1:
        Optical-depth clipping ``Σ_{τ=1}``.  When provided the updated
        density is limited to ``min(Σ_surf, Σ_{τ=1})`` before computing
        fluxes.

    Returns
    -------
    SurfaceStepResult
        dataclass holding the updated density and associated fluxes.
    """

    if dt <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("dt and Omega must be positive")

    t_blow = 1.0 / Omega
    loss = 1.0 / t_blow
    if t_coll is not None and t_coll > 0.0:
        loss += 1.0 / t_coll
    if t_sink is not None and t_sink > 0.0:
        loss += 1.0 / t_sink

    numerator = sigma_surf + dt * prod_subblow_area_rate
    sigma_new = numerator / (1.0 + dt * loss)

    if sigma_tau1 is not None:
        sigma_new = float(min(sigma_new, sigma_tau1))

    outflux = sigma_new * Omega
    sink_flux = sigma_new / t_sink if (t_sink is not None and t_sink > 0.0) else 0.0
    logger.info(
        "step_surface_density_S1: dt=%e sigma=%e sigma_tau1=%e t_blow=%e t_coll=%e t_sink=%e outflux=%e",
        dt,
        sigma_new,
        sigma_tau1 if sigma_tau1 is not None else float("nan"),
        t_blow,
        t_coll if t_coll is not None else float("nan"),
        t_sink if t_sink is not None else float("nan"),
        outflux,
    )
    return SurfaceStepResult(sigma_new, outflux, sink_flux)


def compute_surface_outflux(sigma_surf: float, Omega: float) -> float:
    """Return the instantaneous outflux ``Σ_surf Ω``.

    This thin wrapper exists for API symmetry with :func:`step_surface` and
    simply evaluates the definition of the outflux.
    """

    if Omega <= 0.0:
        raise MarsDiskError("Omega must be positive")
    return sigma_surf * Omega


def step_surface(
    sigma_surf: float,
    prod_subblow_area_rate: float,
    dt: float,
    Omega: float,
    *,
    tau: float | None = None,
    t_coll: float | None = None,
    t_sink: float | None = None,
    sigma_tau1: float | None = None,
) -> SurfaceStepResult:
    """Alias for :func:`step_surface_density_S1` with optional Wyatt coupling.

    When ``t_coll`` is not supplied but a positive optical depth ``tau`` is
    given, the Wyatt collisional time-scale is inserted automatically via
    :func:`wyatt_tcoll_S1`.
    """

    if t_coll is None and tau is not None:
        t_coll = _safe_tcoll(Omega, tau)
    elif t_coll is not None and t_coll <= 0.0:
        t_coll = None
    return step_surface_density_S1(
        sigma_surf,
        prod_subblow_area_rate,
        dt,
        Omega,
        t_coll=t_coll,
        t_sink=t_sink,
        sigma_tau1=sigma_tau1,
    )
