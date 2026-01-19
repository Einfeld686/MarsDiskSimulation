#!/usr/bin/env python3
"""Render optical depth heatmaps for temp_supply_sweep_1d runs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

SECONDS_PER_YEAR = 3.15576e7


def _collect_series_paths(series_dir: Path) -> list[Path]:
    run_parquet = series_dir / "run.parquet"
    if run_parquet.exists():
        return [run_parquet]
    return sorted(series_dir.glob("run_chunk_*.parquet"))


def _read_parquet(path: Path, columns: list[str]):
    import pandas as pd

    try:
        import pyarrow.parquet as pq

        schema = pq.read_schema(path)
        available = set(schema.names)
        keep = [c for c in columns if c in available]
        if keep:
            return pd.read_parquet(path, columns=keep)
    except Exception:
        pass
    return pd.read_parquet(path, columns=columns)


def _load_tau_frame(run_dir: Path):
    series_dir = run_dir / "series"
    if not series_dir.exists():
        print(f"[warn] missing series dir: {series_dir}", file=sys.stderr)
        return None
    frames = []
    for path in _collect_series_paths(series_dir):
        df = _read_parquet(path, ["time", "r_RM", "tau"])
        if df is None or df.empty:
            continue
        frames.append(df)
    if not frames:
        print(f"[warn] no series data: {run_dir}", file=sys.stderr)
        return None
    import pandas as pd

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.dropna(subset=["time", "r_RM", "tau"])
    if merged.empty:
        print(f"[warn] empty tau data: {run_dir}", file=sys.stderr)
        return None
    return merged


def _edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 1:
        return np.array([values[0] - 0.5, values[0] + 0.5], dtype=float)
    diffs = np.diff(values)
    edges = np.empty(values.size + 1, dtype=float)
    edges[1:-1] = (values[:-1] + values[1:]) * 0.5
    edges[0] = values[0] - diffs[0] * 0.5
    edges[-1] = values[-1] + diffs[-1] * 0.5
    return edges


def _format_title(name: str) -> str:
    parts = name.split("_")
    temp = None
    eps = None
    tau = None
    inc = None
    for part in parts:
        if part.startswith("T"):
            temp = part[1:]
        elif part.startswith("eps"):
            eps = part[3:]
        elif part.startswith("tau"):
            tau = part[3:]
        elif part.startswith("i"):
            inc = part[1:]
    if temp and eps and tau and inc:
        temp = temp.replace("p", ".")
        eps = eps.replace("p", ".")
        tau = tau.replace("p", ".")
        inc = inc.replace("p", ".")
        return f"T={temp}K eps={eps} tau={tau} i={inc}"
    return name


def _pivot_tau(df):
    import pandas as pd

    df = df.copy()
    df["time_yr"] = df["time"].to_numpy(dtype=float) / SECONDS_PER_YEAR
    pivot = df.pivot_table(index="r_RM", columns="time_yr", values="tau", aggfunc="mean")
    pivot = pivot.sort_index()
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)
    r_vals = pivot.index.to_numpy(dtype=float)
    t_vals = pivot.columns.to_numpy(dtype=float)
    z_vals = pivot.to_numpy()
    return t_vals, r_vals, z_vals


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot optical depth heatmaps for i00p05 runs.")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(
            "out/temp_supply_sweep_1d/20260113-162712__6031b1edd__seed1709094340"
        ),
        help="Root directory containing sweep run subdirectories.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("figures/thesis"),
        help="Output directory for heatmaps.",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="i00p05",
        help="Substring used to filter run directory names.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.run_root.exists():
        print(f"[error] run root not found: {args.run_root}", file=sys.stderr)
        return 1

    run_dirs = sorted([p for p in args.run_root.iterdir() if p.is_dir() and args.pattern in p.name])
    if not run_dirs:
        print(f"[error] no run directories matched: {args.pattern}", file=sys.stderr)
        return 1

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Hiragino Sans", "Hiragino Sans GB", "DejaVu Sans"]

    grids = []
    tau_min = np.inf
    tau_max = -np.inf
    t_min_global = np.inf
    t_max_global = -np.inf
    for run_dir in run_dirs:
        df = _load_tau_frame(run_dir)
        if df is None:
            continue
        t_vals, r_vals, z_vals = _pivot_tau(df)
        if z_vals.size == 0:
            continue
        tau_min = min(tau_min, float(np.nanmin(z_vals)))
        tau_max = max(tau_max, float(np.nanmax(z_vals)))
        t_min_global = min(t_min_global, float(np.nanmin(t_vals)))
        t_max_global = max(t_max_global, float(np.nanmax(t_vals)))
        grids.append((run_dir.name, t_vals, r_vals, z_vals))

    if not grids:
        print("[error] no tau data available", file=sys.stderr)
        return 1

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cmap = plt.get_cmap("cividis")

    for name, t_vals, r_vals, z_vals in grids:
        t_edges = _edges(t_vals)
        r_edges = _edges(r_vals)
        fig, ax = plt.subplots(figsize=(7.6, 4.8))
        mesh = ax.pcolormesh(
            t_edges,
            r_edges,
            z_vals,
            shading="auto",
            cmap=cmap,
            vmin=tau_min,
            vmax=tau_max,
        )
        cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
        cbar.set_label("光学的厚さ τ")
        ax.set_xlabel("時間 [yr]")
        ax.set_ylabel("火星距離 [R_Mars]")
        ax.set_title(_format_title(name))
        ax.set_xlim(t_min_global, t_max_global)
        ax.set_ylim(r_edges[0], r_edges[-1])
        ax.grid(False)
        fig.tight_layout()

        out_path = out_dir / f"optical_depth_heatmap_{name}.png"
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
        print(f"[info] saved {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
