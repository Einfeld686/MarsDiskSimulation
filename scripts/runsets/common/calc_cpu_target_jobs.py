#!/usr/bin/env python3
"""Compute target cores and sweep-parallel jobs from CPU utilization percent."""
from __future__ import annotations

import math
import os


def _parse_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value


def main() -> int:
    cpu_logical = _parse_int("CELL_CPU_LOGICAL", 0)
    if cpu_logical <= 0:
        cpu_logical = os.cpu_count() or 1
    target_percent = _parse_int("CPU_UTIL_TARGET_PERCENT", 0)
    max_percent = _parse_int("CPU_UTIL_TARGET_MAX_PERCENT", 90)
    if target_percent < 0:
        target_percent = 0
    if target_percent > 100:
        target_percent = 100
    if max_percent <= 0:
        max_percent = 90
    if max_percent > 100:
        max_percent = 100
    if target_percent > max_percent:
        target_percent = max_percent
    cell_jobs = _parse_int("MARSDISK_CELL_JOBS", 1)
    if cell_jobs <= 0:
        cell_jobs = 1

    if target_percent == 0:
        target_cores = 0
        parallel_jobs = 1
    else:
        target_cores = max(1, int(math.ceil(cpu_logical * target_percent / 100.0)))
        parallel_jobs = max(1, int(math.ceil(target_cores / cell_jobs)))

    print(f"{target_cores}|{parallel_jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
