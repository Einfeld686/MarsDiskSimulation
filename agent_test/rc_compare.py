#!/usr/bin/env python3
"""Compare documented references against discovered code symbols."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_PATH = Path(__file__).resolve().parent / "reports" / "ast_symbols.json"
DEFAULT_REF_PATH = Path(__file__).resolve().parent / "reports" / "doc_refs.json"
DEFAULT_COVERAGE_JSON = Path(__file__).resolve().parent / "reports" / "coverage.json"
DEFAULT_COVERAGE_MD = Path(__file__).resolve().parent / "reports" / "coverage_report.md"


@dataclass(frozen=True)
class Symbol:
    """Symbol definition extracted from the AST scan."""

    name: str
    file: str
    lineno: int
    end_lineno: int
    kind: str


@dataclass(frozen=True)
class DocRef:
    """Reference from documentation into the codebase."""

    file: str
    line_start: int
    line_end: int
    source_doc: str
    anchor: str | None


@dataclass
class CoverageResult:
    """Aggregated coverage information."""

    referenced: bool
    matching_docs: List[str]


def load_symbols(path: Path) -> List[Symbol]:
    """Load symbol definitions from *path*."""
    data = json.loads(path.read_text(encoding="utf-8"))
    symbols: List[Symbol] = []
    for entry in data.get("symbols", []):
        symbols.append(
            Symbol(
                name=entry["name"],
                file=entry["file"],
                lineno=int(entry["lineno"]),
                end_lineno=int(entry.get("end_lineno", entry["lineno"])),
                kind=entry.get("kind", "function"),
            )
        )
    return symbols


def load_doc_refs(path: Path) -> List[DocRef]:
    """Load documentation references from *path*."""
    data = json.loads(path.read_text(encoding="utf-8"))
    refs: List[DocRef] = []
    for entry in data.get("refs", []):
        refs.append(
            DocRef(
                file=entry["file"],
                line_start=int(entry["line_start"]),
                line_end=int(entry["line_end"]),
                source_doc=entry.get("source_doc", ""),
                anchor=entry.get("anchor"),
            )
        )
    return refs


def references_by_file(refs: Iterable[DocRef]) -> Dict[str, List[DocRef]]:
    """Group documentation references by target file."""
    grouped: Dict[str, List[DocRef]] = {}
    for ref in refs:
        grouped.setdefault(ref.file, []).append(ref)
    return grouped


def symbol_matches_reference(symbol: Symbol, ref: DocRef) -> bool:
    """Return True if *ref* overlaps *symbol*'s line span."""
    if symbol.file != ref.file:
        return False
    return not (ref.line_end < symbol.lineno or ref.line_start > symbol.end_lineno)


def filter_symbols(symbols: Iterable[Symbol], *, strict: bool) -> List[Symbol]:
    """Filter symbols according to visibility and interest."""
    filtered: List[Symbol] = []
    for symbol in symbols:
        if not strict and symbol.name.startswith("_"):
            continue
        filtered.append(symbol)
    return filtered


def compute_coverage(
    symbols: List[Symbol],
    refs_by_file: Dict[str, List[DocRef]],
    *,
    strict: bool,
    include_classes: bool,
) -> Dict[str, CoverageResult]:
    """Compute documented coverage for each symbol."""
    results: Dict[str, CoverageResult] = {}
    for symbol in filter_symbols(symbols, strict=strict):
        if symbol.kind not in {"function", "async_function"} and not include_classes:
            continue
        refs = refs_by_file.get(symbol.file, [])
        matching_docs = sorted(
            {ref.source_doc for ref in refs if symbol_matches_reference(symbol, ref)}
        )
        results[f"{symbol.file}:{symbol.name}"] = CoverageResult(
            referenced=bool(matching_docs),
            matching_docs=list(matching_docs),
        )
    return results


def aggregate_metrics(
    symbols: List[Symbol],
    coverage: Dict[str, CoverageResult],
    strict: bool,
) -> Dict[str, object]:
    """Aggregate coverage numbers by kind and file."""
    filtered_symbols = filter_symbols(symbols, strict=strict)
    function_symbols = [s for s in filtered_symbols if s.kind in {"function", "async_function"}]
    class_symbols = [s for s in filtered_symbols if s.kind == "class"]

    referenced_function_count = sum(
        1
        for symbol in function_symbols
        if coverage.get(f"{symbol.file}:{symbol.name}", CoverageResult(False, [])).referenced
    )

    function_reference_rate = (
        referenced_function_count / len(function_symbols) if function_symbols else 1.0
    )

    per_file: List[Dict[str, object]] = []
    for file in sorted({s.file for s in filtered_symbols}):
        file_functions = [s for s in function_symbols if s.file == file]
        file_classes = [s for s in class_symbols if s.file == file]
        referenced_file_functions = [
            s
            for s in file_functions
            if coverage.get(f"{s.file}:{s.name}", CoverageResult(False, [])).referenced
        ]
        rate = len(referenced_file_functions) / len(file_functions) if file_functions else 1.0
        per_file.append(
            {
                "file": file,
                "function_total": len(file_functions),
                "function_referenced": len(referenced_file_functions),
                "function_reference_rate": rate,
                "class_total": len(file_classes),
            }
        )

    unreferenced_symbols = [
        {
            "file": symbol.file,
            "name": symbol.name,
            "lineno": symbol.lineno,
            "end_lineno": symbol.end_lineno,
            "kind": symbol.kind,
        }
        for symbol in function_symbols
        if not coverage.get(f"{symbol.file}:{symbol.name}", CoverageResult(False, [])).referenced
    ]

    return {
        "function_reference_rate": function_reference_rate,
        "function_total": len(function_symbols),
        "function_referenced": referenced_function_count,
        "class_total": len(class_symbols),
        "per_file": per_file,
        "unreferenced": sorted(
            unreferenced_symbols,
            key=lambda entry: (entry["file"], entry["lineno"]),
        ),
}


def render_markdown_report(metrics: Dict[str, object], output: Path) -> None:
    """Create a human-readable markdown coverage report."""
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    rate = metrics["function_reference_rate"]
    percent = f"{rate * 100:.1f}"
    lines.append(f"# Documentation Coverage\n")
    lines.append(f"- Function reference rate: {percent}% "
                 f"({metrics['function_referenced']}/{metrics['function_total']})\n")
    lines.append("## Module Coverage\n")
    for entry in metrics["per_file"]:
        lines.append(
            f"- `{entry['file']}`: {entry['function_reference_rate']*100:.1f}% "
            f"({entry['function_referenced']}/{entry['function_total']})"
        )
    lines.append("\n## Top Coverage Gaps\n")
    unreferenced = metrics["unreferenced"][:10]
    if not unreferenced:
        lines.append("- All tracked functions are referenced.\n")
    else:
        for entry in unreferenced:
            lines.append(
                f"- `{entry['file']}`:{entry['lineno']} "
                f"`{entry['name']}` (lines {entry['lineno']}–{entry['end_lineno']})"
            )
    output.write_text("\n".join(lines), encoding="utf-8")


def write_json_report(metrics: Dict[str, object], output: Path) -> None:
    """Persist metrics to JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Compare documentation anchors with discovered code symbols."
    )
    parser.add_argument(
        "--symbols",
        type=Path,
        default=DEFAULT_SYMBOL_PATH,
        help="Path to ast_symbols.json (default: %(default)s).",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=DEFAULT_REF_PATH,
        help="Path to doc_refs.json (default: %(default)s).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_COVERAGE_JSON,
        help="Where to write the coverage JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=DEFAULT_COVERAGE_MD,
        help="Where to write the coverage Markdown (default: %(default)s).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Count private symbols (names starting with '_').",
    )
    parser.add_argument(
        "--include-classes",
        action="store_true",
        help="Include classes when computing coverage statistics.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Fail if function reference rate is below this threshold (0-1).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    symbol_path = (
        args.symbols
        if args.symbols.is_absolute()
        else (Path(__file__).resolve().parent / args.symbols)
    ).resolve()
    reference_path = (
        args.references
        if args.references.is_absolute()
        else (Path(__file__).resolve().parent / args.references)
    ).resolve()
    json_path = (
        args.output_json
        if args.output_json.is_absolute()
        else (Path(__file__).resolve().parent / args.output_json)
    ).resolve()
    markdown_path = (
        args.output_markdown
        if args.output_markdown.is_absolute()
        else (Path(__file__).resolve().parent / args.output_markdown)
    ).resolve()

    symbols = load_symbols(symbol_path)
    refs = load_doc_refs(reference_path)
    coverage_map = compute_coverage(
        symbols,
        references_by_file(refs),
        strict=args.strict,
        include_classes=args.include_classes,
    )
    metrics = aggregate_metrics(symbols, coverage_map, strict=args.strict)

    write_json_report(metrics, json_path)
    render_markdown_report(metrics, markdown_path)
    print(
        f"[rc_compare] Function reference rate: "
        f"{metrics['function_reference_rate']*100:.1f}% "
        f"({metrics['function_referenced']}/{metrics['function_total']})"
    )

    if args.fail_under is not None and metrics["function_reference_rate"] < args.fail_under:
        print(
            f"[rc_compare] FAIL: rate {metrics['function_reference_rate']:.3f} "
            f"is below threshold {args.fail_under:.3f}"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
