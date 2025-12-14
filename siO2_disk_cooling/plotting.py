"""Plotting helpers for the SiO2 cooling map."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import matplotlib.pyplot as plt

from .model import CoolingParams, YEAR_SECONDS, dust_temperature


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
    mode: Literal["arrival", "phase"] = "arrival",
    cooling_model: str | None = None,
    time_axis_max_years: float | None = None,
) -> None:
    """Render the arrival map or phase-fraction map to a PNG file.

    When ``mode="phase"``, the color scale shows the solid fraction
    (blue = solid-rich, red = vapor-rich; 1.0 corresponds to fully solid).
    """

    r_arr = np.asarray(r_over_Rmars, dtype=float)
    time_arr = np.asarray(time_s, dtype=float)
    if mode not in ("arrival", "phase"):
        raise ValueError(f"Unsupported mode: {mode}")
    model_label = (cooling_model or "slab").lower()
    time_years = time_arr / YEAR_SECONDS
    time_min = float(time_years.min())
    time_span_max = float(time_years.max())
    if time_axis_max_years is not None and np.isfinite(time_axis_max_years):
        time_span_max = min(time_span_max, max(float(time_axis_max_years), time_min))
    fig, ax = plt.subplots(figsize=(8.0, 4.8))

    if mode == "phase":
        T_field = dust_temperature(r_arr * params.R_mars, time_arr, T0, params)
        if T_field.ndim == 1:
            T_field = T_field[:, np.newaxis]
        f_vap = (T_field - params.T_glass) / (params.T_liquidus - params.T_glass)
        f_vap = np.clip(f_vap, 0.0, 1.0)
        f_solid = 1.0 - f_vap
        mesh = ax.pcolormesh(
            time_years,
            r_arr,
            f_solid.T,
            shading="auto",
            cmap="coolwarm",
            vmin=0.0,
            vmax=1.0,
        )
        cbar = fig.colorbar(mesh, ax=ax, label="Solid fraction (SiO2)")
        ax.set_title(f"SiO2 phase map ({model_label}, T0={T0:g} K)")
    else:
        glass_field = _arrival_field(time_arr, arrival_glass_s)
        glass_vals = glass_field[np.isfinite(glass_field)]
        if glass_vals.size > 0:
            glass_min = float(glass_vals.min())
            glass_max = float(glass_vals.max())
        else:
            glass_min = time_min
            glass_max = time_span_max
        if glass_max <= glass_min:
            glass_max = glass_min + 1e-6
        mesh = ax.pcolormesh(
            time_years,
            r_arr,
            glass_field.T,
            shading="auto",
            cmap="magma",
            vmin=glass_min,
            vmax=glass_max,
        )
        cbar = fig.colorbar(mesh, ax=ax, label="Arrival time to glass transition [years]")
        finite_liq = np.isfinite(arrival_liquidus_s)
        if np.any(finite_liq):
            liq_field = _arrival_field(time_arr, arrival_liquidus_s)
            finite_vals = (arrival_liquidus_s[finite_liq] / YEAR_SECONDS).astype(float)
            finite_vals = finite_vals[np.isfinite(finite_vals) & (finite_vals <= time_span_max)]
            levels: list[float] = []
            if finite_vals.size > 0:
                vmin, vmax = float(finite_vals.min()), float(finite_vals.max())
                # Require a positive span to avoid contour errors when all values coincide.
                if vmax > vmin:
                    levels = np.linspace(vmin, vmax, num=min(6, max(2, finite_vals.size))).tolist()
            if len(levels) > 0:
                cs = ax.contour(
                    time_years,
                    r_arr,
                    liq_field.T,
                    levels=levels,
                    colors="#f5f5f5",
                    linewidths=1.0,
                    linestyles="--",
                )
                ax.clabel(cs, fmt="Liquidus: %.1f yr", fontsize=8, colors="#f5f5f5", inline_spacing=4)
        note = "Shade: arrival to glass; dashed: liquidus isochrons"
        ax.text(
            0.99,
            0.02,
            note,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            color="#161616",
            bbox={"facecolor": "white", "alpha": 0.8, "boxstyle": "round,pad=0.25", "linewidth": 0.0},
        )
        ax.set_title(f"SiO2 cooling map ({model_label}, T0={T0:g} K)")

    cbar.ax.tick_params(labelsize=9)

    ax.set_xlabel("Time since impact [years]")
    ax.set_ylabel(r"$r / R_{\mathrm{Mars}}$")
    ax.set_xlim(time_min, time_span_max)
    ax.set_ylim(r_arr.min(), r_arr.max())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


__all__ = ["plot_arrival_map"]
