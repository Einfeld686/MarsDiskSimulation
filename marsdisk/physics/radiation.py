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
import math
import os
import warnings
from collections import OrderedDict
from numbers import Real
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np

from .. import constants
from ..io import tables
from ..errors import PhysicsError
from ..warnings import NumericalWarning, TableWarning

try:
    from ..io._numba_tables import NUMBA_AVAILABLE as _NUMBA_TABLES_AVAILABLE, qpr_interp_array_numba
    _NUMBA_TABLES_AVAILABLE = _NUMBA_TABLES_AVAILABLE()
except ImportError:  # pragma: no cover - optional dependency
    _NUMBA_TABLES_AVAILABLE = False

try:
    from ._numba_radiation import NUMBA_AVAILABLE as _NUMBA_RADIATION_AVAILABLE, blowout_radius_numba
    _NUMBA_RADIATION_AVAILABLE = _NUMBA_RADIATION_AVAILABLE()
except ImportError:  # pragma: no cover - optional dependency
    _NUMBA_RADIATION_AVAILABLE = False

# type alias for a Q_pr interpolation function
type_QPr = Callable[[float, float], float]

_QPR_LOOKUP: type_QPr | None = tables.interp_qpr
_QPR_CACHE_ENABLED: bool = True
_QPR_CACHE_MAXSIZE: int = 256
_QPR_CACHE_ROUND: Optional[float] = None
_QPR_CACHE: "OrderedDict[tuple[float, float], float]" = OrderedDict()

DEFAULT_Q_PR: float = 1.0
DEFAULT_RHO: float = 3000.0
DEFAULT_T_M: float = 2000.0
T_M_RANGE: tuple[float, float] = (1000.0, 6500.0)
BLOWOUT_BETA_THRESHOLD: float = 0.5  # [@StrubbeChiang2006_ApJ648_652]

logger = logging.getLogger(__name__)

_NUMBA_DISABLED_ENV = os.environ.get("MARSDISK_DISABLE_NUMBA", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_USE_NUMBA_TABLES = _NUMBA_TABLES_AVAILABLE and not _NUMBA_DISABLED_ENV
_USE_NUMBA_RADIATION = _NUMBA_RADIATION_AVAILABLE and not _NUMBA_DISABLED_ENV
_NUMBA_FAILED = False


def _validate_size(value: float, *, name: str = "s") -> float:
    if not isinstance(value, Real):
        raise TypeError(f"grain size '{name}' must be a real number")
    if not np.isfinite(value):
        raise PhysicsError(f"grain size '{name}' must be finite")
    if value <= 0.0:
        raise PhysicsError(f"grain size '{name}' must be greater than 0")
    return float(value)


def _validate_density(value: Optional[float]) -> float:
    if value is None:
        logger.info("No material density provided; using default %.1f kg/m^3", DEFAULT_RHO)
        return DEFAULT_RHO
    if not isinstance(value, Real):
        raise TypeError("material density 'rho' must be a real number")
    if not np.isfinite(value):
        raise PhysicsError("material density 'rho' must be finite")
    if value <= 0.0:
        raise PhysicsError("material density 'rho' must be greater than 0")
    return float(value)


def _validate_temperature(value: Optional[float]) -> float:
    if value is None:
        logger.info("No Mars surface temperature provided; using default %.1f K", DEFAULT_T_M)
        return DEFAULT_T_M
    if not isinstance(value, Real):
        raise TypeError("temperature 'T_M' must be a real number")
    if not np.isfinite(value):
        raise PhysicsError("temperature 'T_M' must be finite")
    Tmin, Tmax = T_M_RANGE
    if not (Tmin <= value <= Tmax):
        raise PhysicsError(f"temperature 'T_M' must lie within [{Tmin}, {Tmax}] K")
    return float(value)


def _validate_qpr(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, Real):
        raise TypeError("Q_pr must be a real number if provided")
    if not np.isfinite(value):
        raise PhysicsError("Q_pr must be finite if provided")
    if value <= 0.0:
        raise PhysicsError("Q_pr must be greater than 0 if provided")
    return float(value)


def _resolve_qpr(
    s: float,
    T_M: float,
    Q_pr: Optional[float],
    table: type_QPr | None,
    interp: type_QPr | None,
) -> float:
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

    table_path = tables.get_qpr_table_path()
    location_hint = f" (active table: {table_path})" if table_path is not None else ""
    raise RuntimeError(
        "No ⟨Q_pr⟩ lookup table initialised; set radiation.qpr_table_path or call "
        f"marsdisk.io.tables.load_qpr_table before evaluating radiation terms{location_hint}."
    )


def _quantize(value: float, step: float | None) -> float:
    if step is None or step <= 0.0:
        return value
    scaled = value / step
    rounded = round(scaled)
    return rounded * step


def _qpr_cache_key(s: float, T_M: float) -> tuple[float, float]:
    return (_quantize(s, _QPR_CACHE_ROUND), _quantize(T_M, _QPR_CACHE_ROUND))


def _qpr_cache_get(s: float, T_M: float) -> float | None:
    if not _QPR_CACHE_ENABLED or _QPR_CACHE_MAXSIZE <= 0:
        return None
    key = _qpr_cache_key(s, T_M)
    cached = _QPR_CACHE.get(key)
    if cached is None:
        return None
    _QPR_CACHE.move_to_end(key)
    return cached


def _qpr_cache_set(s: float, T_M: float, value: float) -> None:
    if not _QPR_CACHE_ENABLED or _QPR_CACHE_MAXSIZE <= 0:
        return
    key = _qpr_cache_key(s, T_M)
    _QPR_CACHE[key] = value
    _QPR_CACHE.move_to_end(key)
    while len(_QPR_CACHE) > _QPR_CACHE_MAXSIZE:
        _QPR_CACHE.popitem(last=False)


def configure_qpr_cache(*, enabled: bool, maxsize: int = 256, round_tol: float | None = None) -> None:
    """Configure memoisation for ⟨Q_pr⟩ lookups."""

    global _QPR_CACHE_ENABLED, _QPR_CACHE_MAXSIZE, _QPR_CACHE_ROUND
    _QPR_CACHE_ENABLED = bool(enabled)
    _QPR_CACHE_MAXSIZE = max(int(maxsize), 0)
    _QPR_CACHE_ROUND = float(round_tol) if round_tol is not None and round_tol > 0.0 else None
    _QPR_CACHE.clear()


def grain_temperature_graybody(T_M: float, radius_m: float, *, q_abs: float = 1.0) -> float:
    r"""Return the planetary IR equilibrium grain temperature ``T_d`` (E.043). [@Hyodo2018_ApJ860_150]

    The expression follows ``T_d = T_M \bar{Q}_{abs}^{1/4} \sqrt{R_M/(2 r)}`` for a
    Lambertian planet illuminating an optically thin, gas-poor disk.  The
    absorption efficiency ``\bar{Q}_{abs}`` defaults to unity but can be supplied
    to represent material-specific emissivities.
    """

    if not isinstance(radius_m, Real):
        raise TypeError("radius_m must be a real number")
    if not np.isfinite(radius_m):
        raise PhysicsError("radius_m must be finite")
    radius_val = float(radius_m)
    if radius_val <= 0.0:
        raise PhysicsError("radius_m must be positive")

    if not isinstance(q_abs, Real):
        raise TypeError("q_abs must be a real number")
    if not np.isfinite(q_abs):
        raise PhysicsError("q_abs must be finite")
    if q_abs <= 0.0:
        raise PhysicsError("q_abs must be positive")

    T_val = _validate_temperature(T_M)
    factor = (float(q_abs) ** 0.25) * math.sqrt(constants.R_MARS / (2.0 * radius_val))
    return T_val * factor


def load_qpr_table(path: Path | str) -> type_QPr:
    """Load a table file and cache the interpolator. Planck averaged ⟨Q_pr⟩."""

    global _QPR_LOOKUP
    _QPR_CACHE.clear()
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
        raise PhysicsError("grain size 's' must be finite for ⟨Q_pr⟩ lookup")
    if not np.isfinite(T_M):
        raise PhysicsError("temperature 'T_M' must be finite for ⟨Q_pr⟩ lookup")

    s_val = float(s)
    T_val = float(T_M)
    if s_val <= 0.0:
        raise PhysicsError("grain size 's' must be greater than 0 for ⟨Q_pr⟩ lookup")
    if T_val <= 0.0:
        raise PhysicsError("temperature 'T_M' must be greater than 0 for ⟨Q_pr⟩ lookup")

    func = table or _QPR_LOOKUP or tables.interp_qpr
    if not callable(func):
        raise TypeError("provided ⟨Q_pr⟩ interpolator must be callable")

    lookup = func
    table_obj = getattr(lookup, "__self__", None)
    if table_obj is None and lookup is tables.interp_qpr:
        table_obj = getattr(tables, "_QPR_TABLE", None)
        if table is None and _QPR_LOOKUP is None and table_obj is None:
            raise RuntimeError(
                "⟨Q_pr⟩ lookup table not initialised. Provide radiation.qpr_table_path or call "
                "marsdisk.io.tables.load_qpr_table before evaluating Q_pr."
            )

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

    cached = _qpr_cache_get(s_eval, T_eval)
    if cached is not None:
        return float(cached)

    value = float(lookup(s_eval, T_eval))
    _qpr_cache_set(s_eval, T_eval, value)
    return value


def qpr_lookup_array(
    s: Iterable[float] | np.ndarray,
    T_M: float | Iterable[float] | np.ndarray,
    table: type_QPr | None = None,
) -> np.ndarray:
    """Vectorised ⟨Q_pr⟩ lookup for an array of grain sizes at a single temperature.

    The fast path exploits the loaded :class:`~marsdisk.io.tables.QPrTable`
    when available and treats ``T_M`` as a scalar; for other input shapes
    it falls back to element-wise :func:`qpr_lookup`.
    """
    global _NUMBA_FAILED

    s_arr = np.asarray(s, dtype=float)
    T_arr = np.asarray(T_M, dtype=float)
    if s_arr.size == 0:
        return np.zeros_like(s_arr, dtype=float)

    scalar_T = T_arr.size == 1
    if not scalar_T and T_arr.shape != s_arr.shape:
        raise PhysicsError("T_M must be scalar or match the shape of 's' for ⟨Q_pr⟩ lookup")

    s_flat = s_arr.reshape(-1)
    if np.any(~np.isfinite(s_flat)) or np.any(s_flat <= 0.0):
        raise PhysicsError("grain size array contains non-finite or non-positive entries")
    if not np.isfinite(T_arr).all():
        raise PhysicsError("temperature 'T_M' must be finite for ⟨Q_pr⟩ lookup")
    if np.any(T_arr <= 0.0):
        raise PhysicsError("temperature 'T_M' must be greater than 0 for ⟨Q_pr⟩ lookup")

    func = table or _QPR_LOOKUP or tables.interp_qpr
    if not callable(func):
        raise TypeError("provided ⟨Q_pr⟩ interpolator must be callable")

    lookup = func
    table_obj = getattr(lookup, "__self__", None)
    if table_obj is None and lookup is tables.interp_qpr:
        table_obj = getattr(tables, "_QPR_TABLE", None)
        if table is None and _QPR_LOOKUP is None and table_obj is None:
            raise RuntimeError(
                "⟨Q_pr⟩ lookup table not initialised. Provide radiation.qpr_table_path or call "
                "marsdisk.io.tables.load_qpr_table before evaluating Q_pr."
            )

    # Fast bilinear interpolation path for scalar T_M using the table grid.
    if table_obj is not None and hasattr(table_obj, "s_vals") and hasattr(table_obj, "T_vals") and scalar_T:
        s_vals = np.asarray(table_obj.s_vals, dtype=float)
        T_vals = np.asarray(table_obj.T_vals, dtype=float)
        q_grid = np.asarray(getattr(table_obj, "q_vals", None), dtype=float)
        if q_grid.shape != (T_vals.size, s_vals.size):
            q_grid = None
        if s_vals.size >= 2 and T_vals.size >= 2 and q_grid is not None and q_grid.size:
            s_min = float(np.min(s_vals))
            s_max = float(np.max(s_vals))
            T_min = float(np.min(T_vals))
            T_max = float(np.max(T_vals))
            T_eval = float(np.clip(float(T_arr.flat[0]), T_min, T_max))
            s_eval = np.clip(s_flat, s_min, s_max)
            if _USE_NUMBA_TABLES and not _NUMBA_FAILED:
                try:
                    result = qpr_interp_array_numba(
                        np.asarray(s_vals, dtype=np.float64),
                        np.asarray(T_vals, dtype=np.float64),
                        np.asarray(q_grid, dtype=np.float64),
                        np.asarray(s_eval, dtype=np.float64),
                        float(T_eval),
                    )
                    return result.reshape(s_arr.shape).astype(float, copy=False)
                except Exception as exc:
                    _NUMBA_FAILED = True
                    warnings.warn(
                        f"Q_pr numba array interpolation failed ({exc!r}); falling back to NumPy.",
                        TableWarning,
                    )
            i = np.clip(np.searchsorted(s_vals, s_eval) - 1, 0, s_vals.size - 2)
            j = int(np.clip(np.searchsorted(T_vals, T_eval) - 1, 0, T_vals.size - 2))
            s1 = s_vals[i]
            s2 = s_vals[i + 1]
            T1 = T_vals[j]
            T2 = T_vals[j + 1]
            q11 = q_grid[j, i]
            q12 = q_grid[j + 1, i]
            q21 = q_grid[j, i + 1]
            q22 = q_grid[j + 1, i + 1]
            with np.errstate(divide="ignore", invalid="ignore"):
                ws = np.where(s2 == s1, 0.0, (s_eval - s1) / (s2 - s1))
                wT = 0.0 if T2 == T1 else (T_eval - T1) / (T2 - T1)
            q1 = q11 * (1.0 - ws) + q21 * ws
            q2 = q12 * (1.0 - ws) + q22 * ws
            result = q1 * (1.0 - wT) + q2 * wT
            result = result.reshape(s_arr.shape)
            return result.astype(float, copy=False)

    # Fallback: element-wise lookup (supports array T_M).
    if scalar_T:
        T_scalar = float(T_arr.flat[0])
        values = [qpr_lookup(val, T_scalar, table=table) for val in s_flat]
    else:
        values = [qpr_lookup(val, float(T_val), table=table) for val, T_val in zip(s_flat, T_arr.reshape(-1))]
    return np.asarray(values, dtype=float).reshape(s_arr.shape)


def planck_mean_qpr(
    s: float,
    T_M: float,
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the effective grey-body ⟨Q_pr⟩ using the active lookup table."""

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
    """Compute the ratio ``β`` of radiation pressure to gravity (R2). [@StrubbeChiang2006_ApJ648_652]

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
    """Return the blow-out grain size ``s_blow`` for ``β = 0.5`` (R3). [@StrubbeChiang2006_ApJ648_652]"""

    global _NUMBA_FAILED
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    qpr = _resolve_qpr(1.0, T_val, Q_pr, table, interp)
    if _USE_NUMBA_RADIATION and not _NUMBA_FAILED:
        try:
            return float(blowout_radius_numba(rho_val, T_val, qpr))
        except Exception as exc:
            _NUMBA_FAILED = True
            warnings.warn(
                f"blowout radius numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
    numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
    denominator = 2.0 * constants.G * constants.M_MARS * constants.C * rho_val
    return float(numerator / denominator)
