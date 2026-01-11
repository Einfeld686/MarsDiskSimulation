#!/usr/bin/env python3
"""Generate a Planck-mean <Q_pr> table (CSV) from forsterite n,k using Mie.

This script reads the axis-resolved FOR2285 n,k tables under
data/forsterite_material_data/nk_FOR2285 and
computes a/b/c-axis Q_pr via Mie theory, then averages the three axes with 1/3
weighting. The Planck mean is evaluated for user-specified temperatures.

Optionally, high-temperature Eckes/POSEIDON n,k (from nk_data.csv) can be
merged into the 2.5–30 um band, with FOR2285 used outside that range.

Output format
-------------
CSV with columns: T_M, s, Q_pr

Requirements
------------
Requires miepython (external dependency).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import importlib
import os
import re
import json

import numpy as np
import pandas as pd

MIE = None


@dataclass
class NKTemperatureGrid:
    temps: np.ndarray
    n_vals: np.ndarray
    k_vals: np.ndarray


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


def _discover_for2285_temperatures(data_dir: Path) -> list[int]:
    pattern = re.compile(r"fors_a_(\d+)_nk\.dat$")
    temps = []
    for path in data_dir.glob("fors_a_*_nk.dat"):
        match = pattern.match(path.name)
        if match:
            temps.append(int(match.group(1)))
    temps = sorted(set(temps))
    if not temps:
        raise FileNotFoundError(f"No FOR2285 a-axis files found in {data_dir}")
    for temp in temps:
        for axis in ("a", "b", "c"):
            axis_path = data_dir / f"fors_{axis}_{temp}_nk.dat"
            if not axis_path.exists():
                raise FileNotFoundError(f"Missing FOR2285 {axis}-axis file: {axis_path}")
    return temps


def _load_for2285_tables(
    data_dir: Path,
    lam_min_um: float | None,
    lam_max_um: float | None,
) -> tuple[np.ndarray, dict[str, NKTemperatureGrid]]:
    temps = _discover_for2285_temperatures(data_dir)
    base_temp = max(temps)

    lam_axes = []
    nk_axes = []
    for axis in ("a", "b", "c"):
        lam_um, n_vals, k_vals = _load_nk_axis(data_dir / f"fors_{axis}_{base_temp}_nk.dat")
        lam_axes.append(lam_um)
        nk_axes.append((n_vals, k_vals))

    lam_common, _nk_common = _merge_wavelength_grid(
        lam_axes, nk_axes, lam_min_um=lam_min_um, lam_max_um=lam_max_um
    )

    tables: dict[str, dict[float, tuple[np.ndarray, np.ndarray]]] = {axis: {} for axis in ("a", "b", "c")}
    for axis in ("a", "b", "c"):
        for temp in temps:
            lam_um, n_vals, k_vals = _load_nk_axis(data_dir / f"fors_{axis}_{temp}_nk.dat")
            if not np.array_equal(lam_um, lam_common):
                n_vals = np.interp(lam_common, lam_um, n_vals)
                k_vals = np.interp(lam_common, lam_um, k_vals)
            tables[axis][float(temp)] = (n_vals, k_vals)

    axis_tables: dict[str, NKTemperatureGrid] = {}
    for axis, temp_map in tables.items():
        temp_sorted = np.array(sorted(temp_map.keys()), dtype=float)
        n_vals = np.stack([temp_map[t][0] for t in temp_sorted], axis=0)
        k_vals = np.stack([temp_map[t][1] for t in temp_sorted], axis=0)
        axis_tables[axis] = NKTemperatureGrid(temps=temp_sorted, n_vals=n_vals, k_vals=k_vals)

    return lam_common, axis_tables


def _load_eckes_tables(
    csv_path: Path,
    source_id: str,
    lam_min_um: float,
    lam_max_um: float,
) -> tuple[np.ndarray, dict[str, NKTemperatureGrid]]:
    table_path = Path(csv_path)
    suffix = table_path.suffix.lower()
    if suffix == ".csv":
        parquet_path = table_path.with_suffix(".parquet")
        if parquet_path.exists():
            if not table_path.exists() or parquet_path.stat().st_mtime >= table_path.stat().st_mtime:
                table_path = parquet_path
    elif suffix in {".parquet", ".pq"} and not table_path.exists():
        fallback_csv = table_path.with_suffix(".csv")
        if fallback_csv.exists():
            table_path = fallback_csv
    columns = ["source_id", "temperature_K", "wavelength_um", "n", "k", "axis"]
    if table_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(table_path, columns=columns)
    else:
        df = pd.read_csv(
            table_path,
            usecols=columns,
            dtype=str,
            low_memory=False,
        )
    df = df[df["source_id"] == source_id].copy()
    if df.empty:
        raise ValueError(f"No rows found for source_id={source_id} in {csv_path}")

    axis_map = {"B1U": "c", "B2U": "b", "B3U": "a"}
    df["axis"] = df["axis"].astype(str)
    df["axis_key"] = df["axis"].str.split().str[0]
    df = df[df["axis_key"].isin(axis_map)].copy()
    if df.empty:
        raise ValueError(f"No B1U/B2U/B3U rows found for source_id={source_id}")
    df["axis_key"] = df["axis_key"].map(axis_map)

    df["temperature_K"] = pd.to_numeric(df["temperature_K"], errors="coerce")
    df["wavelength_um"] = pd.to_numeric(df["wavelength_um"], errors="coerce")
    df["n"] = pd.to_numeric(df["n"], errors="coerce")
    df["k"] = pd.to_numeric(df["k"], errors="coerce")
    if df[["temperature_K", "wavelength_um", "n", "k"]].isna().any().any():
        raise ValueError("Eckes n,k table has missing or non-numeric values")

    grouped: dict[str, dict[float, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    lam_arrays = []
    for (axis, temp), group in df.groupby(["axis_key", "temperature_K"]):
        lam_um = group["wavelength_um"].to_numpy(dtype=float)
        n_vals = group["n"].to_numpy(dtype=float)
        k_vals = group["k"].to_numpy(dtype=float)
        order = np.argsort(lam_um)
        lam_um = lam_um[order]
        n_vals = n_vals[order]
        k_vals = k_vals[order]
        if np.any(lam_um <= 0.0):
            raise ValueError(f"Non-positive wavelength found for {axis} at {temp} K")
        grouped.setdefault(axis, {})[float(temp)] = (lam_um, n_vals, k_vals)
        lam_arrays.append(lam_um)

    lam_common = lam_arrays[0]
    if not all(np.allclose(lam_common, lam, rtol=0, atol=0) for lam in lam_arrays[1:]):
        lam_common = np.unique(np.concatenate(lam_arrays))

    for axis, temp_map in grouped.items():
        for temp, (lam_um, n_vals, k_vals) in list(temp_map.items()):
            if not np.array_equal(lam_um, lam_common):
                n_vals = np.interp(lam_common, lam_um, n_vals)
                k_vals = np.interp(lam_common, lam_um, k_vals)
                temp_map[temp] = (lam_common, n_vals, k_vals)

    mask = (lam_common >= lam_min_um) & (lam_common <= lam_max_um)
    if not np.any(mask):
        raise ValueError("Eckes wavelength filter removed all entries")
    lam_common = lam_common[mask]

    axis_tables: dict[str, NKTemperatureGrid] = {}
    for axis, temp_map in grouped.items():
        temp_sorted = np.array(sorted(temp_map.keys()), dtype=float)
        n_vals = np.stack([temp_map[t][1][mask] for t in temp_sorted], axis=0)
        k_vals = np.stack([temp_map[t][2][mask] for t in temp_sorted], axis=0)
        axis_tables[axis] = NKTemperatureGrid(temps=temp_sorted, n_vals=n_vals, k_vals=k_vals)

    return lam_common, axis_tables


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


def _interp_temperature_grid(temps: np.ndarray, values: np.ndarray, target: float) -> np.ndarray:
    temps_arr = np.asarray(temps, dtype=float)
    if temps_arr.size == 1:
        return values[0]
    if target <= temps_arr[0]:
        return values[0]
    if target >= temps_arr[-1]:
        return values[-1]
    idx = int(np.searchsorted(temps_arr, target))
    t0, t1 = temps_arr[idx - 1], temps_arr[idx]
    weight = (target - t0) / (t1 - t0)
    return values[idx - 1] * (1.0 - weight) + values[idx] * weight


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


def compute_planck_mean_qpr_by_temperature(
    s_values: Sequence[float],
    temperatures: Sequence[float],
    lam_um: np.ndarray,
    nk_axes_by_temp: Sequence[Sequence[tuple[np.ndarray, np.ndarray]]],
    x_max: float | None = None,
) -> np.ndarray:
    s_arr = np.asarray(s_values, dtype=float)
    T_arr = np.asarray(temperatures, dtype=float)
    lam_m = np.asarray(lam_um, dtype=float) * 1.0e-6
    if len(nk_axes_by_temp) != T_arr.size:
        raise ValueError("nk_axes_by_temp must match temperature count")

    result = np.empty((T_arr.size, s_arr.size), dtype=float)
    for i, T in enumerate(T_arr):
        nk_axes = nk_axes_by_temp[i]
        qpr_lambda = _compute_qpr_lambda(lam_m, s_arr, nk_axes, x_max=x_max)
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
    parser.add_argument(
        "--nk-data-csv",
        type=str,
        default=None,
        help="nk_data.csv path for Eckes/POSEIDON data integration",
    )
    parser.add_argument(
        "--eckes-source-id",
        type=str,
        default="eckes2013_forsterite_highT_POSEIDON_optional",
        help="source_id for Eckes data in nk_data.csv",
    )
    parser.add_argument(
        "--eckes-lam-min-um",
        type=float,
        default=2.5,
        help="min wavelength [um] for Eckes data usage",
    )
    parser.add_argument(
        "--eckes-lam-max-um",
        type=float,
        default=30.0,
        help="max wavelength [um] for Eckes data usage",
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
    parser.add_argument(
        "--meta-out",
        type=str,
        default=None,
        help="optional JSON metadata output path",
    )
    args = parser.parse_args(argv)

    mie = _load_miepython(use_jit=bool(args.use_jit))
    global MIE
    MIE = mie

    data_dir = Path(args.data_dir)
    use_eckes = args.nk_data_csv is not None

    temps = _parse_temperatures(args.T)
    sizes = _build_size_grid(args.s_min, args.s_max, args.Ns)
    x_max = None if args.x_max is None else float(args.x_max)

    if use_eckes:
        lam_for, for2285_tables = _load_for2285_tables(
            data_dir, lam_min_um=args.lam_min_um, lam_max_um=args.lam_max_um
        )
        lam_eckes, eckes_tables = _load_eckes_tables(
            Path(args.nk_data_csv),
            args.eckes_source_id,
            lam_min_um=float(args.eckes_lam_min_um),
            lam_max_um=float(args.eckes_lam_max_um),
        )

        lam_eval = lam_for
        if args.lambda_samples is not None:
            lam_eval = np.geomspace(float(lam_eval[0]), float(lam_eval[-1]), args.lambda_samples)
        eckes_mask = (lam_eval >= args.eckes_lam_min_um) & (lam_eval <= args.eckes_lam_max_um)
        if not np.any(eckes_mask):
            raise ValueError("Eckes wavelength range does not intersect the evaluation grid")

        nk_axes_by_temp = []
        for T in temps:
            nk_axes = []
            for axis in ("a", "b", "c"):
                for2285_grid = for2285_tables[axis]
                n_for = _interp_temperature_grid(for2285_grid.temps, for2285_grid.n_vals, float(T))
                k_for = _interp_temperature_grid(for2285_grid.temps, for2285_grid.k_vals, float(T))
                if not np.array_equal(lam_eval, lam_for):
                    n_for = np.interp(lam_eval, lam_for, n_for)
                    k_for = np.interp(lam_eval, lam_for, k_for)

                eckes_grid = eckes_tables[axis]
                n_eckes = _interp_temperature_grid(eckes_grid.temps, eckes_grid.n_vals, float(T))
                k_eckes = _interp_temperature_grid(eckes_grid.temps, eckes_grid.k_vals, float(T))
                n_eckes_interp = np.interp(lam_eval[eckes_mask], lam_eckes, n_eckes)
                k_eckes_interp = np.interp(lam_eval[eckes_mask], lam_eckes, k_eckes)

                n_for = n_for.copy()
                k_for = k_for.copy()
                n_for[eckes_mask] = n_eckes_interp
                k_for[eckes_mask] = k_eckes_interp
                nk_axes.append((n_for, k_for))
            nk_axes_by_temp.append(nk_axes)

        qpr = compute_planck_mean_qpr_by_temperature(
            sizes, temps, lam_eval, nk_axes_by_temp, x_max=x_max
        )
    else:
        nk_temp = _resolve_temperature_tag(args.nk_temperature)
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

    if use_eckes:
        meta_path = Path(args.meta_out) if args.meta_out else out_path.with_suffix(".meta.json")
        metadata = {
            "qpr_table": "forsterite_phase2_ready",
            "for2285": {
                "data_dir": str(data_dir),
                "temperatures_K": [float(t) for t in for2285_tables["a"].temps.tolist()],
                "wavelength_um_min": float(lam_for[0]),
                "wavelength_um_max": float(lam_for[-1]),
                "temperature_interpolation": "linear with clamp to grid",
                "outside_eckes_policy": "use_for2285",
            },
            "eckes_poseidon": {
                "nk_data_csv": str(args.nk_data_csv),
                "source_id": args.eckes_source_id,
                "wavelength_um_min": float(args.eckes_lam_min_um),
                "wavelength_um_max": float(args.eckes_lam_max_um),
                "temperature_interpolation": "linear with clamp to [295,1948]",
                "axis_map": {"B1U": "c", "B2U": "b", "B3U": "a"},
                "license": "CC BY 4.0",
            },
            "axis_average": "axis-wise Mie -> 1/3 mean",
        }
        meta_path.write_text(json.dumps(metadata, indent=2))
        print(f"Wrote: {meta_path}")


if __name__ == "__main__":
    main()
