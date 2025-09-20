"""Radiation pressure and blow-out size relations (R1--R3).

This module provides utilities to evaluate the Planck-averaged radiation
pressure efficiency ``⟨Q_pr⟩``, the ratio ``β`` of radiation pressure to
gravity, and the corresponding blow-out grain size where ``β = 0.5``.

The implementation delegates the lookup of ``⟨Q_pr⟩`` to the table
interpolation helper in :mod:`marsdisk.io.tables`.  A different interpolation
function can be supplied for testing or when alternative tables are used.
"""
from __future__ import annotations

import logging
from numbers import Real
from pathlib import Path
from typing import Callable, Tuple

import numpy as np

from .. import constants
from ..io import tables

# type alias for a Q_pr interpolation function
type_QPr = Callable[[float, float], float]

_QPR_LOOKUP: type_QPr | None = tables.interp_qpr

logger = logging.getLogger(__name__)


def load_qpr_table(path: Path | str) -> type_QPr:
    """Load a table file and cache the interpolator. Planck averaged ⟨Q_pr⟩."""

    global _QPR_LOOKUP
    table_path = Path(path)
    _QPR_LOOKUP = tables.load_qpr_table(table_path)

    lookup = _QPR_LOOKUP
    table_obj = getattr(lookup, "__self__", None) if lookup is not None else None
    if table_obj is None and lookup is tables.interp_qpr:
        table_obj = getattr(tables, "_QPR_TABLE", None)

    if table_obj is not None and hasattr(table_obj, "s_vals") and hasattr(table_obj, "T_vals"):
        s_vals = np.asarray(table_obj.s_vals, dtype=float)
        T_vals = np.asarray(table_obj.T_vals, dtype=float)
        if s_vals.size and T_vals.size:
            logger.info(
                "Loaded ⟨Q_pr⟩ table from %s with s∈[%e, %e], T_M∈[%e, %e]",
                table_path,
                float(np.min(s_vals)),
                float(np.max(s_vals)),
                float(np.min(T_vals)),
                float(np.max(T_vals)),
            )
            return lookup

    logger.info("Loaded ⟨Q_pr⟩ table from %s", table_path)
    return lookup


def qpr_lookup(s: float, T_M: float, table: type_QPr | None = None) -> float:
    """Return the efficiency for a grain size and temperature. Planck averaged ⟨Q_pr⟩."""

    if not isinstance(s, Real):
        raise TypeError("grain size 's' must be a real number for ⟨Q_pr⟩ lookup")
    if not isinstance(T_M, Real):
        raise TypeError("temperature 'T_M' must be a real number for ⟨Q_pr⟩ lookup")
    if not np.isfinite(s):
        raise ValueError("grain size 's' must be finite for ⟨Q_pr⟩ lookup")
    if not np.isfinite(T_M):
        raise ValueError("temperature 'T_M' must be finite for ⟨Q_pr⟩ lookup")

    s_val = float(s)
    T_val = float(T_M)
    if s_val <= 0.0:
        raise ValueError("grain size 's' must be greater than 0 for ⟨Q_pr⟩ lookup")
    if T_val <= 0.0:
        raise ValueError("temperature 'T_M' must be greater than 0 for ⟨Q_pr⟩ lookup")

    func = table or _QPR_LOOKUP or tables.interp_qpr
    if not callable(func):
        raise TypeError("provided ⟨Q_pr⟩ interpolator must be callable")

    lookup = func
    table_obj = getattr(lookup, "__self__", None)
    if table_obj is None and lookup is tables.interp_qpr:
        table_obj = getattr(tables, "_QPR_TABLE", None)

    s_eval, T_eval = s_val, T_val
    clamp_msgs: list[str] = []
    if table_obj is not None and hasattr(table_obj, "s_vals") and hasattr(table_obj, "T_vals"):
        s_vals = np.asarray(table_obj.s_vals, dtype=float)
        T_vals = np.asarray(table_obj.T_vals, dtype=float)
        if s_vals.size:
            s_min = float(np.min(s_vals))
            s_max = float(np.max(s_vals))
            if s_eval < s_min or s_eval > s_max:
                clamped = float(np.clip(s_eval, s_min, s_max))
                clamp_msgs.append(
                    f"s={s_eval:.6e}->{clamped:.6e} (range {s_min:.6e}–{s_max:.6e})"
                )
                s_eval = clamped
        if T_vals.size:
            T_min = float(np.min(T_vals))
            T_max = float(np.max(T_vals))
            if T_eval < T_min or T_eval > T_max:
                clamped = float(np.clip(T_eval, T_min, T_max))
                clamp_msgs.append(
                    f"T_M={T_eval:.6e}->{clamped:.6e} (range {T_min:.6e}–{T_max:.6e})"
                )
                T_eval = clamped
    if clamp_msgs:
        logger.info("⟨Q_pr⟩ lookup clamped: %s", ", ".join(clamp_msgs))

    return float(lookup(s_eval, T_eval))


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
    if not isinstance(rho, Real):
        raise TypeError("material density 'rho' must be a real number for β")
    if not np.isfinite(rho):
        raise ValueError("material density 'rho' must be finite for β")
    if rho <= 0.0:
        raise ValueError("material density 'rho' must be greater than 0 for β")
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
    if not isinstance(rho, Real):
        raise TypeError("material density 'rho' must be a real number for blow-out search")
    if not np.isfinite(rho):
        raise ValueError("material density 'rho' must be finite for blow-out search")
    if rho <= 0.0:
        raise ValueError("material density 'rho' must be greater than 0 for blow-out search")
    if not isinstance(T_M, Real):
        raise TypeError("temperature 'T_M' must be a real number for blow-out search")
    if not np.isfinite(T_M):
        raise ValueError("temperature 'T_M' must be finite for blow-out search")
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise TypeError("'bounds' must be a tuple of two grain sizes for blow-out search")
    s_min, s_max = bounds
    if not isinstance(s_min, Real) or not isinstance(s_max, Real):
        raise TypeError("'bounds' values must be real numbers for blow-out search")
    if not np.isfinite(s_min) or not np.isfinite(s_max):
        raise ValueError("'bounds' values must be finite for blow-out search")
    if s_min <= 0.0:
        raise ValueError("bounds[0] must be greater than 0 for blow-out search")
    if s_max <= 0.0:
        raise ValueError("bounds[1] must be greater than 0 for blow-out search")
    if s_min >= s_max:
        raise ValueError("bounds[0] must be smaller than bounds[1] for blow-out search")
    if not isinstance(samples, int):
        raise TypeError("'samples' must be an integer for blow-out search")
    if samples < 2:
        raise ValueError("'samples' must be at least 2 for blow-out search")

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
