#!/usr/bin/env python3
"""Execute the reference coverage toolchain end-to-end."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence


SUITE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SUITE_DIR / "reports"


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Run rc_scan_ast → rc_scan_docs → rc_compare → rc_root_cause_probe → rc_anchor_suggestions."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Include private symbols when computing coverage.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Fail if function coverage is below this threshold (propagated to rc_compare).",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Produce a compact summary emphasising JSON artefacts.",
    )
    return parser


def run_step(script: str, extra_args: Sequence[str]) -> subprocess.CompletedProcess:
    """Invoke *script* located in the suite directory."""
    script_path = SUITE_DIR / script
    argv = [sys.executable, str(script_path), *extra_args]
    print(f"[rc_run_all] Running {' '.join(argv)}")
    result = subprocess.run(argv, capture_output=False, check=False)
    if result.returncode != 0:
        print(f"[rc_run_all] Step {script} exited with code {result.returncode}")
    return result


def load_json(path: Path) -> Dict[str, object]:
    """Load JSON content if the file exists."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_summary(
    steps: Dict[str, int],
    coverage: Dict[str, object],
    fail_under: float | None,
    json_only: bool,
) -> None:
    """Write reports/summary.md summarising the run."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPORTS_DIR / "summary.md"
    lines: List[str] = ["# RC Suite Summary", ""]
    lines.append("## Step Status")
    for name, code in steps.items():
        status = "OK" if code == 0 else f"FAILED ({code})"
        lines.append(f"- {name}: {status}")
    lines.append("")

    if coverage:
        rate = float(coverage.get("function_reference_rate", 0.0))
        numerator = coverage.get("function_referenced", 0)
        denominator = coverage.get("function_total", 0)
        lines.append("## Coverage")
        lines.append(
            f"- Function reference rate: {rate*100:.1f}% ({numerator}/{denominator})"
        )
        if fail_under is not None:
            verdict = "met" if rate >= fail_under else "below"
            lines.append(f"- Threshold {fail_under:.2f}: {verdict}")
        lines.append("- Top gaps:")
        top_gaps = coverage.get("unreferenced", [])[:5]
        if top_gaps:
            for entry in top_gaps:
                lines.append(
                    f"  - `{entry['file']}`:{entry['lineno']} `{entry['name']}`"
                )
        else:
            lines.append("  - None")
        lines.append("")

    lines.append("## Artefacts")
    artefacts = [
        "reports/ast_symbols.json",
        "reports/doc_refs.json",
        "reports/coverage.json",
        "reports/coverage_report.md",
        "reports/root_cause_probe.md",
        "reports/suggestions_index.json",
        "reports/summary.md",
    ]
    for item in artefacts:
        lines.append(f"- {item}")
    if not json_only:
        lines.append("")
        lines.append("Generated suggestions reside under `suggestions/`.")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[rc_run_all] Summary written to {summary_path}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    steps: Dict[str, int] = {}

    ast_args: List[str] = []
    if args.strict:
        ast_args.append("--include-private")
    steps["rc_scan_ast.py"] = run_step("rc_scan_ast.py", ast_args).returncode

    steps["rc_scan_docs.py"] = run_step("rc_scan_docs.py", []).returncode

    compare_args: List[str] = []
    if args.strict:
        compare_args.append("--strict")
    if args.fail_under is not None:
        compare_args.extend(["--fail-under", str(args.fail_under)])
    steps["rc_compare.py"] = run_step("rc_compare.py", compare_args).returncode

    steps["rc_root_cause_probe.py"] = run_step("rc_root_cause_probe.py", []).returncode

    steps["rc_anchor_suggestions.py"] = run_step("rc_anchor_suggestions.py", []).returncode

    coverage = load_json(REPORTS_DIR / "coverage.json")
    render_summary(steps, coverage, args.fail_under, args.json_only)

    exit_code = max(steps.values(), default=0)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
