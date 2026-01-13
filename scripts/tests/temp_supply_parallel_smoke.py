#!/usr/bin/env python3
"""Smoke test for temp_supply parallel runs via run_temp_supply_sweep.sh."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


OUTDIR_PATTERN = re.compile(r"->\s*(.+?)\s*\(batch=", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_temp_token(value: str) -> str:
    text = value.strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _validate_cases(repo_root: Path, cases: Iterable[Tuple[str, str, str]]) -> None:
    missing = []
    for t_raw, _, _ in cases:
        t_token = _normalize_temp_token(t_raw)
        table = repo_root / "data" / f"mars_temperature_T{t_token}p0K.csv"
        parquet_path = table.with_suffix(".parquet")
        if parquet_path.exists():
            if not table.exists() or parquet_path.stat().st_mtime >= table.stat().st_mtime:
                table = parquet_path
        if not table.exists():
            missing.append(str(table))
    if missing:
        joined = "\n  - ".join(missing)
        raise FileNotFoundError(f"Missing temperature tables:\n  - {joined}")


def _parse_outdir(output: str) -> Optional[Path]:
    outdir = None
    for line in output.splitlines():
        match = OUTDIR_PATTERN.search(line)
        if match:
            outdir = match.group(1).strip()
    return Path(outdir).expanduser() if outdir else None


def _run_case(
    *,
    case_id: str,
    t_value: str,
    eps_value: str,
    tau_value: str,
    i0_value: str,
    script_path: Path,
    env: Dict[str, str],
    log_dir: Path,
) -> Dict[str, object]:
    cmd = [str(script_path), "--run-one"]
    result = subprocess.run(
        cmd,
        cwd=_repo_root(),
        env=env,
        capture_output=True,
        text=True,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    log_path = log_dir / f"{case_id}.log"
    log_path.write_text(combined, encoding="utf-8")

    outdir = _parse_outdir(combined)
    summary_ok = False
    series_ok = False
    if outdir is not None:
        summary_ok = (outdir / "summary.json").exists()
        series_ok = (outdir / "series" / "run.parquet").exists()

    return {
        "case_id": case_id,
        "t": t_value,
        "eps": eps_value,
        "tau": tau_value,
        "i0": i0_value,
        "returncode": result.returncode,
        "outdir": str(outdir) if outdir else None,
        "summary_exists": summary_ok,
        "series_exists": series_ok,
        "log_path": str(log_path),
    }


def _build_case_id(t_value: str, eps_value: str, tau_value: str, i0_value: str) -> str:
    return f"T{t_value}_eps{eps_value}_tau{tau_value}_i0{i0_value}".replace(".", "p")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--sweep-tag", default="temp_supply_parallel_smoke", help="Sweep tag.")
    ap.add_argument(
        "--base-config",
        default="configs/sweep_temp_supply/temp_supply_T4000_eps1.yml",
        help="BASE_CONFIG for run_temp_supply_sweep.sh.",
    )
    ap.add_argument(
        "--overrides",
        default="",
        help="EXTRA_OVERRIDES_FILE path (optional).",
    )
    ap.add_argument("--jobs", type=int, default=2, help="Concurrent jobs to run.")
    ap.add_argument("--t-end-years", type=float, default=2.0e-4, help="Short integration span.")
    ap.add_argument("--i0", default="0.05", help="dynamics.i0 for run-one cases.")
    ap.add_argument(
        "--case",
        action="append",
        nargs=3,
        metavar=("T", "EPS", "TAU"),
        help="Add a case (repeatable).",
    )
    args = ap.parse_args()

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "research" / "run_temp_supply_sweep.sh"
    if not script_path.exists():
        raise FileNotFoundError(f"run_temp_supply_sweep.sh not found: {script_path}")

    cases: List[Tuple[str, str, str]] = []
    if args.case:
        for t_raw, eps_raw, tau_raw in args.case:
            cases.append((_normalize_temp_token(str(t_raw)), str(eps_raw), str(tau_raw)))
    else:
        cases = [("2000", "1.0", "1.0"), ("2100", "1.0", "1.0")]

    _validate_cases(repo_root, cases)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_outdir = Path(args.out_root).resolve() / f"temp_supply_parallel_smoke_{timestamp}"
    base_outdir.mkdir(parents=True, exist_ok=True)
    log_dir = base_outdir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    common_env = os.environ.copy()
    common_env.update(
        {
            "OUT_ROOT": str(base_outdir),
            "SWEEP_TAG": str(args.sweep_tag),
            "BASE_CONFIG": str(Path(args.base_config).resolve()),
            "RUN_ONE_MODE": "1",
            "SKIP_PIP": "1",
            "HOOKS_ENABLE": "",
            "PLOT_ENABLE": "0",
            "EVAL": "0",
            "COOL_TO_K": "none",
            "T_END_SHORT_YEARS": f"{args.t_end_years}",
            "FORCE_STREAMING_OFF": "1",
            "IO_STREAMING": "off",
        }
    )
    if args.overrides:
        common_env["EXTRA_OVERRIDES_FILE"] = str(Path(args.overrides).resolve())

    results: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        future_map = {}
        for t_value, eps_value, tau_value in cases:
            case_id = _build_case_id(t_value, eps_value, tau_value, str(args.i0))
            env = dict(common_env)
            env.update(
                {
                    "RUN_ONE_T": t_value,
                    "RUN_ONE_EPS": eps_value,
                    "RUN_ONE_TAU": tau_value,
                    "RUN_ONE_I0": str(args.i0),
                }
            )
            future = executor.submit(
                _run_case,
                case_id=case_id,
                t_value=t_value,
                eps_value=eps_value,
                tau_value=tau_value,
                i0_value=str(args.i0),
                script_path=script_path,
                env=env,
                log_dir=log_dir,
            )
            future_map[future] = case_id

        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda rec: rec.get("case_id", ""))
    summary = {
        "timestamp": timestamp,
        "out_root": str(base_outdir),
        "cases": results,
    }
    summary_path = base_outdir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    failures = []
    for rec in results:
        if rec.get("returncode") != 0:
            failures.append(f"{rec.get('case_id')} rc={rec.get('returncode')}")
        elif not rec.get("summary_exists") or not rec.get("series_exists"):
            failures.append(f"{rec.get('case_id')} missing outputs")

    if failures:
        print("[error] temp_supply parallel smoke failed:")
        for msg in failures:
            print(f"  - {msg}")
        print(f"[error] summary: {summary_path}")
        return 2

    print(f"[done] summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
