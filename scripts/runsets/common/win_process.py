#!/usr/bin/env python3
"""Process helpers for Windows cmd runsets."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Iterable


WINDOW_STYLES = {
    "hidden": 0,
    "normal": 1,
    "minimized": 2,
    "maximized": 3,
}


def _parse_pids(raw: str) -> list[int]:
    pids: list[int] = []
    for token in raw.split():
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid > 0:
            pids.append(pid)
    return pids


def _tasklist_has_pid(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    return str(pid) in result.stdout


def _alive_pids(pids: Iterable[int]) -> list[int]:
    alive: list[int] = []
    if os.name == "nt":
        for pid in pids:
            if _tasklist_has_pid(pid):
                alive.append(pid)
        return alive
    for pid in pids:
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        alive.append(pid)
    return alive


def _launch(cmd: str, window_style: str | None) -> int:
    if os.name != "nt":
        proc = subprocess.Popen(cmd, shell=True)
        print(proc.pid)
        return 0

    style_key = (window_style or "").strip().lower()
    show = WINDOW_STYLES.get(style_key)

    startupinfo = None
    creationflags = 0
    if show is not None:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = show

    if style_key == "hidden":
        creationflags |= subprocess.CREATE_NO_WINDOW
    else:
        creationflags |= subprocess.CREATE_NEW_CONSOLE

    proc = subprocess.Popen(
        ["cmd.exe", "/c", cmd],
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    print(proc.pid)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command")

    launch = sub.add_parser("launch", help="Launch a cmd.exe job and print its PID.")
    launch.add_argument("--cmd", default=None, help="Command string to run.")
    launch.add_argument("--window-style", default=None, help="Normal/Hidden/Minimized/Maximized.")

    alive = sub.add_parser("alive", help="Check alive PIDs and print list|count.")
    alive.add_argument("--pids", default=None, help="Space-separated PIDs.")

    args = ap.parse_args()

    if args.command == "launch":
        cmd = args.cmd or os.environ.get("JOB_CMD", "")
        if not cmd:
            print("[error] missing JOB_CMD", file=sys.stderr)
            return 2
        window_style = args.window_style or os.environ.get("PARALLEL_WINDOW_STYLE", "")
        return _launch(cmd, window_style)

    if args.command == "alive":
        raw = args.pids or os.environ.get("JOB_PIDS", "")
        if not raw:
            print("__NONE__|0")
            return 0
        alive_pids = _alive_pids(_parse_pids(raw))
        if not alive_pids:
            print("__NONE__|0")
            return 0
        print(f"{' '.join(str(pid) for pid in alive_pids)}|{len(alive_pids)}")
        return 0

    ap.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
