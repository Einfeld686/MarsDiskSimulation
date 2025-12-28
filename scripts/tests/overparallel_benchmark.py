from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil
except Exception:
    psutil = None

_ENV_SNAPSHOT_KEYS = (
    "FORCE_STREAMING_OFF",
    "IO_STREAMING",
    "MARSDISK_CELL_PARALLEL",
    "MARSDISK_CELL_JOBS",
    "MARSDISK_CELL_MIN_CELLS",
    "NUMBA_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_snapshot(env: dict[str, str]) -> dict[str, str | None]:
    return {key: env.get(key) for key in _ENV_SNAPSHOT_KEYS}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_scenario(
    *,
    label: str,
    cmd_base: list[str],
    out_root: Path,
    parallel_jobs: int,
    env_overrides: dict[str, str],
) -> tuple[int, float, list[Path], list[dict[str, Any]]]:
    outdirs: list[Path] = []
    runs: list[dict[str, Any]] = []
    scenario_start = time.perf_counter()
    for idx in range(parallel_jobs):
        outdir = out_root / label / f"run_{idx:02d}"
        outdirs.append(outdir)
        cmd = cmd_base + ["--override", f"io.outdir={outdir}"]
        env = os.environ.copy()
        env.update(env_overrides)
        start_perf = time.perf_counter()
        start_time_utc = _utc_now()
        proc = subprocess.Popen(cmd, env=env)
        ps_proc = None
        if psutil is not None:
            try:
                ps_proc = psutil.Process(proc.pid)
            except Exception:
                ps_proc = None
        runs.append(
            {
                "index": idx,
                "outdir": outdir,
                "cmd": cmd,
                "env_snapshot": _env_snapshot(env),
                "start_perf": start_perf,
                "start_time_utc": start_time_utc,
                "proc": proc,
                "ps_proc": ps_proc,
                "cpu_time_sec": None,
                "max_rss_mb": None,
                "peak_threads": None,
                "done": False,
                "return_code": None,
                "end_perf": None,
                "end_time_utc": None,
            }
        )
    rc = 0
    while True:
        remaining = 0
        for run in runs:
            if run["done"]:
                continue
            proc = run["proc"]
            if psutil is not None and run["ps_proc"] is not None:
                try:
                    cpu_times = run["ps_proc"].cpu_times()
                    run["cpu_time_sec"] = cpu_times.user + cpu_times.system
                    rss = run["ps_proc"].memory_info().rss
                    run["max_rss_mb"] = max(run["max_rss_mb"] or 0.0, rss / (1024 * 1024))
                    threads = run["ps_proc"].num_threads()
                    run["peak_threads"] = max(run["peak_threads"] or 0, threads)
                except Exception:
                    pass
            proc_rc = proc.poll()
            if proc_rc is None:
                remaining += 1
                continue
            run["done"] = True
            run["return_code"] = proc_rc
            run["end_perf"] = time.perf_counter()
            run["end_time_utc"] = _utc_now()
            rc = max(rc, proc_rc)
        if remaining == 0:
            break
        time.sleep(0.05)
    elapsed = time.perf_counter() - scenario_start
    perf_entries: list[dict[str, Any]] = []
    cpu_logical = os.cpu_count() or 1
    for run in runs:
        wall_time = (run["end_perf"] or run["start_perf"]) - run["start_perf"]
        cpu_time = run["cpu_time_sec"]
        cpu_util = None
        if cpu_time is not None and wall_time > 0:
            cpu_util = 100.0 * cpu_time / wall_time
        perf_data = {
            "scenario_label": label,
            "run_index": run["index"],
            "pid": run["proc"].pid,
            "command": run["cmd"],
            "env": run["env_snapshot"],
            "cpu_logical": cpu_logical,
            "wall_time_sec": wall_time,
            "cpu_time_sec": cpu_time,
            "cpu_util_avg_pct": cpu_util,
            "max_rss_mb": run["max_rss_mb"],
            "peak_threads": run["peak_threads"],
            "return_code": run["return_code"],
            "start_time_utc": run["start_time_utc"],
            "end_time_utc": run["end_time_utc"],
            "psutil_available": psutil is not None,
        }
        perf_entries.append(perf_data)
        _write_json(run["outdir"] / "perf.json", perf_data)
    return rc, elapsed, outdirs, perf_entries


def _load_cell_parallel(outdir: Path) -> dict:
    run_config = outdir / "run_config.json"
    if not run_config.exists():
        return {}
    try:
        return json.loads(run_config.read_text(encoding="utf-8")).get("cell_parallel", {})
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Check over-parallelism risk by timing concurrent 1D runs.")
    ap.add_argument("--config", default="configs/base.yml", help="Base config path.")
    ap.add_argument("--parallel-jobs", type=int, default=2, help="Concurrent run count per scenario.")
    ap.add_argument("--cell-jobs", type=int, default=4, help="MARSDISK_CELL_JOBS for the parallel scenario.")
    ap.add_argument("--n-cells", type=int, default=8, help="geometry.Nr override.")
    ap.add_argument("--t-end-orbits", type=float, default=0.02, help="numerics.t_end_orbits override.")
    ap.add_argument("--dt-init", type=float, default=50.0, help="numerics.dt_init override.")
    ap.add_argument("--out-root", default="out/overparallel_benchmark", help="Output root directory.")
    ap.add_argument("--fail-on-slowdown", action="store_true", help="Exit non-zero if slowdown exceeds threshold.")
    ap.add_argument("--slowdown-threshold", type=float, default=1.10, help="Slowdown ratio threshold.")
    args = ap.parse_args()

    config_path = Path(args.config)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    if psutil is None:
        print("[warn] psutil not available; perf.json will omit cpu/memory metrics.")

    overrides = [
        "geometry.mode=1D",
        f"geometry.Nr={int(args.n_cells)}",
        f"numerics.t_end_orbits={args.t_end_orbits}",
        "numerics.t_end_years=null",
        f"numerics.dt_init={args.dt_init}",
        "dynamics.e_profile.mode=off",
        "phase.enabled=false",
        "supply.enabled=false",
        "radiation.mars_temperature_driver.enabled=false",
        "radiation.TM_K=2000.0",
        "io.streaming.enable=false",
    ]

    cmd_base = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path), "--quiet"]
    for item in overrides:
        cmd_base += ["--override", item]

    cpu_count = os.cpu_count() or 1
    combined = max(args.parallel_jobs, 1) * max(args.cell_jobs, 1)
    print(f"[info] cpu_logical={cpu_count} parallel_jobs={args.parallel_jobs} cell_jobs={args.cell_jobs}")
    print(f"[info] combined_concurrency={combined}")
    if combined > cpu_count:
        print("[warn] combined concurrency exceeds logical cores (oversubscription likely).")

    common_env = {
        "FORCE_STREAMING_OFF": "1",
        "MARSDISK_CELL_MIN_CELLS": "1",
    }

    parallel_env = {
        **common_env,
        "MARSDISK_CELL_PARALLEL": "1",
        "MARSDISK_CELL_JOBS": str(max(args.cell_jobs, 1)),
    }
    control_env = {
        **common_env,
        "MARSDISK_CELL_PARALLEL": "0",
        "MARSDISK_CELL_JOBS": "1",
    }

    rc_parallel, t_parallel, out_parallel, perf_parallel = _run_scenario(
        label="parallel",
        cmd_base=cmd_base,
        out_root=out_root,
        parallel_jobs=args.parallel_jobs,
        env_overrides=parallel_env,
    )
    rc_control, t_control, out_control, perf_control = _run_scenario(
        label="control",
        cmd_base=cmd_base,
        out_root=out_root,
        parallel_jobs=args.parallel_jobs,
        env_overrides=control_env,
    )

    for outdir in out_parallel:
        info = _load_cell_parallel(outdir)
        enabled = info.get("enabled")
        if enabled is not True:
            print(f"[warn] cell_parallel not enabled in {outdir} (info={info})")
    for outdir in out_control:
        info = _load_cell_parallel(outdir)
        enabled = info.get("enabled")
        if enabled is not False:
            print(f"[warn] cell_parallel not disabled in {outdir} (info={info})")

    print(f"[result] parallel_time_sec={t_parallel:.3f} rc={rc_parallel}")
    print(f"[result] control_time_sec={t_control:.3f} rc={rc_control}")
    ratio = t_parallel / t_control if t_control > 0 else float("inf")
    print(f"[result] slowdown_ratio={ratio:.3f}")

    summary = {
        "parallel_time_sec": t_parallel,
        "control_time_sec": t_control,
        "slowdown_ratio": ratio,
        "parallel": perf_parallel,
        "control": perf_control,
        "psutil_available": psutil is not None,
        "cpu_logical": cpu_count,
        "parallel_jobs": args.parallel_jobs,
        "cell_jobs": args.cell_jobs,
        "n_cells": args.n_cells,
        "t_end_orbits": args.t_end_orbits,
        "dt_init": args.dt_init,
        "start_time_utc": perf_parallel[0]["start_time_utc"] if perf_parallel else None,
        "end_time_utc": perf_control[-1]["end_time_utc"] if perf_control else None,
    }
    _write_json(out_root / "perf_summary.json", summary)

    if rc_parallel != 0 or rc_control != 0:
        return 2
    if args.fail_on_slowdown and ratio >= args.slowdown_threshold:
        print("[error] slowdown exceeds threshold; consider reducing cell/process concurrency.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
