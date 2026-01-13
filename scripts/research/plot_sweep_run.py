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


def _select_ring_cells(df):
    if "cell_index" not in df.columns or "r_RM" not in df.columns:
        return []
    cells = (
        df[["cell_index", "r_RM"]]
        .dropna()
        .drop_duplicates()
        .sort_values("r_RM")
    )
    if cells.empty:
        return []
    inner = cells.iloc[0]
    outer = cells.iloc[-1]
    rings = [("inner", int(inner["cell_index"]), float(inner["r_RM"]))]
    if int(outer["cell_index"]) != int(inner["cell_index"]):
        rings.append(("outer", int(outer["cell_index"]), float(outer["r_RM"])))
    return rings


def _series_label(tag, r_rm):
    if r_rm is None or r_rm != r_rm:
        return tag
    return f"{tag} r_RM={r_rm:.3f}"


def _prepare_series_sets(df, columns, max_rows):
    is_1d = "cell_index" in df.columns
    if is_1d and "r_RM" in df.columns:
        rings = _select_ring_cells(df)
        if rings:
            series_sets = []
            for tag, cell_index, r_rm in rings:
                ring_df = df[df["cell_index"] == cell_index].copy()
                if "time" in ring_df.columns:
                    ring_df = ring_df.sort_values("time")
                    ring_df = ring_df.groupby("time", as_index=False).first()
                for col in columns:
                    if col not in ring_df.columns:
                        ring_df[col] = float("nan")
                ring_df = ring_df.reindex(columns=columns)
                ring_df = _downsample(ring_df, max_rows)
                if "time" in ring_df.columns:
                    ring_df["time_days"] = ring_df["time"] / 86400.0
                series_sets.append((tag, r_rm, ring_df))
            return series_sets
    if is_1d:
        rows = _aggregate_1d(df, columns)
        import pandas as pd

        df = pd.DataFrame(rows)
        tag = "avg"
    else:
        tag = "0D"
    df = _downsample(df, max_rows)
    if "time" in df.columns:
        df["time_days"] = df["time"] / 86400.0
    return [(tag, None, df)]


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


def _plot_quicklook(series_sets, plots_dir: Path):
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.use("Agg")

    def _label(base, tag, r_rm):
        suffix = _series_label(tag, r_rm)
        if len(series_sets) == 1 and suffix in ("0D", "avg"):
            return base
        return f"{base} ({suffix})"

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    ax_rates, ax_cum, ax_tau = axes

    for tag, r_rm, df in series_sets:
        years = df["time"] / 3.15576e7
        for col in ("M_out_dot", "M_sink_dot"):
            if col in df:
                ax_rates.plot(years, df[col], label=_label(col, tag, r_rm))
    ax_rates.set_ylabel("loss rate [M_Mars s^-1]")
    ax_rates.legend()
    ax_rates.grid(True, alpha=0.3)

    for tag, r_rm, df in series_sets:
        years = df["time"] / 3.15576e7
        for col in ("mass_lost_by_blowout", "mass_lost_by_sinks", "mass_total_bins"):
            if col in df:
                ax_cum.plot(years, df[col], label=_label(col, tag, r_rm))
    ax_cum.set_ylabel("mass [M_Mars]")
    ax_cum.legend()
    ax_cum.grid(True, alpha=0.3)

    for tag, r_rm, df in series_sets:
        years = df["time"] / 3.15576e7
        tau_col = "tau_los_mars" if "tau_los_mars" in df else "tau"
        if tau_col in df:
            ax_tau.plot(
                years,
                df[tau_col],
                label=_label(tau_col, tag, r_rm),
                color="tab:blue",
                alpha=0.7,
            )
        if "tau_eff" in df:
            ax_tau.plot(
                years,
                df["tau_eff"],
                label=_label("tau_eff", tag, r_rm),
                color="tab:cyan",
                alpha=0.7,
            )
    ax_tau.set_ylabel("tau")
    ax_tau.grid(True, alpha=0.3)
    ax_supply = ax_tau.twinx()
    for tag, r_rm, df in series_sets:
        years = df["time"] / 3.15576e7
        if "prod_subblow_area_rate" in df:
            ax_supply.plot(
                years,
                df["prod_subblow_area_rate"],
                label=_label("prod_subblow_area_rate", tag, r_rm),
                color="tab:orange",
                alpha=0.7,
            )
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
        "r_RM",
    ]
    df = _load_series(run_dir, plot_cols)
    if df is None or df.empty:
        return 0
    df = df.sort_values("time") if "time" in df.columns else df
    is_1d = "cell_index" in df.columns
    out_dir = run_dir / ("figures" if is_1d else "plots")
    out_dir.mkdir(parents=True, exist_ok=True)
    max_rows = int(os.environ.get("PLOT_MAX_ROWS", "4000") or "4000")
    series_sets = _prepare_series_sets(df, plot_cols, max_rows)
    for idx, (tag, r_rm, sdf) in enumerate(series_sets):
        if "tau_los_mars" not in sdf.columns and "tau" in sdf.columns:
            sdf["tau_los_mars"] = sdf["tau"]
        if "tau" not in sdf.columns and "tau_los_mars" in sdf.columns:
            sdf["tau"] = sdf["tau_los_mars"]
        series_sets[idx] = (tag, r_rm, sdf)

    def _label(base, tag, r_rm):
        suffix = _series_label(tag, r_rm)
        if len(series_sets) == 1 and suffix in ("0D", "avg"):
            return base
        return f"{base} ({suffix})"

    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    for tag, r_rm, sdf in series_sets:
        if "M_out_dot" in sdf:
            axes[0].plot(
                sdf["time_days"],
                sdf["M_out_dot"],
                label=_label("M_out_dot", tag, r_rm),
                lw=1.2,
            )
        if "M_sink_dot" in sdf:
            axes[0].plot(
                sdf["time_days"],
                sdf["M_sink_dot"],
                label=_label("M_sink_dot", tag, r_rm),
                lw=1.0,
                alpha=0.7,
            )
    axes[0].set_ylabel("M_Mars / s")
    axes[0].legend(loc="upper right")
    axes[0].set_title("Mass loss rates")

    for tag, r_rm, sdf in series_sets:
        if "M_loss_cum" in sdf:
            axes[1].plot(
                sdf["time_days"],
                sdf["M_loss_cum"],
                label=_label("M_loss_cum", tag, r_rm),
                lw=1.2,
            )
        if "mass_lost_by_blowout" in sdf:
            axes[1].plot(
                sdf["time_days"],
                sdf["mass_lost_by_blowout"],
                label=_label("mass_lost_by_blowout", tag, r_rm),
                lw=1.0,
            )
        if "mass_lost_by_sinks" in sdf:
            axes[1].plot(
                sdf["time_days"],
                sdf["mass_lost_by_sinks"],
                label=_label("mass_lost_by_sinks", tag, r_rm),
                lw=1.0,
            )
    axes[1].set_ylabel("M_Mars")
    axes[1].legend(loc="upper left")
    axes[1].set_title("Cumulative losses")

    for tag, r_rm, sdf in series_sets:
        if "s_min" in sdf:
            axes[2].plot(
                sdf["time_days"],
                sdf["s_min"],
                label=_label("s_min", tag, r_rm),
                lw=1.0,
            )
        if "a_blow" in sdf:
            axes[2].plot(
                sdf["time_days"],
                sdf["a_blow"],
                label=_label("a_blow", tag, r_rm),
                lw=1.0,
                alpha=0.8,
            )
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
    for tag, r_rm, sdf in series_sets:
        if "prod_subblow_area_rate" in sdf:
            ax2[0].plot(
                sdf["time_days"],
                sdf["prod_subblow_area_rate"],
                label=_label("prod_subblow_area_rate", tag, r_rm),
                color="tab:blue",
                alpha=0.7,
            )
    ax2[0].set_ylabel("kg m^-2 s^-1")
    ax2[0].set_title("Sub-blow supply rate")

    for tag, r_rm, sdf in series_sets:
        if "Sigma_surf" in sdf:
            ax2[1].plot(
                sdf["time_days"],
                sdf["Sigma_surf"],
                label=_label("Sigma_surf", tag, r_rm),
                color="tab:green",
                alpha=0.7,
            )
        if "outflux_surface" in sdf:
            ax2[1].plot(
                sdf["time_days"],
                sdf["outflux_surface"],
                label=_label("outflux_surface", tag, r_rm),
                color="tab:red",
                alpha=0.7,
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
    for tag, r_rm, sdf in series_sets:
        tau_col = "tau_los_mars" if "tau_los_mars" in sdf else "tau"
        if tau_col in sdf:
            ax3.plot(
                sdf["time_days"],
                sdf[tau_col],
                label=_label(tau_col, tag, r_rm),
                color="tab:red",
                alpha=0.7,
            )
        if "tau_eff" in sdf:
            ax3.plot(
                sdf["time_days"],
                sdf["tau_eff"],
                label=_label("tau_eff", tag, r_rm),
                color="tab:blue",
                alpha=0.7,
            )
    ax3.axhline(1.0, color="gray", linestyle=":", alpha=0.5, label="tau=1")
    ax3.set_ylabel("optical depth")
    ax3.set_xlabel("days")
    ax3.set_title("Optical depth evolution")
    ax3.legend(loc="upper right")
    fig3.tight_layout()
    fig3.savefig(out_dir / "optical_depth.png", dpi=180)
    plt.close(fig3)

    _plot_quicklook(series_sets, out_dir)

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
