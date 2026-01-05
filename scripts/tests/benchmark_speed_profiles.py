#!/usr/bin/env python3
"""Benchmark marsdisk.run with different performance profiles (I/O/diagnostics)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Optional


PROFILES: Dict[str, List[str]] = {
    "baseline": [],
    "no_psd_history": [
        "io.psd_history=false",
    ],
    "no_psd_high_stride": [
        "io.psd_history=false",
        "io.series_stride=5000",
        "io.diagnostics_stride=50000",
        "io.psd_history_stride=50000",
    ],
    "no_checkpoint": [
        "numerics.checkpoint.enabled=false",
    ],
    "no_psd_no_checkpoint": [
        "io.psd_history=false",
        "numerics.checkpoint.enabled=false",
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _parse_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [chunk for chunk in raw.replace(",", " ").split() if chunk]
    return parts


def _load_base_overrides(path: Path, *, strip_archive: bool) -> List[str]:
    lines: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if strip_archive and stripped.startswith("io.archive."):
            continue
        lines.append(stripped)
    return lines


def _write_overrides(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def _run_case(
    *,
    config_path: Path,
    overrides_path: Path,
    log_path: Path,
    env: Dict[str, str],
) -> Dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "marsdisk.run",
        "--config",
        str(config_path),
        "--overrides-file",
        str(overrides_path),
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            cmd,
            cwd=_repo_root(),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - start
    return {
        "returncode": result.returncode,
        "elapsed_sec": elapsed,
        "log": str(log_path),
        "command": cmd,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--config",
        default="configs/sweep_temp_supply/temp_supply_T4000_eps1.yml",
        help="Config file for the benchmark runs.",
    )
    ap.add_argument(
        "--base-overrides",
        default="scripts/runsets/windows/overrides.txt",
        help="Base overrides file (use 'none' to skip).",
    )
    ap.add_argument(
        "--profiles",
        default="",
        help="Comma/space-separated profile names (default: all).",
    )
    ap.add_argument(
        "--out-root",
        default="out/tests",
        help="Output root directory.",
    )
    ap.add_argument("--t-end-years", type=float, default=0.02, help="numerics.t_end_years override.")
    ap.add_argument("--dt-init", default="20", help="numerics.dt_init override.")
    ap.add_argument("--repeat", type=int, default=2, help="Number of repeats per profile.")
    ap.add_argument(
        "--strip-archive",
        action="store_true",
        help="Strip io.archive.* lines from base overrides.",
    )
    ap.add_argument(
        "--disable-archive",
        action="store_true",
        help="Append io.archive.enabled=false to all profiles.",
    )
    ap.add_argument(
        "--extra-override",
        action="append",
        default=[],
        help="Extra override line(s) applied to all profiles.",
    )
    args = ap.parse_args()

    if args.repeat < 1:
        raise SystemExit("repeat must be >= 1")

    config_path = (_repo_root() / args.config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")

    base_overrides_path: Optional[Path]
    if args.base_overrides.lower() in {"none", "null", "off", ""}:
        base_overrides_path = None
    else:
        base_overrides_path = (_repo_root() / args.base_overrides).resolve()
        if not base_overrides_path.exists():
            raise FileNotFoundError(f"base overrides not found: {base_overrides_path}")

    profile_list = _parse_list(args.profiles)
    if not profile_list:
        profile_list = list(PROFILES.keys())
    missing = [name for name in profile_list if name not in PROFILES]
    if missing:
        raise SystemExit(f"Unknown profile(s): {', '.join(missing)}")

    base_overrides: List[str] = []
    if base_overrides_path is not None:
        base_overrides = _load_base_overrides(base_overrides_path, strip_archive=args.strip_archive)

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")

    timestamp = _timestamp()
    out_root = Path(args.out_root).resolve() / f"bench_speed_profiles_{timestamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, object] = {
        "config": str(config_path),
        "base_overrides": str(base_overrides_path) if base_overrides_path else None,
        "strip_archive": bool(args.strip_archive),
        "disable_archive": bool(args.disable_archive),
        "t_end_years": args.t_end_years,
        "dt_init": args.dt_init,
        "repeat": args.repeat,
        "profiles": {},
    }

    ranking: List[Dict[str, object]] = []

    for profile_name in profile_list:
        profile_dir = out_root / profile_name
        run_dir = profile_dir / "run"
        overrides_path = profile_dir / "overrides.txt"
        overrides: List[str] = []
        overrides.extend(base_overrides)
        overrides.append(f"numerics.t_end_years={args.t_end_years}")
        overrides.append(f"numerics.dt_init={args.dt_init}")
        if args.disable_archive:
            overrides.append("io.archive.enabled=false")
        overrides.extend(args.extra_override)
        overrides.extend(PROFILES[profile_name])
        overrides.append(f"io.outdir={run_dir}")
        _write_overrides(overrides_path, overrides)

        runs: List[Dict[str, object]] = []
        for idx in range(args.repeat):
            log_path = profile_dir / f"run_{idx + 1}.log"
            result = _run_case(
                config_path=config_path,
                overrides_path=overrides_path,
                log_path=log_path,
                env=env,
            )
            runs.append(result)
            if result["returncode"] != 0:
                break

        elapsed_ok = [r["elapsed_sec"] for r in runs if r["returncode"] == 0]
        profile_summary: Dict[str, object] = {
            "overrides": PROFILES[profile_name],
            "runs": runs,
            "ok_runs": len(elapsed_ok),
            "status": "ok" if elapsed_ok else "failed",
        }
        if elapsed_ok:
            profile_summary["median_sec"] = median(elapsed_ok)
            profile_summary["min_sec"] = min(elapsed_ok)
            profile_summary["max_sec"] = max(elapsed_ok)
            ranking.append(
                {
                    "profile": profile_name,
                    "median_sec": profile_summary["median_sec"],
                    "min_sec": profile_summary["min_sec"],
                    "max_sec": profile_summary["max_sec"],
                }
            )
        summary["profiles"][profile_name] = profile_summary

    ranking_sorted = sorted(ranking, key=lambda item: float(item["median_sec"]))
    summary["ranking"] = ranking_sorted
    if ranking_sorted:
        summary["best_profile"] = ranking_sorted[0]["profile"]

    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    csv_lines = ["profile,median_sec,min_sec,max_sec"]
    for item in ranking_sorted:
        csv_lines.append(
            f"{item['profile']},{item['median_sec']:.6f},{item['min_sec']:.6f},{item['max_sec']:.6f}"
        )
    (out_root / "summary.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    print(f"[info] benchmark summary: {summary_path}")
    if ranking_sorted:
        print(f"[info] best profile: {ranking_sorted[0]['profile']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
