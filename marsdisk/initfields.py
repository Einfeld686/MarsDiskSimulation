from __future__ import annotations

"""Deterministic mapping from disk-scale inputs to local surface densities."""

import math
from typing import Optional

from . import constants
from .schema import DiskGeometry, InnerDiskMass, Surface


def sigma_from_mass(mass_cfg: InnerDiskMass, geom: DiskGeometry, r: Optional[float] = None) -> float:
    """Return the mid-plane surface density ``Σ(r)``.

    Parameters
    ----------
    mass_cfg:
        Configuration describing the total mass of the inner disk.
    geom:
        Geometric extent of the disk in Mars radii.
    r:
        Optional evaluation radius in metres.  Defaults to the mid-point of
        the interval ``[r_in, r_out]``.
    """

    r_in = geom.r_in_RM * constants.R_MARS
    r_out = geom.r_out_RM * constants.R_MARS
    r_eval = 0.5 * (r_in + r_out) if r is None else r

    if mass_cfg.use_Mmars_ratio:
        M_in = mass_cfg.M_in_ratio * constants.M_MARS
    else:
        M_in = mass_cfg.M_in_ratio

    p = geom.p_index
    if geom.r_profile == "uniform" or abs(p) < 1e-12:
        Sigma = M_in / (math.pi * (r_out**2 - r_in**2))
        return float(Sigma)

    # power-law profile Σ = Σ0 (r/r_in)^-p
    if abs(p - 2.0) < 1e-8:
        denom = 2.0 * math.pi * math.log(r_out / r_in)
    else:
        denom = 2.0 * math.pi * (r_out ** (2 - p) - r_in ** (2 - p)) / (2 - p)
    Sigma0 = M_in / denom
    Sigma_r = Sigma0 * (r_eval / r_in) ** (-p)
    return float(Sigma_r)


def initial_surface_density(sigma_mid: float, sigma_tau1: Optional[float], surf_cfg: Surface) -> float:
    """Map mid-plane ``Σ`` to initial surface density.

    The default policy clips the surface layer to the optical depth unity limit
    ``Σ_{τ=1}`` when available.
    """

    if surf_cfg.sigma_surf_init_override is not None:
        return surf_cfg.sigma_surf_init_override

    if surf_cfg.init_policy == "clip_by_tau1" and sigma_tau1 is not None:
        return float(min(sigma_mid, sigma_tau1))

    return float(sigma_mid)
