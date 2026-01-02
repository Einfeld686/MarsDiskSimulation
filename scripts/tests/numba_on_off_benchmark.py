#!/usr/bin/env python3
"""Run a short benchmark comparing numba on/off execution time."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class RunResult:
    label: str
    disable_numba: bool
    duration_sec: float
    outdir: str
    returncode: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "FORCE_STREAMING_OFF": "1",
            "IO_STREAMING": "off",
            "MARSDISK_CELL_PARALLEL": "0",
            "NUMBA_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        }
    )
    return env


def _build_overrides(args: argparse.Namespace, outdir: Path) -> List[str]:
    overrides = [
        f"io.outdir={outdir}",
        f"numerics.t_end_years={args.t_end_years}",
        "numerics.t_end_until_temperature_K=none",
        f"numerics.dt_init={args.dt_init}",
        f"dynamics.rng_seed={args.seed}",
    ]
    if args.geometry_mode:
        overrides.append(f"geometry.mode={args.geometry_mode}")
    if args.geometry_nr is not None:
        overrides.append(f"geometry.Nr={args.geometry_nr}")
    return overrides


def _run_case(args: argparse.Namespace, label: str, disable_numba: bool, outdir: Path) -> RunResult:
    repo_root = _repo_root()
    env = _default_env()
    if disable_numba:
        env["MARSDISK_NUMBA_DISABLE"] = "1"
        env["MARSDISK_DISABLE_NUMBA"] = "1"
    else:
        env["MARSDISK_NUMBA_DISABLE"] = "0"
        env["MARSDISK_DISABLE_NUMBA"] = "0"

    overrides = _build_overrides(args, outdir)
    cmd: List[str] = [
        sys.executable,
        "-m",
        "marsdisk.run",
        "--config",
        str(Path(args.config).resolve()),
    ]
    for override in overrides:
        cmd.extend(["--override", override])
    if not args.no_quiet:
        cmd.append("--quiet")

    start = time.perf_counter()
    completed = subprocess.run(cmd, cwd=repo_root, env=env, check=True)
    duration = time.perf_counter() - start
    return RunResult(
        label=label,
        disable_numba=disable_numba,
        duration_sec=float(duration),
        outdir=str(outdir),
        returncode=int(completed.returncode),
    )


def _summarize(results: Sequence[RunResult]) -> dict:
    by_label = {res.label: res for res in results}
    speedup = None
    if "numba_on" in by_label and "numba_off" in by_label:
        denom = by_label["numba_on"].duration_sec
        speedup = (by_label["numba_off"].duration_sec / denom) if denom > 0 else None
    return {
        "speedup_off_over_on": speedup,
        "runs": [res.__dict__ for res in results],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/base.yml", help="Path to YAML config.")
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--t-end-years", type=float, default=0.002, help="Integration span in years.")
    ap.add_argument("--dt-init", default="5000", help="Initial dt override (numeric or 'auto').")
    ap.add_argument("--seed", type=int, default=12345, help="dynamics.rng_seed override.")
    ap.add_argument("--geometry-nr", type=int, default=None, help="Override geometry.Nr.")
    ap.add_argument("--geometry-mode", default="0D", help="Override geometry.mode.")
    ap.add_argument("--no-quiet", action="store_true", help="Show INFO logs.")
    args = ap.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path(args.out_root).resolve() / f"numba_on_off_bench_{timestamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    results: List[RunResult] = []
    results.append(_run_case(args, "numba_on", False, out_root / "numba_on"))
    results.append(_run_case(args, "numba_off", True, out_root / "numba_off"))

    summary = {
        "timestamp": timestamp,
        "config": str(Path(args.config).resolve()),
        "overrides": {
            "t_end_years": args.t_end_years,
            "dt_init": args.dt_init,
            "seed": args.seed,
            "geometry_mode": args.geometry_mode,
            "geometry_nr": args.geometry_nr,
        },
    }
    summary.update(_summarize(results))

    summary_path = out_root / "bench_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[done] summary: {summary_path}")
    if summary.get("speedup_off_over_on") is not None:
        print(f"[done] speedup(off/on): {summary['speedup_off_over_on']:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
