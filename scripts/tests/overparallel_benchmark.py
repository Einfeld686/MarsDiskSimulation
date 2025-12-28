from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _run_scenario(
    *,
    label: str,
    cmd_base: list[str],
    out_root: Path,
    parallel_jobs: int,
    env_overrides: dict[str, str],
) -> tuple[int, float, list[Path]]:
    outdirs: list[Path] = []
    procs: list[subprocess.Popen[bytes]] = []
    for idx in range(parallel_jobs):
        outdir = out_root / label / f"run_{idx:02d}"
        outdirs.append(outdir)
        cmd = cmd_base + ["--override", f"io.outdir={outdir}"]
        env = os.environ.copy()
        env.update(env_overrides)
        procs.append(subprocess.Popen(cmd, env=env))
    start = time.perf_counter()
    rc = 0
    for proc in procs:
        rc = max(rc, proc.wait())
    elapsed = time.perf_counter() - start
    return rc, elapsed, outdirs


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

    rc_parallel, t_parallel, out_parallel = _run_scenario(
        label="parallel",
        cmd_base=cmd_base,
        out_root=out_root,
        parallel_jobs=args.parallel_jobs,
        env_overrides=parallel_env,
    )
    rc_control, t_control, out_control = _run_scenario(
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

    if rc_parallel != 0 or rc_control != 0:
        return 2
    if args.fail_on_slowdown and ratio >= args.slowdown_threshold:
        print("[error] slowdown exceeds threshold; consider reducing cell/process concurrency.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
