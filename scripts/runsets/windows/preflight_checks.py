#!/usr/bin/env python3
"""Preflight checks for Windows cmd runsets."""

import argparse
import fnmatch
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
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
CMD_META_CHARS = "&<>|^()"
CMD_META_CHARS_DISPLAY = "&<>|^()"
POSIX_PATH_MARKERS = ("/Users/", "/Volumes/", "/home/", "~/")
UNC_SHARED_PREFIXES = ("\\\\psf\\", "\\\\mac\\", "\\\\vmware-host\\shared folders\\")
DEFAULT_SCAN_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "out",
    "tmp",
    "venv",
}
MAX_PATH_CLASSIC = 260
CMD_LINE_MAX = 8191
CMD_LINE_WARN_LEN = 7000
PATH_WARN_LEN = 7000
PATHEXT_REQUIRED = {".COM", ".EXE", ".BAT", ".CMD"}
CHCP_SCAN_LINES = 25
DELAYED_SETLOCAL_RE = re.compile(r"\bsetlocal\b.*\benabledelayedexpansion\b", re.I)
DELAYED_CMD_RE = re.compile(r"\bcmd(?:\.exe)?\b.*?/v\s*:\s*on\b", re.I)
DELAYED_SETLOCAL_OFF_RE = re.compile(r"\bsetlocal\b.*\bdisabledelayedexpansion\b", re.I)
DELAYED_CMD_OFF_RE = re.compile(r"\bcmd(?:\.exe)?\b.*?/v\s*:\s*off\b", re.I)
DISABLE_EXT_RE = re.compile(r"\bsetlocal\b.*\bdisableextensions\b", re.I)
ENABLE_EXT_RE = re.compile(r"\bsetlocal\b.*\benableextensions\b", re.I)
DISABLE_EXT_CMD_RE = re.compile(r"\bcmd(?:\.exe)?\b.*?/e\s*:\s*off\b", re.I)
BANG_TOKEN_RE = re.compile(r"![^!]+!")
CHCP_CMD_RE = re.compile(r"^\s*@?(?:call\s+)?chcp\b", re.I)
EXEC_CMD_RE = re.compile(r'^\s*@?(?:"[^"]+"|[^"\s]+)\.(cmd|bat)\b', re.I)
START_QUOTED_RE = re.compile(r'^\s*@?start\s+"(?!")', re.I)
START_CMD_RE = re.compile(r"^\s*@?start\b", re.I)
CMD_C_QUOTED_RE = re.compile(r'\bcmd(?:\.exe)?\b\s+/c\s+"([^"]+)"', re.I)
CMD_INVOKE_RE = re.compile(r"^\s*@?(?:call\s+)?cmd(?:\.exe)?\b", re.I)
SET_INTERACTIVE_RE = re.compile(r"\bset\s+/p\b", re.I)
EXIT_CMD_RE = re.compile(r"^\s*@?exit(?:\s+|$)", re.I)
EXIT_B_RE = re.compile(r"\bexit\s+/b\b", re.I)
FOR_CMD_RE = re.compile(r"^\s*@?for\b", re.I)
FOR_VAR_RE = re.compile(r"^%{1,2}[A-Za-z]$")
SETLOCAL_RE = re.compile(r"^\s*@?setlocal\b", re.I)
ENDLOCAL_RE = re.compile(r"^\s*@?endlocal\b", re.I)
PUSHD_RE = re.compile(r"^\s*@?pushd\b", re.I)
POPD_RE = re.compile(r"^\s*@?popd\b", re.I)
PAUSE_RE = re.compile(r"^\s*@?pause\b", re.I)
CHOICE_RE = re.compile(r"^\s*@?choice\b", re.I)
SETX_RE = re.compile(r"^\s*@?setx\b", re.I)
ERRORLEVEL_RE = re.compile(r"^\s*@?if\s+(not\s+)?errorlevel\s+(-?\d+)\b", re.I)
CMD_QUOTED_META_CHARS = "&<>|^()@"
RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


@dataclass(frozen=True)
class Issue:
    level: str
    rule: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class AllowlistEntry:
    path: str
    rules: set[str] | None


def _add_issue(
    bucket: list[Issue],
    level: str,
    rule: str,
    message: str,
    path: Path | str | None = None,
    line: int | None = None,
) -> None:
    path_str = None
    if path is not None:
        path_str = str(path)
    bucket.append(Issue(level=level, rule=rule, message=message, path=path_str, line=line))


def _error(
    bucket: list[Issue],
    rule: str,
    message: str,
    path: Path | str | None = None,
    line: int | None = None,
) -> None:
    _add_issue(bucket, "error", rule, message, path, line)


def _warn(
    bucket: list[Issue],
    rule: str,
    message: str,
    path: Path | str | None = None,
    line: int | None = None,
) -> None:
    _add_issue(bucket, "warn", rule, message, path, line)


def _info(
    bucket: list[Issue],
    rule: str,
    message: str,
    path: Path | str | None = None,
    line: int | None = None,
) -> None:
    _add_issue(bucket, "info", rule, message, path, line)


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


def _is_windows_abs(path_str: str) -> bool:
    try:
        return PureWindowsPath(path_str).is_absolute()
    except Exception:
        return False


def _normalize_windows(path_str: str) -> str:
    return str(PureWindowsPath(path_str)).lower()


def _is_windows() -> bool:
    return os.name == "nt"


def _contains_posix_path(text: str) -> bool:
    return any(marker in text for marker in POSIX_PATH_MARKERS)


def _looks_like_windows_path(value: str) -> bool:
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    return value.startswith("\\\\")


def _has_reserved_windows_name(value: str) -> bool:
    if "%" in value:
        return False
    parts = re.split(r"[\\/]+", value)
    for part in parts:
        if not part:
            continue
        base = part.split(".", 1)[0].upper()
        if base in RESERVED_DEVICE_NAMES:
            return True
    return False


def _contains_cmd_meta(text: str) -> bool:
    return any(ch in text for ch in CMD_META_CHARS)


def _has_expansion_token(value: str) -> bool:
    if re.search(r"%[^%]+%", value):
        return True
    if re.search(r"![^!]+!", value):
        return True
    return False


def _has_unsafe_bang(value: str, allow_expansion: bool) -> bool:
    if "!" not in value:
        return False
    if not allow_expansion:
        return True
    cleaned = BANG_TOKEN_RE.sub("", value)
    return "!" in cleaned


def _cmd_unsafe_issue(
    label: str,
    value: str,
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
    allow_expansion: bool,
    meta_as_error: bool = False,
    skip_rules: set[str] | None = None,
) -> None:
    def is_skipped(rule: str) -> bool:
        if not skip_rules:
            return False
        return "*" in skip_rules or rule in skip_rules

    if _has_unsafe_bang(value, allow_expansion):
        if not is_skipped("cmd.unsafe.bang"):
            if cmd_unsafe_error:
                _error(errors, "cmd.unsafe.bang", f"{label} contains '!': {value}")
            else:
                _warn(warnings, "cmd.unsafe.bang", f"{label} contains '!': {value}")
    if "%" in value and not allow_expansion:
        if not is_skipped("cmd.unsafe.percent"):
            _warn(
                warnings,
                "cmd.unsafe.percent",
                f"{label} contains '%' which can confuse cmd expansion: {value}",
            )
    if _contains_cmd_meta(value):
        if not is_skipped("cmd.unsafe.meta"):
            if meta_as_error:
                _error(
                    errors,
                    "cmd.unsafe.meta",
                    f"{label} contains cmd meta chars ({CMD_META_CHARS_DISPLAY}): {value}",
                )
            else:
                _warn(
                    warnings,
                    "cmd.unsafe.meta",
                    f"{label} contains cmd meta chars ({CMD_META_CHARS_DISPLAY}): {value}",
                )


def _check_shared_path(label: str, value: str, warnings: list[Issue]) -> None:
    lower = value.lower()
    if lower.startswith("\\\\") and not lower.startswith("\\\\?\\") and not lower.startswith("\\\\.\\"):
        if any(lower.startswith(prefix) for prefix in UNC_SHARED_PREFIXES):
            _warn(
                warnings,
                "path.unc.shared",
                f"{label} is on a shared folder ({value}); consider local drive or C:\\\\Mac"
            )
        else:
            _warn(
                warnings,
                "path.unc.generic",
                f"{label} is a UNC path ({value}); consider local drive",
            )


def _check_name_component(name: str, rel_display: str, errors: list[Issue]) -> None:
    if any(ch in name for ch in WINDOWS_PATH_INVALID_CHARS):
        _error(errors, "path.invalid_chars", f"invalid Windows name: {rel_display}")
    if "\\" in name:
        _error(errors, "path.invalid_backslash", f"invalid Windows name: {rel_display}")
    if name.endswith((" ", ".")):
        _error(errors, "path.trailing_space_dot", f"name ends with space/dot: {rel_display}")
    base = name.rstrip(" .").split(".", 1)[0].upper()
    if base in RESERVED_DEVICE_NAMES:
        _error(errors, "path.reserved_device", f"reserved Windows name: {rel_display}")


def _check_cmd(
    name: str,
    errors: list[Issue],
    warnings: list[Issue],
    warn_only: bool,
) -> None:
    if shutil.which(name) is None:
        msg = f"{name} not found in PATH"
        if warn_only:
            _warn(warnings, "tool.missing", msg)
        else:
            _error(errors, "tool.missing", msg)


def _check_python(
    errors: list[Issue],
    warnings: list[Issue],
    warn_only: bool,
    python_exe: str | None,
) -> None:
    if python_exe:
        raw = python_exe.strip()
        if raw:
            exe_token = ""
            try:
                parts = shlex.split(raw, posix=False)
            except ValueError:
                parts = raw.split()
            if parts:
                exe_token = parts[0].strip().strip('"').strip("'")
            if exe_token:
                expanded = exe_token
                if _is_windows():
                    expanded = os.path.expandvars(exe_token)
                if os.path.exists(expanded):
                    return
                if shutil.which(expanded) is not None:
                    return
            msg = f"python_exe not found: {python_exe}"
            if warn_only:
                _warn(warnings, "tool.python_exe_missing", msg)
            else:
                _error(errors, "tool.python_exe_missing", msg)
    if shutil.which("python") is not None:
        return
    if shutil.which("py") is not None:
        _warn(
            warnings,
            "tool.python_py_available",
            "python not found in PATH; 'py' is available",
        )
        return
    msg = "python not found in PATH"
    if warn_only:
        _warn(warnings, "tool.python_missing", msg)
    else:
        _error(errors, "tool.python_missing", msg)


def _coerce_registry_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _read_cmd_registry_value(root, name: str) -> object | None:
    try:
        import winreg
    except Exception:
        return None
    try:
        key = winreg.OpenKey(root, r"Software\\Microsoft\\Command Processor")
    except OSError:
        return None
    try:
        value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return value


def _read_cmd_autorun_values() -> dict[str, object]:
    try:
        import winreg
    except Exception:
        return {}
    values: dict[str, object] = {}
    for label, root in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        value = _read_cmd_registry_value(root, "AutoRun")
        if value:
            values[label] = value
    return values


def _read_cmd_extensions_enabled() -> tuple[bool | None, str | None, object | None]:
    try:
        import winreg
    except Exception:
        return None, None, None
    value = _read_cmd_registry_value(winreg.HKEY_CURRENT_USER, "EnableExtensions")
    source = "HKCU"
    if value is None:
        value = _read_cmd_registry_value(winreg.HKEY_LOCAL_MACHINE, "EnableExtensions")
        source = "HKLM"
    enabled = _coerce_registry_bool(value)
    if value is None:
        source = None
    return enabled, source, value


def _read_cmd_code_page() -> str | None:
    try:
        result = subprocess.run(
            ["cmd", "/c", "chcp"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    return output or None


def _check_powershell(errors: list[Issue], warnings: list[Issue], warn_only: bool) -> None:
    candidates = [name for name in ("powershell", "pwsh") if shutil.which(name) is not None]
    if not candidates:
        msg = "powershell/pwsh not found in PATH"
        if warn_only:
            _warn(warnings, "tool.powershell_missing", msg)
        else:
            _error(errors, "tool.powershell_missing", msg)
        return
    failures: list[str] = []
    for name in candidates:
        try:
            result = subprocess.run(
                [name, "-NoProfile", "-Command", "Write-Output ok"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception as exc:
            failures.append(f"{name} exec failed: {exc}")
            continue
        if result.returncode != 0:
            failures.append(f"{name} returned {result.returncode}")
            continue
        if "ok" not in result.stdout.lower():
            _warn(warnings, "tool.powershell_output", f"{name} output unexpected")
        return
    if warn_only:
        for failure in failures:
            _warn(warnings, "tool.powershell_exec_failed", failure)
    else:
        for failure in failures:
            _error(errors, "tool.powershell_exec_failed", failure)


def _check_temp_dir(
    temp_dir: str | None,
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
) -> None:
    if not temp_dir:
        _error(errors, "env.temp_missing", "TEMP/TMP is not set")
        return
    temp_path = Path(temp_dir)
    _cmd_unsafe_issue("TEMP/TMP", temp_dir, errors, warnings, cmd_unsafe_error, False)
    if _contains_non_ascii(temp_dir):
        _warn(
            warnings,
            "env.temp_non_ascii",
            f"TEMP/TMP contains non-ASCII characters: {temp_dir}",
        )
    try:
        temp_path.mkdir(parents=True, exist_ok=True)
        test_path = temp_path / "marsdisk_preflight_tmp.txt"
        test_path.write_text("ok", encoding="ascii")
        test_path.unlink()
    except Exception as exc:
        _error(errors, "env.temp_not_writable", f"TEMP/TMP not writable: {exc}")


def _check_env_paths(
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
) -> None:
    for key in PATH_ENV_VARS:
        value = os.environ.get(key, "")
        if not value:
            continue
        _cmd_unsafe_issue(key, value, errors, warnings, cmd_unsafe_error, False)
        if _contains_non_ascii(value):
            _warn(warnings, "env.var_non_ascii", f"{key} contains non-ASCII characters: {value}")
        if key == "COMSPEC":
            lower_value = value.lower()
            if "%" not in value:
                if not Path(value).exists():
                    _error(errors, "env.comspec_missing", f"COMSPEC not found: {value}")
                elif not lower_value.endswith("cmd.exe"):
                    _warn(
                        warnings,
                        "env.comspec.not_cmd",
                        f"COMSPEC does not point to cmd.exe: {value}",
                    )
            elif "cmd.exe" not in lower_value:
                _warn(
                    warnings,
                    "env.comspec.not_cmd",
                    f"COMSPEC does not point to cmd.exe: {value}",
                )
        if len(value) >= MAX_WARN_PATH_LEN:
            _warn(
                warnings,
                "env.var_length",
                f"{key} path length >= {MAX_WARN_PATH_LEN}: {value}",
            )


def _check_path_env_length(warnings: list[Issue]) -> None:
    value = os.environ.get("PATH", "")
    if not value:
        return
    length = len(value)
    if length >= CMD_LINE_MAX:
        _warn(
            warnings,
            "env.path_too_long",
            f"PATH length {length} >= {CMD_LINE_MAX} (cmd limit)",
        )
    elif length >= PATH_WARN_LEN:
        _warn(
            warnings,
            "env.path_near_limit",
            f"PATH length {length} near cmd limit {CMD_LINE_MAX}",
        )


def _check_pathext(
    errors: list[Issue],
    warnings: list[Issue],
    profile: str,
) -> None:
    value = os.environ.get("PATHEXT", "")
    if not value:
        msg = "PATHEXT is not set"
        if profile == "ci":
            _error(errors, "env.pathext.missing_or_suspicious", msg)
        else:
            _warn(warnings, "env.pathext.missing_or_suspicious", msg)
        return
    parts = [item.strip().upper() for item in value.split(";") if item.strip()]
    missing = PATHEXT_REQUIRED.difference(parts)
    if missing:
        msg = f"PATHEXT missing required entries: {sorted(missing)}"
        if profile == "ci":
            _error(errors, "env.pathext.missing_or_suspicious", msg)
        else:
            _warn(warnings, "env.pathext.missing_or_suspicious", msg)


def _check_path_value(
    label: str,
    value: str,
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
    allow_expansion: bool,
    warn_unc: bool = True,
    meta_as_error: bool = False,
    skip_rules: set[str] | None = None,
) -> None:
    if not value:
        return
    has_expansion = allow_expansion and _has_expansion_token(value)
    _cmd_unsafe_issue(
        label,
        value,
        errors,
        warnings,
        cmd_unsafe_error,
        allow_expansion,
        meta_as_error,
        skip_rules,
    )
    if _contains_non_ascii(value):
        if not skip_rules or ("*" not in skip_rules and "path.value_non_ascii" not in skip_rules):
            _warn(
                warnings,
                "path.value_non_ascii",
                f"{label} contains non-ASCII characters: {value}",
            )
    if len(value) >= MAX_WARN_PATH_LEN:
        if not skip_rules or ("*" not in skip_rules and "path.value_length" not in skip_rules):
            _warn(
                warnings,
                "path.value_length",
                f"{label} path length >= {MAX_WARN_PATH_LEN}: {value}",
            )
    if not has_expansion:
        if _has_invalid_windows_chars(value):
            if not skip_rules or ("*" not in skip_rules and "path.invalid_chars" not in skip_rules):
                _error(
                    errors,
                    "path.invalid_chars",
                    f"{label} contains invalid Windows path chars: {value}",
                )
        if value.endswith((" ", ".")):
            if not skip_rules or ("*" not in skip_rules and "path.trailing_space_dot" not in skip_rules):
                _warn(
                    warnings,
                    "path.trailing_space_dot",
                    f"{label} ends with space/dot: {value}",
                )
        if warn_unc and value.startswith("\\\\") and label != "io.archive.dir":
            if not skip_rules or ("*" not in skip_rules and "path.unc" not in skip_rules):
                _warn(warnings, "path.unc", f"{label} is a UNC path: {value}")
        if _looks_like_windows_path(value) and _has_reserved_windows_name(value):
            if not skip_rules or ("*" not in skip_rules and "path.reserved_device" not in skip_rules):
                _error(
                    errors,
                    "path.reserved_device",
                    f"{label} contains reserved device name: {value}",
                )


def _has_invalid_windows_chars(value: str) -> bool:
    has_extended = value.startswith("\\\\?\\")
    has_device = value.startswith("\\\\.\\")
    for idx, ch in enumerate(value):
        if ch not in WINDOWS_PATH_INVALID_CHARS:
            continue
        if ch == ":":
            if idx == 1 and len(value) >= 2 and value[0].isalpha():
                continue
            if has_extended or has_device:
                if idx == 5 and len(value) > 5 and value[4].isalpha():
                    continue
            return True
        if ch == "?" and has_extended and idx == 2:
            continue
        return True
    return False


def _extract_for_var_token(line_body: str) -> str | None:
    if not FOR_CMD_RE.match(line_body):
        return None
    tokens = line_body.split()
    in_index = None
    for idx, token in enumerate(tokens):
        if idx == 0:
            continue
        if token.lower() == "in":
            in_index = idx
            break
    if in_index is None:
        return None
    for token in tokens[1:in_index]:
        if FOR_VAR_RE.match(token):
            return token
    return None


def _parse_set_value(line: str) -> str | None:
    rest = line[3:].lstrip()
    if not rest:
        return None
    if rest.startswith('"') and rest.endswith('"') and "=" in rest:
        content = rest.strip('"')
        _, value = content.split("=", 1)
        return value
    if "=" in rest:
        _, value = rest.split("=", 1)
        return value.strip()
    return None


def _detect_delayed_expansion_lines(text: str) -> list[int]:
    lines: list[int] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lstrip()
        if lowered.startswith("@"):
            lowered = lowered[1:].lstrip()
        lower = lowered.lower()
        if lower.startswith("rem") and (len(lower) == 3 or lower[3].isspace()):
            continue
        if lower.startswith("::"):
            continue
        if DELAYED_SETLOCAL_RE.search(lowered) or DELAYED_CMD_RE.search(lowered):
            lines.append(line_no)
    return lines


def _detect_delayed_expansion(text: str) -> bool:
    return bool(_detect_delayed_expansion_lines(text))


def _decode_cmd_text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    return data.decode("utf-8", errors="replace")


def _read_cmd_text(path: Path, errors: list[Issue]) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        _error(errors, "cmd.read_failed", f"cmd read failed: {path} ({exc})")
        return None
    return _decode_cmd_text(data)


def _normalize_allowlist_path(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def _load_cmd_allowlist(path: Path) -> list[AllowlistEntry]:
    entries: list[AllowlistEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if not line:
            continue
        rules: set[str] | None = None
        path_part = line
        if "::" in line:
            path_part, rule_part = line.split("::", 1)
            rule_part = rule_part.strip()
            if rule_part:
                rules = {item.strip() for item in rule_part.split(",") if item.strip()}
            else:
                rules = None
        entries.append(
            AllowlistEntry(
                path=_normalize_allowlist_path(path_part),
                rules=rules,
            )
        )
    return entries


def _allowlist_rules_for(
    path: Path,
    repo_root: Path,
    entries: list[AllowlistEntry],
) -> set[str] | None:
    if not entries:
        return None
    candidates: list[str] = []
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        candidates.append(rel.as_posix())
    except Exception:
        pass
    candidates.append(path.as_posix())
    candidates.append(str(path))
    normalized = {_normalize_allowlist_path(item) for item in candidates if item}
    matched_rules: set[str] = set()
    for entry in entries:
        if any(fnmatch.fnmatch(candidate, entry.path) for candidate in normalized):
            if entry.rules is None:
                return {"*"}
            matched_rules.update(entry.rules)
    return matched_rules or None


def _format_issue(issue: Issue) -> str:
    if issue.path and issue.path not in issue.message:
        location = issue.path
        if issue.line is not None:
            location = f"{issue.path}:{issue.line}"
        return f"{issue.message} ({location})"
    return issue.message


def _issue_to_dict(issue: Issue) -> dict[str, object]:
    payload: dict[str, object] = {
        "level": issue.level,
        "rule": issue.rule,
        "message": issue.message,
    }
    if issue.path is not None:
        payload["path"] = issue.path
    if issue.line is not None:
        payload["line"] = issue.line
    return payload


def _rule_counts(issues: list[Issue]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for issue in issues:
        bucket = counts.setdefault(issue.rule, {"error": 0, "warn": 0, "info": 0})
        bucket[issue.level] += 1
    return counts


def _build_json_payload(
    errors: list[Issue],
    warnings: list[Issue],
    infos: list[Issue],
    exit_code: int,
) -> dict[str, object]:
    all_issues = errors + warnings + infos
    if exit_code == 1:
        status = "failed"
    elif exit_code == 2:
        status = "warn"
    else:
        status = "ok"
    return {
        "status": status,
        "exit_code": exit_code,
        "counts": {
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
        },
        "rule_counts": _rule_counts(all_issues),
        "issues": {
            "errors": [_issue_to_dict(issue) for issue in errors],
            "warnings": [_issue_to_dict(issue) for issue in warnings],
            "infos": [_issue_to_dict(issue) for issue in infos],
        },
    }


def _has_chcp_directive(lines: list[str], limit: int = CHCP_SCAN_LINES) -> bool:
    checked = 0
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        line_body = stripped.lstrip()
        if line_body.startswith("@"):
            line_body = line_body[1:].lstrip()
        lower = line_body.lower()
        if lower.startswith("rem") and (len(lower) == 3 or lower[3].isspace()):
            continue
        if lower.startswith("::"):
            continue
        checked += 1
        if CHCP_CMD_RE.match(line_body):
            return True
        if checked >= limit:
            return False
    return False


def _scan_cmd_file(
    path: Path,
    errors: list[Issue],
    warnings: list[Issue],
    infos: list[Issue],
    cmd_unsafe_error: bool,
    profile: str,
    allowlist_rules: set[str] | None,
) -> None:
    def should_skip(rule: str) -> bool:
        if not allowlist_rules:
            return False
        return "*" in allowlist_rules or rule in allowlist_rules

    def report_error(rule: str, message: str, line_no: int | None = None) -> None:
        if should_skip(rule):
            return
        _error(errors, rule, message, path=path, line=line_no)

    def report_warn(rule: str, message: str, line_no: int | None = None) -> None:
        if should_skip(rule):
            return
        _warn(warnings, rule, message, path=path, line=line_no)

    def report_info(rule: str, message: str, line_no: int | None = None) -> None:
        if should_skip(rule):
            return
        _info(infos, rule, message, path=path, line=line_no)

    try:
        data = path.read_bytes()
    except OSError as exc:
        report_error("cmd.read_failed", f"cmd read failed: {path} ({exc})")
        return

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        report_error(
            "cmd.encoding.utf16",
            "cmd appears to be UTF-16 encoded; save as UTF-8 without BOM",
        )
        return
    sample = data[:4096]
    if sample:
        nul_count = sample.count(b"\x00")
        if nul_count / len(sample) >= 0.1:
            if profile == "ci":
                report_error(
                    "cmd.encoding.nul",
                    "cmd contains many NUL bytes (possible UTF-16/UTF-32 encoding)",
                )
                return
            report_warn(
                "cmd.encoding.nul",
                "cmd contains many NUL bytes (possible UTF-16/UTF-32 encoding)",
            )

    if data.startswith(b"\xef\xbb\xbf"):
        if profile == "ci":
            report_error("cmd.encoding.bom", "cmd has UTF-8 BOM")
        else:
            report_warn("cmd.encoding.bom", "cmd has UTF-8 BOM")

    has_crlf = b"\r\n" in data
    has_lf = b"\n" in data
    if has_lf and not has_crlf:
        report_warn("cmd.line_endings.lf_only", "cmd uses LF-only line endings")
    if has_crlf:
        if b"\n" in data.replace(b"\r\n", b""):
            report_warn("cmd.line_endings.mixed", "cmd has mixed line endings")

    has_non_ascii = any(byte >= 0x80 for byte in data)
    if has_non_ascii:
        report_warn("cmd.encoding.non_ascii", "cmd contains non-ASCII characters")

    text = _decode_cmd_text(data)
    lines = text.splitlines()
    if has_non_ascii and not _has_chcp_directive(lines):
        report_warn("cmd.encoding.no_chcp", "cmd contains non-ASCII without chcp near top")

    delayed_lines = _detect_delayed_expansion_lines(text)
    for line_no in delayed_lines:
        report_info(
            "cmd.delayed_expansion.enabled",
            "cmd enables delayed expansion",
            line_no,
        )
    delayed_now = False
    extensions_disabled = False
    delayed_stack: list[bool] = []
    extensions_stack: list[bool] = []
    extensions_cmd_off_reported = False
    bang_missing_reported = False
    has_setlocal = False
    setlocal_count = 0
    endlocal_count = 0
    first_setlocal_line: int | None = None
    first_endlocal_line: int | None = None
    env_modified = False
    env_modified_line: int | None = None
    pushd_count = 0
    popd_count = 0
    first_pushd_line: int | None = None
    first_popd_line: int | None = None
    last_errorlevel_value: int | None = None
    last_errorlevel_plain = False

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        line_body = stripped.lstrip()
        if line_body.startswith("@"):
            line_body = line_body[1:].lstrip()
        lower = line_body.lower()
        if lower.startswith("rem") and (len(lower) == 3 or lower[3].isspace()):
            continue
        if lower.startswith("::"):
            continue
        if SETLOCAL_RE.match(line_body):
            has_setlocal = True
            setlocal_count += 1
            if first_setlocal_line is None:
                first_setlocal_line = line_no
            delayed_stack.append(delayed_now)
            extensions_stack.append(extensions_disabled)
            if DELAYED_SETLOCAL_RE.search(line_body):
                delayed_now = True
            if DELAYED_SETLOCAL_OFF_RE.search(line_body):
                delayed_now = False
            if DISABLE_EXT_RE.search(line_body):
                if not extensions_disabled:
                    report_warn(
                        "cmd.extensions.disabled_in_script",
                        "cmd disables command extensions (setlocal disableextensions / cmd /e:off)",
                        line_no,
                    )
                extensions_disabled = True
            if ENABLE_EXT_RE.search(line_body):
                extensions_disabled = False
        if ENDLOCAL_RE.match(line_body):
            endlocal_count += 1
            if first_endlocal_line is None:
                first_endlocal_line = line_no
            if delayed_stack:
                delayed_now = delayed_stack.pop()
            if extensions_stack:
                extensions_disabled = extensions_stack.pop()
        if DELAYED_CMD_RE.search(line_body):
            delayed_now = True
        if DELAYED_CMD_OFF_RE.search(line_body):
            delayed_now = False
        for_var = _extract_for_var_token(line_body)
        if for_var and not for_var.startswith("%%"):
            report_error(
                "cmd.for.single_percent",
                "cmd for uses single % variable (use %% in .cmd)",
                line_no,
            )
        if PUSHD_RE.match(line_body):
            pushd_count += 1
            if first_pushd_line is None:
                first_pushd_line = line_no
            parts = line_body.split(None, 1)
            if len(parts) > 1:
                target = parts[1].strip()
                target = re.split(r"[&|]", target, 1)[0].strip()
                if target and not target.startswith('"') and " " in target:
                    report_warn(
                        "cmd.pushd.unquoted_space",
                        "cmd pushd path has unquoted spaces",
                        line_no,
                    )
        elif POPD_RE.match(line_body):
            popd_count += 1
            if first_popd_line is None:
                first_popd_line = line_no
        errorlevel_match = ERRORLEVEL_RE.match(line_body)
        if errorlevel_match:
            is_plain = errorlevel_match.group(1) is None
            value = int(errorlevel_match.group(2))
            if value == 0:
                report_warn(
                    "cmd.errorlevel.zero",
                    "cmd uses 'if errorlevel 0' (errorlevel is >= comparison)",
                    line_no,
                )
            if (
                is_plain
                and last_errorlevel_plain
                and last_errorlevel_value is not None
                and value > last_errorlevel_value
            ):
                report_warn(
                    "cmd.errorlevel.ascending",
                    "cmd uses ascending if errorlevel checks (should be descending)",
                    line_no,
                )
            last_errorlevel_value = value
            last_errorlevel_plain = is_plain
        else:
            last_errorlevel_value = None
            last_errorlevel_plain = False
        if len(line) >= CMD_LINE_MAX:
            report_error(
                "cmd.line_length.limit",
                f"cmd line length {len(line)} >= {CMD_LINE_MAX}",
                line_no,
            )
        elif len(line) >= CMD_LINE_WARN_LEN:
            report_warn(
                "cmd.line_length.near",
                f"cmd line length {len(line)} near cmd limit {CMD_LINE_MAX}",
                line_no,
            )
        if _contains_posix_path(line_body):
            report_error("cmd.posix_path", "cmd contains POSIX-style path", line_no)
            continue
        if DISABLE_EXT_CMD_RE.search(line_body) and not extensions_cmd_off_reported:
            extensions_cmd_off_reported = True
            report_warn(
                "cmd.extensions.disabled_in_script",
                "cmd disables command extensions (setlocal disableextensions / cmd /e:off)",
                line_no,
            )
        if (
            BANG_TOKEN_RE.search(line_body)
            and not delayed_now
            and not bang_missing_reported
            and not DELAYED_CMD_RE.search(line_body)
        ):
            bang_missing_reported = True
            report_warn(
                "cmd.delayed_expansion.before_enabled",
                "cmd uses !VAR! before enabling delayed expansion",
                line_no,
            )
        if lower.startswith(("cd ", "cd\t", "chdir ")):
            if re.search(r"[A-Za-z]:[\\/]", line_body) and not re.search(r"\s+/d\b", lower):
                report_warn(
                    "cmd.cd.missing_d",
                    "cmd cd without /d for drive path",
                    line_no,
                )
            if "\\\\" in line_body:
                report_warn(
                    "cmd.cd.unc",
                    "cmd cd uses UNC path; prefer pushd",
                    line_no,
                )
            if "&" not in line_body and "|" not in line_body:
                cd_arg = re.sub(r"^(cd|chdir)\b", "", line_body, flags=re.I).strip()
                cd_arg = re.sub(r"^/d\b", "", cd_arg, flags=re.I).strip()
                if cd_arg and " " in cd_arg and not (cd_arg.startswith('"') and cd_arg.endswith('"')):
                    if extensions_disabled:
                        report_error(
                            "cmd.cd.unquoted_space",
                            "cmd cd path has unquoted spaces (extensions disabled)",
                            line_no,
                        )
                    else:
                        report_warn(
                            "cmd.cd.unquoted_space",
                            "cmd cd path has unquoted spaces",
                            line_no,
                        )
        if START_QUOTED_RE.match(line_body):
            report_warn(
                "cmd.start.quoted_title",
                'cmd start uses quoted arg without empty title (use start "" ...)',
                line_no,
            )
        if START_CMD_RE.match(line_body) and profile == "ci":
            if "/wait" not in lower:
                report_warn(
                    "cmd.start.no_wait",
                    "cmd start without /wait in CI",
                    line_no,
                )
        if EXEC_CMD_RE.match(line_body):
            if not lower.startswith("call ") and not lower.startswith("start "):
                report_warn("cmd.call.missing", "cmd invokes batch without call", line_no)
        if lower.startswith("call "):
            rest = line_body[4:].lstrip()
            if rest and not rest.startswith(":"):
                segment = re.split(r"[&|]", rest, 1)[0].strip()
                if segment and not segment.startswith('"'):
                    parts = segment.split()
                    if parts:
                        first = parts[0].lower()
                        if not first.endswith((".cmd", ".bat")):
                            if re.search(r"\.c(md|bat)\b", segment, re.I):
                                report_warn(
                                    "cmd.call.unquoted_space",
                                    "cmd call path has unquoted spaces",
                                    line_no,
                                )
        if EXIT_CMD_RE.match(line_body) and not EXIT_B_RE.search(line_body):
            report_warn("cmd.exit.missing_b", "cmd exit without /b", line_no)
        if SET_INTERACTIVE_RE.search(line_body):
            if profile == "ci":
                report_error("cmd.interactive.set_p", "cmd uses set /p (interactive)", line_no)
            else:
                report_warn("cmd.interactive.set_p", "cmd uses set /p (interactive)", line_no)
        if PAUSE_RE.match(line_body):
            if profile == "ci":
                report_error("cmd.interactive.pause", "cmd uses pause (interactive)", line_no)
            else:
                report_warn("cmd.interactive.pause", "cmd uses pause (interactive)", line_no)
        if CHOICE_RE.match(line_body):
            if profile == "ci":
                report_error("cmd.interactive.choice", "cmd uses choice (interactive)", line_no)
            else:
                report_warn("cmd.interactive.choice", "cmd uses choice (interactive)", line_no)
        if line.rstrip().endswith("^") and not line.endswith("^"):
            report_warn(
                "cmd.caret.trailing_space",
                "cmd line continuation caret has trailing whitespace",
                line_no,
            )
        for match in CMD_C_QUOTED_RE.finditer(line_body):
            inner = match.group(1)
            if any(ch in inner for ch in CMD_QUOTED_META_CHARS):
                report_warn(
                    "cmd.cmd_c.quote_meta",
                    "cmd /c quoted string contains meta characters; quoting rules may change parsing",
                    line_no,
                )
                break
        if lower.startswith("path "):
            if not env_modified:
                env_modified = True
                env_modified_line = line_no
        if SETX_RE.match(line_body):
            if not env_modified:
                env_modified = True
                env_modified_line = line_no
            if profile == "ci":
                report_error(
                    "cmd.env.setx",
                    "cmd uses setx (persistent environment change)",
                    line_no,
                )
            else:
                report_warn(
                    "cmd.env.setx",
                    "cmd uses setx (persistent environment change)",
                    line_no,
                )
        if lower.startswith("set "):
            rest = line_body[3:].lstrip()
            rest_lower = rest.lower()
            is_set_p = rest_lower.startswith("/p")
            is_set_a = rest_lower.startswith("/a")
            if is_set_p or is_set_a or "=" in rest:
                if not env_modified:
                    env_modified = True
                    env_modified_line = line_no
            rest_stripped = rest.strip()
            inner = rest_stripped
            if rest_stripped.startswith('"') and rest_stripped.endswith('"'):
                inner = rest_stripped[1:-1]
            if not is_set_p and not is_set_a and "=" in inner:
                eq_index = inner.find("=")
                before = inner[eq_index - 1] if eq_index > 0 else ""
                after = inner[eq_index + 1] if eq_index + 1 < len(inner) else ""
                if (before and before.isspace()) or (after and after.isspace()):
                    if profile == "ci":
                        report_error(
                            "cmd.set.space_around_equals",
                            "cmd set has spaces around '='",
                            line_no,
                        )
                    else:
                        report_warn(
                            "cmd.set.space_around_equals",
                            "cmd set has spaces around '='",
                            line_no,
                        )
            if is_set_p or is_set_a:
                continue
            value = _parse_set_value(line_body)
            if not value:
                continue
            if _contains_posix_path(value):
                report_error("cmd.set.posix_path", "cmd set uses POSIX path", line_no)
            if ("\\" in value or "/" in value) and not _contains_posix_path(value):
                _check_path_value(
                    f"{path}:{line_no}",
                    value,
                    errors,
                    warnings,
                    cmd_unsafe_error,
                    True,
                    meta_as_error=extensions_disabled,
                    skip_rules=allowlist_rules,
                )
    if env_modified and not has_setlocal:
        report_warn(
            "cmd.setlocal.missing",
            "cmd modifies environment without setlocal",
            env_modified_line,
        )
    if first_endlocal_line is not None and (
        first_setlocal_line is None or first_endlocal_line < first_setlocal_line
    ):
        report_warn(
            "cmd.setlocal.order",
            "cmd uses endlocal before setlocal",
            first_endlocal_line,
        )
    if endlocal_count > setlocal_count:
        report_warn(
            "cmd.setlocal.unbalanced",
            "cmd uses endlocal without matching setlocal",
            first_endlocal_line,
        )
    if popd_count > pushd_count:
        report_warn(
            "cmd.pushd_popd.unbalanced",
            "cmd uses more popd than pushd",
            first_popd_line,
        )
    elif pushd_count > popd_count:
        report_warn(
            "cmd.pushd_popd.unbalanced",
            "cmd uses pushd without matching popd",
            first_pushd_line,
        )


def _collect_cmd_paths(
    cmd_files: list[str],
    cmd_roots: list[str],
    errors: list[Issue],
    cmd_exclude: list[str],
) -> list[Path]:
    exclude_paths: list[Path] = []
    for raw in cmd_exclude:
        if not raw:
            continue
        exclude_paths.append(Path(raw).resolve(strict=False))

    def is_excluded(path: Path) -> bool:
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            resolved = path
        for ex in exclude_paths:
            if resolved == ex:
                return True
            try:
                if resolved.is_relative_to(ex):
                    return True
            except AttributeError:
                if str(resolved).startswith(str(ex)):
                    return True
        return False

    paths: list[Path] = []
    for cmd in cmd_files:
        cmd_path = Path(cmd)
        if not cmd_path.exists():
            _error(errors, "cmd.file_missing", f"cmd missing: {cmd_path}")
            continue
        if not is_excluded(cmd_path):
            paths.append(cmd_path)
    for root in cmd_roots:
        root_path = Path(root)
        if not root_path.exists():
            _error(errors, "cmd.root_missing", f"cmd root missing: {root_path}")
            continue
        for cmd_path in sorted(root_path.rglob("*")):
            if not cmd_path.is_file():
                continue
            if cmd_path.suffix.lower() not in {".cmd", ".bat"}:
                continue
            if not is_excluded(cmd_path):
                paths.append(cmd_path)
    return sorted(set(paths))


def _scan_repo_root(
    root: Path,
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
    exclude_dirs: set[str],
) -> tuple[str, int]:
    max_rel_path = ""
    max_rel_len = 0
    seen_casefold: dict[str, str] = {}
    exclude_lower = {name.lower() for name in exclude_dirs}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            [d for d in dirnames if d.lower() not in exclude_lower],
            key=str.lower,
        )
        filenames = sorted(filenames, key=str.lower)
        base_dir = Path(dirpath)
        rel_dir = base_dir.relative_to(root)
        for name in list(dirnames) + list(filenames):
            rel_path = rel_dir / name if rel_dir.parts else Path(name)
            rel_display = str(PureWindowsPath(*rel_path.parts))
            _check_name_component(name, rel_display, errors)
            _cmd_unsafe_issue(
                f"path {rel_display}",
                rel_display,
                errors,
                warnings,
                cmd_unsafe_error,
                False,
            )
            if _contains_non_ascii(name):
                _warn(warnings, "repo.name_non_ascii", f"non-ASCII name: {rel_display}")
            rel_key = rel_display.casefold()
            if rel_key in seen_casefold and seen_casefold[rel_key] != rel_display:
                _error(
                    errors,
                    "repo.case_conflict",
                    f"case-insensitive conflict: {seen_casefold[rel_key]} vs {rel_display}"
                )
            else:
                seen_casefold[rel_key] = rel_display
            rel_len = len(rel_display)
            if rel_len > max_rel_len:
                max_rel_len = rel_len
                max_rel_path = rel_display
    return max_rel_path, max_rel_len


def _estimate_path_len(base: str, rel_win: str) -> int:
    rel = PureWindowsPath(rel_win)
    base_path = PureWindowsPath(base)
    return len(str(base_path / rel))


def _read_long_paths_enabled() -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except Exception:
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\\CurrentControlSet\\Control\\FileSystem",
        )
        value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
    except OSError:
        return None
    return bool(value)


def _read_git_longpaths(repo_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.longpaths"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip().lower()
    if value in {"true", "1", "yes", "on"}:
        return True
    if value in {"false", "0", "no", "off"}:
        return False
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--overrides", required=True, type=Path)
    ap.add_argument("--out-root", default="", help="Output root (optional).")
    ap.add_argument(
        "--python-exe",
        default="",
        help="Python executable or command used by the caller (optional).",
    )
    ap.add_argument("--require-git", action="store_true")
    ap.add_argument("--require-powershell", action="store_true")
    ap.add_argument(
        "--check-tools",
        action="store_true",
        help="Enforce tool checks even when simulating on non-Windows hosts.",
    )
    ap.add_argument(
        "--simulate-windows",
        action="store_true",
        help="Run Windows-style checks even on non-Windows hosts.",
    )
    ap.add_argument(
        "--windows-root",
        default="",
        help="Expected Windows path for repo_root when simulating.",
    )
    ap.add_argument(
        "--cmd",
        action="append",
        default=[],
        help="CMD/BAT file to lint (repeatable).",
    )
    ap.add_argument(
        "--cmd-root",
        action="append",
        default=[],
        help="Directory to scan for .cmd/.bat files (repeatable).",
    )
    ap.add_argument(
        "--cmd-exclude",
        action="append",
        default=[],
        help="Path to exclude from cmd scan (repeatable).",
    )
    ap.add_argument(
        "--cmd-allowlist",
        type=Path,
        default=None,
        help="Allowlist file for cmd lint (optional).",
    )
    ap.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip host environment path checks.",
    )
    ap.add_argument(
        "--scan-repo",
        action="store_true",
        help="Scan repo_root for Windows-incompatible names.",
    )
    ap.add_argument(
        "--skip-repo-scan",
        action="store_true",
        help="Skip repo_root scan.",
    )
    ap.add_argument(
        "--scan-exclude",
        action="append",
        default=[],
        help="Directory name to exclude from repo scan (repeatable).",
    )
    ap.add_argument(
        "--profile",
        choices=("default", "ci"),
        default="default",
        help="Lint profile (ci treats interactive commands as errors).",
    )
    ap.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    args.repo_root = args.repo_root.resolve(strict=False)
    args.config = args.config.resolve(strict=False)
    args.overrides = args.overrides.resolve(strict=False)

    errors: list[Issue] = []
    warnings: list[Issue] = []
    infos: list[Issue] = []

    if sys.version_info < (3, 11):
        _warn(
            warnings,
            "runtime.python_version",
            f"python {sys.version.split()[0]} < 3.11",
        )
    is_windows_host = _is_windows()
    if not is_windows_host and not args.simulate_windows:
        _warn(
            warnings,
            "host.non_windows",
            "host is not Windows; cmd-specific checks may be incomplete",
        )

    cmd_paths = _collect_cmd_paths(args.cmd, args.cmd_root, errors, args.cmd_exclude)
    delayed_expansion_used = False
    for cmd_path in cmd_paths:
        text = _read_cmd_text(cmd_path, errors)
        if text and _detect_delayed_expansion(text):
            delayed_expansion_used = True
            break
    cmd_unsafe_error = True
    if cmd_paths:
        cmd_unsafe_error = delayed_expansion_used

    allowlist_entries: list[AllowlistEntry] = []
    if args.cmd_allowlist:
        if not args.cmd_allowlist.exists():
            _error(
                errors,
                "cmd.allowlist.missing",
                f"cmd allowlist missing: {args.cmd_allowlist}",
            )
        else:
            try:
                allowlist_entries = _load_cmd_allowlist(args.cmd_allowlist)
            except OSError as exc:
                _error(
                    errors,
                    "cmd.allowlist.read_failed",
                    f"cmd allowlist read failed: {args.cmd_allowlist} ({exc})",
                )

    for label, path in {
        "repo_root": args.repo_root,
        "config": args.config,
        "overrides": args.overrides,
    }.items():
        if not path.exists():
            _error(errors, "path.missing", f"{label} missing: {path}")
        _check_path_value(
            label,
            str(path),
            errors,
            warnings,
            cmd_unsafe_error,
            False,
            warn_unc=False,
        )
        _check_shared_path(label, str(path), warnings)

    if args.config.suffix.lower() not in {".yml", ".yaml"}:
        _warn(
            warnings,
            "config.extension",
            f"config extension is not .yml/.yaml: {args.config.name}",
        )

    if args.out_root:
        _check_path_value(
            "out_root",
            args.out_root,
            errors,
            warnings,
            cmd_unsafe_error,
            False,
            warn_unc=False,
        )
        _check_shared_path("out_root", args.out_root, warnings)
        if not _is_windows_abs(args.out_root):
            _warn(warnings, "path.not_absolute", f"out_root is not absolute: {args.out_root}")

    if args.windows_root:
        _check_path_value(
            "windows_root",
            args.windows_root,
            errors,
            warnings,
            cmd_unsafe_error,
            False,
            warn_unc=False,
        )
        _check_shared_path("windows_root", args.windows_root, warnings)
        if not _is_windows_abs(args.windows_root):
            _warn(
                warnings,
                "path.not_absolute",
                f"windows_root is not absolute: {args.windows_root}",
            )

    tool_checks_warn_only = args.simulate_windows and not is_windows_host and not args.check_tools
    if tool_checks_warn_only:
        _warn(
            warnings,
            "tools.downgraded",
            "tool checks downgraded to warnings on non-Windows (simulate-windows)",
        )

    if args.require_git:
        _check_cmd("git", errors, warnings, tool_checks_warn_only)
    _check_python(errors, warnings, tool_checks_warn_only, args.python_exe or None)
    if args.require_powershell:
        _check_powershell(errors, warnings, tool_checks_warn_only)

    if is_windows_host:
        autorun_values = _read_cmd_autorun_values()
        for label, value in autorun_values.items():
            _warn(
                warnings,
                "cmd.autorun",
                f"cmd AutoRun is set in {label}: {value}; use cmd /d to disable",
            )
        enabled, source, raw = _read_cmd_extensions_enabled()
        if enabled is False:
            _error(
                errors,
                "cmd.extensions.disabled",
                f"cmd extensions disabled (EnableExtensions={raw} from {source})",
            )
        code_page = _read_cmd_code_page()
        if code_page:
            _info(infos, "cmd.code_page", f"cmd code page: {code_page}")

    overrides = {}
    if args.overrides.exists():
        overrides, duplicates = _load_overrides(args.overrides)
        for key in duplicates:
            _warn(warnings, "overrides.duplicate_key", f"overrides duplicated key: {key}")
        for key, expected in REQUIRED_ARCHIVE_KEYS.items():
            if key not in overrides:
                _error(errors, "overrides.missing_key", f"overrides missing: {key}")
                continue
            if expected is not None and overrides[key].lower() != expected:
                _error(
                    errors,
                    "overrides.value_mismatch",
                    f"overrides {key}={overrides[key]} (expected {expected})",
                )
        for key, value in overrides.items():
            _cmd_unsafe_issue(
                f"overrides value {key}",
                value,
                errors,
                warnings,
                cmd_unsafe_error,
                False,
            )
            if _contains_non_ascii(value):
                _warn(
                    warnings,
                    "overrides.value_non_ascii",
                    f"overrides value contains non-ASCII chars: {key}={value}",
                )

        archive_dir = overrides.get("io.archive.dir", "")
        if archive_dir:
            _check_path_value(
                "io.archive.dir",
                archive_dir,
                errors,
                warnings,
                cmd_unsafe_error,
                False,
                warn_unc=False,
            )
            _check_shared_path("io.archive.dir", archive_dir, warnings)
            if not _is_windows_abs(archive_dir):
                _error(
                    errors,
                    "archive.dir.not_absolute",
                    f"io.archive.dir not absolute: {archive_dir}",
                )
            if args.out_root:
                if _normalize_windows(args.out_root) == _normalize_windows(archive_dir):
                    _error(
                        errors,
                        "archive.dir.matches_out_root",
                        "out-root matches io.archive.dir (must be internal)",
                    )
            if is_windows_host:
                drive = PureWindowsPath(archive_dir).drive
                if drive:
                    drive_root = Path(f"{drive}\\")
                    if not drive_root.exists():
                        _error(
                            errors,
                            "archive.dir.drive_missing",
                            f"io.archive.dir drive missing: {drive}",
                        )
                else:
                    _error(
                        errors,
                        "archive.dir.no_drive",
                        f"io.archive.dir has no drive letter: {archive_dir}",
                    )
            else:
                if args.simulate_windows:
                    _info(
                        infos,
                        "archive.dir.drive_unchecked",
                        "non-Windows host; drive availability not checked",
                    )
                else:
                    _warn(
                        warnings,
                        "archive.dir.drive_unchecked",
                        "non-Windows host; drive availability not checked",
                    )

    skip_env = args.skip_env
    if args.simulate_windows and not is_windows_host:
        skip_env = True
        if not args.skip_env:
            _info(
                infos,
                "host.env_checks_skipped",
                "host env checks skipped on non-Windows (simulate-windows)",
            )
    if not skip_env:
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
        _check_temp_dir(temp_dir, errors, warnings, cmd_unsafe_error)
        _check_env_paths(errors, warnings, cmd_unsafe_error)
        if is_windows_host:
            _check_path_env_length(warnings)
            _check_pathext(errors, warnings, args.profile)

    if cmd_paths:
        for cmd_path in cmd_paths:
            allowlist_rules = _allowlist_rules_for(cmd_path, args.repo_root, allowlist_entries)
            if allowlist_rules and "*" in allowlist_rules:
                continue
            _scan_cmd_file(
                cmd_path,
                errors,
                warnings,
                infos,
                cmd_unsafe_error,
                args.profile,
                allowlist_rules,
            )

    scan_repo = args.scan_repo or (args.simulate_windows and not args.skip_repo_scan)
    if args.skip_repo_scan:
        scan_repo = False
    max_rel_path = ""
    max_rel_len = 0
    if scan_repo and args.repo_root.exists():
        exclude_dirs = set(DEFAULT_SCAN_EXCLUDE_DIRS)
        exclude_dirs.update(args.scan_exclude)
        max_rel_path, max_rel_len = _scan_repo_root(
            args.repo_root,
            errors,
            warnings,
            cmd_unsafe_error,
            exclude_dirs,
        )

    if max_rel_path:
        long_paths_enabled = _read_long_paths_enabled()
        git_longpaths = _read_git_longpaths(args.repo_root) if args.require_git else None
        max_est_len = 0
        longest_note = f" (longest relative path: {max_rel_path})"

        repo_base = args.windows_root or str(args.repo_root)
        if args.windows_root or _looks_like_windows_path(str(args.repo_root)):
            est_len = _estimate_path_len(repo_base, max_rel_path)
            max_est_len = max(max_est_len, est_len)
            if not _is_windows_abs(repo_base):
                _warn(
                    warnings,
                    "path.not_absolute",
                    f"repo_root path is not absolute: {repo_base}",
                )
            if est_len >= MAX_PATH_CLASSIC:
                if long_paths_enabled is False:
                    _error(
                        errors,
                        "path.length.exceeds",
                        f"repo_root path length estimate {est_len} >= {MAX_PATH_CLASSIC} (long paths disabled){longest_note}",
                    )
                else:
                    _warn(
                        warnings,
                        "path.length.exceeds",
                        f"repo_root path length estimate {est_len} >= {MAX_PATH_CLASSIC}{longest_note}",
                    )
            elif est_len >= MAX_PATH_CLASSIC - 20:
                _warn(
                    warnings,
                    "path.length.near",
                    f"repo_root path length estimate {est_len} near {MAX_PATH_CLASSIC}{longest_note}",
                )
        else:
            _warn(
                warnings,
                "path.not_windows_like",
                "repo_root not Windows-like; provide --windows-root for length estimate",
            )

        for label, base in {
            "out_root": args.out_root,
            "io.archive.dir": overrides.get("io.archive.dir", ""),
        }.items():
            if not base:
                continue
            if _contains_posix_path(base):
                _warn(warnings, "path.posix_like", f"{label} looks like POSIX path: {base}")
            est_len = _estimate_path_len(base, max_rel_path)
            max_est_len = max(max_est_len, est_len)
            if not _is_windows_abs(base):
                _warn(warnings, "path.not_absolute", f"{label} path is not absolute: {base}")
            if est_len >= MAX_PATH_CLASSIC:
                if long_paths_enabled is False:
                    _error(
                        errors,
                        "path.length.exceeds",
                        f"{label} path length estimate {est_len} >= {MAX_PATH_CLASSIC} (long paths disabled){longest_note}",
                    )
                else:
                    _warn(
                        warnings,
                        "path.length.exceeds",
                        f"{label} path length estimate {est_len} >= {MAX_PATH_CLASSIC}{longest_note}",
                    )
            elif est_len >= MAX_PATH_CLASSIC - 20:
                _warn(
                    warnings,
                    "path.length.near",
                    f"{label} path length estimate {est_len} near {MAX_PATH_CLASSIC}{longest_note}",
                )
        if max_est_len >= MAX_PATH_CLASSIC - 20:
            if long_paths_enabled is False:
                _warn(
                    warnings,
                    "path.long_paths_disabled",
                    "Windows long paths disabled (LongPathsEnabled=0)",
                )
            elif long_paths_enabled is None and is_windows_host:
                _warn(warnings, "path.long_paths_unknown", "Windows long path setting unknown")
            if git_longpaths is False:
                _warn(warnings, "git.longpaths_disabled", "git core.longpaths is disabled")
            elif git_longpaths is None and args.require_git:
                _warn(warnings, "git.longpaths_unset", "git core.longpaths not set")

    exit_code = 0
    if errors:
        exit_code = 1
    elif warnings and args.strict:
        exit_code = 2

    if args.format == "json":
        payload = _build_json_payload(errors, warnings, infos, exit_code)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return exit_code

    status = "ok"
    if errors:
        status = "failed"
    elif warnings and args.strict:
        status = "warn"
    print(
        f"[preflight] {status} (errors={len(errors)}, warnings={len(warnings)}, infos={len(infos)})"
    )

    if errors:
        for issue in errors:
            print(f"[error] {_format_issue(issue)}")
        if warnings:
            for issue in warnings:
                print(f"[warn] {_format_issue(issue)}")
        if infos:
            for issue in infos:
                print(f"[info] {_format_issue(issue)}")
        return exit_code
    if warnings:
        for issue in warnings:
            print(f"[warn] {_format_issue(issue)}")
    if infos:
        for issue in infos:
            print(f"[info] {_format_issue(issue)}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
