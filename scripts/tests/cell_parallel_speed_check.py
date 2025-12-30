#!/usr/bin/env python3
"""Compare wall time for cell-parallel on/off runs (Windows-focused)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_case(
    *,
    label: str,
    config_path: Path,
    outdir: Path,
    overrides: list[str],
    env: Dict[str, str],
    quiet: bool,
) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path)]
    if quiet:
        cmd.append("--quiet")
    for override in overrides:
        cmd.extend(["--override", override])

    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=_repo_root(), env=env, check=False)
    elapsed = time.perf_counter() - start

    run_config_path = outdir / "run_config.json"
    summary_path = outdir / "summary.json"

    run_config = _load_json(run_config_path) if run_config_path.exists() else {}
    summary = _load_json(summary_path) if summary_path.exists() else {}

    return {
        "label": label,
        "returncode": result.returncode,
        "elapsed_sec": elapsed,
        "outdir": str(outdir),
        "run_config_path": str(run_config_path),
        "summary_path": str(summary_path),
        "cell_parallel": run_config.get("cell_parallel"),
        "threading": run_config.get("threading"),
        "summary": summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/base.yml", help="Path to YAML config.")
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--t-end-years", type=float, default=0.02, help="Integration span in years.")
    ap.add_argument("--dt-init", default="5000", help="Initial dt override (numeric or 'auto').")
    ap.add_argument("--seed", type=int, default=12345, help="dynamics.rng_seed override.")
    ap.add_argument("--cell-jobs", type=int, default=4, help="MARSDISK_CELL_JOBS for parallel-on case.")
    ap.add_argument("--geometry-nr", type=int, default=None, help="Override geometry.Nr for 1D runs.")
    ap.add_argument(
        "--force-non-windows",
        action="store_true",
        help="Allow cell parallel on non-Windows by setting MARSDISK_CELL_PARALLEL_FORCE=1.",
    )
    ap.add_argument("--no-quiet", action="store_true", help="Show INFO logs.")
    args = ap.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_outdir = Path(args.out_root).resolve() / f"cell_parallel_speed_{timestamp}"
    base_outdir.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config).resolve()
    overrides = [
        f"io.outdir={base_outdir}",
        f"numerics.t_end_years={args.t_end_years}",
        "numerics.t_end_until_temperature_K=none",
        f"numerics.dt_init={args.dt_init}",
        f"dynamics.rng_seed={args.seed}",
    ]
    if args.geometry_nr is not None:
        overrides.append(f"geometry.Nr={args.geometry_nr}")

    common_env = os.environ.copy()
    common_env.setdefault("FORCE_STREAMING_OFF", "1")
    common_env.setdefault("IO_STREAMING", "off")
    common_env.setdefault("CELL_THREAD_LIMIT", "1")
    common_env.setdefault("NUMBA_NUM_THREADS", "1")
    common_env.setdefault("OMP_NUM_THREADS", "1")
    common_env.setdefault("MKL_NUM_THREADS", "1")
    common_env.setdefault("OPENBLAS_NUM_THREADS", "1")
    common_env.setdefault("NUMEXPR_NUM_THREADS", "1")
    common_env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    if args.force_non_windows:
        common_env["MARSDISK_CELL_PARALLEL_FORCE"] = "1"

    on_env = dict(common_env)
    on_env["MARSDISK_CELL_PARALLEL"] = "1"
    on_env["MARSDISK_CELL_JOBS"] = str(max(args.cell_jobs, 1))
    on_outdir = base_outdir / "cell_parallel_on"
    on_overrides = overrides.copy()
    on_overrides[0] = f"io.outdir={on_outdir}"

    off_env = dict(common_env)
    off_env["MARSDISK_CELL_PARALLEL"] = "0"
    off_env["MARSDISK_CELL_JOBS"] = "1"
    off_outdir = base_outdir / "cell_parallel_off"
    off_overrides = overrides.copy()
    off_overrides[0] = f"io.outdir={off_outdir}"

    quiet = not args.no_quiet
    results = {
        "config": str(config_path),
        "timestamp": timestamp,
        "cases": [],
    }

    print("[info] running cell-parallel ON case...")
    on_result = _run_case(
        label="cell_parallel_on",
        config_path=config_path,
        outdir=on_outdir,
        overrides=on_overrides,
        env=on_env,
        quiet=quiet,
    )
    results["cases"].append(on_result)

    print("[info] running cell-parallel OFF case...")
    off_result = _run_case(
        label="cell_parallel_off",
        config_path=config_path,
        outdir=off_outdir,
        overrides=off_overrides,
        env=off_env,
        quiet=quiet,
    )
    results["cases"].append(off_result)

    summary_path = base_outdir / "speed_check_summary.json"
    speedup = None
    if on_result["returncode"] == 0 and off_result["returncode"] == 0:
        if on_result["elapsed_sec"] > 0:
            speedup = off_result["elapsed_sec"] / on_result["elapsed_sec"]
    results["speedup_off_over_on"] = speedup
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    errors = []
    for result, expected_enabled in ((on_result, True), (off_result, False)):
        if result["returncode"] != 0:
            errors.append(f"{result['label']} failed (rc={result['returncode']})")
            continue
        cell_parallel = result.get("cell_parallel") or {}
        enabled = bool(cell_parallel.get("enabled"))
        if enabled != expected_enabled:
            errors.append(
                f"{result['label']} expected enabled={expected_enabled} but got {enabled}"
            )

    if errors:
        print("[error] speed check failed:")
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
