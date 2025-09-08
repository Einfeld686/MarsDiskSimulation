"""Particle size distribution (P1) with optional wavy correction.

This module provides a minimal three-slope particle size distribution (PSD)
that can mimic the short-term, non-steady behaviour of a collisional cascade.
An optional sinusoidal modulation adds the qualitative "wavy" pattern expected
when grains just above the blow-out limit are removed efficiently.

Two helper functions are exposed:

``update_psd_state``
    Construct a PSD state dictionary for a given size range.
``compute_kappa``
    Compute the mass opacity ``\kappa`` from a PSD state.
"""
from __future__ import annotations

from typing import Dict

import logging

import numpy as np

from ..errors import MarsDiskError

logger = logging.getLogger(__name__)


def update_psd_state(
    *,
    s_min: float,
    s_max: float,
    alpha: float,
    wavy_strength: float,
    n_bins: int = 40,
    rho: float = 3000.0,
) -> Dict[str, np.ndarray | float]:
    """Return a particle size distribution state.

    Parameters
    ----------
    s_min:
        Minimum grain radius in metres.
    s_max:
        Maximum grain radius in metres; must exceed ``s_min``.
    alpha:
        Base power-law slope for the smallest grains.
    wavy_strength:
        Amplitude of the sinusoidal "wavy" modulation.  Set to zero to
        suppress the effect.
    n_bins:
        Number of logarithmic size bins.
    rho:
        Material density of the grains in kg/m^3.

    Returns
    -------
    dict
        Dictionary containing ``sizes`` (bin centres), ``widths`` (bin widths),
        ``number`` (relative number density) and ``rho``.

    Raises
    ------
    MarsDiskError
        If ``s_min`` is not smaller than ``s_max`` or if ``n_bins`` is not
        positive.
    """
    if s_min >= s_max:
        raise MarsDiskError("s_min must be smaller than s_max")
    if n_bins <= 0:
        raise MarsDiskError("n_bins must be positive")

    # logarithmic bin edges and centres
    edges = np.logspace(np.log10(s_min), np.log10(s_max), n_bins + 1)
    centres = np.sqrt(edges[:-1] * edges[1:])
    widths = np.diff(edges)

    # three-slope power-law approximation
    s_break1 = s_min * 10.0
    s_break2 = s_max / 10.0
    slopes = np.empty_like(centres)
    slopes.fill(alpha + 1.5)  # large grains
    slopes[centres < s_break2] = alpha + 1.0
    slopes[centres < s_break1] = alpha

    number = (centres / s_min) ** (-slopes)

    if wavy_strength != 0.0:
        period = np.log(s_max / s_min)
        phase = np.log(centres / s_min)
        number *= 1.0 + wavy_strength * np.sin(2.0 * np.pi * phase / period)

    logger.info("PSD updated: s_min=%g m, s_max=%g m", s_min, s_max)
    return {
        "sizes": centres,
        "widths": widths,
        "number": number,
        "rho": rho,
        "s_min": s_min,
        "s_max": s_max,
    }


def compute_kappa(psd_state: Dict[str, np.ndarray | float]) -> float:
    """Compute the mass opacity ``\kappa`` from a PSD state (P1).

    The opacity is defined as

    ``\kappa = \int \pi s^2 n(s) ds / \int (4/3) \pi \rho s^3 n(s) ds``.

    Parameters
    ----------
    psd_state:
        Dictionary produced by :func:`update_psd_state`.

    Returns
    -------
    float
        Mass opacity in m^2/kg.
    """
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
    rho = float(psd_state["rho"])

    area = np.sum(np.pi * sizes**2 * number * widths)
    mass = np.sum((4.0 / 3.0) * np.pi * rho * sizes**3 * number * widths)

    return float(area / mass)


__all__ = ["update_psd_state", "compute_kappa"]
