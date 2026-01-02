#!/usr/bin/env python3
"""Update the maintainability snapshot numbers in the plan document."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys

EN_DASH = "\u2013"

SECTION_MONO_PREFIX = "### 1."
SECTION_SCHEMA_PREFIX = "### 4."
SECTION_DEPRECATED_PREFIX = "### 5."
SECTION_MODULES_PREFIX = "### 7."

CODEBLOCK_MARKER = "```"


@dataclass(frozen=True)
class SnapshotStats:
    timestamp: str
    tz: str
    commit: str
    branch: str
    dirty: str
    run_zero_start: int
    run_zero_end: int
    run_zero_len: int
    run_one_start: int
    run_one_end: int
    run_one_len: int
    schema_lines: int
    schema_classes: int
    deprecated_count: int
    module_lines: dict[str, int]
    test_counts: dict[str, int]
    size_stats: dict[str, tuple[int, int]]


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    ok_returncodes: set[int] | None = None,
    warn_on_error: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if warn_on_error:
        allowed = ok_returncodes if ok_returncodes is not None else {0}
        if result.returncode not in allowed:
            message = f"warning: command failed (exit {result.returncode}): {' '.join(cmd)}"
            stderr = result.stderr.strip()
            if stderr:
                message = f"{message}: {stderr.splitlines()[0]}"
            print(message, file=sys.stderr)
    return result


def _git_info(repo_root: Path) -> tuple[str, str, str]:
    commit = "unknown"
    branch = "unknown"
    dirty = "unknown"

    result = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, warn_on_error=True)
    if result and result.returncode == 0:
        commit = result.stdout.strip() or "unknown"

    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, warn_on_error=True)
    if result and result.returncode == 0:
        branch = result.stdout.strip() or "unknown"

    result = _run(["git", "status", "--porcelain"], cwd=repo_root, warn_on_error=True)
    if result and result.returncode == 0:
        dirty = "true" if result.stdout.strip() else "false"

    return commit, branch, dirty


def _timestamp() -> tuple[str, str]:
    now = dt.datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M"), now.tzname() or "UTC"


def _parse_ast(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        raise RuntimeError(f"failed to parse {path}: {exc}") from exc


def _function_span(path: Path, name: str) -> tuple[int, int, int]:
    tree = _parse_ast(path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            end = node.end_lineno
            if end is None:
                raise RuntimeError(f"end line unknown for {name} in {path}")
            start = node.lineno
            if node.decorator_list:
                decorator_lines = [d.lineno for d in node.decorator_list if d.lineno is not None]
                if decorator_lines:
                    start = min([start, *decorator_lines])
            return start, end, end - start + 1
    raise RuntimeError(f"function {name} not found in {path}")


def _count_top_level_classes(path: Path) -> int:
    tree = _parse_ast(path)
    return sum(1 for node in tree.body if isinstance(node, ast.ClassDef))


def _count_deprecated(repo_root: Path) -> int:
    result = _run(
        ["rg", "-n", "-w", "-F", "deprecated", "marsdisk"],
        cwd=repo_root,
        ok_returncodes={0, 1},
        warn_on_error=True,
    )
    if result and result.returncode in (0, 1):
        return len(result.stdout.splitlines())
    pattern = re.compile(r"\bdeprecated\b")
    count = 0
    for path in (repo_root / "marsdisk").rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        count += sum(1 for line in text.splitlines() if pattern.search(line))
    return count


def _count_test_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _file_size(path: Path) -> int:
    return path.stat().st_size


def _replace_nth_number(text: str, n: int, value: int) -> tuple[str, bool]:
    matches = list(re.finditer(r"[0-9][0-9,]*", text))
    if len(matches) < n:
        return text, False
    match = matches[n - 1]
    updated = text[: match.start()] + f"{value:,}" + text[match.end() :]
    return updated, True


def _replace_bold_number(text: str, value: int) -> tuple[str, bool]:
    def repl(match: re.Match[str]) -> str:
        return f"**{value:,}{match.group(2)}**"

    updated, count = re.subn(r"\*\*([0-9][0-9,]*)([^\*]+)\*\*", repl, text, count=1)
    return updated, count == 1


def _replace_range(text: str, start: int, end: int) -> tuple[str, bool]:
    updated, count = re.subn(
        r"L[0-9]+[\u2013-]L[0-9]+",
        f"L{start}{EN_DASH}L{end}",
        text,
        count=1,
    )
    return updated, count == 1


def _format_snapshot_line(label: str, stats: SnapshotStats) -> str:
    return (
        f"{label}: {stats.timestamp} (commit {stats.commit}, branch={stats.branch}, "
        f"dirty={stats.dirty}, TZ={stats.tz})"
    )


def _collect_stats(repo_root: Path) -> SnapshotStats:
    commit, branch, dirty = _git_info(repo_root)
    timestamp, tz = _timestamp()

    run_zero_start, run_zero_end, run_zero_len = _function_span(
        repo_root / "marsdisk" / "run_zero_d.py", "run_zero_d"
    )
    run_one_start, run_one_end, run_one_len = _function_span(
        repo_root / "marsdisk" / "run_one_d.py", "run_one_d"
    )
    schema_lines = _line_count(repo_root / "marsdisk" / "schema.py")
    schema_classes = _count_top_level_classes(repo_root / "marsdisk" / "schema.py")
    deprecated_count = _count_deprecated(repo_root)

    module_lines = {
        "collisions_smol.py": _line_count(repo_root / "marsdisk" / "physics" / "collisions_smol.py"),
        "sublimation.py": _line_count(repo_root / "marsdisk" / "physics" / "sublimation.py"),
        "tempdriver.py": _line_count(repo_root / "marsdisk" / "physics" / "tempdriver.py"),
        "supply.py": _line_count(repo_root / "marsdisk" / "physics" / "supply.py"),
        "psd.py": _line_count(repo_root / "marsdisk" / "physics" / "psd.py"),
    }

    test_counts = {
        "integration": _count_test_files(repo_root / "tests" / "integration"),
        "unit": _count_test_files(repo_root / "tests" / "unit"),
        "research": _count_test_files(repo_root / "tests" / "research"),
        "legacy": _count_test_files(repo_root / "tests" / "legacy"),
    }

    size_targets = {
        "run_zero_d.py": repo_root / "marsdisk" / "run_zero_d.py",
        "run_one_d.py": repo_root / "marsdisk" / "run_one_d.py",
        "schema.py": repo_root / "marsdisk" / "schema.py",
        "collisions_smol.py": repo_root / "marsdisk" / "physics" / "collisions_smol.py",
        "sublimation.py": repo_root / "marsdisk" / "physics" / "sublimation.py",
        "psd.py": repo_root / "marsdisk" / "physics" / "psd.py",
        "supply.py": repo_root / "marsdisk" / "physics" / "supply.py",
        "orchestrator.py": repo_root / "marsdisk" / "orchestrator.py",
        "writer.py": repo_root / "marsdisk" / "io" / "writer.py",
        "archive.py": repo_root / "marsdisk" / "io" / "archive.py",
        "constants.py": repo_root / "marsdisk" / "constants.py",
    }
    size_stats = {name: (_file_size(path), _line_count(path)) for name, path in size_targets.items()}

    return SnapshotStats(
        timestamp=timestamp,
        tz=tz,
        commit=commit,
        branch=branch,
        dirty=dirty,
        run_zero_start=run_zero_start,
        run_zero_end=run_zero_end,
        run_zero_len=run_zero_len,
        run_one_start=run_one_start,
        run_one_end=run_one_end,
        run_one_len=run_one_len,
        schema_lines=schema_lines,
        schema_classes=schema_classes,
        deprecated_count=deprecated_count,
        module_lines=module_lines,
        test_counts=test_counts,
        size_stats=size_stats,
    )


def _update_plan_text(text: str, stats: SnapshotStats) -> tuple[str, dict[str, set[str]]]:
    lines = text.splitlines()

    section: str | None = None
    in_code_block = False
    code_block_kind: str | None = None

    bool_flags: dict[str, bool] = {
        "snapshot": False,
        "run_zero": False,
        "run_one": False,
        "schema_table": False,
        "deprecated": False,
    }
    seen_flags: dict[str, set[str]] = {
        "modules": set(),
        "tests": set(),
        "sizes": set(),
    }

    updated_lines: list[str] = []
    for line in lines:
        stripped = line.strip()

        if line.startswith("### "):
            if line.startswith(SECTION_MONO_PREFIX):
                section = "mono"
            elif line.startswith(SECTION_SCHEMA_PREFIX):
                section = "schema"
            elif line.startswith(SECTION_DEPRECATED_PREFIX):
                section = "deprecated"
            elif line.startswith(SECTION_MODULES_PREFIX):
                section = "modules"
            else:
                section = None
        elif line.startswith("## "):
            section = None

        if stripped.startswith(CODEBLOCK_MARKER):
            in_code_block = not in_code_block
            code_block_kind = None

        updated = line

        if in_code_block and code_block_kind is None:
            if "tests/" in stripped:
                code_block_kind = "tests"
            elif "marsdisk/" in stripped:
                code_block_kind = "sizes"

        if "commit " in line and "dirty=" in line and "TZ=" in line and ":" in line:
            label = line.split(":", 1)[0]
            updated = _format_snapshot_line(label, stats)
            bool_flags["snapshot"] = True
        elif section == "mono" and line.startswith("| `run_zero_d.py`"):
            updated, ok = _replace_bold_number(updated, stats.run_zero_len)
            if not ok:
                raise RuntimeError("failed to update run_zero_d line count")
            updated, ok = _replace_range(updated, stats.run_zero_start, stats.run_zero_end)
            if not ok:
                raise RuntimeError("failed to update run_zero_d line range")
            bool_flags["run_zero"] = True
        elif section == "mono" and line.startswith("| `run_one_d.py`"):
            updated, ok = _replace_bold_number(updated, stats.run_one_len)
            if not ok:
                raise RuntimeError("failed to update run_one_d line count")
            updated, ok = _replace_range(updated, stats.run_one_start, stats.run_one_end)
            if not ok:
                raise RuntimeError("failed to update run_one_d line range")
            bool_flags["run_one"] = True
        elif section == "schema" and line.startswith("| `schema.py` |"):
            updated, ok = _replace_nth_number(updated, 1, stats.schema_lines)
            if not ok:
                raise RuntimeError("failed to update schema line count")
            updated, ok = _replace_nth_number(updated, 2, stats.schema_classes)
            if not ok:
                raise RuntimeError("failed to update schema class count")
            bool_flags["schema_table"] = True
        elif section == "deprecated" and "rg " in line and "deprecated" in line and "wc -l" in line:
            updated, ok = _replace_nth_number(updated, 1, stats.deprecated_count)
            if not ok:
                raise RuntimeError("failed to update deprecated count")
            bool_flags["deprecated"] = True
        elif section == "modules" and line.startswith("| `") and "` |" in line:
            for module, count in stats.module_lines.items():
                if f"`{module}`" in line:
                    updated, ok = _replace_nth_number(updated, 1, count)
                    if not ok:
                        raise RuntimeError(f"failed to update module count for {module}")
                    seen_flags["modules"].add(module)
                    break
        elif in_code_block and code_block_kind == "tests" and "integration/" in line:
            updated, ok = _replace_nth_number(updated, 1, stats.test_counts["integration"])
            if not ok:
                raise RuntimeError("failed to update integration test count")
            seen_flags["tests"].add("integration")
        elif in_code_block and code_block_kind == "tests" and "unit/" in line:
            updated, ok = _replace_nth_number(updated, 1, stats.test_counts["unit"])
            if not ok:
                raise RuntimeError("failed to update unit test count")
            seen_flags["tests"].add("unit")
        elif in_code_block and code_block_kind == "tests" and "research/" in line:
            updated, ok = _replace_nth_number(updated, 1, stats.test_counts["research"])
            if not ok:
                raise RuntimeError("failed to update research test count")
            seen_flags["tests"].add("research")
        elif in_code_block and code_block_kind == "tests" and "legacy/" in line:
            updated, ok = _replace_nth_number(updated, 1, stats.test_counts["legacy"])
            if not ok:
                raise RuntimeError("failed to update legacy test count")
            seen_flags["tests"].add("legacy")
        elif in_code_block and code_block_kind == "sizes" and "bytes" in line and "lines" in line:
            for name, (size, line_count) in stats.size_stats.items():
                if f"{name}" in line:
                    updated, ok = _replace_nth_number(updated, 1, size)
                    if not ok:
                        raise RuntimeError(f"failed to update size for {name}")
                    updated, ok = _replace_nth_number(updated, 2, line_count)
                    if not ok:
                        raise RuntimeError(f"failed to update line count for {name}")
                    seen_flags["sizes"].add(name)
                    break

        updated_lines.append(updated)

    if in_code_block:
        raise RuntimeError("unterminated code block detected in plan file")

    missing_modules = set(stats.module_lines) - seen_flags["modules"]
    if missing_modules:
        raise RuntimeError(f"missing module rows: {sorted(missing_modules)}")

    missing_tests = set(stats.test_counts) - seen_flags["tests"]
    if missing_tests:
        raise RuntimeError(f"missing test rows: {sorted(missing_tests)}")

    missing_sizes = set(stats.size_stats) - seen_flags["sizes"]
    if missing_sizes:
        raise RuntimeError(f"missing size rows: {sorted(missing_sizes)}")

    required_flags = ["snapshot", "run_zero", "run_one", "schema_table", "deprecated"]
    for flag in required_flags:
        if not bool_flags[flag]:
            raise RuntimeError(f"missing update for {flag}")

    return "\n".join(updated_lines) + "\n", seen_flags


def _diff_text(old: str, new: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def _print_summary(stats: SnapshotStats) -> None:
    print(f"snapshot: {stats.timestamp} {stats.tz} commit={stats.commit} branch={stats.branch} dirty={stats.dirty}")
    print(
        "run_zero_d: lines={0} range=L{1}{2}L{3}".format(
            stats.run_zero_len,
            stats.run_zero_start,
            EN_DASH,
            stats.run_zero_end,
        )
    )
    print(
        "run_one_d: lines={0} range=L{1}{2}L{3}".format(
            stats.run_one_len,
            stats.run_one_start,
            EN_DASH,
            stats.run_one_end,
        )
    )
    print(f"schema: lines={stats.schema_lines} classes={stats.schema_classes}")
    print(f"deprecated: {stats.deprecated_count}")
    print(
        "tests: integration={integration} unit={unit} research={research} legacy={legacy}".format(
            **stats.test_counts
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update maintainability snapshot values.")
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("docs/plan/20260102_maintainability_analysis.md"),
        help="Plan file to update.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if updates are needed; do not write.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a unified diff; do not write.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print snapshot summary to stdout.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    plan_path = (repo_root / args.plan).resolve()
    if not plan_path.exists():
        print(f"error: plan file not found: {plan_path}", file=sys.stderr)
        return 2
    if not plan_path.is_relative_to(repo_root):
        print(f"error: plan file must be within repo root: {plan_path}", file=sys.stderr)
        return 2

    stats = _collect_stats(repo_root)
    if args.verbose:
        _print_summary(stats)

    original = plan_path.read_text(encoding="utf-8")
    try:
        updated, _ = _update_plan_text(original, stats)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if original == updated:
        return 0

    if args.dry_run or args.check:
        diff = _diff_text(original, updated, plan_path)
        if diff:
            sys.stdout.write(diff)
        return 1 if args.check else 0

    plan_path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
