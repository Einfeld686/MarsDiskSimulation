"""IO helpers for the SiO2 cooling map."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .model import YEAR_SECONDS


def ensure_outputs_dir() -> Path:
    """Create and return the outputs directory."""

    outdir = Path(__file__).resolve().parent / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def write_csv(
    r_over_Rmars: np.ndarray,
    arrival_glass_s: np.ndarray,
    arrival_liquidus_s: np.ndarray,
    path: Path,
) -> None:
    """Write arrival times to CSV."""

    df = pd.DataFrame(
        {
            "r_over_Rmars": np.asarray(r_over_Rmars, dtype=float),
            "t_to_Tglass_yr": np.asarray(arrival_glass_s, dtype=float) / YEAR_SECONDS,
            "t_to_Tliquidus_yr": np.asarray(arrival_liquidus_s, dtype=float) / YEAR_SECONDS,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _format_stat(values: Iterable[float]) -> str:
    arr = np.array(list(values), dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return "none"
    return f"{float(np.nanmedian(finite)):.4g}"


def write_log(
    T0: float,
    r_over_Rmars: np.ndarray,
    arrival_glass_s: np.ndarray,
    arrival_liquidus_s: np.ndarray,
    path: Path,
) -> None:
    """Write a minimal plain-text log for quick inspection."""

    r_arr = np.asarray(r_over_Rmars, dtype=float)
    glass = np.asarray(arrival_glass_s, dtype=float)
    liquidus = np.asarray(arrival_liquidus_s, dtype=float)
    stats = []
    for label, values in (("glass", glass), ("liquidus", liquidus)):
        finite_mask = np.isfinite(values)
        reached_r = r_arr[finite_mask]
        if reached_r.size > 0:
            r_min = f"{float(reached_r.min()):.4g}"
            r_max = f"{float(reached_r.max()):.4g}"
        else:
            r_min = r_max = "none"
        stats.append(
            {
                "label": label,
                "r_min": r_min,
                "r_max": r_max,
                "median_time_yr": _format_stat(values / YEAR_SECONDS),
            }
        )

    lines = [
        f"T0_K: {T0:g}",
    ]
    for entry in stats:
        lines.append(f"{entry['label']}_r_min: {entry['r_min']}")
        lines.append(f"{entry['label']}_r_max: {entry['r_max']}")
        lines.append(f"{entry['label']}_median_time_yr: {entry['median_time_yr']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


__all__ = ["ensure_outputs_dir", "write_csv", "write_log"]
