"""
Utility to generate diagnostic figures from existing marsdisk simulation outputs.

The script produces:
1. A regime map heatmap for Map-1 sweeps.
2. Size-wise contribution curves for selected single runs.
3. Mass-budget timelines for the same runs.

No new simulations are launched; the tool only reads artefacts already on disk.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from ruamel.yaml import YAML  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover - safety net
        raise RuntimeError("Failed to import ruamel.yaml or PyYAML") from exc
    else:  # pragma: no cover - simple wrapper
        class YAML:  # minimal wrapper exposing load
            @staticmethod
            def load(stream):
                return yaml.safe_load(stream)


try:
    from marsdisk.physics import psd as psd_module
except Exception as exc:  # pragma: no cover - repository import required
    raise RuntimeError("Could not import marsdisk.physics.psd; run from repository root") from exc


# --------------------------------------------------------------------------- #
# Utility helpers


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> Mapping[str, object]:
    yaml_loader = YAML()
    with path.open("r", encoding="utf-8") as fh:
        return yaml_loader.load(fh)


def resolve_config_for_run(run_dir: Path, config_dir: Path) -> Path:
    """Infer the configuration file associated with a run directory."""

    run_config_path = run_dir / "run_config.json"
    if run_config_path.exists():
        try:
            with run_config_path.open("r", encoding="utf-8") as fh:
                run_cfg = json.load(fh)
            candidate = run_cfg.get("run_inputs", {}).get("input_config_path")
            if candidate:
                candidate_path = Path(candidate)
                if not candidate_path.is_absolute():
                    candidate_path = (run_dir / candidate).resolve()
                if candidate_path.exists():
                    return candidate_path
        except Exception:  # pragma: no cover - provenance guard
            pass

    base = run_dir.name
    for suffix in (".yml", ".yaml"):
        candidate = (config_dir / f"{base}{suffix}").resolve()
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not resolve configuration file for run '{run_dir}'. Tried run_config.json provenance and {config_dir}."
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path)


def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - detailed diagnostics
        raise RuntimeError(f"Failed to read parquet: {path}") from exc


def select_axes(df: pd.DataFrame) -> Tuple[str, str]:
    """Infer the x/y axes for the sweep heatmap."""

    preferred_pairs = [
        ("param_x_value", "param_y_value"),
        ("r", "T_M"),
        ("geometry.r", "temps.T_M"),
        ("geometry.r", "T_M"),
        ("r", "temps.T_M"),
    ]
    for a, b in preferred_pairs:
        if a in df.columns and b in df.columns:
            return a, b

    ignore = {"map_id", "case_id", "order", "run_status", "case_status", "partition_index", "partition_count"}
    numeric_cols = [c for c in df.columns if c not in ignore and pd.api.types.is_numeric_dtype(df[c])]
    if len(numeric_cols) < 2:
        raise RuntimeError("Could not infer sweep axes (need at least two numeric columns)")
    numeric_cols.sort(key=lambda c: df[c].nunique(dropna=True), reverse=True)
    return numeric_cols[0], numeric_cols[1]


def pick_metric(df: pd.DataFrame) -> str:
    if "beta_ratio" in df.columns:
        return "beta_ratio"
    for key in ("total_mass_lost_Mmars", "blowout_to_supply_ratio"):
        if key in df.columns:
            return key
    patterns = [r"^beta_at_smin", r"_Mmars$", r"_mass$", r"_ratio$"]
    for pattern in patterns:
        regex = re.compile(pattern)
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]) and regex.search(col):
                return col
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise RuntimeError("No numeric metric columns found for heatmap")
    return numeric_cols[-1]


def _success_mask(df: pd.DataFrame) -> pd.Series:
    run_col = df.get("run_status")
    case_col = df.get("case_status")
    run_ok = run_col.isin({"success", "cached"}) if run_col is not None else True
    if isinstance(run_ok, bool):
        run_ok = pd.Series([run_ok] * len(df), index=df.index)
    case_ok = case_col.notna() & ~case_col.astype(str).str.lower().isin({"failed", "error"}) if case_col is not None else True
    if isinstance(case_ok, bool):
        case_ok = pd.Series([case_ok] * len(df), index=df.index)
    return run_ok & case_ok


def plot_regime_map(csv_path: Path, out_path: Path, metric: Optional[str] = None) -> None:
    df = read_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"No rows in sweep CSV ({csv_path})")

    if {"beta_at_smin_effective", "beta_threshold"}.issubset(df.columns):
        with np.errstate(divide="ignore", invalid="ignore"):
            df["beta_ratio"] = df["beta_at_smin_effective"] / df["beta_threshold"]

    ax_y, ax_x = select_axes(df)
    metric_candidate = (metric or "").strip()
    if metric_candidate and metric_candidate in df.columns:
        metric_col = metric_candidate
    else:
        if metric_candidate:
            warnings.warn(
                f"Requested metric '{metric_candidate}' not present in sweep, falling back to automatic selection",
                RuntimeWarning,
            )
        metric_col = pick_metric(df)
    mask = _success_mask(df)
    ok = df.loc[mask].copy()
    if ok.empty:
        warnings.warn("No successful sweep rows found; plotting all rows", RuntimeWarning)
        ok = df.copy()

    pivot = ok.pivot_table(index=ax_y, columns=ax_x, values=metric_col, aggfunc="mean")
    pivot = pivot.sort_index().sort_index(axis=1)
    if pivot.empty:
        raise RuntimeError("Heatmap pivot table is empty; cannot plot regime map")

    y_vals = pivot.index.to_numpy(dtype=float)
    x_vals = pivot.columns.to_numpy(dtype=float)
    data = pivot.to_numpy()

    fig, ax = plt.subplots(figsize=(8.0, 5.5), dpi=200)
    im = ax.imshow(
        data,
        origin="lower",
        aspect="auto",
        extent=[x_vals.min(), x_vals.max(), y_vals.min(), y_vals.max()],
    )
    cbar = fig.colorbar(im, ax=ax)
    xlabel = df.get("param_x_name", pd.Series([ax_x])).iloc[0] if "param_x_name" in df.columns else ax_x
    ylabel = df.get("param_y_name", pd.Series([ax_y])).iloc[0] if "param_y_name" in df.columns else ax_y
    ax.set_xlabel(str(xlabel))
    ax.set_ylabel(str(ylabel))
    cbar_label = "β / β_threshold" if metric_col == "beta_ratio" else metric_col
    cbar.set_label(cbar_label)
    ax.set_title(f"Regime map (Map-1) – {cbar_label}")

    contour_artist = None
    if metric_col == "beta_ratio":
        try:
            x_grid, y_grid = np.meshgrid(x_vals, y_vals)
            contour = ax.contour(
                x_grid,
                y_grid,
                data,
                levels=[1.0],
                colors="white",
                linewidths=1.2,
            )
            if contour.collections:
                contour.collections[0].set_label("β_ratio = 1.0")
                contour_artist = contour.collections[0]
        except Exception:  # pragma: no cover - plotting guard
            contour_artist = None

    failures = df.loc[~mask]
    legend_handles: List[Any] = []
    legend_labels: List[str] = []
    if contour_artist is not None:
        legend_handles.append(contour_artist)
        legend_labels.append("β_ratio = 1.0")
    if not failures.empty:
        scatter = ax.scatter(
            failures[ax_x],
            failures[ax_y],
            marker="x",
            color="k",
            s=20,
            label="failed/cached",
        )
        legend_handles.append(scatter)
        legend_labels.append("failed/cached")
    if legend_handles:
        ax.legend(legend_handles, legend_labels, loc="best")

    ensure_dir(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Size contribution plotting


_SIZE_PATTERN = re.compile(
    r"(?P<prefix>dSigma_dt_[A-Za-z]+|Sigma|mass|flux)[^0-9]*"
    r"(?:bin_)?(?P<value>[0-9]+(?:\.[0-9]+)?)"
    r"(?P<unit>nm|um|µm|mm|cm|m)?$"
)


def _unit_scale(unit: Optional[str]) -> float:
    if not unit:
        return 1.0
    unit = unit.replace("µ", "u")
    return {
        "nm": 1e-9,
        "um": 1e-6,
        "u m": 1e-6,
        "mm": 1e-3,
        "cm": 1e-2,
        "m": 1.0,
    }.get(unit, 1.0)


def _extract_size_columns(columns: Iterable[str]) -> List[Tuple[str, str, float]]:
    results: List[Tuple[str, str, float]] = []
    for col in columns:
        match = _SIZE_PATTERN.search(col)
        if not match:
            continue
        value = float(match.group("value"))
        scale = _unit_scale(match.group("unit"))
        prefix = match.group("prefix")
        results.append((col, prefix, value * scale))
    return results


@dataclass
class PSDInfo:
    sizes_m: np.ndarray
    widths_m: np.ndarray
    number_density: np.ndarray


def _load_psd_from_config(config_path: Path, s_min_dynamic: float, rho: float) -> PSDInfo:
    cfg = load_yaml(config_path)
    sizes_cfg = cfg.get("sizes")
    if not isinstance(sizes_cfg, Mapping):
        raise RuntimeError(f"'sizes' section missing in config: {config_path}")
    s_min = float(sizes_cfg.get("s_min", s_min_dynamic))
    s_max = float(sizes_cfg.get("s_max", 3.0))
    n_bins = int(sizes_cfg.get("n_bins", 40))
    s_min = max(s_min, s_min_dynamic)

    psd_cfg = cfg.get("psd", {})
    alpha = float(psd_cfg.get("alpha", 1.83))
    wavy_strength = float(psd_cfg.get("wavy_strength", 0.0))
    psd_state = psd_module.update_psd_state(
        s_min=s_min,
        s_max=s_max,
        alpha=alpha,
        wavy_strength=wavy_strength,
        n_bins=n_bins,
        rho=rho,
    )
    return PSDInfo(
        sizes_m=np.asarray(psd_state["sizes"], dtype=float),
        widths_m=np.asarray(psd_state["widths"], dtype=float),
        number_density=np.asarray(psd_state["number"], dtype=float),
    )


def _compute_mass_fractions(psd_info: PSDInfo, rho: float) -> Tuple[np.ndarray, np.ndarray]:
    sizes = psd_info.sizes_m
    widths = psd_info.widths_m
    number = psd_info.number_density
    masses = (4.0 / 3.0) * math.pi * rho * sizes**3 * number * widths
    total = np.sum(masses)
    if not math.isfinite(total) or total <= 0.0:
        raise RuntimeError("Computed PSD mass is non-positive; cannot form fractions")
    fractions = masses / total
    return sizes, fractions


def _size_contribution_lines(
    df_series: pd.DataFrame,
    config_path: Path,
    label: str,
    summary_path: Path,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], Dict[str, float]]:
    final = df_series.tail(1).iloc[0]
    rho = float(final.get("rho_used", np.nan))
    if not math.isfinite(rho):
        if summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as fh:
                summary = json.load(fh)
            rho = float(summary.get("rho_used", 3000.0))
        else:
            rho = 3000.0
    s_min_effective = float(final.get("s_min_effective", final.get("s_min", 1e-6)))

    size_columns = _extract_size_columns(df_series.columns)
    contributions: Dict[str, np.ndarray] = {}
    metadata: Dict[str, float] = {}
    size_axis: np.ndarray

    if size_columns:
        # direct extraction path
        grouped: Dict[str, List[Tuple[float, np.ndarray]]] = {}
        for col, prefix, size in size_columns:
            values = df_series[col].to_numpy(dtype=float)
            label = prefix.replace("dSigma_dt_", "")
            grouped.setdefault(label, []).append((size, values))
        contributions_last: Dict[str, np.ndarray] = {}
        size_axis: Optional[np.ndarray] = None
        for label_key, items in grouped.items():
            items_sorted = sorted(items, key=lambda item: item[0])
            sizes = np.array([it[0] for it in items_sorted], dtype=float)
            values = np.array([it[1][-1] for it in items_sorted], dtype=float)
            contributions_last[label_key] = values
            if size_axis is None:
                size_axis = sizes
            metadata[f"{label_key}_flux_total"] = float(np.nansum(values))
        contributions.update(contributions_last)
        if size_axis is None:
            raise RuntimeError("Failed to construct size axis from resolved columns")
        size_axis = size_axis.astype(float)
    else:
        # fallback: use PSD fractions to distribute the fluxes
        psd_info = _load_psd_from_config(config_path, s_min_effective, rho)
        sizes, fractions = _compute_mass_fractions(psd_info, rho)
        blowout_flux = max(float(final.get("dSigma_dt_blowout", 0.0)), 0.0)
        sink_flux = max(float(final.get("dSigma_dt_sinks", 0.0)), 0.0)
        size_axis = sizes
        contributions["blowout"] = fractions * blowout_flux
        metadata["blowout_flux_total"] = blowout_flux
        if sink_flux > 0.0:
            contributions["sinks"] = fractions * sink_flux
        metadata["sinks_flux_total"] = sink_flux

    return size_axis, contributions, metadata


def plot_contrib_by_size(
    run_dir: Path,
    config_path: Path,
    out_path: Path,
    summary_path: Path,
    caption_note: Optional[str] = None,
) -> None:
    series_path = run_dir / "series" / "run.parquet"
    df_series = read_parquet(series_path)
    size_axis, contributions, metadata = _size_contribution_lines(df_series, config_path, run_dir.name, summary_path)

    legend_title: Optional[str] = None
    if summary_path.exists():
        try:
            with summary_path.open("r", encoding="utf-8") as fh:
                summary_data = json.load(fh)
            if isinstance(summary_data, dict):
                table_path = summary_data.get("qpr_table_path")
                qpr_used = summary_data.get("Q_pr_used")
                if table_path:
                    if isinstance(qpr_used, (int, float)) and math.isfinite(qpr_used):
                        legend_title = f"Q_pr(table) ≈ {qpr_used:.2f}"
                    else:
                        legend_title = "Q_pr(table)"
        except Exception:  # pragma: no cover - diagnostic context only
            legend_title = None

    if not contributions:
        raise RuntimeError(f"No size-resolved contributions could be derived for {run_dir}")

    fig, ax = plt.subplots(figsize=(7.5, 5.0), dpi=200)
    plotted = False
    for label, values in contributions.items():
        values = np.asarray(values, dtype=float)
        if np.all(~np.isfinite(values)) or np.all(values <= 0.0):
            continue
        positive = values.copy()
        positive[positive <= 0.0] = np.nan
        ax.plot(size_axis, positive, marker="o", label=f"{label} (total={metadata.get(label + '_flux_total', float('nan')):.2e})")
        plotted = True

    if not plotted:
        ax.plot(size_axis, np.full_like(size_axis, np.nan), label="no positive flux")

    ax.set_xscale("log")
    ax.set_xlabel("particle size [m]")
    ax.set_yscale("log")
    ax.set_ylabel("flux proxy [kg m$^{-2}$ s$^{-1}$]")
    ax.set_title(f"Size-wise contribution ({run_dir.name})")
    legend_kwargs = {"title": legend_title} if legend_title else {}
    ax.legend(**legend_kwargs)
    if caption_note:
        ax.text(0.02, 0.92, caption_note, transform=ax.transAxes)

    ensure_dir(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Mass budget timeline


def _merge_mass_budget(run_dir: Path) -> pd.DataFrame:
    budget_path = run_dir / "checks" / "mass_budget.csv"
    series_path = run_dir / "series" / "run.parquet"
    df_budget = read_csv(budget_path)
    df_series = read_parquet(series_path)
    if "time" not in df_budget.columns:
        raise RuntimeError(f"'time' column missing in {budget_path}")
    merged = pd.merge(df_budget, df_series[["time", "mass_total_bins", "mass_lost_by_blowout", "mass_lost_by_sinks"]], on="time", how="left")
    merged.sort_values("time", inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged


def plot_mass_budget(run_dir: Path, out_path: Path) -> None:
    df = _merge_mass_budget(run_dir)
    t = df["time"].to_numpy(dtype=float)
    mass_initial = float(df["mass_initial"].iloc[0])
    remaining = df["mass_total_bins"].to_numpy(dtype=float)
    lost_total = df["mass_lost"].to_numpy(dtype=float)
    lost_blow = df["mass_lost_by_blowout"].to_numpy(dtype=float)
    lost_sinks = df["mass_lost_by_sinks"].to_numpy(dtype=float)
    supplied = remaining + lost_blow + lost_sinks - mass_initial
    residual = df["error_percent"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(7.5, 5.0), dpi=200)
    ax.plot(t, remaining, label="mass in system")
    ax.plot(t, lost_blow, label="cumulative blowout loss")
    ax.plot(t, lost_sinks, label="cumulative sink loss")
    ax.plot(t, lost_blow + lost_sinks, label="total loss")
    ax.plot(t, supplied, label="cumulative supply")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("mass [M_Mars]")
    ax.set_title(f"Mass budget timeline ({run_dir.name})")
    ax.legend(loc="best")
    if residual.size:
        ax.text(0.02, 0.05, f"residual ≈ {residual[-1]:.3f} %", transform=ax.transAxes)
    ensure_dir(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main orchestration


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate marsdisk diagnostic figures")
    parser.add_argument(
        "--map1",
        type=Path,
        default=None,
        help="Path to Map-1 sweep CSV (e.g., simulation_results/03_inner_disk_sweep/map1/map1.csv)",
    )
    parser.add_argument(
        "--map1-output",
        type=Path,
        default=None,
        help="Destination path for the regime map PNG (defaults near the CSV)",
    )
    parser.add_argument(
        "--map1-metric",
        type=str,
        default="beta_ratio",
        help="Metric column to visualise in the regime map",
    )
    parser.add_argument(
        "--single-run",
        dest="single_runs",
        action="append",
        type=Path,
        default=None,
        help="Run directory to plot (can be supplied multiple times)",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("simulation_results/_configs"),
        help="Directory containing run configuration YAML files",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    if args.map1 is not None:
        map_csv = Path(args.map1)
        if not map_csv.exists():
            raise FileNotFoundError(f"Map-1 CSV not found: {map_csv}")
        map_output = Path(args.map1_output) if args.map1_output is not None else map_csv.parent.parent / "fig_map1_regime.png"
        plot_regime_map(
            csv_path=map_csv,
            out_path=map_output,
            metric=args.map1_metric,
        )

    run_dirs = args.single_runs or []
    config_dir = Path(args.config_dir)
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        if not run_path.exists():
            raise FileNotFoundError(f"Run directory not found: {run_path}")
        config_path = resolve_config_for_run(run_path, config_dir)
        summary_path = run_path / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"summary.json missing for run: {run_path}")
        plot_contrib_by_size(
            run_dir=run_path,
            config_path=config_path,
            out_path=run_path / "fig_contrib_by_size.png",
            summary_path=summary_path,
        )
        plot_mass_budget(
            run_dir=run_path,
            out_path=run_path / "fig_mass_budget_timeline.png",
        )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
