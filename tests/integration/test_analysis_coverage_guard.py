"""Ensure analysis coverage guard passes on every test run."""
from __future__ import annotations

from tools import coverage_guard


def test_analysis_coverage_guard() -> None:
    """Run ci_guard_analysis via the coverage guard bridge."""

    exit_code = coverage_guard.run_guard(fail_under=0.75, require_clean_anchors=True)
    assert exit_code == 0, "analysis coverage fell below the enforced threshold"
