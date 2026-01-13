#!/usr/bin/env python3
"""Run a single temp_supply sweep case and report output size."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sanitize_token(value: str) -> str:
    text = value.strip()
    if text.startswith("0."):
        text = text.replace("0.", "0p", 1)
    text = text.replace(".", "p")
    return text


def _git_short_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "nogit"
    if result.returncode != 0:
        return "nogit"
    return result.stdout.strip() or "nogit"


def _dir_stats(path: Path) -> Tuple[int, int, int]:
    total_bytes = 0
    file_count = 0
    dir_count = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total_bytes += entry.stat().st_size
                file_count += 1
            except OSError:
                continue
        elif entry.is_dir():
            dir_count += 1
    return total_bytes, file_count, dir_count


def _build_outdir(
    *,
    batch_root: Path,
    sweep_tag: str,
    run_ts: str,
    git_sha: str,
    batch_seed: int,
    t_value: str,
    eps_value: str,
    tau_value: str,
    i0_value: str,
) -> Path:
    eps_title = _sanitize_token(eps_value)
    tau_title = _sanitize_token(tau_value)
    i0_title = _sanitize_token(i0_value)
    title = f"T{t_value}_eps{eps_title}_tau{tau_title}_i0{i0_title}"
    batch_dir = batch_root / sweep_tag / f"{run_ts}__{git_sha}__seed{batch_seed}"
    return batch_dir / title


def _write_report(path: Path, payload: Dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-root", default="out/size_probe", help="Output root for the probe run.")
    ap.add_argument("--sweep-tag", default="size_probe", help="Sweep tag to isolate output.")
    ap.add_argument("--t", default="5000", help="RUN_ONE_T value.")
    ap.add_argument("--eps", default="1.0", help="RUN_ONE_EPS value.")
    ap.add_argument("--tau", default="1.0", help="RUN_ONE_TAU value.")
    ap.add_argument("--i0", default="0.05", help="RUN_ONE_I0 value.")
    ap.add_argument("--batch-seed", type=int, default=0, help="BATCH_SEED value.")
    ap.add_argument("--run-ts", default="", help="RUN_TS value (defaults to timestamp).")
    ap.add_argument(
        "--config",
        default="",
        help="Override BASE_CONFIG (defaults to run_temp_supply_sweep.cmd setting).",
    )
    ap.add_argument(
        "--overrides",
        default="scripts/runsets/windows/overrides.txt",
        help="EXTRA_OVERRIDES_FILE path (optional).",
    )
    ap.add_argument(
        "--hooks",
        default="plot,eval",
        help="Comma-separated hooks to enable (default: plot,eval; use 'none' to disable).",
    )
    ap.add_argument(
        "--temp-root",
        default="",
        help="TEMP/TMP/TMPDIR override for the run (recommended on SSD).",
    )
    ap.add_argument(
        "--no-run",
        action="store_true",
        help="Skip the run and only measure the computed output directory.",
    )
    ap.add_argument(
        "--outdir",
        default="",
        help="Measure this directory instead of the computed case directory.",
    )
    ap.add_argument(
        "--skip-pip",
        action="store_true",
        help="Set SKIP_PIP=1 when invoking run_temp_supply_sweep.cmd.",
    )
    ap.add_argument(
        "--reserve-gb",
        type=float,
        default=50.0,
        help="Reserve this many GB of free space (default: 50).",
    )
    ap.add_argument(
        "--safety-fraction",
        type=float,
        default=0.7,
        help="Fraction of remaining space to allocate (default: 0.7).",
    )
    ap.add_argument(
        "--print-recommended-jobs",
        action="store_true",
        help="Print recommended parallel jobs only (for cmd integration).",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress info logs (errors still printed).",
    )
    args = ap.parse_args()

    repo_root = _repo_root()
    batch_root = Path(args.batch_root).expanduser()
    if not batch_root.is_absolute():
        batch_root = (repo_root / batch_root).resolve()
    batch_root.mkdir(parents=True, exist_ok=True)

    run_ts = args.run_ts or datetime.now().strftime("%Y%m%d-%H%M%S")
    git_sha = _git_short_sha(repo_root)

    computed_outdir = _build_outdir(
        batch_root=batch_root,
        sweep_tag=args.sweep_tag,
        run_ts=run_ts,
        git_sha=git_sha,
        batch_seed=args.batch_seed,
        t_value=args.t,
        eps_value=args.eps,
        tau_value=args.tau,
        i0_value=args.i0,
    )

    outdir = Path(args.outdir).expanduser() if args.outdir else computed_outdir
    if not outdir.is_absolute():
        outdir = (repo_root / outdir).resolve()

    if not args.no_run:
        env = os.environ.copy()
        env.update(
            {
                "RUN_ONE_MODE": "1",
                "RUN_ONE_T": str(args.t),
                "RUN_ONE_EPS": str(args.eps),
                "RUN_ONE_TAU": str(args.tau),
                "RUN_ONE_I0": str(args.i0),
                "RUN_TS": run_ts,
                "BATCH_SEED": str(args.batch_seed),
                "BATCH_ROOT": str(batch_root),
                "SWEEP_TAG": str(args.sweep_tag),
                "SWEEP_PARALLEL": "0",
                "PARALLEL_JOBS": "1",
            }
        )
        hooks = args.hooks.strip()
        if hooks.lower() == "none":
            env["HOOKS_ENABLE"] = ""
            env["PLOT_ENABLE"] = "0"
        else:
            env["HOOKS_ENABLE"] = hooks
        if args.temp_root:
            env["TEMP"] = args.temp_root
            env["TMP"] = args.temp_root
            env["TMPDIR"] = args.temp_root
        if args.config:
            env["BASE_CONFIG"] = args.config
        if args.overrides:
            env["EXTRA_OVERRIDES_FILE"] = args.overrides
        if args.skip_pip:
            env["SKIP_PIP"] = "1"

        cmd = [str(repo_root / "scripts" / "research" / "run_temp_supply_sweep.cmd"), "--run-one"]
        if not (args.quiet or args.print_recommended_jobs):
            print(f"[info] running: {' '.join(cmd)}")
        start = time.perf_counter()
        result = subprocess.run(cmd, cwd=repo_root, env=env)
        elapsed = time.perf_counter() - start
        if result.returncode != 0:
            print(f"[error] run_temp_supply_sweep.cmd failed (rc={result.returncode})")
            return result.returncode
        if not (args.quiet or args.print_recommended_jobs):
            print(f"[info] run completed in {elapsed:.1f}s")

    if not outdir.exists():
        print(f"[error] output directory not found: {outdir}")
        return 2

    total_bytes, file_count, dir_count = _dir_stats(outdir)
    size_gb = total_bytes / (1024**3)
    try:
        free_bytes = shutil.disk_usage(batch_root).free
        free_gb = free_bytes / (1024**3)
    except OSError:
        free_gb = None
    reserve_gb = max(args.reserve_gb, 0.0)
    safety_fraction = max(min(args.safety_fraction, 1.0), 0.0)
    available_gb = None
    usable_gb = None
    recommended_jobs = 1
    if free_gb is not None:
        available_gb = max(free_gb - reserve_gb, 0.0)
        usable_gb = available_gb * safety_fraction
        if size_gb > 0:
            recommended_jobs = max(int(usable_gb // size_gb), 1)
    report = {
        "outdir": str(outdir),
        "total_bytes": total_bytes,
        "size_gb": size_gb,
        "file_count": file_count,
        "dir_count": dir_count,
        "disk_free_gb": free_gb,
        "reserve_gb": reserve_gb,
        "safety_fraction": safety_fraction,
        "usable_gb": usable_gb,
        "recommended_jobs": recommended_jobs,
        "run_ts": run_ts,
        "batch_seed": args.batch_seed,
        "t": args.t,
        "eps": args.eps,
        "tau": args.tau,
    }
    report_path = outdir / "size_report.json"
    _write_report(report_path, report)
    if args.print_recommended_jobs:
        print(recommended_jobs)
        return 0
    if not args.quiet:
        print(f"[result] outdir={outdir}")
        print(f"[result] size_gb={size_gb:.3f} files={file_count} dirs={dir_count}")
        if free_gb is not None:
            print(
                "[result] free_gb={:.1f} reserve_gb={:.1f} usable_gb={:.1f} recommended_jobs={}".format(
                    free_gb, reserve_gb, usable_gb or 0.0, recommended_jobs
                )
            )
        print(f"[result] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
