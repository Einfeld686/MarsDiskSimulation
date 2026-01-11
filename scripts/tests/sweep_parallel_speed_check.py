#!/usr/bin/env python3
"""Compare wall time for sweep-parallel on/off runs."""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import pandas as pd


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _output_stub(map_id: str) -> str:
    key = (map_id or "").strip().lower()
    if key.startswith("map"):
        return key
    return f"map{key}"


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


def _load_status_counts(path: Path) -> Dict[str, int]:
    path = _resolve_table_path(path)
    if not path.exists():
        return {}
    counts: Dict[str, int] = {}
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
        for status in df.get("run_status", pd.Series(dtype=str)).astype(str).str.strip().str.lower():
            counts[status] = counts.get(status, 0) + 1
        return counts
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            status = (row.get("run_status") or "unknown").strip().lower()
            counts[status] = counts.get(status, 0) + 1
    return counts


def _run_case(
    *,
    label: str,
    map_id: str,
    base_config: str,
    outdir: Path,
    jobs: int,
    rrm_spec: Tuple[float, float, int],
    tm_spec: Tuple[float, float, int],
    qpr_table: str,
    env: Dict[str, str],
) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "scripts/sweeps/sweep_heatmaps.py",
        "--map",
        map_id,
        "--base",
        base_config,
        "--outdir",
        str(outdir),
        "--jobs",
        str(max(jobs, 1)),
        "--rRM",
        str(rrm_spec[0]),
        str(rrm_spec[1]),
        str(rrm_spec[2]),
        "--TM",
        str(tm_spec[0]),
        str(tm_spec[1]),
        str(tm_spec[2]),
        "--qpr_table",
        qpr_table,
    ]

    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=_repo_root(), env=env, check=False)
    elapsed = time.perf_counter() - start

    stub = _output_stub(map_id)
    result_csv = outdir / stub / f"{stub}.csv"
    status_counts = _load_status_counts(result_csv)

    return {
        "label": label,
        "returncode": result.returncode,
        "elapsed_sec": elapsed,
        "outdir": str(outdir),
        "results_csv": str(result_csv),
        "status_counts": status_counts,
    }


def _parse_triplet(values: Iterable[str], default: Tuple[float, float, int]) -> Tuple[float, float, int]:
    vals = list(values)
    if len(vals) == 3:
        return float(vals[0]), float(vals[1]), int(vals[2])
    return default


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", default="1", help="Sweep map id (default: 1).")
    ap.add_argument("--base", default="configs/map_sweep_base.yml", help="Base YAML config.")
    ap.add_argument(
        "--qpr-table",
        default="marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv",
        help="Q_pr table path to inject into sweep cases.",
    )
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--parallel-jobs", type=int, default=4, help="Worker count for parallel run.")
    ap.add_argument(
        "--rRM",
        nargs=3,
        metavar=("MIN", "MAX", "N"),
        default=None,
        help="r/R_M range for the test sweep (min max count).",
    )
    ap.add_argument(
        "--TM",
        nargs=3,
        metavar=("MIN", "MAX", "N"),
        default=None,
        help="T_M range for the test sweep (min max count).",
    )
    ap.add_argument("--no-quiet", action="store_true", help="Show marsdisk logs.")
    args = ap.parse_args()

    repo_root = _repo_root()
    base_config_path = Path(args.base)
    if not base_config_path.is_absolute():
        base_config_path = (repo_root / base_config_path).resolve()
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")
    qpr_table_path = _resolve_table_path(Path(args.qpr_table))
    if not qpr_table_path.is_absolute():
        qpr_table_path = (repo_root / qpr_table_path).resolve()
    if not qpr_table_path.exists():
        raise FileNotFoundError(f"Q_pr table not found: {qpr_table_path}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_outdir = Path(args.out_root).resolve() / f"sweep_parallel_speed_{timestamp}"
    base_outdir.mkdir(parents=True, exist_ok=True)

    rrm_spec = _parse_triplet(args.rRM or (), (1.0, 1.2, 2))
    tm_spec = _parse_triplet(args.TM or (), (2000.0, 2100.0, 2))

    common_env = os.environ.copy()
    repo_root_str = str(repo_root)
    existing_pythonpath = common_env.get("PYTHONPATH")
    if existing_pythonpath:
        if repo_root_str not in existing_pythonpath.split(os.pathsep):
            common_env["PYTHONPATH"] = f"{repo_root_str}{os.pathsep}{existing_pythonpath}"
    else:
        common_env["PYTHONPATH"] = repo_root_str
    common_env.setdefault("FORCE_STREAMING_OFF", "1")
    common_env.setdefault("IO_STREAMING", "off")
    common_env.setdefault("CELL_THREAD_LIMIT", "1")
    common_env.setdefault("NUMBA_NUM_THREADS", "1")
    common_env.setdefault("OMP_NUM_THREADS", "1")
    common_env.setdefault("MKL_NUM_THREADS", "1")
    common_env.setdefault("OPENBLAS_NUM_THREADS", "1")
    common_env.setdefault("NUMEXPR_NUM_THREADS", "1")
    common_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")

    if args.no_quiet:
        common_env.pop("MARSDISK_LOG_LEVEL", None)
    else:
        common_env.setdefault("MARSDISK_LOG_LEVEL", "warning")

    results = {
        "map": str(args.map),
        "base": str(base_config_path),
        "qpr_table": str(qpr_table_path),
        "timestamp": timestamp,
        "cases": [],
        "rRM": rrm_spec,
        "TM": tm_spec,
    }

    print("[info] running sweep-parallel ON case...")
    on_outdir = base_outdir / "sweep_parallel_on"
    on_result = _run_case(
        label="sweep_parallel_on",
        map_id=str(args.map),
        base_config=str(base_config_path),
        outdir=on_outdir,
        jobs=max(args.parallel_jobs, 1),
        rrm_spec=rrm_spec,
        tm_spec=tm_spec,
        qpr_table=str(qpr_table_path),
        env=common_env,
    )
    results["cases"].append(on_result)

    print("[info] running sweep-parallel OFF case...")
    off_outdir = base_outdir / "sweep_parallel_off"
    off_result = _run_case(
        label="sweep_parallel_off",
        map_id=str(args.map),
        base_config=str(base_config_path),
        outdir=off_outdir,
        jobs=1,
        rrm_spec=rrm_spec,
        tm_spec=tm_spec,
        qpr_table=str(qpr_table_path),
        env=common_env,
    )
    results["cases"].append(off_result)

    speedup = None
    if on_result["returncode"] == 0 and off_result["returncode"] == 0:
        if on_result["elapsed_sec"] > 0:
            speedup = off_result["elapsed_sec"] / on_result["elapsed_sec"]
    results["speedup_off_over_on"] = speedup

    summary_path = base_outdir / "speed_check_summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    errors = []
    for result in (on_result, off_result):
        if result["returncode"] != 0:
            errors.append(f"{result['label']} failed (rc={result['returncode']})")
    if errors:
        print("[error] sweep speed check failed:")
        for msg in errors:
            print(f"  - {msg}")
        print(f"[error] summary: {summary_path}")
        return 2

    print(f"[done] summary: {summary_path}")
    if speedup is not None:
        print(f"[done] speedup(off/on) = {speedup:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
