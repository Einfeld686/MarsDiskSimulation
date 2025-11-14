#!/usr/bin/env python3
"""Run analysis document tests and print a simple health bar."""
from __future__ import annotations

import sys
from glob import glob
from typing import Dict, List

import pytest

DEFAULT_PATTERN = "tests/test_analysis_*"
BAR_WIDTH = 24


class SummaryPlugin:
    """Collect terminal summary stats from pytest."""

    def __init__(self) -> None:
        self.stats: Dict[str, int] = {}

    def pytest_terminal_summary(self, terminalreporter, exitstatus) -> None:  # type: ignore[override]
        counts: Dict[str, int] = {}
        for key in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
            reports = terminalreporter.stats.get(key, [])
            counts[key] = len(reports)
        self.stats = counts


def _build_args(argv: List[str]) -> List[str]:
    user_args = argv[1:]
    has_positional = any(not arg.startswith("-") for arg in user_args)
    final_args: List[str] = []
    if has_positional:
        final_args.extend(user_args)
    else:
        final_args.append(DEFAULT_PATTERN)
        final_args.extend(user_args)
    if not any(arg in ("-q", "-qq", "--quiet") for arg in final_args):
        final_args.append("-q")
    return final_args


def _expand_globs(args: List[str]) -> List[str]:
    expanded: List[str] = []
    for item in args:
        if item.startswith("-"):
            expanded.append(item)
            continue
        matches = sorted(glob(item))
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(item)
    return expanded


def _render_bar(ratio: float) -> str:
    width = BAR_WIDTH
    filled = int(round(max(0.0, min(1.0, ratio)) * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _format_counts(stats: Dict[str, int]) -> str:
    parts = []
    for key in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        value = stats.get(key, 0)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else "no collected tests"


def main(argv: List[str]) -> int:
    args = _expand_globs(_build_args(argv))
    plugin = SummaryPlugin()
    print("Running pytest", " ".join(args))
    exit_code = pytest.main(args, plugins=[plugin])

    stats = plugin.stats or {}
    passed = stats.get("passed", 0)
    xfailed = stats.get("xfailed", 0)
    failed = stats.get("failed", 0)
    errors = stats.get("error", 0)
    xpassed = stats.get("xpassed", 0)
    skipped = stats.get("skipped", 0)

    healthy = passed + xfailed
    problematic = failed + errors + xpassed
    effective_total = healthy + problematic
    ratio = healthy / effective_total if effective_total else 1.0

    bar = _render_bar(ratio)
    details = _format_counts(stats)
    print()
    print(f"analysis-doc-tests summary: {bar} {ratio*100:.1f}% healthy")
    print(f"  breakdown: {details or 'n/a'} (skipped={skipped})")
    if problematic:
        print("  WARNING: Issues detected; see pytest output above.")
    else:
        print("  All tracked analysis doc tests passed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
