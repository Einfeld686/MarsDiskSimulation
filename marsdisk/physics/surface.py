from __future__ import annotations

"""Surface layer evolution and outflux (S1).

This module implements a minimal zero-dimensional model for the surface
number/mass density of grains susceptible to radiation-pressure
blow-out.  Only the optically thin top layer (``\tau\lesssim1``) is
assumed to receive direct irradiation; deeper layers are treated as
self-shaded and do not participate in the radiation-driven outflow.
The loss terms follow the gas-poor, optically thin picture in
[@StrubbeChiang2006_ApJ648_652], while the gas-rich surface-flow solution
[@TakeuchiLin2003_ApJ593_524; @TakeuchiLin2002_ApJ581_1344; @Shadmehri2007_MNRAS378_1365]
remains an optional path guarded by ``ALLOW_TL2003`` (disabled by default
per the specification).

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
    return 1.0 / (Omega * max(tau, TAU_MIN))

__all__ = [
    "step_surface_density_S1",
    "wyatt_tcoll_S1",
    "step_surface",
    "compute_surface_outflux",
]


def wyatt_tcoll_S1(tau: float, Omega: float) -> float:
    """Return the Strubbe & Chiang (2006) collisional time-scale. [@StrubbeChiang2006_ApJ648_652]

    The expression ``t_{\mathrm{coll}} = 1/(\Omega\,\tau_{\perp})`` reduces to the
    same scaling highlighted by Wyatt (2008) but cites the optically thin
    derivation in Strubbe & Chiang (2006).  ``tau`` must be positive and
    typically corresponds to the vertical optical depth of the disk.
    """

    if tau <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("tau and Omega must be positive")
    return 1.0 / (Omega * tau)


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
    enable_blowout: bool = True,
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
    enable_blowout:
        Toggle for the radiation-pressure loss term.  Disable to remove the
        ``1/t_blow`` contribution and force the returned outflux to zero.

    Returns
    -------
    SurfaceStepResult
        dataclass holding the updated density and associated fluxes.
    """

    if dt <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("dt and Omega must be positive")

    t_blow = 1.0 / Omega
    loss = 0.0
    if enable_blowout:
        loss += 1.0 / t_blow
    if t_coll is not None and t_coll > 0.0:
        loss += 1.0 / t_coll
    if t_sink is not None and t_sink > 0.0:
        loss += 1.0 / t_sink

    numerator = sigma_surf + dt * prod_subblow_area_rate
    sigma_new = numerator / (1.0 + dt * loss)

    if sigma_tau1 is not None:
        sigma_new = float(min(sigma_new, sigma_tau1))

    outflux = sigma_new * Omega if enable_blowout else 0.0
    sink_flux = sigma_new / t_sink if (t_sink is not None and t_sink > 0.0) else 0.0
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "step_surface_density_S1: dt=%e sigma=%e sigma_tau1=%e t_blow=%e t_coll=%e t_sink=%e outflux=%e blowout=%s",
            dt,
            sigma_new,
            sigma_tau1 if sigma_tau1 is not None else float("nan"),
            t_blow,
            t_coll if t_coll is not None else float("nan"),
            t_sink if t_sink is not None else float("nan"),
            outflux,
            enable_blowout,
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
    enable_blowout: bool = True,
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
        enable_blowout=enable_blowout,
    )
