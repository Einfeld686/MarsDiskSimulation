#!/usr/bin/env python3
"""Concatenate time-series outputs from multiple simulation runs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd


def _iter_series_paths(root: Path) -> Iterable[Path]:
    """Yield Parquet files residing two levels below ``root``."""

    if not root.exists():
        return []
    return sorted(root.glob("*/*/series/run.parquet"))


def collect_series(roots: List[Path], out_path: Path) -> None:
    """Aggregate series tables under ``roots`` and write a combined Parquet file."""

    frames: list[pd.DataFrame] = []
    for root in roots:
        for series_path in _iter_series_paths(root):
            run_dir = series_path.parent.parent
            case_dir = run_dir.parent
            df = pd.read_parquet(series_path)
            df = df.assign(case_id=case_dir.name, outdir=str(run_dir))
            frames.append(df)
    if not frames:
        raise FileNotFoundError("No series/run.parquet files found under the provided roots.")
    combined = pd.concat(frames, ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect series/run.parquet outputs into one table.")
    parser.add_argument(
        "--roots",
        nargs="+",
        required=True,
        help="Root directories containing */*/series/run.parquet outputs.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Destination Parquet file.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the collect_series CLI."""

    args = _parse_args()
    roots = [Path(item).expanduser().resolve() for item in args.roots]
    out_path = Path(args.out).expanduser().resolve()
    collect_series(roots, out_path)


if __name__ == "__main__":
    main()
