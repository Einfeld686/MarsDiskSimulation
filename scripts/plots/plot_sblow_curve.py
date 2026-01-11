#!/usr/bin/env python3
"""Plot blow-out size vs. Mars temperature using a Q_pr table."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk.physics import radiation
from paper.plot_style import apply_default_style


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


def _load_temperatures(path: Path) -> np.ndarray:
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "T_M" not in df.columns:
        raise ValueError(f"{path} must contain a T_M column")
    temps = np.unique(df["T_M"].astype(float))
    return temps


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table",
        type=Path,
        default=Path("marsdisk/io/data/qpr_planck_sio2_generated.csv"),
        help="Path to the Q_pr table (CSV).",
    )
    parser.add_argument(
        "--rho",
        type=float,
        default=3000.0,
        help="Bulk density in kg/m^3.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out/figures"),
        help="Output directory for CSV/plots.",
    )
    parser.add_argument(
        "--basename",
        type=str,
        default="sblow_curve",
        help="Base filename for outputs (without extension).",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    table_path = _resolve_table_path(args.table)
    if not table_path.exists():
        raise FileNotFoundError(f"Q_pr table not found: {table_path}")

    radiation.load_qpr_table(table_path)
    temps = _load_temperatures(table_path)
    s_blow = np.array([radiation.blowout_radius(args.rho, T) for T in temps], dtype=float)

    df = pd.DataFrame({"T_M": temps, "s_blow_m": s_blow, "s_blow_um": s_blow * 1.0e6})
    args.outdir.mkdir(parents=True, exist_ok=True)
    csv_path = args.outdir / f"{args.basename}.csv"
    df.to_csv(csv_path, index=False)

    apply_default_style({"figure.figsize": (6.0, 4.0)})
    fig, ax = plt.subplots()
    ax.plot(df["T_M"], df["s_blow_um"], marker="o", lw=1.6)
    ax.set_xlabel(r"Mars-facing temperature $T_{\rm M}$ [K]")
    ax.set_ylabel(r"Blow-out size $s_{\rm blow}$ [$\mu$m]")
    ax.set_title("Blow-out size from Q_pr table")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(args.outdir / f"{args.basename}.{ext}")
    plt.close(fig)

    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
