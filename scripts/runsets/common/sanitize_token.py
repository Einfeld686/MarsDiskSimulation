#!/usr/bin/env python3
"""Sanitize or regenerate token-like environment variables."""
from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path


_INVALID_RE = re.compile(r"[=!&|<>?*\t\r\n]")


def _sanitize(value: str) -> str:
    value = value.replace(":", "")
    value = value.replace(" ", "_")
    value = value.replace("/", "-")
    value = value.replace("\\", "-")
    return value


def _timestamp(ts_script: Path) -> str:
    try:
        result = subprocess.run(
            [sys.executable, str(ts_script)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        result = None
    if result and result.returncode == 0:
        ts = (result.stdout or "").strip()
        if ts:
            return ts
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True, help="Environment variable name to sanitize")
    ap.add_argument("--mode", default="default", choices=["default", "timestamp"])
    ap.add_argument("--fallback", default="", help="Fallback token when mode=default")
    ap.add_argument("--timestamp-script", required=True, help="Path to timestamp.py")
    args = ap.parse_args()

    raw = os.environ.get(args.name, "")
    value = _sanitize(raw)
    needs_regen = (not value) or bool(_INVALID_RE.search(value))

    if args.mode == "timestamp" and needs_regen:
        value = _sanitize(_timestamp(Path(args.timestamp_script)))
    elif args.mode == "default" and needs_regen:
        fallback = args.fallback or "temp_supply_sweep"
        value = _sanitize(fallback)

    if not value:
        return 2
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
