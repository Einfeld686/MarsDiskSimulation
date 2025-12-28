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

PATH_ENV_VARS = ("TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "COMSPEC")
MAX_WARN_PATH_LEN = 240
WINDOWS_PATH_INVALID_CHARS = set('<>:"|?*')
CMD_UNSAFE_CHARS = "!"


def _load_overrides(path: Path) -> tuple[dict[str, str], list[str]]:
    data: dict[str, str] = {}
    duplicates: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key in data and key not in duplicates:
            duplicates.append(key)
        data[key] = val.strip()
    return data, duplicates


def _contains_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _contains_cmd_unsafe(text: str) -> bool:
    return any(ch in text for ch in CMD_UNSAFE_CHARS)


def _is_windows_abs(path_str: str) -> bool:
    try:
        return PureWindowsPath(path_str).is_absolute()
    except Exception:
        return False


def _normalize_windows(path_str: str) -> str:
    return str(PureWindowsPath(path_str)).lower()


def _is_windows() -> bool:
    return os.name == "nt"


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


def _check_env_paths(errors: list[str], warnings: list[str]) -> None:
    for key in PATH_ENV_VARS:
        value = os.environ.get(key, "")
        if not value:
            continue
        if _contains_cmd_unsafe(value):
            errors.append(f"{key} contains '!': {value}")
        if _contains_non_ascii(value):
            warnings.append(f"{key} contains non-ASCII characters: {value}")
        if key == "COMSPEC" and not Path(value).exists():
            errors.append(f"COMSPEC not found: {value}")
        if len(value) >= MAX_WARN_PATH_LEN:
            warnings.append(f"{key} path length >= {MAX_WARN_PATH_LEN}: {value}")


def _check_path_value(label: str, value: str, errors: list[str], warnings: list[str]) -> None:
    if not value:
        return
    if _contains_cmd_unsafe(value):
        errors.append(f"{label} contains '!': {value}")
    if _contains_non_ascii(value):
        warnings.append(f"{label} contains non-ASCII characters: {value}")
    if len(value) >= MAX_WARN_PATH_LEN:
        warnings.append(f"{label} path length >= {MAX_WARN_PATH_LEN}: {value}")
    if _has_invalid_windows_chars(value):
        errors.append(f"{label} contains invalid Windows path chars: {value}")
    if value.endswith((" ", ".")):
        warnings.append(f"{label} ends with space/dot: {value}")
    if value.startswith("\\\\") and label != "io.archive.dir":
        warnings.append(f"{label} is a UNC path: {value}")


def _has_invalid_windows_chars(value: str) -> bool:
    for idx, ch in enumerate(value):
        if ch not in WINDOWS_PATH_INVALID_CHARS:
            continue
        if ch == ":":
            if idx == 1 and len(value) >= 2 and value[0].isalpha():
                continue
            if value.startswith("\\\\?\\") or value.startswith("\\\\.\\"):
                if idx == 5 and len(value) > 5 and value[4].isalpha():
                    continue
            return True
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--overrides", required=True, type=Path)
    ap.add_argument("--out-root", default="", help="Output root (optional).")
    ap.add_argument("--require-git", action="store_true")
    ap.add_argument("--require-powershell", action="store_true")
    ap.add_argument(
        "--simulate-windows",
        action="store_true",
        help="Run Windows-style checks even on non-Windows hosts.",
    )
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    if sys.version_info < (3, 11):
        warnings.append(f"python {sys.version.split()[0]} < 3.11")
    is_windows_host = _is_windows()
    if not is_windows_host and not args.simulate_windows:
        warnings.append("host is not Windows; cmd-specific checks may be incomplete")

    for label, path in {
        "repo_root": args.repo_root,
        "config": args.config,
        "overrides": args.overrides,
    }.items():
        if not path.exists():
            errors.append(f"{label} missing: {path}")
        _check_path_value(label, str(path), errors, warnings)

    if args.config.suffix.lower() not in {".yml", ".yaml"}:
        warnings.append(f"config extension is not .yml/.yaml: {args.config.name}")

    if args.out_root:
        _check_path_value("out_root", args.out_root, errors, warnings)
        if not _is_windows_abs(args.out_root):
            warnings.append(f"out_root is not absolute: {args.out_root}")

    if args.require_git:
        _check_cmd("git", errors)
    _check_cmd("python", errors)
    if args.require_powershell:
        _check_powershell(errors, warnings)

    overrides = {}
    if args.overrides.exists():
        overrides, duplicates = _load_overrides(args.overrides)
        for key in duplicates:
            warnings.append(f"overrides duplicated key: {key}")
        for key, expected in REQUIRED_ARCHIVE_KEYS.items():
            if key not in overrides:
                errors.append(f"overrides missing: {key}")
                continue
            if expected is not None and overrides[key].lower() != expected:
                errors.append(f"overrides {key}={overrides[key]} (expected {expected})")
        for key, value in overrides.items():
            if _contains_cmd_unsafe(value):
                warnings.append(f"overrides value contains '!': {key}={value}")
            if _contains_non_ascii(value):
                warnings.append(f"overrides value contains non-ASCII chars: {key}={value}")

        archive_dir = overrides.get("io.archive.dir", "")
        if archive_dir:
            _check_path_value("io.archive.dir", archive_dir, errors, warnings)
            if not _is_windows_abs(archive_dir):
                errors.append(f"io.archive.dir not absolute: {archive_dir}")
            if args.out_root:
                if _normalize_windows(args.out_root) == _normalize_windows(archive_dir):
                    errors.append("out-root matches io.archive.dir (must be internal)")
            if is_windows_host:
                drive = PureWindowsPath(archive_dir).drive
                if drive:
                    drive_root = Path(f"{drive}\\")
                    if not drive_root.exists():
                        errors.append(f"io.archive.dir drive missing: {drive}")
                else:
                    errors.append(f"io.archive.dir has no drive letter: {archive_dir}")
            else:
                warnings.append("non-Windows host; drive availability not checked")

    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    _check_temp_dir(temp_dir, errors, warnings)
    _check_env_paths(errors, warnings)

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
