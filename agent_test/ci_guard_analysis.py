#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE_PATH = REPO_ROOT / "analysis" / "coverage.json"
DEFAULT_REFS_PATH = REPO_ROOT / "analysis" / "doc_refs.json"
DEFAULT_INVENTORY_PATH = REPO_ROOT / "analysis" / "inventory.json"


@dataclass
class CoverageSnapshot:
    function_referenced: int
    function_total: int
    function_rate: float
    anchor_rate: float
    invalid_anchor_count: int
    duplicate_anchor_count: int
    top_gaps: List[str]
    per_file_unreferenced: List[Tuple[str, str]]


def load_coverage(path: Path) -> CoverageSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    rate = float(data.get("function_reference_rate", 0.0))
    referenced = int(data.get("function_referenced", 0))
    total = int(data.get("function_total", 0))

    anchor_info = data.get("anchor_consistency_rate", {}) or {}
    anchor_rate = float(anchor_info.get("rate", 1.0))
    invalid_anchor_count = int(data.get("invalid_anchor_count", 0))
    duplicate_anchor_count = int(data.get("duplicate_anchor_count", 0))

    top_gaps = list(data.get("top_gaps", []) or [])
    per_file_entries = data.get("per_file", []) or []
    per_file_unreferenced: List[Tuple[str, str]] = []
    for entry in per_file_entries:
        file_path = entry.get("file_path")
        if not file_path:
            continue
        for symbol in entry.get("unreferenced", []) or []:
            per_file_unreferenced.append((file_path, symbol))

    return CoverageSnapshot(
        function_referenced=referenced,
        function_total=total,
        function_rate=rate,
        anchor_rate=anchor_rate,
        invalid_anchor_count=invalid_anchor_count,
        duplicate_anchor_count=duplicate_anchor_count,
        top_gaps=top_gaps,
        per_file_unreferenced=per_file_unreferenced,
    )


def resolve_path(candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail CI when analysis coverage drops below the requested threshold."
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=DEFAULT_COVERAGE_PATH,
        help="Path to analysis/coverage.json (default: analysis/coverage.json).",
    )
    parser.add_argument(
        "--refs",
        type=Path,
        default=DEFAULT_REFS_PATH,
        help="Path to analysis/doc_refs.json (default: analysis/doc_refs.json).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY_PATH,
        help="Path to analysis/inventory.json (default: analysis/inventory.json).",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        required=True,
        help="Minimum acceptable function reference rate (0-1).",
    )
    parser.add_argument(
        "--require-clean-anchors",
        action="store_true",
        help="Fail if anchor consistency is below unity or invalid anchors are present.",
    )
    parser.add_argument(
        "--show-top",
        type=int,
        default=5,
        help="Number of missing functions to list when failing (default: 5).",
    )
    return parser


def iter_missing(snapshot: CoverageSnapshot) -> Iterable[str]:
    yielded: set[str] = set()
    for item in snapshot.top_gaps:
        if item and item not in yielded:
            yielded.add(item)
            yield item
    for file_path, symbol in snapshot.per_file_unreferenced:
        key = f"{file_path}#{symbol}"
        if key not in yielded:
            yielded.add(key)
            yield key


def _load_inventory_records(path: Path) -> List[Tuple[str, str, int, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records: List[Tuple[str, str, int, int]] = []
    for entry in data:
        file_path = entry.get("file_path")
        symbol = entry.get("symbol")
        if not file_path or not symbol:
            continue
        line_no = int(entry.get("line_no", 0))
        end_line = int(entry.get("end_line", line_no))
        if end_line < line_no:
            end_line = line_no
        records.append((file_path, symbol, line_no, end_line))
    return records


def find_invalid_anchors(refs_path: Path, inventory_path: Path) -> List[str]:
    if not refs_path.exists() or not inventory_path.exists():
        return []
    refs = json.loads(refs_path.read_text(encoding="utf-8"))
    inventory_records = _load_inventory_records(inventory_path)
    symbol_index = {(file_path, symbol) for file_path, symbol, _, _ in inventory_records}
    span_index: Dict[str, List[Tuple[int, int, str]]] = {}
    for file_path, symbol, start, end in inventory_records:
        span_index.setdefault(file_path, []).append((start, end, symbol))

    invalid: List[str] = []

    for anchor in refs.get("symbol_anchors", []) or []:
        target = anchor.get("target_path")
        symbol = anchor.get("symbol")
        doc_path = anchor.get("doc_path", "?")
        if not target or not symbol:
            continue
        if (target, symbol) not in symbol_index:
            invalid.append(f"{doc_path}: {target}#{symbol}")

    for anchor in refs.get("line_anchors", []) or []:
        target = anchor.get("target_path")
        start = int(anchor.get("line_start", 0))
        end = int(anchor.get("line_end", start))
        doc_path = anchor.get("doc_path", "?")
        spans = span_index.get(target, [])
        matched = False
        for span_start, span_end, symbol in spans:
            if span_start <= start <= span_end and span_start <= end <= span_end:
                matched = True
                break
        if not matched:
            invalid.append(f"{doc_path}: {target}:{start}-{end}")

    return invalid


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    coverage_path = resolve_path(args.coverage)
    if not coverage_path.exists():
        print(f"[ci_guard_analysis] coverage file not found: {coverage_path}")
        return 2
    snapshot = load_coverage(coverage_path)
    refs_path = resolve_path(args.refs)
    inventory_path = resolve_path(args.inventory)

    rate = snapshot.function_rate
    referenced = snapshot.function_referenced
    total = snapshot.function_total
    anchor_rate = snapshot.anchor_rate
    invalid_count = snapshot.invalid_anchor_count
    duplicate_count = snapshot.duplicate_anchor_count

    print(
        "[ci_guard_analysis] "
        f"rate={rate:.3f} ({referenced}/{total}) "
        f"threshold={args.fail_under:.3f} "
        f"anchors={anchor_rate:.3f} invalid={invalid_count} duplicate={duplicate_count}"
    )

    fail = False
    invalid_anchors: List[str] = []
    if args.require_clean_anchors and (anchor_rate < 1.0 or invalid_count > 0):
        print("[ci_guard_analysis] FAIL: anchor consistency below expectations.")
        invalid_anchors = find_invalid_anchors(refs_path, inventory_path)
        for entry in invalid_anchors[: args.show_top]:
            print(f"  ! {entry}")
        fail = True

    if rate < args.fail_under:
        print("[ci_guard_analysis] FAIL: function reference rate below threshold.")
        missing = list(iter_missing(snapshot))
        if missing:
            limit = max(0, args.show_top)
            view = missing if limit == 0 else missing[:limit]
            for entry in view:
                print(f"  - {entry}")
        fail = True

    if fail:
        return 2

    print("[ci_guard_analysis] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
