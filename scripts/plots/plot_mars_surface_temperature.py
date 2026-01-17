#!/usr/bin/env python3
"""Plot Mars surface temperature vs time from precomputed tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk.physics import radiation
from paper.plot_style import apply_default_style
from siO2_disk_cooling.model import CoolingParams, YEAR_SECONDS, hyodo_cooling_time, hyodo_temperature


TIME_COLUMNS: Tuple[str, ...] = (
    "time_year",
    "time_yr",
    "time_years",
    "time_day",
    "time_days",
    "time_s",
    "time_sec",
    "time_seconds",
)
TEMP_COLUMNS: Tuple[str, ...] = ("T_K", "T_M", "temperature_K", "temperature")


def _resolve_table_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        parquet_path = path.with_suffix(".parquet")
        if parquet_path.exists():
            if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
                return parquet_path
    elif suffix in {".parquet", ".pq"} and not path.exists():
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
    return path


def _infer_columns(df: pd.DataFrame) -> Tuple[str, str]:
    time_col = next((col for col in TIME_COLUMNS if col in df.columns), None)
    if time_col is None:
        raise ValueError(f"Missing time column. Expected one of: {', '.join(TIME_COLUMNS)}")
    temp_col = next((col for col in TEMP_COLUMNS if col in df.columns), None)
    if temp_col is None:
        raise ValueError(f"Missing temperature column. Expected one of: {', '.join(TEMP_COLUMNS)}")
    return time_col, temp_col


def _time_to_years(values: pd.Series, column: str) -> pd.Series:
    vals = pd.to_numeric(values, errors="coerce")
    if column in {"time_day", "time_days"}:
        return vals / 365.25
    if column in {"time_s", "time_sec", "time_seconds"}:
        return vals / (365.25 * 86400.0)
    return vals


def _infer_label(path: Path) -> str:
    match = re.search(r"mars_temperature_T(?P<value>\d+(?:p\d+)?)K", path.stem)
    if match:
        raw = match.group("value").replace("p", ".")
        try:
            value = float(raw)
        except ValueError:
            value = raw
        if isinstance(value, float) and abs(value - round(value)) < 1.0e-6:
            return f"火星表面温度 {int(round(value))}K"
        return f"火星表面温度 {value}K"
    match = re.search(r"T(?P<value>\d+(?:p\d+)?)K", path.stem)
    if match:
        raw = match.group("value").replace("p", ".")
        return f"Slab T0={raw} K"
    return f"Slab {path.stem}"


def _load_table_series(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    time_col, temp_col = _infer_columns(df)
    time_years = _time_to_years(df[time_col], time_col)
    temps = pd.to_numeric(df[temp_col], errors="coerce")
    data = pd.DataFrame({"time_years": time_years, "temperature_K": temps}).dropna()
    return data.sort_values("time_years")


def _truncate_at_temperature(data: pd.DataFrame, cutoff_K: float) -> pd.DataFrame:
    if data.empty:
        return data
    if cutoff_K is None or not np.isfinite(cutoff_K):
        return data
    temps = data["temperature_K"].to_numpy(dtype=float)
    times = data["time_years"].to_numpy(dtype=float)
    idx = np.where(temps <= cutoff_K)[0]
    if idx.size == 0:
        return data
    cut = int(idx[0])
    if cut == 0:
        return data.iloc[:1].copy()
    if temps[cut] == cutoff_K:
        return data.iloc[: cut + 1].copy()
    t0, t1 = times[cut - 1], times[cut]
    y0, y1 = temps[cut - 1], temps[cut]
    if y1 == y0:
        t_cut = t1
    else:
        t_cut = t0 + (cutoff_K - y0) * (t1 - t0) / (y1 - y0)
    trimmed = data.iloc[:cut].copy()
    extra = pd.DataFrame({"time_years": [t_cut], "temperature_K": [cutoff_K]})
    return pd.concat([trimmed, extra], ignore_index=True)


def _load_density_from_json(path: Path) -> float:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    density = payload.get("density", {})
    rho = density.get("rho_kg_m3")
    if rho is None:
        raise ValueError(f"rho_kg_m3 missing in {path}")
    return float(rho)


def _compute_blowout_temperature(
    size_m: float, qpr_table: Path, rho_kg_m3: float
) -> float | None:
    if size_m <= 0.0:
        raise ValueError("blowout size must be positive")
    radiation.load_qpr_table(qpr_table)
    if qpr_table.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(qpr_table)
    else:
        df = pd.read_csv(qpr_table)
    if "T_M" not in df.columns:
        raise ValueError(f"{qpr_table} must contain a T_M column")
    temps = np.unique(df["T_M"].astype(float))
    temps = temps[(temps >= 1000.0) & (temps <= 6500.0)]
    temps.sort()
    if temps.size < 2:
        return None
    s_blow = np.array([radiation.blowout_radius(rho_kg_m3, T) for T in temps], dtype=float)
    idx = np.where(s_blow >= size_m)[0]
    if idx.size == 0:
        return None
    i = int(idx[0])
    if i == 0:
        return float(temps[0])
    t0, t1 = float(temps[i - 1]), float(temps[i])
    s0, s1 = float(s_blow[i - 1]), float(s_blow[i])
    if s1 == s0:
        return t1
    return t0 + (size_m - s0) * (t1 - t0) / (s1 - s0)


def _ensure_hyodo_grid(time_s: np.ndarray, t_stop_s: float) -> np.ndarray:
    if time_s.size == 0:
        return np.array([0.0, t_stop_s], dtype=float)
    if t_stop_s <= time_s[-1]:
        return time_s
    diffs = np.diff(time_s)
    dt_s = float(np.median(diffs[diffs > 0.0])) if diffs.size else 0.0
    if dt_s <= 0.0:
        dt_s = t_stop_s / 200.0
    extra = np.arange(time_s[-1] + dt_s, t_stop_s + 0.5 * dt_s, dt_s, dtype=float)
    return np.concatenate([time_s, extra])


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table",
        type=Path,
        action="append",
        default=None,
        help="Path to a Mars temperature table (CSV or Parquet). Repeatable.",
    )
    parser.add_argument(
        "--label",
        type=str,
        action="append",
        default=None,
        help="Optional label per table (same order as --table).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figures/mars_surface_temperature_vs_time.png"),
        help="Output PNG path.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Mars surface temperature cooling",
        help="Plot title.",
    )
    parser.add_argument(
        "--cutoff-temp",
        type=float,
        default=1000.0,
        help="Stop plotting each curve once the temperature reaches this value [K].",
    )
    parser.add_argument(
        "--no-blowout-line",
        action="store_true",
        help="Disable the horizontal blowout threshold line.",
    )
    parser.add_argument(
        "--blowout-size-um",
        type=float,
        default=0.1,
        help="Grain size for the blowout threshold line [um].",
    )
    parser.add_argument(
        "--blowout-qpr-table",
        type=Path,
        default=Path("data/qpr_planck_forsterite_mie.csv"),
        help="Q_pr table used to compute the blowout threshold line.",
    )
    parser.add_argument(
        "--blowout-density-json",
        type=Path,
        default=Path("data/forsterite_material_data/forsterite_material_properties.json"),
        help="Material properties JSON for the blowout density.",
    )
    parser.add_argument(
        "--blowout-rho",
        type=float,
        default=None,
        help="Override density for the blowout threshold [kg/m^3].",
    )
    parser.add_argument(
        "--include-hyodo",
        action="store_true",
        help="Include the Hyodo linear approximation from 4000 K to 1000 K.",
    )
    parser.add_argument(
        "--hyodo-T0",
        type=float,
        default=4000.0,
        help="Initial temperature for the Hyodo approximation [K].",
    )
    parser.add_argument(
        "--hyodo-floor",
        type=float,
        default=1000.0,
        help="Floor temperature for the Hyodo approximation [K].",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    table_paths = args.table or [
        Path("data/mars_temperature_T4000p0K.csv"),
        Path("data/mars_temperature_T3000p0K.csv"),
    ]
    labels = args.label
    if labels is not None and len(labels) != len(table_paths):
        raise ValueError("Number of --label entries must match --table entries")

    series = []
    for idx, raw_path in enumerate(table_paths):
        table_path = _resolve_table_path(raw_path)
        if not table_path.exists():
            raise FileNotFoundError(f"Temperature table not found: {table_path}")
        data = _load_table_series(table_path)
        data = _truncate_at_temperature(data, args.cutoff_temp)
        label = labels[idx] if labels is not None else _infer_label(table_path)
        series.append((label, data))

    apply_default_style({"figure.figsize": (6.2, 3.8)})
    fig, ax = plt.subplots()
    max_time_years = 0.0
    for label, data in series:
        ax.plot(data["time_years"], data["temperature_K"], label=label)
        if not data.empty:
            max_time_years = max(max_time_years, float(data["time_years"].iloc[-1]))

    if args.include_hyodo:
        params = CoolingParams()
        t_stop_s = hyodo_cooling_time(args.hyodo_T0, args.hyodo_floor, params)
        ref_time_s = None
        if series:
            ref = max(series, key=lambda item: float(item[1]["time_years"].iloc[-1]) if not item[1].empty else 0.0)
            ref_time_s = ref[1]["time_years"].to_numpy(dtype=float) * YEAR_SECONDS
        if ref_time_s is None or ref_time_s.size == 0:
            ref_time_s = np.array([0.0, t_stop_s], dtype=float)
        time_s = _ensure_hyodo_grid(ref_time_s, t_stop_s)
        temps = hyodo_temperature(time_s, args.hyodo_T0, params, floor_K=args.hyodo_floor)
        hyodo_data = pd.DataFrame(
            {"time_years": time_s / YEAR_SECONDS, "temperature_K": temps}
        )
        hyodo_data = _truncate_at_temperature(hyodo_data, args.cutoff_temp)
        ax.plot(
            hyodo_data["time_years"],
            hyodo_data["temperature_K"],
            label="Hyodo et al., 2018",
            linestyle="--",
            color="#d95f02",
        )
        if not hyodo_data.empty:
            max_time_years = max(max_time_years, float(hyodo_data["time_years"].iloc[-1]))

    if not args.no_blowout_line:
        qpr_table = _resolve_table_path(args.blowout_qpr_table)
        if not qpr_table.exists():
            raise FileNotFoundError(f"Q_pr table not found: {qpr_table}")
        rho = (
            float(args.blowout_rho)
            if args.blowout_rho is not None
            else _load_density_from_json(args.blowout_density_json)
        )
        size_m = float(args.blowout_size_um) * 1.0e-6
        T_blow = _compute_blowout_temperature(size_m, qpr_table, rho)
        if T_blow is not None:
            ax.axhline(
                T_blow,
                color="#6a3d9a",
                linestyle=":",
                linewidth=1.4,
                label=f"{args.blowout_size_um:g} um blowout",
            )
    ax.set_xlabel("Time [yr]")
    ax.set_ylabel("Mars surface temperature [K]")
    ax.set_title(args.title)
    ax.set_xlim(left=0.0, right=max_time_years if max_time_years > 0.0 else None)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200)
    plt.close(fig)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
