#!/usr/bin/env python3
"""Generate a Planck-mean <Q_pr> table (CSV) from FOR2285 forsterite n,k using Mie.

This script reads the axis-resolved FOR2285 n,k tables under
data/forsterite_material_data/nk_FOR2285 and
computes a/b/c-axis Q_pr via Mie theory, then averages the three axes with 1/3
weighting. The Planck mean is evaluated for user-specified temperatures.

Output format
-------------
CSV with columns: T_M, s, Q_pr

Requirements
------------
Requires miepython (external dependency).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import importlib
import os

import numpy as np
import pandas as pd

MIE = None


def _load_miepython(use_jit: bool):
    os.environ["MIEPYTHON_USE_JIT"] = "1" if use_jit else "0"
    mie = importlib.import_module("miepython")
    mie = importlib.reload(mie)
    importlib.reload(importlib.import_module("miepython.core"))
    return mie


# Physical constants in SI units
PLANCK = 6.62607015e-34  # J s
LIGHT_SPEED = 2.99792458e8  # m s^-1
BOLTZMANN = 1.380649e-23  # J K^-1
HC_OVER_K = PLANCK * LIGHT_SPEED / BOLTZMANN


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


def _load_nk_axis(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.loadtxt(path, dtype=float)
    if data.ndim != 2 or data.shape[1] != 3:
        raise ValueError(f"Expected 3-column n,k file, got shape {data.shape} at {path}")
    lam_um = data[:, 0]
    n_vals = data[:, 1]
    k_vals = data[:, 2]
    if np.any(lam_um <= 0.0):
        raise ValueError(f"Non-positive wavelength found in {path}")
    if not np.all(np.isfinite(n_vals)) or not np.all(np.isfinite(k_vals)):
        raise ValueError(f"Non-finite n/k values found in {path}")
    return lam_um, n_vals, k_vals


def _merge_wavelength_grid(
    lam_axes: Sequence[np.ndarray],
    nk_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    lam_min_um: float | None,
    lam_max_um: float | None,
) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray]]]:
    lam_base = lam_axes[0]
    same = all(np.array_equal(lam_base, lam) for lam in lam_axes[1:])
    if same:
        lam_common = lam_base
        nk_common = list(nk_axes)
    else:
        lam_common = np.unique(np.concatenate(lam_axes))
        nk_common = []
        for lam, (n_vals, k_vals) in zip(lam_axes, nk_axes):
            n_interp = np.interp(lam_common, lam, n_vals)
            k_interp = np.interp(lam_common, lam, k_vals)
            nk_common.append((n_interp, k_interp))

    if lam_min_um is not None or lam_max_um is not None:
        lo = lam_min_um if lam_min_um is not None else float(lam_common[0])
        hi = lam_max_um if lam_max_um is not None else float(lam_common[-1])
        mask = (lam_common >= lo) & (lam_common <= hi)
        if not np.any(mask):
            raise ValueError("Wavelength filter removed all entries")
        lam_common = lam_common[mask]
        nk_common = [(n_vals[mask], k_vals[mask]) for n_vals, k_vals in nk_common]

    return lam_common, nk_common


def _resample_wavelength_grid(
    lam_um: np.ndarray,
    nk_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    samples: int,
) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray]]]:
    if samples < 2:
        raise ValueError("lambda_samples must be at least 2")
    lam_min = float(lam_um[0])
    lam_max = float(lam_um[-1])
    lam_resampled = np.geomspace(lam_min, lam_max, samples)
    nk_resampled: list[tuple[np.ndarray, np.ndarray]] = []
    for n_vals, k_vals in nk_axes:
        n_interp = np.interp(lam_resampled, lam_um, n_vals)
        k_interp = np.interp(lam_resampled, lam_um, k_vals)
        nk_resampled.append((n_interp, k_interp))
    return lam_resampled, nk_resampled


def _mie_qpr(m_complex: complex, x: float) -> float:
    if MIE is None:
        raise RuntimeError("miepython module not initialised")
    qext, qsca, _qback, g = MIE.efficiencies_mx(m_complex, x)
    return float(qext - g * qsca)


def _compute_qpr_lambda(
    lam_m: np.ndarray,
    s_values: np.ndarray,
    nk_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    x_max: float | None = None,
) -> np.ndarray:
    lam_m = np.asarray(lam_m, dtype=float)
    s_arr = np.asarray(s_values, dtype=float)
    qpr_axes = []
    for n_vals, k_vals in nk_axes:
        m_vals = n_vals + 1j * k_vals
        qpr_axis = np.empty((s_arr.size, lam_m.size), dtype=float)
        for i, s in enumerate(s_arr):
            x_vals = (2.0 * np.pi * s) / lam_m
            if x_max is not None:
                mask = x_vals <= x_max
                qpr = np.empty_like(x_vals)
                qpr[~mask] = 1.0
                if np.any(mask):
                    if MIE is None:
                        raise RuntimeError("miepython module not initialised")
                    qext, qsca, _qback, g = MIE.efficiencies_mx(m_vals[mask], x_vals[mask])
                    qpr[mask] = qext - g * qsca
                qpr_axis[i, :] = qpr
            else:
                if MIE is None:
                    raise RuntimeError("miepython module not initialised")
                qext, qsca, _qback, g = MIE.efficiencies_mx(m_vals, x_vals)
                qpr_axis[i, :] = qext - g * qsca
        qpr_axes.append(qpr_axis)
    return np.mean(np.stack(qpr_axes, axis=0), axis=0)


def compute_planck_mean_qpr(
    s_values: Sequence[float],
    temperatures: Sequence[float],
    lam_um: np.ndarray,
    nk_axes: Sequence[tuple[np.ndarray, np.ndarray]],
    x_max: float | None = None,
) -> np.ndarray:
    s_arr = np.asarray(s_values, dtype=float)
    T_arr = np.asarray(temperatures, dtype=float)
    lam_m = np.asarray(lam_um, dtype=float) * 1.0e-6

    qpr_lambda = _compute_qpr_lambda(lam_m, s_arr, nk_axes, x_max=x_max)

    result = np.empty((T_arr.size, s_arr.size), dtype=float)
    for i, T in enumerate(T_arr):
        spectrum = _planck_lambda(lam_m, float(T))
        denom = np.trapz(spectrum, lam_m)
        numer = np.trapz(qpr_lambda * spectrum[None, :], lam_m, axis=1)
        result[i, :] = numer / denom
    return result


def _resolve_temperature_tag(value: float) -> int:
    rounded = int(round(value))
    if not np.isclose(value, rounded):
        raise ValueError("nk temperature must be an integer (e.g., 295)")
    return rounded


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/forsterite_material_data/nk_FOR2285",
        help="FOR2285 data directory",
    )
    parser.add_argument("--nk-temperature", type=float, default=295.0, help="n,k temperature (K)")
    parser.add_argument("--s-min", type=float, required=True, help="min grain size [m]")
    parser.add_argument("--s-max", type=float, required=True, help="max grain size [m]")
    parser.add_argument("--Ns", type=int, required=True, help="# of size bins")
    parser.add_argument("--T", type=str, required=True, help="comma-separated temperatures [K]")
    parser.add_argument("--lam-min-um", type=float, default=None, help="min wavelength [um]")
    parser.add_argument("--lam-max-um", type=float, default=None, help="max wavelength [um]")
    parser.add_argument(
        "--lambda-samples",
        type=int,
        default=None,
        help="resample wavelength grid to N log-spaced points for speed",
    )
    parser.add_argument(
        "--use-jit",
        action="store_true",
        help="enable miepython JIT acceleration when available",
    )
    parser.add_argument(
        "--x-max",
        type=float,
        default=1.0e4,
        help="size-parameter cutoff; x > x_max uses Q_pr=1 approximation",
    )
    parser.add_argument("--out", type=str, required=True, help="output CSV path")
    args = parser.parse_args(argv)

    mie = _load_miepython(use_jit=bool(args.use_jit))
    global MIE
    MIE = mie

    nk_temp = _resolve_temperature_tag(args.nk_temperature)
    data_dir = Path(args.data_dir)
    axis_files = {
        "a": data_dir / f"fors_a_{nk_temp}_nk.dat",
        "b": data_dir / f"fors_b_{nk_temp}_nk.dat",
        "c": data_dir / f"fors_c_{nk_temp}_nk.dat",
    }
    for axis, path in axis_files.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing FOR2285 {axis}-axis file: {path}")

    lam_axes = []
    nk_axes = []
    for axis in ("a", "b", "c"):
        lam_um, n_vals, k_vals = _load_nk_axis(axis_files[axis])
        lam_axes.append(lam_um)
        nk_axes.append((n_vals, k_vals))

    lam_um, nk_axes = _merge_wavelength_grid(
        lam_axes, nk_axes, lam_min_um=args.lam_min_um, lam_max_um=args.lam_max_um
    )
    if args.lambda_samples is not None:
        lam_um, nk_axes = _resample_wavelength_grid(lam_um, nk_axes, args.lambda_samples)

    temps = _parse_temperatures(args.T)
    sizes = _build_size_grid(args.s_min, args.s_max, args.Ns)
    x_max = None if args.x_max is None else float(args.x_max)
    qpr = compute_planck_mean_qpr(sizes, temps, lam_um, nk_axes, x_max=x_max)

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
