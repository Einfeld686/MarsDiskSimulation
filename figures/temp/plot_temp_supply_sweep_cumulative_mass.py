#!/usr/bin/env python3
"""Plot cumulative mass vs time for each sweep in a temp_supply_sweep_1d run."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

SECONDS_PER_YEAR = 3.15576e7
DEFAULT_REF_MASS = 1e-5


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


def _aggregate_series(run_dir: Path):
    series_dir = run_dir / "series"
    if not series_dir.exists():
        print(f"[warn] missing series dir: {series_dir}", file=sys.stderr)
        return None

    columns = ["time", "M_loss_cum", "mass_lost_by_blowout", "mass_lost_by_sinks"]
    frames = []
    for path in _collect_series_paths(series_dir):
        df = _read_parquet(path, columns)
        if df is None or df.empty:
            continue
        if "M_loss_cum" not in df.columns:
            if "mass_lost_by_blowout" in df.columns or "mass_lost_by_sinks" in df.columns:
                df["M_loss_cum"] = df.get("mass_lost_by_blowout", 0.0) + df.get(
                    "mass_lost_by_sinks", 0.0
                )
            else:
                continue
        grouped = df.groupby("time", as_index=False)["M_loss_cum"].sum()
        frames.append(grouped)

    if not frames:
        return None
    import pandas as pd

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values("time")
    merged = merged.drop_duplicates(subset="time", keep="last")
    return merged


def _downsample(df, max_points: int):
    if df is None or df.empty or max_points <= 0:
        return df
    step = max(len(df) // max_points, 1)
    return df.iloc[::step].copy()


def _format_label(name: str) -> str:
    parts = name.split("_")
    temp = None
    eps = None
    tau = None
    for part in parts:
        if part.startswith("T"):
            temp = part[1:]
        elif part.startswith("eps"):
            eps = part[3:]
        elif part.startswith("tau"):
            tau = part[3:]
    if temp and eps and tau:
        temp = temp.replace("p", ".")
        eps = eps.replace("p", ".")
        tau = tau.replace("p", ".")
        return f"T={temp}K eps={eps} tau={tau}"
    return name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot cumulative mass vs time for temp_supply_sweep_1d runs."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(
            "out/temp_supply_sweep_1d/20260111-201706__080ef164f__seed608796459"
        ),
        help="Root directory containing sweep run subdirectories.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("figures/temp/temp_supply_sweep_1d_cumulative_mass.png"),
        help="Output figure path.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=4000,
        help="Maximum points per series after downsampling.",
    )
    parser.add_argument(
        "--ref-mass",
        type=float,
        default=DEFAULT_REF_MASS,
        help="Reference mass to normalize cumulative mass (M_Mars).",
    )
    args = parser.parse_args()

    if not args.run_root.exists():
        print(f"[error] run root not found: {args.run_root}", file=sys.stderr)
        return 1

    run_dirs = sorted([p for p in args.run_root.iterdir() if p.is_dir()])
    if not run_dirs:
        print(f"[error] no run directories under: {args.run_root}", file=sys.stderr)
        return 1

    series = []
    for run_dir in run_dirs:
        df = _aggregate_series(run_dir)
        if df is None or df.empty:
            print(f"[warn] no data for: {run_dir.name}", file=sys.stderr)
            continue
        df = _downsample(df, args.max_points)
        years = df["time"].to_numpy(dtype=float) / SECONDS_PER_YEAR
        ref_mass = float(args.ref_mass)
        mass = df["M_loss_cum"].to_numpy(dtype=float) / ref_mass
        series.append((_format_label(run_dir.name), years, mass))

    if not series:
        print("[error] no series data to plot", file=sys.stderr)
        return 1

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogFormatterMathtext

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab10.colors
    for idx, (label, years, mass) in enumerate(series):
        color = colors[idx % len(colors)]
        ax.plot(years, mass, label=label, lw=1.2, alpha=0.85, color=color)

    ax.set_xlabel("Time [yr]")
    ax.set_ylabel(f"Cumulative mass / {args.ref_mass:.1e} M_Mars")
    ax.set_yscale("log")
    ticks = [1e-2, 1e-1, 1e0, 1e1]
    ax.set_ylim(ticks[0], ticks[-1])
    ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(LogFormatterMathtext(base=10.0))
    ax.grid(True, which="major", axis="y", alpha=0.35)
    ax.grid(True, axis="x", alpha=0.3)
    ax.legend(ncol=2, fontsize=8, frameon=False)
    fig.suptitle(args.run_root.name)
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200)
    plt.close(fig)
    print(f"[info] saved figure: {args.out} ({len(series)} series)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
