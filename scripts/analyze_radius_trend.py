#!/usr/bin/env python3
"""Radius sweep helper to inspect Ω(r), t_blow, and dM/dt trends.

The script reuses the existing 0D runner to execute a small set of
single-radius cases.  For each radius it reads the ``series/run.parquet``
time series and the corresponding ``summary.json`` to collect diagnostic
quantities:

* instantaneous outflow rates (``M_out_dot``, ``M_sink_dot``,
  ``dM_dt_surface_total``)
* orbital frequency ``Ω`` and blow-out timescale ``t_blow``
* β diagnostics and effective size thresholds from the summary

The aggregated results are written to ``radius_sweep_metrics.csv`` within
the chosen output directory.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk import constants
DEFAULT_CONFIG = REPO_ROOT / "configs" / "base.yml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "analysis" / "radius_sweep"

YAML_LOADER = YAML(typ="safe")
YAML_DUMPER = YAML()
YAML_DUMPER.default_flow_style = False


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Base YAML configuration to clone for each radius (default: configs/base.yml).",
    )
    parser.add_argument(
        "--radii",
        type=float,
        nargs="+",
        default=[1.4, 1.6, 1.8, 2.0, 2.2],
        help="List of orbital radii in units of R_Mars for the sweep.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory to store per-radius runs and the aggregated CSV.",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Skip running cases whose outdir already contains results.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = YAML_LOADER.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration at {path} did not parse to a mapping.")
    return data


def write_config(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        YAML_DUMPER.dump(data, handle)


def run_case(config_path: Path) -> None:
    cmd = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path)]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def collect_metrics(case_dir: Path) -> dict[str, float | str]:
    series_path = case_dir / "series" / "run.parquet"
    summary_path = case_dir / "summary.json"
    if not series_path.exists():
        raise FileNotFoundError(f"Missing time series at {series_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing summary JSON at {summary_path}")

    df = pd.read_parquet(series_path)
    if df.empty:
        raise ValueError(f"Time series at {series_path} contains no records.")
    row = df.iloc[-1]
    dt = float(row.get("dt", float("nan")))
    t_blow = float(row.get("t_blow_s", row.get("t_blow", 0.0)))
    Omega = float(row.get("Omega_s", float("nan")))
    if not math.isfinite(Omega):
        Omega = float("nan") if t_blow == 0.0 else 1.0 / t_blow
    M_sink_dot = float(row.get("M_sink_dot", 0.0))
    dM_dt_total = float(
        row.get("dM_dt_surface_total", row["M_out_dot"] + M_sink_dot)
    )
    dt_over_t_blow = float(row.get("dt_over_t_blow", float("inf")))
    if not math.isfinite(dt_over_t_blow):
        dt_over_t_blow = float("inf") if t_blow == 0.0 else dt / t_blow
    fast_ratio = float(row.get("fast_blowout_ratio", dt_over_t_blow))
    fast_factor = float(row.get("fast_blowout_factor", 1.0))
    fast_corrected_val = row.get("fast_blowout_corrected", False)
    fast_corrected = False if pd.isna(fast_corrected_val) else bool(fast_corrected_val)
    flag_gt3_val = row.get("fast_blowout_flag_gt3", False)
    flag_gt3 = False if pd.isna(flag_gt3_val) else bool(flag_gt3_val)
    flag_gt10_val = row.get("fast_blowout_flag_gt10", False)
    flag_gt10 = False if pd.isna(flag_gt10_val) else bool(flag_gt10_val)
    dSigma_blow = float(row.get("dSigma_dt_blowout", float("nan")))
    dSigma_sink = float(row.get("dSigma_dt_sinks", float("nan")))
    dSigma_total = float(row.get("dSigma_dt_total", float("nan")))
    n_substeps_val = row.get("n_substeps", 1)
    n_substeps = int(n_substeps_val) if pd.notna(n_substeps_val) else 1
    chi_blow_eff = float(row.get("chi_blow_eff", float("nan")))
    fast_factor_avg = float(row.get("fast_blowout_factor_avg", float("nan")))

    summary = json.loads(summary_path.read_text())

    tau_los = float(row.get("tau_los_mars", row.get("tau", float("nan"))))
    record = {
        "case_dir": str(case_dir),
        "time_final_s": float(row["time"]),
        "M_loss_cum_final": float(row["M_loss_cum"]),
        "M_out_dot": float(row["M_out_dot"]),
        "M_sink_dot": M_sink_dot,
        "dM_dt_surface_total": dM_dt_total,
        "Omega_s": Omega,
        "t_blow_s": t_blow,
        "t_orb_s": float(row.get("t_orb_s", float("nan"))),
        "dt_s": dt,
        "dt_over_t_blow": dt_over_t_blow,
        "fast_blowout_ratio": fast_ratio,
        "fast_blowout_factor": fast_factor,
        "fast_blowout_corrected": fast_corrected,
        "fast_blowout_flag_gt3": flag_gt3,
        "fast_blowout_flag_gt10": flag_gt10,
        "dSigma_dt_blowout": dSigma_blow,
        "dSigma_dt_sinks": dSigma_sink,
        "dSigma_dt_total": dSigma_total,
        "n_substeps": n_substeps,
        "chi_blow_eff": chi_blow_eff,
        "fast_blowout_factor_avg": fast_factor_avg,
        "tau_final": tau_los,
        "tau_los_mars": tau_los,
        "s_min_series": float(row["s_min"]),
        "s_min_summary": float(summary.get("s_min_effective", row["s_min"])),
        "beta_at_smin_effective": float(summary.get("beta_at_smin_effective", float("nan"))),
        "beta_threshold": float(summary.get("beta_threshold", float("nan"))),
        "case_status": summary.get("case_status", ""),
    }
    return record


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)

    base_config = load_config(args.config)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    configs_dir = output_root / "configs"
    results: list[dict[str, float | str]] = []

    for radius_rm in args.radii:
        r_m = float(radius_rm * constants.R_MARS)
        case_id = f"r_{radius_rm:.3f}RM"
        case_dir = output_root / case_id
        case_config = copy.deepcopy(base_config)

        geometry = case_config.setdefault("geometry", {})
        geometry["mode"] = geometry.get("mode", "0D")
        geometry["r"] = r_m

        io_section = case_config.setdefault("io", {})
        io_section["outdir"] = str(case_dir)

        config_path = configs_dir / f"{case_id}.yml"
        write_config(case_config, config_path)

        series_path = case_dir / "series" / "run.parquet"
        if not (args.reuse and series_path.exists()):
            run_case(config_path)

        record = collect_metrics(case_dir)
        record.update(
            {
                "r_over_RM": radius_rm,
                "r_m": r_m,
            }
        )
        results.append(record)

    if not results:
        print("No results collected; check input radii.", file=sys.stderr)
        return

    df = pd.DataFrame(results)
    df.sort_values("r_over_RM", inplace=True)
    if "dt_over_t_blow" in df.columns:
        for threshold in (3.0, 10.0):
            column = f"flag_dt_over_t_blow_gt{int(threshold)}"
            df[column] = df["dt_over_t_blow"] > threshold
            flagged = df[df[column]]
            if not flagged.empty:
                cases = ", ".join(
                    f"r={row.r_over_RM:.2f} (dt/t_blow={row.dt_over_t_blow:.2f}, corrected={row.fast_blowout_corrected})"
                    for row in flagged.itertuples()
                )
                print(
                    f"WARNING: dt/t_blow exceeds {threshold:g} for cases: {cases}."
                    " Consider enabling io.substep_fast_blowout or lowering dt."
                )
    csv_path = output_root / "radius_sweep_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"Wrote aggregated metrics to {csv_path}")


if __name__ == "__main__":
    main()
