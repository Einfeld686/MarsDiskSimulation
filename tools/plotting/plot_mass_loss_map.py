"""Render mass_loss_frac_per_orbit over (r/R_M, T_M) as a heatmap."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DEFAULT_CONTOURS = (0.1, 0.3, 0.5)
DEFAULT_CMAP = "magma"


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


def _parse_contours(values: Sequence[float]) -> Sequence[float]:
    levels = [float(value) for value in values if value is not None]
    return [level for level in levels if level >= 0.0]


def _build_grid(
    df: pd.DataFrame,
    column: str,
    r_values: np.ndarray,
    T_values: np.ndarray,
) -> np.ndarray:
    grid = np.full((T_values.size, r_values.size), np.nan, dtype=float)
    index_r = {float(value): idx for idx, value in enumerate(r_values)}
    index_T = {float(value): idx for idx, value in enumerate(T_values)}
    for row in df.itertuples():
        r_idx = index_r.get(float(row.r_RM))
        T_idx = index_T.get(float(row.T_M))
        if r_idx is None or T_idx is None:
            continue
        value = getattr(row, column, np.nan)
        grid[T_idx, r_idx] = float(value)
    return grid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot mass_loss_frac_per_orbit over (r/R_M, T_M)."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Input CSV produced by scripts/sweeps/sweep_mass_loss_map.py.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Destination PNG (default: fig_massloss_heatmap.png next to the CSV).",
    )
    parser.add_argument(
        "--cmap",
        type=str,
        default=DEFAULT_CMAP,
        help=f"Matplotlib colormap (default: {DEFAULT_CMAP}).",
    )
    parser.add_argument(
        "--contours",
        nargs="*",
        type=float,
        default=DEFAULT_CONTOURS,
        help="Contour levels for mass_loss_frac_per_orbit (default: 0.1 0.3 0.5).",
    )
    parser.add_argument(
        "--vmin",
        type=float,
        default=0.0,
        help="Optional lower bound for the colour scale (default: 0.0).",
    )
    parser.add_argument(
        "--vmax",
        type=float,
        default=None,
        help="Optional upper bound for the colour scale (default: data-driven).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=240,
        help="Figure resolution in DPI (default: 240).",
    )
    return parser.parse_args()


def _make_annotation(
    df: pd.DataFrame,
    contour_levels: Iterable[float],
) -> str:
    dt_ratio = float(np.nanmedian(df["dt_over_t_blow_median"])) if "dt_over_t_blow_median" in df else float("nan")
    qpr_names = sorted({Path(value).name for value in df.get("qpr_table_path", pd.Series(dtype=str)).dropna().unique()})
    contour_str = ", ".join(f"{level:.2f}" for level in contour_levels)
    lines = [
        "One-orbit coupling (gas-poor)",
        f"Contours: {contour_str}",
    ]
    if np.isfinite(dt_ratio):
        lines.append(f"median Δt/t_blow = {dt_ratio:.3f}")
    if qpr_names:
        lines.append(f"⟨Q_pr⟩ table(s): {', '.join(qpr_names)}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    csv_path = _resolve_table_path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if csv_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(csv_path)
    else:
        df = pd.read_csv(csv_path)
    required = {"r_RM", "T_M", "mass_loss_frac_per_orbit"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(f"Input CSV missing required columns: {', '.join(missing)}")

    r_values = np.sort(df["r_RM"].unique())
    T_values = np.sort(df["T_M"].unique())
    if r_values.size == 0 or T_values.size == 0:
        raise ValueError("CSV must contain at least one unique r_RM and T_M value.")

    grid_loss = _build_grid(df, "mass_loss_frac_per_orbit", r_values, T_values)
    levels = sorted(_parse_contours(args.contours))

    vmin = args.vmin
    vmax_data = float(np.nanmax(grid_loss)) if np.isfinite(grid_loss).any() else 1.0
    vmax = args.vmax if args.vmax is not None else vmax_data

    extent = (
        float(r_values.min()),
        float(r_values.max()),
        float(T_values.min()),
        float(T_values.max()),
    )

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    im = ax.imshow(
        grid_loss,
        origin="lower",
        extent=extent,
        aspect="auto",
        cmap=args.cmap,
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_xlabel("r / R_M")
    ax.set_ylabel("T_M [K]")
    ax.set_title("Mass-Loss Fraction per Orbit")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("mass_loss_frac_per_orbit")

    if levels and np.isfinite(grid_loss).any():
        masked = np.ma.masked_invalid(grid_loss)
        try:
            cs = ax.contour(
                r_values,
                T_values,
                masked,
                levels=levels,
                colors="white",
                linewidths=1.0,
                linestyles="dashed",
            )
            ax.clabel(cs, inline=True, fmt=lambda v: f"{v:.2f}", fontsize=7, colors="white")
        except ValueError:
            pass  # Degenerate grids can fail; ignore gracefully.

    annotation = _make_annotation(df, levels)
    ax.text(
        0.02,
        0.98,
        annotation,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
    )

    out_path = args.out
    if out_path is None:
        out_path = csv_path.parent / "fig_massloss_heatmap.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=args.dpi)
    plt.close(fig)


if __name__ == "__main__":
    main()
