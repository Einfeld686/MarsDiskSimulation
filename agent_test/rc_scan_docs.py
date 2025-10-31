#!/usr/bin/env python3
"""Extract documentation anchors that reference marsdisk Python sources."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATHS = [
    "analysis/equations.md",
    "analysis/overview.md",
    "analysis/run-recipes.md",
    "analysis/sinks_callgraph.md",
    "analysis/AI_USAGE.md",
    "analysis/inventory.json",
]
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "reports" / "doc_refs.json"

COLON_PATTERN = re.compile(
    r"\[(marsdisk/[^\]:]+\.py):(\d+)(?:[–-](\d+))?\]"
)
HASH_PATTERN = re.compile(
    r"\[(marsdisk/[^\]:]+\.py)#([^\s\[]+)\s+\[L(\d+)(?:[–-]L?(\d+))?\]\]"
)


@dataclass(frozen=True)
class DocReference:
    """Reference extracted from an analysis document."""

    file: str
    line_start: int
    line_end: int
    source_doc: str
    anchor: str | None


def read_document(path: Path) -> str:
    """Return the UTF-8 content of *path*."""
    return path.read_text(encoding="utf-8")


def parse_references(text: str, doc_path: Path) -> Tuple[List[DocReference], List[Dict[str, str]]]:
    """Parse *text* for code references, returning references and issues."""
    refs: List[DocReference] = []
    issues: List[Dict[str, str]] = []
    seen: set[Tuple[str, int, int]] = set()

    for match in COLON_PATTERN.finditer(text):
        file_path = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3) or match.group(2))
        anchor = None
        refs, issues, seen = _register_reference(
            refs, issues, seen, file_path, start, end, doc_path, anchor
        )

    for match in HASH_PATTERN.finditer(text):
        file_path = match.group(1)
        anchor = match.group(2)
        start = int(match.group(3))
        end_text = match.group(4)
        end = int(end_text) if end_text else start
        refs, issues, seen = _register_reference(
            refs, issues, seen, file_path, start, end, doc_path, anchor
        )

    return refs, issues


def _register_reference(
    refs: List[DocReference],
    issues: List[Dict[str, str]],
    seen: set[Tuple[str, int, int]],
    file_path: str,
    start: int,
    end: int,
    doc_path: Path,
    anchor: str | None,
) -> Tuple[List[DocReference], List[Dict[str, str]], set[Tuple[str, int, int]]]:
    key = (file_path, start, end)
    if end < start:
        issues.append(
            {
                "type": "reverse_range",
                "message": f"line range reversed: {file_path}:{start}–{end}",
                "doc": str(doc_path.relative_to(REPO_ROOT)),
            }
        )
    if key in seen:
        issues.append(
            {
                "type": "duplicate_reference",
                "message": f"duplicate reference: {file_path}:{start}–{end}",
                "doc": str(doc_path.relative_to(REPO_ROOT)),
            }
        )
    seen.add(key)
    refs.append(
        DocReference(
            file=file_path,
            line_start=min(start, end),
            line_end=max(start, end),
            source_doc=str(doc_path.relative_to(REPO_ROOT)),
            anchor=anchor,
        )
    )
    return refs, issues, seen


def normalise_doc_paths(paths: Iterable[str]) -> List[Path]:
    """Convert CLI doc path arguments to absolute Path objects."""
    resolved: List[Path] = []
    for item in paths:
        path = (REPO_ROOT / item).resolve() if not Path(item).is_absolute() else Path(item)
        if not path.exists():
            continue
        resolved.append(path)
    return resolved


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Scan analysis documents for code anchor references."
    )
    parser.add_argument(
        "--docs",
        nargs="*",
        default=DEFAULT_DOC_PATHS,
        help="Document paths to scan (default: a curated analysis list).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write the JSON report (default: %(default)s).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    doc_paths = normalise_doc_paths(args.docs)
    if not doc_paths:
        parser.error("No document paths resolved.")

    all_refs: List[DocReference] = []
    all_issues: List[Dict[str, str]] = []
    for doc_path in doc_paths:
        text = read_document(doc_path)
        refs, issues = parse_references(text, doc_path)
        all_refs.extend(refs)
        all_issues.extend(issues)

    output_path = args.output if args.output.is_absolute() else (Path(__file__).resolve().parent / args.output)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "doc_paths": [str(path.relative_to(REPO_ROOT)) for path in doc_paths],
        "reference_count": len(all_refs),
        "refs": [
            {
                "file": ref.file,
                "line_start": ref.line_start,
                "line_end": ref.line_end,
                "source_doc": ref.source_doc,
                "anchor": ref.anchor,
            }
            for ref in all_refs
        ],
        "issues": all_issues,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[rc_scan_docs] Wrote {len(all_refs)} references to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
