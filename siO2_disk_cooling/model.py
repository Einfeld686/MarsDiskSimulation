"""Pure physics helpers for the SiO2 cooling map."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

YEAR_SECONDS: float = 365.25 * 24.0 * 3600.0


@dataclass(frozen=True)
class CoolingParams:
    """Physical parameters used by the cooling model.

    ``q_abs_mean`` is applied as ``q_abs_mean**0.25`` in the grain temperature scaling.
    """

    R_mars: float = 3.3895e6
    sigma: float = 5.670374419e-8
    q_abs_mean: float = 0.4  # Planck-mean absorption efficiency <Q_abs>
    rho: float = 3000.0
    cp: float = 1000.0
    d_layer: float = 1.0e5
    T_glass: float = 1475.0
    T_liquidus: float = 1986.0


def cooling_time_to_temperature(
    T0: float, T_target: float, params: CoolingParams, *, floor_at_zero: bool = True
) -> float:
    """Return time [s] for Mars slab to cool from ``T0`` to ``T_target``.

    Uses the analytic inverse of :func:`mars_temperature`. If ``T_target`` is above
    ``T0`` the returned time is zero when ``floor_at_zero`` is true; otherwise a negative
    duration is surfaced to signal an invalid ordering.
    """

    if T0 <= 0.0 or T_target <= 0.0:
        raise ValueError("T0 and T_target must be positive")
    coeff = 3.0 * params.sigma / (params.d_layer * params.rho * params.cp)
    delta = (T_target**-3) - (T0**-3)
    time_s = delta / coeff
    if floor_at_zero:
        return float(max(time_s, 0.0))
    return float(time_s)


def hyodo_cooling_time(
    T0: float, T_target: float, params: CoolingParams, *, floor_at_zero: bool = True
) -> float:
    """Hyodo linear cooling time [s] using constant flux approximation.

    Implements τ_cool ≈ 717 days × (D/100 km) × (ΔT/3000 K) × (T0/4000 K)
    with D taken from ``params.d_layer``. Uses T0 as the scale temperature.
    """

    if T0 <= 0.0 or T_target < 0.0:
        raise ValueError("T0 must be positive and T_target non-negative for Hyodo cooling")
    delta_T = float(T0 - T_target)
    if delta_T <= 0.0:
        return 0.0 if floor_at_zero else -0.0
    depth_km = float(params.d_layer) / 1.0e3
    tau_days = 717.0 * (depth_km / 100.0) * (delta_T / 3000.0) * (float(T0) / 4000.0)
    tau_s = tau_days * 86400.0
    return float(max(tau_s, 0.0)) if floor_at_zero else float(tau_s)


def hyodo_temperature(
    time_s: np.ndarray,
    T0: float,
    params: CoolingParams,
    *,
    floor_K: float = 0.0,
) -> np.ndarray:
    """Linear cooling profile implied by the Hyodo τ_cool scaling."""

    if T0 <= 0.0:
        raise ValueError("T0 must be positive for Hyodo cooling")
    slope_K_per_s = 0.0
    try:
        tau_s = hyodo_cooling_time(T0, floor_K, params, floor_at_zero=True)
        if tau_s > 0.0:
            slope_K_per_s = float((T0 - floor_K) / tau_s)
    except Exception:
        tau_s = 0.0
        slope_K_per_s = 0.0
    t_arr = np.asarray(time_s, dtype=float)
    T = T0 - slope_K_per_s * t_arr
    return np.maximum(T, float(floor_K))


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
    radius_m: float | np.ndarray,
    time_s: np.ndarray,
    T0: float,
    params: CoolingParams,
    *,
    temperature_model: str = "slab",
) -> np.ndarray:
    """Instantaneous greybody temperature of a dust grain (includes ``q_abs_mean**0.25``)."""

    radius_arr = np.asarray(radius_m, dtype=float)
    if np.any(radius_arr <= 0.0):
        raise ValueError("radius_m must be positive")
    time_arr = np.asarray(time_s, dtype=float)
    model = temperature_model.lower() if isinstance(temperature_model, str) else "slab"
    if model == "hyodo":
        T_mars = hyodo_temperature(time_arr, T0, params)
    else:
        T_mars = mars_temperature(time_arr, T0, params)
    q_factor = float(params.q_abs_mean) ** 0.25
    factor = q_factor * np.sqrt(params.R_mars / (2.0 * radius_arr))
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
    T0: float,
    params: CoolingParams,
    r_over_Rmars: np.ndarray,
    time_s: np.ndarray,
    *,
    temperature_model: str = "slab",
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute arrival times for glass/liquidus thresholds across radii."""

    radii = np.asarray(r_over_Rmars, dtype=float)
    if np.any(radii <= 0.0):
        raise ValueError("r_over_Rmars must be positive")
    time_arr = np.asarray(time_s, dtype=float)
    radii_m = radii * params.R_mars
    T_dust = dust_temperature(radii_m, time_arr, T0, params, temperature_model=temperature_model)
    arrival_glass = np.full(radii.shape, np.nan, dtype=float)
    arrival_liquidus = np.full(radii.shape, np.nan, dtype=float)
    for i, radius_m in enumerate(radii_m):
        T_dust_col = T_dust[:, i] if T_dust.ndim > 1 else T_dust
        arrival_glass[i] = arrival_time_for_threshold(
            radius_m, time_arr, T_dust_col, params.T_glass
        )
        arrival_liquidus[i] = arrival_time_for_threshold(
            radius_m, time_arr, T_dust_col, params.T_liquidus
        )
    return arrival_glass, arrival_liquidus


__all__ = [
    "CoolingParams",
    "YEAR_SECONDS",
    "mars_temperature",
    "hyodo_temperature",
    "hyodo_cooling_time",
    "dust_temperature",
    "arrival_time_for_threshold",
    "compute_arrival_times",
    "cooling_time_to_temperature",
]
