"""Plotting helpers for the SiO2 cooling map."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import matplotlib.pyplot as plt

from .model import CoolingParams, YEAR_SECONDS


def _arrival_field(time_s: np.ndarray, arrival_s: np.ndarray) -> np.ndarray:
    time_arr = np.asarray(time_s, dtype=float)
    arrivals = np.asarray(arrival_s, dtype=float)
    time_mat = time_arr[:, np.newaxis]
    arrival_mat = arrivals[np.newaxis, :]
    return np.where(time_mat >= arrival_mat, arrival_mat / YEAR_SECONDS, np.nan)


def plot_arrival_map(
    r_over_Rmars: np.ndarray,
    time_s: np.ndarray,
    arrival_glass_s: np.ndarray,
    arrival_liquidus_s: np.ndarray,
    output_path: Path,
    *,
    T0: float,
    params: CoolingParams,
) -> None:
    """Render the arrival map to a PNG file."""

    time_years = np.asarray(time_s, dtype=float) / YEAR_SECONDS
    glass_field = _arrival_field(time_s, arrival_glass_s)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    mesh = ax.pcolormesh(
        np.asarray(r_over_Rmars, dtype=float),
        time_years,
        glass_field,
        shading="auto",
        cmap="viridis",
    )
    cbar = fig.colorbar(mesh, ax=ax, label="Arrival time to glass transition [years]")
    cbar.ax.tick_params(labelsize=9)

    finite_liq = np.isfinite(arrival_liquidus_s)
    if np.any(finite_liq):
        liq_field = _arrival_field(time_s, arrival_liquidus_s)
        finite_vals = (arrival_liquidus_s[finite_liq] / YEAR_SECONDS).astype(float)
        vmin, vmax = float(finite_vals.min()), float(finite_vals.max())
        levels: Iterable[float]
        if vmin == vmax:
            levels = [vmin]
        else:
            levels = np.linspace(vmin, vmax, num=min(5, max(2, finite_vals.size)))
        cs = ax.contour(
            np.asarray(r_over_Rmars, dtype=float),
            time_years,
            liq_field,
            levels=levels,
            colors="white",
            linewidths=0.8,
        )
        ax.clabel(cs, fmt="Liquidus: %.2f yr", fontsize=8)

    ax.set_xlabel(r"$r / R_{\mathrm{Mars}}$")
    ax.set_ylabel("Time [years]")
    ax.set_title(f"SiO2 cooling map (T0={T0:g} K)")
    ax.set_ylim(time_years.min(), time_years.max())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


__all__ = ["plot_arrival_map"]
