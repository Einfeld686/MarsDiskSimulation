#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


EXCLUDE_START = "<!-- TEX_EXCLUDE_START -->"
EXCLUDE_END = "<!-- TEX_EXCLUDE_END -->"
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
TEX_HEADING_RE = re.compile(
    r"^\\(section|subsection|subsubsection|paragraph)\*?\{(.+)\}\s*$"
)
CHAPTER_RE = re.compile(r"^\\chapter\{(.+)\}\s*$")
HEADING_LEVEL = {
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
}


def extract_excluded_titles(markdown_text: str) -> list[str]:
    titles: list[str] = []
    in_exclude = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped == EXCLUDE_START:
            in_exclude = True
            continue
        if stripped == EXCLUDE_END:
            in_exclude = False
            continue
        if not in_exclude:
            continue
        match = MD_HEADING_RE.match(stripped)
        if match:
            title = match.group(2).strip()
            if title:
                titles.append(title)
    return titles


def find_chapter_range(lines: list[str], chapter_title: str | None) -> tuple[int, int]:
    if not chapter_title:
        return 0, len(lines)
    start_idx = None
    for idx, line in enumerate(lines):
        match = CHAPTER_RE.match(line.strip())
        if match and match.group(1) == chapter_title:
            start_idx = idx
            break
    if start_idx is None:
        return 0, len(lines)
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if CHAPTER_RE.match(lines[idx].strip()):
            end_idx = idx
            break
    return start_idx, end_idx


def strip_tex_blocks(
    lines: list[str],
    titles: set[str],
    start_idx: int,
    end_idx: int,
) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    idx = start_idx
    while idx < end_idx:
        line = lines[idx]
        match = TEX_HEADING_RE.match(line.strip())
        if not match:
            idx += 1
            continue
        heading_type = match.group(1)
        heading_title = match.group(2).strip()
        if heading_title not in titles:
            idx += 1
            continue
        removed.append(heading_title)
        level = HEADING_LEVEL[heading_type]
        next_idx = idx + 1
        while next_idx < end_idx:
            next_line = lines[next_idx].strip()
            if CHAPTER_RE.match(next_line):
                break
            next_heading = TEX_HEADING_RE.match(next_line)
            if next_heading and HEADING_LEVEL[next_heading.group(1)] <= level:
                break
            next_idx += 1
        del lines[idx:next_idx]
        end_idx -= next_idx - idx
    return lines, removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove TEX_EXCLUDE sections from a TeX file."
    )
    parser.add_argument(
        "--markdown",
        default="analysis/introduction.md",
        help="Markdown source containing TEX_EXCLUDE markers.",
    )
    parser.add_argument(
        "--tex",
        default="paper/thesis_draft.tex",
        help="Target TeX file to update.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (defaults to --tex).",
    )
    parser.add_argument(
        "--chapter",
        default=None,
        help="Chapter title to constrain removals (required unless --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply removals across the entire document.",
    )
    args = parser.parse_args()

    md_path = Path(args.markdown)
    tex_path = Path(args.tex)
    out_path = Path(args.out) if args.out else tex_path

    if args.all and args.chapter:
        print("--all and --chapter are mutually exclusive.", file=sys.stderr)
        return 2
    if not args.all and not args.chapter:
        print("--chapter is required unless --all is set.", file=sys.stderr)
        return 2

    chapter = None if args.all else args.chapter

    markdown_text = md_path.read_text(encoding="utf-8")
    titles = set(extract_excluded_titles(markdown_text))
    if not titles:
        print("No TEX_EXCLUDE headings found.", file=sys.stderr)
        return 1

    tex_lines = tex_path.read_text(encoding="utf-8").splitlines(keepends=True)
    start_idx, end_idx = find_chapter_range(tex_lines, chapter)
    tex_lines, removed = strip_tex_blocks(tex_lines, titles, start_idx, end_idx)

    if not removed:
        print("No matching TeX headings removed.", file=sys.stderr)
    else:
        removed_sorted = ", ".join(sorted(set(removed)))
        print(f"Removed TeX sections: {removed_sorted}", file=sys.stderr)

    out_path.write_text("".join(tex_lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
