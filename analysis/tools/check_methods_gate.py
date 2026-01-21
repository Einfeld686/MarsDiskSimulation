#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_METHODS_PATH = REPO_ROOT / "analysis" / "thesis" / "methods.md"

TEX_EXCLUDE_START = "<!-- TEX_EXCLUDE_START -->"
TEX_EXCLUDE_END = "<!-- TEX_EXCLUDE_END -->"


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    pattern: str
    snippet: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check that the thesis Methods chapter (excluding TEX_EXCLUDE blocks) "
            "does not contain internal-doc references or OS-dependent operations."
        )
    )
    parser.add_argument(
        "--methods",
        type=Path,
        default=DEFAULT_METHODS_PATH,
        help=f"Path to merged methods.md (default: {DEFAULT_METHODS_PATH})",
    )
    return parser.parse_args(argv)


def strip_tex_exclude_blocks(text: str) -> str:
    lines: List[str] = []
    in_exclude = False
    for line in text.splitlines():
        if TEX_EXCLUDE_START in line:
            in_exclude = True
            continue
        if TEX_EXCLUDE_END in line:
            in_exclude = False
            continue
        if in_exclude:
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def strip_html_comments(text: str) -> str:
    """Drop HTML comment blocks (e.g., implementation notes) from the scan target."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def iter_findings(path: Path, text: str, patterns: Iterable[str]) -> List[Finding]:
    compiled = [(pattern, re.compile(pattern)) for pattern in patterns]
    findings: List[Finding] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern, regex in compiled:
            if regex.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line=idx,
                        pattern=pattern,
                        snippet=line.strip(),
                    )
                )
    return findings


def require_substrings(text: str, required: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for token in required:
        if token not in text:
            missing.append(token)
    return missing


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    methods_path: Path = args.methods
    if not methods_path.exists():
        print(f"ERROR: methods file not found: {methods_path}", file=sys.stderr)
        return 1

    raw_text = methods_path.read_text(encoding="utf-8")
    text = strip_html_comments(strip_tex_exclude_blocks(raw_text))

    banned_patterns = [
        r"\banalysis/",
        r"\brun_sweep\.cmd\b",
        r"\bDocSync\b",
        r"\bmake\s+analysis-sync\b",
        r"\bmake\s+analysis-doc-tests\b",
        r"\bpytest\b",
        r"\bFORCE_STREAMING_OFF\b",
        r"\bIO_STREAMING\b",
        r"\bSKIP_PREFLIGHT\b",
        r"\bHOOKS_ENABLE\b",
        r"\bscripts/runsets/",
    ]

    findings = iter_findings(methods_path, text, banned_patterns)

    required_tokens = [
        "### 1.2 研究対象と基本仮定",
        "### 4.2 数値解法と停止条件",
        "### 5.1 出力と検証",
        r"\label{eq:smoluchowski}",
        r"\label{eq:mass_budget_definition}",
        r"\label{tab:validation_criteria}",
    ]
    missing = require_substrings(text, required_tokens)

    if not findings and not missing:
        return 0

    if findings:
        print("ERROR: banned references found in Methods (TEX_EXCLUDE stripped):", file=sys.stderr)
        for occ in findings[:20]:
            rel = occ.path.relative_to(REPO_ROOT)
            print(
                f"  - {rel}:{occ.line} matches /{occ.pattern}/: {occ.snippet}",
                file=sys.stderr,
            )
        if len(findings) > 20:
            print(f"  ... {len(findings) - 20} more", file=sys.stderr)

    if missing:
        print("ERROR: required content markers missing in Methods:", file=sys.stderr)
        for token in missing:
            print(f"  - {token}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
