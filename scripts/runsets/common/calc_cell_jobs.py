#!/usr/bin/env python3
"""Compute cell-parallel defaults for cmd runsets."""
from __future__ import annotations

import ctypes
import math
import os
import sys


def _parse_fraction(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0 or value > 1:
        return default
    return value


def _get_cpu_logical() -> int:
    env_val = os.environ.get("NUMBER_OF_PROCESSORS", "")
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


def main() -> int:
    mem_fraction = _parse_fraction("CELL_MEM_FRACTION", 0.7)
    cpu_fraction = _parse_fraction("CELL_CPU_FRACTION", 0.7)
    mem_total_gb = _get_mem_total_gb()
    cpu_logical = _get_cpu_logical()
    jobs = max(int(math.floor(cpu_logical * cpu_fraction)), 1)
    print(f"{mem_total_gb}|{cpu_logical}|{mem_fraction}|{cpu_fraction}|{jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
