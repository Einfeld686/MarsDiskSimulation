#!/usr/bin/env python3
"""Run marsdisk with auto-tune enabled by default."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    args = sys.argv[1:]
    if "--auto-tune" not in args:
        args = ["--auto-tune", *args]
    cmd = [sys.executable, "-m", "marsdisk.run", *args]
    return subprocess.call(cmd, env=os.environ.copy())


if __name__ == "__main__":
    raise SystemExit(main())
