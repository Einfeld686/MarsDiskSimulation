#!/usr/bin/env python3
"""Generate Markdown patch templates for undocumented symbols."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE_PATH = Path(__file__).resolve().parent / "reports" / "coverage.json"
DEFAULT_SUGGESTION_DIR = Path(__file__).resolve().parent / "suggestions"
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent / "reports" / "suggestions_index.json"


@dataclass
class UnreferencedSymbol:
    """A symbol lacking documentation coverage."""

    file: str
    name: str
    lineno: int
    end_lineno: int
    kind: str


def load_unreferenced_symbols(path: Path) -> List[UnreferencedSymbol]:
    """Return unreferenced symbol data loaded from *path*."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("unreferenced", [])
    symbols: List[UnreferencedSymbol] = []
    for entry in entries:
        symbols.append(
            UnreferencedSymbol(
                file=entry["file"],
                name=entry["name"],
                lineno=int(entry["lineno"]),
                end_lineno=int(entry["end_lineno"]),
                kind=entry.get("kind", "function"),
            )
        )
    return symbols


def select_target_doc(file_path: str) -> str:
    """Choose a documentation file suited to *file_path*."""
    heuristics = [
        (re.compile(r"^marsdisk/grid\.py$"), "analysis/overview.md"),
        (re.compile(r"^marsdisk/physics/"), "analysis/run-recipes.md"),
        (re.compile(r"^marsdisk/io/"), "analysis/overview.md"),
        (re.compile(r"^marsdisk/schema\.py$"), "analysis/overview.md"),
    ]
    for pattern, doc in heuristics:
        if pattern.search(file_path):
            return doc
    return "analysis/run-recipes.md"


def build_patch_content(symbol: UnreferencedSymbol, doc_path: str) -> str:
    """Return a git-style patch template referencing *symbol*."""
    summary_line = (
        f"+根拠: [{symbol.file}:{symbol.lineno}–{symbol.end_lineno}] "
        f"— `{symbol.name}` の概要と使用箇所を追記"
    )
    rationale_line = (
        "+補足: 0D円盤シミュレーションでの役割と、関連する出力指標との"
        " つながりを1段落で説明してください。"
    )
    heading = f"+#### TODO: `{symbol.name}` を分析ドキュメントへ明示"
    lines = [
        f"--- a/{doc_path}",
        f"+++ b/{doc_path}",
        "@@",
        heading,
        summary_line,
        rationale_line,
        "+",
    ]
    return "\n".join(lines) + "\n"


def slugify(symbol: UnreferencedSymbol) -> str:
    """Create a filesystem-friendly slug for *symbol*."""
    base = f"{symbol.file.replace('/', '__').replace('.', '_')}"
    return f"{base}__{symbol.name}"


def emit_suggestions(
    symbols: Iterable[UnreferencedSymbol],
    suggestion_dir: Path,
) -> Dict[str, Dict[str, str]]:
    """Write patch templates and return an index."""
    suggestion_dir.mkdir(parents=True, exist_ok=True)
    index: Dict[str, Dict[str, str]] = {}
    for symbol in symbols:
        doc_path = select_target_doc(symbol.file)
        slug = slugify(symbol)
        filename = suggestion_dir / f"{slug}.mdpatch"
        content = build_patch_content(symbol, doc_path)
        filename.write_text(content, encoding="utf-8")
        rel_path = str(filename.relative_to(REPO_ROOT))
        index_key = f"{symbol.file}:{symbol.name}"
        index[index_key] = {
            "symbol": symbol.name,
            "file": symbol.file,
            "suggested_doc": doc_path,
            "patch": rel_path,
        }
    return index


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Create Markdown patch templates for undocumented symbols."
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=DEFAULT_COVERAGE_PATH,
        help="Path to coverage.json produced by rc_compare.py.",
    )
    parser.add_argument(
        "--suggestion-dir",
        type=Path,
        default=DEFAULT_SUGGESTION_DIR,
        help="Directory for generated .mdpatch files.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Path for the JSON index summarising suggestions.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    coverage_path = (
        args.coverage
        if args.coverage.is_absolute()
        else (Path(__file__).resolve().parent / args.coverage)
    ).resolve()
    suggestion_dir = (
        args.suggestion_dir
        if args.suggestion_dir.is_absolute()
        else (Path(__file__).resolve().parent / args.suggestion_dir)
    ).resolve()
    index_path = (
        args.index
        if args.index.is_absolute()
        else (Path(__file__).resolve().parent / args.index)
    ).resolve()

    if not coverage_path.exists():
        parser.error(f"Coverage file not found: {coverage_path}")

    symbols = load_unreferenced_symbols(coverage_path)
    index = emit_suggestions(symbols, suggestion_dir)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"[rc_anchor_suggestions] Generated {len(index)} suggestion templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
