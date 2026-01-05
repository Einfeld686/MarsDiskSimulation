#!/usr/bin/env python3
"""Compare sweep-parallel vs cell-parallel wall time using run_sweep.cmd."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _parse_number_list(raw: str) -> List[float]:
    parts = [chunk for chunk in raw.replace(",", " ").split() if chunk]
    return [float(part) for part in parts]


def _format_yaml_list(values: Iterable[float]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _write_study(path: Path, *, t_list: List[float], eps_list: List[float], tau_list: List[float], sweep_tag: str) -> None:
    lines = [
        f"T_LIST: {_format_yaml_list(t_list)}",
        f"EPS_LIST: {_format_yaml_list(eps_list)}",
        f"TAU_LIST: {_format_yaml_list(tau_list)}",
        f"SWEEP_TAG: {sweep_tag}",
    ]
    _write_text(path, "\n".join(lines) + "\n")


def _build_overrides(base_path: Path, extra_lines: List[str], out_path: Path) -> None:
    base_text = base_path.read_text(encoding="utf-8")
    combined = base_text.rstrip() + "\n"
    if extra_lines:
        combined += "\n# Added by sweep_vs_cell_parallel_speed_check.py\n"
        combined += "\n".join(extra_lines) + "\n"
    _write_text(out_path, combined)


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


def _run_cmd(cmd: List[str], *, env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, check=False)


def _build_cmd(
    cmd_path: Path,
    *,
    overrides_path: Path,
    out_root: Path,
    study_path: Path,
    config_path: Path | None,
    with_plot: bool,
    with_eval: bool,
) -> List[str]:
    cmd = ["cmd.exe", "/c", str(cmd_path)]
    if config_path is not None:
        cmd.extend(["--config", str(config_path)])
    cmd.extend(["--overrides", str(overrides_path), "--out-root", str(out_root), "--study", str(study_path)])
    if not with_plot:
        cmd.append("--no-plot")
    if not with_eval:
        cmd.append("--no-eval")
    return cmd


def _run_case(
    *,
    label: str,
    cmd_path: Path,
    overrides_path: Path,
    out_root: Path,
    study_path: Path,
    config_path: Path | None,
    env: Dict[str, str],
    debug_log: Path,
    trace_log: Path,
    with_plot: bool,
    with_eval: bool,
) -> Dict[str, Any]:
    env_case = dict(env)
    env_case["DEBUG"] = "1"
    env_case["DEBUG_LOG_FILE"] = str(debug_log)
    env_case["TRACE_LOG"] = str(trace_log)
    cmd = _build_cmd(
        cmd_path,
        overrides_path=overrides_path,
        out_root=out_root,
        study_path=study_path,
        config_path=config_path,
        with_plot=with_plot,
        with_eval=with_eval,
    )
    start = time.perf_counter()
    result = _run_cmd(cmd, env=env_case, cwd=_repo_root())
    elapsed = time.perf_counter() - start
    parallel_config = _parse_parallel_final(debug_log)
    return {
        "label": label,
        "returncode": result.returncode,
        "elapsed_sec": elapsed,
        "command": cmd,
        "parallel_config": parallel_config,
        "debug_log": str(debug_log),
        "trace_log": str(trace_log),
        "out_root": str(out_root),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cmd", default="scripts/runsets/windows/run_sweep.cmd", help="run_sweep.cmd path.")
    ap.add_argument("--config", default=None, help="Optional config override.")
    ap.add_argument(
        "--overrides",
        default="scripts/runsets/windows/overrides.txt",
        help="Base overrides file path.",
    )
    ap.add_argument("--study", default=None, help="Optional study YAML path.")
    ap.add_argument("--out-root", default="out/tests", help="Output root directory.")
    ap.add_argument("--parallel-jobs", type=int, default=6, help="PARALLEL_JOBS for sweep-parallel.")
    ap.add_argument("--cell-jobs", type=int, default=4, help="MARSDISK_CELL_JOBS for cell-parallel.")
    ap.add_argument("--t-list", default="4000,3000", help="Comma/space-separated T list.")
    ap.add_argument("--eps-list", default="1.0,0.5", help="Comma/space-separated epsilon list.")
    ap.add_argument("--tau-list", default="1.0", help="Comma/space-separated tau list.")
    ap.add_argument("--t-end-years", type=float, default=0.02, help="numerics.t_end_years override.")
    ap.add_argument("--dt-init", default="20", help="numerics.dt_init override.")
    ap.add_argument("--with-plot", action="store_true", help="Run plot hook.")
    ap.add_argument("--with-eval", action="store_true", help="Run eval hook.")
    ap.add_argument("--fast-io", action="store_true", help="Disable streaming for a quick test.")
    args = ap.parse_args()

    if os.name != "nt":
        print("[error] This test uses run_sweep.cmd and must be run on Windows.")
        return 2

    repo_root = _repo_root()
    cmd_path = (repo_root / args.cmd).resolve()
    if not cmd_path.exists():
        raise FileNotFoundError(f"run_sweep.cmd not found: {cmd_path}")

    config_path = Path(args.config).resolve() if args.config else None
    if config_path is not None and not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    base_overrides = (repo_root / args.overrides).resolve()
    if not base_overrides.exists():
        raise FileNotFoundError(f"Overrides not found: {base_overrides}")

    t_list = _parse_number_list(args.t_list)
    eps_list = _parse_number_list(args.eps_list)
    tau_list = _parse_number_list(args.tau_list)

    timestamp = _timestamp()
    base_out = Path(args.out_root).resolve() / f"sweep_vs_cell_parallel_{timestamp}"
    artifacts = base_out / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    study_path = Path(args.study).resolve() if args.study else artifacts / "study.yml"
    if args.study is None:
        _write_study(
            study_path,
            t_list=t_list,
            eps_list=eps_list,
            tau_list=tau_list,
            sweep_tag="sweep_vs_cell_parallel",
        )

    overrides_path = artifacts / "overrides_effective.txt"
    extra_overrides = [
        f"numerics.t_end_years={args.t_end_years}",
        f"numerics.dt_init={args.dt_init}",
    ]
    _build_overrides(base_overrides, extra_overrides, overrides_path)

    common_env = os.environ.copy()
    common_env.setdefault("SKIP_PIP", "1")
    common_env.setdefault("REQUIREMENTS_INSTALLED", "1")
    common_env.setdefault("QUIET_MODE", "1")
    common_env.setdefault("COOL_TO_K", "none")
    if args.fast_io:
        common_env["FORCE_STREAMING_OFF"] = "1"
        common_env["IO_STREAMING"] = "off"

    sweep_env = dict(common_env)
    sweep_env["SWEEP_PARALLEL"] = "1"
    sweep_env["PARALLEL_JOBS"] = str(max(args.parallel_jobs, 1))
    sweep_env["MARSDISK_CELL_PARALLEL"] = "0"
    sweep_env["MARSDISK_CELL_JOBS"] = "1"
    sweep_env.setdefault("CELL_THREAD_LIMIT", "1")

    cell_env = dict(common_env)
    cell_env["SWEEP_PARALLEL"] = "0"
    cell_env["PARALLEL_JOBS"] = "1"
    cell_env["MARSDISK_CELL_PARALLEL"] = "1"
    cell_env["MARSDISK_CELL_JOBS"] = str(max(args.cell_jobs, 1))
    cell_env.setdefault("CELL_THREAD_LIMIT", "1")

    sweep_out_root = base_out / "sweep_parallel"
    cell_out_root = base_out / "cell_parallel"

    results = {
        "timestamp": timestamp,
        "study_path": str(study_path),
        "overrides_path": str(overrides_path),
        "parallel_jobs": args.parallel_jobs,
        "cell_jobs": args.cell_jobs,
        "t_list": t_list,
        "eps_list": eps_list,
        "tau_list": tau_list,
        "cases": [],
    }

    print("[info] running sweep-parallel case...")
    sweep_result = _run_case(
        label="sweep_parallel",
        cmd_path=cmd_path,
        overrides_path=overrides_path,
        out_root=sweep_out_root,
        study_path=study_path,
        config_path=config_path,
        env=sweep_env,
        debug_log=artifacts / "sweep_debug.log",
        trace_log=artifacts / "sweep_trace.log",
        with_plot=args.with_plot,
        with_eval=args.with_eval,
    )
    results["cases"].append(sweep_result)

    print("[info] running cell-parallel case...")
    cell_result = _run_case(
        label="cell_parallel",
        cmd_path=cmd_path,
        overrides_path=overrides_path,
        out_root=cell_out_root,
        study_path=study_path,
        config_path=config_path,
        env=cell_env,
        debug_log=artifacts / "cell_debug.log",
        trace_log=artifacts / "cell_trace.log",
        with_plot=args.with_plot,
        with_eval=args.with_eval,
    )
    results["cases"].append(cell_result)

    sweep_time = sweep_result.get("elapsed_sec")
    cell_time = cell_result.get("elapsed_sec")
    speedup_sweep_over_cell = None
    speedup_cell_over_sweep = None
    if isinstance(sweep_time, (int, float)) and isinstance(cell_time, (int, float)):
        if sweep_time > 0:
            speedup_cell_over_sweep = sweep_time / cell_time if cell_time else None
            speedup_sweep_over_cell = cell_time / sweep_time
    results["speedup_sweep_over_cell"] = speedup_sweep_over_cell
    results["speedup_cell_over_sweep"] = speedup_cell_over_sweep

    summary_path = base_out / "speed_check_summary.json"
    _write_json(summary_path, results)

    print(f"[done] summary: {summary_path}")
    if speedup_sweep_over_cell is not None:
        print(f"[done] speedup(sweep/cell) = {speedup_sweep_over_cell:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
