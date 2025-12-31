#!/usr/bin/env python3
"""Process helpers for Windows cmd runsets."""
from __future__ import annotations

import argparse
import os
import shutil
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


def _resolve_cwd(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        path = os.path.abspath(raw)
    except OSError:
        return None
    if not os.path.isdir(path):
        return None
    return path


def _launch(cmd: str, window_style: str | None, cwd_raw: str | None) -> int:
    cwd = _resolve_cwd(cwd_raw or os.environ.get("JOB_CWD"))
    if os.name != "nt":
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd)
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

    cmd_exe = os.environ.get("COMSPEC") or "cmd.exe"
    if not os.path.isfile(cmd_exe):
        resolved = shutil.which(cmd_exe)
        if resolved:
            cmd_exe = resolved
        else:
            cmd_exe = "cmd.exe"
    proc = subprocess.Popen(
        [cmd_exe, "/c", cmd],
        startupinfo=startupinfo,
        creationflags=creationflags,
        cwd=cwd,
    )
    print(proc.pid)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command")

    launch = sub.add_parser("launch", help="Launch a cmd.exe job and print its PID.")
    launch.add_argument("--cmd", default=None, help="Command string to run.")
    launch.add_argument("--cmd-file", default=None, help="File containing command string to run.")
    launch.add_argument("--cwd", default=None, help="Working directory for the launched cmd.exe job.")
    launch.add_argument("--window-style", default=None, help="Normal/Hidden/Minimized/Maximized.")

    alive = sub.add_parser("alive", help="Check alive PIDs and print list|count.")
    alive.add_argument("--pids", default=None, help="Space-separated PIDs.")

    args = ap.parse_args()

    if args.command == "launch":
        cmd = args.cmd
        if not cmd and args.cmd_file:
            # Try multiple encodings for Windows cmd.exe output
            encodings = ["utf-8", "cp932", "latin-1"]
            for enc in encodings:
                try:
                    with open(args.cmd_file, "r", encoding=enc) as f:
                        cmd = f.read().strip()
                    break
                except (OSError, UnicodeDecodeError):
                    continue
            if not cmd:
                print(f"[error] failed to read cmd-file with any encoding", file=sys.stderr)
                return 2
        if not cmd:
            cmd = os.environ.get("JOB_CMD", "")
        if not cmd:
            print("[error] missing JOB_CMD", file=sys.stderr)
            return 2
        window_style = args.window_style or os.environ.get("PARALLEL_WINDOW_STYLE", "")
        return _launch(cmd, window_style, args.cwd)

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
