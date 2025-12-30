#!/usr/bin/env python3
"""Profile a short run and estimate time spent in python-level loops."""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _set_default_env() -> None:
    os.environ.setdefault("FORCE_STREAMING_OFF", "1")
    os.environ.setdefault("IO_STREAMING", "off")
    os.environ.setdefault("CELL_THREAD_LIMIT", "1")
    os.environ.setdefault("NUMBA_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("MARSDISK_CELL_PARALLEL", "0")


def _run_profile(argv: list[str], outdir: Path) -> Path:
    import marsdisk.run as run_mod

    profile_path = outdir / "profile.pstats"
    profiler = cProfile.Profile()
    profiler.enable()
    run_mod.main(argv)
    profiler.disable()
    profiler.dump_stats(str(profile_path))
    return profile_path


def _summarize_profile(profile_path: Path, top_n: int) -> Dict[str, Any]:
    output = io.StringIO()
    stats = pstats.Stats(str(profile_path), stream=output)
    total_tt = stats.total_tt
    run_one_d_time = 0.0
    for (filename, _line, _func), (_cc, _nc, tt, _ct, _callers) in stats.stats.items():
        if filename.replace("\\", "/").endswith("marsdisk/run_one_d.py"):
            run_one_d_time += tt
    ratio = run_one_d_time / total_tt if total_tt > 0 else 0.0

    stats.strip_dirs().sort_stats("tottime").print_stats(top_n)
    top_stats = output.getvalue()

    return {
        "total_time_sec": total_tt,
        "run_one_d_tottime_sec": run_one_d_time,
        "run_one_d_tottime_ratio": ratio,
        "top_stats": top_stats,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/base.yml", help="Path to YAML config.")
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--t-end-years", type=float, default=0.02, help="Integration span in years.")
    ap.add_argument("--dt-init", default="5000", help="Initial dt override (numeric or 'auto').")
    ap.add_argument("--seed", type=int, default=12345, help="dynamics.rng_seed override.")
    ap.add_argument("--top-n", type=int, default=30, help="Top functions to dump in report.")
    ap.add_argument(
        "--disable-numba",
        action="store_true",
        help="Set MARSDISK_DISABLE_NUMBA=1 for this run.",
    )
    ap.add_argument("--no-quiet", action="store_true", help="Show INFO logs.")
    args = ap.parse_args()

    _set_default_env()
    if args.disable_numba:
        os.environ["MARSDISK_DISABLE_NUMBA"] = "1"

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = Path(args.out_root).resolve() / f"python_loop_profile_{timestamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    argv = [
        "--config",
        str(Path(args.config).resolve()),
        "--override",
        f"io.outdir={outdir}",
        "--override",
        f"numerics.t_end_years={args.t_end_years}",
        "--override",
        "numerics.t_end_until_temperature_K=none",
        "--override",
        f"numerics.dt_init={args.dt_init}",
        "--override",
        f"dynamics.rng_seed={args.seed}",
    ]
    if not args.no_quiet:
        argv.append("--quiet")

    profile_path = _run_profile(argv, outdir)
    summary = _summarize_profile(profile_path, args.top_n)

    summary_path = outdir / "profile_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    top_path = outdir / "profile_top.txt"
    top_path.write_text(summary["top_stats"], encoding="utf-8")

    print(f"[done] profile: {profile_path}")
    print(f"[done] summary: {summary_path}")
    print(f"[done] top stats: {top_path}")
    print(
        "[done] run_one_d tottime ratio: {:.3f}".format(summary["run_one_d_tottime_ratio"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
