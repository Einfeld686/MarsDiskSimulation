"""Sweep the one-orbit mass-loss fraction over (r/R_M, T_M) for gas-poor disks.

The driver orchestrates a grid of ``python -m marsdisk.run`` executions while
ensuring that the sequential coupling order described in the user brief is
respected on every step:

⟨Q_pr⟩ → β → a_blow → sublimation ``ds/dt`` → τ & Φ → surface sink fluxes.

Results are collected into ``map.csv`` alongside validation metadata such as the
median ``dt/t_blow`` and the recorded ⟨Q_pr⟩ table path.  Any mass-budget
violations are written to ``map1_validation.json`` for quick inspection.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Thread environment setup for parallel execution (must be before numpy/numba)
# ---------------------------------------------------------------------------
# When using ProcessPoolExecutor, each worker spawns its own process. If BLAS
# or Numba also spawn multiple threads, the total thread count can explode
# (e.g., 4 workers × 8 threads = 32 threads). Setting these to "1" ensures
# "process parallelism only" mode, which is optimal for embarrassingly parallel
# workloads like parameter sweeps. Set MARSDISK_THREAD_GUARD=0 to opt out.
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

import argparse
import copy
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk import constants

DEFAULT_BASE_CONFIG = Path("_configs/05_massloss_base.yml")
MAP_SUBDIR = "map1"
LOG_SUBDIR = "logs"
FRAMES_SUBDIR = "frames"
CASE_CONFIG_NAME = "run_config.yml"
SUMMARY_FILENAME = "summary.json"
SERIES_FILENAME = "series/run.parquet"
MASS_BUDGET_FILENAME = "checks/mass_budget.csv"
DT_OVER_T_BLOW_CAP = 0.05


@dataclass(frozen=True)
class CaseSpec:
    """Container describing a single (r/R_M, T_M) evaluation."""

    r_rm: float
    T_M: float
    dt_init_s: float
    n_steps_estimate: int
    case_id: str
    run_dir: Path
    log_path: Path


def _parse_grid(spec: Sequence[float], label: str) -> np.ndarray:
    if len(spec) != 3:
        raise ValueError(f"{label} requires three numbers: start stop count")
    start, stop, count = map(float, spec)
    n = int(round(count))
    if n < 1:
        raise ValueError(f"{label} count must be at least 1")
    if stop < start:
        raise ValueError(f"{label} stop must be ≥ start")
    if n == 1:
        return np.asarray([start], dtype=float)
    return np.linspace(start, stop, n, dtype=float)


def _load_base_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Base YAML configuration not found: {path}")
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        raise TypeError("Base YAML must encode a mapping at the top level.")
    return data


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(payload, fh)


def _compute_dt_controls(r_rm: float, steps_per_orbit: int, dt_ratio_cap: float) -> Tuple[float, int, float]:
    """Return (dt_init, steps_estimate, Omega) for the given orbital radius."""

    if steps_per_orbit < 1:
        raise ValueError("time_steps_per_orbit must be ≥ 1")
    radius_m = float(r_rm) * constants.R_MARS
    if radius_m <= 0.0:
        raise ValueError("Orbital radius must be positive.")
    GM = constants.G * constants.M_MARS
    Omega = math.sqrt(GM / (radius_m**3))
    t_orb = 2.0 * math.pi / Omega
    dt_candidate = t_orb / float(steps_per_orbit)
    dt_cap = dt_ratio_cap / Omega
    dt_init = min(dt_candidate, dt_cap)
    dt_init = max(dt_init, 1.0e-6)
    steps_estimate = max(1, int(math.ceil(t_orb / dt_init)))
    return dt_init, steps_estimate, Omega


def _case_identifier(r_rm: float, T_M: float) -> str:
    return f"r{r_rm:.3f}_T{T_M:.0f}"


def _prepare_case_spec(
    r_rm: float,
    T_M: float,
    *,
    base_outdir: Path,
    logs_dir: Path,
    steps_per_orbit: int,
    dt_ratio_cap: float,
) -> CaseSpec:
    dt_init, steps_estimate, _ = _compute_dt_controls(r_rm, steps_per_orbit, dt_ratio_cap)
    case_id = _case_identifier(r_rm, T_M)
    run_dir = base_outdir / case_id
    log_path = logs_dir / f"{case_id}.log"
    return CaseSpec(
        r_rm=float(r_rm),
        T_M=float(T_M),
        dt_init_s=float(dt_init),
        n_steps_estimate=int(steps_estimate),
        case_id=case_id,
        run_dir=run_dir,
        log_path=log_path,
    )


def _inject_case_parameters(
    base_cfg: Dict[str, Any],
    *,
    spec: CaseSpec,
    qpr_table: Path,
) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_cfg)

    geometry = cfg.setdefault("geometry", {})
    geometry["mode"] = "0D"
    geometry.pop("r", None)
    geometry.pop("runtime_orbital_radius_rm", None)

    disk_cfg = cfg.setdefault("disk", {})
    geom_cfg = disk_cfg.setdefault("geometry", {})
    geom_cfg["r_in_RM"] = float(spec.r_rm)
    geom_cfg["r_out_RM"] = float(spec.r_rm)
    geom_cfg.setdefault("r_profile", "uniform")
    geom_cfg.setdefault("p_index", 0.0)

    cfg.pop("temps", None)

    radiation_cfg = cfg.setdefault("radiation", {})
    radiation_cfg["TM_K"] = float(spec.T_M)
    radiation_cfg["qpr_table_path"] = str(qpr_table)
    radiation_cfg.pop("qpr_table", None)
    radiation_cfg.pop("Q_pr", None)

    shielding_cfg = cfg.setdefault("shielding", {})
    if "phi_table" in shielding_cfg and "table_path" not in shielding_cfg:
        shielding_cfg["table_path"] = shielding_cfg.pop("phi_table")
    else:
        shielding_cfg.pop("phi_table", None)

    sinks_cfg = cfg.setdefault("sinks", {})
    sinks_cfg["mode"] = "sublimation"
    sinks_cfg["enable_sublimation"] = True
    sinks_cfg["enable_gas_drag"] = False

    numerics = cfg.setdefault("numerics", {})
    numerics["t_end_orbits"] = 1.0
    numerics.pop("t_end_years", None)
    numerics["dt_init"] = float(spec.dt_init_s)
    numerics["eval_per_step"] = True
    numerics["orbit_rollup"] = True
    numerics["dt_over_t_blow_max"] = DT_OVER_T_BLOW_CAP

    io_cfg = cfg.setdefault("io", {})
    io_cfg["outdir"] = str(spec.run_dir)

    sizes_cfg = cfg.setdefault("sizes", {})
    floor = max(float(sizes_cfg.get("s_min", 1.0e-6)), 1.0e-9)
    sizes_cfg["s_min"] = floor
    sizes_cfg["evolve_min_size"] = False

    return cfg


def _read_summary(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"summary.json not found at {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_series(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Time series Parquet file missing at {path}")
    return pd.read_parquet(path)


def _read_mass_budget(path: Path) -> Dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"Mass budget log missing at {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Mass budget log at {path} is empty")
    last = df.iloc[-1]
    return {
        "error_percent": float(last.get("error_percent", float("nan"))),
        "tolerance_percent": float(last.get("tolerance_percent", float("nan"))),
    }


def _median_ratio(numerator: pd.Series, denominator: pd.Series) -> float:
    num = np.asarray(numerator.to_numpy(dtype=float))
    den = np.asarray(denominator.to_numpy(dtype=float))
    mask = np.isfinite(num) & np.isfinite(den) & (den != 0.0)
    if not mask.any():
        return float("nan")
    ratio = num[mask] / den[mask]
    finite = ratio[np.isfinite(ratio)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite))


def _median_finite(series: pd.Series) -> float:
    values = np.asarray(series.to_numpy(dtype=float))
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite))


def _run_case(
    spec: CaseSpec,
    *,
    base_cfg: Dict[str, Any],
    qpr_table: Path,
) -> Dict[str, Any]:
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    cfg = _inject_case_parameters(base_cfg, spec=spec, qpr_table=qpr_table)

    config_path = spec.run_dir / CASE_CONFIG_NAME
    _write_yaml(config_path, cfg)

    cmd = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path)]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    with spec.log_path.open("w", encoding="utf-8") as fh:
        fh.write("# Command:\n")
        fh.write(" ".join(cmd) + "\n\n")
        fh.write("# STDOUT:\n")
        fh.write(proc.stdout or "")
        fh.write("\n\n# STDERR:\n")
        fh.write(proc.stderr or "")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Run failed for {spec.case_id} (exit code {proc.returncode}); see {spec.log_path}"
        )

    summary_path = spec.run_dir / SUMMARY_FILENAME
    series_path = spec.run_dir / SERIES_FILENAME
    mass_budget_path = spec.run_dir / MASS_BUDGET_FILENAME

    summary = _read_summary(summary_path)
    series = _read_series(series_path)
    mass_budget = _read_mass_budget(mass_budget_path)

    M_out = float(summary.get("M_out_cum", float("nan")))
    M_sink = float(summary.get("M_sink_cum", summary.get("M_loss_from_sinks", 0.0)))
    M_loss = M_out + M_sink

    initial_cfg = cfg.get("initial", {})
    M_init = float(initial_cfg.get("mass_total", float("nan")))

    if not math.isfinite(M_init) or M_init <= 0.0:
        raise ValueError(f"Invalid initial mass for {spec.case_id}: {M_init!r}")

    loss_frac = M_loss / M_init
    out_frac = M_out / M_init
    sink_frac = M_sink / M_init

    beta_ratio_median = _median_ratio(series["beta_at_smin_effective"], series["beta_threshold"])
    dt_ratio_median = _median_finite(series["dt_over_t_blow"])

    qpr_path = summary.get("qpr_table_path") or ""
    if not qpr_path:
        raise RuntimeError(f"qpr_table_path missing in summary for {spec.case_id}")

    result: Dict[str, Any] = {
        "r_RM": float(spec.r_rm),
        "T_M": float(spec.T_M),
        "loss_frac": float(loss_frac),
        "out_frac": float(out_frac),
        "sink_frac": float(sink_frac),
        "M_out_cum": float(M_out),
        "M_sink_cum": float(M_sink),
        "M_init": float(M_init),
        "beta_ratio_median": float(beta_ratio_median),
        "dt_over_t_blow_median": float(dt_ratio_median),
        "run_dir": str(spec.run_dir),
        "log_path": str(spec.log_path),
        "qpr_table_path": str(qpr_path),
        "mass_budget_error_percent": float(mass_budget["error_percent"]),
        "mass_budget_tolerance_percent": float(mass_budget["tolerance_percent"]),
        "n_steps_estimate": int(spec.n_steps_estimate),
        "dt_init_s": float(spec.dt_init_s),
    }
    return result


def _iter_specs(
    r_values: Iterable[float],
    T_values: Iterable[float],
    *,
    base_outdir: Path,
    logs_dir: Path,
    steps_per_orbit: int,
    dt_ratio_cap: float,
) -> List[CaseSpec]:
    specs: List[CaseSpec] = []
    for r in r_values:
        for T in T_values:
            specs.append(
                _prepare_case_spec(
                    r,
                    T,
                    base_outdir=base_outdir,
                    logs_dir=logs_dir,
                    steps_per_orbit=steps_per_orbit,
                    dt_ratio_cap=dt_ratio_cap,
                )
            )
    return specs


def _run_sequential(
    specs: Sequence[CaseSpec],
    *,
    base_cfg: Dict[str, Any],
    qpr_table: Path,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    total = len(specs)
    for idx, spec in enumerate(specs, start=1):
        print(f"[{idx}/{total}] r={spec.r_rm:.3f} R_M, T={spec.T_M:.0f} K", flush=True)
        results.append(_run_case(spec, base_cfg=base_cfg, qpr_table=qpr_table))
    return results


def _run_parallel(
    specs: Sequence[CaseSpec],
    *,
    base_cfg: Dict[str, Any],
    qpr_table: Path,
    jobs: int,
) -> List[Dict[str, Any]]:
    from concurrent.futures import ProcessPoolExecutor, as_completed

    payload = {
        "base_cfg": base_cfg,
        "qpr_table": qpr_table,
    }
    results: List[Dict[str, Any]] = []
    total = len(specs)
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(_run_case, spec, base_cfg=payload["base_cfg"], qpr_table=payload["qpr_table"]): spec
            for spec in specs
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            spec = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                raise RuntimeError(f"Case {spec.case_id} failed: {exc}") from exc
            print(f"[{completed}/{total}] r={spec.r_rm:.3f} R_M, T={spec.T_M:.0f} K", flush=True)
            results.append(result)
    return results


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _collect_validation(records: Sequence[Dict[str, Any]], *, tolerance: float) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    for rec in records:
        error = float(rec.get("mass_budget_error_percent", float("nan")))
        qpr_path = rec.get("qpr_table_path")
        violation_flags: List[str] = []
        if math.isfinite(error) and error > tolerance:
            violation_flags.append("mass_budget_error")
        if not qpr_path:
            violation_flags.append("missing_qpr_table_path")
        if violation_flags:
            violations.append(
                {
                    "r_RM": rec.get("r_RM"),
                    "T_M": rec.get("T_M"),
                    "issues": violation_flags,
                    "error_percent": error,
                    "run_dir": rec.get("run_dir"),
                    "log_path": rec.get("log_path"),
                }
            )
    return {
        "checked": len(records),
        "tolerance_percent": tolerance,
        "violations": violations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate loss_frac = (M_out_cum + M_sink_cum) / M_init over a regular (r/R_M, T_M) grid."
    )
    parser.add_argument(
        "--rRM",
        nargs=3,
        type=float,
        metavar=("START", "STOP", "COUNT"),
        required=True,
        help="Radial grid specification in Mars radii.",
    )
    parser.add_argument(
        "--TM",
        nargs=3,
        type=float,
        metavar=("START", "STOP", "COUNT"),
        required=True,
        help="Temperature grid specification in Kelvin.",
    )
    parser.add_argument(
        "--time-steps-per-orbit",
        type=int,
        default=100,
        help="Nominal number of steps per orbital period (before dt/t_blow cap).",
    )
    parser.add_argument(
        "--qpr-table",
        type=Path,
        required=True,
        help="CSV table containing the Planck-averaged ⟨Q_pr⟩ lookups.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        required=True,
        help="Destination directory (map.csv, map_spec.json, validation logs).",
    )
    parser.add_argument("--jobs", type=int, default=1, help="Number of worker processes.")
    parser.add_argument(
        "--base-config",
        type=Path,
        default=DEFAULT_BASE_CONFIG,
        help="Base 0D YAML configuration (default: _configs/05_massloss_base.yml).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    base_cfg_path = args.base_config
    qpr_table_path = args.qpr_table
    outdir = args.outdir
    map_dir = outdir / MAP_SUBDIR
    logs_dir = outdir / LOG_SUBDIR

    for directory in (outdir, map_dir, logs_dir, outdir / FRAMES_SUBDIR):
        directory.mkdir(parents=True, exist_ok=True)

    if not qpr_table_path.exists():
        raise FileNotFoundError(f"⟨Q_pr⟩ table not found: {qpr_table_path}")

    base_cfg = _load_base_config(base_cfg_path)

    r_values = _parse_grid(args.rRM, "r/R_M grid")
    T_values = _parse_grid(args.TM, "T_M grid")

    specs = _iter_specs(
        r_values,
        T_values,
        base_outdir=map_dir,
        logs_dir=logs_dir,
        steps_per_orbit=int(args.time_steps_per_orbit),
        dt_ratio_cap=DT_OVER_T_BLOW_CAP,
    )

    jobs = max(1, int(args.jobs))
    if jobs == 1:
        records = _run_sequential(specs, base_cfg=base_cfg, qpr_table=qpr_table_path)
    else:
        records = _run_parallel(specs, base_cfg=base_cfg, qpr_table=qpr_table_path, jobs=jobs)

    if not records:
        raise RuntimeError("No simulation records produced; map.csv would be empty.")

    df = pd.DataFrame(records)
    df = df.sort_values(["r_RM", "T_M"]).reset_index(drop=True)

    csv_path = map_dir / "map.csv"
    df.to_csv(csv_path, index=False)

    tolerance = float(df["mass_budget_tolerance_percent"].dropna().median()) if "mass_budget_tolerance_percent" in df else 0.5
    validation = _collect_validation(records, tolerance=tolerance)
    validation_path = map_dir / "map1_validation.json"
    _write_json(validation_path, validation)

    map_spec = {
        "r_RM": {
            "start": float(r_values[0]),
            "stop": float(r_values[-1]),
            "count": int(r_values.size),
        },
        "T_M": {
            "start": float(T_values[0]),
            "stop": float(T_values[-1]),
            "count": int(T_values.size),
        },
        "samples": int(len(records)),
        "time_steps_per_orbit": int(args.time_steps_per_orbit),
        "dt_over_t_blow_cap": DT_OVER_T_BLOW_CAP,
        "dt_over_t_blow_median": float(df["dt_over_t_blow_median"].median()),
        "loss_frac_median": float(df["loss_frac"].median()),
        "loss_frac_max": float(df["loss_frac"].max()),
        "qpr_table_paths": sorted({str(Path(path).resolve()) for path in df["qpr_table_path"].dropna().unique()}),
        "base_config": str(base_cfg_path.resolve()),
        "qpr_table": str(qpr_table_path.resolve()),
        "outdir": str(outdir.resolve()),
    }
    map_spec_path = map_dir / "map_spec.json"
    _write_json(map_spec_path, map_spec)

    print(f"Wrote {csv_path} with {len(df)} rows.")
    print(f"Wrote {map_spec_path}.")
    print(f"Validation log: {validation_path}")


if __name__ == "__main__":
    main()
