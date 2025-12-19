#!/usr/bin/env python3
"""Sync README AUTOGEN blocks from analysis sources."""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
README_PATH = REPO_ROOT / "README.md"

AUTOGEN_PATTERN = re.compile(
    r"(<!-- AUTOGEN:(?P<name>[A-Z0-9_]+) START -->)(?P<body>.*?)(<!-- AUTOGEN:(?P=name) END -->)",
    re.DOTALL,
)


@dataclass(frozen=True)
class SourceSpec:
    path: Path
    marker: str | None = None


SOURCES: dict[str, SourceSpec] = {
    "README_PHYSICS_SUMMARY": SourceSpec(ANALYSIS_DIR / "equations.md", "README_PHYSICS_SUMMARY"),
    "README_QUICKSTART": SourceSpec(ANALYSIS_DIR / "run-recipes.md", "README_QUICKSTART"),
    "README_CLI_DRIVER_RULE": SourceSpec(ANALYSIS_DIR / "run-recipes.md", "README_CLI_DRIVER_RULE"),
    "README_SMOKE_COMMAND": SourceSpec(ANALYSIS_DIR / "run-recipes.md", "README_SMOKE_COMMAND"),
    "README_CLI_EXAMPLES": SourceSpec(ANALYSIS_DIR / "run-recipes.md", "README_CLI_EXAMPLES"),
    "README_OUTPUT_COLUMNS": SourceSpec(ANALYSIS_DIR / "AI_USAGE.md", "README_OUTPUT_COLUMNS"),
}


def extract_marked_block(text: str, marker: str, source: Path) -> str:
    """Extract a marker block from text."""
    start_tag = f"<!-- {marker} START -->"
    end_tag = f"<!-- {marker} END -->"
    start_count = text.count(start_tag)
    end_count = text.count(end_tag)
    if start_count != 1 or end_count != 1:
        raise ValueError(
            f"Expected exactly one {marker} block in {source}, found start={start_count}, end={end_count}."
        )
    start_idx = text.find(start_tag)
    end_idx = text.find(end_tag, start_idx + len(start_tag))
    if end_idx == -1:
        raise ValueError(f"Missing end tag for {marker} in {source}.")
    content = text[start_idx + len(start_tag) : end_idx]
    return content.strip("\n")


def load_source(spec: SourceSpec) -> str:
    """Load content from a marker or full snippet file."""
    text = spec.path.read_text(encoding="utf-8")
    if spec.marker:
        return extract_marked_block(text, spec.marker, spec.path)
    return text.strip("\n")


def render_readme(text: str) -> tuple[str, list[str], int]:
    """Render README content by replacing AUTOGEN blocks."""
    unknown: list[str] = []
    matches = list(AUTOGEN_PATTERN.finditer(text))

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        spec = SOURCES.get(name)
        if spec is None:
            unknown.append(name)
            return match.group(0)
        body = load_source(spec)
        return f"{match.group(1)}\n{body}\n{match.group(4)}"

    rendered = AUTOGEN_PATTERN.sub(replace, text)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered, unknown, len(matches)


def diff_lines(before: str, after: str) -> str:
    """Return a unified diff for display."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="README.md (current)",
            tofile="README.md (generated)",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync README AUTOGEN blocks from analysis sources.")
    parser.add_argument("--write", action="store_true", help="Update README in place.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if README is out of sync.")
    args = parser.parse_args()

    if args.write and args.check:
        parser.error("Choose either --write or --check.")
    if not args.write and not args.check:
        parser.error("Specify --write or --check.")

    readme_text = README_PATH.read_text(encoding="utf-8")
    rendered, unknown, block_count = render_readme(readme_text)

    if args.check:
        if block_count == 0:
            print("No AUTOGEN blocks found in README.md.", file=sys.stderr)
            return 1
        if unknown:
            unknown_list = ", ".join(sorted(set(unknown)))
            print(f"Unknown AUTOGEN block(s): {unknown_list}", file=sys.stderr)
            return 1
        if rendered != readme_text:
            print(diff_lines(readme_text, rendered))
            return 1
        return 0

    if unknown:
        unknown_list = ", ".join(sorted(set(unknown)))
        raise SystemExit(f"Unknown AUTOGEN block(s): {unknown_list}")

    if rendered != readme_text:
        README_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
