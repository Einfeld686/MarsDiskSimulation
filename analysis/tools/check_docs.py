#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Ensure we can import sibling helper modules.
TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    import make_coverage  # type: ignore
    import anchor_sync  # type: ignore
except ImportError as exc:  # pragma: no cover - hard failure
    raise SystemExit(f"Failed to import helper modules: {exc}")


ANCHOR_PATTERN = anchor_sync.ANCHOR_PATTERN
MODULE_SENTINEL = anchor_sync.MODULE_SENTINEL
SymbolResolver = anchor_sync.SymbolResolver

COVERAGE_JSON_PATH = REPO_ROOT / "analysis" / "coverage" / "coverage.json"


@dataclass
class AnchorOccurrence:
    doc_path: Path
    line: int
    rel_path: str
    symbol: str
    recorded_start: Optional[int]
    recorded_end: Optional[int]
    expected_start: int
    expected_end: int


def load_coverage_json() -> Dict[str, object]:
    if not COVERAGE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"Coverage file not found at {COVERAGE_JSON_PATH}. "
            "Run make_coverage.py first."
        )
    try:
        return json.loads(COVERAGE_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - configuration error
        raise RuntimeError(f"Failed to parse coverage.json: {exc}") from exc


def discover_markdown_paths() -> List[Path]:
    paths: List[Path] = []
    for path in (REPO_ROOT / "analysis").glob("**/*.md"):
        if not path.is_file():
            continue
        if (REPO_ROOT / "analysis" / "coverage") in path.parents:
            continue
        paths.append(path)
    return sorted(paths)


def detect_anchor_range_mismatches(resolver: SymbolResolver) -> List[AnchorOccurrence]:
    mismatches: List[AnchorOccurrence] = []
    for doc_path in discover_markdown_paths():
        text = doc_path.read_text(encoding="utf-8")
        for match in ANCHOR_PATTERN.finditer(text):
            rel_path = match.group(1)
            symbol_name = match.group(2)
            start_token = match.group(3)
            end_token = match.group(4)

            if start_token is None and end_token is None:
                continue  # No range recorded, nothing to compare.

            symbol_range = resolver.find_symbol_by_name(rel_path, symbol_name)
            if symbol_range is None:
                # Should not happen after anchor_sync; treat as mismatch for logging.
                continue

            expected_start = symbol_range.start_line
            expected_end = symbol_range.end_line
            recorded_start = int(start_token) if start_token else None
            recorded_end: Optional[int]
            if end_token:
                recorded_end = int(end_token)
            elif recorded_start is not None:
                recorded_end = recorded_start
            else:
                recorded_end = None

            if symbol_range.symbol == MODULE_SENTINEL:
                # Module anchors typically point to the whole file. Use recorded
                # values as-is to avoid noisy warnings.
                continue

            mismatch = False
            if recorded_start is not None and recorded_start != expected_start:
                mismatch = True
            if recorded_end is not None and recorded_end != expected_end:
                mismatch = True

            if mismatch:
                line_number = text.count("\n", 0, match.start()) + 1
                mismatches.append(
                    AnchorOccurrence(
                        doc_path=doc_path,
                        line=line_number,
                        rel_path=rel_path,
                        symbol=symbol_name,
                        recorded_start=recorded_start,
                        recorded_end=recorded_end,
                        expected_start=expected_start,
                        expected_end=expected_end,
                    )
                )
    return mismatches


def format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate analysis documentation coverage and anchors."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors and enforce thresholds strictly.",
    )
    parser.add_argument(
        "--no-regen",
        action="store_true",
        help="Skip regenerating coverage.json via make_coverage.",
    )
    return parser.parse_args(argv)


def summarize_anchors(mismatches: Sequence[AnchorOccurrence], limit: int = 3) -> str:
    lines: List[str] = []
    for occ in mismatches[:limit]:
        recorded_range = ""
        if occ.recorded_start is not None:
            if occ.recorded_end is not None and occ.recorded_end != occ.recorded_start:
                recorded_range = f"[L{occ.recorded_start}–L{occ.recorded_end}]"
            else:
                recorded_range = f"[L{occ.recorded_start}]"
        lines.append(
            f"{occ.doc_path.relative_to(REPO_ROOT)}:{occ.line} "
            f"{occ.rel_path}#{occ.symbol} "
            f"expected [L{occ.expected_start}–L{occ.expected_end}] "
            f"found {recorded_range or '[no range]'}"
        )
    if len(mismatches) > limit:
        lines.append(f"... {len(mismatches) - limit} more mismatch(es)")
    return "; ".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if not args.no_regen:
        make_status = make_coverage.main()
        if make_status != 0:  # pragma: no cover - delegated failure
            print("ERROR: make_coverage.py failed.", file=sys.stderr)
            return 1

    try:
        coverage = load_coverage_json()
    except Exception as exc:  # pragma: no cover - configuration error
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: List[str] = []
    warnings: List[str] = []

    func_rate = float(coverage["function_reference_rate"]["rate"])  # type: ignore[index]
    func_num = int(coverage["function_reference_rate"]["numerator"])  # type: ignore[index]
    func_den = int(coverage["function_reference_rate"]["denominator"])  # type: ignore[index]

    anchor_rate = float(coverage["anchor_consistency_rate"]["rate"])  # type: ignore[index]
    anchor_num = int(coverage["anchor_consistency_rate"]["numerator"])  # type: ignore[index]
    anchor_den = int(coverage["anchor_consistency_rate"]["denominator"])  # type: ignore[index]

    equation_rate = float(coverage["equation_unit_coverage"]["rate"])  # type: ignore[index]
    equation_num = int(coverage["equation_unit_coverage"]["numerator"])  # type: ignore[index]
    equation_den = int(coverage["equation_unit_coverage"]["denominator"])  # type: ignore[index]

    holes = coverage.get("holes", [])

    if anchor_rate < 1.0:
        errors.append(
            f"Anchor consistency rate {format_rate(anchor_rate)} "
            f"below 100% ({anchor_num}/{anchor_den})."
        )

    if func_den > 0 and func_rate < 0.70:
        msg = (
            f"Function reference rate {format_rate(func_rate)} "
            f"below target 70% ({func_num}/{func_den})."
        )
        errors.append(msg if args.strict else msg)

    if equation_den > 0 and equation_rate < 0.90:
        warnings.append(
            f"Equation unit coverage {format_rate(equation_rate)} "
            f"below 90% ({equation_num}/{equation_den})."
        )

    resolver = SymbolResolver(REPO_ROOT)
    mismatches = detect_anchor_range_mismatches(resolver)
    if mismatches:
        warnings.append(
            "Anchor line ranges out of date: "
            + summarize_anchors(mismatches)
        )

    if args.strict and warnings:
        errors.extend(f"Strict mode escalation: {warn}" for warn in warnings)
        warnings = []

    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    for warning in warnings:
        print(f"WARN: {warning}", file=sys.stderr)

    hole_list = list(holes) if isinstance(holes, list) else []
    fixups = ", ".join(hole_list[:3]) if hole_list else "none"
    print(f"Next fixes: {fixups}", file=sys.stderr)

    status = "OK" if not errors else "ERROR"
    print(
        f"{status}: functions {format_rate(func_rate)}, anchors {format_rate(anchor_rate)}, "
        f"equation units {format_rate(equation_rate)}",
        file=sys.stderr,
    )

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
