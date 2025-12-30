#!/usr/bin/env python3
"""Run sweep-parallel on/off and validate structural outputs."""
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

ALLOWED_STATUSES = {"success", "cached"}
REQUIRED_KEYS = {"case_status", "M_loss"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _output_stub(map_id: str) -> str:
    key = (map_id or "").strip().lower()
    if key.startswith("map"):
        return key
    return f"map{key}"


def _parse_triplet(values: Iterable[str], default: Tuple[float, float, int]) -> Tuple[float, float, int]:
    vals = list(values)
    if len(vals) == 3:
        return float(vals[0]), float(vals[1]), int(vals[2])
    return default


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

    return {
        "label": label,
        "returncode": result.returncode,
        "elapsed_sec": elapsed,
        "outdir": str(outdir),
        "results_csv": str(result_csv),
    }


def _load_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _resolve_outdir(raw: Optional[str], repo_root: Path) -> Optional[Path]:
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _expected_row_count(rows: List[Dict[str, str]]) -> int:
    if not rows:
        return 0
    x_values = {row.get("param_x_value", "").strip() for row in rows if row.get("param_x_value")}
    y_values = {row.get("param_y_value", "").strip() for row in rows if row.get("param_y_value")}
    variant_labels = {row.get("variant_label", "").strip() for row in rows if "variant_label" in row}
    if not variant_labels:
        variant_labels = {"default"}
    return len(x_values) * len(y_values) * len(variant_labels)


def _check_mass_budget(path: Path) -> Optional[str]:
    if not path.exists():
        return "mass_budget.csv missing"
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return f"mass_budget.csv read failed: {exc}"
    if len(lines) < 2:
        return "mass_budget.csv has no data rows"
    return None


def _check_outputs(row: Dict[str, str], repo_root: Path) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    status = (row.get("run_status") or "").strip().lower()
    if status not in ALLOWED_STATUSES:
        errors.append(f"run_status={status or 'missing'}")
        return errors, warnings

    outdir = _resolve_outdir(row.get("outdir"), repo_root)
    if outdir is None:
        errors.append("outdir missing")
        return errors, warnings
    if not outdir.exists():
        errors.append(f"outdir missing: {outdir}")
        return errors, warnings

    summary_path = outdir / "summary.json"
    series_path = outdir / "series" / "run.parquet"
    budget_path = outdir / "checks" / "mass_budget.csv"
    completion_path = outdir / "case_completed.json"

    if not summary_path.exists():
        errors.append(f"summary.json missing: {summary_path}")
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"summary.json read failed: {summary_path} ({exc})")
        else:
            missing_keys = REQUIRED_KEYS - set(summary.keys())
            if missing_keys:
                errors.append(f"summary.json missing keys: {sorted(missing_keys)}")
    if not series_path.exists():
        errors.append(f"series/run.parquet missing: {series_path}")
    else:
        try:
            if series_path.stat().st_size == 0:
                errors.append(f"series/run.parquet empty: {series_path}")
        except OSError as exc:
            errors.append(f"series/run.parquet stat failed: {series_path} ({exc})")
    if not completion_path.exists():
        errors.append(f"case_completed.json missing: {completion_path}")
    budget_issue = _check_mass_budget(budget_path)
    if budget_issue:
        warnings.append(f"{budget_issue}: {budget_path}")
    return errors, warnings


def _validate_rows(rows: List[Dict[str, str]], repo_root: Path) -> Tuple[List[str], List[str], Dict[str, Any]]:
    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {
        "row_count": len(rows),
        "expected_row_count": _expected_row_count(rows),
        "duplicate_case_ids": [],
        "duplicate_outdirs": [],
        "invalid_status_count": 0,
        "missing_param_values": 0,
    }

    if not rows:
        errors.append("results CSV missing or empty")
        return errors, warnings, details

    case_ids = [row.get("case_id", "").strip() for row in rows]
    outdirs = [row.get("outdir", "").strip() for row in rows]
    dup_case_ids = sorted({cid for cid in case_ids if cid and case_ids.count(cid) > 1})
    dup_outdirs = sorted({od for od in outdirs if od and outdirs.count(od) > 1})
    if dup_case_ids:
        details["duplicate_case_ids"] = dup_case_ids
        errors.append(f"duplicate case_id count={len(dup_case_ids)}")
    if dup_outdirs:
        details["duplicate_outdirs"] = dup_outdirs
        errors.append(f"duplicate outdir count={len(dup_outdirs)}")

    expected = details["expected_row_count"]
    if expected and expected != len(rows):
        errors.append(f"row_count mismatch: expected={expected} actual={len(rows)}")

    missing_params = 0
    for row in rows:
        if not row.get("param_x_value") or not row.get("param_y_value"):
            missing_params += 1
    if missing_params:
        details["missing_param_values"] = missing_params
        errors.append(f"missing param values: {missing_params}")

    for row in rows:
        row_errors, row_warnings = _check_outputs(row, repo_root)
        if row_errors:
            case_id = row.get("case_id", "unknown")
            errors.append(f"{case_id}: " + "; ".join(row_errors))
        warnings.extend(row_warnings)

    return errors, warnings, details


def _load_validation(outdir: Path, stub: str) -> Optional[Dict[str, Any]]:
    path = outdir / f"{stub}_validation.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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
    qpr_table_path = Path(args.qpr_table)
    if not qpr_table_path.is_absolute():
        qpr_table_path = (repo_root / qpr_table_path).resolve()
    if not qpr_table_path.exists():
        raise FileNotFoundError(f"Q_pr table not found: {qpr_table_path}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_outdir = Path(args.out_root).resolve() / f"sweep_parallel_smoke_{timestamp}"
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
        "errors": [],
        "warnings": [],
        "cross_checks": {},
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

    summary_path = base_outdir / "smoke_check_summary.json"
    overall_errors: List[str] = []
    overall_warnings: List[str] = []

    case_rows: Dict[str, List[Dict[str, str]]] = {}
    for result in results["cases"]:
        label = result["label"]
        if result["returncode"] != 0:
            overall_errors.append(f"{label} failed (rc={result['returncode']})")
            continue
        csv_path = Path(result["results_csv"])
        rows = _load_rows(csv_path)
        case_rows[label] = rows
        errors, warnings, details = _validate_rows(rows, repo_root)
        result["checks"] = details
        if errors:
            result["errors"] = errors
            overall_errors.extend([f"{label}: {msg}" for msg in errors])
        if warnings:
            result["warnings"] = warnings
            overall_warnings.extend([f"{label}: {msg}" for msg in warnings])
        validation = _load_validation(Path(result["outdir"]), _output_stub(str(args.map)))
        if validation:
            result["validation"] = validation
            if not (validation.get("low_temp_band", {}).get("ok", True)):
                overall_warnings.append(f"{label}: low_temp_band validation not ok")
            if not (validation.get("mass_per_r2", {}).get("ok", True)):
                overall_warnings.append(f"{label}: mass_per_r2 validation not ok")

    if case_rows.get("sweep_parallel_on") and case_rows.get("sweep_parallel_off"):
        on_ids = {row.get("case_id", "") for row in case_rows["sweep_parallel_on"] if row.get("case_id")}
        off_ids = {row.get("case_id", "") for row in case_rows["sweep_parallel_off"] if row.get("case_id")}
        missing_in_on = sorted(off_ids - on_ids)
        missing_in_off = sorted(on_ids - off_ids)
        results["cross_checks"] = {
            "case_id_mismatch": {
                "missing_in_on": missing_in_on,
                "missing_in_off": missing_in_off,
            }
        }
        if missing_in_on or missing_in_off:
            overall_errors.append("case_id sets differ between parallel on/off")

    results["errors"] = overall_errors
    results["warnings"] = overall_warnings
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    if overall_errors:
        print("[error] sweep parallel smoke failed")
        for msg in overall_errors:
            print(f"  - {msg}")
        print(f"[error] summary: {summary_path}")
        return 2

    print(f"[done] summary: {summary_path}")
    if overall_warnings:
        print("[warn] warnings detected (see summary for details)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
