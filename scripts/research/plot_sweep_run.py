#!/usr/bin/env python3
"""Quick-look plot generator for temp_supply_sweep runs.

Usage:
    python scripts/research/plot_sweep_run.py <run_dir>

This script is called by run_temp_supply_sweep.cmd to generate overview plots
after each simulation run completes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(run_dir: Path) -> int:
    """Generate overview plots for a single run directory."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError as e:
        print(f"[error] Missing dependency: {e}", file=sys.stderr)
        return 1

    series_path = run_dir / "series" / "run.parquet"
    summary_path = run_dir / "summary.json"
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    if not series_path.exists():
        print(f"[warn] series not found: {series_path}, skip plotting")
        return 0

    series_cols = [
        "time",
        "M_out_dot",
        "M_sink_dot",
        "M_loss_cum",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "s_min",
        "a_blow",
        "prod_subblow_area_rate",
        "Sigma_surf",
        "outflux_surface",
    ]

    summary: dict = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    df = pd.read_parquet(series_path, columns=series_cols)
    n = len(df)
    step = max(n // 4000, 1)
    df = df.iloc[::step].copy()
    df["time_days"] = df["time"] / 86400.0

    # Plot 1: Overview (3 subplots)
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)

    axes[0].plot(df["time_days"], df["M_out_dot"], label="M_out_dot (blowout)", lw=1.2)
    axes[0].plot(
        df["time_days"], df["M_sink_dot"], label="M_sink_dot (sinks)", lw=1.0, alpha=0.7
    )
    axes[0].set_ylabel("M_Mars / s")
    axes[0].legend(loc="upper right")
    axes[0].set_title("Mass loss rates")

    axes[1].plot(df["time_days"], df["M_loss_cum"], label="M_loss_cum (total)", lw=1.2)
    axes[1].plot(
        df["time_days"], df["mass_lost_by_blowout"], label="mass_lost_by_blowout", lw=1.0
    )
    axes[1].plot(
        df["time_days"], df["mass_lost_by_sinks"], label="mass_lost_by_sinks", lw=1.0
    )
    axes[1].set_ylabel("M_Mars")
    axes[1].legend(loc="upper left")
    axes[1].set_title("Cumulative losses")

    axes[2].plot(df["time_days"], df["s_min"], label="s_min", lw=1.0)
    axes[2].plot(df["time_days"], df["a_blow"], label="a_blow", lw=1.0, alpha=0.8)
    axes[2].set_ylabel("m")
    axes[2].set_xlabel("days")
    axes[2].set_yscale("log")
    axes[2].legend(loc="upper right")
    axes[2].set_title("Minimum size vs blowout")

    mloss = summary.get("M_loss")
    mass_err = summary.get("mass_budget_max_error_percent")
    title_lines = [run_dir.name]
    if mloss is not None:
        title_lines.append(f"M_loss={mloss:.3e} M_Mars")
    if mass_err is not None:
        title_lines.append(f"mass budget err={mass_err:.3f} pct")
    fig.suptitle(" / ".join(title_lines))
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(plots_dir / "overview.png", dpi=180)
    plt.close(fig)

    # Plot 2: Supply and surface
    fig2, ax2 = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax2[0].plot(
        df["time_days"],
        df["prod_subblow_area_rate"],
        label="prod_subblow_area_rate",
        color="tab:blue",
    )
    ax2[0].set_ylabel("kg m^-2 s^-1")
    ax2[0].set_title("Sub-blow supply rate")

    ax2[1].plot(
        df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green"
    )
    ax2[1].plot(
        df["time_days"],
        df["outflux_surface"],
        label="outflux_surface (surface blowout)",
        color="tab:red",
        alpha=0.8,
    )
    ax2[1].set_ylabel("kg m^-2 / M_Mars s^-1")
    ax2[1].set_xlabel("days")
    ax2[1].legend(loc="upper right")
    ax2[1].set_title("Surface mass and outflux")

    fig2.suptitle(run_dir.name)
    fig2.tight_layout(rect=(0, 0, 1, 0.95))
    fig2.savefig(plots_dir / "supply_surface.png", dpi=180)
    plt.close(fig2)

    print(f"[plot] saved plots to {plots_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <run_dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"[error] Directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    sys.exit(main(run_dir))
