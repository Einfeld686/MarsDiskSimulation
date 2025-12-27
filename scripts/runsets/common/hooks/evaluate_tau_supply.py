#!/usr/bin/env python3
"""Run tau supply evaluation and write results to checks/tau_supply_eval.json."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _env_or_default(name: str, default: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None, help="Run directory (defaults to RUN_DIR env)")
    ap.add_argument("--window-spans", type=str, default=None, help="Window spans (override EVAL_WINDOW_SPANS)")
    ap.add_argument("--min-duration-days", type=str, default=None, help="Min duration (override EVAL_MIN_DURATION_DAYS)")
    ap.add_argument("--threshold-factor", type=str, default=None, help="Threshold factor (override EVAL_THRESHOLD_FACTOR)")
    args = ap.parse_args()

    run_dir = args.run_dir
    if run_dir is None:
        run_dir_env = os.environ.get("RUN_DIR")
        if run_dir_env:
            run_dir = Path(run_dir_env)
    if run_dir is None:
        print("[error] --run-dir or RUN_DIR is required", file=sys.stderr)
        return 2

    window_spans = args.window_spans or _env_or_default("EVAL_WINDOW_SPANS", None)
    min_duration = args.min_duration_days or _env_or_default("EVAL_MIN_DURATION_DAYS", None)
    threshold_factor = args.threshold_factor or _env_or_default("EVAL_THRESHOLD_FACTOR", None)

    root = _repo_root()
    script = root / "scripts" / "research" / "evaluate_tau_supply.py"
    cmd = [sys.executable, str(script), "--run-dir", str(run_dir)]
    if window_spans:
        cmd += ["--window-spans", window_spans]
    if min_duration:
        cmd += ["--min-duration-days", str(min_duration)]
    if threshold_factor:
        cmd += ["--threshold-factor", str(threshold_factor)]

    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stdout:
            sys.stderr.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return result.returncode

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("[error] evaluate_tau_supply output is not valid JSON\n")
        sys.stderr.write(result.stdout)
        return 2

    out_path = run_dir / "checks" / "tau_supply_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[eval] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
