"""Generate a one-orbit mass-loss map over (r/R_M, T_M) for gas-poor disks.

The driver executes the 0D coupling loop for each grid point while enforcing
the sequential ordering documented in the repository:

⟨Q_pr⟩ → Ω → a_blow → HKL ds/dt → Φ(τ) → surface sinks → accumulation.

Results are serialised to ``map_massloss.csv`` alongside provenance and
stability diagnostics in ``logs/spec.json``.  By default the gas-poor,
``sinks.mode='sublimation'`` configuration is sampled; an optional comparison
with ``sinks.mode='none'`` can be requested via ``--include-sinks-none``.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk.analysis.massloss_sampler import sample_mass_loss_one_orbit

DEFAULT_QPR_TABLE = ROOT / "data" / "qpr_table.csv"
CSV_FILENAME = "map_massloss.csv"
SPEC_RELATIVE_PATH = Path("logs/spec.json")
DT_REQUIREMENT_THRESHOLD = 0.05
ALT_MODE_PREFIX = "nosinks_"
ALT_EXPORT_FIELDS = (
    "mass_loss_frac_per_orbit",
    "M_out_cum",
    "M_sink_cum",
    "M_loss_cum",
)


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


def _iter_grid(r_values: Iterable[float], T_values: Iterable[float]) -> List[Tuple[float, float]]:
    return [(float(r), float(T)) for r in r_values for T in T_values]


def _format_case_index(idx: int, total: int, r_rm: float, T_m: float) -> str:
    return f"[{idx}/{total}] r={r_rm:.3f} R_M, T={T_m:.0f} K"


def _execute_case(
    r_rm: float,
    T_m: float,
    *,
    base_config: Path,
    qpr_table: Path,
    dt_over_t_blow_max: float,
    include_sinks_none: bool,
    overrides: Optional[List[str]] = None,
) -> Dict[str, float]:
    base = sample_mass_loss_one_orbit(
        r_rm,
        T_m,
        base_config,
        qpr_table,
        dt_over_t_blow_max=dt_over_t_blow_max,
        sinks_mode="sublimation",
        enable_sublimation=True,
        enable_gas_drag=False,
        overrides=overrides,
    )
    if include_sinks_none:
        compare = sample_mass_loss_one_orbit(
            r_rm,
            T_m,
            base_config,
            qpr_table,
            dt_over_t_blow_max=dt_over_t_blow_max,
            sinks_mode="none",
            enable_sublimation=False,
            enable_gas_drag=False,
            overrides=overrides,
        )
        for key in ALT_EXPORT_FIELDS:
            if key in compare:
                base[f"{ALT_MODE_PREFIX}{key}"] = compare[key]
    return base


def _run_sequential(
    grid: List[Tuple[float, float]],
    *,
    base_config: Path,
    qpr_table: Path,
    dt_ratio_max: float,
    include_sinks_none: bool,
    overrides: Optional[List[str]],
) -> List[Dict[str, float]]:
    results: List[Dict[str, float]] = []
    total = len(grid)
    for idx, (r, T) in enumerate(grid, start=1):
        print(_format_case_index(idx, total, r, T), flush=True)
        results.append(
            _execute_case(
                r,
                T,
                base_config=base_config,
                qpr_table=qpr_table,
                dt_over_t_blow_max=dt_ratio_max,
                include_sinks_none=include_sinks_none,
                overrides=overrides,
            )
        )
    return results


def _run_parallel(
    grid: List[Tuple[float, float]],
    *,
    base_config: Path,
    qpr_table: Path,
    dt_ratio_max: float,
    include_sinks_none: bool,
    jobs: int,
    overrides: Optional[List[str]],
) -> List[Dict[str, float]]:
    results: List[Dict[str, float]] = []
    total = len(grid)
    with ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = {
                executor.submit(
                    _execute_case,
                    r,
                    T,
                    base_config=base_config,
                    qpr_table=qpr_table,
                    dt_over_t_blow_max=dt_ratio_max,
                    include_sinks_none=include_sinks_none,
                    overrides=overrides,
                ): (r, T)
                for r, T in grid
            }
        for idx, future in enumerate(as_completed(futures), start=1):
            r, T = futures[future]
            print(_format_case_index(idx, total, r, T), flush=True)
            results.append(future.result())
    return results


def _collect_stats(df: pd.DataFrame) -> Dict[str, float | int | List[str]]:
    dt_median_global = float(np.nanmedian(df["dt_over_t_blow_median"]))
    dt_median_max = float(np.nanmax(df["dt_over_t_blow_median"]))
    dt_p90_global = float(np.nanmedian(df["dt_over_t_blow_p90"]))
    dt_p90_max = float(np.nanmax(df["dt_over_t_blow_p90"]))
    requirement_failures = int(
        np.sum(
            (df["dt_over_t_blow_requirement_pass"] == False)  # noqa: E712 - intentional identity check
        )
    )
    mb_series = df["mass_budget_max_error_percent"].to_numpy(dtype=float)
    finite_mb = np.isfinite(mb_series)
    mass_budget_max = (
        float(np.nanmax(np.abs(mb_series[finite_mb])))
        if finite_mb.any()
        else float("nan")
    )
    qpr_paths = sorted({Path(path).resolve().as_posix() for path in df["qpr_table_path"].dropna().unique()})
    return {
        "dt_over_t_blow_median_global": dt_median_global,
        "dt_over_t_blow_p90_global": dt_p90_global,
        "dt_over_t_blow_median_max": dt_median_max,
        "dt_over_t_blow_p90_max": dt_p90_max,
        "dt_over_t_blow_requirement_threshold": DT_REQUIREMENT_THRESHOLD,
        "dt_over_t_blow_requirement_failures": requirement_failures,
        "mass_budget_max_error_percent_global": mass_budget_max,
        "qpr_table_paths": qpr_paths,
    }


def _write_spec(
    *,
    outdir: Path,
    df: pd.DataFrame,
    r_values: np.ndarray,
    T_values: np.ndarray,
    base_config: Path,
    qpr_table: Path,
    jobs: int,
) -> None:
    stats = _collect_stats(df)
    payload = {
        "grid": {
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
        },
        "samples": int(df.shape[0]),
        "jobs": int(jobs),
        "columns": df.columns.tolist(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_config": str(base_config.resolve()),
        "qpr_table": str(qpr_table.resolve()),
        "mass_loss_frac_min": float(np.nanmin(df["mass_loss_frac_per_orbit"])),
        "mass_loss_frac_max": float(np.nanmax(df["mass_loss_frac_per_orbit"])),
        "mass_loss_frac_median": float(np.nanmedian(df["mass_loss_frac_per_orbit"])),
        "dt_over_t_blow_stats": stats,
        "notes": (
            "mass_loss_frac_per_orbit = (M_out_cum + M_sink_cum) / M_init; "
            "gas-poor regime with ⟨Q_pr⟩ from data/qpr_table.csv."
        ),
    }
    spec_path = outdir / SPEC_RELATIVE_PATH
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    with spec_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map the per-orbit mass-loss fraction (M_out + M_sink)/M_init over (r/R_M, T_M)."
    )
    parser.add_argument(
        "--base-config",
        type=Path,
        required=True,
        help="Reference YAML configuration (0D gas-poor setup).",
    )
    parser.add_argument(
        "--qpr-table",
        type=Path,
        default=DEFAULT_QPR_TABLE,
        help=f"Planck-averaged ⟨Q_pr⟩ lookup table (default: {DEFAULT_QPR_TABLE}).",
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
        "--outdir",
        type=Path,
        required=True,
        help="Destination directory for map_massloss.csv and logs/spec.json.",
    )
    parser.add_argument("--jobs", type=int, default=1, help="Number of worker processes (default: 1).")
    parser.add_argument(
        "--dt-over-tblow-max",
        type=float,
        default=DT_REQUIREMENT_THRESHOLD,
        help="Safety cap applied to dt/t_blow (default: 0.05).",
    )
    parser.add_argument(
        "--include-sinks-none",
        action="store_true",
        help="Also sample sinks.mode='none' and append prefixed columns.",
    )
    parser.add_argument(
        "--override",
        action="append",
        nargs="+",
        metavar="PATH=VALUE",
        help="Apply configuration overrides before sampling (passed to marsdisk.run).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_config = args.base_config
    qpr_table = args.qpr_table
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    if not base_config.exists():
        raise FileNotFoundError(f"Base configuration not found: {base_config}")
    if not qpr_table.exists():
        raise FileNotFoundError(f"⟨Q_pr⟩ table not found: {qpr_table}")

    r_values = _parse_grid(args.rRM, "r/R_M grid")
    T_values = _parse_grid(args.TM, "T_M grid")
    grid = _iter_grid(r_values, T_values)

    jobs = max(1, int(args.jobs))
    include_sinks_none = bool(args.include_sinks_none)
    dt_ratio_max = float(args.dt_over_tblow_max)
    overrides: List[str] = []
    if args.override:
        for group in args.override:
            overrides.extend(group)

    if jobs == 1:
        rows = _run_sequential(
            grid,
            base_config=base_config,
            qpr_table=qpr_table,
            dt_ratio_max=dt_ratio_max,
            include_sinks_none=include_sinks_none,
            overrides=overrides,
        )
    else:
        rows = _run_parallel(
            grid,
            base_config=base_config,
            qpr_table=qpr_table,
            dt_ratio_max=dt_ratio_max,
            include_sinks_none=include_sinks_none,
            jobs=jobs,
            overrides=overrides,
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No results collected; map_massloss.csv would be empty.")
    df = df.sort_values(["r_RM", "T_M"]).reset_index(drop=True)

    csv_path = outdir / CSV_FILENAME
    df.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path} with {df.shape[0]} rows.")

    _write_spec(
        outdir=outdir,
        df=df,
        r_values=r_values,
        T_values=T_values,
        base_config=base_config,
        qpr_table=qpr_table,
        jobs=jobs,
    )
    print(f"Wrote {outdir / SPEC_RELATIVE_PATH}.")


if __name__ == "__main__":
    main()
