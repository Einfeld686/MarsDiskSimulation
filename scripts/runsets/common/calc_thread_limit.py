#!/usr/bin/env python3
"""Compute thread cap for cell-parallel runs."""
from __future__ import annotations

import math
import os


def _parse_fraction(value: str | None, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0 or parsed > 1:
        return default
    return parsed


def _parse_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _get_cpu_logical() -> int:
    env_val = os.environ.get("CELL_CPU_LOGICAL") or os.environ.get("CPU_LOGICAL")
    count = _parse_int(env_val, 0)
    if count <= 0:
        count = os.cpu_count() or 0
    if count <= 0:
        count = 1
    return count


def main() -> int:
    cpu_logical = _get_cpu_logical()
    jobs = _parse_int(os.environ.get("MARSDISK_CELL_JOBS"), 1)
    fraction = _parse_fraction(
        os.environ.get("CELL_CPU_FRACTION_USED") or os.environ.get("CELL_CPU_FRACTION"),
        0.7,
    )
    limit = max(int(math.floor(cpu_logical * fraction / jobs)), 1)
    print(limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
