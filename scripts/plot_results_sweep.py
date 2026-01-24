#!/usr/bin/env python3
"""Plot sweep results for thesis-ready mass loss figures.

Input directory structure (RUN_ROOT):
  RUN_ROOT/
    <run_name>/
      series/run.parquet (or series/run_chunk_*.parquet)
      summary.json
      checks/mass_budget.csv
      run_config.json (optional)

Outputs (saved into subdirectories of --outdir as PNG):
  cumloss_grid/<run_name>.png
  outflow_tau_cumloss_representative/<run_name>.png
  final_cumloss_heatmap/<run_name>.png
  mass_budget_error/<run_name>.png
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SECONDS_PER_YEAR = 365.25 * 24 * 3600
LOG_CLIP_FRACTION = 1e-8
LOG_CLIP_OUTFLOW = 1e-30

PARAM_CANDIDATES = {
    "T_M": ["T_M", "T_Mars", "T0", "T_init", "T_mars0"],
    "epsilon_mix": ["epsilon_mix", "eps_mix", "eps", "epsilon"],
    "tau0": ["tau0", "tau_init", "tau_eff0", "tau_norm"],
    "i0": ["i0", "inc0", "incl0"],
    "f_Q": ["f_Q", "f_Qstar", "f_Q*", "f_q"],
}

REGEX_T = re.compile(r"T(\d+)")
REGEX_EPS = re.compile(r"eps([0-9]+(?:p[0-9]+)?)")
REGEX_TAU = re.compile(r"tau([0-9]+(?:p[0-9]+)?)")
REGEX_I0 = re.compile(r"i0?([0-9]+(?:p[0-9]+)?)")
REGEX_FQ = re.compile(r"fQ([0-9]+(?:p[0-9]+)?)")
_NO_MATCH = object()

OUTPUT_SUBDIRS = {
    "cumloss": "cumloss_grid",
    "outflow": "outflow_tau_cumloss_representative",
    "heatmap": "final_cumloss_heatmap",
    "mass_budget": "mass_budget_error",
}


@dataclass(frozen=True)
class RunData:
    path: Path
    name: str
    params: dict[str, float | None]
    series: pd.DataFrame
    summary: dict
    mass_budget: pd.DataFrame | None
    mass_initial: float | None
    tau_stop: float | None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot cumulative loss, outflow, and validation figures from sweep runs."
    )
    parser.add_argument("--run-root", type=Path, required=True, help="Root directory of run outputs.")
    parser.add_argument("--outdir", type=Path, required=True, help="Output directory for figures.")
    parser.add_argument("--baseline-i0", type=float, default=None, help="Fix baseline i0 to this value.")
    parser.add_argument(
        "--baseline-fq",
        type=float,
        default=None,
        help="Fix baseline f_Q* to this value (default prefers 1.0).",
    )
    parser.add_argument(
        "--max-lines-per-axes",
        type=int,
        default=6,
        help="Maximum number of lines per subplot (default: 6).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _warn(message: str) -> None:
    print(f"[warn] {message}", file=sys.stderr)


def _info(message: str) -> None:
    print(f"[info] {message}")


def _read_json(path: Path) -> dict:
    if not path.exists():
        _warn(f"missing json: {path}")
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        _warn(f"failed to read json {path}: {exc}")
        return {}


def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        _warn(f"missing csv: {path}")
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        _warn(f"failed to read csv {path}: {exc}")
        return None


def _collect_series_paths(series_dir: Path) -> list[Path]:
    run_parquet = series_dir / "run.parquet"
    if run_parquet.exists():
        return [run_parquet]
    return sorted(series_dir.glob("run_chunk_*.parquet"))


def _read_parquet(path: Path, columns: list[str]) -> pd.DataFrame | None:
    try:
        try:
            import pyarrow.parquet as pq

            schema = pq.read_schema(path)
            available = set(schema.names)
            keep = [c for c in columns if c in available]
            if keep:
                return pd.read_parquet(path, columns=keep)
        except Exception:
            pass
        try:
            return pd.read_parquet(path, columns=columns)
        except Exception:
            return pd.read_parquet(path)
    except Exception as exc:
        _warn(f"failed to read parquet {path}: {exc}")
        return None


def _compute_cell_weights(df: pd.DataFrame) -> dict[int, float] | None:
    if "cell_index" not in df.columns:
        return None
    radius_col = None
    if "r_m" in df.columns:
        radius_col = "r_m"
    elif "r_RM" in df.columns:
        radius_col = "r_RM"
    if radius_col is None:
        return None
    cells = (
        df[["cell_index", radius_col]]
        .dropna()
        .drop_duplicates()
        .sort_values("cell_index")
    )
    if cells.empty:
        return None
    r_vals = cells[radius_col].to_numpy(dtype=float)
    if r_vals.size == 1:
        weights = np.array([1.0], dtype=float)
    else:
        edges = np.empty(r_vals.size + 1, dtype=float)
        edges[1:-1] = 0.5 * (r_vals[1:] + r_vals[:-1])
        edges[0] = r_vals[0] - (edges[1] - r_vals[0])
        edges[-1] = r_vals[-1] + (r_vals[-1] - edges[-2])
        edges = np.maximum(edges, 0.0)
        areas = math.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
        total = float(np.sum(areas))
        if total > 0:
            weights = areas / total
        else:
            weights = np.ones_like(r_vals) / float(r_vals.size)
    return {
        int(cell): float(weight)
        for cell, weight in zip(cells["cell_index"].astype(int), weights)
    }


def _weighted_mean(values: pd.Series, weights: np.ndarray | None) -> float:
    vals = values.to_numpy(dtype=float)
    mask = np.isfinite(vals)
    if not mask.any():
        return float("nan")
    if weights is None:
        return float(np.nanmean(vals))
    w = weights[mask]
    v = vals[mask]
    wsum = float(np.sum(w))
    if wsum <= 0:
        return float(np.nanmean(v))
    return float(np.sum(w * v) / wsum)


def _aggregate_series(df: pd.DataFrame) -> pd.DataFrame:
    if "cell_index" not in df.columns:
        return df.sort_values("time")
    weights_map = _compute_cell_weights(df)
    rows = []
    for time_val, group in df.groupby("time", sort=True):
        row = {"time": float(time_val)}
        weights = None
        if weights_map is not None:
            weights = group["cell_index"].map(weights_map).to_numpy(dtype=float)
        if "tau" in group.columns:
            row["tau"] = _weighted_mean(group["tau"], weights)
        if "M_out_dot" in group.columns:
            row["M_out_dot"] = float(group["M_out_dot"].sum(skipna=True))
        if "M_loss_cum" in group.columns:
            row["M_loss_cum"] = float(group["M_loss_cum"].sum(skipna=True))
        rows.append(row)
    return pd.DataFrame(rows)


def _load_series(run_dir: Path) -> pd.DataFrame | None:
    series_dir = run_dir / "series"
    if not series_dir.exists():
        _warn(f"missing series dir: {series_dir}")
        return None
    paths = _collect_series_paths(series_dir)
    if not paths:
        _warn(f"missing run.parquet or run_chunk_*.parquet: {series_dir}")
        return None
    if (series_dir / "run.parquet").exists() is False:
        _warn(f"run.parquet missing, using chunks: {series_dir}")
    columns = ["time", "tau", "M_out_dot", "M_loss_cum", "cell_index", "r_RM", "r_m"]
    frames = []
    for path in paths:
        df = _read_parquet(path, columns=columns)
        if df is None or df.empty:
            continue
        frames.append(df)
    if not frames:
        _warn(f"no series data found: {run_dir}")
        return None
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.dropna(subset=["time"])
    if merged.empty:
        _warn(f"empty series data: {run_dir}")
        return None
    merged = _aggregate_series(merged)
    required = ["time", "tau", "M_out_dot", "M_loss_cum"]
    missing = [col for col in required if col not in merged.columns]
    if missing:
        _warn(f"missing required columns {missing} in {run_dir}")
        return None
    merged = merged.sort_values("time").reset_index(drop=True)
    merged["t_year"] = merged["time"] / SECONDS_PER_YEAR
    return merged


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def _search_key_paths(data: object, key: str) -> list[tuple[str, object]]:
    matches: list[tuple[str, object]] = []

    def walk(obj: object, path: list[str]) -> None:
        if isinstance(obj, dict):
            for k in sorted(obj.keys()):
                v = obj[k]
                next_path = path + [k]
                if k == key:
                    matches.append((".".join(next_path), v))
                walk(v, next_path)
        elif isinstance(obj, list):
            for idx, v in enumerate(obj):
                walk(v, path + [str(idx)])

    walk(data, [])
    return matches


def _find_first_value(config: dict, candidates: Iterable[str]) -> float | None:
    for key in candidates:
        matches = _search_key_paths(config, key)
        if not matches:
            continue
        matches.sort(key=lambda item: (len(item[0]), item[0]))
        value = _coerce_float(matches[0][1])
        if value is not None:
            return value
    return None


def _parse_decimal(token: str | None) -> float | None:
    if not token:
        return None
    try:
        return float(token.replace("p", "."))
    except ValueError:
        return None


def _parse_params_from_name(name: str) -> dict[str, float | None]:
    values: dict[str, float | None] = {
        "T_M": None,
        "epsilon_mix": None,
        "tau0": None,
        "i0": None,
        "f_Q": None,
    }
    match = REGEX_T.search(name)
    if match:
        try:
            values["T_M"] = float(match.group(1))
        except ValueError:
            values["T_M"] = None
    match = REGEX_EPS.search(name)
    if match:
        values["epsilon_mix"] = _parse_decimal(match.group(1))
    match = REGEX_TAU.search(name)
    if match:
        values["tau0"] = _parse_decimal(match.group(1))
    match = REGEX_I0.search(name)
    if match:
        values["i0"] = _parse_decimal(match.group(1))
    match = REGEX_FQ.search(name)
    if match:
        values["f_Q"] = _parse_decimal(match.group(1))
    return values


def _extract_params(run_dir: Path, config: dict) -> tuple[dict[str, float | None], float | None]:
    params: dict[str, float | None] = {}
    for param_name, keys in PARAM_CANDIDATES.items():
        params[param_name] = _find_first_value(config, keys)
    tau_stop = _find_first_value(config, ["tau_stop"])
    name_values = _parse_params_from_name(run_dir.name)
    for key, value in name_values.items():
        if params.get(key) is None and value is not None:
            params[key] = value
    return params, tau_stop


def _sort_value(value: float | None) -> tuple[int, float]:
    if value is None or not math.isfinite(value):
        return (1, 0.0)
    return (0, float(value))


def _run_sort_key(run: RunData) -> tuple:
    return (
        _sort_value(run.params.get("T_M")),
        _sort_value(run.params.get("epsilon_mix")),
        _sort_value(run.params.get("tau0")),
        _sort_value(run.params.get("i0")),
        _sort_value(run.params.get("f_Q")),
        run.name,
    )


def _value_mode(values: list[float]) -> float | None:
    if not values:
        return None
    rounded = [round(v, 6) for v in values]
    counts: dict[float, int] = {}
    for v in rounded:
        counts[v] = counts.get(v, 0) + 1
    best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    for v in values:
        if round(v, 6) == best:
            return v
    return values[0]


def _match_value(value: float | None, target: float) -> bool:
    if value is None or not math.isfinite(value):
        return False
    return math.isclose(float(value), float(target), rel_tol=1e-6, abs_tol=1e-9)


def _select_baseline(
    runs: list[RunData],
    baseline_i0: float | None,
    baseline_fq: float | None,
) -> tuple[list[RunData], dict[str, float | None]]:
    values_fq = [r.params["f_Q"] for r in runs if r.params.get("f_Q") is not None]
    values_fq = [float(v) for v in values_fq if math.isfinite(float(v))]
    selected_fq = None
    if baseline_fq is not None:
        selected_fq = float(baseline_fq)
    elif values_fq:
        if any(math.isclose(v, 1.0, rel_tol=1e-6, abs_tol=1e-9) for v in values_fq):
            selected_fq = 1.0
        else:
            selected_fq = _value_mode(values_fq)
    if selected_fq is not None:
        runs = [r for r in runs if _match_value(r.params.get("f_Q"), selected_fq)]

    values_i0 = [r.params["i0"] for r in runs if r.params.get("i0") is not None]
    values_i0 = [float(v) for v in values_i0 if math.isfinite(float(v))]
    selected_i0 = None
    if baseline_i0 is not None:
        selected_i0 = float(baseline_i0)
    elif values_i0:
        selected_i0 = min(values_i0)
    if selected_i0 is not None:
        runs = [r for r in runs if _match_value(r.params.get("i0"), selected_i0)]

    return runs, {"f_Q": selected_fq, "i0": selected_i0}


def _format_value(value: float | None, fmt: str = "{:g}") -> str:
    if value is None or not math.isfinite(value):
        return "unknown"
    return fmt.format(value)


def _value_key(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), 8)


def _select_representatives(values: list[float | None], max_count: int) -> list[float | None]:
    if len(values) <= max_count:
        return list(values)
    indices = np.linspace(0, len(values) - 1, max_count, dtype=int)
    selected: list[float | None] = []
    seen = set()
    for idx in indices:
        val = values[idx]
        key = ("none" if val is None else round(float(val), 8))
        if key in seen:
            continue
        seen.add(key)
        selected.append(val)
    for val in values:
        if len(selected) >= max_count:
            break
        key = ("none" if val is None else round(float(val), 8))
        if key in seen:
            continue
        seen.add(key)
        selected.append(val)
    return selected


def _assign_colors(values: list[object]) -> dict[object, tuple]:
    cmap = plt.get_cmap("tab10" if len(values) <= 10 else "tab20")
    colors: dict[object, tuple] = {}
    for idx, value in enumerate(values):
        colors[value] = cmap(idx % cmap.N)
    return colors


def _match_from_list(value: float | None, candidates: Iterable[float | None]) -> float | None | object:
    if value is None:
        return None if None in candidates else _NO_MATCH
    for candidate in candidates:
        if candidate is None:
            continue
        if _match_value(value, candidate):
            return candidate
    return _NO_MATCH


def _clip_log(values: np.ndarray, floor: float) -> np.ndarray:
    return np.where(values > floor, values, floor)


def _determine_mass_initial(mass_budget: pd.DataFrame | None, run_name: str) -> float | None:
    if mass_budget is None or mass_budget.empty:
        _warn(f"mass_budget missing or empty for {run_name}")
        return None
    if "mass_initial" not in mass_budget.columns:
        _warn(f"mass_initial column missing for {run_name}")
        return None
    try:
        value = float(mass_budget["mass_initial"].iloc[0])
    except Exception:
        _warn(f"failed to parse mass_initial for {run_name}")
        return None
    if not math.isfinite(value) or value <= 0:
        _warn(f"invalid mass_initial for {run_name}: {value}")
        return None
    return value


def _select_baseline_run(runs: list[RunData]) -> RunData:
    runs_sorted = sorted(runs, key=_run_sort_key)
    t_vals = [r.params.get("T_M") for r in runs_sorted if r.params.get("T_M") is not None]
    e_vals = [r.params.get("epsilon_mix") for r in runs_sorted if r.params.get("epsilon_mix") is not None]
    tau_vals = [r.params.get("tau0") for r in runs_sorted if r.params.get("tau0") is not None]
    if t_vals and e_vals and tau_vals:
        target_t = max(t_vals)
        target_e = max(e_vals)
        target_tau = max(tau_vals)
        matches = [
            r
            for r in runs_sorted
            if _match_value(r.params.get("T_M"), target_t)
            and _match_value(r.params.get("epsilon_mix"), target_e)
            and _match_value(r.params.get("tau0"), target_tau)
        ]
        if matches:
            return matches[0]
    return runs_sorted[0]


def _select_comparisons(baseline: RunData, runs: list[RunData]) -> list[RunData]:
    selections = [baseline]
    selected_names = {baseline.name}
    runs_sorted = sorted(runs, key=_run_sort_key)
    base_eps = baseline.params.get("epsilon_mix")
    base_tau = baseline.params.get("tau0")
    base_t = baseline.params.get("T_M")

    if base_eps is not None and base_tau is not None:
        candidates = [
            r
            for r in runs_sorted
            if _match_value(r.params.get("epsilon_mix"), base_eps)
            and _match_value(r.params.get("tau0"), base_tau)
            and r.params.get("T_M") is not None
        ]
        if candidates:
            target = min(c.params["T_M"] for c in candidates if c.params.get("T_M") is not None)
            for run in candidates:
                if _match_value(run.params.get("T_M"), target) and run.name not in selected_names:
                    selections.append(run)
                    selected_names.add(run.name)
                    break

    if base_t is not None and base_eps is not None:
        candidates = [
            r
            for r in runs_sorted
            if _match_value(r.params.get("T_M"), base_t)
            and _match_value(r.params.get("epsilon_mix"), base_eps)
            and r.params.get("tau0") is not None
        ]
        if candidates:
            target = min(c.params["tau0"] for c in candidates if c.params.get("tau0") is not None)
            for run in candidates:
                if _match_value(run.params.get("tau0"), target) and run.name not in selected_names:
                    selections.append(run)
                    selected_names.add(run.name)
                    break

    return selections[:3]


def _prepare_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.6,
        }
    )


def _prepare_output_dirs(outdir: Path) -> dict[str, Path]:
    paths = {key: outdir / name for key, name in OUTPUT_SUBDIRS.items()}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _run_title(run: RunData) -> str:
    return (
        f"T_M={_format_value(run.params.get('T_M'))} K, "
        f"eps={_format_value(run.params.get('epsilon_mix'))}, "
        f"tau0={_format_value(run.params.get('tau0'))}, "
        f"i0={_format_value(run.params.get('i0'))}"
    )


def _plot_cumloss_single(run: RunData, outdir: Path) -> bool:
    y_vals = run.series["M_loss_cum"].to_numpy(dtype=float)
    use_fraction = run.mass_initial is not None
    if use_fraction and run.mass_initial:
        y_vals = y_vals / run.mass_initial
    else:
        _warn(f"mass_initial missing; using raw M_loss_cum for {run.name}")
    y_vals = _clip_log(y_vals, LOG_CLIP_FRACTION)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(run.series["t_year"], y_vals, color="C0", lw=1.5)
    ax.set_yscale("log")
    ax.set_xlabel("Time [yr]")
    if use_fraction:
        ax.set_ylabel("M_loss_cum / M_in0")
    else:
        ax.set_ylabel("M_loss_cum [M_Mars]")
    ax.set_title(_run_title(run))
    ax.grid(True, alpha=0.3, linewidth=0.6)
    fig.savefig(outdir / f"{run.name}.png", bbox_inches="tight")
    plt.close(fig)
    return True


def _plot_outflow_tau_cumloss_single(run: RunData, outdir: Path) -> bool:
    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(7.2, 7.8), sharex=True)
    ax_out, ax_tau, ax_cum = axes
    t_year = run.series["t_year"]

    out_vals = _clip_log(run.series["M_out_dot"].to_numpy(dtype=float), LOG_CLIP_OUTFLOW)
    ax_out.plot(t_year, out_vals, color="C0", lw=1.5, label=_label_for_run(run))
    ax_out.set_yscale("log")
    ax_out.set_ylabel("M_out_dot [M_Mars s$^{-1}$]")
    ax_out.legend(loc="upper right", frameon=False)

    ax_tau.plot(t_year, run.series["tau"], color="C0", lw=1.5)
    if run.tau_stop is not None:
        ax_tau.axhline(run.tau_stop, color="gray", linestyle="--", linewidth=1.0, alpha=0.6)
    ax_tau.set_ylabel("Optical depth tau")

    loss_vals = run.series["M_loss_cum"].to_numpy(dtype=float)
    use_fraction = run.mass_initial is not None
    if use_fraction and run.mass_initial:
        loss_vals = loss_vals / run.mass_initial
    else:
        _warn(f"mass_initial missing; using raw M_loss_cum for {run.name}")
    loss_vals = _clip_log(loss_vals, LOG_CLIP_FRACTION)
    ax_cum.plot(t_year, loss_vals, color="C0", lw=1.5)
    ax_cum.set_yscale("log")
    if use_fraction:
        ax_cum.set_ylabel("M_loss_cum / M_in0")
    else:
        ax_cum.set_ylabel("M_loss_cum [M_Mars]")
    ax_cum.set_xlabel("Time [yr]")

    fig.suptitle(_run_title(run))
    for ax in axes:
        ax.grid(True, alpha=0.3, linewidth=0.6)

    fig.savefig(outdir / f"{run.name}.png", bbox_inches="tight")
    plt.close(fig)
    return True


def _compute_heatmap_values(
    runs: Iterable[RunData],
) -> tuple[dict[str, float], float | None, float | None]:
    values: dict[str, float] = {}
    for run in runs:
        if run.mass_initial is None:
            _warn(f"mass_initial missing; skipping heatmap for {run.name}")
            continue
        loss_value = None
        if "M_loss" in run.summary:
            loss_value = _coerce_float(run.summary.get("M_loss"))
        if loss_value is None:
            loss_value = _coerce_float(run.series["M_loss_cum"].iloc[-1])
        if loss_value is None or not math.isfinite(loss_value):
            _warn(f"missing M_loss; skipping heatmap for {run.name}")
            continue
        values[run.name] = float(loss_value) / run.mass_initial
    if not values:
        return values, None, None
    finite_vals = [v for v in values.values() if math.isfinite(v)]
    if not finite_vals:
        return values, None, None
    return values, min(finite_vals), max(finite_vals)


def _plot_heatmap_single(
    run: RunData,
    outdir: Path,
    value: float,
    vmin: float,
    vmax: float,
) -> bool:
    grid = np.array([[value]], dtype=float)
    masked = np.ma.masked_invalid(grid)
    cmap = plt.get_cmap("cividis").copy()
    cmap.set_bad("white")
    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    mesh = ax.imshow(masked, origin="lower", aspect="auto", vmin=vmin, vmax=vmax, cmap=cmap)
    ax.set_xticks([0])
    ax.set_xticklabels([_format_value(run.params.get("tau0"))])
    ax.set_yticks([0])
    ax.set_yticklabels([_format_value(run.params.get("T_M"))])
    ax.set_xlabel("tau0")
    ax.set_ylabel("T_M [K]")
    ax.set_title(f"epsilon_mix={_format_value(run.params.get('epsilon_mix'))}")
    ax.grid(False)
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("M_loss / M_in0")
    fig.savefig(outdir / f"{run.name}.png", bbox_inches="tight")
    plt.close(fig)
    return True


def _plot_mass_budget_single(run: RunData, outdir: Path) -> bool:
    if run.mass_budget is None or run.mass_budget.empty:
        _warn(f"mass_budget missing for {run.name}")
        return False
    if "time" not in run.mass_budget.columns or "error_percent" not in run.mass_budget.columns:
        _warn(f"mass_budget missing time/error_percent for {run.name}")
        return False
    df = run.mass_budget.dropna(subset=["time", "error_percent"]).copy()
    if df.empty:
        _warn(f"mass_budget empty after filtering for {run.name}")
        return False
    df["t_year"] = df["time"] / SECONDS_PER_YEAR
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(df["t_year"], df["error_percent"], color="black", lw=1.2)
    ax.set_xlabel("Time [yr]")
    ax.set_ylabel("Mass budget error [%]")
    ax.set_title(_run_title(run))
    ax.grid(True, alpha=0.3, linewidth=0.6)
    fig.savefig(outdir / f"{run.name}.png", bbox_inches="tight")
    plt.close(fig)
    return True


def _tau_token(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9):
        return f"{int(round(value))}p0"
    text = f"{value:g}"
    if "." not in text:
        text = f"{text}.0"
    return text.replace(".", "p")


def _plot_cumloss_grid_for_tau0(runs: list[RunData], outdir: Path, tau0_value: float) -> bool:
    subset = [r for r in runs if _match_value(r.params.get("tau0"), tau0_value)]
    if not subset:
        _warn(f"no runs matched tau0={tau0_value} for cumloss grid")
        return False
    subset = sorted(subset, key=_run_sort_key)

    t_vals = sorted({r.params["T_M"] for r in subset if r.params.get("T_M") is not None})
    eps_vals = sorted(
        {r.params["epsilon_mix"] for r in subset if r.params.get("epsilon_mix") is not None}
    )
    if not t_vals or not eps_vals:
        _warn(f"missing T_M/epsilon_mix coverage for tau0={tau0_value}")
        return False

    all_have_mass = all(r.mass_initial is not None for r in subset)
    if not all_have_mass:
        _warn(f"mass_initial missing in some runs; grid tau0={tau0_value} uses raw M_loss_cum")

    fig, axes = plt.subplots(
        nrows=len(t_vals),
        ncols=len(eps_vals),
        figsize=(3.6 * len(eps_vals), 2.8 * len(t_vals)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    for i, t_val in enumerate(t_vals):
        for j, eps_val in enumerate(eps_vals):
            ax = axes[i][j]
            cell_runs = [
                r
                for r in subset
                if _match_value(r.params.get("T_M"), t_val)
                and _match_value(r.params.get("epsilon_mix"), eps_val)
            ]
            cell_runs = sorted(cell_runs, key=_run_sort_key)
            if cell_runs:
                run = cell_runs[0]
                y_vals = run.series["M_loss_cum"].to_numpy(dtype=float)
                if all_have_mass and run.mass_initial:
                    y_vals = y_vals / run.mass_initial
                y_vals = _clip_log(y_vals, LOG_CLIP_FRACTION)
                ax.plot(run.series["t_year"], y_vals, color="C0", lw=1.5)
            else:
                ax.text(
                    0.5,
                    0.5,
                    "missing",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="gray",
                )

            ax.set_title(f"T_M={_format_value(t_val)} K, eps={_format_value(eps_val)}")
            ax.set_yscale("log")
            ax.grid(True, alpha=0.3, linewidth=0.6)
            if i == len(t_vals) - 1:
                ax.set_xlabel("Time [yr]")
            if j == 0:
                if all_have_mass:
                    ax.set_ylabel("M_loss_cum / M_in0")
                else:
                    ax.set_ylabel("M_loss_cum [M_Mars]")

    fig.suptitle(f"Cumulative loss (tau0={_format_value(tau0_value)})", y=1.02)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"cumloss_grid_tau{_tau_token(tau0_value)}.png"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return True


def _plot_r1(
    runs: list[RunData],
    outdir: Path,
    max_lines: int,
) -> None:
    runs = [r for r in runs if r.params.get("T_M") is not None and r.params.get("epsilon_mix") is not None]
    if not runs:
        _warn("no runs with T_M and epsilon_mix for Figure R1")
        return
    t_vals = sorted({r.params["T_M"] for r in runs if r.params.get("T_M") is not None})
    eps_vals = sorted({r.params["epsilon_mix"] for r in runs if r.params.get("epsilon_mix") is not None})
    tau_vals = sorted({r.params["tau0"] for r in runs if r.params.get("tau0") is not None})
    if not tau_vals:
        tau_vals = [None]
    selected_tau = _select_representatives(tau_vals, max_lines)
    colors = _assign_colors(selected_tau)

    all_have_mass = all(r.mass_initial is not None for r in runs)
    if not all_have_mass:
        _warn("mass_initial missing in some runs; Figure R1 will use raw M_loss_cum")
    use_fraction = all_have_mass

    fig, axes = plt.subplots(
        nrows=len(t_vals),
        ncols=len(eps_vals),
        figsize=(3.6 * len(eps_vals), 2.8 * len(t_vals)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    for i, t_val in enumerate(t_vals):
        for j, eps_val in enumerate(eps_vals):
            ax = axes[i][j]
            subset = []
            for r in runs:
                if not _match_value(r.params.get("T_M"), t_val):
                    continue
                if not _match_value(r.params.get("epsilon_mix"), eps_val):
                    continue
                match = _match_from_list(r.params.get("tau0"), selected_tau)
                if match is _NO_MATCH:
                    continue
                subset.append(r)
            subset = sorted(subset, key=_run_sort_key)
            for run in subset:
                tau_val = _match_from_list(run.params.get("tau0"), selected_tau)
                color = colors.get(tau_val, "black")
                y_vals = run.series["M_loss_cum"].to_numpy(dtype=float)
                if use_fraction and run.mass_initial:
                    y_vals = y_vals / run.mass_initial
                y_vals = _clip_log(y_vals, LOG_CLIP_FRACTION)
                ax.plot(
                    run.series["t_year"],
                    y_vals,
                    color=color,
                    lw=1.5,
                )
            title = f"T_M={_format_value(t_val)} K, ε_mix={_format_value(eps_val)}"
            ax.set_title(title)
            ax.set_yscale("log")
            ax.grid(True, alpha=0.3, linewidth=0.6)
            if i == len(t_vals) - 1:
                ax.set_xlabel("Time [yr]")
            if j == 0:
                if use_fraction:
                    ax.set_ylabel("M_loss_cum / M_in0")
                else:
                    ax.set_ylabel("M_loss_cum [M_Mars]")

    legend_handles = []
    legend_labels = []
    for tau_val in selected_tau:
        label = f"tau0={_format_value(tau_val)}"
        legend_handles.append(Line2D([0], [0], color=colors[tau_val], lw=1.5))
        legend_labels.append(label)
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=False,
    )

    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(outdir / f"fig_R1_cumloss_grid.{ext}", bbox_inches="tight")
    plt.close(fig)


def _plot_r2(
    runs: list[RunData],
    outdir: Path,
) -> RunData | None:
    if not runs:
        _warn("no runs available for Figure R2")
        return None
    baseline = _select_baseline_run(runs)
    selections = _select_comparisons(baseline, runs)
    colors = _assign_colors([run.name for run in selections])

    all_have_mass = all(r.mass_initial is not None for r in selections)
    if not all_have_mass:
        _warn("mass_initial missing in representative runs; Figure R2 uses raw M_loss_cum")
    use_fraction = all_have_mass

    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(7.2, 7.8), sharex=True)
    ax_out, ax_tau, ax_cum = axes

    for run in selections:
        color = colors[run.name]
        t_year = run.series["t_year"]
        out_vals = _clip_log(run.series["M_out_dot"].to_numpy(dtype=float), LOG_CLIP_OUTFLOW)
        ax_out.plot(t_year, out_vals, color=color, lw=1.5, label=_label_for_run(run))

        ax_tau.plot(t_year, run.series["tau"], color=color, lw=1.5)

        loss_vals = run.series["M_loss_cum"].to_numpy(dtype=float)
        if use_fraction and run.mass_initial:
            loss_vals = loss_vals / run.mass_initial
        loss_vals = _clip_log(loss_vals, LOG_CLIP_FRACTION)
        ax_cum.plot(t_year, loss_vals, color=color, lw=1.5)

    ax_out.set_yscale("log")
    ax_out.set_ylabel("M_out_dot [M_Mars s$^{-1}$]")
    ax_out.legend(loc="upper right", frameon=False)

    ax_tau.set_ylabel("Optical depth tau")
    tau_stops = [r.tau_stop for r in selections if r.tau_stop is not None]
    if tau_stops:
        unique = sorted({round(float(v), 8) for v in tau_stops})
        for tau_stop in unique:
            ax_tau.axhline(tau_stop, color="gray", linestyle="--", linewidth=1.0, alpha=0.6)

    ax_cum.set_yscale("log")
    if use_fraction:
        ax_cum.set_ylabel("M_loss_cum / M_in0")
    else:
        ax_cum.set_ylabel("M_loss_cum [M_Mars]")
    ax_cum.set_xlabel("Time [yr]")

    for ax in axes:
        ax.grid(True, alpha=0.3, linewidth=0.6)

    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(outdir / f"fig_R2_outflow_tau_cumloss_representative.{ext}", bbox_inches="tight")
    plt.close(fig)
    return baseline


def _label_for_run(run: RunData) -> str:
    return (
        f"T_M={_format_value(run.params.get('T_M'))} K, "
        f"eps={_format_value(run.params.get('epsilon_mix'))}, "
        f"tau0={_format_value(run.params.get('tau0'))}"
    )


def _plot_r3(runs: list[RunData], outdir: Path) -> None:
    runs = [
        r
        for r in runs
        if r.params.get("T_M") is not None
        and r.params.get("tau0") is not None
        and r.params.get("epsilon_mix") is not None
    ]
    if not runs:
        _warn("no runs with T_M, tau0, epsilon_mix for Figure R3")
        return
    t_vals = sorted({r.params["T_M"] for r in runs if r.params.get("T_M") is not None})
    tau_vals = sorted({r.params["tau0"] for r in runs if r.params.get("tau0") is not None})
    eps_vals = sorted({r.params["epsilon_mix"] for r in runs if r.params.get("epsilon_mix") is not None})
    if not t_vals or not tau_vals or not eps_vals:
        _warn("insufficient parameter coverage for Figure R3")
        return

    t_index = {_value_key(value): idx for idx, value in enumerate(t_vals)}
    tau_index = {_value_key(value): idx for idx, value in enumerate(tau_vals)}

    grids = []
    for eps in eps_vals:
        grid = np.full((len(t_vals), len(tau_vals)), np.nan, dtype=float)
        for run in runs:
            if not _match_value(run.params.get("epsilon_mix"), eps):
                continue
            if run.mass_initial is None:
                _warn(f"mass_initial missing for heatmap run {run.name}")
                continue
            t_key = _value_key(run.params.get("T_M"))
            tau_key = _value_key(run.params.get("tau0"))
            if t_key is None or tau_key is None:
                continue
            t_idx = t_index.get(t_key)
            tau_idx = tau_index.get(tau_key)
            if t_idx is None or tau_idx is None:
                continue
            loss_value = None
            if "M_loss" in run.summary:
                loss_value = _coerce_float(run.summary.get("M_loss"))
            if loss_value is None:
                loss_value = _coerce_float(run.series["M_loss_cum"].iloc[-1])
            if loss_value is None:
                _warn(f"missing M_loss for heatmap run {run.name}")
                continue
            grid[t_idx, tau_idx] = loss_value / run.mass_initial
        grids.append(grid)

    flat_vals = np.concatenate([g.ravel() for g in grids])
    finite_vals = flat_vals[np.isfinite(flat_vals)]
    if finite_vals.size == 0:
        _warn("no finite values for Figure R3 heatmap")
        return
    vmin = float(finite_vals.min())
    vmax = float(finite_vals.max())
    cmap = plt.get_cmap("cividis").copy()
    cmap.set_bad("white")

    fig, axes = plt.subplots(
        nrows=1,
        ncols=len(eps_vals),
        figsize=(3.6 * len(eps_vals), 3.2),
        sharey=True,
        squeeze=False,
    )
    for idx, eps in enumerate(eps_vals):
        ax = axes[0][idx]
        grid = grids[idx]
        masked = np.ma.masked_invalid(grid)
        mesh = ax.imshow(
            masked,
            origin="lower",
            aspect="auto",
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
        )
        ax.set_title(f"epsilon_mix={_format_value(eps)}")
        ax.set_xticks(range(len(tau_vals)))
        ax.set_xticklabels([_format_value(v) for v in tau_vals], rotation=45, ha="right")
        if idx == 0:
            ax.set_yticks(range(len(t_vals)))
            ax.set_yticklabels([_format_value(v) for v in t_vals])
            ax.set_ylabel("T_M [K]")
        else:
            ax.set_yticks(range(len(t_vals)))
            ax.set_yticklabels([])
        ax.set_xlabel("tau0")
        ax.grid(False)

    cbar = fig.colorbar(mesh, ax=axes.ravel().tolist(), pad=0.02)
    cbar.set_label("M_loss / M_in0")

    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(outdir / f"fig_R3_final_cumloss_heatmap.{ext}", bbox_inches="tight")
    plt.close(fig)


def _plot_v1(baseline: RunData | None, outdir: Path) -> None:
    if baseline is None:
        _warn("no baseline run for Figure V1")
        return
    if baseline.mass_budget is None or baseline.mass_budget.empty:
        _warn("mass_budget missing for Figure V1")
        return
    if "time" not in baseline.mass_budget.columns or "error_percent" not in baseline.mass_budget.columns:
        _warn("mass_budget missing time/error_percent for Figure V1")
        return
    df = baseline.mass_budget.copy()
    df = df.dropna(subset=["time", "error_percent"])
    if df.empty:
        _warn("mass_budget empty after filtering for Figure V1")
        return
    df["t_year"] = df["time"] / SECONDS_PER_YEAR
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.plot(df["t_year"], df["error_percent"], color="black", lw=1.2)
    ax.set_xlabel("Time [yr]")
    ax.set_ylabel("Mass budget error [%]")
    ax.grid(True, alpha=0.3, linewidth=0.6)
    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(outdir / f"fig_V1_mass_budget_error_example.{ext}", bbox_inches="tight")
    plt.close(fig)


def _load_runs(run_root: Path) -> list[RunData]:
    runs: list[RunData] = []
    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    for run_dir in run_dirs:
        series = _load_series(run_dir)
        if series is None:
            _warn(f"skip run (missing series): {run_dir.name}")
            continue
        summary = _read_json(run_dir / "summary.json")
        mass_budget = _read_csv(run_dir / "checks" / "mass_budget.csv")
        config = _read_json(run_dir / "run_config.json")
        params, tau_stop = _extract_params(run_dir, config)
        mass_initial = _determine_mass_initial(mass_budget, run_dir.name)
        runs.append(
            RunData(
                path=run_dir,
                name=run_dir.name,
                params=params,
                series=series,
                summary=summary,
                mass_budget=mass_budget,
                mass_initial=mass_initial,
                tau_stop=tau_stop,
            )
        )
    return runs


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.run_root.exists():
        print(f"[error] run root not found: {args.run_root}", file=sys.stderr)
        return 1
    _prepare_style()

    runs = _load_runs(args.run_root)
    total = len([p for p in args.run_root.iterdir() if p.is_dir()])
    _info(f"run directories: {total}, loaded: {len(runs)}, skipped: {total - len(runs)}")
    if not runs:
        print("[error] no valid runs found", file=sys.stderr)
        return 1

    runs, baseline_values = _select_baseline(runs, args.baseline_i0, args.baseline_fq)
    _info(
        "baseline filter: f_Q*="
        f"{_format_value(baseline_values.get('f_Q'))}, "
        f"i0={_format_value(baseline_values.get('i0'))}, "
        f"remaining={len(runs)}"
    )
    if not runs:
        print("[error] baseline filter resulted in 0 runs", file=sys.stderr)
        return 1

    out_dirs = _prepare_output_dirs(args.outdir)
    runs_sorted = sorted(runs, key=_run_sort_key)
    heatmap_values, vmin, vmax = _compute_heatmap_values(runs_sorted)
    counts = {"cumloss": 0, "outflow": 0, "heatmap": 0, "mass_budget": 0}

    for run in runs_sorted:
        if _plot_cumloss_single(run, out_dirs["cumloss"]):
            counts["cumloss"] += 1
        if _plot_outflow_tau_cumloss_single(run, out_dirs["outflow"]):
            counts["outflow"] += 1
        if (
            run.name in heatmap_values
            and vmin is not None
            and vmax is not None
            and math.isfinite(vmin)
            and math.isfinite(vmax)
        ):
            if _plot_heatmap_single(run, out_dirs["heatmap"], heatmap_values[run.name], vmin, vmax):
                counts["heatmap"] += 1
        if _plot_mass_budget_single(run, out_dirs["mass_budget"]):
            counts["mass_budget"] += 1

    _info(
        "saved pngs: cumloss="
        f"{counts['cumloss']}, outflow={counts['outflow']}, "
        f"heatmap={counts['heatmap']}, mass_budget={counts['mass_budget']}"
    )

    tau0_values = sorted(
        {
            round(float(r.params["tau0"]), 8)
            for r in runs_sorted
            if r.params.get("tau0") is not None and math.isfinite(float(r.params["tau0"]))
        }
    )
    for tau0 in tau0_values:
        _plot_cumloss_grid_for_tau0(runs_sorted, out_dirs["cumloss"], float(tau0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
