#!/usr/bin/env python3
"""Run archive transfer for a run directory."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=None, help="Run directory (defaults to RUN_DIR env)")
    args = ap.parse_args()

    run_dir = args.run_dir
    if run_dir is None:
        run_dir_env = os.environ.get("RUN_DIR")
        if run_dir_env:
            run_dir = Path(run_dir_env)
    if run_dir is None:
        print("[error] --run-dir or RUN_DIR is required", file=sys.stderr)
        return 2

    root = _repo_root()
    cmd = [sys.executable, "-m", "marsdisk.archive", "--run-dir", str(run_dir)]
    archive_dir = os.environ.get("ARCHIVE_DIR")
    if archive_dir:
        cmd += ["--archive-dir", archive_dir]
    verify_level = os.environ.get("ARCHIVE_VERIFY_LEVEL")
    if verify_level:
        cmd += ["--verify-level", verify_level]
    keep_local = os.environ.get("ARCHIVE_KEEP_LOCAL")
    if keep_local:
        cmd += ["--keep-local", keep_local]
    if os.environ.get("ARCHIVE_NO_VERIFY") in {"1", "true", "yes", "on"}:
        cmd.append("--no-verify")
    if os.environ.get("ARCHIVE_RESUME") in {"1", "true", "yes", "on"}:
        cmd.append("--archive-resume")

    result = subprocess.run(cmd, cwd=root)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
