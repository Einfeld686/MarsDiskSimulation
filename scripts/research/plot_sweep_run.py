#!/usr/bin/env python3
"""Quick-look plot generator for temp_supply_sweep runs.

Usage:
    python scripts/research/plot_sweep_run.py <run_dir>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _load_summary(run_dir: Path) -> dict:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text())
    except Exception:
        return {}


def _compute_cell_weights(df):
    if "cell_index" not in df.columns or "r_m" not in df.columns:
        return None
    cells = (
        df[["cell_index", "r_m"]]
        .dropna()
        .drop_duplicates()
        .sort_values("cell_index")
    )
    if cells.empty:
        return None
    r_vals = cells["r_m"].to_numpy(dtype=float)
    if r_vals.size == 1:
        weights = [1.0]
    else:
        edges = [0.0] * (r_vals.size + 1)
        for i in range(1, r_vals.size):
            edges[i] = 0.5 * (r_vals[i] + r_vals[i - 1])
        edges[0] = r_vals[0] - (edges[1] - r_vals[0])
        edges[-1] = r_vals[-1] + (r_vals[-1] - edges[-2])
        edges = [max(e, 0.0) for e in edges]
        areas = [
            3.141592653589793 * (edges[i + 1] ** 2 - edges[i] ** 2)
            for i in range(len(edges) - 1)
        ]
        total = sum(areas)
        if total > 0:
            weights = [a / total for a in areas]
        else:
            weights = [1.0 / r_vals.size for _ in r_vals]
    return {
        int(cell): float(weight)
        for cell, weight in zip(cells["cell_index"].astype(int), weights)
    }


def _weighted_mean(values, weights):
    if values is None:
        return float("nan")
    vals = values.to_numpy(dtype=float)
    mask = vals == vals
    if not mask.any():
        return float("nan")
    if weights is None:
        return float(vals[mask].mean())
    w = weights[mask]
    v = vals[mask]
    if w.sum() <= 0:
        return float(v.mean())
    return float((w * v).sum() / w.sum())


def _aggregate_1d(df, columns):
    sum_cols = {
        "M_out_dot",
        "M_sink_dot",
        "M_loss_cum",
        "M_sink_cum",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "mass_total_bins",
        "mass_lost_sinks_step",
        "mass_lost_sublimation_step",
    }
    mean_cols = {
        "Sigma_surf",
        "sigma_surf",
        "sigma_deep",
        "Sigma_tau1",
        "sigma_tau1",
        "outflux_surface",
        "prod_subblow_area_rate",
        "supply_rate_nominal",
        "supply_rate_scaled",
        "supply_rate_applied",
        "prod_rate_raw",
        "prod_rate_applied_to_surf",
        "prod_rate_diverted_to_deep",
        "deep_to_surf_flux",
        "supply_headroom",
        "supply_clip_factor",
        "headroom",
        "tau",
        "tau_los_mars",
        "tau_eff",
        "dt_over_t_blow",
        "t_blow",
        "t_coll",
    }
    weights_map = _compute_cell_weights(df)
    rows = []
    for time_val, group in df.groupby("time", sort=True):
        weights = None
        if weights_map is not None and "cell_index" in group:
            weights = group["cell_index"].map(weights_map).to_numpy(dtype=float)
        row = {"time": float(time_val)}
        if "dt" in group.columns:
            row["dt"] = float(group["dt"].iloc[0])
        for col in columns:
            if col == "time" or col == "dt":
                continue
            if col in sum_cols and col in group.columns:
                row[col] = float(group[col].sum(skipna=True))
            elif col in mean_cols and col in group.columns:
                row[col] = _weighted_mean(group[col], weights)
            elif col in group.columns:
                series = group[col].dropna()
                row[col] = float(series.iloc[0]) if not series.empty else float("nan")
            else:
                row[col] = float("nan")
        rows.append(row)
    return rows


def _load_series(run_dir: Path, columns):
    series_dir = run_dir / "series"
    run_path = series_dir / "run.parquet"
    if run_path.exists():
        df = _read_parquet(run_path, columns)
        return df
    chunk_paths = sorted(series_dir.glob("run_chunk_*.parquet"))
    if not chunk_paths:
        print(f"[warn] series not found: {series_dir}, skip plotting")
        return None
    frames = [_read_parquet(path, columns) for path in chunk_paths]
    return _concat_frames(frames)


def _concat_frames(frames):
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return None
    return _pd_concat(frames)


def _pd_concat(frames):
    import pandas as pd

    return pd.concat(frames, ignore_index=True)


def _read_parquet(path: Path, columns):
    import pandas as pd

    available = None
    try:
        import pyarrow.parquet as pq

        schema = pq.read_schema(path)
        available = set(schema.names)
    except Exception:
        available = None
    if available is None:
        return pd.read_parquet(path)
    keep = [c for c in columns if c in available]
    if not keep:
        return pd.read_parquet(path)
    return pd.read_parquet(path, columns=keep)


def _downsample(df, max_rows):
    if df is None or df.empty:
        return df
    if max_rows <= 0:
        return df
    step = max(len(df) // max_rows, 1)
    return df.iloc[::step].copy()


def _plot_quicklook(df, plots_dir: Path):
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.use("Agg")
    years = df["time"] / 3.15576e7
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    ax_rates, ax_cum, ax_tau = axes

    for col in ("M_out_dot", "M_sink_dot"):
        if col in df:
            ax_rates.plot(years, df[col], label=col)
    ax_rates.set_ylabel("loss rate [M_Mars s^-1]")
    ax_rates.legend()
    ax_rates.grid(True, alpha=0.3)

    for col in ("mass_lost_by_blowout", "mass_lost_by_sinks", "mass_total_bins"):
        if col in df:
            ax_cum.plot(years, df[col], label=col)
    ax_cum.set_ylabel("mass [M_Mars]")
    ax_cum.legend()
    ax_cum.grid(True, alpha=0.3)

    tau_col = "tau_los_mars" if "tau_los_mars" in df else "tau"
    if tau_col in df:
        ax_tau.plot(years, df[tau_col], label=tau_col, color="tab:blue")
    if "tau_eff" in df:
        ax_tau.plot(years, df["tau_eff"], label="tau_eff", color="tab:cyan")
    ax_tau.set_ylabel("tau")
    ax_tau.grid(True, alpha=0.3)
    ax_supply = ax_tau.twinx()
    if "prod_subblow_area_rate" in df:
        ax_supply.plot(years, df["prod_subblow_area_rate"], label="prod_subblow_area_rate", color="tab:orange")
    ax_supply.set_ylabel("prod_subblow [kg m^-2 s^-1]")
    handles, labels = ax_tau.get_legend_handles_labels()
    h2, l2 = ax_supply.get_legend_handles_labels()
    ax_tau.legend(handles + h2, labels + l2, loc="upper right")
    axes[-1].set_xlabel("time [yr]")
    fig.tight_layout()
    fig.savefig(plots_dir / "quicklook.png", dpi=180)
    plt.close(fig)


def main(run_dir: Path) -> int:
    try:
        import matplotlib
        import pandas as pd  # noqa: F401
    except ImportError as exc:
        print(f"[error] Missing dependency: {exc}", file=sys.stderr)
        return 1
    matplotlib.use("Agg")

    summary = _load_summary(run_dir)

    plot_cols = [
        "time",
        "dt",
        "M_out_dot",
        "M_sink_dot",
        "M_loss_cum",
        "M_sink_cum",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "mass_total_bins",
        "s_min",
        "a_blow",
        "prod_subblow_area_rate",
        "Sigma_surf",
        "Sigma_tau1",
        "outflux_surface",
        "tau",
        "tau_los_mars",
        "tau_eff",
        "dt_over_t_blow",
        "t_blow",
        "t_coll",
        "supply_rate_nominal",
        "supply_rate_scaled",
        "supply_rate_applied",
        "prod_rate_raw",
        "prod_rate_applied_to_surf",
        "prod_rate_diverted_to_deep",
        "deep_to_surf_flux",
        "sigma_deep",
        "supply_headroom",
        "supply_clip_factor",
        "headroom",
        "supply_feedback_scale",
        "supply_temperature_scale",
        "supply_reservoir_remaining_Mmars",
        "cell_index",
        "r_m",
    ]
    df = _load_series(run_dir, plot_cols)
    if df is None or df.empty:
        return 0
    df = df.sort_values("time") if "time" in df.columns else df
    is_1d = "cell_index" in df.columns
    out_dir = run_dir / ("figures" if is_1d else "plots")
    out_dir.mkdir(parents=True, exist_ok=True)
    if is_1d:
        rows = _aggregate_1d(df, plot_cols)
        import pandas as pd

        df = pd.DataFrame(rows)

    if "tau_los_mars" not in df.columns and "tau" in df.columns:
        df["tau_los_mars"] = df["tau"]
    if "tau" not in df.columns and "tau_los_mars" in df.columns:
        df["tau"] = df["tau_los_mars"]

    max_rows = int(os.environ.get("PLOT_MAX_ROWS", "4000") or "4000")
    df = _downsample(df, max_rows)
    df["time_days"] = df["time"] / 86400.0

    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    if "M_out_dot" in df:
        axes[0].plot(df["time_days"], df["M_out_dot"], label="M_out_dot", lw=1.2)
    if "M_sink_dot" in df:
        axes[0].plot(df["time_days"], df["M_sink_dot"], label="M_sink_dot", lw=1.0, alpha=0.7)
    axes[0].set_ylabel("M_Mars / s")
    axes[0].legend(loc="upper right")
    axes[0].set_title("Mass loss rates")

    if "M_loss_cum" in df:
        axes[1].plot(df["time_days"], df["M_loss_cum"], label="M_loss_cum", lw=1.2)
    if "mass_lost_by_blowout" in df:
        axes[1].plot(df["time_days"], df["mass_lost_by_blowout"], label="mass_lost_by_blowout", lw=1.0)
    if "mass_lost_by_sinks" in df:
        axes[1].plot(df["time_days"], df["mass_lost_by_sinks"], label="mass_lost_by_sinks", lw=1.0)
    axes[1].set_ylabel("M_Mars")
    axes[1].legend(loc="upper left")
    axes[1].set_title("Cumulative losses")

    if "s_min" in df:
        axes[2].plot(df["time_days"], df["s_min"], label="s_min", lw=1.0)
    if "a_blow" in df:
        axes[2].plot(df["time_days"], df["a_blow"], label="a_blow", lw=1.0, alpha=0.8)
    axes[2].set_ylabel("m")
    axes[2].set_xlabel("days")
    axes[2].set_yscale("log")
    axes[2].legend(loc="upper right")
    axes[2].set_title("Minimum size vs blowout")

    title_lines = [run_dir.name]
    mloss = summary.get("M_loss")
    mass_err = summary.get("mass_budget_max_error_percent")
    if mloss is not None:
        title_lines.append(f"M_loss={mloss:.3e} M_Mars")
    if mass_err is not None:
        title_lines.append(f"mass budget err={mass_err:.3f} pct")
    fig.suptitle(" / ".join(title_lines))
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_dir / "overview.png", dpi=180)
    plt.close(fig)

    fig2, ax2 = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    if "prod_subblow_area_rate" in df:
        ax2[0].plot(
            df["time_days"],
            df["prod_subblow_area_rate"],
            label="prod_subblow_area_rate",
            color="tab:blue",
        )
    ax2[0].set_ylabel("kg m^-2 s^-1")
    ax2[0].set_title("Sub-blow supply rate")

    if "Sigma_surf" in df:
        ax2[1].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
    if "outflux_surface" in df:
        ax2[1].plot(
            df["time_days"],
            df["outflux_surface"],
            label="outflux_surface",
            color="tab:red",
            alpha=0.8,
        )
    ax2[1].set_ylabel("kg m^-2 / M_Mars s^-1")
    ax2[1].set_xlabel("days")
    ax2[1].legend(loc="upper right")
    ax2[1].set_title("Surface mass and outflux")

    fig2.suptitle(run_dir.name)
    fig2.tight_layout(rect=(0, 0, 1, 0.95))
    fig2.savefig(out_dir / "supply_surface.png", dpi=180)
    plt.close(fig2)

    fig3, ax3 = plt.subplots(1, 1, figsize=(10, 4))
    tau_col = "tau_los_mars" if "tau_los_mars" in df else "tau"
    if tau_col in df:
        ax3.plot(df["time_days"], df[tau_col], label=tau_col, color="tab:red", alpha=0.8)
    if "tau_eff" in df:
        ax3.plot(df["time_days"], df["tau_eff"], label="tau_eff", color="tab:blue", alpha=0.7)
    ax3.axhline(1.0, color="gray", linestyle=":", alpha=0.5, label="tau=1")
    ax3.set_ylabel("optical depth")
    ax3.set_xlabel("days")
    ax3.set_title("Optical depth evolution")
    ax3.legend(loc="upper right")
    fig3.tight_layout()
    fig3.savefig(out_dir / "optical_depth.png", dpi=180)
    plt.close(fig3)

    _plot_quicklook(df, out_dir)

    print(f"[plot] saved plots to {out_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <run_dir>", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"[error] Directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    sys.exit(main(run_dir))
