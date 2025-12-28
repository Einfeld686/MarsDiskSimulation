#!/usr/bin/env python3
"""Compute sweep-parallel defaults for cmd runsets."""
from __future__ import annotations

import ctypes
import math
import os


def _get_cpu_logical() -> int:
    env_val = os.environ.get("CPU_LOGICAL", "")
    try:
        count = int(env_val)
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        count = os.cpu_count() or 0
    if count <= 0:
        count = 1
    return count


def _get_mem_total_gb() -> int:
    if os.name != "nt":
        return 0
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0
    return int(status.ullTotalPhys // (1024**3))


def _parse_positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return value


def main() -> int:
    total_gb = _get_mem_total_gb()
    cpu_logical = _get_cpu_logical()
    reserve_gb = _parse_positive_float("MEM_RESERVE_GB", 4.0)
    job_mem_gb = _parse_positive_float("JOB_MEM_GB", 10.0)
    avail_gb = max(total_gb - reserve_gb, 1.0)
    mem_jobs = max(int(math.floor(avail_gb / job_mem_gb)), 1)
    parallel_jobs = max(min(cpu_logical, mem_jobs), 1)
    print(f"{total_gb}|{cpu_logical}|{parallel_jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
