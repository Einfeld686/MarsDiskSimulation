#!/usr/bin/env python3
"""Generate a Planck-mean <Q_pr> table (CSV) using a simple SiO2-motivated bridge model.

This is a CSV-producing counterpart of the existing make_qpr_table.py, with one extra
physics knob (c_abs) that prevents <Q_pr> from becoming too small in the smallest-grain
corner.

Model
-----
We compute a Planck mean over wavelength:

    <Q_pr>(T, s) = ∫ Q_pr(λ, s) B_λ(T) dλ / ∫ B_λ(T) dλ

with a minimal bridge function for the monochromatic efficiency:

    Q_pr(λ, s) = (x^4 + c_abs * x) / (1 + x^4 + c_abs * x)
    x = 2π s / λ

When c_abs = 0, this reduces to the scattering-only bridge x^4/(1+x^4).
A positive c_abs adds an absorption-like term ~x, which is relevant when the material
is not perfectly transparent.

Output format
-------------
CSV with columns: T_M, s, Q_pr

"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# Physical constants in SI units
PLANCK = 6.62607015e-34  # J s
LIGHT_SPEED = 2.99792458e8  # m s^-1
BOLTZMANN = 1.380649e-23  # J K^-1
HC_OVER_K = PLANCK * LIGHT_SPEED / BOLTZMANN

WAVELENGTH_MIN_UM = 0.5
WAVELENGTH_MAX_UM = 30.0
DEFAULT_WAVELENGTH_SAMPLES = 512


def _parse_temperatures(raw: str) -> np.ndarray:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("At least one temperature must be provided")
    temps = np.array([float(p) for p in parts], dtype=float)
    if np.any(temps <= 0.0):
        raise ValueError("Temperatures must be positive")
    return temps


def _build_size_grid(s_min: float, s_max: float, count: int) -> np.ndarray:
    if s_min <= 0.0 or s_max <= 0.0:
        raise ValueError("s_min and s_max must be positive")
    if s_max <= s_min:
        raise ValueError("s_max must be larger than s_min")
    if count < 2:
        raise ValueError("Ns must be at least 2")
    return np.geomspace(s_min, s_max, count)


def _planck_lambda(wavelength_m: np.ndarray, temperature: float) -> np.ndarray:
    lam = np.asarray(wavelength_m, dtype=float)
    exponent = HC_OVER_K / (lam * temperature)
    return (2.0 * PLANCK * LIGHT_SPEED**2) / (lam**5 * np.expm1(exponent))


def _qpr_lambda_bridge(size_parameter: np.ndarray, c_abs: float) -> np.ndarray:
    x = np.asarray(size_parameter, dtype=float)
    if c_abs < 0.0:
        raise ValueError("c_abs must be non-negative")
    num = x**4 + c_abs * x
    den = 1.0 + num
    return num / den


def compute_planck_mean_qpr(
    s_values: Sequence[float],
    temperatures: Sequence[float],
    c_abs: float,
    wavelengths_um: Iterable[float] | None = None,
) -> np.ndarray:
    s_arr = np.asarray(s_values, dtype=float)
    T_arr = np.asarray(temperatures, dtype=float)

    if wavelengths_um is None:
        wavelengths_um = np.geomspace(
            WAVELENGTH_MIN_UM, WAVELENGTH_MAX_UM, DEFAULT_WAVELENGTH_SAMPLES
        )
    lam_um = np.asarray(list(wavelengths_um), dtype=float)
    lam_m = lam_um * 1.0e-6

    size_parameter = (2.0 * np.pi * s_arr[:, None]) / lam_m[None, :]
    q_lambda = _qpr_lambda_bridge(size_parameter, c_abs=c_abs)

    result = np.empty((T_arr.size, s_arr.size), dtype=float)
    for i, T in enumerate(T_arr):
        spectrum = _planck_lambda(lam_m, float(T))
        denom = np.trapz(spectrum, lam_m)
        numer = np.trapz(q_lambda * spectrum[None, :], lam_m, axis=1)
        result[i, :] = numer / denom
    return result


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s-min", type=float, required=True, help="min grain size [m]")
    parser.add_argument("--s-max", type=float, required=True, help="max grain size [m]")
    parser.add_argument("--Ns", type=int, required=True, help="# of size bins")
    parser.add_argument("--T", type=str, required=True, help="comma-separated temperatures [K]")
    parser.add_argument("--c-abs", type=float, default=0.10, help="absorption-like coefficient")
    parser.add_argument("--out", type=str, required=True, help="output CSV path")
    args = parser.parse_args(argv)

    temps = _parse_temperatures(args.T)
    sizes = _build_size_grid(args.s_min, args.s_max, args.Ns)
    qpr = compute_planck_mean_qpr(sizes, temps, c_abs=float(args.c_abs))

    rows = []
    for i, T in enumerate(temps):
        for j, s in enumerate(sizes):
            rows.append((float(T), float(s), float(qpr[i, j])))

    out_df = pd.DataFrame(rows, columns=["T_M", "s", "Q_pr"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
