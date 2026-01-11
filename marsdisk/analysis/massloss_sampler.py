"""Sampling helper for one-orbit mass-loss fractions in the gas-poor regime.

The routine in this module wraps :func:`marsdisk.run.run_zero_d` so that a
single (r/R_M, T_M) point can be evaluated while honouring the sequential
coupling order (⟨Q_pr⟩ → a_blow → PSD drift → shielding → surface sinks).
It enforces the table-based ⟨Q_pr⟩ lookup, disables gas drag and keeps the
minimum size floor at ``max(s_min_config, a_blow)`` throughout the orbit.
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config_utils, constants
from ..run import load_config, run_zero_d
from ..schema import Config, Radiation
from ..physics import radiation

__all__ = ["sample_mass_loss_one_orbit"]


def _resolve_table_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        parquet_path = path.with_suffix(".parquet")
        if parquet_path.exists():
            if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
                return parquet_path
    elif suffix in {".parquet", ".pq"} and not path.exists():
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
    return path


def _prepare_config(
    base_cfg: Config,
    *,
    r_rm: float,
    T_M: float,
    qpr_table_path: Path,
    dt_over_t_blow_max: float,
    sinks_mode: str,
    enable_sublimation: Optional[bool],
    enable_gas_drag: bool,
) -> Config:
    """Return a deep-copied configuration tailored to a single sample."""

    work = base_cfg.model_copy(deep=True)

    work.geometry.mode = "0D"
    config_utils.ensure_disk_geometry(work, r_rm=float(r_rm))

    if work.radiation is None:
        work.radiation = Radiation(TM_K=float(T_M), qpr_table_path=qpr_table_path)
    else:
        work.radiation.TM_K = float(T_M)
        work.radiation.qpr_table_path = qpr_table_path
    work.radiation.Q_pr = None

    work.sinks.mode = sinks_mode
    if enable_sublimation is None:
        work.sinks.enable_sublimation = sinks_mode == "sublimation"
    else:
        work.sinks.enable_sublimation = bool(enable_sublimation)
    work.sinks.enable_gas_drag = bool(enable_gas_drag)

    work.numerics.t_end_orbits = 1.0
    work.numerics.t_end_years = None
    work.numerics.dt_init = "auto"
    work.numerics.eval_per_step = True
    work.numerics.orbit_rollup = True
    work.numerics.dt_over_t_blow_max = float(dt_over_t_blow_max)

    work.io.outdir = Path(".")  # placeholder overwritten at runtime

    if hasattr(work.sizes, "evolve_min_size"):
        work.sizes.evolve_min_size = False
    if getattr(work.sizes, "s_min", None) is not None:
        work.sizes.s_min = float(work.sizes.s_min)

    return work


def _percentile(values: Iterable[float], q: float) -> float:
    if isinstance(values, np.ndarray):
        data = values.astype(float, copy=False)
    else:
        data = np.asarray(list(values), dtype=float)
    if data.size == 0:
        return float("nan")
    finite = np.isfinite(data)
    if not finite.any():
        return float("nan")
    return float(np.nanpercentile(data[finite], q))


def _median_dt_ratio(series: pd.Series) -> float:
    if series is None:
        return float("nan")
    return _percentile(series.to_numpy(dtype=float), 50.0)


def _p90_dt_ratio(series: pd.Series) -> float:
    if series is None:
        return float("nan")
    return _percentile(series.to_numpy(dtype=float), 90.0)


def _float_or_nan(payload: Dict[str, Any], key: str) -> float:
    value = payload.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def sample_mass_loss_one_orbit(
    r_RM: float,
    T_M: float,
    base_yaml: Path | str,
    qpr_table: Path | str,
    *,
    dt_over_t_blow_max: float = 0.1,
    sinks_mode: str = "sublimation",
    enable_sublimation: Optional[bool] = None,
    enable_gas_drag: bool = False,
    overrides: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Execute a single-orbit 0D run and return aggregated mass-loss metrics.

    Parameters
    ----------
    r_RM:
        Orbital radius expressed in Mars radii.
    T_M:
        Mars-facing temperature in Kelvin.
    base_yaml:
        Path to the base YAML configuration describing the reference setup.
    qpr_table:
        Path to the mandatory ⟨Q_pr⟩ lookup table.
    dt_over_t_blow_max:
        Safety cap for ``dt / t_blow``; defaults to 0.1 per user specification.

    Returns
    -------
    dict
        Dictionary with mass-loss fractions, cumulative losses and provenance.
    """

    base_path = Path(base_yaml)
    if not base_path.exists():
        raise FileNotFoundError(f"Base YAML configuration not found: {base_path}")
    table_path = _resolve_table_path(Path(qpr_table))
    if not table_path.exists():
        raise FileNotFoundError(f"⟨Q_pr⟩ table not found: {table_path}")

    base_cfg = load_config(base_path, overrides=overrides)
    case_cfg = _prepare_config(
        base_cfg,
        r_rm=float(r_RM),
        T_M=float(T_M),
        qpr_table_path=table_path,
        dt_over_t_blow_max=float(dt_over_t_blow_max),
        sinks_mode=str(sinks_mode),
        enable_sublimation=enable_sublimation,
        enable_gas_drag=bool(enable_gas_drag),
    )

    # Ensure the lookup table is active inside this process.
    radiation.load_qpr_table(table_path)

    with tempfile.TemporaryDirectory(prefix="massloss_sampler_") as tmp:
        outdir = Path(tmp)
        case_cfg.io.outdir = outdir
        run_zero_d(case_cfg)

        summary_path = outdir / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"summary.json missing in {outdir}")
        with summary_path.open("r", encoding="utf-8") as fh:
            summary = json.load(fh)

        series_path = outdir / "series" / "run.parquet"
        if not series_path.exists():
            raise FileNotFoundError(f"run.parquet missing in {outdir}")
        df = pd.read_parquet(series_path)

        mass_out = summary.get("M_out_cum")
        mass_sink = summary.get("M_sink_cum", summary.get("M_loss_from_sinks"))
        if mass_out is None or mass_sink is None:
            last = df.iloc[-1]
            mass_out = last.get("mass_lost_by_blowout", math.nan)
            mass_sink = last.get("mass_lost_by_sinks", math.nan)
        mass_out = float(mass_out)
        mass_sink = float(mass_sink)

        total_loss = mass_out + mass_sink
        M0 = float(case_cfg.initial.mass_total)
        f_loss = total_loss / M0 if M0 > 0.0 else float("nan")
        denominator = mass_out + mass_sink
        blow_fraction = mass_out / denominator if denominator > 0.0 else float("nan")

        beta_config = _float_or_nan(summary, "beta_at_smin_config")
        beta_effective = _float_or_nan(summary, "beta_at_smin_effective")
        dt_ratio_median = _median_dt_ratio(df.get("dt_over_t_blow"))

        qpr_table_path = summary.get("qpr_table_path") or str(table_path)
        if not qpr_table_path:
            raise RuntimeError(
                "Run completed without recording qpr_table_path; analytic fallback would violate requirements."
            )

        dt_ratio_median = _median_dt_ratio(df.get("dt_over_t_blow"))
        dt_ratio_p90 = _p90_dt_ratio(df.get("dt_over_t_blow"))
        steps_per_orbit = int(df.shape[0])
        time_grid = summary.get("time_grid") or {}
        if isinstance(time_grid, dict):
            n_steps_recorded = time_grid.get("n_steps")
            if isinstance(n_steps_recorded, (int, float)) and n_steps_recorded > 0:
                steps_per_orbit = int(n_steps_recorded)

        mass_budget_path = outdir / "checks" / "mass_budget.csv"
        parquet_path = mass_budget_path.with_suffix(".parquet")
        if parquet_path.exists():
            if not mass_budget_path.exists() or parquet_path.stat().st_mtime >= mass_budget_path.stat().st_mtime:
                mass_budget_path = parquet_path
        mass_budget_max_error = float("nan")
        if mass_budget_path.exists():
            if mass_budget_path.suffix == ".parquet":
                mb_df = pd.read_parquet(mass_budget_path)
            else:
                mb_df = pd.read_csv(mass_budget_path)
            if "error_percent" in mb_df.columns:
                mass_budget_max_error = float(np.nanmax(np.abs(mb_df["error_percent"].to_numpy(dtype=float))))

        sink_fraction = float("nan")
        if np.isfinite(blow_fraction):
            sink_fraction = float(max(0.0, min(1.0, 1.0 - blow_fraction)))

        dt_requirement_pass = (
            bool(dt_ratio_median <= 0.05) if np.isfinite(dt_ratio_median) else np.nan
        )

    result: Dict[str, Any] = {
        "r_RM": float(r_RM),
        "T_M": float(T_M),
        "r_over_RM": float(r_RM),
        "TM_K": float(T_M),
        "M_out_cum": mass_out,
        "M_sink_cum": mass_sink,
        "M_loss_cum": total_loss,
        "M_init": M0,
        "mass_loss_frac_per_orbit": f_loss,
            "blowout_fraction": blow_fraction if np.isfinite(blow_fraction) else float("nan"),
            "sink_fraction": sink_fraction,
            "beta_at_smin_config": beta_config,
            "beta_at_smin_effective": beta_effective,
            "dt_over_t_blow_median": dt_ratio_median,
            "dt_over_t_blow_p90": dt_ratio_p90,
            "steps_per_orbit": steps_per_orbit,
            "qpr_table_path": str(qpr_table_path),
            "Q_pr_used": _float_or_nan(summary, "Q_pr_used"),
            "Q_pr_blow": _float_or_nan(summary, "Q_pr_blow"),
            "case_status": summary.get("case_status"),
            "orbits_completed": summary.get("orbits_completed"),
            "dt_nominal_s": summary.get("time_grid", {}).get("dt_nominal_s"),
            "dt_step_s": summary.get("time_grid", {}).get("dt_step_s"),
            "mass_budget_max_error_percent": mass_budget_max_error,
        "dt_over_t_blow_requirement_pass": dt_requirement_pass,
        "sinks_mode": str(sinks_mode),
    }

    return result
