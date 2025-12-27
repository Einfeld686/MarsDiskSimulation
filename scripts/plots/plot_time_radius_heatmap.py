#!/usr/bin/env python3
"""Plot time-radius heatmaps from run outputs (1D default)."""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from matplotlib.ticker import ScalarFormatter

try:
    import matplotlib.pyplot as plt
    from matplotlib import colors
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit("matplotlib is required for plotting") from exc

try:
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit("pyarrow is required for parquet streaming") from exc

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk.constants import R_MARS
from paper.plot_style import apply_default_style

SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
DEFAULT_METRICS_MAIN = ["tau", "Sigma_surf", "s_min", "M_out_dot", "t_coll", "t_blow"]
DEFAULT_METRICS_DIAG = [
    "prod_subblow_area_rate",
    "supply_rate_scaled",
    "ts_ratio",
    "dt_over_t_blow",
    "smol_mass_budget_delta",
    "blowout_phase_allowed",
]
DEFAULT_METRICS = DEFAULT_METRICS_MAIN + DEFAULT_METRICS_DIAG


@dataclass(frozen=True)
class MetricSpec:
    key: str
    candidates: Tuple[str, ...]
    label: str
    unit: str
    scale: str
    cmap: str
    percentiles: Optional[Tuple[float, float]] = None
    abs_percentile: Optional[float] = None
    vmin: Optional[float] = None
    vmax: Optional[float] = None


@dataclass(frozen=True)
class ResolvedMetric:
    key: str
    column: str
    label: str
    unit: str
    scale: str
    cmap: str
    percentiles: Optional[Tuple[float, float]] = None
    abs_percentile: Optional[float] = None
    vmin: Optional[float] = None
    vmax: Optional[float] = None


METRIC_SPECS: Dict[str, MetricSpec] = {
    "tau": MetricSpec(
        key="tau",
        candidates=("tau_los_mars", "tau_mars_line_of_sight", "tau"),
        label="tau_LOS",
        unit="dimensionless",
        scale="log",
        cmap="cividis",
    ),
    "Sigma_surf": MetricSpec(
        key="Sigma_surf",
        candidates=("Sigma_surf", "sigma_surf"),
        label="Sigma_surf",
        unit="kg m^-2",
        scale="log",
        cmap="cividis",
    ),
    "M_out_dot": MetricSpec(
        key="M_out_dot",
        candidates=("M_out_dot",),
        label="M_out_dot",
        unit="M_Mars s^-1",
        scale="log",
        cmap="cividis",
    ),
    "s_min": MetricSpec(
        key="s_min",
        candidates=("s_min_effective", "s_min"),
        label="s_min_eff",
        unit="m",
        scale="log",
        cmap="cividis",
    ),
    "t_coll": MetricSpec(
        key="t_coll",
        candidates=("t_coll",),
        label="t_coll",
        unit="s",
        scale="log",
        cmap="cividis",
    ),
    "t_blow": MetricSpec(
        key="t_blow",
        candidates=("t_blow", "t_blow_s"),
        label="t_blow",
        unit="s",
        scale="log",
        cmap="cividis",
    ),
    "smol_mass_budget_delta": MetricSpec(
        key="smol_mass_budget_delta",
        candidates=("smol_mass_budget_delta",),
        label="smol_budget_delta",
        unit="kg m^-2",
        scale="diverging",
        cmap="RdBu_r",
        abs_percentile=95.0,
    ),
    "prod_subblow_area_rate": MetricSpec(
        key="prod_subblow_area_rate",
        candidates=("prod_subblow_area_rate",),
        label="prod_subblow_rate",
        unit="kg m^-2 s^-1",
        scale="log",
        cmap="cividis",
        percentiles=(5.0, 95.0),
    ),
    "supply_rate_scaled": MetricSpec(
        key="supply_rate_scaled",
        candidates=("supply_rate_scaled",),
        label="supply_rate_scaled",
        unit="kg m^-2 s^-1",
        scale="log",
        cmap="cividis",
        percentiles=(5.0, 95.0),
    ),
    "dt_over_t_blow": MetricSpec(
        key="dt_over_t_blow",
        candidates=("dt_over_t_blow",),
        label="dt_over_t_blow",
        unit="dimensionless",
        scale="linear",
        cmap="cividis",
        vmin=0.0,
        vmax=0.05,
    ),
    "ts_ratio": MetricSpec(
        key="ts_ratio",
        candidates=("ts_ratio",),
        label="ts_ratio",
        unit="dimensionless",
        scale="log",
        cmap="cividis",
        percentiles=(5.0, 95.0),
    ),
    "blowout_phase_allowed": MetricSpec(
        key="blowout_phase_allowed",
        candidates=("blowout_phase_allowed",),
        label="blowout_phase_allowed",
        unit="bool",
        scale="linear",
        cmap="Greys",
        vmin=0.0,
        vmax=1.0,
    ),
}

UNIT_MAP = {
    "tau": "dimensionless",
    "tau_los_mars": "dimensionless",
    "tau_mars_line_of_sight": "dimensionless",
    "Sigma_surf": "kg m^-2",
    "sigma_surf": "kg m^-2",
    "M_out_dot": "M_Mars s^-1",
    "s_min_effective": "m",
    "s_min": "m",
    "t_coll": "s",
    "t_blow": "s",
    "t_blow_s": "s",
    "smol_mass_budget_delta": "kg m^-2",
    "prod_subblow_area_rate": "kg m^-2 s^-1",
    "supply_rate_scaled": "kg m^-2 s^-1",
    "dt_over_t_blow": "dimensionless",
    "ts_ratio": "dimensionless",
    "blowout_phase_allowed": "bool",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot time-radius heatmaps from run outputs (1D default)."
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="run output directory")
    parser.add_argument(
        "--metrics",
        default=None,
        help=(
            "comma/space-separated metric keys "
            "(default: tau,Sigma_surf,M_out_dot,s_min,t_coll,t_blow + diagnostics set)"
        ),
    )
    parser.add_argument("--out", type=Path, help="output directory (default: run_dir/figures)")
    parser.add_argument("--max-time-bins", type=int, default=2000)
    parser.add_argument("--time-stride", type=int, default=1)
    parser.add_argument("--radius-stride", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=200_000)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--reduce", choices=("median", "mean"), default="median")
    parser.add_argument("--sum-metrics", default="M_out_dot")
    parser.add_argument("--auto-scale", action="store_true")
    parser.add_argument("--panels-per-figure", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--title-prefix", default=None)
    return parser.parse_args(list(argv) if argv is not None else None)


def _parse_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts: List[str] = []
    for chunk in value.split(","):
        parts.extend(chunk.strip().split())
    return [part for part in parts if part]


def _resolve_series_files(run_dir: Path) -> Tuple[Optional[Path], List[Path]]:
    series_dir = run_dir / "series"
    run_parquet = series_dir / "run.parquet"
    if run_parquet.exists():
        return run_parquet, []
    chunk_files = sorted(series_dir.glob("run_chunk_*.parquet"))
    return None, chunk_files


def _available_columns(dataset: ds.Dataset) -> List[str]:
    return list(dataset.schema.names)


def _pick_first_available(available: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    available_set = set(available)
    for name in candidates:
        if name in available_set:
            return name
    return None


def _resolve_metrics(
    available: Iterable[str], requested: Iterable[str], *, auto_scale: bool
) -> List[ResolvedMetric]:
    available_set = set(available)
    resolved: List[ResolvedMetric] = []
    for key in requested:
        spec = METRIC_SPECS.get(key)
        if spec is None:
            for candidate in METRIC_SPECS.values():
                if key in candidate.candidates:
                    spec = candidate
                    break
        if spec is not None:
            if key in available_set:
                column = key
            else:
                column = _pick_first_available(available_set, spec.candidates)
            if column is None:
                print(f"[plot_time_radius_heatmap] skip {key}: no column found")
                continue
            scale = "auto" if auto_scale else spec.scale
            resolved.append(
                ResolvedMetric(
                    key=spec.key,
                    column=column,
                    label=spec.label,
                    unit=spec.unit,
                    scale=scale,
                    cmap=spec.cmap,
                    percentiles=spec.percentiles,
                    abs_percentile=spec.abs_percentile,
                    vmin=spec.vmin,
                    vmax=spec.vmax,
                )
            )
            continue

        if key in available_set:
            unit = UNIT_MAP.get(key, "dimensionless")
            scale = "auto" if auto_scale else "auto"
            resolved.append(
                ResolvedMetric(
                    key=key,
                    column=key,
                    label=key,
                    unit=unit,
                    scale=scale,
                    cmap="cividis",
                    percentiles=None,
                    abs_percentile=None,
                    vmin=None,
                    vmax=None,
                )
            )
            continue

        print(f"[plot_time_radius_heatmap] skip {key}: no column found")
    return resolved


def _minmax_from_parquet(path: Path, column: str) -> Tuple[Optional[float], Optional[float]]:
    pf = pq.ParquetFile(path)
    try:
        col_index = pf.schema_arrow.get_field_index(column)
    except Exception:
        return None, None
    if col_index < 0:
        return None, None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    for rg_index in range(pf.num_row_groups):
        stats = pf.metadata.row_group(rg_index).column(col_index).statistics
        if stats is None:
            continue
        try:
            rg_min = float(stats.min)
            rg_max = float(stats.max)
        except Exception:
            continue
        min_val = rg_min if min_val is None else min(min_val, rg_min)
        max_val = rg_max if max_val is None else max(max_val, rg_max)
    return min_val, max_val


def _minmax_time(
    dataset: ds.Dataset,
    files: List[Path],
    column: str,
    *,
    batch_size: int,
) -> Tuple[float, float]:
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    for path in files:
        rg_min, rg_max = _minmax_from_parquet(path, column)
        if rg_min is None or rg_max is None:
            continue
        min_val = rg_min if min_val is None else min(min_val, rg_min)
        max_val = rg_max if max_val is None else max(max_val, rg_max)
    if min_val is not None and max_val is not None:
        return min_val, max_val

    if hasattr(dataset, "to_batches"):
        batches = dataset.to_batches(columns=[column], batch_size=batch_size)
    else:
        scanner = dataset.scan(columns=[column], batch_size=batch_size)
        batches = scanner.to_batches()
    for batch in batches:
        arr = batch.column(0).to_numpy(zero_copy_only=False)
        if arr.size == 0:
            continue
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            continue
        batch_min = float(np.min(finite))
        batch_max = float(np.max(finite))
        min_val = batch_min if min_val is None else min(min_val, batch_min)
        max_val = batch_max if max_val is None else max(max_val, batch_max)
    if min_val is None or max_val is None:
        raise ValueError("Unable to determine time range from dataset")
    return min_val, max_val


def _estimate_row_stride(dataset: ds.Dataset, max_rows: Optional[int]) -> int:
    if not max_rows or max_rows <= 0:
        return 1
    try:
        total_rows = dataset.count_rows()
    except Exception:
        return 1
    if total_rows <= max_rows:
        return 1
    return int(math.ceil(total_rows / max_rows))


def _row_stride_mask(length: int, stride: int, offset: int) -> Tuple[np.ndarray, int]:
    if stride <= 1:
        return np.ones(length, dtype=bool), offset + length
    indices = np.arange(length) + offset
    mask = (indices % stride) == 0
    return mask, offset + length


def _coarsen_edges(edges: np.ndarray, stride: int) -> np.ndarray:
    if stride <= 1:
        return edges
    if edges.size <= 1:
        return edges
    new_edges = edges[::stride]
    if new_edges[-1] != edges[-1]:
        new_edges = np.append(new_edges, edges[-1])
    return new_edges


def _coarsen_time(values: np.ndarray, stride: int) -> np.ndarray:
    if stride <= 1:
        return values
    n_bins = values.shape[1]
    n_groups = int(math.ceil(n_bins / stride))
    out = np.full((values.shape[0], n_groups), np.nan)
    for idx in range(n_groups):
        start = idx * stride
        end = min((idx + 1) * stride, n_bins)
        block = values[:, start:end]
        out[:, idx] = np.nanmean(block, axis=1)
    return out


def _coarsen_radius(values: np.ndarray, r_values: np.ndarray, stride: int) -> Tuple[np.ndarray, np.ndarray]:
    if stride <= 1:
        return values, r_values
    n_rows = values.shape[0]
    n_groups = int(math.ceil(n_rows / stride))
    out = np.full((n_groups, values.shape[1]), np.nan)
    r_out = np.full(n_groups, np.nan)
    for idx in range(n_groups):
        start = idx * stride
        end = min((idx + 1) * stride, n_rows)
        block = values[start:end, :]
        out[idx, :] = np.nanmean(block, axis=0)
        r_out[idx] = float(np.nanmean(r_values[start:end]))
    return out, r_out


def _compute_edges(values: np.ndarray) -> np.ndarray:
    if values.size == 1:
        delta = 0.5 if values[0] == 0 else 0.1 * abs(values[0])
        delta = max(delta, 0.05)
        return np.array([values[0] - delta, values[0] + delta])
    mid = (values[:-1] + values[1:]) / 2.0
    first = values[0] - (mid[0] - values[0])
    last = values[-1] + (values[-1] - mid[-1])
    return np.concatenate(([first], mid, [last]))


def _auto_scale(values: np.ndarray) -> str:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return "linear"
    if np.any(finite < 0.0) and np.any(finite > 0.0):
        return "diverging"
    if np.any(finite <= 0.0):
        return "linear"
    p5, p95 = np.percentile(finite, [5, 95])
    if p5 <= 0.0:
        return "linear"
    if (p95 / p5) > 10.0:
        return "log"
    return "linear"


def _prepare_colormap(name: str) -> colors.Colormap:
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(color="lightgray")
    return cmap


def _scale_values(
    values: np.ndarray,
    scale: str,
    *,
    vmin: Optional[float],
    vmax: Optional[float],
    percentiles: Optional[Tuple[float, float]],
    abs_percentile: Optional[float],
) -> Tuple[np.ndarray, colors.Normalize, str]:
    if scale == "log":
        masked = np.where(values > 0.0, values, np.nan)
        log_values = np.log10(masked)
        finite = log_values[np.isfinite(log_values)]
        if finite.size == 0:
            raise ValueError("no positive values for log scale")
        pct = percentiles or (1.0, 99.0)
        vmin_log, vmax_log = np.percentile(finite, pct)
        if vmin is not None and vmin > 0.0:
            vmin_log = math.log10(vmin)
        if vmax is not None and vmax > 0.0:
            vmax_log = math.log10(vmax)
        if vmin_log == vmax_log:
            vmax_log = vmin_log + 1.0
        norm = colors.Normalize(vmin=vmin_log, vmax=vmax_log)
        return log_values, norm, "log10"
    if scale == "diverging":
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            raise ValueError("no finite values for diverging scale")
        pct = abs_percentile or 99.0
        limit = float(np.percentile(np.abs(finite), pct))
        if limit == 0.0:
            limit = float(np.max(np.abs(finite)))
        if limit == 0.0:
            limit = 1.0
        norm = colors.TwoSlopeNorm(vcenter=0.0, vmin=-limit, vmax=limit)
        return values, norm, "linear"
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("no finite values for linear scale")
    if vmin is None or vmax is None:
        pct = percentiles or (1.0, 99.0)
        vmin_val, vmax_val = np.percentile(finite, pct)
        if vmin is None:
            vmin = vmin_val
        if vmax is None:
            vmax = vmax_val
    if vmin == vmax:
        vmax = vmin + 1.0
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    return values, norm, "linear"


def _plot_page(
    metrics: List[ResolvedMetric],
    grids: Dict[str, np.ndarray],
    time_edges: np.ndarray,
    r_edges: np.ndarray,
    *,
    out_path: Path,
    title: str,
    zero_d: bool,
    dpi: int,
) -> None:
    n_panels = len(metrics)
    cols = min(3, n_panels)
    rows = int(math.ceil(n_panels / cols))
    figsize = (3.6 * cols, 3.0 * rows)
    fig, axes = plt.subplots(rows, cols, figsize=figsize, squeeze=False)

    for ax, metric in zip(axes.flat, metrics):
        values = grids[metric.key]
        scale = metric.scale
        if scale == "auto":
            scale = _auto_scale(values)
        try:
            plot_values, norm, scale_kind = _scale_values(
                values,
                scale,
                vmin=metric.vmin,
                vmax=metric.vmax,
                percentiles=metric.percentiles,
                abs_percentile=metric.abs_percentile,
            )
        except ValueError:
            ax.set_visible(False)
            continue
        cmap = _prepare_colormap(metric.cmap)
        mesh = ax.pcolormesh(
            time_edges,
            r_edges,
            plot_values,
            shading="auto",
            cmap=cmap,
            norm=norm,
        )
        ax.set_xlabel("time [yr]")
        ax.set_ylabel("r/R_Mars")
        ax.set_title(metric.label, pad=8)
        cbar = fig.colorbar(mesh, ax=ax)
        if scale_kind == "log10":
            cbar.set_label(f"log10({metric.label} [{metric.unit}])")
        else:
            cbar.set_label(f"{metric.label} [{metric.unit}]")
        formatter = ScalarFormatter(useOffset=False)
        formatter.set_scientific(False)
        cbar.ax.yaxis.set_major_formatter(formatter)
        cbar.ax.yaxis.get_offset_text().set_visible(False)
        cbar.update_ticks()

    for ax in axes.flat[n_panels:]:
        ax.set_visible(False)

    fig_title = title
    if zero_d:
        fig_title = f"{fig_title} (0D)"
    fig.suptitle(fig_title)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.95])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    out_dir = args.out or (run_dir / "figures")
    apply_default_style()

    run_parquet, chunk_files = _resolve_series_files(run_dir)
    files: List[Path]
    if run_parquet is not None:
        files = [run_parquet]
    else:
        files = chunk_files
    if not files:
        raise SystemExit(f"No run.parquet or run_chunk_*.parquet under {run_dir / 'series'}")

    dataset = ds.dataset([str(p) for p in files], format="parquet")
    available = _available_columns(dataset)

    if "time" not in available:
        raise SystemExit("Required column 'time' not found in series data.")

    r_field: Optional[str]
    if "r_RM" in available:
        r_field = "r_RM"
    elif "r_m" in available:
        r_field = "r_m"
    else:
        r_field = None

    resolved_groups: List[Tuple[str, List[ResolvedMetric]]] = []
    if args.metrics:
        metrics_requested = _parse_list(args.metrics)
        resolved = _resolve_metrics(available, metrics_requested, auto_scale=args.auto_scale)
        if resolved:
            resolved_groups.append(("time_radius_heatmap", resolved))
    else:
        resolved_main = _resolve_metrics(available, DEFAULT_METRICS_MAIN, auto_scale=args.auto_scale)
        resolved_diag = _resolve_metrics(available, DEFAULT_METRICS_DIAG, auto_scale=args.auto_scale)
        if resolved_main:
            resolved_groups.append(("time_radius_heatmap", resolved_main))
        if resolved_diag:
            resolved_groups.append(("time_radius_heatmap_diag", resolved_diag))
    if not resolved_groups:
        raise SystemExit("No metrics available to plot.")

    resolved_all: List[ResolvedMetric] = []
    seen_keys: set[str] = set()
    for _, group in resolved_groups:
        for metric in group:
            if metric.key in seen_keys:
                continue
            resolved_all.append(metric)
            seen_keys.add(metric.key)

    columns = {"time"}
    if r_field is not None:
        columns.add(r_field)
    for metric in resolved_all:
        columns.add(metric.column)
    columns_list = sorted(columns)

    time_min, time_max = _minmax_time(dataset, files, "time", batch_size=args.batch_size)
    if time_min == time_max:
        time_max = time_min + 1.0
    n_bins = max(1, int(args.max_time_bins))
    time_edges = np.linspace(time_min, time_max, n_bins + 1)

    row_stride = _estimate_row_stride(dataset, args.max_rows)
    row_offset = 0

    r_values: List[float] = []
    r_index: Dict[float, int] = {}
    sums: Dict[str, List[np.ndarray]] = {metric.key: [] for metric in resolved_all}
    counts: Dict[str, List[np.ndarray]] = {metric.key: [] for metric in resolved_all}

    sum_metrics = set(_parse_list(args.sum_metrics))
    if hasattr(dataset, "to_batches"):
        batches = dataset.to_batches(columns=columns_list, batch_size=args.batch_size)
    else:
        scanner = dataset.scan(columns=columns_list, batch_size=args.batch_size)
        batches = scanner.to_batches()
    for batch in batches:
        df = batch.to_pandas()
        if df.empty:
            continue
        mask, row_offset = _row_stride_mask(len(df), row_stride, row_offset)
        if not np.all(mask):
            df = df.loc[mask]
        if df.empty:
            continue

        if r_field is None:
            df = df.assign(r_RM=1.0)
        elif r_field == "r_m":
            df = df.assign(r_RM=df["r_m"] / R_MARS)
        else:
            df = df.assign(r_RM=df[r_field])

        df = df[np.isfinite(df["time"]) & np.isfinite(df["r_RM"])]
        if df.empty:
            continue

        agg = {metric.column: args.reduce for metric in resolved_all}
        for metric in resolved_all:
            if metric.key in sum_metrics or metric.column in sum_metrics:
                agg[metric.column] = "sum"
        df = df.groupby(["time", "r_RM"], sort=False).agg(agg).reset_index()
        if df.empty:
            continue

        times = df["time"].to_numpy(dtype=float)
        r_vals = df["r_RM"].to_numpy(dtype=float)
        bin_idx = np.searchsorted(time_edges, times, side="right") - 1
        bin_idx = np.clip(bin_idx, 0, n_bins - 1)

        for r_val in np.unique(r_vals):
            r_key = float(r_val)
            r_idx = r_index.get(r_key)
            if r_idx is None:
                r_idx = len(r_values)
                r_index[r_key] = r_idx
                r_values.append(r_key)
                for metric in resolved_all:
                    sums[metric.key].append(np.zeros(n_bins, dtype=float))
                    counts[metric.key].append(np.zeros(n_bins, dtype=float))

            mask_r = r_vals == r_val
            bins_r = bin_idx[mask_r]
            for metric in resolved_all:
                vals = df.loc[mask_r, metric.column].to_numpy(dtype=float)
                finite = np.isfinite(vals)
                if not np.any(finite):
                    continue
                np.add.at(sums[metric.key][r_idx], bins_r[finite], vals[finite])
                np.add.at(counts[metric.key][r_idx], bins_r[finite], 1.0)

    if not r_values:
        raise SystemExit("No valid r values found in series data.")

    order = np.argsort(np.array(r_values))
    r_sorted = np.array(r_values)[order]
    grids: Dict[str, np.ndarray] = {}
    for metric in resolved_all:
        sum_arr = np.vstack(sums[metric.key])[order]
        count_arr = np.vstack(counts[metric.key])[order]
        with np.errstate(invalid="ignore", divide="ignore"):
            grids[metric.key] = np.where(count_arr > 0.0, sum_arr / count_arr, np.nan)

    if args.time_stride > 1:
        time_edges = _coarsen_edges(time_edges, args.time_stride)
        for metric in resolved_all:
            grids[metric.key] = _coarsen_time(grids[metric.key], args.time_stride)

    if args.radius_stride > 1:
        r_coarse: Optional[np.ndarray] = None
        for metric in resolved_all:
            grid_coarse, r_coarse = _coarsen_radius(grids[metric.key], r_sorted, args.radius_stride)
            grids[metric.key] = grid_coarse
        if r_coarse is not None:
            r_sorted = r_coarse

    time_edges_yr = time_edges / SECONDS_PER_YEAR
    r_edges = _compute_edges(r_sorted)

    panels_per_fig = min(max(1, args.panels_per_figure), 6)
    title = args.title_prefix or run_dir.name
    zero_d = (r_field is None) or (r_sorted.size == 1)

    for base_name, metrics in resolved_groups:
        pages = [
            metrics[idx : idx + panels_per_fig] for idx in range(0, len(metrics), panels_per_fig)
        ]
        for idx, page_metrics in enumerate(pages, start=1):
            suffix = f"_page{idx}" if len(pages) > 1 else ""
            out_path = out_dir / f"{base_name}{suffix}.png"
            _plot_page(
                page_metrics,
                grids,
                time_edges_yr,
                r_edges,
                out_path=out_path,
                title=title,
                zero_d=zero_d,
                dpi=args.dpi,
            )
            print(f"[plot_time_radius_heatmap] wrote {out_path}")


if __name__ == "__main__":
    main()
