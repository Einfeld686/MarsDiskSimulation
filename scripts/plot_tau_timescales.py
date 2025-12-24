#!/usr/bin/env python3
"""Plot optical depth vs timescales (sublimation/collision/blowout)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.collections import PathCollection
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk.physics.surface import wyatt_tcoll_S1
from paper.plot_style import apply_default_style


DEFAULT_COLUMNS = (
    "time",
    "tau",
    "tau_los_mars",
    "tau_mars_line_of_sight",
    "t_coll",
    "t_blow_s",
    "t_blow",
    "s_min_effective",
    "s_min",
    "ds_dt_sublimation",
    "Omega_s",
    "cell_index",
    "cell_active",
    "r_RM",
    "r_orbit_RM",
    "r_m",
)

ONE_D_SIGNATURE_FIELDS = ("cell_index", "cell_active", "active_mask")
RADIUS_FIELD_CANDIDATES = ("r_RM", "r_orbit_RM", "r_m")
TAU_LABELS_JP = {
    "tau_los_mars": "光学的厚さ τ（火星視線）",
    "tau_mars_line_of_sight": "光学的厚さ τ（火星視線）",
    "tau": "光学的厚さ τ",
}


def _resolve_series_files(run_dir: Path) -> tuple[Optional[Path], list[Path]]:
    series_dir = run_dir / "series"
    run_parquet = series_dir / "run.parquet"
    if run_parquet.exists():
        return run_parquet, []
    chunk_files = sorted(series_dir.glob("run_chunk_*.parquet"))
    return None, chunk_files


def _available_columns_from_parquet(path: Path) -> list[str]:
    schema = pq.read_schema(path)
    return list(schema.names)


def _available_columns_from_dataset(files: list[Path]) -> list[str]:
    dataset = ds.dataset([str(p) for p in files], format="parquet")
    return list(dataset.schema.names)


def _select_columns(available: Iterable[str], desired: Iterable[str]) -> list[str]:
    available_set = set(available)
    return [name for name in desired if name in available_set]


def _estimate_batch_size(memory_limit_gb: Optional[float]) -> int:
    if memory_limit_gb is None:
        return 200_000
    scaled = int(25_000 * max(1.0, memory_limit_gb))
    return max(50_000, min(500_000, scaled))


def _load_series_dataframe(
    run_dir: Path,
    columns: list[str],
    *,
    batch_size: Optional[int],
    memory_limit_gb: Optional[float],
) -> pd.DataFrame:
    run_parquet, chunk_files = _resolve_series_files(run_dir)
    if run_parquet is not None:
        return pd.read_parquet(run_parquet, columns=columns)

    if not chunk_files:
        raise FileNotFoundError(f"No run.parquet or run_chunk_*.parquet under {run_dir / 'series'}")

    dataset = ds.dataset([str(p) for p in chunk_files], format="parquet")
    batch_size = batch_size or _estimate_batch_size(memory_limit_gb)
    if hasattr(dataset, "to_batches"):
        batches = dataset.to_batches(columns=columns, batch_size=batch_size)
    else:
        scanner = dataset.scan(columns=columns, batch_size=batch_size)
        batches = scanner.to_batches()
    frames: list[pd.DataFrame] = []
    for batch in batches:
        frames.append(batch.to_pandas())
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def _pick_first_available(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _pick_first_available_name(available: Iterable[str], candidates: list[str]) -> Optional[str]:
    available_set = set(available)
    for name in candidates:
        if name in available_set:
            return name
    return None


def _is_one_d_columns(available: Iterable[str]) -> bool:
    available_set = set(available)
    return any(name in available_set for name in ONE_D_SIGNATURE_FIELDS)


def _filter_active_cells(df: pd.DataFrame) -> pd.DataFrame:
    if "cell_active" not in df.columns:
        return df
    mask = df["cell_active"].fillna(False).astype(bool)
    return df[mask]


def _compute_t_coll_from_tau(tau: np.ndarray, omega: np.ndarray) -> np.ndarray:
    out = np.full_like(tau, np.nan, dtype=float)
    mask = np.isfinite(tau) & np.isfinite(omega) & (tau > 0.0) & (omega > 0.0)
    if not np.any(mask):
        return out
    vec = np.vectorize(wyatt_tcoll_S1, otypes=[float])
    out[mask] = vec(tau[mask], omega[mask])
    return out


def _compute_timescale_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Optional[str]]]:
    used = {
        "tau": _pick_first_available(df, ["tau_los_mars", "tau_mars_line_of_sight", "tau"]),
        "t_blow": _pick_first_available(df, ["t_blow_s", "t_blow"]),
        "s_min": _pick_first_available(df, ["s_min_effective", "s_min"]),
    }
    if used["tau"] is None:
        raise ValueError("No tau column found (expected tau, tau_los_mars, or tau_mars_line_of_sight)")
    if "time" not in df.columns:
        raise ValueError("Required column 'time' is missing")

    tau_values = df[used["tau"]].to_numpy(dtype=float, copy=False)
    df = df.assign(tau_plot=tau_values)

    if used["t_blow"] is not None:
        t_blow = df[used["t_blow"]].to_numpy(dtype=float, copy=False)
        t_blow = np.where(np.isfinite(t_blow) & (t_blow > 0.0), t_blow, np.nan)
        df = df.assign(t_blow_plot=t_blow)

    if "t_coll" in df.columns:
        t_coll = df["t_coll"].to_numpy(dtype=float, copy=False)
        t_coll = np.where(np.isfinite(t_coll) & (t_coll > 0.0), t_coll, np.nan)
        df = df.assign(t_coll_plot=t_coll)
    elif "Omega_s" in df.columns:
        omega = df["Omega_s"].to_numpy(dtype=float, copy=False)
        t_coll = _compute_t_coll_from_tau(tau_values, omega)
        df = df.assign(t_coll_plot=t_coll)

    if used["s_min"] is not None and "ds_dt_sublimation" in df.columns:
        s_min = df[used["s_min"]].to_numpy(dtype=float, copy=False)
        ds_dt = df["ds_dt_sublimation"].to_numpy(dtype=float, copy=False)
        t_sub = np.full_like(s_min, np.nan, dtype=float)
        mask = np.isfinite(s_min) & np.isfinite(ds_dt) & (ds_dt < 0.0)
        t_sub[mask] = s_min[mask] / np.abs(ds_dt[mask])
        df = df.assign(t_sub_plot=t_sub)

    return df, used


def _reduce_cells(df: pd.DataFrame, reduce_mode: str) -> pd.DataFrame:
    if reduce_mode == "none":
        return df
    group = df.groupby("time", sort=True, as_index=False)
    if reduce_mode == "cell_mean":
        return group.mean(numeric_only=True)
    return group.median(numeric_only=True)


def _tau_label_jp(tau_columns: set[str]) -> str:
    if len(tau_columns) == 1:
        name = next(iter(tau_columns))
        return TAU_LABELS_JP.get(name, TAU_LABELS_JP["tau"])
    return TAU_LABELS_JP["tau"]


def _apply_timescale_clip(values: np.ndarray, clip_min: Optional[float]) -> np.ndarray:
    if clip_min is None:
        return values
    return np.where(np.isfinite(values), np.maximum(values, clip_min), values)


def _plot_cell_tracks(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    tau_scale: str,
    time_scale: str,
    clip_timescale_min: Optional[float],
) -> None:
    if "cell_index" not in df.columns or "tau_plot" not in df.columns:
        return
    series_specs = [
        ("t_sub_plot", "tab:orange"),
        ("t_coll_plot", "tab:blue"),
        ("t_blow_plot", "tab:green"),
    ]
    for _, group in df.groupby("cell_index", sort=False):
        if "time" in group.columns:
            group = group.sort_values("time")
        tau = group["tau_plot"].to_numpy(dtype=float, copy=False)
        for col, color in series_specs:
            if col not in group.columns:
                continue
            values = group[col].to_numpy(dtype=float, copy=False)
            values = _apply_timescale_clip(values, clip_timescale_min)
            mask = np.isfinite(values) & np.isfinite(tau)
            if time_scale == "log":
                mask &= values > 0.0
            if tau_scale == "log":
                mask &= tau > 0.0
            if np.count_nonzero(mask) < 2:
                continue
            ax.plot(
                values[mask],
                tau[mask],
                color=color,
                alpha=0.08,
                linewidth=0.6,
                zorder=1,
            )


def _plot_trend_lines(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    tau_scale: str,
    time_scale: str,
    clip_timescale_min: Optional[float],
) -> None:
    if "tau_plot" not in df.columns:
        return
    if "time" in df.columns:
        df = df.sort_values("time")
    tau = df["tau_plot"].to_numpy(dtype=float, copy=False)
    series_specs = [
        ("t_sub_plot", "tab:orange"),
        ("t_coll_plot", "tab:blue"),
        ("t_blow_plot", "tab:green"),
    ]
    for col, color in series_specs:
        if col not in df.columns:
            continue
        values = df[col].to_numpy(dtype=float, copy=False)
        values = _apply_timescale_clip(values, clip_timescale_min)
        mask = np.isfinite(values) & np.isfinite(tau)
        if time_scale == "log":
            mask &= values > 0.0
        if tau_scale == "log":
            mask &= tau > 0.0
        if np.count_nonzero(mask) < 2:
            continue
        ax.plot(
            values[mask],
            tau[mask],
            color=color,
            alpha=0.8,
            linewidth=1.2,
            zorder=3,
        )


def _scatter_timescale(
    ax: plt.Axes,
    *,
    x: np.ndarray,
    y: np.ndarray,
    label: str,
    color: Optional[str],
    marker: str,
    alpha: float,
    size: float,
    cmap: str,
    norm: Optional[colors.Normalize],
    color_values: Optional[np.ndarray],
) -> Optional[PathCollection]:
    if color_values is not None and norm is not None:
        return ax.scatter(
            x,
            y,
            c=color_values,
            cmap=cmap,
            norm=norm,
            s=size,
            alpha=alpha,
            marker=marker,
            label=label,
            linewidths=0.0,
        )
    return ax.scatter(
        x,
        y,
        color=color,
        s=size,
        alpha=alpha,
        marker=marker,
        label=label,
        linewidths=0.0,
    )


def _plot_run(
    ax: plt.Axes,
    df: pd.DataFrame,
    label_prefix: str,
    *,
    tau_scale: str,
    time_scale: str,
    alpha: float,
    size: float,
    color_by_time: bool,
    color_by_radius: bool,
    cmap: str,
    time_norm: Optional[colors.Normalize],
    radius_norm: Optional[colors.Normalize],
    radius_label: Optional[str],
    clip_timescale_min: Optional[float],
) -> Optional[PathCollection]:
    tau = df["tau_plot"].to_numpy(dtype=float, copy=False)
    time_values = df["time"].to_numpy(dtype=float, copy=False) if color_by_time else None
    radius_values = None
    if color_by_radius and radius_label and radius_label in df.columns:
        radius_values = df[radius_label].to_numpy(dtype=float, copy=False)
    mappable = None

    series_specs = [
        ("t_sub_plot", "t_sub", "tab:orange", "o"),
        ("t_coll_plot", "t_coll", "tab:blue", "^"),
        ("t_blow_plot", "t_blow", "tab:green", "s"),
    ]
    for col, suffix, color, marker in series_specs:
        if col not in df.columns:
            continue
        values = df[col].to_numpy(dtype=float, copy=False)
        values = _apply_timescale_clip(values, clip_timescale_min)
        mask = np.isfinite(values) & np.isfinite(tau)
        if color_by_time and time_values is not None:
            mask &= np.isfinite(time_values)
        if color_by_radius and radius_values is not None:
            mask &= np.isfinite(radius_values)
        if time_scale == "log":
            mask &= values > 0.0
        if tau_scale == "log":
            mask &= tau > 0.0
        if not np.any(mask):
            continue
        label = f"{label_prefix} {suffix}" if label_prefix else suffix
        color_values = time_values if color_by_time else radius_values
        norm = time_norm if color_by_time else radius_norm
        scatter = _scatter_timescale(
            ax,
            x=values[mask],
            y=tau[mask],
            label=label,
            color=None if (color_by_time or color_by_radius) else color,
            marker=marker,
            alpha=alpha,
            size=size,
            cmap=cmap,
            norm=norm,
            color_values=color_values[mask] if color_values is not None else None,
        )
        if (color_by_time or color_by_radius) and mappable is None:
            mappable = scatter

    return mappable


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot tau vs timescales from run outputs")
    parser.add_argument("--run", action="append", required=True, help="run directory under out/")
    parser.add_argument("--output-dir", type=Path, help="destination directory (default: run/figures)")
    parser.add_argument("--output-name", default="tau_timescales.png")
    parser.add_argument("--reduce", choices=["cell_median", "cell_mean", "none"], default="cell_median")
    parser.add_argument("--tau-scale", choices=["linear", "log"], default="log")
    parser.add_argument("--time-scale", choices=["linear", "log"], default="log")
    parser.add_argument("--color-by", choices=["none", "time", "radius"], default="none")
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--alpha", type=float, default=0.25)
    parser.add_argument("--point-size", type=float, default=6.0)
    parser.add_argument(
        "--clip-timescale-min",
        type=float,
        default=None,
        help="Minimum timescale value for plotting (applied before log scale).",
    )
    parser.add_argument("--with-inset", action="store_true")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--memory-limit-gb", type=float, default=None)
    parser.add_argument("--no-style", action="store_true")
    args = parser.parse_args()

    runs = [Path(p).resolve() for p in args.run]
    output_dir = args.output_dir or (runs[0] / "figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    memory_limit_gb = args.memory_limit_gb
    if memory_limit_gb is None:
        env_value = os.environ.get("STREAM_MEM_GB")
        if env_value:
            try:
                memory_limit_gb = float(env_value)
            except ValueError:
                memory_limit_gb = None

    if not args.no_style:
        apply_default_style()

    fig, ax = plt.subplots(figsize=(7, 4))

    color_by_time = args.color_by == "time"
    color_by_radius = args.color_by == "radius"
    with_inset = args.with_inset
    clip_timescale_min = args.clip_timescale_min
    time_norm: Optional[colors.Normalize] = None
    time_range: Optional[tuple[float, float]] = None
    radius_norm: Optional[colors.Normalize] = None
    radius_field: Optional[str] = None
    if color_by_time:
        all_times = []
        for run_dir in runs:
            _, chunk_files = _resolve_series_files(run_dir)
            if chunk_files:
                available = _available_columns_from_dataset(chunk_files)
            else:
                run_parquet, _ = _resolve_series_files(run_dir)
                if run_parquet is None:
                    continue
                available = _available_columns_from_parquet(run_parquet)
            columns = _select_columns(available, DEFAULT_COLUMNS)
            if "time" not in columns:
                continue
            df_time = _load_series_dataframe(
                run_dir,
                ["time"],
                batch_size=args.batch_size,
                memory_limit_gb=memory_limit_gb,
            )
            if not df_time.empty:
                all_times.append(df_time["time"].to_numpy(dtype=float, copy=False))
        if all_times:
            time_values = np.concatenate(all_times)
            if np.isfinite(time_values).any():
                time_min = float(np.nanmin(time_values))
                time_max = float(np.nanmax(time_values))
                time_range = (time_min, time_max)
                time_norm = colors.Normalize(vmin=time_min, vmax=time_max)
        if time_norm is None:
            print("[plot_tau_timescales] time-based coloring disabled (no valid time values)")
            color_by_time = False
    if color_by_radius:
        all_radii = []
        for run_dir in runs:
            run_parquet, chunk_files = _resolve_series_files(run_dir)
            if run_parquet is not None:
                available = _available_columns_from_parquet(run_parquet)
            elif chunk_files:
                available = _available_columns_from_dataset(chunk_files)
            else:
                continue
            if not _is_one_d_columns(available):
                continue
            if radius_field is None:
                radius_field = _pick_first_available_name(
                    available,
                    list(RADIUS_FIELD_CANDIDATES),
                )
            if radius_field is None:
                continue
            df_radius = _load_series_dataframe(
                run_dir,
                [radius_field],
                batch_size=args.batch_size,
                memory_limit_gb=memory_limit_gb,
            )
            if not df_radius.empty:
                all_radii.append(df_radius[radius_field].to_numpy(dtype=float, copy=False))
        if all_radii:
            radius_values = np.concatenate(all_radii)
            if np.isfinite(radius_values).any():
                radius_norm = colors.Normalize(
                    vmin=np.nanmin(radius_values),
                    vmax=np.nanmax(radius_values),
                )
        if radius_norm is None or radius_field is None:
            print("[plot_tau_timescales] radius-based coloring disabled (1D runs only)")
            color_by_radius = False
    if with_inset and radius_field is None:
        for run_dir in runs:
            run_parquet, chunk_files = _resolve_series_files(run_dir)
            if run_parquet is not None:
                available = _available_columns_from_parquet(run_parquet)
            elif chunk_files:
                available = _available_columns_from_dataset(chunk_files)
            else:
                continue
            if not _is_one_d_columns(available):
                continue
            radius_field = _pick_first_available_name(
                available,
                list(RADIUS_FIELD_CANDIDATES),
            )
            if radius_field is not None:
                break
        if radius_field is None:
            print("[plot_tau_timescales] inset disabled (1D radius column not found)")
            with_inset = False

    inset_ax = None
    if with_inset:
        inset_ax = ax.inset_axes([0.62, 0.55, 0.35, 0.38])

    mappable = None
    tau_columns_used: set[str] = set()
    for run_dir in runs:
        run_parquet, chunk_files = _resolve_series_files(run_dir)
        if run_parquet is not None:
            available = _available_columns_from_parquet(run_parquet)
        elif chunk_files:
            available = _available_columns_from_dataset(chunk_files)
        else:
            print(f"[plot_tau_timescales] missing series data under {run_dir}")
            continue
        run_is_1d = _is_one_d_columns(available)
        columns = _select_columns(available, DEFAULT_COLUMNS)
        df = _load_series_dataframe(
            run_dir,
            columns,
            batch_size=args.batch_size,
            memory_limit_gb=memory_limit_gb,
        )
        if df.empty:
            print(f"[plot_tau_timescales] no data rows for {run_dir}")
            continue
        df, used = _compute_timescale_columns(df)
        tau_columns_used.add(used["tau"] or "tau")
        df_active = _filter_active_cells(df)
        if color_by_radius and run_is_1d and args.reduce != "none":
            print("[plot_tau_timescales] forcing --reduce none to preserve radius coloring")
            reduce_mode = "none"
        else:
            reduce_mode = args.reduce
        if run_is_1d:
            df_plot = _reduce_cells(df_active, reduce_mode)
        else:
            df_plot = df
        if run_is_1d and reduce_mode == "none":
            _plot_cell_tracks(
                ax,
                df_active,
                tau_scale=args.tau_scale,
                time_scale=args.time_scale,
                clip_timescale_min=clip_timescale_min,
            )
        label_prefix = run_dir.name
        run_color_by_radius = (
            color_by_radius
            and run_is_1d
            and radius_field in df_plot.columns
            if radius_field
            else False
        )
        if color_by_radius and not run_is_1d:
            print(f"[plot_tau_timescales] radius coloring skipped for 0D run {run_dir.name}")
        elif color_by_radius and not run_color_by_radius:
            print(f"[plot_tau_timescales] radius column missing for {run_dir.name}; using fixed colors")
        mappable = _plot_run(
            ax,
            df_plot,
            label_prefix,
            tau_scale=args.tau_scale,
            time_scale=args.time_scale,
            alpha=args.alpha,
            size=args.point_size,
            color_by_time=color_by_time,
            color_by_radius=run_color_by_radius,
            cmap=args.cmap,
            time_norm=time_norm,
            radius_norm=radius_norm,
            radius_label=radius_field,
            clip_timescale_min=clip_timescale_min,
        ) or mappable
        if run_is_1d and reduce_mode == "cell_median":
            _plot_trend_lines(
                ax,
                df_plot,
                tau_scale=args.tau_scale,
                time_scale=args.time_scale,
                clip_timescale_min=clip_timescale_min,
            )
        if inset_ax is not None and run_is_1d and radius_field in df_active.columns:
            radius_values = df_active[radius_field].to_numpy(dtype=float, copy=False)
            tau_values = df_active["tau_plot"].to_numpy(dtype=float, copy=False)
            mask = np.isfinite(radius_values) & np.isfinite(tau_values)
            if args.tau_scale == "log":
                mask &= tau_values > 0.0
            if np.any(mask):
                inset_ax.scatter(
                    radius_values[mask],
                    tau_values[mask],
                    s=max(1.0, args.point_size * 0.4),
                    alpha=min(0.4, args.alpha + 0.1),
                    linewidths=0.0,
                )
        print(
            f"[plot_tau_timescales] {run_dir.name}: tau={used['tau']} t_blow={used['t_blow']} s_min={used['s_min']}"
        )

    ax.set_xlabel("timescale [s]")
    ax.set_ylabel(_tau_label_jp(tau_columns_used))
    ax.set_xscale(args.time_scale)
    ax.set_yscale(args.tau_scale)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.2)
    if color_by_time and mappable is not None:
        cbar = fig.colorbar(mappable, ax=ax)
        cbar.set_label("time [s]")
    elif color_by_radius and mappable is not None and radius_field is not None:
        cbar = fig.colorbar(mappable, ax=ax)
        if radius_field in {"r_RM", "r_orbit_RM"}:
            cbar.set_label("r / R_M")
        else:
            cbar.set_label("r [m]")
    if color_by_time and time_range is not None:
        t_min, t_max = time_range
        ax.text(
            0.99,
            0.01,
            f"time range: {t_min:.2e}–{t_max:.2e} s",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            alpha=0.7,
        )
    if inset_ax is not None:
        if radius_field in {"r_RM", "r_orbit_RM"}:
            inset_ax.set_xlabel("r / R_M", fontsize=8)
        elif radius_field is not None:
            inset_ax.set_xlabel("r [m]", fontsize=8)
        inset_ax.set_ylabel("τ", fontsize=8)
        inset_ax.set_yscale(args.tau_scale)
        inset_ax.tick_params(axis="both", labelsize=7)
        inset_ax.grid(True, which="both", alpha=0.2)

    outpath = output_dir / args.output_name
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    print(f"[plot_tau_timescales] wrote {outpath}")


if __name__ == "__main__":
    main()
