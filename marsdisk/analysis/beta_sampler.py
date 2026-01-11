"""Sampling utilities for β(r, T, t) maps over a single orbital period.

This module wires together the existing zero-dimensional runner so that the
sequential coupling loop (Q_pr → β → surface sinks) can be evaluated on a grid
of orbital radii and Mars-facing temperatures.  The implementation honours the
physics constraints requested by the user:

* Planck-averaged ⟨Q_pr⟩ values are always obtained from the supplied table via
  :func:`marsdisk.physics.radiation.qpr_lookup`.
* The effective minimum particle size is clamped to ``max(s_min_config, a_blow)``
  at every step; sublimation-driven erosion never lowers this floor.
* Gas drag sinks remain disabled by default to stay within the gas-poor regime.
* Each time-step re-evaluates ⟨Q_pr⟩, the blow-out size and the surface sinks,
  matching the sequential coupling order of :mod:`marsdisk.run`.

The main entry point :func:`sample_beta_over_orbit` returns structured grids
that can be fed directly into post-processing pipelines (e.g. movie rendering).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Thread environment setup for parallel execution (must be before numpy/numba)
# ---------------------------------------------------------------------------
# When using ProcessPoolExecutor, each worker spawns its own process. If BLAS
# or Numba also spawn multiple threads, the total thread count can explode.
# Setting these to "1" ensures "process parallelism only" mode. Set
# MARSDISK_THREAD_GUARD=0 to retain default threading behaviour.
import os as _os


def _apply_thread_guard() -> None:
    guard = _os.environ.get("MARSDISK_THREAD_GUARD", "1").lower()
    if guard in {"0", "false", "off", "no"}:
        return
    _os.environ.setdefault("OMP_NUM_THREADS", "1")
    _os.environ.setdefault("MKL_NUM_THREADS", "1")
    _os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    _os.environ.setdefault("NUMBA_NUM_THREADS", "1")


_apply_thread_guard()

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import concurrent.futures
import json
import math
import tempfile

import numpy as np
import pandas as pd

from .. import config_utils, constants
from ..schema import Config, Radiation
from ..physics import radiation
from ..run import run_zero_d


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


@dataclass
class BetaSamplingConfig:
    """Configuration bundle for :func:`sample_beta_over_orbit`.

    Attributes
    ----------
    base_config:
        Pydantic configuration describing the reference zero-dimensional run.
    r_values:
        Iterable of orbital radii expressed in Mars radii.
    T_values:
        Iterable of Mars-facing temperatures in Kelvin.
    qpr_table_path:
        Path to the Planck-averaged ⟨Q_pr⟩ lookup table; must exist.
    jobs:
        Maximum worker processes.  ``1`` executes sequentially.
    min_steps:
        Lower bound on the number of integration steps per orbit.
    dt_over_t_blow_max:
        Safety cap applied to ``dt / t_blow`` during the run.
    capture_example_run_config:
        Whether to expose the first run's ``run_config.json`` in ``diagnostics``.
    diagnostics:
        Mutable dictionary populated with auxiliary outputs (e.g. dt statistics,
        run_config metadata).  Filled in-place by :func:`sample_beta_over_orbit`.
    """

    base_config: Config
    r_values: Sequence[float]
    T_values: Sequence[float]
    qpr_table_path: Path
    jobs: int = 1
    min_steps: int = 100
    dt_over_t_blow_max: float = 0.1
    capture_example_run_config: bool = True
    enforce_mass_budget: bool = False
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.base_config, Config):
            raise TypeError("base_config must be an instance of marsdisk.schema.Config")
        resolved_qpr = _resolve_table_path(Path(self.qpr_table_path))
        self.qpr_table_path = resolved_qpr
        if not resolved_qpr.exists():
            raise FileNotFoundError(f"Q_pr table not found: {resolved_qpr}")
        if self.jobs < 1:
            raise ValueError("jobs must be at least 1")
        if self.min_steps < 1:
            raise ValueError("min_steps must be at least 1")
        if not math.isfinite(self.dt_over_t_blow_max) or self.dt_over_t_blow_max <= 0.0:
            raise ValueError("dt_over_t_blow_max must be positive and finite")
        if len(self.r_values) == 0 or len(self.T_values) == 0:
            raise ValueError("r_values and T_values must be non-empty")


def _prepare_case_config(
    cfg: Config,
    *,
    r_rm: float,
    T_M: float,
    qpr_table_path: Path,
    dt_over_t_blow_max: float,
) -> Config:
    """Return a deep copy of ``cfg`` customised for a single (r, T) sample."""

    work = cfg.model_copy(deep=True)

    work.geometry.mode = "0D"
    config_utils.ensure_disk_geometry(work, r_rm=float(r_rm))

    # Temperature floor and Q_pr table provenance.
    if work.radiation is None:
        work.radiation = Radiation(qpr_table_path=qpr_table_path, TM_K=float(T_M))
    else:
        work.radiation.qpr_table_path = qpr_table_path
    work.radiation.TM_K = float(T_M)

    # Enforce gas-poor defaults.
    work.sinks.enable_gas_drag = False
    work.sinks.mode = getattr(work.sinks, "mode", "none") or "none"

    # Numerical controls: one full orbit with per-step re-evaluation.
    work.numerics.t_end_orbits = 1.0
    work.numerics.t_end_years = None
    work.numerics.dt_init = "auto"
    work.numerics.eval_per_step = True
    work.numerics.orbit_rollup = True
    work.numerics.dt_over_t_blow_max = float(dt_over_t_blow_max)

    # Each run writes to a temporary location that is removed afterwards.
    work.io.outdir = Path(".")  # placeholder overwritten at runtime

    return work


def _run_single_case(args: Mapping[str, Any]) -> Dict[str, Any]:
    """Worker helper executing a single zero-dimensional run."""

    base_dict = args["base_config_dict"]
    r_rm = float(args["r_rm"])
    T_M = float(args["T_M"])
    qpr_table_path = Path(args["qpr_table_path"])
    dt_over_t_blow_max = float(args["dt_over_t_blow_max"])
    min_steps = int(args["min_steps"])
    capture_artifacts = bool(args["capture_artifacts"])
    enforce_mass_budget = bool(args.get("enforce_mass_budget", False))

    cfg = Config.model_validate(base_dict)
    case_cfg = _prepare_case_config(
        cfg,
        r_rm=r_rm,
        T_M=T_M,
        qpr_table_path=qpr_table_path,
        dt_over_t_blow_max=dt_over_t_blow_max,
    )

    # Ensure the requested Q_pr table is active inside the worker.
    radiation.load_qpr_table(qpr_table_path)

    with tempfile.TemporaryDirectory(prefix="beta_sampler_") as tmp:
        outdir = Path(tmp)
        case_cfg.io.outdir = outdir
        run_zero_d(case_cfg, enforce_mass_budget=enforce_mass_budget)

        series_path = outdir / "series" / "run.parquet"
        if not series_path.exists():
            raise FileNotFoundError(f"Expected time series output missing: {series_path}")
        df = pd.read_parquet(series_path)

        required_cols = ["time", "beta_at_smin_effective", "dt_over_t_blow"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise KeyError(f"run output missing required columns: {', '.join(missing_cols)}")

        times = df["time"].to_numpy(dtype=float)
        beta_vals = df["beta_at_smin_effective"].to_numpy(dtype=float)
        dt_ratios = df["dt_over_t_blow"].to_numpy(dtype=float)

        if times.size < min_steps:
            raise RuntimeError(
                f"time series has only {times.size} steps < min_steps={min_steps} for r={r_rm}, T={T_M}"
            )

        summary_path = outdir / "summary.json"
        summary_payload: Optional[Dict[str, Any]] = None
        if summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as fh:
                summary_payload = json.load(fh)

        run_config_path = outdir / "run_config.json"
        run_config_payload: Optional[Dict[str, Any]] = None
        if capture_artifacts and run_config_path.exists():
            with run_config_path.open("r", encoding="utf-8") as fh:
                run_config_payload = json.load(fh)

    result: Dict[str, Any] = {
        "i_r": int(args["i_r"]),
        "i_T": int(args["i_T"]),
        "r_rm": r_rm,
        "T_M": T_M,
        "time": times.tolist(),
        "beta": beta_vals.tolist(),
        "dt_over_t_blow": dt_ratios.tolist(),
        "summary": summary_payload,
    }
    if run_config_payload is not None:
        result["run_config"] = run_config_payload
    return result


def _iter_cases(r_values: Sequence[float], T_values: Sequence[float]) -> Iterable[Tuple[int, int, float, float]]:
    for i_r, r_rm in enumerate(r_values):
        for i_T, T_M in enumerate(T_values):
            yield i_r, i_T, float(r_rm), float(T_M)


def sample_beta_over_orbit(cfg: BetaSamplingConfig) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate β(r, T, t) for one orbital period over the provided grids."""

    r_values = np.asarray(list(cfg.r_values), dtype=float)
    T_values = np.asarray(list(cfg.T_values), dtype=float)
    base_dict = cfg.base_config.model_dump(mode="python")

    # Initialise ⟨Q_pr⟩ lookup in the parent process for consistency.
    radiation.load_qpr_table(cfg.qpr_table_path)

    tasks: List[Dict[str, Any]] = []
    capture_first = cfg.capture_example_run_config
    counter = 0
    for i_r, r_rm in enumerate(r_values):
        for i_T, T_M in enumerate(T_values):
            task = {
                "base_config_dict": base_dict,
                "r_rm": float(r_rm),
                "T_M": float(T_M),
                "qpr_table_path": str(cfg.qpr_table_path),
                "dt_over_t_blow_max": cfg.dt_over_t_blow_max,
                "min_steps": cfg.min_steps,
                "capture_artifacts": capture_first and counter == 0,
                "enforce_mass_budget": cfg.enforce_mass_budget,
                "i_r": i_r,
                "i_T": i_T,
            }
            tasks.append(task)
            counter += 1

    results: List[Dict[str, Any]] = []
    if cfg.jobs == 1:
        for task in tasks:
            results.append(_run_single_case(task))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=cfg.jobs) as pool:
            futures = [pool.submit(_run_single_case, task) for task in tasks]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

    if not results:
        raise RuntimeError("No β samples were produced")

    lengths = [len(entry["time"]) for entry in results]
    if not lengths:
        raise RuntimeError("No time series available from β sampling runs")
    ref_index = int(np.argmax(lengths))
    reference_raw_time = np.asarray(results[ref_index]["time"], dtype=float)
    if reference_raw_time.size == 0:
        raise RuntimeError("Reference time series is empty")
    t_orb_reference = float(reference_raw_time[-1])
    if not math.isfinite(t_orb_reference) or t_orb_reference <= 0.0:
        raise RuntimeError("Reference orbit duration is non-positive")
    reference_fraction = reference_raw_time / t_orb_reference
    n_time = reference_fraction.size
    beta_cube = np.zeros((r_values.size, T_values.size, n_time), dtype=np.float32)

    dt_ratios_all: List[float] = []
    qpr_used_values: List[float] = []
    run_config_example: Optional[Dict[str, Any]] = None
    t_orb_values: List[float] = []

    for result in results:
        i_r = int(result["i_r"])
        i_T = int(result["i_T"])

        time_series = np.asarray(result["time"], dtype=float)
        if time_series.size == 0:
            raise RuntimeError("Encountered empty time series in a sample run")
        t_orb_local = float(time_series[-1]) if time_series.size else float("nan")
        t_orb_values.append(t_orb_local)
        if not math.isfinite(t_orb_local) or t_orb_local <= 0.0:
            raise RuntimeError("Encountered non-positive orbital period in a sample run")
        fractions = time_series / t_orb_local
        beta_series = np.asarray(result["beta"], dtype=float)
        if beta_series.size != time_series.size:
            raise RuntimeError("β series length does not match time samples in a run")
        if np.any(np.diff(fractions) <= 0.0):
            raise RuntimeError("Time fractions must increase monotonically")
        beta_interp = np.interp(reference_fraction, fractions, beta_series)
        beta_cube[i_r, i_T, :] = beta_interp.astype(np.float32, copy=False)

        dt_ratios_all.extend(float(x) for x in result["dt_over_t_blow"])

        if "run_config" in result and run_config_example is None:
            run_config_example = result["run_config"]
            qpr_used = run_config_example.get("run_inputs", {}).get("Q_pr_used")
            if isinstance(qpr_used, (float, int)):
                qpr_used_values.append(float(qpr_used))

        if result.get("summary"):
            qpr_used = result["summary"].get("Q_pr_used") if isinstance(result["summary"], Mapping) else None
            if isinstance(qpr_used, (float, int)):
                qpr_used_values.append(float(qpr_used))

    dt_ratios_all = [val for val in dt_ratios_all if np.isfinite(val)]

    cfg.diagnostics["time_grid_fraction"] = reference_fraction.tolist()
    cfg.diagnostics["time_grid_s_reference"] = reference_raw_time.tolist()
    cfg.diagnostics["t_orb_reference_s"] = t_orb_reference
    if t_orb_values:
        cfg.diagnostics["t_orb_range_s"] = [float(min(t_orb_values)), float(max(t_orb_values))]
    cfg.diagnostics["time_steps_per_orbit"] = int(n_time)
    cfg.diagnostics["dt_over_t_blow_median"] = float(np.median(dt_ratios_all)) if dt_ratios_all else float("nan")
    cfg.diagnostics["dt_over_t_blow_p90"] = float(np.percentile(dt_ratios_all, 90)) if dt_ratios_all else float("nan")
    cfg.diagnostics["dt_over_t_blow_max_observed"] = float(max(dt_ratios_all)) if dt_ratios_all else float("nan")
    cfg.diagnostics["qpr_used_stats"] = {
        "samples": len(qpr_used_values),
        "min": float(min(qpr_used_values)) if qpr_used_values else None,
        "max": float(max(qpr_used_values)) if qpr_used_values else None,
    }
    if run_config_example is not None:
        cfg.diagnostics["example_run_config"] = run_config_example

    return r_values, T_values, reference_fraction, beta_cube
