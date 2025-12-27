#!/usr/bin/env python3
"""Plot Smol mass-error diagnostics from a run directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.dataset as ds

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from paper.plot_style import apply_default_style
except Exception:  # pragma: no cover - optional styling
    apply_default_style = None


def _load_series(run_dir: Path, columns: Iterable[str]) -> pd.DataFrame:
    series_dir = run_dir / "series"
    run_parquet = series_dir / "run.parquet"
    if run_parquet.exists():
        return pd.read_parquet(run_parquet, columns=list(columns))

    chunk_files = sorted(series_dir.glob("run_chunk_*.parquet"))
    if not chunk_files:
        raise FileNotFoundError(f"No series/run.parquet or run_chunk_*.parquet found under {series_dir}")

    dataset = ds.dataset(chunk_files, format="parquet")
    cols = [col for col in columns if col in dataset.schema.names]
    table = dataset.to_table(columns=cols)
    return table.to_pandas()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Smol mass-error diagnostics from a run directory.")
    parser.add_argument("--run-dir", required=True, type=Path, help="Path to a single run output directory.")
    parser.add_argument("--cell-index", type=int, help="Cell index to plot for 1D runs.")
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Downsample every N points (default: 1, no downsampling).",
    )
    parser.add_argument("--out", type=Path, help="Output PNG path (default: run_dir/figures/smol_mass_error.png).")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    columns = ["time", "smol_mass_error", "smol_mass_budget_delta", "cell_index"]
    df = _load_series(run_dir, columns=columns)
    if "smol_mass_error" not in df.columns:
        raise SystemExit("smol_mass_error is missing from the series output; rerun after enabling it.")

    if "cell_index" in df.columns:
        if args.cell_index is not None:
            df = df[df["cell_index"] == args.cell_index]
            label_suffix = f"cell {args.cell_index}"
        else:
            df = df.groupby("time", as_index=False).max(numeric_only=True)
            label_suffix = "max over cells"
    else:
        label_suffix = "0D"

    df = df.sort_values("time")
    if args.stride and args.stride > 1:
        df = df.iloc[:: args.stride]

    if apply_default_style:
        apply_default_style()

    fig, ax1 = plt.subplots()
    ax1.plot(df["time"], df["smol_mass_error"], label=f"smol_mass_error ({label_suffix})")
    ax1.set_xlabel("time [s]")
    ax1.set_ylabel("smol_mass_error [dimensionless]")
    ax1.grid(True, alpha=0.3)

    if "smol_mass_budget_delta" in df.columns and df["smol_mass_budget_delta"].notna().any():
        ax2 = ax1.twinx()
        ax2.plot(
            df["time"],
            df["smol_mass_budget_delta"],
            color="tab:orange",
            alpha=0.7,
            label="smol_mass_budget_delta",
        )
        ax2.axhline(0.0, color="tab:orange", linestyle="--", linewidth=1.0, alpha=0.5)
        ax2.set_ylabel("smol_mass_budget_delta [kg m^-2]")
        ax2.legend(loc="upper right", fontsize=9)

    ax1.legend(loc="upper left", fontsize=9)
    ax1.set_title("Smol mass error")
    out_path = args.out or (run_dir / "figures" / "smol_mass_error.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
