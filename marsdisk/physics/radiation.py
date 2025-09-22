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
from typing import Callable, Optional

import numpy as np

from .. import constants
from ..io import tables

# type alias for a Q_pr interpolation function
type_QPr = Callable[[float, float], float]

_QPR_LOOKUP: type_QPr | None = tables.interp_qpr

DEFAULT_Q_PR: float = 1.0
DEFAULT_RHO: float = 3000.0
DEFAULT_T_M: float = 2000.0
T_M_RANGE: tuple[float, float] = (1000.0, 6000.0)
BLOWOUT_BETA_THRESHOLD: float = 0.5

_DEFAULT_QPR_LOGGED = False

logger = logging.getLogger(__name__)


def _validate_size(value: float, *, name: str = "s") -> float:
    if not isinstance(value, Real):
        raise TypeError(f"grain size '{name}' must be a real number")
    if not np.isfinite(value):
        raise ValueError(f"grain size '{name}' must be finite")
    if value <= 0.0:
        raise ValueError(f"grain size '{name}' must be greater than 0")
    return float(value)


def _validate_density(value: Optional[float]) -> float:
    if value is None:
        logger.info("No material density provided; using default %.1f kg/m^3", DEFAULT_RHO)
        return DEFAULT_RHO
    if not isinstance(value, Real):
        raise TypeError("material density 'rho' must be a real number")
    if not np.isfinite(value):
        raise ValueError("material density 'rho' must be finite")
    if value <= 0.0:
        raise ValueError("material density 'rho' must be greater than 0")
    return float(value)


def _validate_temperature(value: Optional[float]) -> float:
    if value is None:
        logger.info("No Mars surface temperature provided; using default %.1f K", DEFAULT_T_M)
        return DEFAULT_T_M
    if not isinstance(value, Real):
        raise TypeError("temperature 'T_M' must be a real number")
    if not np.isfinite(value):
        raise ValueError("temperature 'T_M' must be finite")
    Tmin, Tmax = T_M_RANGE
    if not (Tmin <= value <= Tmax):
        raise ValueError(f"temperature 'T_M' must lie within [{Tmin}, {Tmax}] K")
    return float(value)


def _validate_qpr(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, Real):
        raise TypeError("Q_pr must be a real number if provided")
    if not np.isfinite(value):
        raise ValueError("Q_pr must be finite if provided")
    if value <= 0.0:
        raise ValueError("Q_pr must be greater than 0 if provided")
    return float(value)


def _resolve_qpr(
    s: float,
    T_M: float,
    Q_pr: Optional[float],
    table: type_QPr | None,
    interp: type_QPr | None,
) -> float:
    global _DEFAULT_QPR_LOGGED
    Q_pr = _validate_qpr(Q_pr)
    if table is not None and interp is not None:
        raise TypeError("Q_pr resolution received both 'table' and 'interp'")
    if Q_pr is not None:
        return Q_pr

    lookup = table if table is not None else interp
    if lookup is not None:
        return qpr_lookup(s, T_M, lookup)

    if _QPR_LOOKUP is not None:
        lookup = _QPR_LOOKUP
        table_obj = getattr(lookup, "__self__", None)
        if table_obj is None and lookup is tables.interp_qpr:
            table_obj = getattr(tables, "_QPR_TABLE", None)
        if table_obj is not None:
            return qpr_lookup(s, T_M, lookup)

    if not _DEFAULT_QPR_LOGGED:
        logger.info("Using grey-body default ⟨Q_pr⟩=%.2f", DEFAULT_Q_PR)
        _DEFAULT_QPR_LOGGED = True
    return DEFAULT_Q_PR


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
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the effective grey-body ⟨Q_pr⟩, defaulting to unity."""

    s_val = _validate_size(s)
    T_val = _validate_temperature(T_M)
    return _resolve_qpr(s_val, T_val, Q_pr, table, interp)


def beta(
    s: float,
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Compute the ratio ``β`` of radiation pressure to gravity (R2).

    The expression follows directly from conservation of momentum using the
    luminosity of Mars ``L_M = 4π R_M^2 σ T_M^4`` and reads

    ``β = 3 L_M ⟨Q_pr⟩ / (16 π c G M_M ρ s)``.
    """
    s_val = _validate_size(s)
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    qpr = _resolve_qpr(s_val, T_val, Q_pr, table, interp)
    numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
    denominator = 4.0 * constants.G * constants.M_MARS * constants.C * rho_val * s_val
    return float(numerator / denominator)


def blowout_radius(
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the blow-out grain size ``s_blow`` for ``β = 0.5`` (R3)."""

    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    qpr = _resolve_qpr(1.0, T_val, Q_pr, table, interp)
    numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
    denominator = 2.0 * constants.G * constants.M_MARS * constants.C * rho_val
    return float(numerator / denominator)
