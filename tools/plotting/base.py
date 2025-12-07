"""
Plotting utilities for PSD temperature-time diagnostics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import imageio.v2 as imageio
import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_DPI = 200


def _temperature_edges(temperatures: np.ndarray) -> np.ndarray:
    """Construct temperature edges for pcolormesh."""

    if temperatures.size == 1:
        delta = max(1.0, 0.1 * temperatures[0])
        return np.array([temperatures[0] - delta, temperatures[0] + delta])

    diffs = np.diff(temperatures)
    edges = np.empty(temperatures.size + 1, dtype=float)
    edges[1:-1] = temperatures[:-1] + 0.5 * diffs
    edges[0] = temperatures[0] - 0.5 * diffs[0]
    edges[-1] = temperatures[-1] + 0.5 * diffs[-1]
    return edges


def save_heatmap_frames(
    outdir: Path,
    times: Sequence[float],
    temperatures: np.ndarray,
    size_edges: np.ndarray,
    log_counts_cube: np.ndarray,
    s_min_eff_curve: np.ndarray,
    cmap: str = "viridis",
    dpi: int = DEFAULT_DPI,
) -> list[Path]:
    """
    Generate heatmap frames for each time snapshot.

    Parameters
    ----------
    times : Sequence[float]
        Array-like of time samples (length N_time).
    temperatures : np.ndarray
        Temperatures at which PSDs were computed (length N_T).
    size_edges : np.ndarray
        Size grid edges (length N_size + 1).
    log_counts_cube : np.ndarray
        Data array with shape (N_time, N_T, N_size).
    s_min_eff_curve : np.ndarray
        Effective minimum size per temperature (length N_T).
    """

    outdir.mkdir(parents=True, exist_ok=True)
    time_arr = np.asarray(times, dtype=float)
    temps = np.asarray(temperatures, dtype=float)
    log_cube = np.asarray(log_counts_cube, dtype=float)

    vmin = float(np.nanmin(log_cube))
    vmax = float(np.nanmax(log_cube))

    temp_edges = _temperature_edges(temps)

    frame_paths: list[Path] = []
    for idx, time_val in enumerate(time_arr):
        fig, ax = plt.subplots(figsize=(8, 5))
        mesh = ax.pcolormesh(
            size_edges,
            temp_edges,
            log_cube[idx],
            shading="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_xscale("log")
        ax.set_xlabel("Size s [m]")
        ax.set_ylabel("Temperature [K]")
        ax.set_title(f"log10 N; t = {time_val:.3e} s")
        ax.plot(s_min_eff_curve, temps, linestyle="--", color="white", linewidth=1.2)
        cbar = fig.colorbar(mesh, ax=ax)
        cbar.set_label("log10 N")
        ax.text(
            0.02,
            0.95,
            f"Frame {idx:03d}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            color="white",
            bbox=dict(facecolor="black", alpha=0.35, edgecolor="none", boxstyle="round,pad=0.2"),
        )
        fig.tight_layout()
        frame_path = outdir / f"fig_heatmap_t{idx:03d}.png"
        fig.savefig(frame_path, dpi=dpi)
        plt.close(fig)
        frame_paths.append(frame_path)
    return frame_paths


def save_keyframe_montage(
    out_path: Path,
    times: Sequence[float],
    temperatures: np.ndarray,
    size_edges: np.ndarray,
    log_counts_cube: np.ndarray,
    s_min_eff_curve: np.ndarray,
    indices: Iterable[int] | None = None,
    cmap: str = "viridis",
    dpi: int = DEFAULT_DPI,
) -> None:
    """Render a montage of selected time frames."""

    time_arr = np.asarray(times, dtype=float)
    temps = np.asarray(temperatures, dtype=float)
    log_cube = np.asarray(log_counts_cube, dtype=float)
    temp_edges = _temperature_edges(temps)

    if indices is None:
        candidate = [0, log_cube.shape[0] // 4, log_cube.shape[0] // 2, 3 * log_cube.shape[0] // 4, log_cube.shape[0] - 1]
        indices = sorted(set(max(0, min(log_cube.shape[0] - 1, idx)) for idx in candidate))
    else:
        indices = sorted(set(idx for idx in indices if 0 <= idx < log_cube.shape[0]))

    if not indices:
        return

    vmin = float(np.nanmin(log_cube))
    vmax = float(np.nanmax(log_cube))

    ncols = min(5, len(indices))
    nrows = int(np.ceil(len(indices) / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4 * ncols, 3 * nrows), squeeze=False)

    for ax, idx in zip(axes.flat, indices):
        mesh = ax.pcolormesh(
            size_edges,
            temp_edges,
            log_cube[idx],
            shading="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_xscale("log")
        ax.set_xlabel("Size s [m]")
        ax.set_ylabel("Temperature [K]")
        ax.set_title(f"t = {time_arr[idx]:.3e} s")
        ax.plot(s_min_eff_curve, temps, linestyle="--", color="white", linewidth=1.2)

    # Hide unused axes
    for ax in axes.flat[len(indices) :]:
        ax.axis("off")

    fig.tight_layout()
    cbar = fig.colorbar(mesh, ax=axes, shrink=0.6)
    cbar.set_label("log10 N")
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def save_gif(frame_paths: Sequence[Path], gif_path: Path, fps: int = 8) -> None:
    """Combine individual PNG frames into an animated GIF."""

    if not frame_paths:
        return
    images = [imageio.imread(path) for path in frame_paths]
    imageio.mimsave(gif_path, images, fps=fps)

