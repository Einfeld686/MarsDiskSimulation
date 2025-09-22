"""Output helper utilities.

The routines in this module provide thin wrappers around :mod:`pandas`
functionality to serialise simulation results.  Parquet is used for time
series data, JSON for run summaries and CSV for diagnostic mass budget
checks.  All functions ensure that destination directories are created when
necessary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping
import json

import pandas as pd


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to a Parquet file using ``pyarrow``.

    Parameters
    ----------
    df:
        Table to serialise.
    path:
        Destination file path.
    """
    _ensure_parent(path)
    df.to_parquet(path, engine="pyarrow", index=False)


def write_summary(summary: Mapping[str, Any], path: Path) -> None:
    """Write a summary dictionary to ``summary.json``.

    The JSON file is formatted with a small indentation for human
    readability.
    """
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)


def write_run_config(config: Mapping[str, Any], path: Path) -> None:
    """Persist the deterministic run configuration metadata."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)


def write_mass_budget(records: Iterable[Mapping[str, Any]], path: Path) -> None:
    """Write mass conservation diagnostics to a CSV file."""
    _ensure_parent(path)
    df = pd.DataFrame(list(records))
    df.to_csv(path, index=False)
