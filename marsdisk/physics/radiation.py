"""Radiation pressure and blow-out size relations (R1--R3).

This module provides utilities to evaluate the Planck-averaged radiation
pressure efficiency ``⟨Q_pr⟩``, the ratio ``β`` of radiation pressure to
gravity, and the corresponding blow-out grain size where ``β = 0.5``.

The implementation delegates the lookup of ``⟨Q_pr⟩`` to the table
interpolation helper in :mod:`marsdisk.io.tables`.  A different interpolation
function can be supplied for testing or when alternative tables are used.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Tuple

import numpy as np

from .. import constants
from ..io import tables

# type alias for a Q_pr interpolation function
type_QPr = Callable[[float, float], float]

_QPR_LOOKUP: type_QPr | None = tables.interp_qpr


def load_qpr_table(path: Path | str) -> type_QPr:
    """Load a table file and cache the interpolator. Planck averaged ⟨Q_pr⟩."""

    global _QPR_LOOKUP
    _QPR_LOOKUP = tables.load_qpr_table(path)
    return _QPR_LOOKUP


def qpr_lookup(s: float, T_M: float, table: type_QPr | None = None) -> float:
    """Return the efficiency for a grain size and temperature. Planck averaged ⟨Q_pr⟩."""

    if s <= 0.0:
        raise ValueError("grain size must be positive for ⟨Q_pr⟩ lookup")
    if T_M <= 0.0:
        raise ValueError("temperature must be positive for ⟨Q_pr⟩ lookup")

    func = table or _QPR_LOOKUP or tables.interp_qpr
    return float(func(s, T_M))


def planck_mean_qpr(
    s: float,
    T_M: float,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the same value as :func:`qpr_lookup`. Planck averaged ⟨Q_pr⟩."""

    if table is not None and interp is not None:
        raise TypeError("planck_mean_qpr received both 'table' and 'interp'")
    lookup = table if table is not None else interp
    return qpr_lookup(s, T_M, lookup)


def beta(
    s: float,
    rho: float,
    T_M: float,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Compute the ratio ``β`` of radiation pressure to gravity (R2).

    The expression follows directly from conservation of momentum using the
    luminosity of Mars ``L_M = 4π R_M^2 σ T_M^4`` and reads

    ``β = 3 L_M ⟨Q_pr⟩ / (16 π c G M_M ρ s)``.
    """
    if table is not None and interp is not None:
        raise TypeError("beta received both 'table' and 'interp'")
    lookup = table if table is not None else interp
    qpr = qpr_lookup(s, T_M, lookup)
    L_M = 4.0 * np.pi * constants.R_MARS**2 * constants.SIGMA_SB * T_M**4
    num = 3.0 * L_M * qpr
    den = 16.0 * np.pi * constants.C * constants.G * constants.M_MARS * rho * s
    return float(num / den)


def blowout_radius(
    rho: float,
    T_M: float,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
    bounds: Tuple[float, float] = (1e-9, 1e-2),
    samples: int = 256,
) -> float:
    """Estimate the grain radius where ``β = 0.5`` (R3).

    The function samples ``β(s)`` on a logarithmic grid and linearly
    interpolates the location where it crosses 0.5.  A ``RuntimeError`` is
    raised when the maximum ``β`` never exceeds 0.5, i.e. when no blow-out
    occurs for the given parameters.
    """

    if table is not None and interp is not None:
        raise TypeError("blowout_radius received both 'table' and 'interp'")
    lookup = table if table is not None else interp

    s_min, s_max = bounds
    s_grid = np.logspace(np.log10(s_min), np.log10(s_max), samples)
    kwargs = {"table": lookup} if lookup is not None else {}
    beta_vals = np.array([beta(s, rho, T_M, **kwargs) for s in s_grid])
    imax = int(np.argmax(beta_vals))
    if beta_vals[imax] <= 0.5:
        raise RuntimeError("β never reaches 0.5; blow-out does not occur")
    # Search on the descending branch for the 0.5 crossing
    tail = beta_vals[imax:]
    idx_offset = np.where(tail <= 0.5)[0][0]
    j = imax + idx_offset
    s1, s2 = s_grid[j - 1], s_grid[j]
    b1, b2 = beta_vals[j - 1], beta_vals[j]
    # linear interpolation
    return float(s1 + (0.5 - b1) * (s2 - s1) / (b2 - b1))
