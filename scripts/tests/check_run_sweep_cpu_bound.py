#!/usr/bin/env python3
"""Verify run_sweep.cmd thread budget and CPU-bound behavior."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import psutil
except Exception:
    psutil = None


DEFAULT_T_LIST = [4000]
DEFAULT_EPS_LIST = [1.0]
DEFAULT_TAU_LIST = [1.0]
DEFAULT_I0_LIST = [0.05]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _format_list(values: Iterable[float]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _write_study(path: Path, sweep_tag: str) -> None:
    lines = [
        f"T_LIST: {_format_list(DEFAULT_T_LIST)}",
        f"EPS_LIST: {_format_list(DEFAULT_EPS_LIST)}",
        f"TAU_LIST: {_format_list(DEFAULT_TAU_LIST)}",
        f"I0_LIST: {_format_list(DEFAULT_I0_LIST)}",
        f"SWEEP_TAG: {sweep_tag}",
    ]
    _write_text(path, "\n".join(lines) + "\n")


def _format_override_value(value: Optional[float]) -> str:
    if value is None:
        return "null"
    return str(value)


def _build_overrides(
    base_overrides: Path,
    extra_overrides: Iterable[str],
    out_path: Path,
) -> None:
    base_text = base_overrides.read_text(encoding="utf-8")
    extra_lines = [line.strip() for line in extra_overrides if line.strip()]
    combined = base_text.rstrip() + "\n"
    if extra_lines:
        combined += "\n# Added by check_run_sweep_cpu_bound.py\n"
        combined += "\n".join(extra_lines) + "\n"
    _write_text(out_path, combined)


def _run_cmd(cmd: list[str], env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    if os.name == "nt":
        return subprocess.run(["cmd.exe", "/c", *cmd], cwd=cwd, env=env, check=False)
    return subprocess.run(cmd, cwd=cwd, env=env, check=False)


def _parse_parallel_final(log_path: Path) -> Dict[str, str]:
    if not log_path.exists():
        return {}
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for raw in reversed(lines):
        if "parallel_final:" not in raw:
            continue
        _, _, payload = raw.partition("parallel_final:")
        tokens = payload.strip().split()
        parsed: Dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed
    return {}


def _coerce_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _thread_budget(parallel_config: Dict[str, str], cpu_logical: int) -> Dict[str, Any]:
    sweep_parallel = _coerce_int(parallel_config.get("sweep_parallel"), 0)
    parallel_jobs = _coerce_int(parallel_config.get("parallel_jobs"), 1)
    cell_jobs = _coerce_int(parallel_config.get("cell_jobs"), 1)
    cell_thread_limit = _coerce_int(parallel_config.get("cell_thread_limit"), 1)
    mode = "sweep_parallel" if sweep_parallel == 1 else "cell_parallel"
    if sweep_parallel == 1:
        expected_threads = max(1, parallel_jobs) * max(1, cell_thread_limit)
    else:
        expected_threads = max(1, cell_jobs) * max(1, cell_thread_limit)
    expected_capacity_pct = (min(expected_threads, cpu_logical) / cpu_logical) * 100.0
    return {
        "mode": mode,
        "sweep_parallel": sweep_parallel,
        "parallel_jobs": parallel_jobs,
        "cell_jobs": cell_jobs,
        "cell_thread_limit": cell_thread_limit,
        "expected_threads": expected_threads,
        "cpu_logical": cpu_logical,
        "expected_capacity_pct": expected_capacity_pct,
        "threads_within_cpu": expected_threads <= cpu_logical,
    }


def _update_cpu_times(root: Optional["psutil.Process"], seen: Dict[int, float]) -> None:
    if root is None or psutil is None:
        return
    try:
        procs = [root] + root.children(recursive=True)
    except Exception:
        procs = []
    for proc in procs:
        try:
            times = proc.cpu_times()
            total = float(times.user + times.system)
        except Exception:
            continue
        prev = seen.get(proc.pid, 0.0)
        if total > prev:
            seen[proc.pid] = total


def _monitor_cpu(proc: subprocess.Popen, interval: float) -> tuple[list[float], Dict[int, float]]:
    samples: list[float] = []
    cpu_times: Dict[int, float] = {}
    if psutil is None:
        while proc.poll() is None:
            time.sleep(interval)
        return samples, cpu_times
    try:
        root = psutil.Process(proc.pid)
    except Exception:
        root = None
    psutil.cpu_percent(interval=None)
    while proc.poll() is None:
        samples.append(psutil.cpu_percent(interval=interval))
        _update_cpu_times(root, cpu_times)
    _update_cpu_times(root, cpu_times)
    return samples, cpu_times


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cmd", default="scripts/runsets/windows/run_sweep.cmd", help="run_sweep.cmd path.")
    ap.add_argument("--config", default=None, help="Optional --config override for run_sweep.cmd.")
    ap.add_argument(
        "--overrides",
        default="scripts/runsets/windows/overrides.txt",
        help="Base overrides file to copy.",
    )
    ap.add_argument("--study", default=None, help="Optional study YAML; default is a 1x1x1 probe.")
    ap.add_argument("--out-root", default="out/tests", help="Output root for reports.")
    ap.add_argument("--run", action="store_true", help="Run the sweep after dry-run.")
    ap.add_argument("--sample-interval", type=float, default=0.5, help="CPU sample interval seconds.")
    ap.add_argument(
        "--cpu-bound-threshold",
        type=float,
        default=0.7,
        help="Threshold ratio for CPU-bound判定 (0-1).",
    )
    ap.add_argument("--no-probe-overrides", action="store_true", help="Skip default short-run overrides.")
    ap.add_argument("--probe-nr", type=int, default=8, help="geometry.Nr for probe overrides.")
    ap.add_argument("--probe-t-end-years", type=float, default=1e-4, help="numerics.t_end_years for probe.")
    ap.add_argument("--parallel-jobs", type=int, default=None, help="Force PARALLEL_JOBS.")
    ap.add_argument("--sweep-parallel", type=int, choices=[0, 1], default=None, help="Force SWEEP_PARALLEL.")
    ap.add_argument("--cell-thread-limit", type=int, default=None, help="Force CELL_THREAD_LIMIT and thread caps.")
    args = ap.parse_args()

    repo_root = _repo_root()
    cmd_path = Path(args.cmd)
    if not cmd_path.is_absolute():
        cmd_path = (repo_root / cmd_path).resolve()
    if not cmd_path.exists():
        raise FileNotFoundError(f"run_sweep.cmd not found: {cmd_path}")

    base_overrides = Path(args.overrides)
    if not base_overrides.is_absolute():
        base_overrides = (repo_root / base_overrides).resolve()
    if not base_overrides.exists():
        raise FileNotFoundError(f"Base overrides not found: {base_overrides}")

    report_root = Path(args.out_root).resolve() / f"run_sweep_cpu_bound_{_timestamp()}"
    run_root = report_root / "runs"
    artifacts_root = report_root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    study_path = Path(args.study).resolve() if args.study else artifacts_root / "study_probe.yml"
    if args.study is None:
        _write_study(study_path, sweep_tag="cpu_bound_probe")

    extra_overrides = []
    if not args.no_probe_overrides:
        extra_overrides.extend(
            [
                f"geometry.Nr={args.probe_nr}",
                f"numerics.t_end_years={args.probe_t_end_years}",
                "numerics.t_end_orbits=null",
            ]
        )
    overrides_path = artifacts_root / "overrides_effective.txt"
    _build_overrides(base_overrides, extra_overrides, overrides_path)

    debug_log = artifacts_root / "run_sweep_debug.log"
    trace_log = artifacts_root / "run_sweep_trace.log"

    env = os.environ.copy()
    env.setdefault("SKIP_PIP", "1")
    env.setdefault("REQUIREMENTS_INSTALLED", "1")
    env.setdefault("NO_PLOT", "1")
    env.setdefault("NO_EVAL", "1")
    env.setdefault("QUIET_MODE", "1")
    env.setdefault("COOL_TO_K", "none")
    env["DEBUG_LOG_FILE"] = str(debug_log)
    env["TRACE_LOG"] = str(trace_log)

    if args.parallel_jobs is not None:
        env["PARALLEL_JOBS"] = str(args.parallel_jobs)
    if args.sweep_parallel is not None:
        env["SWEEP_PARALLEL"] = str(args.sweep_parallel)
    if args.cell_thread_limit is not None:
        env["CELL_THREAD_LIMIT"] = str(args.cell_thread_limit)
        env.setdefault("NUMBA_NUM_THREADS", str(args.cell_thread_limit))
        env.setdefault("OMP_NUM_THREADS", str(args.cell_thread_limit))
        env.setdefault("MKL_NUM_THREADS", str(args.cell_thread_limit))
        env.setdefault("OPENBLAS_NUM_THREADS", str(args.cell_thread_limit))
        env.setdefault("NUMEXPR_NUM_THREADS", str(args.cell_thread_limit))
        env.setdefault("VECLIB_MAXIMUM_THREADS", str(args.cell_thread_limit))

    dry_cmd = [str(cmd_path), "--dry-run", "--debug", "--overrides", str(overrides_path), "--out-root", str(run_root)]
    if args.config:
        dry_cmd.extend(["--config", args.config])
    if study_path:
        dry_cmd.extend(["--study", str(study_path)])

    if os.name != "nt":
        print("[warn] non-Windows environment: skipping run_sweep.cmd dry-run.")
        parallel_config = {}
    else:
        result = _run_cmd(dry_cmd, env=env, cwd=repo_root)
        if result.returncode != 0:
            print(f"[warn] dry-run exited with status {result.returncode}")
        parallel_config = _parse_parallel_final(debug_log)

    cpu_logical = os.cpu_count() or 1
    if not parallel_config:
        parallel_config = {
            "sweep_parallel": env.get("SWEEP_PARALLEL", "1"),
            "parallel_jobs": env.get("PARALLEL_JOBS", "6"),
            "cell_jobs": env.get("MARSDISK_CELL_JOBS", "1"),
            "cell_thread_limit": env.get("CELL_THREAD_LIMIT", "1"),
        }

    thread_check = _thread_budget(parallel_config, cpu_logical)
    _write_json(report_root / "parallel_config.json", parallel_config)
    _write_json(report_root / "thread_budget.json", thread_check)

    print(f"[info] cpu_logical={cpu_logical} expected_threads={thread_check['expected_threads']}")
    if not thread_check["threads_within_cpu"]:
        print("[warn] total threads exceed logical cores (oversubscription likely).")

    if not args.run:
        print(f"[done] report: {report_root}")
        return 0

    if os.name != "nt":
        print("[error] --run requires Windows cmd execution.")
        return 2

    run_cmd = [str(cmd_path), "--debug", "--overrides", str(overrides_path), "--out-root", str(run_root)]
    if args.config:
        run_cmd.extend(["--config", args.config])
    if study_path:
        run_cmd.extend(["--study", str(study_path)])

    start = time.perf_counter()
    proc = subprocess.Popen(["cmd.exe", "/c", *run_cmd], cwd=repo_root, env=env)
    samples, cpu_times = _monitor_cpu(proc, args.sample_interval)
    rc = proc.wait()
    wall_time = time.perf_counter() - start

    avg_cpu_percent = sum(samples) / len(samples) if samples else None
    cpu_time_total = sum(cpu_times.values()) if cpu_times else None
    cpu_util_tree_pct = None
    if cpu_time_total is not None and wall_time > 0:
        cpu_util_tree_pct = (cpu_time_total / wall_time / cpu_logical) * 100.0

    expected_capacity_pct = float(thread_check["expected_capacity_pct"])
    threshold_pct = expected_capacity_pct * float(args.cpu_bound_threshold)
    metric_pct = cpu_util_tree_pct if cpu_util_tree_pct is not None else avg_cpu_percent
    cpu_bound = None
    if metric_pct is not None:
        cpu_bound = metric_pct >= threshold_pct

    summary = {
        "returncode": rc,
        "wall_time_sec": wall_time,
        "cpu_logical": cpu_logical,
        "expected_threads": thread_check["expected_threads"],
        "expected_capacity_pct": expected_capacity_pct,
        "cpu_bound_threshold_ratio": args.cpu_bound_threshold,
        "cpu_bound_threshold_pct": threshold_pct,
        "avg_cpu_percent": avg_cpu_percent,
        "cpu_time_total_sec": cpu_time_total,
        "cpu_util_tree_pct": cpu_util_tree_pct,
        "cpu_bound": cpu_bound,
        "psutil_available": psutil is not None,
        "samples_count": len(samples),
        "sample_interval_sec": args.sample_interval,
        "report_root": str(report_root),
        "run_root": str(run_root),
    }
    _write_json(report_root / "cpu_summary.json", summary)

    if samples:
        samples_path = report_root / "cpu_samples.csv"
        _write_text(samples_path, "sample_index,cpu_percent\n")
        with samples_path.open("a", encoding="utf-8") as handle:
            for idx, value in enumerate(samples):
                handle.write(f"{idx},{value}\n")

    print(f"[done] cpu_bound={cpu_bound} rc={rc} report={report_root}")
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
