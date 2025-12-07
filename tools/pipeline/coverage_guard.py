"""Bridge new coverage format to ci_guard_analysis."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Sequence

from agent_test import ci_guard_analysis

# tools/pipeline -> tools -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE = REPO_ROOT / "analysis" / "coverage" / "coverage.json"
DEFAULT_REFS = REPO_ROOT / "analysis" / "doc_refs.json"
DEFAULT_INVENTORY = REPO_ROOT / "analysis" / "inventory.json"


def _load_extended_coverage(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))

    def _detail(entry: Any) -> Dict[str, float]:
        if isinstance(entry, dict):
            return {
                "rate": float(entry.get("rate", 0.0)),
                "numerator": float(entry.get("numerator", 0.0)),
                "denominator": float(entry.get("denominator", 0.0)),
            }
        rate = float(entry or 0.0)
        return {"rate": rate, "numerator": rate, "denominator": 1.0}

    func = _detail(data.get("function_reference_rate"))
    anchor = _detail(data.get("anchor_consistency_rate"))
    equation = _detail(data.get("equation_unit_coverage"))
    sinks_flag = bool(data.get("sinks_callgraph_documented", False))

    payload: Dict[str, Any] = {
        "function_reference_rate": func["rate"],
        "function_referenced": int(func["numerator"]),
        "function_total": int(func["denominator"]),
        "anchor_consistency_rate": {"rate": anchor["rate"]},
        "anchor_resolved": int(anchor["numerator"]),
        "anchor_total": int(anchor["denominator"]),
        "invalid_anchor_count": int(data.get("invalid_anchor_count", 0)),
        "duplicate_anchor_count": int(data.get("duplicate_anchor_count", 0)),
        "top_gaps": list(data.get("holes", []) or []),
        "per_file": list(data.get("per_file", []) or []),
        "equation_unit_coverage": {
            "rate": equation["rate"],
            "numerator": int(equation["numerator"]),
            "denominator": int(equation["denominator"]),
        },
        "sinks_callgraph_documented": sinks_flag,
    }
    return payload


def run_guard(
    *,
    coverage_source: Path = DEFAULT_COVERAGE,
    refs_path: Path = DEFAULT_REFS,
    inventory_path: Path = DEFAULT_INVENTORY,
    fail_under: float = 0.75,
    require_clean_anchors: bool = True,
    equation_fail_under: float = 0.25,
    require_sinks_callgraph: bool = True,
) -> int:
    payload = _load_extended_coverage(coverage_source)
    with tempfile.TemporaryDirectory(prefix="coverage_guard_") as tmpdir:
        tmp_path = Path(tmpdir) / "coverage_guard.json"
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        args = [
            "--coverage",
            str(tmp_path),
            "--refs",
            str(refs_path),
            "--inventory",
            str(inventory_path),
            "--fail-under",
            str(fail_under),
        ]
        if require_clean_anchors:
            args.append("--require-clean-anchors")
        exit_code = ci_guard_analysis.main(args)

    equation_info = payload.get("equation_unit_coverage", {}) or {}
    equation_rate = float(equation_info.get("rate", 0.0))
    equation_denominator = int(equation_info.get("denominator", 0))
    sinks_flag = bool(payload.get("sinks_callgraph_documented", False))

    failures: List[str] = []
    if equation_denominator and equation_rate < equation_fail_under:
        failures.append(
            f"equation unit coverage {equation_rate:.3f} fell below threshold {equation_fail_under:.3f}"
        )
    if require_sinks_callgraph and not sinks_flag:
        failures.append("sinks callgraph reference chain missing required anchors")

    if failures:
        for msg in failures:
            print(f"[coverage_guard] {msg}")
        if exit_code == 0:
            return 1
    return exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ci_guard_analysis against the new coverage format.")
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE, help="Path to analysis coverage JSON.")
    parser.add_argument("--refs", type=Path, default=DEFAULT_REFS, help="Path to analysis/doc_refs.json.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY, help="Path to analysis/inventory.json.")
    parser.add_argument("--fail-under", type=float, default=0.75, help="Minimum acceptable function reference rate.")
    parser.add_argument(
        "--no-clean-anchors",
        action="store_true",
        help="Disable the clean-anchor requirement (default: enforce).",
    )
    parser.add_argument(
        "--equation-fail-under",
        type=float,
        default=0.25,
        help="Minimum acceptable equation unit coverage rate (default: 0.25).",
    )
    parser.add_argument(
        "--allow-missing-sinks-callgraph",
        action="store_true",
        help="Allow missing sinks callgraph anchors without failing the guard.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return run_guard(
        coverage_source=args.coverage,
        refs_path=args.refs,
        inventory_path=args.inventory,
        fail_under=args.fail_under,
        require_clean_anchors=not args.no_clean_anchors,
        equation_fail_under=args.equation_fail_under,
        require_sinks_callgraph=not args.allow_missing_sinks_callgraph,
    )


if __name__ == "__main__":
    raise SystemExit(main())
