#!/usr/bin/env python3
"""Preflight checks for Windows cmd runsets.

This tool performs static analysis of CMD/BAT files and validates
Windows-specific path and environment configurations before running
batch scripts.

Usage:
    python preflight_checks.py --repo-root . --config config.yml --overrides overrides.txt
    python preflight_checks.py --list-rules
    python preflight_checks.py --fix --cmd script.cmd
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

# Optional: YAML support for config file
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


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
CWD_SCAN_LINES = 30
DELAYED_SETLOCAL_RE = re.compile(r"\bsetlocal\b.*\benabledelayedexpansion\b", re.I)
DELAYED_SETLOCAL_OFF_RE = re.compile(r"\bsetlocal\b.*\bdisabledelayedexpansion\b", re.I)
DISABLE_EXT_RE = re.compile(r"\bsetlocal\b.*\bdisableextensions\b", re.I)
ENABLE_EXT_RE = re.compile(r"\bsetlocal\b.*\benableextensions\b", re.I)
DISABLE_EXT_CMD_RE = re.compile(r"\bcmd(?:\.exe)?\b.*?/e\s*:\s*off\b", re.I)
BANG_TOKEN_RE = re.compile(r"![^!]+!")
CHCP_CMD_RE = re.compile(r"^\s*@?(?:call\s+)?chcp\b", re.I)
EXEC_CMD_RE = re.compile(r'^\s*@?(?:"[^"]+"|[^"\s]+)\.(cmd|bat)\b', re.I)
START_QUOTED_RE = re.compile(r'^\s*@?start\s+"(?!")', re.I)
START_CMD_RE = re.compile(r"^\s*@?start\b", re.I)
CMD_C_QUOTED_RE = re.compile(r'\bcmd(?:\.exe)?\b\s+/c\s+"([^"]+)"', re.I)
CMD_SWITCH_C_RE = re.compile(r"(?:^|\s)/c(?:\s|$)", re.I)
CMD_SWITCH_K_RE = re.compile(r"(?:^|\s)/k(?:\s|$)", re.I)
CMD_SWITCH_V_ON_RE = re.compile(r"(?:^|\s)/v\s*:\s*on(?:\s|$)", re.I)
SCRIPT_DIR_RE = re.compile(r"%~dp0", re.I)
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
ERRORLEVEL_ANY_RE = re.compile(r"\bif\s+(not\s+)?errorlevel\s+(-?\d+)\b", re.I)
ERRORLEVEL_CMP_RE = re.compile(
    r"(?:%|!)errorlevel(?:%|!)\s+(geq|gtr|leq|lss)\s+(-?\d+)",
    re.I,
)
NUMERIC_COMPARISON_RE = re.compile(
    r"\bif\s+(?:not\s+)?(?:%[^%]+%|![^!]+!)\s+(equ|neq|lss|leq|gtr|geq)\s+",
    re.I,
)
PERCENT_ERRORLEVEL_RE = re.compile(r"%errorlevel%", re.I)
CMD_QUOTED_META_CHARS = "&<>|^()@"
CMD_ENV_VAR_RE = re.compile(r"%([^%]+)%")
VAR_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
PY_LAUNCHER_VERSION_RE = re.compile(r"^-\d+(?:\.\d+)*(?:-[0-9A-Za-z]+)?$")
PY_LAUNCHER_ALLOWED_ARGS = {"-V", "-h", "-?"}
PYTHON_PROBE_ERROR_RE = re.compile(
    r"(usage:|unknown option|unrecognized option|invalid option|unknown switch)",
    re.I,
)
DASH_OPTION_CMD_NAMES = {"where", "findstr"}
XCOPY_CMD_NAMES = {"xcopy", "xcopy.exe"}
ROBOCOPY_CMD_NAMES = {"robocopy", "robocopy.exe"}
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

CMD_ALLOWLIST_RULES = {
    "cmd.autorun.missing_d",
    "cmd.block.percent_errorlevel",
    "cmd.block.percent_var_after_set",
    "cmd.call.missing",
    "cmd.call.pipe_or_redirect",
    "cmd.call.unquoted_space",
    "cmd.caret.trailing_space",
    "cmd.cd.missing_d",
    "cmd.cd.unc",
    "cmd.cd.unquoted_space",
    "cmd.cmd_c.quote_meta",
    "cmd.delayed_expansion.before_enabled",
    "cmd.delayed_expansion.cmd_v_on",
    "cmd.delayed_expansion.enabled",
    "cmd.delayed_expansion.token",
    "cmd.cwd.relative_paths",
    "cmd.encoding.bom",
    "cmd.encoding.no_chcp",
    "cmd.encoding.non_ascii",
    "cmd.encoding.nul",
    "cmd.encoding.utf16",
    "cmd.env.setx",
    "cmd.errorlevel.ascending",
    "cmd.errorlevel.zero",
    "cmd.exit.missing_b",
    "cmd.extensions.disabled_in_script",
    "cmd.for.single_percent",
    "cmd.if_errorlevel_equal_misuse",
    "cmd.interactive.choice",
    "cmd.interactive.cmd",
    "cmd.interactive.pause",
    "cmd.interactive.set_p",
    "cmd.line_endings.lf_only",
    "cmd.line_endings.mixed",
    "cmd.line_length.limit",
    "cmd.line_length.near",
    "cmd.numeric_comparison.unguarded",
    "cmd.option.dash",
    "cmd.posix_path",
    "infra.common_scripts.missing",
    "cmd.pushd_popd.unbalanced",
    "cmd.pushd.unquoted_space",
    "cmd.read_failed",
    "cmd.robocopy.exitcode",
    "cmd.robocopy.retries_default",
    "cmd.set.space_around_equals",
    "cmd.set.posix_path",
    "cmd.setlocal.missing",
    "cmd.setlocal.order",
    "cmd.setlocal.unbalanced",
    "cmd.start.no_wait",
    "cmd.start.quoted_title",
    "cmd.unsafe.bang",
    "cmd.unsafe.meta",
    "cmd.unsafe.percent",
    "cmd.xcopy.interactive",
    "cmd.xcopy.missing_i",
    "cmd.xcopy.missing_y",
    "path.invalid_chars",
    "path.reserved_device",
    "path.trailing_space_dot",
    "path.unc",
    "path.value_length",
    "path.value_non_ascii",
}

# Rules that can be automatically fixed
FIXABLE_RULES = {
    "cmd.encoding.bom": "Remove UTF-8 BOM from file",
    "cmd.line_endings.lf_only": "Convert LF to CRLF line endings",
    "cmd.line_endings.mixed": "Normalize to CRLF line endings",
}

# Rule descriptions for --list-rules
RULE_DESCRIPTIONS: dict[str, str] = {
    "cmd.autorun.missing_d": "cmd invocation missing /d when AutoRun is enabled in registry",
    "cmd.block.percent_errorlevel": "Percent expansion of ERRORLEVEL inside (...) block (may be stale)",
    "cmd.block.percent_var_after_set": "Percent expansion inside (...) block with set variable (use delayed expansion)",
    "cmd.call.missing": "Batch file invoked without 'call' keyword",
    "cmd.call.pipe_or_redirect": "call combined with pipe or redirection (cmd parsing can break)",
    "cmd.call.unquoted_space": "call command path contains unquoted spaces",
    "cmd.caret.trailing_space": "Line continuation caret (^) has trailing whitespace",
    "cmd.cd.missing_d": "cd command without /d flag for cross-drive paths",
    "cmd.cd.unc": "cd command uses UNC path (prefer pushd)",
    "cmd.cd.unquoted_space": "cd command path has unquoted spaces",
    "cmd.cmd_c.quote_meta": "cmd /c quoted string contains meta characters",
    "cmd.delayed_expansion.before_enabled": "!VAR! syntax used before enabling delayed expansion",
    "cmd.delayed_expansion.cmd_v_on": "Delayed expansion enabled via cmd /v:on",
    "cmd.delayed_expansion.enabled": "Script enables delayed expansion",
    "cmd.delayed_expansion.token": "Script uses !VAR! token syntax",
    "cmd.cwd.relative_paths": "Script uses relative paths without early script-dir anchor (e.g., %~dp0)",
    "cmd.encoding.bom": "File has UTF-8 BOM (fixable)",
    "cmd.encoding.no_chcp": "Non-ASCII content without chcp directive near top",
    "cmd.encoding.non_ascii": "File contains non-ASCII characters",
    "cmd.encoding.nul": "File contains many NUL bytes (possible wrong encoding)",
    "cmd.encoding.utf16": "File is UTF-16 encoded (save as UTF-8)",
    "cmd.env.setx": "setx command modifies persistent environment",
    "cmd.errorlevel.ascending": "if errorlevel checks in ascending order (should be descending)",
    "cmd.errorlevel.zero": "if errorlevel 0 always matches (errorlevel is >= comparison)",
    "cmd.exit.missing_b": "exit command without /b (will exit cmd.exe)",
    "cmd.extensions.disabled_in_script": "Script disables command extensions",
    "cmd.for.single_percent": "for loop uses single % variable (use %% in .cmd)",
    "cmd.if_errorlevel_equal_misuse": "if errorlevel uses >= comparison (order comparisons carefully)",
    "cmd.interactive.choice": "choice command is interactive",
    "cmd.interactive.cmd": "cmd invoked without /c or with /k (interactive)",
    "cmd.interactive.pause": "pause command is interactive",
    "cmd.interactive.set_p": "set /p is interactive (prompts for input)",
    "cmd.line_endings.lf_only": "File uses LF-only line endings (fixable)",
    "cmd.line_endings.mixed": "File has mixed line endings (fixable)",
    "cmd.line_length.limit": "Line exceeds cmd.exe limit (8191 chars)",
    "cmd.line_length.near": "Line near cmd.exe limit",
    "cmd.numeric_comparison.unguarded": "Numeric comparison (GTR/LSS etc) with possibly empty variable (requires 'if defined' or non-empty guard)",
    "cmd.option.dash": "Command uses dash-style options (prefer /style)",
    "cmd.posix_path": "POSIX-style path detected in cmd script",
    "cmd.pushd_popd.unbalanced": "Unbalanced pushd/popd commands",
    "cmd.pushd.unquoted_space": "pushd path has unquoted spaces",
    "cmd.read_failed": "Failed to read cmd file",
    "cmd.robocopy.exitcode": "robocopy used without handling success codes (0-7 are success)",
    "cmd.robocopy.retries_default": "robocopy used without /r: and /w: (defaults can be very long)",
    "cmd.set.space_around_equals": "set command has spaces around '='",
    "cmd.set.posix_path": "set command assigns POSIX-style path",
    "cmd.setlocal.missing": "Environment modified without setlocal",
    "cmd.setlocal.order": "endlocal used before setlocal",
    "cmd.setlocal.unbalanced": "Unbalanced setlocal/endlocal",
    "cmd.start.no_wait": "start without /wait in CI profile",
    "cmd.start.quoted_title": "start with quoted arg missing empty title",
    "cmd.unsafe.bang": "Path/value contains '!' (conflicts with delayed expansion)",
    "cmd.unsafe.meta": "Path/value contains cmd meta characters (&<>|^)",
    "cmd.unsafe.percent": "Path/value contains '%' (may cause expansion issues)",
    "cmd.xcopy.interactive": "xcopy uses interactive flags (/w or /p)",
    "cmd.xcopy.missing_i": "xcopy without /i may prompt for file/dir destination",
    "cmd.xcopy.missing_y": "xcopy without /y may prompt for overwrite confirmation",
    "env.copycmd.present": "COPYCMD is set (xcopy overwrite prompt behavior may change)",
    "path.invalid_chars": "Path contains invalid Windows characters",
    "path.reserved_device": "Path contains Windows reserved device name",
    "path.trailing_space_dot": "Path ends with space or dot",
    "path.unc": "UNC network path detected",
    "path.value_length": "Path length near or exceeds limits",
    "path.value_non_ascii": "Path contains non-ASCII characters",
    "infra.common_scripts.missing": "Required core common script missing from scripts/runsets/common/",
}

# SARIF format constants
SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
TOOL_NAME = "preflight_checks"
TOOL_VERSION = "1.1.0"

# Default config file names
CONFIG_FILE_NAMES = [".preflightrc.yml", ".preflightrc.yaml", ".preflightrc.json", "preflight.config.yml"]


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


# =============================================================================
# Configuration file support
# =============================================================================

@dataclass
class PreflightConfig:
    """Configuration loaded from .preflightrc.yml or similar."""
    profile: str = "default"
    allow_non_ascii: bool = False
    cmd_exclude: list[str] = field(default_factory=list)
    scan_exclude: list[str] = field(default_factory=list)
    disable_rules: list[str] = field(default_factory=list)
    enable_only: list[str] = field(default_factory=list)
    require_git: bool = False
    require_powershell: bool = False
    strict: bool = False
    simulate_windows: bool = False


def _find_config_file(repo_root: Path) -> Path | None:
    """Search for a config file in the repo root."""
    for name in CONFIG_FILE_NAMES:
        candidate = repo_root / name
        if candidate.exists():
            return candidate
    return None


def _load_config_file(path: Path) -> PreflightConfig:
    """Load configuration from YAML or JSON file."""
    config = PreflightConfig()
    if not path.exists():
        return config
    
    text = path.read_text(encoding="utf-8-sig")
    data: dict[str, Any] = {}
    
    if path.suffix in {".yml", ".yaml"}:
        if not HAS_YAML:
            print(f"[warn] YAML config found but PyYAML not installed: {path}", file=sys.stderr)
            return config
        data = yaml.safe_load(text) or {}
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        return config
    
    if not isinstance(data, dict):
        return config
    
    if "profile" in data:
        config.profile = str(data["profile"])
    if "allow_non_ascii" in data:
        config.allow_non_ascii = bool(data["allow_non_ascii"])
    if "cmd_exclude" in data and isinstance(data["cmd_exclude"], list):
        config.cmd_exclude = [str(x) for x in data["cmd_exclude"]]
    if "scan_exclude" in data and isinstance(data["scan_exclude"], list):
        config.scan_exclude = [str(x) for x in data["scan_exclude"]]
    if "disable_rules" in data and isinstance(data["disable_rules"], list):
        config.disable_rules = [str(x) for x in data["disable_rules"]]
    if "enable_only" in data and isinstance(data["enable_only"], list):
        config.enable_only = [str(x) for x in data["enable_only"]]
    if "require_git" in data:
        config.require_git = bool(data["require_git"])
    if "require_powershell" in data:
        config.require_powershell = bool(data["require_powershell"])
    if "strict" in data:
        config.strict = bool(data["strict"])
    if "simulate_windows" in data:
        config.simulate_windows = bool(data["simulate_windows"])
    
    return config


# =============================================================================
# Git integration for --changed-only
# =============================================================================

def _get_git_changed_files(repo_root: Path, extensions: set[str]) -> list[Path]:
    """Get list of changed files (staged + unstaged) from git."""
    changed: set[Path] = set()
    
    try:
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    p = repo_root / line
                    if p.suffix.lower() in extensions:
                        changed.add(p)
        
        # Get unstaged files
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    p = repo_root / line
                    if p.suffix.lower() in extensions:
                        changed.add(p)
        
        # Get untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    p = repo_root / line
                    if p.suffix.lower() in extensions:
                        changed.add(p)
    except OSError:
        pass
    
    return sorted(changed)


# =============================================================================
# Auto-fix functionality
# =============================================================================

@dataclass
class FixResult:
    """Result of an auto-fix operation."""
    path: Path
    rule: str
    success: bool
    message: str


def _fix_bom(path: Path) -> FixResult:
    """Remove UTF-8 BOM from a file."""
    try:
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            path.write_bytes(data[3:])
            return FixResult(path, "cmd.encoding.bom", True, "Removed UTF-8 BOM")
        return FixResult(path, "cmd.encoding.bom", True, "No BOM found")
    except OSError as e:
        return FixResult(path, "cmd.encoding.bom", False, f"Failed: {e}")


def _fix_line_endings(path: Path) -> FixResult:
    """Convert line endings to CRLF."""
    try:
        data = path.read_bytes()
        # Normalize all line endings to LF first, then convert to CRLF
        normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        crlf_data = normalized.replace(b"\n", b"\r\n")
        if data != crlf_data:
            path.write_bytes(crlf_data)
            return FixResult(path, "cmd.line_endings", True, "Converted to CRLF")
        return FixResult(path, "cmd.line_endings", True, "Already CRLF")
    except OSError as e:
        return FixResult(path, "cmd.line_endings", False, f"Failed: {e}")


def _apply_fixes(path: Path, rules_to_fix: set[str]) -> list[FixResult]:
    """Apply all applicable fixes to a file."""
    results: list[FixResult] = []
    
    if "cmd.encoding.bom" in rules_to_fix:
        results.append(_fix_bom(path))
    
    if "cmd.line_endings.lf_only" in rules_to_fix or "cmd.line_endings.mixed" in rules_to_fix:
        results.append(_fix_line_endings(path))
    
    return results


def _collect_fixable_issues(issues: list[Issue]) -> dict[Path, set[str]]:
    """Collect fixable issues grouped by file path."""
    fixable: dict[Path, set[str]] = {}
    for issue in issues:
        if issue.rule in FIXABLE_RULES and issue.path:
            p = Path(issue.path)
            if p not in fixable:
                fixable[p] = set()
            fixable[p].add(issue.rule)
    return fixable


# =============================================================================
# SARIF output format
# =============================================================================

def _issue_to_sarif_result(issue: Issue, repo_root: Path) -> dict[str, Any]:
    """Convert an Issue to a SARIF result object."""
    level_map = {"error": "error", "warn": "warning", "info": "note"}
    
    result: dict[str, Any] = {
        "ruleId": issue.rule,
        "level": level_map.get(issue.level, "warning"),
        "message": {"text": issue.message},
    }
    
    if issue.path:
        try:
            rel_path = Path(issue.path).relative_to(repo_root)
            uri = str(rel_path).replace("\\", "/")
        except ValueError:
            uri = issue.path
        
        location: dict[str, Any] = {
            "physicalLocation": {
                "artifactLocation": {"uri": uri},
            }
        }
        
        if issue.line is not None:
            location["physicalLocation"]["region"] = {
                "startLine": issue.line,
            }
        
        result["locations"] = [location]
    
    return result


def _build_sarif_output(
    errors: list[Issue],
    warnings: list[Issue],
    infos: list[Issue],
    repo_root: Path,
) -> dict[str, Any]:
    """Build SARIF 2.1.0 compliant output."""
    all_issues = errors + warnings + infos
    
    # Build rule definitions
    rules: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    for issue in all_issues:
        if issue.rule not in seen_rules:
            seen_rules.add(issue.rule)
            rule_def: dict[str, Any] = {
                "id": issue.rule,
                "shortDescription": {"text": issue.rule},
            }
            if issue.rule in RULE_DESCRIPTIONS:
                rule_def["fullDescription"] = {"text": RULE_DESCRIPTIONS[issue.rule]}
            if issue.rule in FIXABLE_RULES:
                rule_def["properties"] = {"fixable": True}
            rules.append(rule_def)
    
    # Build results
    results = [_issue_to_sarif_result(issue, repo_root) for issue in all_issues]
    
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "informationUri": "https://github.com/Einfeld686/MarsDiskSimulation",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


# =============================================================================
# Rule filtering
# =============================================================================

def _should_report_rule(
    rule: str,
    disable_rules: set[str],
    enable_only: set[str],
) -> bool:
    """Determine if a rule should be reported based on filters."""
    if enable_only:
        return rule in enable_only
    if disable_rules:
        return rule not in disable_rules
    return True


def _filter_issues(
    issues: list[Issue],
    disable_rules: set[str],
    enable_only: set[str],
) -> list[Issue]:
    """Filter issues based on rule enable/disable settings."""
    return [
        issue for issue in issues
        if _should_report_rule(issue.rule, disable_rules, enable_only)
    ]


# =============================================================================
# List rules command
# =============================================================================

def _print_rules_list() -> None:
    """Print all available rules with descriptions."""
    print("Available preflight check rules:\n")
    
    # Group rules by prefix
    groups: dict[str, list[str]] = {}
    all_rules = set(CMD_ALLOWLIST_RULES) | set(RULE_DESCRIPTIONS.keys())
    
    for rule in sorted(all_rules):
        prefix = rule.split(".")[0] if "." in rule else "other"
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(rule)
    
    for group_name in sorted(groups.keys()):
        print(f"## {group_name.upper()}\n")
        for rule in sorted(groups[group_name]):
            desc = RULE_DESCRIPTIONS.get(rule, "(no description)")
            fixable = " [FIXABLE]" if rule in FIXABLE_RULES else ""
            print(f"  {rule}{fixable}")
            print(f"    {desc}\n")
    
    print("\nFixable rules can be automatically corrected with --fix option.")
    print(f"Total rules: {len(all_rules)}")


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


def _maybe_reexec_with_python311() -> None:
    if sys.version_info >= (3, 11):
        return
    if os.environ.get("MARS_PREFLIGHT_NO_REEXEC") == "1":
        return
    if os.environ.get("MARS_PREFLIGHT_REEXEC") == "1":
        return
    if not Path(sys.argv[0]).exists():
        return
    candidates: list[list[str]] = []
    if _is_windows():
        candidates.append(["py", "-3.11"])
    candidates.append(["python3.11"])
    env = os.environ.copy()
    env["MARS_PREFLIGHT_REEXEC"] = "1"
    for cmd in candidates:
        try:
            os.execvpe(cmd[0], cmd + sys.argv, env)
        except FileNotFoundError:
            continue
        except OSError:
            continue


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


def _split_cmdline_tokens(raw: str) -> list[str]:
    try:
        return shlex.split(raw, posix=False)
    except ValueError:
        return raw.split()


def _expand_cmd_vars(raw: str) -> tuple[str, bool]:
    expanded = False

    def repl(match: re.Match[str]) -> str:
        nonlocal expanded
        expanded = True
        name = match.group(1)
        return os.environ.get(name, "")

    return CMD_ENV_VAR_RE.sub(repl, raw), expanded


def _normalize_exe_token(token: str) -> str:
    return token.strip().strip('"').strip("'")


def _python_exe_basename(token: str) -> str:
    if not token:
        return ""
    return PureWindowsPath(token).name.lower()


def _validate_python_exe_tokens(
    label: str,
    exe_token: str,
    args: list[str],
    errors: list[Issue],
    warnings: list[Issue],
    warn_only: bool,
) -> bool:
    ok = True

    def report(rule: str, message: str) -> None:
        nonlocal ok
        ok = False
        if warn_only:
            _warn(warnings, rule, message)
        else:
            _error(errors, rule, message)

    exe_clean = _normalize_exe_token(exe_token)
    if not exe_clean:
        report("tool.python_exe_empty", f"{label} is empty")
        return False
    if exe_clean == "-" or exe_clean.startswith("-"):
        report("tool.python_exe_invalid", f"{label} starts with '-': {exe_token}")
    exe_name = _python_exe_basename(exe_clean)
    exe_unknown = any(ch in exe_clean for ch in "%!$")
    exe_is_py = None if exe_unknown else exe_name in {"py", "py.exe"}
    for raw_arg in args:
        arg = _normalize_exe_token(raw_arg)
        if not arg:
            continue
        if arg == "-":
            report("tool.python_exe_arg_dash", f"{label} has standalone '-' argument")
            continue
        if arg.startswith("-"):
            if exe_is_py is None:
                continue
            if exe_is_py:
                if arg in PY_LAUNCHER_ALLOWED_ARGS or PY_LAUNCHER_VERSION_RE.match(arg):
                    continue
                report(
                    "tool.python_exe_arg_invalid",
                    f"{label} has unsupported py argument: {arg}",
                )
                continue
            if PY_LAUNCHER_VERSION_RE.match(arg):
                report(
                    "tool.python_exe_version_arg_non_py",
                    f"{label} has {arg} but launcher is '{exe_name}'",
                )
                continue
            report(
                "tool.python_exe_arg_invalid",
                f"{label} has unexpected argument: {arg}",
            )
    return ok


def _probe_python_exe(
    exe_token: str,
    args: list[str],
    errors: list[Issue],
    warnings: list[Issue],
    warn_only: bool,
) -> bool:
    normalized_args = [_normalize_exe_token(arg) for arg in args if arg]
    cmd = [_normalize_exe_token(exe_token)] + normalized_args + [
        "-c",
        "import sys; sys.exit(0)",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError as exc:
        msg = f"python_exe probe failed to start: {exe_token} ({exc})"
        if warn_only:
            _warn(warnings, "tool.python_exe_probe_failed", msg)
        else:
            _error(errors, "tool.python_exe_probe_failed", msg)
        return False
    if result.returncode != 0:
        combined = f"{result.stderr}\n{result.stdout}".strip()
        if PYTHON_PROBE_ERROR_RE.search(combined):
            msg = f"python_exe probe rejected arguments: {exe_token}"
            if warn_only:
                _warn(warnings, "tool.python_exe_invalid_invocation", msg)
            else:
                _error(errors, "tool.python_exe_invalid_invocation", msg)
            return False
        msg = f"python_exe probe exited with {result.returncode}: {exe_token}"
        if warn_only:
            _warn(warnings, "tool.python_exe_probe_failed", msg)
        else:
            _error(errors, "tool.python_exe_probe_failed", msg)
        return False
    return True


def _check_python(
    errors: list[Issue],
    warnings: list[Issue],
    warn_only: bool,
    python_exe: str | None,
) -> None:
    if python_exe:
        raw = python_exe.strip()
        if raw:
            raw_parts = _split_cmdline_tokens(raw)
            raw_exe = _normalize_exe_token(raw_parts[0]) if raw_parts else ""
            raw_args = raw_parts[1:] if raw_parts else []
            ok = True
            if raw_parts:
                ok = _validate_python_exe_tokens(
                    "python_exe",
                    raw_exe,
                    raw_args,
                    errors,
                    warnings,
                    warn_only,
                )
            else:
                msg = f"python_exe is empty: {python_exe}"
                if warn_only:
                    _warn(warnings, "tool.python_exe_empty", msg)
                else:
                    _error(errors, "tool.python_exe_empty", msg)
                ok = False
            expanded_raw, did_expand = _expand_cmd_vars(raw)
            exe_token = raw_exe
            args = raw_args
            if did_expand:
                expanded_parts = _split_cmdline_tokens(expanded_raw.strip())
                if expanded_parts:
                    exe_token = _normalize_exe_token(expanded_parts[0])
                    args = expanded_parts[1:]
                    ok = _validate_python_exe_tokens(
                        "python_exe (expanded)",
                        exe_token,
                        args,
                        errors,
                        warnings,
                        warn_only,
                    ) and ok
                else:
                    msg = f"python_exe empty after expansion: {python_exe}"
                    if warn_only:
                        _warn(warnings, "tool.python_exe_empty_after_expand", msg)
                    else:
                        _error(errors, "tool.python_exe_empty_after_expand", msg)
                    exe_token = ""
                    args = []
                    ok = False
            if exe_token and not exe_token.startswith("-"):
                expanded = exe_token
                if _is_windows() or "$" in expanded or "%" in expanded:
                    expanded = os.path.expandvars(exe_token)
                if os.path.exists(expanded) or shutil.which(expanded) is not None:
                    if ok and _probe_python_exe(expanded, args, errors, warnings, warn_only):
                        return
                else:
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
        key = winreg.OpenKey(root, r"Software\Microsoft\Command Processor")
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
    allow_non_ascii: bool = False,
) -> None:
    if not temp_dir:
        _error(errors, "env.temp_missing", "TEMP/TMP is not set")
        return
    temp_path = Path(temp_dir)
    _cmd_unsafe_issue("TEMP/TMP", temp_dir, errors, warnings, cmd_unsafe_error, False)
    if _contains_non_ascii(temp_dir) and not allow_non_ascii:
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
    allow_non_ascii: bool = False,
) -> None:
    for key in PATH_ENV_VARS:
        value = os.environ.get(key, "")
        if not value:
            continue
        _cmd_unsafe_issue(key, value, errors, warnings, cmd_unsafe_error, False)
        if _contains_non_ascii(value) and not allow_non_ascii:
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
    copycmd = os.environ.get("COPYCMD", "")
    if copycmd:
        _warn(warnings, "env.copycmd.present", f"COPYCMD is set: {copycmd}")


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
    allow_non_ascii: bool = False,
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
    if _contains_non_ascii(value) and not allow_non_ascii:
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


def _check_common_scripts(repo_root: Path, errors: list[Issue]) -> None:
    common_dir = repo_root / "scripts" / "runsets" / "common"
    required = [
        "resolve_python.cmd",
        "python_exec.cmd",
        "sanitize_token.cmd",
        "read_overrides_cmd.py",
        "calc_parallel_jobs.py",
    ]
    for script in required:
        script_path = common_dir / script
        if not script_path.exists():
            _error(
                errors,
                "infra.common_scripts.missing",
                f"required common infrastructure script missing: {script}",
            )


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
        if DELAYED_SETLOCAL_RE.search(lowered):
            lines.append(line_no)
        elif _line_has_cmd_v_on(lowered):
            lines.append(line_no)
    return lines


def _detect_delayed_expansion(text: str) -> bool:
    for line in text.splitlines():
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
        if DELAYED_SETLOCAL_RE.search(line_body):
            return True
        if _line_has_cmd_v_on(line_body):
            return True
    return False


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


def _load_cmd_allowlist(path: Path, warnings: list[Issue]) -> list[AllowlistEntry]:
    entries: list[AllowlistEntry] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "::" not in line:
            _warn(
                warnings,
                "cmd.allowlist.missing_rules",
                "allowlist entry missing rules; ignored (use ::* or ::rule1,rule2)",
                path=path,
                line=line_no,
            )
            continue
        path_part, rule_part = line.split("::", 1)
        path_part = path_part.strip()
        rule_part = rule_part.strip()
        if not path_part:
            _warn(
                warnings,
                "cmd.allowlist.missing_path",
                "allowlist entry missing path",
                path=path,
                line=line_no,
            )
            continue
        rules = {item.strip() for item in rule_part.split(",") if item.strip()}
        if not rules:
            _warn(
                warnings,
                "cmd.allowlist.missing_rules",
                "allowlist entry missing rules; ignored (use ::* or ::rule1,rule2)",
                path=path,
                line=line_no,
            )
            continue
        unknown_rules = {rule for rule in rules if rule != "*" and rule not in CMD_ALLOWLIST_RULES}
        if unknown_rules:
            unknown_list = ", ".join(sorted(unknown_rules))
            _warn(
                warnings,
                "cmd.allowlist.unknown_rule",
                f"allowlist entry has unknown rule(s): {unknown_list}",
                path=path,
                line=line_no,
            )
            rules.difference_update(unknown_rules)
            if not rules:
                _warn(
                    warnings,
                    "cmd.allowlist.missing_rules",
                    "allowlist entry has no valid rules; ignored (use ::* or ::rule1,rule2)",
                    path=path,
                    line=line_no,
                )
                continue
        if "*" in rules and len(rules) > 1:
            _warn(
                warnings,
                "cmd.allowlist.ambiguous_rules",
                "allowlist entry mixes '*' with rule names; '*' will override",
                path=path,
                line=line_no,
            )
            rules = {"*"}
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
            if not entry.rules:
                continue
            if "*" in entry.rules:
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


def _join_caret_lines(lines: list[str]) -> list[tuple[int, str]]:
    logical_lines: list[tuple[int, str]] = []
    buffer: list[str] = []
    start_line: int | None = None
    for line_no, line in enumerate(lines, 1):
        if start_line is None:
            start_line = line_no
        stripped = line.rstrip("\r\n")
        trimmed = stripped.rstrip()
        if trimmed.endswith("^"):
            buffer.append(trimmed[:-1])
            continue
        buffer.append(stripped)
        logical_lines.append((start_line, "".join(buffer)))
        buffer = []
        start_line = None
    if buffer:
        logical_lines.append((start_line or 1, "".join(buffer)))
    return logical_lines


def _split_cmd_segments(line: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    in_quote = False
    escape = False
    for ch in line:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "^":
            escape = True
            current.append(ch)
            continue
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
            continue
        if not in_quote and ch in "&|":
            segment = "".join(current)
            if segment.strip():
                segments.append(segment)
            current = []
            continue
        current.append(ch)
    segment = "".join(current)
    if segment.strip():
        segments.append(segment)
    return segments


@dataclass
class _BlockState:
    set_vars: set[str] = field(default_factory=set)
    used_vars: dict[str, int] = field(default_factory=dict)
    warned_vars: set[str] = field(default_factory=set)
    errorlevel_warned: bool = False


def _has_unquoted_meta(line: str, meta_chars: set[str]) -> bool:
    in_quote = False
    escape = False
    for ch in line:
        if escape:
            escape = False
            continue
        if ch == "^":
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if not in_quote and ch in meta_chars:
            return True
    return False


def _count_parens(line: str) -> tuple[int, int]:
    opens = 0
    closes = 0
    in_quote = False
    escape = False
    for ch in line:
        if escape:
            escape = False
            continue
        if ch == "^":
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if ch == "(":
            opens += 1
        elif ch == ")":
            closes += 1
    return opens, closes


def _token_is_relative_path(token: str) -> bool:
    if not token:
        return False
    cleaned = token.strip()
    if not cleaned:
        return False
    if cleaned.startswith(("%", "!", "^")):
        return False
    if cleaned.startswith(("-", "/")):
        return False
    if cleaned.startswith(("\\\\", "//")):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", cleaned):
        return False
    if cleaned.startswith((".\\", "..\\", "./", "../")):
        return True
    if "\\" in cleaned or "/" in cleaned:
        return True
    return False


def _line_has_relative_path(line_body: str) -> bool:
    try:
        tokens = _split_cmdline_tokens(line_body)
    except Exception:
        tokens = line_body.split()
    for token in tokens:
        token_clean = _normalize_exe_token(token)
        if _token_is_relative_path(token_clean):
            return True
    return False


def _detect_script_dir_anchor(lines: list[tuple[int, str]], limit: int) -> bool:
    checked = 0
    for _line_no, line in lines:
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
        checked += 1
        if SCRIPT_DIR_RE.search(line_body):
            return True
        if checked >= limit:
            return False
    return False


def _iter_named_commands(line: str, names: set[str]) -> list[tuple[str, list[str]]]:
    commands: list[tuple[str, list[str]]] = []
    for segment in _split_cmd_segments(line):
        segment_body = segment.strip()
        if not segment_body:
            continue
        if segment_body.startswith("@"):
            segment_body = segment_body[1:].lstrip()
        lower = segment_body.lower()
        if lower.startswith("rem") and (len(lower) == 3 or lower[3].isspace()):
            continue
        if lower.startswith("::"):
            continue
        tokens = _split_cmdline_tokens(segment_body)
        if not tokens:
            continue
        tokens[0] = tokens[0].lstrip("@")
        first_token = _normalize_exe_token(tokens[0]).lower()
        if first_token.startswith("echo") or first_token in {"set", "setx"}:
            continue
        for idx, token in enumerate(tokens):
            token_clean = _normalize_exe_token(token)
            if not token_clean:
                continue
            cmd_name = PureWindowsPath(token_clean).name.lower()
            if cmd_name in names:
                commands.append((cmd_name, tokens[idx + 1 :]))
                break
    return commands


def _parse_xcopy_flags(tokens: list[str]) -> tuple[bool, bool, bool, bool, bool]:
    has_w = False
    has_p = False
    has_y = False
    has_i = False
    has_no_y = False
    for raw in tokens:
        token = _normalize_exe_token(raw).lower()
        if not token.startswith("/"):
            continue
        if token.startswith("/-y"):
            has_no_y = True
            continue
        body = token[1:]
        if ":" in body:
            continue
        if not body:
            continue
        if "w" in body:
            has_w = True
        if "p" in body:
            has_p = True
        if "y" in body:
            has_y = True
        if "i" in body:
            has_i = True
    return has_w, has_p, has_y, has_i, has_no_y


def _extract_set_name(line_body: str) -> str | None:
    rest = line_body[3:].lstrip()
    if not rest:
        return None
    rest = re.split(r"[&|]", rest, 1)[0].strip()
    rest_lower = rest.lower()
    if rest_lower.startswith("/p") or rest_lower.startswith("/a"):
        return None
    if rest.startswith('"') and rest.endswith('"') and "=" in rest:
        content = rest.strip('"')
        name, _ = content.split("=", 1)
        return name.strip()
    if "=" in rest:
        name, _ = rest.split("=", 1)
        return name.strip()
    return None


def _is_cmd_token(token: str) -> bool:
    if not token:
        return False
    lower = token.lower()
    if lower in {"cmd", "cmd.exe", "%comspec%", "!comspec!"}:
        return True
    base = PureWindowsPath(token).name.lower()
    return base in {"cmd", "cmd.exe"}


def _iter_cmd_invocations(line: str) -> list[tuple[bool, bool, bool, bool]]:
    invocations: list[tuple[bool, bool, bool, bool]] = []
    for segment in _split_cmd_segments(line):
        segment_body = segment.strip()
        if not segment_body:
            continue
        if segment_body.startswith("@"):
            segment_body = segment_body[1:].lstrip()
        lower = segment_body.lower()
        if lower.startswith("rem") and (len(lower) == 3 or lower[3].isspace()):
            continue
        if lower.startswith("::"):
            continue
        tokens = _split_cmdline_tokens(segment_body)
        if not tokens:
            continue
        tokens[0] = tokens[0].lstrip("@")
        first_token = _normalize_exe_token(tokens[0]).lower()
        if first_token.startswith("echo") or first_token in {"set", "setx"}:
            continue
        for idx, token in enumerate(tokens):
            token_clean = _normalize_exe_token(token)
            if not token_clean:
                continue
            if not _is_cmd_token(token_clean):
                continue
            if idx > 0:
                prev = _normalize_exe_token(tokens[idx - 1]).lower()
                prev2 = ""
                if idx > 1:
                    prev2 = _normalize_exe_token(tokens[idx - 2]).lower()
                if prev not in {"call", "start"} and not (
                    prev2 == "start" and prev in {"", '""'}
                ):
                    continue
            tail_tokens = tokens[idx + 1 :]
            tail = " ".join(tail_tokens)
            has_d = False
            for tail_token in tail_tokens:
                token_clean = _normalize_exe_token(tail_token).lower()
                if not token_clean:
                    continue
                if token_clean.startswith(("/c", "/k")):
                    break
                if token_clean == "/d" or token_clean.startswith("/d:"):
                    has_d = True
            invocations.append(
                (
                    bool(CMD_SWITCH_C_RE.search(tail)),
                    bool(CMD_SWITCH_K_RE.search(tail)),
                    bool(CMD_SWITCH_V_ON_RE.search(tail)),
                    has_d,
                )
            )
    return invocations


def _line_has_cmd_v_on(line_body: str) -> bool:
    return any(cmd_v_on for _cmd_c, _cmd_k, cmd_v_on, _cmd_d in _iter_cmd_invocations(line_body))


def _dash_option_cmd(line_body: str) -> str | None:
    for segment in _split_cmd_segments(line_body):
        tokens = _split_cmdline_tokens(segment)
        if not tokens:
            continue
        tokens[0] = tokens[0].lstrip("@")
        idx = 0
        if tokens[0].lower() == "call" and len(tokens) > 1:
            idx = 1
        if idx >= len(tokens):
            continue
        cmd_token = _normalize_exe_token(tokens[idx])
        cmd_name = PureWindowsPath(cmd_token).name.lower()
        if cmd_name in DASH_OPTION_CMD_NAMES:
            if len(tokens) > idx + 1 and tokens[idx + 1].startswith("-"):
                return cmd_name
    return None


def _scan_cmd_file(
    path: Path,
    errors: list[Issue],
    warnings: list[Issue],
    infos: list[Issue],
    cmd_unsafe_error: bool,
    profile: str,
    allowlist_rules: set[str] | None,
    autorun_detected: bool,
    debug: bool = False,
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
    for line_no, line in enumerate(lines, 1):
        if line.rstrip().endswith("^") and not line.endswith("^"):
            report_warn(
                "cmd.caret.trailing_space",
                "cmd line continuation caret has trailing whitespace",
                line_no,
            )
    logical_lines = _join_caret_lines(lines)
    script_dir_anchor = _detect_script_dir_anchor(logical_lines, CWD_SCAN_LINES)
    if debug:
        for line_no, line in logical_lines:
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
            if _line_has_cmd_v_on(line_body):
                report_info(
                    "cmd.delayed_expansion.cmd_v_on",
                    "cmd enables delayed expansion via /v:on",
                    line_no,
                )
            if BANG_TOKEN_RE.search(line_body):
                report_info(
                    "cmd.delayed_expansion.token",
                    "cmd uses !VAR! token",
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
    block_stack: list[_BlockState] = []
    block_errorlevel_warned = False
    relative_path_line: int | None = None
    errorlevel_semantics_line: int | None = None
    robocopy_used = False
    robocopy_exitcode_checked = False
    robocopy_first_line: int | None = None
    robocopy_retry_missing_line: int | None = None

    for line_no, line in logical_lines:
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
        if relative_path_line is None and _line_has_relative_path(line_body):
            relative_path_line = line_no
        if re.search(r"\bcall\b", lower) and _has_unquoted_meta(line_body, {"|", "<", ">"}):
            report_warn(
                "cmd.call.pipe_or_redirect",
                "cmd call with pipe/redirection is unreliable (avoid call + |/< / >)",
                line_no,
            )
        opens, closes = _count_parens(line_body)
        for _ in range(opens):
            block_stack.append(_BlockState())
        if block_stack:
            if PERCENT_ERRORLEVEL_RE.search(line_body) and not block_errorlevel_warned:
                report_warn(
                    "cmd.block.percent_errorlevel",
                    "cmd uses %ERRORLEVEL% inside (...) block; value may be stale",
                    line_no,
                )
                block_errorlevel_warned = True
            for match in CMD_ENV_VAR_RE.finditer(line_body):
                var_name = match.group(1)
                if not var_name or not VAR_NAME_RE.match(var_name):
                    continue
                var_upper = var_name.upper()
                if var_upper == "ERRORLEVEL":
                    continue
                for block in block_stack:
                    if var_upper not in block.used_vars:
                        block.used_vars[var_upper] = line_no
                    if var_upper in block.set_vars and var_upper not in block.warned_vars:
                        report_warn(
                            "cmd.block.percent_var_after_set",
                            f"cmd uses %{var_name}% inside (...) block; percent expansion is parsed before execution",
                            line_no,
                        )
                        block.warned_vars.add(var_upper)
            if NUMERIC_COMPARISON_RE.search(line_body):
                # Heuristic skip if the line seems to have a guard early on
                if not re.search(r"\bif\s+defined\s+", line_body, re.I) and not '""' in line_body:
                    report_warn(
                        "cmd.numeric_comparison.unguarded",
                        "cmd uses numeric comparison with possibly empty variable; wrap in 'if defined' or check for empty string",
                        line_no,
                    )
            set_name = _extract_set_name(line_body)
            if set_name and VAR_NAME_RE.match(set_name):
                set_upper = set_name.upper()
                for block in block_stack:
                    if set_upper in block.used_vars and set_upper not in block.warned_vars:
                        report_warn(
                            "cmd.block.percent_var_after_set",
                            f"cmd sets {set_name} inside (...) block; percent expansion may not reflect updates",
                            line_no,
                        )
                        block.warned_vars.add(set_upper)
                    block.set_vars.add(set_upper)
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
        cmd_invocations = _iter_cmd_invocations(line_body)
        cmd_v_on_with_c = any(
            cmd_v_on and cmd_has_c for cmd_has_c, _cmd_k, cmd_v_on, _cmd_d in cmd_invocations
        )
        if autorun_detected:
            for _cmd_has_c, _cmd_has_k, _cmd_v_on, cmd_has_d in cmd_invocations:
                if not cmd_has_d:
                    if profile == "ci":
                        report_error(
                            "cmd.autorun.missing_d",
                            "cmd invocation missing /d while AutoRun is enabled",
                            line_no,
                        )
                    else:
                        report_warn(
                            "cmd.autorun.missing_d",
                            "cmd invocation missing /d while AutoRun is enabled",
                            line_no,
                        )
                    break
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
            if errorlevel_semantics_line is None:
                errorlevel_semantics_line = line_no
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
        if errorlevel_semantics_line is None and ERRORLEVEL_ANY_RE.search(line_body):
            errorlevel_semantics_line = line_no
        for match in ERRORLEVEL_ANY_RE.finditer(line_body):
            try:
                value = int(match.group(2))
            except (TypeError, ValueError):
                continue
            if value >= 8:
                robocopy_exitcode_checked = True
        for match in ERRORLEVEL_CMP_RE.finditer(line_body):
            op = match.group(1).lower()
            try:
                value = int(match.group(2))
            except (TypeError, ValueError):
                continue
            if op in {"geq", "gtr"} and value >= 8:
                robocopy_exitcode_checked = True
            if op in {"leq", "lss"} and value <= 7:
                robocopy_exitcode_checked = True
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
            for _ in range(closes):
                if block_stack:
                    block_stack.pop()
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
            and not (delayed_now or cmd_v_on_with_c)
            and not bang_missing_reported
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
        for cmd_has_c, cmd_has_k, _cmd_v_on, _cmd_d in cmd_invocations:
            if cmd_has_k or not cmd_has_c:
                if profile == "ci":
                    report_error(
                        "cmd.interactive.cmd",
                        "cmd invoked without /c (or with /k) is interactive",
                        line_no,
                    )
                else:
                    report_warn(
                        "cmd.interactive.cmd",
                        "cmd invoked without /c (or with /k) is interactive",
                        line_no,
                    )
                break
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
        dash_cmd = _dash_option_cmd(line_body)
        if dash_cmd:
            if profile == "ci":
                report_error(
                    "cmd.option.dash",
                    f"cmd {dash_cmd} uses '-' option; prefer '/' style switches",
                    line_no,
                )
            else:
                report_warn(
                    "cmd.option.dash",
                    f"cmd {dash_cmd} uses '-' option; prefer '/' style switches",
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
        for _cmd_name, tail_tokens in _iter_named_commands(line_body, XCOPY_CMD_NAMES):
            has_w, has_p, has_y, has_i, has_no_y = _parse_xcopy_flags(tail_tokens)
            if has_w or has_p:
                if profile == "ci":
                    report_error(
                        "cmd.xcopy.interactive",
                        "xcopy uses /w or /p (interactive)",
                        line_no,
                    )
                else:
                    report_warn(
                        "cmd.xcopy.interactive",
                        "xcopy uses /w or /p (interactive)",
                        line_no,
                    )
            if not has_y or has_no_y:
                report_warn(
                    "cmd.xcopy.missing_y",
                    "xcopy without /y may prompt for overwrite confirmation",
                    line_no,
                )
            if not has_i:
                report_warn(
                    "cmd.xcopy.missing_i",
                    "xcopy without /i may prompt for file/dir destination",
                    line_no,
                )
        for _cmd_name, tail_tokens in _iter_named_commands(line_body, ROBOCOPY_CMD_NAMES):
            robocopy_used = True
            if robocopy_first_line is None:
                robocopy_first_line = line_no
            has_r = False
            has_w = False
            for raw in tail_tokens:
                token = _normalize_exe_token(raw).lower()
                if token.startswith("/r:"):
                    has_r = True
                if token.startswith("/w:"):
                    has_w = True
            if (not has_r or not has_w) and robocopy_retry_missing_line is None:
                robocopy_retry_missing_line = line_no
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
            if not (is_set_p or is_set_a):
                value = _parse_set_value(line_body)
                if value:
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
        for _ in range(closes):
            if block_stack:
                block_stack.pop()
    if relative_path_line is not None and not script_dir_anchor:
        report_warn(
            "cmd.cwd.relative_paths",
            "cmd uses relative paths without anchoring to script dir (e.g., pushd %~dp0)",
            relative_path_line,
        )
    if errorlevel_semantics_line is not None:
        report_warn(
            "cmd.if_errorlevel_equal_misuse",
            "cmd uses if errorlevel; comparisons are >= (use descending checks or %errorlevel%)",
            errorlevel_semantics_line,
        )
    if robocopy_used and not robocopy_exitcode_checked and robocopy_first_line is not None:
        report_warn(
            "cmd.robocopy.exitcode",
            "robocopy used without handling success codes 0-7 (use if errorlevel 8)",
            robocopy_first_line,
        )
    if robocopy_retry_missing_line is not None:
        report_warn(
            "cmd.robocopy.retries_default",
            "robocopy used without /r: and /w: (defaults can be very long)",
            robocopy_retry_missing_line,
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
    elif setlocal_count > endlocal_count or delayed_stack or extensions_stack:
        report_warn(
            "cmd.setlocal.unbalanced",
            "cmd uses setlocal without matching endlocal (state stack not empty at end)",
            first_setlocal_line,
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

    def normalize_path(path: Path) -> Path:
        try:
            return path.resolve(strict=False)
        except OSError:
            return path

    seen: dict[Path, Path] = {}

    def add_path(path: Path) -> None:
        normalized = normalize_path(path)
        if normalized not in seen:
            seen[normalized] = normalized

    for cmd in cmd_files:
        cmd_path = Path(cmd)
        if not cmd_path.exists():
            _error(errors, "cmd.file_missing", f"cmd missing: {cmd_path}")
            continue
        if not is_excluded(cmd_path):
            add_path(cmd_path)
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
                add_path(cmd_path)
    return sorted(seen.values())


def _scan_repo_root(
    root: Path,
    errors: list[Issue],
    warnings: list[Issue],
    cmd_unsafe_error: bool,
    exclude_dirs: set[str],
    allow_non_ascii: bool = False,
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
            if _contains_non_ascii(name) and not allow_non_ascii:
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
    _maybe_reexec_with_python311()
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Core arguments (made optional for --list-rules and --fix modes)
    ap.add_argument("--repo-root", type=Path, help="Repository root directory.")
    ap.add_argument("--config", type=Path, help="Configuration YAML file.")
    ap.add_argument("--overrides", type=Path, help="Overrides file.")
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
        "--allow-non-ascii",
        action="store_true",
        help="Suppress non-ASCII path warnings.",
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
        choices=("text", "json", "sarif"),
        default="text",
        help="Output format (text, json, or sarif).",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Emit verbose diagnostics (e.g., delayed expansion usage).",
    )
    ap.add_argument("--strict", action="store_true")
    
    # New feature arguments
    ap.add_argument(
        "--list-rules",
        action="store_true",
        help="List all available rules and exit.",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix issues where possible (BOM, line endings).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what --fix would do without making changes.",
    )
    ap.add_argument(
        "--disable-rule",
        action="append",
        default=[],
        dest="disable_rules",
        metavar="RULE",
        help="Disable specific rule (repeatable).",
    )
    ap.add_argument(
        "--enable-only",
        action="append",
        default=[],
        dest="enable_only",
        metavar="RULE",
        help="Enable only specific rules (repeatable).",
    )
    ap.add_argument(
        "--changed-only",
        action="store_true",
        help="Only scan files changed in git working tree.",
    )
    ap.add_argument(
        "--config-file",
        type=Path,
        default=None,
        help="Path to .preflightrc.yml config file (auto-detected if not specified).",
    )
    
    args = ap.parse_args()

    # Handle --list-rules early exit
    if args.list_rules:
        _print_rules_list()
        return 0
    
    # Load config file if present
    file_config: PreflightConfig | None = None
    if args.config_file:
        if args.config_file.exists():
            file_config = _load_config_file(args.config_file)
        else:
            print(f"[error] Config file not found: {args.config_file}", file=sys.stderr)
            return 1
    elif args.repo_root:
        found_config = _find_config_file(args.repo_root)
        if found_config:
            file_config = _load_config_file(found_config)
            print(f"[info] Using config file: {found_config}", file=sys.stderr)
    
    # Merge config file settings with CLI args (CLI takes precedence)
    if file_config:
        if not args.profile or args.profile == "default":
            args.profile = file_config.profile
        if not args.allow_non_ascii:
            args.allow_non_ascii = file_config.allow_non_ascii
        if not args.cmd_exclude:
            args.cmd_exclude = file_config.cmd_exclude
        if not args.scan_exclude:
            args.scan_exclude = file_config.scan_exclude
        if not args.disable_rules:
            args.disable_rules = file_config.disable_rules
        if not args.enable_only:
            args.enable_only = file_config.enable_only
        if not args.require_git:
            args.require_git = file_config.require_git
        if not args.require_powershell:
            args.require_powershell = file_config.require_powershell
        if not args.strict:
            args.strict = file_config.strict
        if not args.simulate_windows:
            args.simulate_windows = file_config.simulate_windows

    # Convert rule lists to sets for faster lookup
    disable_rules_set = set(args.disable_rules) if args.disable_rules else set()
    enable_only_set = set(args.enable_only) if args.enable_only else set()
    
    # Validate rule names
    all_known_rules = set(CMD_ALLOWLIST_RULES) | set(RULE_DESCRIPTIONS.keys())
    for rule in disable_rules_set | enable_only_set:
        if rule not in all_known_rules:
            print(f"[warn] Unknown rule: {rule}", file=sys.stderr)

    # For --fix mode with minimal args, allow operation on just cmd files
    if args.fix and args.cmd and not args.repo_root:
        args.repo_root = Path.cwd()
    if args.fix and args.cmd and not args.config:
        args.config = Path("/dev/null") if not _is_windows() else Path("NUL")
    if args.fix and args.cmd and not args.overrides:
        args.overrides = Path("/dev/null") if not _is_windows() else Path("NUL")
    
    # Validate required arguments for normal operation
    if not args.repo_root:
        print("[error] --repo-root is required", file=sys.stderr)
        return 1
    if not args.config:
        print("[error] --config is required", file=sys.stderr)
        return 1
    if not args.overrides:
        print("[error] --overrides is required", file=sys.stderr)
        return 1

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

    # Handle --changed-only: get changed CMD files from git
    if args.changed_only:
        changed_cmd_files = _get_git_changed_files(args.repo_root, {".cmd", ".bat"})
        if changed_cmd_files:
            args.cmd = [str(p) for p in changed_cmd_files]
            print(f"[info] Scanning {len(changed_cmd_files)} changed file(s)", file=sys.stderr)
        else:
            print("[info] No changed CMD/BAT files found", file=sys.stderr)
            args.cmd = []

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
    autorun_detected = False

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
                allowlist_entries = _load_cmd_allowlist(args.cmd_allowlist, warnings)
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
            allow_non_ascii=args.allow_non_ascii,
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
            allow_non_ascii=args.allow_non_ascii,
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
            allow_non_ascii=args.allow_non_ascii,
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
    _check_common_scripts(args.repo_root, errors)

    if is_windows_host:
        autorun_values = _read_cmd_autorun_values()
        for label, value in autorun_values.items():
            _warn(
                warnings,
                "cmd.autorun",
                f"cmd AutoRun is set in {label}: {value}; use cmd /d to disable",
            )
        autorun_detected = bool(autorun_values)
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
            if _contains_non_ascii(value) and not args.allow_non_ascii:
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
                allow_non_ascii=args.allow_non_ascii,
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
        _check_temp_dir(temp_dir, errors, warnings, cmd_unsafe_error, args.allow_non_ascii)
        _check_env_paths(errors, warnings, cmd_unsafe_error, args.allow_non_ascii)
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
                autorun_detected,
                debug=args.debug,
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
            args.allow_non_ascii,
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

    # Apply rule filtering
    if disable_rules_set or enable_only_set:
        errors = _filter_issues(errors, disable_rules_set, enable_only_set)
        warnings = _filter_issues(warnings, disable_rules_set, enable_only_set)
        infos = _filter_issues(infos, disable_rules_set, enable_only_set)

    # Handle --fix mode
    fix_results: list[FixResult] = []
    if args.fix or args.dry_run:
        all_issues = errors + warnings
        fixable_by_path = _collect_fixable_issues(all_issues)
        
        if fixable_by_path:
            if args.dry_run:
                print("\n[dry-run] Would fix the following files:")
                for path, rules in sorted(fixable_by_path.items()):
                    for rule in sorted(rules):
                        print(f"  {path}: {rule} - {FIXABLE_RULES.get(rule, 'fix')}")
            else:
                print("\n[fix] Applying automatic fixes...")
                for path, rules in sorted(fixable_by_path.items()):
                    results = _apply_fixes(path, rules)
                    fix_results.extend(results)
                    for result in results:
                        status_icon = "✓" if result.success else "✗"
                        print(f"  [{status_icon}] {result.path}: {result.message}")
                
                # Re-scan fixed files to update issue counts
                if fix_results:
                    fixed_paths = {r.path for r in fix_results if r.success}
                    if fixed_paths:
                        print(f"\n[fix] Fixed {len(fixed_paths)} file(s). Re-scanning...")
                        # Clear issues for re-scan
                        errors_new: list[Issue] = []
                        warnings_new: list[Issue] = []
                        infos_new: list[Issue] = []
                        
                        for cmd_path in cmd_paths:
                            if cmd_path in fixed_paths:
                                allowlist_rules = _allowlist_rules_for(cmd_path, args.repo_root, allowlist_entries)
                                if allowlist_rules and "*" in allowlist_rules:
                                    continue
                                _scan_cmd_file(
                                    cmd_path,
                                    errors_new,
                                    warnings_new,
                                    infos_new,
                                    cmd_unsafe_error,
                                    args.profile,
                                    allowlist_rules,
                                    autorun_detected,
                                    debug=args.debug,
                                )
                        
                        # Update with re-scanned results for fixed files
                        # Keep issues from unfixed files
                        errors = [e for e in errors if e.path not in {str(p) for p in fixed_paths}] + errors_new
                        warnings = [w for w in warnings if w.path not in {str(p) for p in fixed_paths}] + warnings_new
                        infos = [i for i in infos if i.path not in {str(p) for p in fixed_paths}] + infos_new
                        
                        # Re-apply filtering
                        if disable_rules_set or enable_only_set:
                            errors = _filter_issues(errors, disable_rules_set, enable_only_set)
                            warnings = _filter_issues(warnings, disable_rules_set, enable_only_set)
                            infos = _filter_issues(infos, disable_rules_set, enable_only_set)
        else:
            print("\n[fix] No fixable issues found.")

    exit_code = 0
    if errors:
        exit_code = 1
    elif warnings and args.strict:
        exit_code = 2

    # Output formatting
    if args.format == "json":
        payload = _build_json_payload(errors, warnings, infos, exit_code)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return exit_code
    
    if args.format == "sarif":
        sarif_output = _build_sarif_output(errors, warnings, infos, args.repo_root)
        print(json.dumps(sarif_output, ensure_ascii=True, indent=2))
        return exit_code

    status = "ok"
    if errors:
        status = "failed"
    elif warnings and args.strict:
        status = "warn"
    
    # Summary line
    fix_summary = ""
    if fix_results:
        success_count = sum(1 for r in fix_results if r.success)
        fix_summary = f", fixes={success_count}/{len(fix_results)}"
    
    print(
        f"[preflight] {status} (errors={len(errors)}, warnings={len(warnings)}, infos={len(infos)}{fix_summary})"
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
