"""Pure physics helpers for the SiO2 cooling map."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

YEAR_SECONDS: float = 365.25 * 24.0 * 3600.0


@dataclass(frozen=True)
class CoolingParams:
    """Physical parameters used by the cooling model."""

    R_mars: float = 3.3895e6
    sigma: float = 5.670374419e-8
    rho: float = 3000.0
    cp: float = 1000.0
    d_layer: float = 1.0e5
    T_glass: float = 1475.0
    T_liquidus: float = 1986.0


def mars_temperature(time_s: np.ndarray, T0: float, params: CoolingParams) -> np.ndarray:
    """Analytic slab-cooling solution for Mars.

    Parameters
    ----------
    time_s:
        Sample times [s], must be non-negative.
    T0:
        Initial surface temperature [K], must be positive.
    params:
        Physical constants.
    """

    time_arr = np.asarray(time_s, dtype=float)
    if np.any(time_arr < 0.0):
        raise ValueError("time_s must be non-negative")
    if T0 <= 0.0:
        raise ValueError("T0 must be positive")
    coeff = 3.0 * params.sigma / (params.d_layer * params.rho * params.cp)
    base = (T0 ** -3) + coeff * time_arr
    return np.power(base, -1.0 / 3.0)


def dust_temperature(
    radius_m: float | np.ndarray, time_s: np.ndarray, T0: float, params: CoolingParams
) -> np.ndarray:
    """Instantaneous greybody temperature of a dust grain."""

    radius_arr = np.asarray(radius_m, dtype=float)
    if np.any(radius_arr <= 0.0):
        raise ValueError("radius_m must be positive")
    time_arr = np.asarray(time_s, dtype=float)
    T_mars = mars_temperature(time_arr, T0, params)
    factor = np.sqrt(params.R_mars / (2.0 * radius_arr))
    if radius_arr.ndim == 0:
        return T_mars * float(factor)
    return T_mars[:, np.newaxis] * factor[np.newaxis, :]


def arrival_time_for_threshold(
    radius_m: float, time_s: np.ndarray, T_dust: np.ndarray, threshold_K: float
) -> float:
    """Return first time [s] when ``T_dust`` crosses below the threshold."""

    if radius_m <= 0.0:
        raise ValueError("radius_m must be positive")
    time_arr = np.asarray(time_s, dtype=float)
    temps = np.asarray(T_dust, dtype=float)
    if temps.shape != time_arr.shape:
        raise ValueError("T_dust and time_s must share the same shape")
    idx = np.flatnonzero(temps <= threshold_K)
    if idx.size == 0:
        return float("nan")
    return float(time_arr[idx[0]])


def compute_arrival_times(
    T0: float, params: CoolingParams, r_over_Rmars: np.ndarray, time_s: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute arrival times for glass/liquidus thresholds across radii."""

    radii = np.asarray(r_over_Rmars, dtype=float)
    if np.any(radii <= 0.0):
        raise ValueError("r_over_Rmars must be positive")
    time_arr = np.asarray(time_s, dtype=float)
    T_mars = mars_temperature(time_arr, T0, params)
    factors = np.sqrt(params.R_mars / (2.0 * (radii * params.R_mars)))
    arrival_glass = np.full(radii.shape, np.nan, dtype=float)
    arrival_liquidus = np.full(radii.shape, np.nan, dtype=float)
    for i, factor in enumerate(factors):
        T_dust = T_mars * factor
        arrival_glass[i] = arrival_time_for_threshold(
            radii[i] * params.R_mars, time_arr, T_dust, params.T_glass
        )
        arrival_liquidus[i] = arrival_time_for_threshold(
            radii[i] * params.R_mars, time_arr, T_dust, params.T_liquidus
        )
    return arrival_glass, arrival_liquidus


__all__ = [
    "CoolingParams",
    "YEAR_SECONDS",
    "mars_temperature",
    "dust_temperature",
    "arrival_time_for_threshold",
    "compute_arrival_times",
]
