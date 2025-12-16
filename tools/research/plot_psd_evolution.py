"""
PSD（粒径分布）の時間発展をヒートマップとスナップショットで可視化する。
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

from .common import column_or_default, ensure_plot_path, load_psd_hist, load_series, select_temperature


def _edges_from_centers_log(centers: np.ndarray) -> np.ndarray:
    centers = np.asarray(centers, dtype=float)
    centers = np.sort(centers)
    if centers.size == 1:
        factor = 0.25
        return np.array([centers[0] * (1 - factor), centers[0] * (1 + factor)])
    ratios = np.sqrt(centers[1:] / centers[:-1])
    edges = np.empty(centers.size + 1, dtype=float)
    edges[1:-1] = centers[:-1] * ratios
    edges[0] = centers[0] / ratios[0]
    edges[-1] = centers[-1] * ratios[-1]
    return edges


def _time_edges(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    if samples.size == 1:
        delta = max(1.0, 0.05 * samples[0])
        return np.array([samples[0] - delta, samples[0] + delta])
    diffs = np.diff(samples)
    edges = np.empty(samples.size + 1, dtype=float)
    edges[1:-1] = samples[:-1] + 0.5 * diffs
    edges[0] = samples[0] - 0.5 * diffs[0]
    edges[-1] = samples[-1] + 0.5 * diffs[-1]
    return edges


def _select_indices(values: np.ndarray, max_points: int | None) -> np.ndarray:
    if max_points is None or len(values) <= max_points:
        return values
    step = max(len(values) // max_points, 1)
    return values[::step]


def _merge_temperature(psd_df: pd.DataFrame, series_df: pd.DataFrame) -> pd.DataFrame:
    if "time" not in psd_df.columns or "time" not in series_df.columns:
        psd_df["T_M_used"] = np.nan
        return psd_df
    temp_map = dict(zip(series_df["time"].to_numpy(), select_temperature(series_df) or []))
    psd_df = psd_df.copy()
    psd_df["T_M_used"] = psd_df["time"].map(temp_map)
    return psd_df


def _nearest_rows(series_df: pd.DataFrame, target_T: float, count: int = 1) -> pd.DataFrame:
    temps = select_temperature(series_df)
    if temps is None:
        return pd.DataFrame()
    diffs = np.abs(temps - target_T)
    order = np.argsort(diffs)
    return series_df.iloc[order[:count]]


def plot_psd_evolution(
    run_dir: Path,
    out_heatmap: Path | None = None,
    out_snapshots: Path | None = None,
    max_times: int | None = 300,
    snapshot_temps: Iterable[float] | None = None,
    use_time_axis: bool = False,
) -> tuple[Path | None, Path | None]:
    psd = load_psd_hist(run_dir, max_points=None)
    if psd.empty:
        raise RuntimeError(f"psd_hist.parquet not found or empty: {run_dir}")

    series_cols = ["time", "T_M_used", "a_blow", "s_min", "Sigma_surf"]
    series_df = load_series(run_dir, columns=series_cols, max_points=None)

    psd = _merge_temperature(psd, series_df)

    unique_times = np.unique(psd["time"].to_numpy())
    unique_times = _select_indices(unique_times, max_times)
    psd = psd[psd["time"].isin(unique_times)].copy()

    pivot = psd.pivot_table(index="time", columns="s_bin_center", values="Sigma_bin", aggfunc="sum")
    pivot = pivot.sort_index(axis=0).sort_index(axis=1)
    times_sorted = pivot.index.to_numpy(dtype=float)

    x_axis = times_sorted
    xlabel = "time [s]"
    if not use_time_axis:
        temp_map = dict(zip(series_df["time"].to_numpy(), select_temperature(series_df) or []))
        temps = np.array([temp_map.get(t, np.nan) for t in times_sorted], dtype=float)
        if np.isfinite(temps).any():
            x_axis = temps
            xlabel = "T_M [K]"

    size_centers = pivot.columns.to_numpy(dtype=float)
    size_edges = _edges_from_centers_log(size_centers)
    x_edges = _time_edges(x_axis)

    data = pivot.to_numpy()
    data = np.clip(data, a_min=1e-40, a_max=None)

    fig, ax = plt.subplots(figsize=(10, 6))
    mesh = ax.pcolormesh(x_edges, size_edges, data.T, norm=LogNorm(), shading="auto", cmap="viridis")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("size [m]")
    ax.set_title("PSD 時間発展 (Sigma_bin)")

    # オーバーレイ: a_blow と s_min
    if not series_df.empty:
        temps_axis = x_axis if xlabel.startswith("T_M") else series_df["time"].to_numpy()
        series_for_overlay = series_df.copy()
        if xlabel.startswith("T_M"):
            series_for_overlay["x_axis"] = select_temperature(series_df)
        else:
            series_for_overlay["x_axis"] = series_df["time"]
        series_for_overlay = series_for_overlay.dropna(subset=["x_axis"])
        ax.plot(series_for_overlay["x_axis"], series_for_overlay["a_blow"], color="white", lw=1.0, linestyle="--", label="a_blow")
        ax.plot(series_for_overlay["x_axis"], series_for_overlay["s_min"], color="cyan", lw=1.0, linestyle="-", label="s_min")
        ax.legend(loc="upper right")

    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("Sigma_bin [kg m$^{-2}$]")
    fig.tight_layout()
    heatmap_path = ensure_plot_path(run_dir, out_heatmap, "psd_heatmap.png")
    fig.savefig(heatmap_path, dpi=180)
    plt.close(fig)

    # スナップショット (ログスケール)
    snapshot_path = None
    targets = list(snapshot_temps) if snapshot_temps else [5000, 4000, 3000, 2500, 2000]
    if targets and not series_df.empty:
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        for target in targets:
            rows = _nearest_rows(series_df, target, count=1)
            if rows.empty:
                continue
            t_val = rows["time"].iloc[0]
            x_val = rows["T_M_used"].iloc[0] if "T_M_used" in rows.columns else target
            slice_row = pivot.loc[pivot.index.get_loc(t_val, method="nearest")]
            ax2.plot(size_centers, slice_row, label=f"T~{x_val:.0f} K")
        ax2.set_xscale("log")
        ax2.set_yscale("log")
        ax2.set_xlabel("size [m]")
        ax2.set_ylabel("Sigma_bin [kg m$^{-2}$]")
        ax2.set_title("PSD スナップショット")
        ax2.legend(loc="best")
        ax2.grid(True, which="both", linestyle=":", alpha=0.4)
        fig2.tight_layout()
        snapshot_path = ensure_plot_path(run_dir, out_snapshots, "psd_snapshots.png")
        fig2.savefig(snapshot_path, dpi=180)
        plt.close(fig2)

    return heatmap_path, snapshot_path


def main() -> int:
    parser = argparse.ArgumentParser(description="PSD 時間発展のヒートマップを生成します。")
    parser.add_argument("--run-dir", type=Path, required=True, help="run ディレクトリ")
    parser.add_argument("--heatmap-out", type=Path, default=None, help="ヒートマップ出力。未指定なら run_dir/plots/psd_heatmap.png")
    parser.add_argument("--snapshots-out", type=Path, default=None, help="スナップショット出力。未指定なら run_dir/plots/psd_snapshots.png")
    parser.add_argument("--max-times", type=int, default=300, help="ヒートマップに使う時間サンプル上限")
    parser.add_argument("--use-time-axis", action="store_true", help="横軸に時間を使う（既定は温度優先）")
    args = parser.parse_args()

    plot_psd_evolution(
        args.run_dir,
        out_heatmap=args.heatmap_out,
        out_snapshots=args.snapshots_out,
        max_times=args.max_times,
        snapshot_temps=None,
        use_time_axis=args.use_time_axis,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
