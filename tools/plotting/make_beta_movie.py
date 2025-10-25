"""Render β(r/R_M, T_M, t) frames and assemble an MP4 movie."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _read_zarr_array(path: Path) -> np.ndarray:
    meta_path = path / ".zarray"
    if not meta_path.exists():
        raise FileNotFoundError(f"Zarr metadata not found: {meta_path}")
    with meta_path.open("r", encoding="utf-8") as fh:
        meta = json.load(fh)
    dtype = np.dtype(meta["dtype"])
    shape = tuple(meta["shape"])
    order = meta.get("order", "C")
    chunk_name = ".".join("0" for _ in shape)
    chunk_path = path / chunk_name
    if not chunk_path.exists():
        raise FileNotFoundError(f"Zarr chunk missing: {chunk_path}")
    data = np.frombuffer(chunk_path.read_bytes(), dtype=dtype)
    return np.reshape(data, shape, order=order)


def _load_map_spec(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        spec = json.load(fh)
    required = ["r_RM_values", "T_M_values", "qpr_table_path"]
    missing = [key for key in required if key not in spec]
    if missing:
        raise KeyError(f"map_spec.json missing keys: {', '.join(missing)}")
    if "time_orbit_fraction" not in spec and "time_s" not in spec:
        raise KeyError("map_spec.json must provide time_orbit_fraction or time_s")
    return spec


def _format_time_label(index: int, times: Sequence[float]) -> str:
    if not times:
        return f"step {index}"
    total = times[-1]
    if total <= 0.0:
        total = 1.0
    fraction = times[index] / total if total else 0.0
    return f"t = {fraction:.3f} orbit"


def _render_frames(
    beta_cube: np.ndarray,
    r_vals: Sequence[float],
    T_vals: Sequence[float],
    times: Sequence[float],
    outdir: Path,
    *,
    dt_ratio_median: float,
    qpr_table: str,
    vmax: float | None,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    n_frames = beta_cube.shape[2]
    width = max(3, len(str(max(n_frames - 1, 0))))
    extent = (
        float(r_vals[0]),
        float(r_vals[-1]),
        float(T_vals[0]),
        float(T_vals[-1]),
    )
    vmin = float(np.nanmin(beta_cube))
    vmax_val = float(np.nanmax(beta_cube)) if vmax is None else float(vmax)
    for k in range(n_frames):
        fig, ax = plt.subplots(figsize=(6, 4))
        im = ax.imshow(
            beta_cube[:, :, k].T,
            origin="lower",
            extent=extent,
            aspect="auto",
            vmin=vmin,
            vmax=vmax_val,
            cmap="viridis",
        )
        ax.set_xlabel("r / R_M")
        ax.set_ylabel("T_M [K]")
        ax.set_title("β at s_min_effective")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("β")
        legend_text = "\n".join(
            [
                _format_time_label(k, times),
                f"median(dt/t_blow) = {dt_ratio_median:.3f}",
                Path(qpr_table).name,
            ]
        )
        ax.text(
            0.98,
            0.98,
            legend_text,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )
        frame_path = outdir / f"step_{k:0{width}d}.png"
        fig.tight_layout()
        fig.savefig(frame_path, dpi=160)
        plt.close(fig)

    return width


def _build_movie(frames_dir: Path, movie_path: Path, fps: int, width: int) -> None:
    import shutil

    frame_files = sorted(frames_dir.glob("step_*.png"))
    if not frame_files:
        raise RuntimeError("No PNG frames generated; cannot assemble movie.")
    movie_path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg") is not None:
        pattern = frames_dir / f"step_%0{width}d.png"
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(pattern),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            str(movie_path),
        ]
        subprocess.run(cmd, check=True)
        return

    try:
        import imageio.v2 as imageio
    except ImportError as exc:  # pragma: no cover - fallback guard
        raise RuntimeError(
            "ffmpeg executable not found and imageio is unavailable; install either ffmpeg or imageio[ffmpeg]."
        ) from exc

    frames = [imageio.imread(path) for path in frame_files]
    imageio.mimwrite(
        movie_path,
        frames,
        fps=fps,
        codec="libx264",
        quality=8,
        macro_block_size=None,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render β movie frames from a Zarr cube.")
    parser.add_argument("--cube", type=Path, required=True, help="Path to beta_cube.zarr directory.")
    parser.add_argument("--spec", type=Path, required=True, help="map_spec.json produced by sweep_beta_map.")
    parser.add_argument("--frames", type=Path, required=True, help="Directory to store PNG frames.")
    parser.add_argument("--movie", type=Path, required=True, help="Output MP4 path.")
    parser.add_argument("--fps", type=int, default=15, help="Movie frame rate.")
    parser.add_argument("--vmax", type=float, default=None, help="Optional colour scale upper bound.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    beta_cube = _read_zarr_array(args.cube)
    spec = _load_map_spec(args.spec)
    r_vals = np.asarray(spec["r_RM_values"], dtype=float)
    T_vals = np.asarray(spec["T_M_values"], dtype=float)
    times = spec.get("time_orbit_fraction") or spec.get("time_s", [])
    dt_ratio_median = float(spec.get("dt_over_t_blow_median", math.nan))
    qpr_table = spec.get("qpr_table_path", "unknown")

    width = _render_frames(
        beta_cube,
        r_vals,
        T_vals,
        times,
        args.frames,
        dt_ratio_median=dt_ratio_median,
        qpr_table=qpr_table,
        vmax=args.vmax,
    )
    _build_movie(args.frames, args.movie, args.fps, width)


if __name__ == "__main__":
    main()
