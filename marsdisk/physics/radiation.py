"""Radiation pressure and blow-out size relations (R1--R3).

This module provides utilities to evaluate the Planck-averaged radiation
pressure efficiency ``⟨Q_pr⟩``, the ratio ``β`` of radiation pressure to
gravity, and the corresponding blow-out grain size where ``β = 0.5``.

The implementation delegates the lookup of ``⟨Q_pr⟩`` to the table
interpolation helper in :mod:`marsdisk.io.tables`.  A different interpolation
function can be supplied for testing or when alternative tables are used.
"""
from __future__ import annotations

from typing import Callable, Tuple

import numpy as np

from .. import constants
from ..io import tables

# type alias for a Q_pr interpolation function
type_QPr = Callable[[float, float], float]


def planck_mean_qpr(s: float, T_M: float, interp: type_QPr | None = None) -> float:
    """Return the Planck-mean radiation pressure efficiency ``⟨Q_pr⟩``.

    Parameters
    ----------
    s:
        Grain radius in metres.
    T_M:
        Surface temperature of Mars in Kelvin.
    interp:
        Optional custom interpolation function.  Defaults to
        :func:`marsdisk.io.tables.interp_qpr`.
    """
    func = tables.interp_qpr if interp is None else interp
    return float(func(s, T_M))


def beta(
    s: float,
    rho: float,
    T_M: float,
    interp: type_QPr | None = None,
) -> float:
    """Compute the ratio ``β`` of radiation pressure to gravity (R2).

    The expression follows directly from conservation of momentum using the
    luminosity of Mars ``L_M = 4π R_M^2 σ T_M^4`` and reads

    ``β = 3 L_M ⟨Q_pr⟩ / (16 π c G M_M ρ s)``.
    """
    qpr = planck_mean_qpr(s, T_M, interp)
    L_M = 4.0 * np.pi * constants.R_MARS**2 * constants.SIGMA_SB * T_M**4
    num = 3.0 * L_M * qpr
    den = 16.0 * np.pi * constants.C * constants.G * constants.M_MARS * rho * s
    return float(num / den)


def blowout_radius(
    rho: float,
    T_M: float,
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

    s_min, s_max = bounds
    s_grid = np.logspace(np.log10(s_min), np.log10(s_max), samples)
    beta_vals = np.array([beta(s, rho, T_M, interp) for s in s_grid])
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
