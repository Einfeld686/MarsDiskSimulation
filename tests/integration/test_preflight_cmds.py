from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts" / "runsets" / "windows" / "preflight_checks.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("preflight_checks", PREFLIGHT_PATH)
    assert spec and spec.loader, f"Failed to load {PREFLIGHT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _python311_cmd() -> list[str]:
    if sys.version_info >= (3, 11):
        return [sys.executable]
    candidate = shutil.which("python3.11")
    if candidate:
        return [candidate]
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            return [launcher, "-3.11"]
    raise RuntimeError("Python 3.11+ is required to run preflight strict test")


def _run_preflight(argv: list[str], monkeypatch, capsys) -> tuple[int, str]:
    runner = _python311_cmd()
    if runner == [sys.executable] and sys.version_info >= (3, 11):
        module = _load_module()
        monkeypatch.setattr(sys, "argv", argv)
        rc = module.main()
        output = capsys.readouterr().out
        return rc, output
    result = subprocess.run(
        runner + [str(PREFLIGHT_PATH)] + argv[1:],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def test_preflight_cmds_required(monkeypatch, capsys) -> None:
    argv = [
        "preflight_checks.py",
        "--repo-root",
        str(REPO_ROOT),
        "--config",
        str(REPO_ROOT / "scripts/runsets/common/base.yml"),
        "--overrides",
        str(REPO_ROOT / "scripts/runsets/windows/overrides.txt"),
        "--cmd",
        str(REPO_ROOT / "scripts/runsets/windows/run_sweep.cmd"),
        "--cmd",
        str(REPO_ROOT / "scripts/runsets/windows/run_one.cmd"),
        "--cmd",
        str(REPO_ROOT / "scripts/research/run_temp_supply_sweep.cmd"),
        "--cmd",
        str(REPO_ROOT / "scripts/runsets/common/resolve_python.cmd"),
        "--cmd",
        str(REPO_ROOT / "scripts/runsets/common/python_exec.cmd"),
        "--cmd",
        str(REPO_ROOT / "scripts/runsets/common/sanitize_token.cmd"),
        "--cmd-exclude",
        str(REPO_ROOT / "scripts/runsets/windows/legacy"),
        "--cmd-allowlist",
        str(REPO_ROOT / "scripts/runsets/windows/preflight_allowlist.txt"),
        "--simulate-windows",
        "--allow-non-ascii",
        "--check-tools",
        "--windows-root",
        r"C:\marsdisk",
    ]
    rc, output = _run_preflight(argv, monkeypatch, capsys)
    assert rc == 0
    assert "warnings=0" in output
