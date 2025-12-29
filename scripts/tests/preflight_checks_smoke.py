#!/usr/bin/env python3
"""Smoke checks for preflight_checks.py behavior."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "scripts" / "runsets" / "windows" / "preflight_checks.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("preflight_checks", PREFLIGHT_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Failed to load {PREFLIGHT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_overrides(path: Path, archive_dir: str) -> None:
    _write_text(
        path,
        "\n".join(
            [
                "io.archive.enabled=true",
                f"io.archive.dir={archive_dir}",
                "io.archive.merge_target=external",
                "io.archive.verify_level=standard_plus",
                "io.archive.keep_local=metadata",
                "",
            ]
        ),
    )


def _run_preflight(module: object, argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        old_argv = sys.argv
        sys.argv = argv
        try:
            rc = module.main()
        finally:
            sys.argv = old_argv
    return rc, stdout.getvalue()


def _check_unc_warning(module: object, temp_dir: Path) -> None:
    config = temp_dir / "config.yml"
    overrides = temp_dir / "overrides.txt"
    cmd = temp_dir / "noop.cmd"
    _write_text(config, "dummy: 1\n")
    _write_overrides(overrides, r"E:\archive")
    _write_text(cmd, "echo ok\n")

    argv = [
        "preflight_checks.py",
        "--repo-root",
        str(temp_dir),
        "--config",
        str(config),
        "--overrides",
        str(overrides),
        "--out-root",
        r"\\server\share",
        "--cmd",
        str(cmd),
        "--skip-env",
        "--skip-repo-scan",
    ]
    rc, out = _run_preflight(module, argv)
    if rc != 0:
        raise RuntimeError("UNC warning check failed\n" + out)
    if out.count("out_root is a UNC path") != 1:
        raise RuntimeError("UNC warning count mismatch\n" + out)


def _check_comment_only_delayed_expansion(module: object, temp_dir: Path) -> None:
    config = temp_dir / "config.yml"
    overrides = temp_dir / "overrides_bang.txt"
    cmd = temp_dir / "comment_only.cmd"
    _write_text(config, "dummy: 1\n")
    _write_overrides(overrides, r"E:\temp!dir")
    _write_text(
        cmd,
        "\n".join(
            [
                "@echo off",
                "rem enabledelayedexpansion should be ignored",
                ":: cmd /v:on should be ignored",
                "rem setlocal enabledelayedexpansion should be ignored",
                "@rem cmd /v:on should also be ignored",
                "echo ok",
                "",
            ]
        ),
    )

    argv = [
        "preflight_checks.py",
        "--repo-root",
        str(temp_dir),
        "--config",
        str(config),
        "--overrides",
        str(overrides),
        "--cmd",
        str(cmd),
        "--skip-env",
        "--skip-repo-scan",
    ]
    rc, out = _run_preflight(module, argv)
    if rc != 0:
        raise RuntimeError("Delayed expansion comment check failed\n" + out)
    if "contains '!': E:\\temp!dir" not in out:
        raise RuntimeError("Expected warning for '!'\n" + out)


def main() -> int:
    module = _load_module()
    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root)
        _check_unc_warning(module, temp_dir)
        _check_comment_only_delayed_expansion(module, temp_dir)
    print("[smoke] preflight checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
