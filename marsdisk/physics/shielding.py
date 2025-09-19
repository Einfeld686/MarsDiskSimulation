"""Self-shielding utilities for the disk surface layer (S0).

The surface opacity ``κ_surf`` obtained from the particle size distribution is
modified by the self-shielding factor ``Φ`` to yield an effective opacity
``κ_eff = Φ κ``.  From this, the surface density corresponding to optical depth
unity is ``Σ_{τ=1} = 1 / κ_eff``.  Functions in this module facilitate this
calculation and provide a helper to clip the surface density accordingly.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple
import numpy as np

from ..io import tables

# type alias for Φ interpolation function
type_Phi = Callable[[float, float, float], float]


def effective_kappa(
    kappa: float,
    tau: float,
    phi_fn: Optional[Callable[[float], float]],
) -> float:
    """Compute the effective opacity from Φ. Self-shielding Φ."""

    if phi_fn is None:
        return float(kappa)

    phi = float(phi_fn(tau))
    phi = float(np.clip(phi, 0.0, 1.0))
    return float(phi * kappa)


def sigma_tau1(kappa_eff: float) -> float:
    """Return Σ_{τ=1} derived from κ_eff. Self-shielding Φ."""

    if not np.isfinite(kappa_eff) or kappa_eff <= 0.0:
        return float(np.inf)
    return float(1.0 / kappa_eff)


def apply_shielding(
    kappa_surf: float,
    tau: float,
    w0: float,
    g: float,
    interp: type_Phi | None = None,
) -> Tuple[float, float]:
    """Return effective opacity and ``Σ_{τ=1}`` for given conditions.

    Parameters
    ----------
    kappa_surf:
        Surface mass opacity derived from the PSD (m² kg⁻¹).
    tau, w0, g:
        Optical depth and scattering properties passed to the Φ lookup.
    interp:
        Optional interpolation function; defaults to
        :func:`marsdisk.io.tables.interp_phi`.
    """
    func = tables.interp_phi if interp is None else interp

    def phi_wrapper(val_tau: float) -> float:
        return float(func(val_tau, w0, g))

    kappa_eff = effective_kappa(kappa_surf, tau, phi_wrapper)
    sigma_tau1_limit = sigma_tau1(kappa_eff)
    return kappa_eff, sigma_tau1_limit


def clip_to_tau1(sigma_surf: float, kappa_eff: float) -> float:
    """Clip ``Σ_surf`` so that it does not exceed ``Σ_{τ=1}``.

    Any negative result caused by numerical noise is set to zero to maintain
    non-negativity.
    """
    if kappa_eff <= 0.0:
        return max(0.0, sigma_surf)
    sigma_tau1_limit = sigma_tau1(kappa_eff)
    clipped = min(sigma_surf, sigma_tau1_limit)
    return 0.0 if clipped < 0.0 else clipped
