#!/usr/bin/env python3
"""Aggregate temp_supply_sweep batch results into summary CSV and heatmaps.

Usage:
    python -m tools.plotting.make_sweep_summary --batch-dir <path>
    python -m tools.plotting.make_sweep_summary --batch-dir out/temp_supply_sweep/<ts>__<sha>__seed<n>/

Reads summary.json from each run subdirectory and produces:
- sweep_summary.csv: Aggregated metrics for all cases
- fig_sweep_mloss.png: M_loss heatmap (T × mu, phi panels)
- fig_sweep_clip.png: supply_clip_time_fraction heatmap
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass
class SweepCase:
    """Parsed metadata from a single run subdirectory."""

    run_dir: Path
    T_M: float
    epsilon_mix: float
    phi: float
    M_loss: float = float("nan")
    M_out_cum: float = float("nan")
    M_sink_cum: float = float("nan")
    supply_clip_time_fraction: float = float("nan")
    mass_budget_max_error_percent: float = float("nan")
    orbits_completed: float = float("nan")
    effective_prod_rate_kg_m2_s: float = float("nan")
    tau_vertical_median: float = float("nan")
    extra: Dict[str, Any] = field(default_factory=dict)


# Pattern to extract T, mu (epsilon_mix), and phi from directory name
# Examples: T6000_mu1p0_phi20, T4000_mu0p5_phi37
DIR_PATTERN = re.compile(
    r"T(?P<T>\d+)_mu(?P<mu>[\d]+p[\d]+|\d+(?:\.\d+)?)_phi(?P<phi>\d+)"
)


def parse_dir_name(name: str) -> Optional[tuple[float, float, float]]:
    """Extract (T_M, epsilon_mix, phi) from directory name."""
    match = DIR_PATTERN.search(name)
    if not match:
        return None
    t_str = match.group("T")
    mu_str = match.group("mu").replace("p", ".")
    phi_str = match.group("phi")
    try:
        return float(t_str), float(mu_str), float(phi_str) / 100.0
    except ValueError:
        return None


def load_case(run_dir: Path) -> Optional[SweepCase]:
    """Load summary.json and construct a SweepCase."""
    parsed = parse_dir_name(run_dir.name)
    if parsed is None:
        return None
    T_M, epsilon_mix, phi = parsed

    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return SweepCase(run_dir=run_dir, T_M=T_M, epsilon_mix=epsilon_mix, phi=phi)

    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        return SweepCase(run_dir=run_dir, T_M=T_M, epsilon_mix=epsilon_mix, phi=phi)

    # Extract supply clipping info (may be nested)
    clip_frac = summary.get("supply_clip_time_fraction")
    if clip_frac is None:
        clip_info = summary.get("supply_clipping", {})
        if isinstance(clip_info, dict):
            clip_frac = clip_info.get("clip_time_fraction")

    # Extract tau_vertical_median if available
    tau_median = summary.get("tau_vertical_median")
    if tau_median is None:
        tau_median = summary.get("tau_median")

    return SweepCase(
        run_dir=run_dir,
        T_M=T_M,
        epsilon_mix=epsilon_mix,
        phi=phi,
        M_loss=float(summary.get("M_loss", float("nan"))),
        M_out_cum=float(summary.get("M_out_cum", float("nan"))),
        M_sink_cum=float(summary.get("M_sink_cum", float("nan"))),
        supply_clip_time_fraction=float(clip_frac) if clip_frac is not None else float("nan"),
        mass_budget_max_error_percent=float(
            summary.get("mass_budget_max_error_percent", float("nan"))
        ),
        orbits_completed=float(summary.get("orbits_completed", float("nan"))),
        effective_prod_rate_kg_m2_s=float(
            summary.get("effective_prod_rate_kg_m2_s", float("nan"))
        ),
        tau_vertical_median=float(tau_median) if tau_median is not None else float("nan"),
    )


def discover_cases(batch_dir: Path) -> List[SweepCase]:
    """Walk batch directory and load all valid cases."""
    cases: List[SweepCase] = []
    for entry in sorted(batch_dir.iterdir()):
        if not entry.is_dir():
            continue
        case = load_case(entry)
        if case is not None:
            cases.append(case)
    return cases


def cases_to_dataframe(cases: Sequence[SweepCase]) -> pd.DataFrame:
    """Convert list of SweepCase to DataFrame."""
    records = []
    for c in cases:
        records.append(
            {
                "run_dir": str(c.run_dir),
                "T_M": c.T_M,
                "epsilon_mix": c.epsilon_mix,
                "phi": c.phi,
                "M_loss": c.M_loss,
                "M_out_cum": c.M_out_cum,
                "M_sink_cum": c.M_sink_cum,
                "supply_clip_time_fraction": c.supply_clip_time_fraction,
                "mass_budget_max_error_percent": c.mass_budget_max_error_percent,
                "orbits_completed": c.orbits_completed,
                "effective_prod_rate_kg_m2_s": c.effective_prod_rate_kg_m2_s,
                "tau_vertical_median": c.tau_vertical_median,
            }
        )
    return pd.DataFrame(records)


def plot_heatmap_by_phi(
    df: pd.DataFrame,
    value_col: str,
    out_path: Path,
    title: str,
    cmap: str = "viridis",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> None:
    """Create faceted heatmap with phi as panel axis, T_M vs epsilon_mix."""
    phi_values = sorted(df["phi"].unique())
    n_panels = len(phi_values)
    if n_panels == 0:
        return

    fig, axes = plt.subplots(
        1, n_panels, figsize=(4 * n_panels + 1, 4), squeeze=False, sharey=True
    )
    axes = axes[0]

    T_unique = sorted(df["T_M"].unique())
    mu_unique = sorted(df["epsilon_mix"].unique())

    for idx, phi_val in enumerate(phi_values):
        ax = axes[idx]
        subset = df[df["phi"] == phi_val]

        grid = np.full((len(T_unique), len(mu_unique)), np.nan)
        T_idx = {v: i for i, v in enumerate(T_unique)}
        mu_idx = {v: i for i, v in enumerate(mu_unique)}

        for _, row in subset.iterrows():
            ti = T_idx.get(row["T_M"])
            mi = mu_idx.get(row["epsilon_mix"])
            if ti is not None and mi is not None:
                grid[ti, mi] = row[value_col]

        im = ax.imshow(
            grid,
            origin="lower",
            aspect="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            extent=[
                min(mu_unique) - 0.05,
                max(mu_unique) + 0.05,
                min(T_unique) - 200,
                max(T_unique) + 200,
            ],
        )
        ax.set_xlabel("epsilon_mix")
        ax.set_title(f"phi = {phi_val:.2f}")
        if idx == 0:
            ax.set_ylabel("T_M [K]")

        # Annotate values
        for ti, t_val in enumerate(T_unique):
            for mi, mu_val in enumerate(mu_unique):
                val = grid[ti, mi]
                if np.isfinite(val):
                    ax.text(
                        mu_val,
                        t_val,
                        f"{val:.2e}" if abs(val) < 0.01 or abs(val) > 100 else f"{val:.2f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white" if val > (vmax or np.nanmax(grid)) * 0.5 else "black",
                    )

    fig.colorbar(im, ax=axes, label=value_col, shrink=0.8)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_sensitivity_matrix(
    df: pd.DataFrame,
    out_path: Path,
) -> None:
    """Create a 3x3 sensitivity matrix showing M_loss across parameter combinations."""
    fig, axes = plt.subplots(3, 3, figsize=(12, 10))

    # Row: fixed parameter (T, mu, phi)
    # Col: metric (M_loss, supply_clip, tau_median)
    metrics = [
        ("M_loss", "M_loss [M_Mars]", "plasma"),
        ("supply_clip_time_fraction", "Supply Clip Fraction", "Reds"),
        ("tau_vertical_median", "τ_vertical median", "Blues"),
    ]
    fixed_params = ["T_M", "epsilon_mix", "phi"]

    for row_idx, fixed in enumerate(fixed_params):
        other_params = [p for p in fixed_params if p != fixed]
        fixed_values = sorted(df[fixed].unique())
        fixed_mid = fixed_values[len(fixed_values) // 2] if fixed_values else None

        for col_idx, (metric, label, cmap) in enumerate(metrics):
            ax = axes[row_idx, col_idx]

            if fixed_mid is None:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                continue

            subset = df[df[fixed] == fixed_mid]
            x_param, y_param = other_params

            x_unique = sorted(subset[x_param].unique())
            y_unique = sorted(subset[y_param].unique())

            if not x_unique or not y_unique:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
                continue

            grid = np.full((len(y_unique), len(x_unique)), np.nan)
            for _, row in subset.iterrows():
                xi = x_unique.index(row[x_param]) if row[x_param] in x_unique else None
                yi = y_unique.index(row[y_param]) if row[y_param] in y_unique else None
                if xi is not None and yi is not None:
                    grid[yi, xi] = row[metric]

            im = ax.imshow(
                grid,
                origin="lower",
                aspect="auto",
                cmap=cmap,
            )
            ax.set_xticks(range(len(x_unique)))
            ax.set_xticklabels([f"{v:.2g}" for v in x_unique], fontsize=8)
            ax.set_yticks(range(len(y_unique)))
            ax.set_yticklabels([f"{v:.2g}" for v in y_unique], fontsize=8)
            ax.set_xlabel(x_param)
            ax.set_ylabel(y_param)
            ax.set_title(f"{label}\n({fixed}={fixed_mid:.0f})" if fixed == "T_M" else f"{label}\n({fixed}={fixed_mid:.2g})")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Path to temp_supply_sweep batch directory (contains T*_mu*_phi* subdirs).",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="Output CSV path (default: <batch-dir>/sweep_summary.csv).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation, only output CSV.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    batch_dir = args.batch_dir.resolve()

    if not batch_dir.exists():
        print(f"[error] Batch directory not found: {batch_dir}")
        return 1

    cases = discover_cases(batch_dir)
    if not cases:
        print(f"[warn] No valid sweep cases found in {batch_dir}")
        return 0

    print(f"[info] Found {len(cases)} sweep cases in {batch_dir.name}")

    df = cases_to_dataframe(cases)

    # Write CSV
    csv_path = args.out_csv or (batch_dir / "sweep_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"[info] Wrote summary CSV: {csv_path}")

    if args.no_plots:
        return 0

    # Generate heatmaps
    plot_heatmap_by_phi(
        df,
        "M_loss",
        batch_dir / "fig_sweep_mloss.png",
        "Total Mass Loss (M_loss) by Parameter",
        cmap="plasma",
    )
    print(f"[info] Wrote M_loss heatmap: {batch_dir / 'fig_sweep_mloss.png'}")

    plot_heatmap_by_phi(
        df,
        "supply_clip_time_fraction",
        batch_dir / "fig_sweep_clip.png",
        "Supply Clipping Time Fraction",
        cmap="Reds",
        vmin=0.0,
        vmax=1.0,
    )
    print(f"[info] Wrote clip heatmap: {batch_dir / 'fig_sweep_clip.png'}")

    # Sensitivity matrix
    plot_sensitivity_matrix(df, batch_dir / "fig_sweep_sensitivity.png")
    print(f"[info] Wrote sensitivity matrix: {batch_dir / 'fig_sweep_sensitivity.png'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
