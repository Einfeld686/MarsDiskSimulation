"""Radial grid utilities for the Mars disk model.

The current implementation supports a zero dimensional (0D) mode in which a
single orbital radius is considered.  A light-weight one dimensional (1D)
radial grid class is provided as a skeleton for future extensions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from . import constants


def omega_kepler(r: float) -> float:
    """Return the Keplerian angular frequency :math:`\Omega(r)`.

    Parameters
    ----------
    r:
        Orbital radius in metres.

    Returns
    -------
    float
        Angular frequency in radians per second.
    """
    mu = constants.G * constants.M_MARS
    return float(np.sqrt(mu / r**3))


def v_kepler(r: float) -> float:
    """Return the Keplerian orbital velocity :math:`v_K(r)`.

    Parameters
    ----------
    r:
        Orbital radius in metres.

    Returns
    -------
    float
        Orbital speed in metres per second.
    """
    mu = constants.G * constants.M_MARS
    return float(np.sqrt(mu / r))


@dataclass
class RadialGrid:
    """Minimal 1D radial grid.

    Parameters
    ----------
    r:
        Cell centre radii (m).
    edges:
        Radii at cell edges (m); length ``len(r)+1``.
    areas:
        Surface areas of the annular cells, ``2π r Δr`` (m²).
    """

    r: np.ndarray
    edges: np.ndarray
    areas: np.ndarray

    @classmethod
    def from_edges(cls, edges: Iterable[float]) -> "RadialGrid":
        """Construct grid from an iterable of cell edge locations.

        The edges are converted to a NumPy array of floats.  Cell centres and
        areas are derived assuming axisymmetry.
        """
        edges = np.asarray(list(edges), dtype=float)
        if edges.ndim != 1 or edges.size < 2:
            raise ValueError("edges must be a one dimensional array with >=2 entries")
        r = 0.5 * (edges[:-1] + edges[1:])
        dr = np.diff(edges)
        areas = 2.0 * np.pi * r * dr
        return cls(r=r, edges=edges, areas=areas)

    @classmethod
    def linear(cls, r_min: float, r_max: float, n: int) -> "RadialGrid":
        """Generate a grid with linearly spaced edges."""
        edges = np.linspace(r_min, r_max, n + 1)
        return cls.from_edges(edges)

def omega(r: float) -> float:      # alias
    return omega_kepler(r)

def v_keplerian(r: float) -> float:  # alias
    return v_kepler(r)
