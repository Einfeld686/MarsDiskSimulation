#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

LINE_REF_PATTERN = re.compile(
    r"(marsdisk/[A-Za-z0-9_/\.-]+\.py):(\d+)(?:[–-](\d+))?"
)

ANCHOR_PATTERN = re.compile(
    r"(marsdisk/[A-Za-z0-9_/\.-]+\.py)#([A-Za-z0-9_\.]+)(?:\s*\[(?:L)?(\d+)(?:[–-](?:L)?(\d+))?\])?"
)

DEFAULT_MARKDOWN_ROOT = REPO_ROOT / "analysis"
DEFAULT_MARKDOWN_GLOB = "**/*.md"
UNRESOLVED_LOG_PATH = REPO_ROOT / "analysis" / "coverage" / "anchor_unresolved.tsv"
MODULE_SENTINEL = "__module__"


@dataclass
class SymbolRange:
    rel_path: str
    symbol: str
    start_line: int
    end_line: int

    @property
    def width(self) -> int:
        return max(0, self.end_line - self.start_line)


@dataclass
class UnresolvedEntry:
    doc_path: Path
    raw_ref: str
    reason: str


@dataclass
class FileChange:
    path: Path
    original: str
    updated: str

    def has_changes(self) -> bool:
        return self.original != self.updated

    def diff(self) -> str:
        if not self.has_changes():
            return ""
        original_lines = self.original.splitlines(keepends=True)
        updated_lines = self.updated.splitlines(keepends=True)
        diff_iter = difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile=f"a/{self.path.relative_to(REPO_ROOT)}",
            tofile=f"b/{self.path.relative_to(REPO_ROOT)}",
        )
        return "".join(diff_iter)

    def write(self) -> None:
        if not self.has_changes():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.updated, encoding="utf-8")


class SymbolResolver:
    """Resolve source symbol ownership for code references."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.inventory_path = repo_root / "analysis" / "inventory.json"
        self.symbols_raw_path = repo_root / "analysis" / "symbols.raw.txt"
        self.inventory = self._load_inventory()
        self.block_symbols = self._load_block_symbols()
        self.ast_cache: Dict[str, Dict[str, Tuple[int, int]]] = {}
        self.symbol_ranges: Dict[str, List[SymbolRange]] = self._build_symbol_ranges()

    def _load_inventory(self) -> List[dict]:
        if not self.inventory_path.exists():
            raise FileNotFoundError(
                f"Missing inventory file: {self.inventory_path}"
            )
        try:
            return json.loads(self.inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse {self.inventory_path}: {exc}") from exc

    def _load_block_symbols(self) -> Dict[str, set[str]]:
        block_symbols: Dict[str, set[str]] = {}
        if not self.symbols_raw_path.exists():
            return block_symbols
        for line in self.symbols_raw_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            rel_path, _, header = parts
            name = self._extract_symbol_name(header)
            if not name:
                continue
            block_symbols.setdefault(rel_path, set()).add(name)
        return block_symbols

    def _extract_symbol_name(self, header: str) -> Optional[str]:
        header = header.strip()
        if header.startswith("def "):
            return header.split()[1].split("(")[0]
        if header.startswith("async def "):
            return header.split()[2].split("(")[0]
        if header.startswith("class "):
            return header.split()[1].split("(")[0].split(":")[0]
        return None

    def _build_symbol_ranges(self) -> Dict[str, List[SymbolRange]]:
        symbols_by_file: Dict[str, List[SymbolRange]] = {}
        grouped: Dict[str, List[dict]] = {}
        for entry in self.inventory:
            grouped.setdefault(entry["file_path"], []).append(entry)

        for rel_path, items in grouped.items():
            entries = sorted(items, key=lambda item: item["line_no"])
            ast_ranges = self._load_ast_ranges(rel_path)
            text_path = self.repo_root / rel_path
            try:
                total_lines = len(text_path.read_text(encoding="utf-8").splitlines())
            except FileNotFoundError:
                total_lines = 0
            except UnicodeDecodeError:
                total_lines = 0

            symbol_ranges: List[SymbolRange] = []
            for entry in entries:
                symbol = entry["symbol"]
                start = entry["line_no"]
                is_block = symbol in self.block_symbols.get(rel_path, set())
                ast_range = ast_ranges.get(symbol)
                if ast_range:
                    start, end = ast_range
                elif is_block:
                    end = self._fallback_block_end(start, entries, total_lines, symbol)
                else:
                    end = start
                symbol_ranges.append(
                    SymbolRange(
                        rel_path=rel_path,
                        symbol=symbol,
                        start_line=start,
                        end_line=end if end >= start else start,
                    )
                )
            symbols_by_file[rel_path] = sorted(
                symbol_ranges, key=lambda s: (s.start_line, s.end_line)
            )
        return symbols_by_file

    def _load_ast_ranges(self, rel_path: str) -> Dict[str, Tuple[int, int]]:
        if rel_path in self.ast_cache:
            return self.ast_cache[rel_path]

        path = self.repo_root / rel_path
        ranges: Dict[str, Tuple[int, int]] = {}
        if not path.exists():
            self.ast_cache[rel_path] = ranges
            return ranges

        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.ast_cache[rel_path] = ranges
            return ranges

        import ast

        try:
            tree = ast.parse(source)
        except SyntaxError:
            self.ast_cache[rel_path] = ranges
            return ranges

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None)
                if start is None:
                    continue
                if end is None:
                    end = start
                ranges[node.name] = (start, end)
        self.ast_cache[rel_path] = ranges
        return ranges

    def _fallback_block_end(
        self,
        start: int,
        entries: List[dict],
        total_lines: int,
        symbol: str,
    ) -> int:
        # Determine end line from the next inventory entry or file length.
        for candidate in entries:
            candidate_start = candidate["line_no"]
            if candidate_start > start:
                return candidate_start - 1
        if total_lines:
            return total_lines
        return start

    # ------------------------------------------------------------------ #
    def find_symbol_covering(
        self,
        rel_path: str,
        start_line: int,
        end_line: Optional[int] = None,
    ) -> Optional[SymbolRange]:
        ranges = self.symbol_ranges.get(rel_path)
        if not ranges:
            ranges = self._ensure_module_symbol(rel_path)
            if not ranges:
                return None
        target_end = end_line if end_line is not None else start_line

        covering = [
            symbol
            for symbol in ranges
            if symbol.start_line <= start_line <= symbol.end_line
            and symbol.start_line <= target_end <= symbol.end_line
        ]
        if covering:
            covering.sort(key=lambda s: (s.width, -s.start_line))
            return covering[0]

        # Fallback: choose the symbol with the largest overlap.
        best_symbol: Optional[SymbolRange] = None
        best_overlap = -1
        for symbol in ranges:
            overlap = self._overlap_length(
                symbol.start_line,
                symbol.end_line,
                start_line,
                target_end,
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_symbol = symbol
            elif overlap == best_overlap and best_symbol is not None:
                if symbol.width < best_symbol.width:
                    best_symbol = symbol
        return best_symbol

    def find_symbol_by_name(self, rel_path: str, symbol_name: str) -> Optional[SymbolRange]:
        ranges = self.symbol_ranges.get(rel_path)
        if not ranges:
            ranges = self._ensure_module_symbol(rel_path)
            if not ranges:
                return None
        for symbol in ranges:
            if symbol.symbol == symbol_name:
                return symbol
        return None

    def _ensure_module_symbol(self, rel_path: str) -> List[SymbolRange]:
        path = self.repo_root / rel_path
        if not path.exists():
            return []
        try:
            total_lines = len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            return []
        if total_lines == 0:
            total_lines = 1
        module_symbol = SymbolRange(
            rel_path=rel_path,
            symbol=MODULE_SENTINEL,
            start_line=1,
            end_line=total_lines,
        )
        existing = self.symbol_ranges.get(rel_path)
        if existing:
            # Avoid duplicating the sentinel if already present.
            if any(symbol.symbol == MODULE_SENTINEL for symbol in existing):
                return existing
            existing.append(module_symbol)
            existing.sort(key=lambda s: (s.start_line, s.end_line))
            return existing
        self.symbol_ranges[rel_path] = [module_symbol]
        return self.symbol_ranges[rel_path]

    def _overlap_length(
        self,
        a_start: int,
        a_end: int,
        b_start: int,
        b_end: int,
    ) -> int:
        lo = max(a_start, b_start)
        hi = min(a_end, b_end)
        if hi < lo:
            return 0
        return hi - lo + 1


class AnchorSync:
    """Perform anchor replacement across analysis markdown files."""

    def __init__(self, *, write: bool, paths: Sequence[Path]) -> None:
        self.write = write
        self.paths = list(paths)
        self.resolver = SymbolResolver(REPO_ROOT)
        self.unresolved: List[UnresolvedEntry] = []

    def run(self) -> Tuple[int, List[FileChange]]:
        changes: List[FileChange] = []
        for path in self.paths:
            original = path.read_text(encoding="utf-8")
            updated = self._rewrite_text(path, original)
            changes.append(FileChange(path, original, updated))

        log_change = self._build_unresolved_log()
        changes.append(log_change)
        return 0, changes

    def _rewrite_text(self, doc_path: Path, text: str) -> str:
        text = ANCHOR_PATTERN.sub(
            lambda match: self._replace_anchor_reference(doc_path, match),
            text,
        )
        text = LINE_REF_PATTERN.sub(
            lambda match: self._replace_line_reference(doc_path, match),
            text,
        )
        return text

    def _replace_line_reference(self, doc_path: Path, match: re.Match[str]) -> str:
        rel_path = match.group(1)
        start = int(match.group(2))
        end_group = match.group(3)
        end = int(end_group) if end_group else None

        symbol = self.resolver.find_symbol_covering(rel_path, start, end)
        if symbol is None:
            self.unresolved.append(
                UnresolvedEntry(
                    doc_path=doc_path,
                    raw_ref=match.group(0),
                    reason="symbol-not-found",
                )
            )
            return match.group(0)

        new_start, new_end = self._clamp_to_symbol(symbol, start, end)
        line_repr = self._format_line_range(new_start, new_end)
        return f"{rel_path}#{symbol.symbol} {line_repr}"

    def _replace_anchor_reference(self, doc_path: Path, match: re.Match[str]) -> str:
        rel_path = match.group(1)
        symbol_name = match.group(2)
        symbol = self.resolver.find_symbol_by_name(rel_path, symbol_name)
        if symbol is None:
            self.unresolved.append(
                UnresolvedEntry(
                    doc_path=doc_path,
                    raw_ref=match.group(0),
                    reason="anchor-symbol-missing",
                )
            )
            return match.group(0)
        req_start = match.group(3)
        req_end = match.group(4)
        start_val = int(req_start) if req_start else symbol.start_line
        end_val = int(req_end) if req_end else (start_val if req_start else symbol.end_line)
        new_start, new_end = self._clamp_to_symbol(symbol, start_val, end_val)
        line_repr = self._format_line_range(new_start, new_end)
        return f"{rel_path}#{symbol.symbol} {line_repr}"

    def _clamp_to_symbol(
        self,
        symbol: SymbolRange,
        requested_start: int,
        requested_end: Optional[int],
    ) -> Tuple[int, int]:
        start = min(max(requested_start, symbol.start_line), symbol.end_line)
        target_end = requested_end if requested_end is not None else requested_start
        end = min(max(target_end, start), symbol.end_line)
        return start, end

    def _format_line_range(self, start: int, end: int) -> str:
        if start == end:
            return f"[L{start}]"
        return f"[L{start}–L{end}]"

    def _build_unresolved_log(self) -> FileChange:
        rows = ["doc_path\traw_ref\treason"]
        for entry in self.unresolved:
            rel_doc = entry.doc_path.relative_to(REPO_ROOT)
            rows.append(
                f"{rel_doc}\t{entry.raw_ref}\t{entry.reason}"
            )
        content = "\n".join(rows) + ("\n" if rows else "")
        original = ""
        if UNRESOLVED_LOG_PATH.exists():
            original = UNRESOLVED_LOG_PATH.read_text(encoding="utf-8")
        return FileChange(UNRESOLVED_LOG_PATH, original, content)


def _discover_markdown_paths(root: Path, pattern: str) -> List[Path]:
    return sorted(path for path in root.glob(pattern) if path.is_file())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replace marsdisk source line references with stable anchors."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes to disk instead of printing diffs.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Specific markdown files to process. Defaults to all analysis/*.md.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(DEFAULT_MARKDOWN_ROOT),
        help="Root directory to search for markdown files.",
    )
    parser.add_argument(
        "--glob",
        type=str,
        default=DEFAULT_MARKDOWN_GLOB,
        help="Glob pattern relative to --root.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.paths:
        markdown_paths = [Path(path).resolve() for path in args.paths]
    else:
        markdown_paths = _discover_markdown_paths(root, args.glob)

    anchor_sync = AnchorSync(write=args.write, paths=markdown_paths)
    exit_code, changes = anchor_sync.run()
    changed = [change for change in changes if change.has_changes()]

    if args.write:
        for change in changed:
            change.write()
        print(f"AnchorSync: wrote {len(changed)} file(s).")
    else:
        for change in changed:
            diff_text = change.diff()
            if diff_text:
                sys.stdout.write(diff_text)
        print(f"AnchorSync (dry-run): {len(changed)} file(s) would change.")

    if anchor_sync.unresolved:
        for entry in anchor_sync.unresolved:
            print(
                f"UNRESOLVED: {entry.doc_path.relative_to(REPO_ROOT)} -> "
                f"{entry.raw_ref} ({entry.reason})",
                file=sys.stderr,
            )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
