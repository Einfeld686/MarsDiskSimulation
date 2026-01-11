#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

SUMMARY_KEYS = [
    "M_loss",
    "M_out_cum",
    "M_sink_cum",
    "mass_budget_max_error_percent",
    "dt_over_t_blow_median",
    "beta_at_smin_config",
    "beta_at_smin_effective",
]

SUMMARY_RTOL = 1.0e-6
SUMMARY_ATOL = 1.0e-12
SERIES_RTOL = 1.0e-6
SERIES_ATOL = 1.0e-10
MASS_BUDGET_TOL = 0.5


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


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _compare_numeric(ref: np.ndarray, new: np.ndarray, *, rtol: float, atol: float) -> tuple[float, bool]:
    ref = np.asarray(ref, dtype=float)
    new = np.asarray(new, dtype=float)
    if ref.shape != new.shape:
        return float("inf"), False
    nan_mask = np.isnan(ref) & np.isnan(new)
    diff = np.abs(new - ref)
    diff[nan_mask] = 0.0
    diff[np.isnan(diff)] = float("inf")
    tol = atol + rtol * np.abs(ref)
    valid = ~nan_mask
    diff_valid = diff[valid]
    tol_valid = tol[valid]
    if diff_valid.size:
        comp = diff_valid <= tol_valid
        comp = comp & np.isfinite(tol_valid)
        ok = bool(np.all(comp))
        max_diff = float(np.nanmax(diff_valid))
    else:
        ok = True
        max_diff = 0.0
    return max_diff, ok


def _compare_series(
    ref_df: pd.DataFrame,
    new_df: pd.DataFrame,
    *,
    series_rtol: float,
    series_atol: float,
    include_cols: list[str] | None,
    exclude_cols: set[str],
    include_non_numeric: bool,
) -> tuple[dict[str, float], bool, list[str], list[str], list[str]]:
    diffs: dict[str, float] = {}
    ok = True
    missing_cols: list[str] = []
    skipped_cols: list[str] = []

    ref_cols = set(ref_df.columns)
    new_cols = set(new_df.columns)
    if include_cols is None:
        target_cols = sorted(ref_cols.union(new_cols))
    else:
        target_cols = list(include_cols)
    if exclude_cols:
        target_cols = [col for col in target_cols if col not in exclude_cols]

    missing_cols = sorted([col for col in target_cols if col not in ref_cols or col not in new_cols])
    if missing_cols:
        ok = False

    compare_cols = [col for col in target_cols if col in ref_cols and col in new_cols]
    for col in compare_cols:
        ref_col = ref_df[col]
        new_col = new_df[col]
        if is_bool_dtype(ref_col) or is_bool_dtype(new_col):
            mismatch = int((ref_col.fillna(False) != new_col.fillna(False)).sum())
            diffs[col] = float(mismatch)
            ok = ok and mismatch == 0
            continue
        if is_numeric_dtype(ref_col) and is_numeric_dtype(new_col):
            max_diff, col_ok = _compare_numeric(
                ref_col.to_numpy(),
                new_col.to_numpy(),
                rtol=series_rtol,
                atol=series_atol,
            )
            diffs[col] = max_diff
            ok = ok and col_ok
            continue
        if include_cols is None and not include_non_numeric:
            skipped_cols.append(col)
            continue
        mismatch = int((ref_col.fillna("__nan__") != new_col.fillna("__nan__")).sum())
        diffs[col] = float(mismatch)
        ok = ok and mismatch == 0

    return diffs, ok, missing_cols, compare_cols, skipped_cols


def _compare_summary(
    ref: dict[str, Any],
    new: dict[str, Any],
    *,
    summary_rtol: float,
    summary_atol: float,
    summary_keys: list[str],
) -> tuple[dict[str, float], bool, list[str]]:
    diffs: dict[str, float] = {}
    ok = True
    missing: list[str] = []
    for key in summary_keys:
        if key not in ref or key not in new:
            missing.append(key)
            ok = False
            continue
        try:
            ref_val = float(ref[key])
            new_val = float(new[key])
        except (TypeError, ValueError):
            ok = False
            diffs[key] = float("inf")
            continue
        max_diff, col_ok = _compare_numeric(
            np.array([ref_val]),
            np.array([new_val]),
            rtol=summary_rtol,
            atol=summary_atol,
        )
        diffs[key] = max_diff
        ok = ok and col_ok
    return diffs, ok, missing


def _read_mass_budget(path: Path) -> tuple[float, bool]:
    path = _resolve_table_path(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "error_percent" not in df.columns:
        return float("inf"), False
    max_err = float(df["error_percent"].max()) if not df.empty else 0.0
    return max_err, max_err <= MASS_BUDGET_TOL


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# compare_zero_d_outputs: {payload.get('case_id', '')}",
        "",
        f"status: {payload.get('status', 'unknown')}",
        "",
        "## files",
        f"- ref: {payload.get('ref_dir', '')}",
        f"- new: {payload.get('new_dir', '')}",
    ]
    missing = payload.get("missing_files", [])
    if missing:
        lines.extend(["", "## missing files"] + [f"- {item}" for item in missing])
    lines.append("")
    lines.append("## summary diffs")
    for key, val in (payload.get("summary_diff_max", {}) or {}).items():
        lines.append(f"- {key}: {val}")
    lines.append("")
    lines.append("## series diffs")
    for key, val in (payload.get("series_diff_max", {}) or {}).items():
        lines.append(f"- {key}: {val}")
    lines.append("")
    lines.append("## mass budget")
    mb = payload.get("mass_budget_max_error_percent", {}) or {}
    lines.append(f"- ref: {mb.get('ref')}")
    lines.append(f"- new: {mb.get('new')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare zero-D outputs between two runs.")
    parser.add_argument("--ref", required=True, help="Reference output directory")
    parser.add_argument("--new", required=True, help="New output directory")
    parser.add_argument("--case-id", required=True, help="Case identifier")
    parser.add_argument("--outdir", help="Output directory for compare reports")
    parser.add_argument("--summary-keys", help="Comma-separated summary keys to compare")
    parser.add_argument("--summary-rtol", type=float, default=SUMMARY_RTOL)
    parser.add_argument("--summary-atol", type=float, default=SUMMARY_ATOL)
    parser.add_argument("--series-rtol", type=float, default=SERIES_RTOL)
    parser.add_argument("--series-atol", type=float, default=SERIES_ATOL)
    parser.add_argument("--series-include", help="Comma-separated series columns to compare")
    parser.add_argument("--series-exclude", help="Comma-separated series columns to skip")
    parser.add_argument("--include-non-numeric", action="store_true", help="Compare non-numeric series columns")
    args = parser.parse_args()

    ref_dir = Path(args.ref)
    new_dir = Path(args.new)
    outdir = Path(args.outdir) if args.outdir else Path("out/plan/physics_step_baseline") / args.case_id

    missing_files: list[str] = []
    summary_ref_path = ref_dir / "summary.json"
    summary_new_path = new_dir / "summary.json"
    series_ref_path = ref_dir / "series" / "run.parquet"
    series_new_path = new_dir / "series" / "run.parquet"
    budget_ref_path = _resolve_table_path(ref_dir / "checks" / "mass_budget.csv")
    budget_new_path = _resolve_table_path(new_dir / "checks" / "mass_budget.csv")

    for path in [summary_ref_path, summary_new_path, series_ref_path, series_new_path, budget_ref_path, budget_new_path]:
        if not path.exists():
            missing_files.append(str(path))

    summary_diff: dict[str, float] = {}
    series_diff: dict[str, float] = {}
    mass_budget_max: dict[str, float] = {}
    status = "pass"
    exit_code = 0

    summary_keys = SUMMARY_KEYS
    if args.summary_keys:
        summary_keys = [item for item in args.summary_keys.split(",") if item]

    series_include = None
    if args.series_include:
        series_include = [item for item in args.series_include.split(",") if item]
    series_exclude = set(item for item in (args.series_exclude or "").split(",") if item)

    if missing_files:
        status = "fail"
        exit_code = 2
    else:
        ref_summary = _read_json(summary_ref_path)
        new_summary = _read_json(summary_new_path)
        summary_diff, summary_ok, summary_missing = _compare_summary(
            ref_summary,
            new_summary,
            summary_rtol=args.summary_rtol,
            summary_atol=args.summary_atol,
            summary_keys=summary_keys,
        )
        if summary_missing:
            missing_files.extend([f"summary.json:{k}" for k in summary_missing])
        if not summary_ok:
            status = "fail"
            exit_code = max(exit_code, 3)

        ref_series = pd.read_parquet(series_ref_path)
        new_series = pd.read_parquet(series_new_path)
        if len(ref_series) != len(new_series):
            status = "fail"
            exit_code = max(exit_code, 3)
        series_diff, series_ok, series_missing, series_cols_compared, series_cols_skipped = _compare_series(
            ref_series,
            new_series,
            series_rtol=args.series_rtol,
            series_atol=args.series_atol,
            include_cols=series_include,
            exclude_cols=series_exclude,
            include_non_numeric=args.include_non_numeric,
        )
        if series_missing:
            missing_files.extend([f"series/run.parquet:{col}" for col in series_missing])
        if not series_ok:
            status = "fail"
            exit_code = max(exit_code, 3)

        ref_budget_max, ref_budget_ok = _read_mass_budget(budget_ref_path)
        new_budget_max, new_budget_ok = _read_mass_budget(budget_new_path)
        mass_budget_max = {"ref": ref_budget_max, "new": new_budget_max}
        if not (ref_budget_ok and new_budget_ok):
            status = "fail"
            exit_code = max(exit_code, 3)

    payload = {
        "status": status,
        "case_id": args.case_id,
        "ref_dir": str(ref_dir),
        "new_dir": str(new_dir),
        "missing_files": missing_files,
        "summary_diff_max": summary_diff,
        "series_diff_max": series_diff,
        "summary_keys_compared": summary_keys,
        "series_columns_compared": series_cols_compared if not missing_files else [],
        "series_columns_skipped": series_cols_skipped if not missing_files else [],
        "tolerances": {
            "summary_rtol": args.summary_rtol,
            "summary_atol": args.summary_atol,
            "series_rtol": args.series_rtol,
            "series_atol": args.series_atol,
        },
        "mass_budget_max_error_percent": mass_budget_max,
    }

    _write_json(outdir / "compare.json", payload)
    _write_md(outdir / "compare.md", payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
