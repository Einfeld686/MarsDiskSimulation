#!/usr/bin/env python3
"""
Clean OCR outputs in paper/pdf_extractor/outputs based on the migration plan.

This script updates result.md files by removing table bodies and isolated junk
lines, then refreshes cleanup reports and summary CSVs.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


TABLE_PLACEHOLDER_RE = re.compile(r"^\s*\[\[TABLE:(?P<label>[^]]+)\]\]\s*$")
EQ_PLACEHOLDER_RE = re.compile(r"\[\[EQN:\((?P<num>[^)]+)\)\]\]")
EQ_LABEL_PATTERN = r"(?:[A-Za-z]\.?)?\d+(?:\.\d+)*[A-Za-z]?"
EQ_LABEL_RE = re.compile(EQ_LABEL_PATTERN)
EQ_NUMBER_TRAIL_RE = re.compile(rf"\((?P<num>{EQ_LABEL_PATTERN})\)\s*[.,]?\s*$")
EQ_NUMBER_ONLY_RE = re.compile(rf"^\s*\((?P<num>{EQ_LABEL_PATTERN})\)\s*[.,]?\s*$")
EQUATION_REF_RE = re.compile(r"\bEq(?:s|n)?\.?\b|\bEquations?\b", re.IGNORECASE)
EQ_REF_HEAD_RE = re.compile(
    rf"\b(?:Eq(?:s|n)?|Equations?)\.?\s*(?:\(\s*(?P<label>{EQ_LABEL_PATTERN})\s*\)|(?P<label_plain>{EQ_LABEL_PATTERN}))",
    re.IGNORECASE,
)
EQ_REF_EXTRA_RE = re.compile(
    rf"\s*(?:,|and|or|&|\u2013|-)\s*(?:\(\s*(?P<label>{EQ_LABEL_PATTERN})\s*\)|(?P<label_plain>{EQ_LABEL_PATTERN}))",
    re.IGNORECASE,
)
EQ_REF_RANGE_RE = re.compile(
    rf"\b(?:Eq(?:ns?|s)?|Equations?)\.?\s*(?:\(\s*(?P<start>{EQ_LABEL_PATTERN})\s*\)|(?P<start_plain>{EQ_LABEL_PATTERN}))\s*[\u2013-]\s*(?:\(\s*(?P<end>{EQ_LABEL_PATTERN})\s*\)|(?P<end_plain>{EQ_LABEL_PATTERN}))",
    re.IGNORECASE,
)
EQ_REF_LIST_RE = re.compile(
    rf"\b(?:Eq(?:ns?|s)?|Equations?)\.?\s+(?P<rest>(?:\(?{EQ_LABEL_PATTERN}\)?\s*(?:,|and|or|&)\s*)+\(?{EQ_LABEL_PATTERN}\)?)",
    re.IGNORECASE,
)
EQ_REF_PLURAL_SINGLE_RE = re.compile(
    rf"\b(?:Eqs|Eqns|Equations)\.?\s*(?:\(\s*(?P<label>{EQ_LABEL_PATTERN})\s*\)|(?P<label_plain>{EQ_LABEL_PATTERN}))",
    re.IGNORECASE,
)
EQ_REF_SINGLE_RE = re.compile(
    rf"\b(?:Eq|Eqn|Equation)\.?\s*(?:\(\s*(?P<label>{EQ_LABEL_PATTERN})\s*\)|(?P<label_plain>{EQ_LABEL_PATTERN}))",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(18|19|20)\d{2}\b")
AUTHOR_RE = re.compile(r"\b[A-Z][A-Za-z\-]+\b")
ET_AL_RE = re.compile(r"\bet\s+al\.?\b", re.IGNORECASE)
EQ_EXTERNAL_HINT_RE = re.compile(r"\b(of|from|in)\b", re.IGNORECASE)
CITATION_BRACKET_RE = re.compile(r"\[[0-9][0-9,\s\-]*\]")
AUTHOR_YEAR_PAREN_RE = re.compile(r"\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,?\s*(18|19|20)\d{2}\)")
AUTHOR_YEAR_INLINE_RE = re.compile(r"\b[A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s*(18|19|20)\d{2}\b")
AUTHOR_YEAR_TRAILING_PAREN_RE = re.compile(
    r"\b[A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?\s*\((18|19|20)\d{2}\)"
)
AUTHOR_YEAR_BARE_RE = re.compile(
    r"\b[A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?\s+(18|19|20)\d{2}\b"
)
INTERNAL_LOC_RE = re.compile(r"\b(Appendix|Section|Sect\.|Sec\.|Fig\.|Figure|Table|Chapter)\b", re.IGNORECASE)
INTERNAL_SELF_RE = re.compile(r"\b(this|present|current)\s+(paper|work|study|section|appendix)\b", re.IGNORECASE)
EQ_EXTERNAL_IMMEDIATE_RE = re.compile(
    r"^\s*[,;:]\s*"
    r"(?:\[[0-9][0-9,\s\-]*\]"
    r"|\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,?\s*(18|19|20)\d{2}\)"
    r"|[A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s*(18|19|20)\d{2}"
    r"|[A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?\s*\((18|19|20)\d{2}\))"
)
EQ_EXTERNAL_LINK_RE = re.compile(r"^\s*(?:,?\s*)?(?:of|from|in)\b", re.IGNORECASE)
EQ_EXTERNAL_PRONOUN_RE = re.compile(r"\b(their|his|her|its)\s*$", re.IGNORECASE)
MATH_TOKEN_RE = re.compile(
    r"(\\[a-zA-Z]+|[_^]|=|\\cdot|\\times|\\pm|\\propto|\\sqrt|\\frac|[\u00b7\u00b1\u00d7])"
)
MATH_BLOCK_START_RE = re.compile(r"^\s*(\\\[|\\begin\{equation\*?\}|\$\$)\s*$")
MATH_BLOCK_END_RE = re.compile(r"^\s*(\\\]|\\end\{equation\*?\}|\$\$)\s*$")
IMAGE_REF_INLINE_RE = re.compile(r"!\[\]\[image\d+\]", re.IGNORECASE)
IMAGE_LABEL_RE = re.compile(r"^\s*\[image\d+\]\s*$", re.IGNORECASE)
IMAGE_DEF_BASE64_RE = re.compile(r"^\s*\[image\d+\]:\s*<data:image/[^>]+>\s*$", re.IGNORECASE)
DATA_URI_RE = re.compile(r"^\s*<data:image/[^>]+>\s*$", re.IGNORECASE)
INLINE_IMAGE_TOKEN_RE = re.compile(r"!\[\]\[image\d+\]|\[image\d+\]", re.IGNORECASE)
PAGE_MARKER_RE = re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
PAGE_FRACTION_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
PAGE_ALPHA_RE = re.compile(r"^[A-Z]\d+,\s*page\s+\d+\s+of\s+\d+", re.IGNORECASE)
PAGE_ALPHA_TRAIL_RE = re.compile(r"\b[A-Z]\d+,\s*page\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
ROMAN_RE = re.compile(r"^\s*[IVXLCDM]+\s*$")
DIGITS_RE = re.compile(r"^\s*\d+\s*$")
PUNCT_ONLY_RE = re.compile(r"^\s*[\W_]+\s*$")
MATH_GUARD_RE = re.compile(r"(\\[a-zA-Z]+|\\\[|\\\]|[_^])")

META_PATTERNS = [
    re.compile(r"\b(Received|Accepted|Revised|Available online)\b", re.IGNORECASE),
    re.compile(r"\bDOI:\s*\S+", re.IGNORECASE),
    re.compile(r"\bdoi:\s*\S+", re.IGNORECASE),
    re.compile(r"\bhttps?://\S+"),
    re.compile(r"\bArticle ID\b", re.IGNORECASE),
]

BANNER_PATTERNS = [
    re.compile(r"Downloaded from .*personal use only", re.IGNORECASE),
    re.compile(r"Downloaded from .*", re.IGNORECASE),
    re.compile(r"^Article published by .*available at\b", re.IGNORECASE),
    re.compile(r"^Preprint typeset using\b", re.IGNORECASE),
    re.compile(r"^\W*(Other articles in this volume|Top cited articles|Top downloaded articles|Our comprehensive search)\b", re.IGNORECASE),
    re.compile(r"^Click here for quick links\b", re.IGNORECASE),
    re.compile(r"^Annual Reviews content online\b", re.IGNORECASE),
    re.compile(r"^including:\s*$", re.IGNORECASE),
    re.compile(r"All rights reserved", re.IGNORECASE),
    re.compile(r"Macmillan Publishers Limited", re.IGNORECASE),
]

LABEL_ADJACENT_RE = re.compile(r"\b(Fig\.?|Figure|Table|Eq\.?|Equation)\b", re.IGNORECASE)
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^[A-Z][A-Za-z&.\- ]+\s+\d+\s*,\s*[A-Z]?\d+\s*\(\d{4}\)\s*$"),
    re.compile(r"^A\\?&A\s+\d+\s*,\s*[A-Z]?\d+\s*\(\d{4}\)\s*$", re.IGNORECASE),
    re.compile(r"^MNRAS\s+\*{0,2}\d+\*{0,2},\s*\d+[^0-9A-Za-z]+\d+\s*\(\d{4}\)\s*$", re.IGNORECASE),
    re.compile(r"^The Astrophysical Journal(?: Letters)?,\s*\d+:\S+\s*\(\d+pp\),\s*\d{4}\s+[A-Za-z]+\s+\d{1,2}\s+.+$", re.IGNORECASE),
    re.compile(r"^ApJ Letters,\s*in press,\s*[A-Za-z]+\s+\d{1,2},\s*\d{4}$", re.IGNORECASE),
]


@dataclass
class CleanupCounts:
    found: Dict[str, int]
    removed: Dict[str, int]
    removed_total: int
    removed_page_markers: int
    repeated_header_footer_lines: List[str] = field(default_factory=list)
    repeated_header_footer_removed: int = 0


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _iter_nonempty_neighbors(lines: Sequence[str], idx: int) -> Tuple[Optional[str], Optional[str]]:
    prev_line = None
    for j in range(idx - 1, -1, -1):
        if lines[j].strip():
            prev_line = lines[j]
            break
    next_line = None
    for j in range(idx + 1, len(lines)):
        if lines[j].strip():
            next_line = lines[j]
            break
    return prev_line, next_line


def _strip_inline_image_tokens(line: str) -> Tuple[str, int]:
    cleaned, count = INLINE_IMAGE_TOKEN_RE.subn("", line)
    if count:
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, count


def _strip_page_markers(line: str) -> Tuple[str, bool]:
    cleaned = PAGE_ALPHA_TRAIL_RE.sub("", line)
    cleaned = PAGE_MARKER_RE.sub("", cleaned)
    if cleaned == line:
        return line, False
    cleaned = re.sub(r"\b[A-Z]\d+\s*,?\s*$", "", cleaned)
    cleaned = cleaned.rstrip(" ,;:-")
    return cleaned, True


def _is_header_footer_candidate(line: str) -> bool:
    stripped = line.strip()
    for pattern in HEADER_FOOTER_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _is_adjacent_label(lines: Sequence[str], idx: int) -> bool:
    prev_line, next_line = _iter_nonempty_neighbors(lines, idx)
    for line in (prev_line, next_line):
        if not line:
            continue
        if LABEL_ADJACENT_RE.search(line) and not re.search(r"\d", line):
            return True
    return False


def _normalize_for_table_label(line: str) -> str:
    return re.sub(r"[*_`]", "", line).strip()


def _extract_table_label(line: str) -> Optional[str]:
    normalized = _normalize_for_table_label(line)
    if not normalized.lower().startswith("table"):
        return None
    parts = normalized.split()
    if len(parts) < 2:
        return None
    label = parts[1].strip()
    label = re.sub(r"[^\w]+", "", label)
    return label or None


def _is_table_start_line(line: str, prev_line: Optional[str] = None, next_line: Optional[str] = None) -> bool:
    normalized = _normalize_for_table_label(line)
    if not normalized.lower().startswith("table "):
        return False
    parts = normalized.split(maxsplit=2)
    if len(parts) >= 3 and parts[2].startswith("("):
        return False
    if prev_line is not None and next_line is not None:
        if prev_line.strip() and next_line.strip():
            return False
    return True


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("|") or stripped.endswith("|"):
        return True
    if re.match(r"^[\|\-\:\s]+$", stripped):
        return True
    return False


def _is_markdown_table_start(lines: Sequence[str], idx: int) -> bool:
    if not _is_markdown_table_line(lines[idx]):
        return False
    prev_line, _ = _iter_nonempty_neighbors(lines, idx)
    if prev_line and _is_markdown_table_line(prev_line):
        return False
    return True


def _is_table_note_line(line: str) -> bool:
    stripped = line.strip()
    normalized = _normalize_for_table_label(stripped)
    if normalized.lower().startswith("notes."):
        return True
    if normalized.lower().startswith("note."):
        return True
    if re.match(r"^\*[a-z]\*", stripped, re.IGNORECASE):
        return True
    return False


def _is_table_like_line_strict(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_markdown_table_line(stripped):
        return True
    if MATH_GUARD_RE.search(stripped):
        return False
    if "=" in stripped:
        return False
    numeric_tokens = re.findall(r"\d+(?:\.\d+)?", stripped)
    digit_count = sum(ch.isdigit() for ch in stripped)
    alpha_count = sum(ch.isalpha() for ch in stripped)
    if len(numeric_tokens) >= 3 and digit_count >= 10 and digit_count >= max(1, alpha_count * 2):
        return True
    if len(numeric_tokens) >= 3 and re.search(r"\s{2,}", stripped):
        return True
    return False


def _is_table_like_line_loose(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_markdown_table_line(stripped):
        return True
    if MATH_GUARD_RE.search(stripped):
        return False
    if "=" in stripped:
        return False
    if _is_table_note_line(stripped):
        return True
    numeric_tokens = re.findall(r"\d+(?:\.\d+)?", stripped)
    digit_count = sum(ch.isdigit() for ch in stripped)
    alpha_count = sum(ch.isalpha() for ch in stripped)
    if len(numeric_tokens) >= 2 and digit_count >= 6 and digit_count >= max(1, alpha_count * 2):
        return True
    if len(numeric_tokens) >= 2 and re.search(r"\s{2,}", stripped):
        return True
    if stripped.count("(") >= 2 and len(stripped) < 80:
        return True
    return False


def _looks_like_table_fragment(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_table_like_line_loose(stripped):
        return True
    if _is_table_note_line(stripped):
        return True
    if stripped.endswith("."):
        return False
    numeric_tokens = re.findall(r"\d+(?:\.\d+)?", stripped)
    if numeric_tokens and len(stripped) <= 80:
        return True
    if len(stripped) <= 20 and not re.search(r"[A-Za-z]{3,}", stripped):
        return True
    return False


def _is_math_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if MATH_GUARD_RE.search(stripped):
        return True
    if "=" in stripped:
        return True
    return False


def _line_has_page_marker(line: str) -> bool:
    stripped = line.strip()
    if PAGE_FRACTION_RE.match(stripped):
        return True
    if PAGE_MARKER_RE.search(line):
        return True
    if PAGE_ALPHA_TRAIL_RE.search(line):
        return True
    return False


def _is_table_block_end(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if TABLE_PLACEHOLDER_RE.match(stripped):
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith("**"):
        if LABEL_ADJACENT_RE.search(stripped):
            return True
        if re.match(r"^\*\*\d", stripped):
            return True
        return False
    if re.match(r"^\d+\.\s", stripped):
        return True
    if re.match(r"^[A-Z]", stripped) and len(stripped) > 50:
        return True
    if LABEL_ADJACENT_RE.search(stripped) and stripped.startswith("**"):
        return True
    return False


def _skip_table_block(lines: Sequence[str], start_idx: int, counts: Dict[str, int]) -> int:
    idx = start_idx
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            j = idx + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                return j
            if _looks_like_table_fragment(lines[j]):
                idx = j
                continue
            return j
        if _looks_like_table_fragment(line):
            counts["table_block"] = counts.get("table_block", 0) + 1
            idx += 1
            continue
        if _is_table_block_end(line):
            return idx
        return idx
    return idx


def _has_recent_table_placeholder(lines: Sequence[str], idx: int, window: int = 60) -> bool:
    start = max(0, idx - window)
    for j in range(idx - 1, start - 1, -1):
        if TABLE_PLACEHOLDER_RE.match(lines[j].strip()):
            return True
    return False


def _has_recent_table_label(lines: Sequence[str], idx: int, window: int = 6) -> bool:
    start = max(0, idx - window)
    for j in range(idx - 1, start - 1, -1):
        prev_line = lines[j - 1] if j - 1 >= 0 else ""
        next_line = lines[j + 1] if j + 1 < len(lines) else ""
        if _is_table_start_line(lines[j], prev_line, next_line):
            return True
    return False


def _compress_blank_lines(lines: Sequence[str], max_blank: int = 2) -> List[str]:
    compressed: List[str] = []
    blank_run = 0
    for line in lines:
        if line.strip():
            blank_run = 0
            compressed.append(line)
            continue
        blank_run += 1
        if blank_run <= max_blank:
            compressed.append("")
    return compressed


def _count_paragraphs(lines: Sequence[str]) -> int:
    count = 0
    in_para = False
    for line in lines:
        if line.strip():
            if not in_para:
                count += 1
                in_para = True
        else:
            in_para = False
    return count


def _max_blank_run(lines: Sequence[str]) -> int:
    max_run = 0
    current = 0
    for line in lines:
        if line.strip():
            current = 0
            continue
        current += 1
        max_run = max(max_run, current)
    return max_run


def _scan_remaining_suspects(lines: Sequence[str]) -> List[Dict[str, str]]:
    suspects: List[Dict[str, str]] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if IMAGE_LABEL_RE.match(stripped) or IMAGE_REF_INLINE_RE.search(stripped) or INLINE_IMAGE_TOKEN_RE.search(stripped):
            suspects.append({"line_no": idx, "content": line})
            continue
        if IMAGE_DEF_BASE64_RE.match(stripped) or DATA_URI_RE.match(stripped):
            suspects.append({"line_no": idx, "content": line})
            continue
        if DIGITS_RE.match(stripped) or ROMAN_RE.match(stripped) or PUNCT_ONLY_RE.match(stripped):
            suspects.append({"line_no": idx, "content": line})
            continue
    return suspects


def _scan_meta_flags(lines: Sequence[str]) -> List[Dict[str, str]]:
    flagged: List[Dict[str, str]] = []
    for idx, line in enumerate(lines, start=1):
        for pattern in META_PATTERNS:
            if pattern.search(line):
                flagged.append({"line_no": idx, "content": line})
                break
    return flagged


def _remove_junk_and_tables(lines: Sequence[str]) -> Tuple[List[str], CleanupCounts]:
    found: Dict[str, int] = {}
    removed: Dict[str, int] = {}
    removed_page_markers = 0
    header_seen: Dict[str, int] = {}
    repeated_header_footer_lines: List[str] = []
    repeated_header_footer_seen: set[str] = set()
    repeated_header_footer_removed = 0

    def mark(pattern_key: str, removed_flag: bool) -> None:
        found[pattern_key] = found.get(pattern_key, 0) + 1
        if removed_flag:
            removed[pattern_key] = removed.get(pattern_key, 0) + 1

    output: List[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if IMAGE_LABEL_RE.match(stripped):
            mark("image_ref_inline", True)
            idx += 1
            continue
        if IMAGE_DEF_BASE64_RE.match(stripped):
            mark("image_def_base64", True)
            idx += 1
            continue
        if DATA_URI_RE.match(stripped):
            mark("image_def_base64", True)
            idx += 1
            continue

        if any(p.search(line) for p in BANNER_PATTERNS):
            mark("banner_line", True)
            idx += 1
            continue

        if PAGE_FRACTION_RE.match(stripped):
            mark("page_marker", True)
            removed_page_markers += 1
            idx += 1
            continue
        if PAGE_MARKER_RE.search(line) or PAGE_ALPHA_TRAIL_RE.search(line):
            cleaned_line, trimmed = _strip_page_markers(line)
            if trimmed:
                mark("page_marker", True)
                removed_page_markers += 1
                if not cleaned_line.strip():
                    idx += 1
                    continue
                line = cleaned_line
                stripped = line.strip()

        if _is_header_footer_candidate(stripped):
            normalized = " ".join(stripped.split())
            header_seen[normalized] = header_seen.get(normalized, 0) + 1
            if header_seen[normalized] > 1:
                if normalized not in repeated_header_footer_seen:
                    repeated_header_footer_lines.append(normalized)
                    repeated_header_footer_seen.add(normalized)
                repeated_header_footer_removed += 1
                mark("repeated_header_footer", True)
                idx += 1
                continue
            mark("repeated_header_footer", False)
            output.append(line)
            idx += 1
            continue

        cleaned_line, inline_removed = _strip_inline_image_tokens(line)
        if inline_removed:
            mark("image_ref_inline", True)
            if not cleaned_line.strip():
                idx += 1
                continue
            line = cleaned_line
            stripped = line.strip()

        if TABLE_PLACEHOLDER_RE.match(stripped):
            prev_line, next_line = _iter_nonempty_neighbors(lines, idx)
            if _is_math_line(prev_line or "") and _is_math_line(next_line or ""):
                mark("table_placeholder_dropped", True)
                idx += 1
                continue
            output.append(line)
            output.append("")
            idx += 1
            idx = _skip_table_block(lines, idx, removed)
            continue

        prev_raw = lines[idx - 1] if idx - 1 >= 0 else ""
        next_raw = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _is_table_start_line(line, prev_raw, next_raw):
            label = _extract_table_label(line) or "unnumbered"
            output.append(f"[[TABLE:({label})]]" if label != "unnumbered" else "[[TABLE:unnumbered]]")
            output.append("")
            mark("table_header", True)
            idx += 1
            idx = _skip_table_block(lines, idx, removed)
            continue

        if _is_markdown_table_line(line):
            if _is_markdown_table_start(lines, idx):
                if not (_has_recent_table_label(lines, idx) or _has_recent_table_placeholder(lines, idx, window=12)):
                    output.append("[[TABLE:unnumbered]]")
                    output.append("")
                    mark("table_header", True)
                idx = _skip_table_block(lines, idx, removed)
            else:
                mark("table_block", True)
                idx += 1
            continue

        if _is_table_like_line_strict(line) and _has_recent_table_placeholder(lines, idx):
            mark("table_block", True)
            idx += 1
            continue

        if DIGITS_RE.match(stripped):
            if len(stripped) >= 5:
                mark("isolated_digits_5plus", True)
                idx += 1
                continue
            if not _is_adjacent_label(lines, idx):
                mark("isolated_digits", True)
                idx += 1
                continue

        if ROMAN_RE.match(stripped) and not _is_adjacent_label(lines, idx):
            mark("isolated_roman", True)
            idx += 1
            continue

        if PUNCT_ONLY_RE.match(stripped):
            mark("punct_only", True)
            idx += 1
            continue

        output.append(line)
        idx += 1

    output = _compress_blank_lines(output, max_blank=2)
    removed_total = sum(removed.values())
    return output, CleanupCounts(
        found=found,
        removed=removed,
        removed_total=removed_total,
        removed_page_markers=removed_page_markers,
        repeated_header_footer_lines=repeated_header_footer_lines,
        repeated_header_footer_removed=repeated_header_footer_removed,
    )


def _calc_placeholder_counts(lines: Sequence[str]) -> Tuple[int, int, int]:
    eq_numbered = 0
    table_numbered = 0
    table_unnumbered = 0
    for line in lines:
        if EQ_PLACEHOLDER_RE.search(line):
            eq_numbered += 1
        match = TABLE_PLACEHOLDER_RE.match(line.strip())
        if match:
            label = match.group("label")
            if label == "unnumbered":
                table_unnumbered += 1
            else:
                table_numbered += 1
    return eq_numbered, table_numbered, table_unnumbered


def _detect_equation_number(line: str, in_block: bool = False) -> Optional[str]:
    if EQ_PLACEHOLDER_RE.search(line):
        return None
    match = EQ_NUMBER_TRAIL_RE.search(line)
    if not match:
        return None
    if EQUATION_REF_RE.search(line):
        return None
    if not in_block and not MATH_TOKEN_RE.search(line):
        return None
    return match.group("num")


def _is_math_candidate_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if EQUATION_REF_RE.search(stripped):
        return False
    if EQ_PLACEHOLDER_RE.search(stripped):
        return False
    if MATH_TOKEN_RE.search(stripped):
        return True
    if re.search(r"\d", stripped) and re.search(r"[+\-*/]", stripped):
        return True
    return False


def _extract_eq_labels(line: str) -> List[str]:
    labels: List[str] = []
    for _, group_labels, _ in _iter_eq_reference_groups(line):
        labels.extend(group_labels)
    return labels


def _label_from_match(match: re.Match[str]) -> str:
    return match.group("label") or match.group("label_plain") or ""


def _iter_eq_reference_groups(line: str) -> List[Tuple[re.Match[str], List[str], int]]:
    groups: List[Tuple[re.Match[str], List[str], int]] = []
    for match in EQ_REF_HEAD_RE.finditer(line):
        label = _label_from_match(match)
        if not label:
            continue
        labels = [label]
        end = match.end()
        if re.search(r"\bEqs\b|\bEqns\b|\bEquations\b", match.group(0), re.IGNORECASE):
            pos = end
            while True:
                extra_match = EQ_REF_EXTRA_RE.match(line[pos:])
                if not extra_match:
                    break
                extra_label = _label_from_match(extra_match)
                if extra_label:
                    labels.append(extra_label)
                pos += extra_match.end()
            end = pos
        groups.append((match, labels, end))
    return groups


def _normalize_eq_reference_line(line: str) -> str:
    if EQ_PLACEHOLDER_RE.search(line):
        return line
    if not EQUATION_REF_RE.search(line):
        return line

    def range_repl(match: re.Match[str]) -> str:
        start = match.group("start") or match.group("start_plain") or ""
        end = match.group("end") or match.group("end_plain") or ""
        if not start or not end:
            return match.group(0)
        return f"Eqs. ({start})-({end})"

    def list_repl(match: re.Match[str]) -> str:
        rest = match.group("rest")
        if "-" in rest or "\u2013" in rest:
            return match.group(0)
        labels = EQ_LABEL_RE.findall(rest)
        if not labels:
            return match.group(0)
        return "Eqs. " + ", ".join(f"({label})" for label in labels)

    def single_label(match: re.Match[str]) -> str:
        label = match.group("label") or match.group("label_plain") or ""
        if not label:
            return match.group(0)
        return f"Eq. ({label})"

    line = EQ_REF_PLURAL_SINGLE_RE.sub(single_label, line)
    line = EQ_REF_RANGE_RE.sub(range_repl, line)
    line = EQ_REF_LIST_RE.sub(list_repl, line)
    line = EQ_REF_SINGLE_RE.sub(single_label, line)
    return line


def _normalize_eq_references(lines: Sequence[str]) -> List[str]:
    return [_normalize_eq_reference_line(line) for line in lines]


def _has_citation(text: str) -> bool:
    return bool(
        CITATION_BRACKET_RE.search(text)
        or AUTHOR_YEAR_PAREN_RE.search(text)
        or AUTHOR_YEAR_INLINE_RE.search(text)
        or AUTHOR_YEAR_TRAILING_PAREN_RE.search(text)
        or AUTHOR_YEAR_BARE_RE.search(text)
    )


def _external_reference_reason(
    line: str, match: re.Match[str], group_end: int
) -> Optional[Tuple[str, str, str]]:
    head_window = line[max(0, match.start() - 50):match.start()]
    tail_window = line[group_end:group_end + 140]

    pronoun_match = EQ_EXTERNAL_PRONOUN_RE.search(head_window)
    if pronoun_match:
        return ("strong", "pronoun", pronoun_match.group(0))
    immediate_match = EQ_EXTERNAL_IMMEDIATE_RE.match(tail_window)
    if immediate_match:
        return ("strong", "immediate_citation", immediate_match.group(0).strip())
    link_match = EQ_EXTERNAL_LINK_RE.search(tail_window)
    if link_match:
        link_tail = tail_window[link_match.end():]
        for pattern in (
            CITATION_BRACKET_RE,
            AUTHOR_YEAR_PAREN_RE,
            AUTHOR_YEAR_INLINE_RE,
            AUTHOR_YEAR_TRAILING_PAREN_RE,
            AUTHOR_YEAR_BARE_RE,
        ):
            citation_match = pattern.search(link_tail)
            if citation_match:
                return ("strong", "link_with_citation", citation_match.group(0))
    return None


def _is_external_eq_reference(line: str, match: re.Match[str], group_end: int) -> bool:
    if _external_reference_reason(line, match, group_end):
        return True
    head_window = line[max(0, match.start() - 50):match.start()]
    tail_window = line[group_end:group_end + 140]
    if INTERNAL_LOC_RE.search(head_window) or INTERNAL_LOC_RE.search(tail_window):
        return False
    if INTERNAL_SELF_RE.search(head_window) or INTERNAL_SELF_RE.search(tail_window):
        return False
    return False


def _build_external_audit_rows(output_root: Path) -> List[List[str]]:
    rows: List[List[str]] = []
    for result_path in sorted(output_root.glob("*/result.md")):
        text = _read_text(result_path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            groups = _iter_eq_reference_groups(line)
            if not groups:
                continue
            for match, labels, group_end in groups:
                if not _is_external_eq_reference(line, match, group_end):
                    continue
                reason = _external_reference_reason(line, match, group_end)
                if reason:
                    strength, reason_tag, evidence = reason
                else:
                    strength = "weak"
                    reason_tag = "unclassified"
                    evidence = ""
                for label in labels:
                    rows.append(
                        [
                            str(result_path.resolve()),
                            str(line_no),
                            label,
                            strength,
                            reason_tag,
                            evidence.replace("\t", " ").strip(),
                            line.replace("\t", " ").strip(),
                        ]
                    )
    return rows


def _write_external_audit_report(output_root: Path) -> None:
    checks_dir = output_root / "_checks"
    _ensure_dir(checks_dir)
    path = checks_dir / "eqn_external_audit.tsv"
    header = ["file", "line_no", "label", "strength", "reason", "evidence", "text"]
    rows = _build_external_audit_rows(output_root)
    path.write_text(
        "\t".join(header) + "\n" + "\n".join("\t".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _supplement_placeholders_from_eq_refs(lines: Sequence[str]) -> Tuple[List[str], int]:
    existing_labels = set()
    for line in lines:
        for match in EQ_PLACEHOLDER_RE.finditer(line):
            existing_labels.add(match.group("num"))
    inserted_labels = set()
    output: List[str] = []
    inserted = 0
    for line in lines:
        output.append(line)
        groups = _iter_eq_reference_groups(line)
        if not groups:
            continue
        for match, labels, group_end in groups:
            if _is_external_eq_reference(line, match, group_end):
                continue
            for label in labels:
                if label in existing_labels or label in inserted_labels:
                    continue
                output.append(f"[[EQN:({label})]]")
                output.append("")
                inserted_labels.add(label)
                inserted += 1
    return output, inserted


def _replace_equation_placeholders(lines: Sequence[str]) -> Tuple[List[str], int]:
    replaced = 0
    output: List[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if MATH_BLOCK_START_RE.match(line):
            block = [line]
            idx += 1
            while idx < len(lines):
                block.append(lines[idx])
                if MATH_BLOCK_END_RE.match(lines[idx]):
                    idx += 1
                    break
                idx += 1
            eq_num = None
            for block_line in block:
                eq_num = _detect_equation_number(block_line, in_block=True)
                if eq_num:
                    break
            if eq_num:
                output.append(f"[[EQN:({eq_num})]]")
                output.append("")
                replaced += 1
            else:
                output.extend(block)
            continue

        eq_num = _detect_equation_number(line)
        if eq_num:
            output.append(f"[[EQN:({eq_num})]]")
            output.append("")
            replaced += 1
            idx += 1
            continue

        if _is_math_candidate_line(line):
            j = idx
            eq_num = None
            while j < len(lines):
                candidate = lines[j]
                if EQ_NUMBER_ONLY_RE.match(candidate):
                    eq_num = EQ_NUMBER_ONLY_RE.match(candidate).group("num")
                    j += 1
                    break
                if not candidate.strip():
                    j += 1
                    continue
                if _is_math_candidate_line(candidate):
                    j += 1
                    continue
                break
            if eq_num:
                output.append(f"[[EQN:({eq_num})]]")
                output.append("")
                replaced += 1
                idx = j
                continue

        output.append(line)
        idx += 1
    return output, replaced


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _format_status(line_count_before: int, line_count_after: int, paragraph_count_after: int, remaining_suspects: int, page_markers: int) -> str:
    if line_count_before > 0 and line_count_after < 0.5 * line_count_before:
        return "blocked"
    if paragraph_count_after < 5:
        return "blocked"
    if remaining_suspects == 0 and page_markers == 0:
        return "clean"
    return "needs_review"


def _load_cleanup_report(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _update_report(
    key: str,
    source_path: Path,
    target_path: Path,
    before_counts: Dict[str, int],
    lines_after: Sequence[str],
    new_counts: CleanupCounts,
    existing_report: Dict[str, object],
) -> Dict[str, object]:
    existing_stats = dict(existing_report.get("stats", {})) if existing_report else {}
    existing_junk = dict(existing_report.get("junk", {})) if existing_report else {}
    found_by = dict(new_counts.found)
    removed_by = dict(new_counts.removed)

    eq_numbered, table_numbered, table_unnumbered = _calc_placeholder_counts(lines_after)
    line_count_after = len(lines_after)
    paragraph_count_after = _count_paragraphs(lines_after)
    max_blank_after = _max_blank_run(lines_after)
    remaining_suspect_lines = _scan_remaining_suspects(lines_after)
    page_marker_remaining = sum(1 for line in lines_after if _line_has_page_marker(line))

    line_count_before = int(existing_stats.get("line_count_before", before_counts.get("line_count_before", 0)))
    paragraph_count_before = int(existing_stats.get("paragraph_count_before", before_counts.get("paragraph_count_before", 0)))
    max_blank_before = int(existing_stats.get("max_consecutive_blank_lines_before", before_counts.get("max_consecutive_blank_lines_before", 0)))
    paragraph_merge_count = int(existing_stats.get("paragraph_merge_count", 0))
    hyphen_join_count = int(existing_stats.get("hyphen_join_count", 0))

    repeated_lines = new_counts.repeated_header_footer_lines
    repeated_removed = new_counts.repeated_header_footer_removed
    page_marker_removed = new_counts.removed_page_markers

    format_status = _format_status(
        line_count_before,
        line_count_after,
        paragraph_count_after,
        len(remaining_suspect_lines),
        page_marker_remaining,
    )

    report = {
        "key": key,
        "source_path": str(source_path.as_posix()),
        "target_path": str(target_path.as_posix()),
        "stats": {
            "line_count_before": line_count_before,
            "paragraph_count_before": paragraph_count_before,
            "max_consecutive_blank_lines_before": max_blank_before,
            "line_count_after": line_count_after,
            "paragraph_count_after": paragraph_count_after,
            "paragraph_merge_count": paragraph_merge_count,
            "hyphen_join_count": hyphen_join_count,
            "max_consecutive_blank_lines_after": max_blank_after,
            "eq_placeholder_numbered": eq_numbered,
            "table_placeholder_numbered": table_numbered,
            "table_placeholder_unnumbered": table_unnumbered,
        },
        "junk": {
            "found_by_pattern": found_by,
            "removed_by_pattern": removed_by,
            "remaining_suspect_lines": remaining_suspect_lines,
            "repeated_header_footer_lines": repeated_lines,
            "repeated_header_footer_removed": repeated_removed,
            "page_marker_removed": page_marker_removed,
            "page_marker_remaining": page_marker_remaining,
            "meta_flagged_lines": _scan_meta_flags(lines_after),
        },
        "format_status": format_status,
    }
    return report


def _before_counts_from_source(source_path: Path) -> Dict[str, int]:
    if not source_path.exists():
        return {}
    lines = _read_text(source_path).split("\n")
    return {
        "line_count_before": len(lines),
        "paragraph_count_before": _count_paragraphs(lines),
        "max_consecutive_blank_lines_before": _max_blank_run(lines),
    }


def _write_diff(old_lines: Sequence[str], new_lines: Sequence[str], diff_path: Path) -> None:
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="result.before",
        tofile="result.after",
        lineterm="",
    )
    _write_text(diff_path, "\n".join(diff) + "\n")


def _collect_keys(source_root: Path, output_root: Path) -> Dict[str, Dict[str, bool]]:
    keys: Dict[str, Dict[str, bool]] = {}
    if source_root.exists():
        for path in sorted(source_root.glob("*.md")):
            keys.setdefault(path.stem, {})["has_ocr"] = True
    if output_root.exists():
        for path in sorted(output_root.iterdir()):
            if not path.is_dir() or path.name.startswith("_"):
                continue
            keys.setdefault(path.name, {})["has_output"] = True
    for key, flags in keys.items():
        flags.setdefault("has_ocr", False)
        flags.setdefault("has_output", False)
    return keys


def _write_key_inventory(keys: Dict[str, Dict[str, bool]], output_root: Path) -> None:
    rows = []
    for key, flags in sorted(keys.items()):
        has_ocr = bool(flags.get("has_ocr"))
        has_output = bool(flags.get("has_output"))
        if has_ocr and has_output:
            status = "both"
        elif has_ocr:
            status = "ocr_only"
        else:
            status = "output_only"
        rows.append([key, has_ocr, has_output, status])

    checks_dir = output_root / "_checks"
    _ensure_dir(checks_dir)
    path = checks_dir / "key_inventory.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "has_ocr", "has_output", "status"])
        writer.writerows(rows)


def _write_cleanup_summary(reports: Dict[str, Dict[str, object]], output_root: Path) -> None:
    checks_dir = output_root / "_checks"
    _ensure_dir(checks_dir)
    path = checks_dir / "cleanup_summary.csv"
    header = [
        "key",
        "format_status",
        "line_count_before",
        "line_count_after",
        "paragraph_count_before",
        "paragraph_count_after",
        "paragraph_merge_count",
        "hyphen_join_count",
        "eq_placeholder_numbered",
        "table_placeholder_numbered",
        "table_placeholder_unnumbered",
        "junk_removed_total",
        "page_marker_remaining",
        "repeated_header_footer_removed",
    ]
    rows: List[List[object]] = []
    for key in sorted(reports.keys()):
        report = reports[key]
        stats = report.get("stats", {})
        junk = report.get("junk", {})
        removed_by = junk.get("removed_by_pattern", {})
        removed_total = 0
        if isinstance(removed_by, dict):
            removed_total = sum(int(v) for v in removed_by.values())
        rows.append(
            [
                key,
                report.get("format_status", ""),
                stats.get("line_count_before", 0),
                stats.get("line_count_after", 0),
                stats.get("paragraph_count_before", 0),
                stats.get("paragraph_count_after", 0),
                stats.get("paragraph_merge_count", 0),
                stats.get("hyphen_join_count", 0),
                stats.get("eq_placeholder_numbered", 0),
                stats.get("table_placeholder_numbered", 0),
                stats.get("table_placeholder_unnumbered", 0),
                removed_total,
                junk.get("page_marker_remaining", 0),
                junk.get("repeated_header_footer_removed", 0),
            ]
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _append_convert_log(
    log_path: Path,
    key: str,
    source_path: Path,
    target_path: Path,
    raw_backup_path: Optional[Path],
    diff_path: Path,
    junk_removed_total: int,
    format_status: str,
    cleanup_report_path: Path,
) -> None:
    _ensure_dir(log_path.parent)
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "key": key,
        "source_path": str(source_path.as_posix()),
        "target_path": str(target_path.as_posix()),
        "raw_backup_path": str(raw_backup_path.as_posix()) if raw_backup_path else "",
        "diff_path": str(diff_path.as_posix()),
        "junk_removed_total": junk_removed_total,
        "format_status": format_status,
        "decision_notes": "",
        "cleanup_report_path": str(cleanup_report_path.as_posix()),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _process_key(
    key: str,
    source_path: Path,
    output_dir: Path,
    timestamp: str,
) -> Optional[Dict[str, object]]:
    if not source_path.exists():
        return None

    _ensure_dir(output_dir)
    logs_dir = output_dir / "logs"
    checks_dir = output_dir / "checks"
    _ensure_dir(logs_dir)
    _ensure_dir(checks_dir)

    result_path = output_dir / "result.md"
    cleanup_report_path = checks_dir / "cleanup_report.json"
    existing_report = _load_cleanup_report(cleanup_report_path)

    source_text = _read_text(source_path)
    if result_path.exists():
        old_text = _read_text(result_path)
        raw_backup = output_dir / f"result.raw.{timestamp}.md"
        _write_text(raw_backup, old_text)
    else:
        old_text = source_text
        raw_backup = None

    old_lines = old_text.split("\n")
    cleaned_lines, counts = _remove_junk_and_tables(source_text.split("\n"))
    cleaned_lines = _normalize_eq_references(cleaned_lines)
    equation_lines, _eq_replaced = _replace_equation_placeholders(cleaned_lines)
    equation_lines, _eq_ref_inserted = _supplement_placeholders_from_eq_refs(equation_lines)
    equation_lines = _compress_blank_lines(equation_lines, max_blank=2)
    new_text = "\n".join(equation_lines).rstrip() + "\n"
    _write_text(result_path, new_text)

    diff_path = logs_dir / "result.diff"
    _write_diff(old_lines, new_text.split("\n"), diff_path)

    before_counts = _before_counts_from_source(source_path)
    report = _update_report(
        key=key,
        source_path=source_path,
        target_path=result_path,
        before_counts=before_counts,
        lines_after=new_text.split("\n"),
        new_counts=counts,
        existing_report=existing_report,
    )
    _write_text(cleanup_report_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    removed_total = sum(int(v) for v in report["junk"]["removed_by_pattern"].values())
    _append_convert_log(
        logs_dir / "convert_log.jsonl",
        key=key,
        source_path=source_path,
        target_path=result_path,
        raw_backup_path=raw_backup,
        diff_path=diff_path,
        junk_removed_total=removed_total,
        format_status=report["format_status"],
        cleanup_report_path=cleanup_report_path,
    )

    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Update OCR outputs and cleanup reports.")
    parser.add_argument("--source-root", default="paper/ocr_references", help="OCR reference directory")
    parser.add_argument("--output-root", default="paper/pdf_extractor/outputs", help="Output directory root")
    parser.add_argument("--keys", nargs="*", default=None, help="Optional key list to process")
    parser.add_argument("--skip-keys", nargs="*", default=None, help="Optional key list to skip")
    parser.add_argument("--skip-keys-file", default=None, help="Optional path to a file containing keys to skip")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    source_root = (repo_root / args.source_root).resolve()
    output_root = (repo_root / args.output_root).resolve()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    key_map = _collect_keys(source_root, output_root)
    _write_key_inventory(key_map, output_root)

    skip_keys = set(args.skip_keys or [])
    if args.skip_keys_file:
        skip_path = Path(args.skip_keys_file)
        if skip_path.exists():
            for line in skip_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                skip_keys.add(line)

    reports: Dict[str, Dict[str, object]] = {}
    selected_keys = set(args.keys) if args.keys else None
    for key, flags in sorted(key_map.items()):
        if selected_keys and key not in selected_keys:
            continue
        if key in skip_keys:
            continue
        if not flags.get("has_ocr"):
            continue
        source_path = source_root / f"{key}.md"
        output_dir = output_root / key
        report = _process_key(key, source_path, output_dir, timestamp)
        if report:
            reports[key] = report

    _write_cleanup_summary(reports, output_root)
    _write_external_audit_report(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
