#!/usr/bin/env python3
"""Preflight checks for Windows cmd runsets."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath


REQUIRED_ARCHIVE_KEYS = {
    "io.archive.enabled": "true",
    "io.archive.dir": None,
    "io.archive.merge_target": "external",
    "io.archive.verify_level": "standard_plus",
    "io.archive.keep_local": "metadata",
}


def _load_overrides(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip()
    return data


def _contains_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _contains_cmd_unsafe(text: str) -> bool:
    return "!" in text


def _is_windows_abs(path_str: str) -> bool:
    try:
        return PureWindowsPath(path_str).is_absolute()
    except Exception:
        return False


def _normalize_windows(path_str: str) -> str:
    return str(PureWindowsPath(path_str)).lower()


def _check_cmd(name: str, errors: list[str]) -> None:
    if shutil.which(name) is None:
        errors.append(f"{name} not found in PATH")


def _check_powershell(errors: list[str], warnings: list[str]) -> None:
    if shutil.which("powershell") is None:
        errors.append("powershell not found in PATH")
        return
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Write-Output ok"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        errors.append(f"powershell exec failed: {exc}")
        return
    if result.returncode != 0:
        errors.append(f"powershell returned {result.returncode}")
    if "ok" not in result.stdout.lower():
        warnings.append("powershell output unexpected")


def _check_temp_dir(temp_dir: str | None, errors: list[str], warnings: list[str]) -> None:
    if not temp_dir:
        errors.append("TEMP/TMP is not set")
        return
    temp_path = Path(temp_dir)
    if _contains_cmd_unsafe(temp_dir):
        errors.append(f"TEMP/TMP contains '!': {temp_dir}")
    if _contains_non_ascii(temp_dir):
        warnings.append(f"TEMP/TMP contains non-ASCII characters: {temp_dir}")
    try:
        temp_path.mkdir(parents=True, exist_ok=True)
        test_path = temp_path / "marsdisk_preflight_tmp.txt"
        test_path.write_text("ok", encoding="ascii")
        test_path.unlink()
    except Exception as exc:
        errors.append(f"TEMP/TMP not writable: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--overrides", required=True, type=Path)
    ap.add_argument("--out-root", default="", help="Output root (optional).")
    ap.add_argument("--require-git", action="store_true")
    ap.add_argument("--require-powershell", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    if sys.version_info < (3, 11):
        warnings.append(f"python {sys.version.split()[0]} < 3.11")

    for label, path in {
        "repo_root": args.repo_root,
        "config": args.config,
        "overrides": args.overrides,
    }.items():
        if not path.exists():
            errors.append(f"{label} missing: {path}")
        text = str(path)
        if _contains_cmd_unsafe(text):
            errors.append(f"{label} path contains '!': {path}")
        if _contains_non_ascii(text):
            warnings.append(f"{label} path contains non-ASCII characters: {path}")

    if args.require_git:
        _check_cmd("git", errors)
    _check_cmd("python", errors)
    if args.require_powershell:
        _check_powershell(errors, warnings)

    overrides = {}
    if args.overrides.exists():
        overrides = _load_overrides(args.overrides)
        for key, expected in REQUIRED_ARCHIVE_KEYS.items():
            if key not in overrides:
                errors.append(f"overrides missing: {key}")
                continue
            if expected is not None and overrides[key].lower() != expected:
                errors.append(f"overrides {key}={overrides[key]} (expected {expected})")

        archive_dir = overrides.get("io.archive.dir", "")
        if archive_dir:
            if not _is_windows_abs(archive_dir):
                errors.append(f"io.archive.dir not absolute: {archive_dir}")
            if args.out_root:
                if _normalize_windows(args.out_root) == _normalize_windows(archive_dir):
                    errors.append("out-root matches io.archive.dir (must be internal)")

    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    _check_temp_dir(temp_dir, errors, warnings)

    if errors:
        print("[preflight] failed")
        for msg in errors:
            print(f"[error] {msg}")
        if warnings:
            for msg in warnings:
                print(f"[warn] {msg}")
        return 1
    print("[preflight] ok")
    if warnings:
        for msg in warnings:
            print(f"[warn] {msg}")
        if args.strict:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
