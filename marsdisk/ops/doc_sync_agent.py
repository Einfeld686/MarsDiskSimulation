from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Single source for analysis markdown documents (DRY principle)
# ---------------------------------------------------------------------------
_ANALYSIS_MD_DOCS: list[str] = [
    # Core documentation
    "equations.md",
    "overview.md",
    "slides_outline.md",
    "run_catalog.md",
    "figures_catalog.md",
    "glossary.md",
    "literature_map.md",
    "run-recipes.md",
    "sinks_callgraph.md",
    "AI_USAGE.md",
    "CHANGELOG.md",
    # Additional docs with code references requiring line number sync
    "physics_flow.md",
    "introduction.md",
    "methods.md",
    "bibliography.md",
    "assumption_trace.md",
    "config_guide.md",
    "provenance_report.md",
]

# Non-markdown files to sync
_ANALYSIS_DATA_FILES: list[str] = [
    "inventory.json",
    "symbols.raw.txt",
    "symbols.rg.txt",
]

# Default markdown docs to keep in sync (slide-facing files intentionally carry no equations,
# only anchors into analysis/equations.md and catalog IDs).
DEFAULT_DOC_PATHS: list[str] = [
    f"analysis/{name}" for name in _ANALYSIS_MD_DOCS
] + [f"analysis/{name}" for name in _ANALYSIS_DATA_FILES]

RG_PATTERN = r"beta_at_smin|beta_threshold|s_min"
SUMMARY_DEFAULT_PATHS = [
    REPO_ROOT / "analysis" / "outputs" / "baseline_blowout_only" / "summary.json",
    REPO_ROOT / "analysis" / "outputs" / "summary.json",
]

# Pattern matching inline references such as `marsdisk/run.py:123–145`
REF_PATTERN = re.compile(
    r"((?:marsdisk|tests|configs|scripts)/[A-Za-z0-9_/\.-]+\.(?:py|yml|yaml)):(\d+)(?:([–-])(\d+))?"
)

# Pattern for hash-anchor with line numbers: `marsdisk/path.py#symbol [L123–L456]`
HASH_ANCHOR_LINE_PATTERN = re.compile(
    r"\[((?:marsdisk|tests|configs|scripts)/[A-Za-z0-9_/\.-]+\.(?:py|yml|yaml))#([A-Za-z0-9_]+)\s+\[L(\d+)(?:[–—-]L?(\d+))?\]\]"
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
}

DOC_COLON_REF_PATTERN = re.compile(
    r"((?:marsdisk|tests|configs|scripts)/[A-Za-z0-9_/\.-]+\.(?:py|yml|yaml)):(\d+)(?:[–—-](\d+))?"
)
DOC_INLINE_LINE_ANCHOR_PATTERN = re.compile(
    r"\s*[（(]\s*#L(\d+)(?:[–—-](\d+))?\s*[）)]",
    re.IGNORECASE,
)
DOC_LINE_ANCHOR_PATTERN = re.compile(
    r"((?:marsdisk|tests|configs|scripts)/[A-Za-z0-9_/\.-]+\.(?:py|yml|yaml))#L(\d+)(?:[–—-](\d+))?",
    re.IGNORECASE,
)
DOC_SYMBOL_ANCHOR_PATTERN = re.compile(
    r"((?:marsdisk|tests|configs|scripts)/[A-Za-z0-9_/\.-]+\.(?:py|yml|yaml))#(?!L)([A-Za-z0-9_]+)"
)

HEADING_IO_PATTERN = re.compile(r"^## [^\n]*I/O[^\n]*$", re.MULTILINE)
HEADING_RESPONSIBILITIES_PATTERN = re.compile(r"^## [^\n]*責務[^\n]*$", re.MULTILINE)

SUGGESTIONS_DEFAULT_PATH = REPO_ROOT / "analysis" / "suggestions_index.json"
ML_CACHE_PATH = REPO_ROOT / ".cache" / "doc_sync" / "equation_matcher.pkl"
EQUATIONS_PATH_DEFAULT = REPO_ROOT / "analysis" / "equations.md"
OVERVIEW_PATH_DEFAULT = REPO_ROOT / "analysis" / "overview.md"
RUN_RECIPES_PATH_DEFAULT = REPO_ROOT / "analysis" / "run-recipes.md"

# Derive from _ANALYSIS_MD_DOCS to maintain single source of truth
DEFAULT_DOCS_FOR_REFS: list[Path] = [
    REPO_ROOT / "analysis" / name for name in _ANALYSIS_MD_DOCS
]

EQUATION_HEADING_PATTERN = re.compile(r"^### (?:\((E\.\d{3}[a-z]?)\)\s*)?(.*)$")
EQUATION_ID_PATTERN = re.compile(r"^### \(E\.(\d{3}[a-z]?)\)\s*(.*)$")
CODE_REF_PATTERN = re.compile(
    r"\[(marsdisk/[^\]]+\.py)#([A-Za-z0-9_]+)\s+\[L(\d+)[–—-]L?(\d+)?\]\]"
)
LINE_ANCHOR_INLINE_PATTERN = re.compile(r"[（(]#L\d+(?:[–—-]L?\d+)?[）)]")


@dataclass
class SymbolInfo:
    """Container describing code symbols detected in the repository."""

    rel_path: str
    name: str
    kind: str
    line_no: int
    end_line: int
    signature: str
    raw_header: str
    brief_usage: str


@dataclass
class FileChange:
    """Track a prospective file update."""

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


@dataclass
class CodeRef:
    file_path: str
    symbol: str
    line_start: int
    line_end: int


@dataclass
class EquationEntry:
    eq_id: str
    title: str
    code_refs: list[CodeRef] = field(default_factory=list)
    literature_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InventoryRecord:
    """Normalized record describing a top-level symbol."""

    file_path: str
    symbol: str
    kind: str
    line_no: int
    end_line: int
    signature: str
    brief_usage: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "symbol": self.symbol,
            "kind": self.kind,
            "line_no": self.line_no,
            "end_line": self.end_line,
            "signature": self.signature,
            "brief_usage": self.brief_usage,
        }

    @property
    def span(self) -> Tuple[int, int]:
        end = self.end_line if self.end_line >= self.line_no else self.line_no
        return self.line_no, end

    @property
    def is_function(self) -> bool:
        if self.kind in {"function", "async_function"}:
            return True
        if self.signature.startswith(f"{self.symbol}("):
            return True
        return False


class DocSyncAgent:
    """Synchronise analysis documentation artefacts with repository sources."""

    def __init__(
        self,
        *,
        write: bool,
        commit: bool,
        doc_paths: Sequence[str],
    ) -> None:
        self.write = write
        self.commit = commit
        self.requested_paths = set(self._normalise_paths(doc_paths) or DEFAULT_DOC_PATHS)
        self.doc_paths = [path for path in self.requested_paths if path.endswith(".md")]
        self.warnings: list[str] = []
        self.existing_inventory = self._load_existing_inventory()
        self.symbols_by_file: dict[str, list[SymbolInfo]] = {}
        self.summary_data = self._load_summary()
        # File line count cache for performance (improvement #5)
        self._file_line_cache: dict[str, int | None] = {}
        # Check for missing documents at startup (improvement #3)
        self._check_doc_existence()

    def run(self) -> Tuple[int, List[FileChange]]:
        symbols = self._collect_symbols()
        inventory_changes = self._update_inventory(symbols)
        raw_changes = self._update_symbols_raw(symbols)
        rg_changes = self._update_symbols_rg()
        doc_changes = self._update_docs(symbols)

        changes: List[FileChange] = []
        changes.extend(inventory_changes)
        changes.extend(raw_changes)
        changes.extend(rg_changes)
        changes.extend(doc_changes)

        return 0, [change for change in changes if change.has_changes()]

    # --------------------------------------------------------------------- #
    # Symbol collection
    # --------------------------------------------------------------------- #
    def _collect_symbols(self) -> List[SymbolInfo]:
        symbols: List[SymbolInfo] = []
        for path in sorted(REPO_ROOT.rglob("*.py")):
            if self._should_skip(path):
                continue
            rel_path = path.relative_to(REPO_ROOT)
            file_symbols = self._collect_symbols_from_python(path, rel_path)
            if file_symbols:
                self.symbols_by_file[str(rel_path)] = file_symbols
                symbols.extend(file_symbols)
        symbols.sort(key=lambda s: (s.rel_path, s.line_no, s.name))
        return symbols

    def _should_skip(self, path: Path) -> bool:
        parts = set(path.parts)
        if parts & SKIP_DIR_NAMES:
            return True
        return False

    def _collect_symbols_from_python(
        self,
        path: Path,
        rel_path: Path,
    ) -> List[SymbolInfo]:
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.warnings.append(f"Skipping non-text file: {rel_path}")
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self.warnings.append(f"Failed to parse {rel_path}: {exc}")
            return []

        symbols: List[SymbolInfo] = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    self._symbol_from_function(node, rel_path, async_kind=False)
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    self._symbol_from_function(node, rel_path, async_kind=True)
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(self._symbol_from_class(node, rel_path))
            elif isinstance(node, ast.Assign):
                symbols.extend(self._symbols_from_assign(node, rel_path))
            elif isinstance(node, ast.AnnAssign):
                sym = self._symbol_from_ann_assign(node, rel_path)
                if sym:
                    symbols.append(sym)
        symbols.sort(key=lambda s: (s.rel_path, s.line_no, s.name))
        return symbols

    def _symbol_from_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        rel_path: Path,
        *,
        async_kind: bool,
    ) -> SymbolInfo:
        args_src = ast.unparse(node.args)
        signature = f"{node.name}({args_src})"
        if node.returns is not None:
            signature += f" -> {ast.unparse(node.returns)}"
        raw_header = (
            f"{'async def' if async_kind else 'def'} {signature}"
        )
        brief = self._extract_docstring(rel_path, node.name, node)
        end_line = getattr(node, "end_lineno", node.lineno)
        return SymbolInfo(
            rel_path=str(rel_path),
            name=node.name,
            kind="async_function" if async_kind else "function",
            line_no=node.lineno,
            end_line=end_line,
            signature=signature,
            raw_header=raw_header,
            brief_usage=brief,
        )

    def _symbol_from_class(self, node: ast.ClassDef, rel_path: Path) -> SymbolInfo:
        if node.bases:
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            signature = f"class {node.name}({bases})"
        else:
            signature = f"class {node.name}"
        brief = self._extract_docstring(rel_path, node.name, node)
        end_line = getattr(node, "end_lineno", node.lineno)
        return SymbolInfo(
            rel_path=str(rel_path),
            name=node.name,
            kind="class",
            line_no=node.lineno,
            end_line=end_line,
            signature=signature,
            raw_header=signature,
            brief_usage=brief,
        )

    def _symbols_from_assign(
        self,
        node: ast.Assign,
        rel_path: Path,
    ) -> List[SymbolInfo]:
        symbols: List[SymbolInfo] = []
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                value_src = ast.unparse(node.value) if node.value else "..."
                signature = f"{target.id} = {value_src}"
                brief = self._fallback_brief(rel_path, target.id, "Module constant")
                symbols.append(
                    SymbolInfo(
                        rel_path=str(rel_path),
                        name=target.id,
                        kind="constant",
                        line_no=target.lineno,
                        end_line=target.lineno,
                        signature=signature,
                        raw_header=signature,
                        brief_usage=brief,
                    )
                )
        return symbols

    def _symbol_from_ann_assign(
        self,
        node: ast.AnnAssign,
        rel_path: Path,
    ) -> Optional[SymbolInfo]:
        target = node.target
        if not isinstance(target, ast.Name) or not target.id.isupper():
            return None
        annotation = ast.unparse(node.annotation) if node.annotation else "Any"
        signature = f"{target.id}: {annotation}"
        if node.value is not None:
            signature += f" = {ast.unparse(node.value)}"
        brief = self._fallback_brief(rel_path, target.id, "Module constant")
        return SymbolInfo(
            rel_path=str(rel_path),
            name=target.id,
            kind="constant",
            line_no=node.lineno,
            end_line=node.lineno,
            signature=signature,
            raw_header=signature,
            brief_usage=brief,
        )

    def _extract_docstring(
        self,
        rel_path: Path,
        symbol_name: str,
        node: ast.AST,
    ) -> str:
        docstring = ast.get_docstring(node, clean=True)
        if docstring:
            return docstring.splitlines()[0].strip()
        return self._fallback_brief(rel_path, symbol_name, "No description available.")

    def _fallback_brief(
        self,
        rel_path: Path,
        symbol_name: str,
        default_text: str,
    ) -> str:
        existing = self.existing_inventory.get((str(rel_path), symbol_name))
        if existing:
            brief = existing.get("brief_usage", "").strip()
            if brief:
                return brief
        return default_text

    # --------------------------------------------------------------------- #
    # Inventory and symbol files
    # --------------------------------------------------------------------- #
    def _update_inventory(self, symbols: List[SymbolInfo]) -> List[FileChange]:
        rel_target = "analysis/inventory.json"
        if rel_target not in self.requested_paths:
            return []
        inventory_path = REPO_ROOT / rel_target
        items = [
            {
                "file_path": symbol.rel_path,
                "line_no": symbol.line_no,
                "symbol": symbol.name,
                "signature": symbol.signature,
                "brief_usage": symbol.brief_usage,
            }
            for symbol in symbols
        ]
        new_content = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
        original = self._read_file_text(inventory_path)
        return [FileChange(inventory_path, original, new_content)]

    def _update_symbols_raw(self, symbols: List[SymbolInfo]) -> List[FileChange]:
        rel_target = "analysis/symbols.raw.txt"
        if rel_target not in self.requested_paths:
            return []
        raw_path = REPO_ROOT / rel_target
        lines = [
            f"{symbol.rel_path}:{symbol.line_no}:{symbol.raw_header}"
            for symbol in symbols
            if symbol.kind in {"function", "async_function", "class"}
        ]
        new_content = "\n".join(lines) + ("\n" if lines else "")
        original = self._read_file_text(raw_path)
        return [FileChange(raw_path, original, new_content)]

    def _update_symbols_rg(self) -> List[FileChange]:
        rel_target = "analysis/symbols.rg.txt"
        if rel_target not in self.requested_paths:
            return []
        rg_path = REPO_ROOT / rel_target
        try:
            result = subprocess.run(
                [
                    "rg",
                    "--color",
                    "never",
                    "--no-heading",
                    "--line-number",
                    "--glob",
                    "!analysis/symbols.rg.txt",
                    "--glob",
                    "!.venv/**",
                    "--glob",
                    "!venv/**",
                    "--glob",
                    "!env/**",
                    "--glob",
                    "!node_modules/**",
                    "--glob",
                    "!build/**",
                    "--glob",
                    "!dist/**",
                    RG_PATTERN,
                    ".",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.warnings.append("rg command not found; skipping symbols.rg.txt update.")
            return []

        if result.returncode not in {0, 1}:
            self.warnings.append(
                f"rg invocation failed with exit code {result.returncode}: {result.stderr.strip()}"
            )
            return []

        content = result.stdout
        if content and not content.endswith("\n"):
            content += "\n"
        original = self._read_file_text(rg_path)
        return [FileChange(rg_path, original, content)]

    # --------------------------------------------------------------------- #
    # Documentation updates
    # --------------------------------------------------------------------- #
    def _update_docs(self, symbols: List[SymbolInfo]) -> List[FileChange]:
        doc_changes: List[FileChange] = []
        doc_texts: Dict[str, str] = {}

        for rel_str in sorted(self.doc_paths):
            path = REPO_ROOT / rel_str
            if not path.exists():
                self.warnings.append(f"Document not found: {rel_str}")
                continue
            original = path.read_text(encoding="utf-8")
            updated = self._rewrite_references(original)
            self._check_summary_fields(rel_str, updated)
            doc_texts[rel_str] = updated
            doc_changes.append(FileChange(path, original, updated))

        # Cross-document consistency check
        run_doc = doc_texts.get("analysis/run-recipes.md")
        sinks_doc = doc_texts.get("analysis/sinks_callgraph.md")
        if run_doc and sinks_doc:
            self._check_sink_consistency(run_doc, sinks_doc)

        return doc_changes

    def _rewrite_references(self, text: str) -> str:
        def replace_colon_ref(match: re.Match[str]) -> str:
            path_str = match.group(1)
            start = int(match.group(2))
            dash = match.group(3) or "–"
            end_str = match.group(4)
            end = int(end_str) if end_str else None
            new_start, new_end = self._resolve_reference(path_str, start, end)
            if new_start is None:
                return match.group(0)
            if end is not None:
                return f"{path_str}:{new_start}{dash}{new_end}"
            if new_end and new_end != new_start:
                return f"{path_str}:{new_start}{dash}{new_end}"
            return f"{path_str}:{new_start}"

        def replace_hash_anchor(match: re.Match[str]) -> str:
            """Handle [path#symbol [L123–L456]] format (improvement #2)."""
            path_str = match.group(1)
            symbol_name = match.group(2)
            old_start = int(match.group(3))
            old_end_str = match.group(4)
            old_end = int(old_end_str) if old_end_str else old_start

            # Try to find the symbol in the file
            symbols = self.symbols_by_file.get(path_str)
            if symbols:
                matching = [s for s in symbols if s.name == symbol_name]
                if matching:
                    sym = matching[0]
                    new_start = sym.line_no
                    new_end = sym.end_line or sym.line_no
                    if new_start == new_end:
                        return f"[{path_str}#{symbol_name} [L{new_start}]]"
                    return f"[{path_str}#{symbol_name} [L{new_start}–L{new_end}]]"
            
            # Fallback: clamp to file bounds
            new_start, new_end = self._clamp_to_file(path_str, old_start, old_end)
            if new_start is None:
                return match.group(0)
            if new_start == new_end:
                return f"[{path_str}#{symbol_name} [L{new_start}]]"
            return f"[{path_str}#{symbol_name} [L{new_start}–L{new_end}]]"

        # First pass: colon-style references (path:123–456)
        text = REF_PATTERN.sub(replace_colon_ref, text)
        # Second pass: hash-anchor with line numbers [path#symbol [L123–L456]]
        text = HASH_ANCHOR_LINE_PATTERN.sub(replace_hash_anchor, text)
        return text

    def _resolve_reference(
        self,
        rel_path: str,
        approx_start: int,
        approx_end: Optional[int],
    ) -> Tuple[Optional[int], Optional[int]]:
        symbols = self.symbols_by_file.get(rel_path)
        if not symbols:
            return self._clamp_to_file(rel_path, approx_start, approx_end)

        covering = [
            s
            for s in symbols
            if s.line_no <= approx_start <= (s.end_line or s.line_no)
        ]
        if approx_end is not None:
            covering_end = [
                s
                for s in symbols
                if s.line_no <= approx_end <= (s.end_line or s.line_no)
            ]
            if covering_end:
                covering.extend(
                    s for s in covering_end if s not in covering
                )
        if covering:
            best_symbol = min(covering, key=lambda s: approx_start - s.line_no)
        else:
            best_symbol = min(symbols, key=lambda s: abs(s.line_no - approx_start))
        end_line = best_symbol.end_line or best_symbol.line_no
        start = min(max(best_symbol.line_no, approx_start), end_line)
        if approx_end is None:
            return start, start
        end_target = max(approx_end, start)
        end = min(end_target, end_line)
        if end < start:
            end = start
        return start, end

    def _clamp_to_file(
        self,
        rel_path: str,
        approx_start: int,
        approx_end: Optional[int],
    ) -> Tuple[Optional[int], Optional[int]]:
        # Use cache for file line counts (improvement #5)
        if rel_path not in self._file_line_cache:
            file_path = REPO_ROOT / rel_path
            if not file_path.exists():
                self.warnings.append(f"Referenced file missing: {rel_path}")
                self._file_line_cache[rel_path] = None
            else:
                try:
                    self._file_line_cache[rel_path] = len(
                        file_path.read_text(encoding="utf-8").splitlines()
                    )
                except UnicodeDecodeError:
                    self._file_line_cache[rel_path] = None
        
        line_count = self._file_line_cache[rel_path]
        if line_count is None:
            return None, None
        
        start = max(1, min(approx_start, line_count))
        if approx_end is None:
            return start, start
        end_target = max(approx_end, start)
        end = max(start, min(end_target, line_count))
        return start, end

    def _check_summary_fields(self, rel_path: str, text: str) -> None:
        if not self.summary_data:
            return
        # Mode-conditional fields only present in certain run modes (e.g. deep_mixing)
        mode_conditional_fields = {
            "t_mix_orbits",
            "supply_transport_mode",
        }
        summary_keys = set(self.summary_data.keys())
        for line in text.splitlines():
            if "summary" not in line:
                continue
            for token in re.findall(r"`([^`]+)`", line):
                lowered = token.lower()
                if lowered.startswith("summary"):
                    continue
                if token in summary_keys:
                    continue
                if token in mode_conditional_fields:
                    continue
                if any(prefix in lowered for prefix in ("beta", "s_min", "t_m", "rho", "q_pr", "case_status", "m_loss")):
                    self.warnings.append(
                        f"{rel_path}: summary.json is missing field '{token}'"
                    )

    def _check_sink_consistency(self, run_doc: str, sinks_doc: str) -> None:
        run_tokens = self._extract_sink_tokens(run_doc)
        sink_tokens = self._extract_sink_tokens(sinks_doc)
        if not run_tokens or not sink_tokens:
            return
        extra_run = sorted(run_tokens - sink_tokens)
        extra_sinks = sorted(sink_tokens - run_tokens)
        if extra_run:
            self.warnings.append(
                "run-recipes.md references sink tokens not documented in sinks_callgraph.md: "
                + ", ".join(extra_run)
            )
        if extra_sinks:
            self.warnings.append(
                "sinks_callgraph.md references sink tokens not present in run-recipes.md: "
                + ", ".join(extra_sinks)
            )

    def _extract_sink_tokens(self, text: str) -> set[str]:
        tokens = set()
        for token in re.findall(r"`([^`]+)`", text):
            if "sink" in token.lower():
                cleaned = token.strip()
                if not cleaned or "\n" in cleaned:
                    continue
                tokens.add(cleaned)
        return tokens

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _check_doc_existence(self) -> None:
        """Check for missing documents at startup and log warnings (improvement #3)."""
        missing: list[str] = []
        for rel_str in sorted(self.doc_paths):
            path = REPO_ROOT / rel_str
            if not path.exists():
                missing.append(rel_str)
        if missing:
            self.warnings.append(
                f"Documents not found (will be skipped): {', '.join(missing)}"
            )

    def _normalise_paths(self, paths: Sequence[str]) -> list[str]:
        normalised: list[str] = []
        for entry in paths:
            if "," in entry:
                parts = [part.strip() for part in entry.split(",") if part.strip()]
            else:
                parts = [entry]
            for part in parts:
                if part:
                    normalised.append(part)
        return normalised

    def _load_existing_inventory(self) -> Dict[Tuple[str, str], Dict[str, str]]:
        inventory_path = REPO_ROOT / "analysis" / "inventory.json"
        if not inventory_path.exists():
            return {}
        try:
            data = json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return {(item["file_path"], item["symbol"]): item for item in data}

    def _load_summary(self) -> Optional[Dict[str, object]]:
        for path in SUMMARY_DEFAULT_PATHS:
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    self.warnings.append(f"Failed to parse summary.json at {path}: {exc}")
                    return None
        self.warnings.append("No summary.json found in analysis/outputs/ directories.")
        return None

    def _read_file_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")


def _legacy_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronise analysis documentation.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all synchronisation steps (default behaviour).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show diffs without modifying files instead of writing.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Apply the computed changes to disk.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help='After writing, run "git commit -am \'docs: sync analysis\'".',
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=DEFAULT_DOC_PATHS,
        help="Subset of documentation files to refresh.",
    )
    args = parser.parse_args(argv)

    if args.write and args.dry_run:
        parser.error("Cannot combine --write with --dry-run.")
    if args.commit and not args.write:
        parser.error("--commit requires --write.")

    doc_paths: Sequence[str] = args.paths or DEFAULT_DOC_PATHS

    agent = DocSyncAgent(
        write=args.write,
        commit=args.commit,
        doc_paths=doc_paths,
    )
    exit_code, changes = agent.run()

    if args.write:
        for change in changes:
            change.write()
        if agent.commit and changes:
            _git_commit(changes)
        # Improvement #8: Show list of modified files
        if changes:
            changed_names = [change.path.name for change in changes]
            print(f"DocSyncAgent: wrote {len(changes)} files: {', '.join(changed_names)}")
        else:
            print("DocSyncAgent: no changes detected.")
    else:
        if changes:
            for change in changes:
                diff_text = change.diff()
                if diff_text:
                    sys.stdout.write(diff_text)
            print(f"DocSyncAgent (dry-run): {len(changes)} file(s) would change.")
        else:
            print("DocSyncAgent (dry-run): no changes detected.")

    for warning in agent.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    return exit_code


def _collect_inventory_records(root: Path) -> List[InventoryRecord]:
    root = root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Scan root does not exist: {root}")
    agent = DocSyncAgent(write=False, commit=False, doc_paths=[])
    symbols = agent._collect_symbols()

    records: List[InventoryRecord] = []
    for symbol in symbols:
        rel_path = symbol.rel_path
        if not rel_path.startswith("marsdisk/"):
            continue
        if "/tests/" in rel_path or rel_path.startswith("marsdisk/tests"):
            continue
        abs_path = (REPO_ROOT / rel_path).resolve()
        try:
            abs_path.relative_to(root)
        except ValueError:
            continue
        if any(part.startswith(".") for part in Path(rel_path).parts):
            continue
        if symbol.kind not in {"function", "async_function", "class"}:
            continue
        end_line = symbol.end_line if symbol.end_line and symbol.end_line >= symbol.line_no else symbol.line_no
        records.append(
            InventoryRecord(
                file_path=rel_path,
                symbol=symbol.name,
                kind=symbol.kind,
                line_no=symbol.line_no,
                end_line=end_line,
                signature=symbol.signature,
                brief_usage=symbol.brief_usage,
            )
        )

    records.sort(key=lambda rec: (rec.file_path, rec.line_no, rec.symbol))
    return records


def _resolve_cli_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _cmd_scan(args: argparse.Namespace) -> int:
    root = _resolve_cli_path(args.root)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"--root must point to an existing directory (got {root})")
    records = _collect_inventory_records(root)
    output_path = _resolve_cli_path(args.write_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.to_json() for record in records]
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"scan: wrote {len(records)} symbols to {_rel_to_repo(output_path)}")
    return 0


def _collect_doc_references(doc_paths: Sequence[Path]) -> Dict[str, Any]:
    colon_refs: List[Dict[str, Any]] = []
    line_anchors: List[Dict[str, Any]] = []
    symbol_anchors: List[Dict[str, Any]] = []

    duplicate_counts = {"colon": 0, "line_anchor": 0, "symbol_anchor": 0}
    reversed_line_anchor_count = 0

    colon_seen: set[Tuple[str, str, int, int]] = set()
    line_anchor_seen: set[Tuple[str, str, int, int]] = set()
    symbol_anchor_seen: set[Tuple[str, str, str]] = set()

    for doc_path in doc_paths:
        rel_doc = _rel_to_repo(doc_path)
        text = doc_path.read_text(encoding="utf-8")

        for match in DOC_COLON_REF_PATTERN.finditer(text):
            target = match.group(1)
            start = int(match.group(2))
            end_str = match.group(3)
            end = int(end_str) if end_str else start
            if end < start:
                start, end = end, start
            key = (rel_doc, target, start, end)
            if key in colon_seen:
                duplicate_counts["colon"] += 1
            else:
                colon_seen.add(key)
                colon_refs.append(
                    {
                        "doc_path": rel_doc,
                        "target_path": target,
                        "line_start": start,
                        "line_end": end,
                    }
                )

            inline = DOC_INLINE_LINE_ANCHOR_PATTERN.match(text, match.end())
            if inline:
                anchor_start = int(inline.group(1))
                anchor_end_str = inline.group(2)
                anchor_end = int(anchor_end_str) if anchor_end_str else anchor_start
                reversed_flag = anchor_end < anchor_start
                if reversed_flag:
                    reversed_line_anchor_count += 1
                norm_start = min(anchor_start, anchor_end)
                norm_end = max(anchor_start, anchor_end)
                anchor_key = (rel_doc, target, norm_start, norm_end)
                if anchor_key in line_anchor_seen:
                    duplicate_counts["line_anchor"] += 1
                else:
                    line_anchor_seen.add(anchor_key)
                    line_anchors.append(
                        {
                            "doc_path": rel_doc,
                            "target_path": target,
                            "line_start": norm_start,
                            "line_end": norm_end,
                            "reversed": reversed_flag,
                        }
                    )

        for match in DOC_LINE_ANCHOR_PATTERN.finditer(text):
            target = match.group(1)
            start = int(match.group(2))
            end_str = match.group(3)
            end = int(end_str) if end_str else start
            reversed_flag = end < start
            if reversed_flag:
                reversed_line_anchor_count += 1
            norm_start = min(start, end)
            norm_end = max(start, end)
            key = (rel_doc, target, norm_start, norm_end)
            if key in line_anchor_seen:
                duplicate_counts["line_anchor"] += 1
                continue
            line_anchor_seen.add(key)
            line_anchors.append(
                {
                    "doc_path": rel_doc,
                    "target_path": target,
                    "line_start": norm_start,
                    "line_end": norm_end,
                    "reversed": reversed_flag,
                }
            )

        for match in DOC_SYMBOL_ANCHOR_PATTERN.finditer(text):
            target = match.group(1)
            symbol = match.group(2)
            key = (rel_doc, target, symbol)
            if key in symbol_anchor_seen:
                duplicate_counts["symbol_anchor"] += 1
                continue
            symbol_anchor_seen.add(key)
            symbol_anchors.append(
                {
                    "doc_path": rel_doc,
                    "target_path": target,
                    "symbol": symbol,
                }
            )

    colon_refs.sort(key=lambda item: (item["target_path"], item["line_start"], item["doc_path"]))
    line_anchors.sort(
        key=lambda item: (item["target_path"], item["line_start"], item["line_end"], item["doc_path"])
    )
    symbol_anchors.sort(key=lambda item: (item["target_path"], item["symbol"], item["doc_path"]))

    stats = {
        "colon_total": len(colon_refs),
        "line_anchor_total": len(line_anchors),
        "symbol_anchor_total": len(symbol_anchors),
        "duplicate_counts": duplicate_counts,
        "reversed_line_anchor_count": reversed_line_anchor_count,
    }
    documents = sorted({_rel_to_repo(path) for path in doc_paths})
    return {
        "documents": documents,
        "colon": colon_refs,
        "line_anchors": line_anchors,
        "symbol_anchors": symbol_anchors,
        "stats": stats,
    }


def _cmd_refs(args: argparse.Namespace) -> int:
    doc_paths = [_resolve_cli_path(doc) for doc in args.docs]
    missing = [path for path in doc_paths if not path.exists()]
    if missing:
        missing_str = ", ".join(str(path) for path in missing)
        raise SystemExit(f"--docs contains non-existent paths: {missing_str}")
    payload = _collect_doc_references(doc_paths)
    output_path = _resolve_cli_path(args.write_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    stats = payload["stats"]
    print(
        "refs: scanned "
        f"{len(payload['documents'])} docs, "
        f"{stats['symbol_anchor_total']} symbol anchors, "
        f"{stats['line_anchor_total']} line anchors → {_rel_to_repo(output_path)}"
    )
    return 0


def _load_inventory_records(path: Path) -> List[InventoryRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("inventory.json must contain a list of records.")

    records: List[InventoryRecord] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file_path")
        symbol = entry.get("symbol")
        if not file_path or not symbol:
            continue
        kind = entry.get("kind")
        signature = entry.get("signature", "")
        if not kind:
            if signature.startswith("class "):
                kind = "class"
            else:
                kind = "function"
        line_no = int(entry.get("line_no", 0) or 0)
        end_line = int(entry.get("end_line", line_no) or line_no)
        records.append(
            InventoryRecord(
                file_path=file_path,
                symbol=symbol,
                kind=kind,
                line_no=line_no,
                end_line=end_line,
                signature=signature,
                brief_usage=entry.get("brief_usage", ""),
            )
        )

    records.sort(key=lambda rec: (rec.file_path, rec.line_no, rec.symbol))
    return records


def _match_symbol_by_span(
    symbols: Sequence[InventoryRecord],
    start: int,
    end: int,
) -> Optional[InventoryRecord]:
    for record in symbols:
        sym_start, sym_end = record.span
        if end >= sym_start and start <= sym_end:
            return record
    return None


def _compute_coverage(
    inventory: Sequence[InventoryRecord],
    docs_payload: Dict[str, Any],
) -> Dict[str, Any]:
    symbols_by_name: Dict[Tuple[str, str], InventoryRecord] = {}
    functions_all_by_file: Dict[str, List[InventoryRecord]] = defaultdict(list)
    coverage_records_by_file: Dict[str, List[InventoryRecord]] = defaultdict(list)
    coverage_keys: set[Tuple[str, str]] = set()

    for record in inventory:
        if not record.file_path.startswith("marsdisk/"):
            continue
        symbols_by_name[(record.file_path, record.symbol)] = record
        if "/tests/" in record.file_path or record.file_path.startswith("marsdisk/tests"):
            continue
        if not record.is_function:
            continue
        functions_all_by_file[record.file_path].append(record)
        if record.symbol.startswith("_"):
            continue
        coverage_records_by_file[record.file_path].append(record)
        coverage_keys.add((record.file_path, record.symbol))

    for records in functions_all_by_file.values():
        records.sort(key=lambda rec: rec.line_no)
    for records in coverage_records_by_file.values():
        records.sort(key=lambda rec: rec.line_no)

    referenced_keys: set[Tuple[str, str]] = set()

    def mark_referenced(record: InventoryRecord) -> None:
        key = (record.file_path, record.symbol)
        if key in coverage_keys:
            referenced_keys.add(key)

    for ref in docs_payload.get("colon", []):
        target = ref["target_path"]
        start = int(ref["line_start"])
        end = int(ref["line_end"])
        symbols = functions_all_by_file.get(target)
        if not symbols:
            continue
        match = _match_symbol_by_span(symbols, start, end)
        if match:
            mark_referenced(match)

    for ref in docs_payload.get("line_anchors", []):
        target = ref["target_path"]
        start = int(ref["line_start"])
        end = int(ref["line_end"])
        symbols = functions_all_by_file.get(target)
        if not symbols:
            continue
        match = _match_symbol_by_span(symbols, start, end)
        if match:
            mark_referenced(match)

    symbol_anchors = docs_payload.get("symbol_anchors", [])
    resolved_symbol_anchors = 0
    unresolved_symbol_anchors: List[Dict[str, Any]] = []
    for ref in symbol_anchors:
        key = (ref["target_path"], ref["symbol"])
        record = symbols_by_name.get(key)
        if record:
            if record.is_function and record.file_path in functions_all_by_file:
                mark_referenced(record)
            resolved_symbol_anchors += 1
        else:
            unresolved_symbol_anchors.append(ref)

    function_total = sum(len(records) for records in coverage_records_by_file.values())
    function_referenced = len(referenced_keys)
    function_reference_rate = (
        function_referenced / function_total if function_total else 1.0
    )

    per_file_entries: List[Dict[str, Any]] = []
    gap_candidates: List[Tuple[float, int, int, str]] = []
    for file_path, records in sorted(coverage_records_by_file.items()):
        total = len(records)
        referenced = sum(
            1 for record in records if (record.file_path, record.symbol) in referenced_keys
        )
        rate = referenced / total if total else 0.0
        unreferenced_names = [
            record.symbol
            for record in records
            if (record.file_path, record.symbol) not in referenced_keys
        ]
        per_file_entries.append(
            {
                "file_path": file_path,
                "functions_referenced": referenced,
                "functions_total": total,
                "coverage_rate": rate,
                "unreferenced": unreferenced_names,
            }
        )
        for record in records:
            key = (record.file_path, record.symbol)
            if key not in referenced_keys:
                gap_candidates.append(
                    (
                        rate,
                        -total,
                        record.line_no,
                        f"{file_path}#{record.symbol}",
                    )
                )

    per_file_entries.sort(key=lambda item: (item["coverage_rate"], item["file_path"]))
    gap_candidates.sort()
    top_gaps = [item[3] for item in gap_candidates]

    stats = docs_payload.get("stats", {})
    duplicate_counts = stats.get("duplicate_counts", {})
    duplicate_anchor_count = int(duplicate_counts.get("line_anchor", 0)) + int(
        duplicate_counts.get("symbol_anchor", 0)
    )
    reversed_line_anchor_count = int(stats.get("reversed_line_anchor_count", 0))

    total_symbol_anchors = len(symbol_anchors)
    anchor_rate = (
        resolved_symbol_anchors / total_symbol_anchors
        if total_symbol_anchors
        else 1.0
    )
    invalid_anchor_count = len(unresolved_symbol_anchors) + reversed_line_anchor_count

    coverage_data = {
        "function_total": function_total,
        "function_referenced": function_referenced,
        "function_reference_rate": function_reference_rate,
        "anchor_consistency_rate": {
            "numerator": resolved_symbol_anchors,
            "denominator": total_symbol_anchors,
            "rate": anchor_rate,
        },
        "invalid_anchor_count": invalid_anchor_count,
        "duplicate_anchor_count": duplicate_anchor_count,
        "line_anchor_reversed_count": reversed_line_anchor_count,
        "per_file": per_file_entries,
        "top_gaps": top_gaps,
    }
    return coverage_data


def _parse_gap_identifier(identifier: str) -> Optional[Tuple[str, str]]:
    if "#" not in identifier:
        return None
    parts = identifier.split("#", 1)
    if len(parts) != 2:
        return None
    file_path, symbol = parts
    if not file_path or not symbol:
        return None
    return file_path, symbol


def _collect_unreferenced_from_coverage(
    coverage_data: Dict[str, Any],
) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []

    seen: set[Tuple[str, str]] = set()
    for raw in coverage_data.get("top_gaps", []):
        parsed = _parse_gap_identifier(raw)
        if parsed and parsed not in seen:
            seen.add(parsed)
            entries.append(parsed)

    if not entries:
        for per_file in coverage_data.get("per_file", []):
            file_path = per_file.get("file_path")
            if not file_path:
                continue
            for name in per_file.get("unreferenced", []):
                key = (file_path, name)
                if key not in seen:
                    seen.add(key)
                    entries.append(key)
    return entries


def _load_suggestions_index(path: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    suggestions: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if not path.exists():
        return suggestions
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return suggestions
    for raw_key, meta in payload.items():
        if not isinstance(meta, dict):
            continue
        file_path = meta.get("file")
        symbol = meta.get("symbol")
        doc = meta.get("suggested_doc")
        if not file_path or not symbol or not doc:
            continue
        suggestions[(file_path, symbol)] = {
            "suggested_doc": doc,
            "patch": meta.get("patch"),
        }
    return suggestions


def _format_code_anchor(record: InventoryRecord) -> str:
    start, end = record.span
    if start == end:
        return f"[{record.file_path}:{start}]"
    return f"[{record.file_path}:{start}–{end}]"


def _strip_line_anchor_annotations(text: str) -> str:
    return LINE_ANCHOR_INLINE_PATTERN.sub("", text)


def ensure_equation_ids(equations_path: Path) -> None:
    if not equations_path.exists():
        return
    original_text = equations_path.read_text(encoding="utf-8")
    if not original_text:
        return
    cleaned_text = _strip_line_anchor_annotations(original_text)
    lines = cleaned_text.splitlines()
    existing_map: Dict[str, int] = {}
    max_existing = 0

    for line in lines:
        match = EQUATION_HEADING_PATTERN.match(line)
        if not match:
            continue
        eq_id = match.group(1)
        rest = match.group(2).strip()
        if not rest:
            continue
        if eq_id:
            try:
                number = int(eq_id.split(".")[1])
            except (IndexError, ValueError):
                continue
            existing_map[rest] = number
            max_existing = max(max_existing, number)

    next_id = max_existing
    updated_lines: List[str] = []
    for line in lines:
        match = EQUATION_HEADING_PATTERN.match(line)
        if not match:
            updated_lines.append(line)
            continue
        rest = match.group(2).strip()
        if not rest:
            updated_lines.append(line)
            continue
        eq_id = match.group(1)
        if eq_id:
            try:
                number = existing_map.get(rest, int(eq_id.split(".")[1]))
            except (IndexError, ValueError):
                next_id += 1
                number = next_id
        else:
            next_id += 1
            number = next_id
            existing_map[rest] = number
        updated_lines.append(f"### (E.{number:03d}) {rest}")

    updated_text = "\n".join(updated_lines)
    if cleaned_text.endswith("\n"):
        updated_text += "\n"
    else:
        updated_text += "\n"

    if updated_text != original_text:
        equations_path.write_text(updated_text, encoding="utf-8")


def _parse_equations_md(path: Path) -> List[EquationEntry]:
    if not path.exists():
        raise SystemExit(f"equations file not found: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries: List[EquationEntry] = []
    current_start = None
    current_meta: Optional[Tuple[str, str]] = None

    for idx, line in enumerate(lines):
        match = EQUATION_ID_PATTERN.match(line)
        if match:
            if current_meta is not None and current_start is not None:
                block = "\n".join(lines[current_start:idx])
                entries.append(_build_equation_entry(current_meta, block))
            eq_id, title = match.group(1), match.group(2).strip()
            current_meta = (eq_id, title)
            current_start = idx + 1
    if current_meta is not None and current_start is not None:
        block = "\n".join(lines[current_start:])
        entries.append(_build_equation_entry(current_meta, block))
    return entries


def _build_equation_entry(meta: Tuple[str, str], block: str) -> EquationEntry:
    eq_id, title = meta
    code_refs: list[CodeRef] = []
    for ref_match in CODE_REF_PATTERN.finditer(block):
        file_path, symbol, start, end = ref_match.groups()
        line_start = int(start)
        line_end = int(end) if end else line_start
        code_refs.append(
            CodeRef(
                file_path=file_path,
                symbol=symbol,
                line_start=line_start,
                line_end=line_end,
            )
        )
    literature_refs = re.findall(r"\[@([^\]]+)\]", block)
    return EquationEntry(eq_id=eq_id, title=title, code_refs=code_refs, literature_refs=literature_refs)


def _compute_equation_code_map(
    equations: Sequence[EquationEntry],
    inventory: Sequence[InventoryRecord],
) -> Dict[str, Any]:
    index = {
        (record.file_path, record.symbol): record
        for record in inventory
        if record.kind in {"function", "async_function", "class", "method"}
    }
    referenced: set[Tuple[str, str]] = set()
    equations_payload: list[Dict[str, Any]] = []
    warnings: list[str] = []

    for entry in equations:
        refs_payload: list[Dict[str, Any]] = []
        has_valid = False
        for ref in entry.code_refs:
            key = (ref.file_path, ref.symbol)
            is_valid = key in index
            if is_valid:
                has_valid = True
                referenced.add(key)
            refs_payload.append(
                {
                    "file": ref.file_path,
                    "symbol": ref.symbol,
                    "line_start": ref.line_start,
                    "line_end": ref.line_end,
                    "valid": is_valid,
                }
            )
        if not has_valid:
            warnings.append(f"{entry.eq_id}: no valid code reference")
        equations_payload.append(
            {
                "eq_id": entry.eq_id,
                "title": entry.title,
                "code_refs": refs_payload,
                "literature_refs": entry.literature_refs,
                "status": "implemented" if has_valid else "unmapped",
            }
        )

    unmapped_equations = [item["eq_id"] for item in equations_payload if item["status"] == "unmapped"]
    unmapped_code = [
        {"file": record.file_path, "symbol": record.symbol}
        for record in inventory
        if record.kind in {"function", "async_function"}
        and record.file_path.startswith("marsdisk/")
        and (record.file_path, record.symbol) not in referenced
    ]

    total = len(equations_payload)
    mapped = total - len(unmapped_equations)
    coverage_rate = mapped / total if total else 1.0

    return {
        "equations": equations_payload,
        "unmapped_equations": unmapped_equations,
        "unmapped_code": unmapped_code,
        "stats": {
            "total_equations": total,
            "mapped": mapped,
            "unmapped": len(unmapped_equations),
            "coverage_rate": coverage_rate,
        },
        "warnings": warnings,
    }

def _render_coverage_markdown(data: Dict[str, Any]) -> str:
    function_total = data["function_total"]
    function_referenced = data["function_referenced"]
    function_rate = data["function_reference_rate"] * 100.0

    anchor_info = data["anchor_consistency_rate"]
    anchor_den = anchor_info["denominator"]
    anchor_rate_pct = (anchor_info["rate"] * 100.0) if anchor_den else 100.0
    invalid_anchor_count = data["invalid_anchor_count"]
    duplicate_anchor_count = data["duplicate_anchor_count"]

    lines: List[str] = ["# Coverage Snapshot", ""]
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    if function_total:
        lines.append(
            f"| Function reference rate | {function_rate:.1f}% ({function_referenced}/{function_total}) |"
        )
    else:
        lines.append("| Function reference rate | n/a (0/0) |")
    lines.append(
        f"| Anchor consistency rate | {anchor_rate_pct:.1f}% ({anchor_info['numerator']}/{anchor_den}) |"
    )
    lines.append(
        f"| Anchor anomalies | invalid={invalid_anchor_count}, duplicates={duplicate_anchor_count} |"
    )
    lines.append("")
    lines.append(
        f"Anchors: {anchor_rate_pct:.1f}% consistent "
        f"({anchor_info['numerator']}/{anchor_den}); "
        f"invalid={invalid_anchor_count}; "
        f"duplicates={duplicate_anchor_count}."
    )
    lines.append("")
    lines.append("## Module Coverage")
    lines.append("")
    lines.append("| Module | Referenced | Total | Coverage |")
    lines.append("| --- | --- | --- | --- |")
    for entry in data["per_file"]:
        total = entry["functions_total"]
        rate_pct = entry["coverage_rate"] * 100.0 if total else 0.0
        lines.append(
            f"| {entry['file_path']} | {entry['functions_referenced']} | {total} | {rate_pct:.1f}% |"
        )
    lines.append("")
    lines.append("## Top Coverage Gaps")
    lines.append("")
    top_gaps = data.get("top_gaps", [])[:10]
    if top_gaps:
        for gap in top_gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def _is_stub_already_present(text: str, record: InventoryRecord) -> bool:
    anchor = _format_code_anchor(record)
    return anchor in text


def _render_stub_block(record: InventoryRecord, doc_kind: str) -> str:
    anchor = _format_code_anchor(record)
    if doc_kind == "equations":
        lines = [
            f"### {record.symbol} ─ TODO: describe {record.symbol}",
            "",
            "- 概要: TODO（計算の目的とスケール感を記載）",
            "- 式: TODO（代表式・導出の要点を記載）",
            f"- 参照: {anchor}",
            "- 根拠: TODO（参照論文や式番号を記載）",
        ]
    elif doc_kind == "run_recipes":
        lines = [
            f"### {record.symbol} ─ TODO: 実行時の流れを補足",
            "",
            "- 手順: TODO（CLI/設定変更のポイント）",
            "- 入出力: TODO（必要な設定と戻り値）",
            f"- 参照: {anchor}",
            "- 根拠: TODO（関連する検証・ケース）",
        ]
    else:  # overview / generic
        lines = [
            f"### {record.symbol} ─ TODO: describe {record.symbol}",
            "",
            "- 役割: TODO（責務の概要を記載）",
            "- 入出力: TODO（主要なI/O項目）",
            f"- 参照: {anchor}",
            "- 根拠: TODO（利用箇所や前提条件）",
        ]
    return "\n".join(lines)


def _append_to_section(text: str, heading_pattern: re.Pattern[str], stub: str) -> str:
    match = heading_pattern.search(text)
    if not match:
        raise RuntimeError(f"Heading not found for autostub insertion: pattern {heading_pattern.pattern}")
    section_start = match.end()
    following = text[section_start:]
    next_heading = re.search(r"^## ", following, re.MULTILINE)
    if next_heading:
        insert_pos = section_start + next_heading.start()
    else:
        insert_pos = len(text)
    addition = "\n\n" + stub.strip() + "\n"
    return text[:insert_pos] + addition + text[insert_pos:]


def _append_to_end(text: str, stub: str) -> str:
    trimmed = text.rstrip()
    addition = "\n\n" + stub.strip() + "\n"
    return trimmed + addition


def _determine_autostub_target(
    record: InventoryRecord,
    suggestions: Dict[Tuple[str, str], Dict[str, Any]],
    overview_path: Path,
    equations_path: Path,
    run_recipes_path: Path,
) -> Tuple[Path, Optional[re.Pattern[str]], str]:
    key = (record.file_path, record.symbol)
    doc_path: Path
    heading_pattern: Optional[re.Pattern[str]] = None
    doc_kind = "overview"

    if key in suggestions:
        suggested = suggestions[key]["suggested_doc"]
        candidate_str = str(suggested)
        if candidate_str == "analysis/overview.md":
            doc_path = overview_path
        elif candidate_str == "analysis/equations.md":
            doc_path = equations_path
        elif candidate_str == "analysis/run-recipes.md":
            doc_path = run_recipes_path
        else:
            doc_path = _resolve_cli_path(candidate_str)
    else:
        file_path = record.file_path
        if file_path.startswith("marsdisk/physics/"):
            doc_path = equations_path
        elif file_path.startswith("marsdisk/io/"):
            doc_path = overview_path
        else:
            doc_path = run_recipes_path

    if doc_path.samefile(equations_path):
        doc_kind = "equations"
    elif doc_path.samefile(run_recipes_path):
        doc_kind = "run_recipes"
    else:
        doc_kind = "overview"

    if doc_kind == "overview":
        heading_pattern = HEADING_IO_PATTERN
    else:
        heading_pattern = None

    return doc_path, heading_pattern, doc_kind


def _cmd_coverage(args: argparse.Namespace) -> int:
    inventory_path = _resolve_cli_path(args.inv)
    refs_path = _resolve_cli_path(args.refs)
    if not inventory_path.exists():
        raise SystemExit(f"--inv path does not exist: {inventory_path}")
    if not refs_path.exists():
        raise SystemExit(f"--refs path does not exist: {refs_path}")

    inventory_records = _load_inventory_records(inventory_path)
    docs_payload = json.loads(refs_path.read_text(encoding="utf-8"))
    coverage_data = _compute_coverage(inventory_records, docs_payload)

    json_output_path = _resolve_cli_path(args.write_json)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(
        json.dumps(coverage_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md_output_path = _resolve_cli_path(args.write_md)
    md_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.write_text(
        _render_coverage_markdown(coverage_data),
        encoding="utf-8",
    )

    print(
        "coverage: wrote "
        f"{_rel_to_repo(json_output_path)} and {_rel_to_repo(md_output_path)}"
    )
    return 0


def _cmd_equations(args: argparse.Namespace) -> int:
    equations_path = _resolve_cli_path(args.equations)
    inventory_path = _resolve_cli_path(args.inventory)
    output_path = _resolve_cli_path(args.write)

    if not equations_path.exists():
        raise SystemExit(f"--equations path does not exist: {equations_path}")
    if not inventory_path.exists():
        raise SystemExit(f"--inventory path does not exist: {inventory_path}")

    equations = _parse_equations_md(equations_path)
    inventory_records = _load_inventory_records(inventory_path)
    report = _compute_equation_code_map(equations, inventory_records)
    report["generated_at"] = (
        __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")
    )
    report["ml_suggested_refs"] = []

    if getattr(args, "with_ml_suggest", False):
        try:
            from .equation_matcher import load_or_train_matcher
        except Exception as exc:
            warnings.warn(f"equations: ML suggestion unavailable ({exc})")
        else:
            try:
                matcher = load_or_train_matcher(
                    equations,
                    inventory_records,
                    cache_path=ML_CACHE_PATH,
                    use_classifier=not getattr(args, "ml_no_classifier", False),
                )
                ml_candidates = matcher.suggest(
                    top_k=int(getattr(args, "ml_top", 3)),
                    sim_threshold=float(getattr(args, "ml_threshold", 0.2)),
                )
                report["ml_suggested_refs"] = [
                    {
                        "eq_id": item.eq_id,
                        "file": item.file_path,
                        "symbol": item.symbol,
                        "score": item.score,
                        "confidence": item.confidence,
                        "priority": item.priority,
                    }
                    for item in ml_candidates
                ]
            except Exception as exc:  # pragma: no cover - defensive
                warnings.warn(f"equations: ML suggestion failed ({exc})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "equations: wrote "
        f"{_rel_to_repo(output_path)} "
        f"(coverage_rate={report['stats']['coverage_rate']:.3f}, "
        f"unmapped={len(report['unmapped_equations'])})"
    )
    return 0


def _cmd_autostub(args: argparse.Namespace) -> int:
    coverage_path = _resolve_cli_path(args.coverage)
    if not coverage_path.exists():
        raise SystemExit(f"--coverage path does not exist: {coverage_path}")

    coverage_data = json.loads(coverage_path.read_text(encoding="utf-8"))
    candidates = _collect_unreferenced_from_coverage(coverage_data)
    if not candidates:
        print("autostub: no unreferenced functions detected in coverage report.")
        return 0

    limit = max(0, int(args.top))
    if limit > 0:
        candidates = candidates[:limit]

    inventory_path = _resolve_cli_path(args.inventory)
    if not inventory_path.exists():
        raise SystemExit(f"--inventory path does not exist: {inventory_path}")
    inventory_records = _load_inventory_records(inventory_path)
    record_map = {(rec.file_path, rec.symbol): rec for rec in inventory_records}

    overview_path = _resolve_cli_path(args.overview)
    equations_path = _resolve_cli_path(args.equations)
    run_recipes_path = _resolve_cli_path(args.run_recipes)
    suggestions_path = _resolve_cli_path(args.suggestions)
    suggestions = _load_suggestions_index(suggestions_path)

    doc_text_cache: Dict[Path, str] = {}
    docs_requiring_numbering: set[Path] = set()
    inserted: List[Tuple[str, str]] = []

    for file_path, symbol in candidates:
        record = record_map.get((file_path, symbol))
        if not record:
            continue
        if record.kind not in {"function", "async_function"}:
            continue
        doc_path, heading_pattern, doc_kind = _determine_autostub_target(
            record,
            suggestions,
            overview_path,
            equations_path,
            run_recipes_path,
        )
        if doc_path not in doc_text_cache:
            if not doc_path.exists():
                raise SystemExit(f"Document not found for autostub insertion: {doc_path}")
            doc_text_cache[doc_path] = doc_path.read_text(encoding="utf-8")
        current_text = doc_text_cache[doc_path]
        if _is_stub_already_present(current_text, record):
            continue
        stub_block = _render_stub_block(record, doc_kind)
        if heading_pattern is None:
            updated_text = _append_to_end(current_text, stub_block)
        else:
            updated_text = _append_to_section(current_text, heading_pattern, stub_block)
        if doc_kind == "equations":
            updated_text = _strip_line_anchor_annotations(updated_text)
            docs_requiring_numbering.add(doc_path)
        doc_text_cache[doc_path] = updated_text
        inserted.append((record.file_path, record.symbol))

    for path, text in doc_text_cache.items():
        if path.exists():
            path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
            if path in docs_requiring_numbering:
                ensure_equation_ids(path)

    print(
        "autostub: inserted "
        f"{len(inserted)} stub(s)."
        + ("" if not inserted else " " + ", ".join(f"{fp}#{sym}" for fp, sym in inserted))
    )
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    root = args.root
    inventory_path = _resolve_cli_path(args.inventory)
    refs_path = _resolve_cli_path(args.refs)
    coverage_json_path = _resolve_cli_path(args.coverage_json)
    coverage_md_path = _resolve_cli_path(args.coverage_md)
    overview_path = _resolve_cli_path(args.overview)
    equations_path = _resolve_cli_path(args.equations)
    run_recipes_path = _resolve_cli_path(args.run_recipes)
    suggestions_path = _resolve_cli_path(args.suggestions)
    eq_map_path = _resolve_cli_path(args.equations_map)

    doc_paths: List[Path] = []
    for doc in args.docs:
        path = _resolve_cli_path(doc)
        if not path.exists():
            print(f"update: skipping missing documentation file {path}")
            continue
        doc_paths.append(path)
    if not doc_paths:
        raise SystemExit("update: no documentation files available for refs step.")

    # Normalise equation numbering and strip legacy line anchors before scanning.
    ensure_equation_ids(equations_path)
    for doc in doc_paths:
        if doc.suffix.lower() == ".md":
            text = doc.read_text(encoding="utf-8")
            cleaned = _strip_line_anchor_annotations(text)
            if cleaned != text:
                doc.write_text(cleaned if cleaned.endswith("\n") else cleaned + "\n", encoding="utf-8")

    # Preserve duplicate count from previous coverage to detect regressions.
    previous_coverage = None
    if coverage_json_path.exists():
        try:
            previous_coverage = json.loads(coverage_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_coverage = None
    prev_duplicates = (
        previous_coverage.get("duplicate_anchor_count") if previous_coverage else None
    )

    scan_args = argparse.Namespace(root=root, write_path=str(inventory_path))
    _cmd_scan(scan_args)

    refs_args = argparse.Namespace(
        docs=[str(path) for path in doc_paths],
        write_path=str(refs_path),
    )
    _cmd_refs(refs_args)

    coverage_args = argparse.Namespace(
        inv=str(inventory_path),
        refs=str(refs_path),
        write_json=str(coverage_json_path),
        write_md=str(coverage_md_path),
    )
    _cmd_coverage(coverage_args)

    autostub_args = argparse.Namespace(
        coverage=str(coverage_json_path),
        top=int(args.autostub_top),
        inventory=str(inventory_path),
        overview=str(overview_path),
        equations=str(equations_path),
        run_recipes=str(run_recipes_path),
        suggestions=str(suggestions_path),
    )
    _cmd_autostub(autostub_args)

    ensure_equation_ids(equations_path)

    _cmd_refs(refs_args)
    _cmd_coverage(coverage_args)

    if not args.skip_equations:
        eq_args = argparse.Namespace(
            equations=str(equations_path),
            inventory=str(inventory_path),
            write=str(eq_map_path),
            with_ml_suggest=bool(args.with_ml_suggest),
            ml_top=int(args.ml_top),
            ml_threshold=float(args.ml_threshold),
            ml_no_classifier=bool(args.ml_no_classifier),
        )
        _cmd_equations(eq_args)

    coverage_data = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    function_rate = float(coverage_data.get("function_reference_rate", 0.0))
    anchor_rate = float(
        coverage_data.get("anchor_consistency_rate", {}).get("rate", 1.0)
    )
    invalid_count = int(coverage_data.get("invalid_anchor_count", 0))
    duplicate_count = int(coverage_data.get("duplicate_anchor_count", 0))

    if prev_duplicates is not None and duplicate_count > prev_duplicates:
        raise SystemExit(
            f"update: duplicate anchor count increased "
            f"{prev_duplicates} → {duplicate_count}."
        )
    if function_rate < args.fail_under:
        raise SystemExit(
            f"update: function reference rate {function_rate:.3f} below threshold {args.fail_under:.3f}."
        )
    if anchor_rate < args.anchor_threshold:
        raise SystemExit(
            f"update: anchor consistency rate {anchor_rate:.3f} below threshold {args.anchor_threshold:.3f}."
        )
    if invalid_count > 0:
        raise SystemExit(
            f"update: invalid anchor count {invalid_count} detected; clean anchors required."
        )

    if not args.skip_guard:
        guard_cmd = [
            sys.executable,
            "-m",
            "agent_test.ci_guard_analysis",
            "--coverage",
            str(coverage_json_path),
            "--refs",
            str(refs_path),
            "--inventory",
            str(inventory_path),
            "--fail-under",
            f"{args.fail_under:.2f}",
            "--require-clean-anchors",
            "--show-top",
            str(args.guard_show_top),
        ]
        subprocess.run(guard_cmd, check=True, cwd=REPO_ROOT)

    if not args.skip_pytest and args.pytest_target:
        pytest_cmd = ["pytest", "-q", *args.pytest_target]
        subprocess.run(pytest_cmd, check=True, cwd=REPO_ROOT)

    print(
        "update: analysis refreshed "
        f"(function_reference_rate={function_rate:.3f}, "
        f"anchor_rate={anchor_rate:.3f}, duplicates={duplicate_count})."
    )
    return 0


def _run_new_cli(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="doc_sync_agent.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Collect top-level marsdisk symbols into a JSON inventory.",
    )
    scan_parser.add_argument(
        "--root",
        default=".",
        help="Root directory containing the marsdisk package (default: current repo root).",
    )
    scan_parser.add_argument(
        "--write",
        dest="write_path",
        required=True,
        help="Output path for the generated inventory JSON.",
    )
    scan_parser.set_defaults(func=_cmd_scan)

    refs_parser = subparsers.add_parser(
        "refs",
        help="Parse documentation files and extract code references.",
    )
    refs_parser.add_argument(
        "--docs",
        nargs="+",
        required=True,
        help="Markdown documents to inspect.",
    )
    refs_parser.add_argument(
        "--write",
        dest="write_path",
        required=True,
        help="Output path for the reference summary JSON.",
    )
    refs_parser.set_defaults(func=_cmd_refs)

    coverage_parser = subparsers.add_parser(
        "coverage",
        help="Combine inventory and reference data to compute coverage metrics.",
    )
    coverage_parser.add_argument(
        "--inv",
        required=True,
        help="Path to the inventory JSON produced by the scan command.",
    )
    coverage_parser.add_argument(
        "--refs",
        required=True,
        help="Path to the documentation references JSON produced by the refs command.",
    )
    coverage_parser.add_argument(
        "--write-json",
        dest="write_json",
        required=True,
        help="Output path for the coverage summary JSON.",
    )
    coverage_parser.add_argument(
        "--write-md",
        dest="write_md",
        required=True,
        help="Output path for the Markdown coverage report.",
    )
    coverage_parser.set_defaults(func=_cmd_coverage)

    equations_parser = subparsers.add_parser(
        "equations",
        help="Parse equations.md and map equations to code symbols using inventory.",
    )
    equations_parser.add_argument(
        "--equations",
        default=str(EQUATIONS_PATH_DEFAULT.relative_to(REPO_ROOT)),
        help="Path to equations markdown (default: analysis/equations.md).",
    )
    equations_parser.add_argument(
        "--inventory",
        default="analysis/inventory.json",
        help="Path to inventory JSON produced by scan (default: analysis/inventory.json).",
    )
    equations_parser.add_argument(
        "--write",
        default="analysis/equation_code_map.json",
        help="Output path for equation-code mapping JSON (default: analysis/equation_code_map.json).",
    )
    equations_parser.add_argument(
        "--with-ml-suggest",
        action="store_true",
        help="Enable ML-based suggestion of equation↔code pairs (warn-only, no auto-apply).",
    )
    equations_parser.add_argument(
        "--ml-top",
        type=int,
        default=3,
        help="Top-K ML suggestions per equation (default: 3).",
    )
    equations_parser.add_argument(
        "--ml-threshold",
        type=float,
        default=0.2,
        help="Minimum cosine similarity to keep a suggestion (default: 0.2).",
    )
    equations_parser.add_argument(
        "--ml-no-classifier",
        action="store_true",
        help="Skip training logistic regression; rely on similarity only.",
    )
    equations_parser.set_defaults(func=_cmd_equations)

    autostub_parser = subparsers.add_parser(
        "autostub",
        help="Insert skeleton documentation entries for unreferenced functions.",
    )
    autostub_parser.add_argument(
        "--coverage",
        required=True,
        help="Path to coverage JSON generated by the coverage command.",
    )
    autostub_parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Maximum number of unreferenced functions to stub (default: 0 = unlimited).",
    )
    autostub_parser.add_argument(
        "--inventory",
        default="analysis/inventory.json",
        help="Inventory JSON containing function metadata (default: analysis/inventory.json).",
    )
    autostub_parser.add_argument(
        "--overview",
        default="analysis/overview.md",
        help="Path to the overview markdown file (default: analysis/overview.md).",
    )
    autostub_parser.add_argument(
        "--equations",
        default="analysis/equations.md",
        help="Path to the equations markdown file (default: analysis/equations.md).",
    )
    autostub_parser.add_argument(
        "--run-recipes",
        dest="run_recipes",
        default="analysis/run-recipes.md",
        help="Path to the run-recipes markdown file (default: analysis/run-recipes.md).",
    )
    autostub_parser.add_argument(
        "--suggestions",
        default=str(SUGGESTIONS_DEFAULT_PATH),
        help="Path to suggestions_index.json mapping functions to documents (default: analysis/suggestions_index.json).",
    )
    autostub_parser.set_defaults(func=_cmd_autostub)

    update_parser = subparsers.add_parser(
        "update",
        help="Run scan→refs→coverage→autostub pipeline and enforce documentation guards.",
    )
    update_parser.add_argument(
        "--root",
        default="marsdisk",
        help="Root directory containing the marsdisk package (default: marsdisk).",
    )
    update_parser.add_argument(
        "--docs",
        nargs="+",
        default=[str(path.relative_to(REPO_ROOT)) if path.is_absolute() else str(path) for path in DEFAULT_DOCS_FOR_REFS],
        help="Documentation files to include in refs step (default: key analysis markdown files).",
    )
    update_parser.add_argument(
        "--inventory",
        default="analysis/inventory.json",
        help="Output path for the inventory JSON (default: analysis/inventory.json).",
    )
    update_parser.add_argument(
        "--refs",
        default="analysis/doc_refs.json",
        help="Output path for the references JSON (default: analysis/doc_refs.json).",
    )
    update_parser.add_argument(
        "--coverage-json",
        dest="coverage_json",
        default="analysis/coverage.json",
        help="Output path for the coverage JSON (default: analysis/coverage.json).",
    )
    update_parser.add_argument(
        "--coverage-md",
        dest="coverage_md",
        default="analysis/coverage_report.md",
        help="Output path for the coverage markdown report (default: analysis/coverage_report.md).",
    )
    update_parser.add_argument(
        "--overview",
        default=str(OVERVIEW_PATH_DEFAULT.relative_to(REPO_ROOT)),
        help="Path to overview markdown (default: analysis/overview.md).",
    )
    update_parser.add_argument(
        "--equations",
        default=str(EQUATIONS_PATH_DEFAULT.relative_to(REPO_ROOT)),
        help="Path to equations markdown (default: analysis/equations.md).",
    )
    update_parser.add_argument(
        "--equations-map",
        default="analysis/equation_code_map.json",
        help="Output path for equation-code mapping JSON (default: analysis/equation_code_map.json).",
    )
    update_parser.add_argument(
        "--run-recipes",
        dest="run_recipes",
        default=str(RUN_RECIPES_PATH_DEFAULT.relative_to(REPO_ROOT)),
        help="Path to run-recipes markdown (default: analysis/run-recipes.md).",
    )
    update_parser.add_argument(
        "--suggestions",
        default=str(SUGGESTIONS_DEFAULT_PATH.relative_to(REPO_ROOT)),
        help="Path to suggestions_index.json (default: analysis/suggestions_index.json).",
    )
    update_parser.add_argument(
        "--autostub-top",
        type=int,
        default=0,
        help="Limit for autostub insertions (default: 0 = unlimited).",
    )
    update_parser.add_argument(
        "--skip-equations",
        action="store_true",
        help="Skip equations↔code mapping during update.",
    )
    update_parser.add_argument(
        "--with-ml-suggest",
        action="store_true",
        help="Enable ML-based equation suggestions (warn-only, no auto-apply).",
    )
    update_parser.add_argument(
        "--ml-top",
        type=int,
        default=3,
        help="Top-K ML suggestions per equation when enabled (default: 3).",
    )
    update_parser.add_argument(
        "--ml-threshold",
        type=float,
        default=0.2,
        help="Cosine similarity threshold for ML suggestions (default: 0.2).",
    )
    update_parser.add_argument(
        "--ml-no-classifier",
        action="store_true",
        help="Skip logistic regression and rely on similarity only.",
    )
    update_parser.add_argument(
        "--fail-under",
        type=float,
        default=0.90,
        help="Minimum acceptable function reference rate (default: 0.90).",
    )
    update_parser.add_argument(
        "--anchor-threshold",
        type=float,
        default=0.98,
        help="Minimum acceptable anchor consistency rate (default: 0.98).",
    )
    update_parser.add_argument(
        "--guard-show-top",
        type=int,
        default=5,
        help="How many missing functions to surface when guard fails (default: 5).",
    )
    update_parser.add_argument(
        "--skip-guard",
        action="store_true",
        help="Skip the agent_test.ci_guard_analysis check.",
    )
    update_parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip running pytest after the update pipeline.",
    )
    update_parser.add_argument(
        "--pytest-target",
        nargs="+",
        default=["tests/test_doc_sync_agent.py"],
        help="Targets to pass to pytest (default: tests/test_doc_sync_agent.py).",
    )
    update_parser.set_defaults(func=_cmd_update)

    parsed_args = parser.parse_args(list(argv))
    return parsed_args.func(parsed_args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in {"scan", "refs", "coverage", "equations", "autostub", "update"}:
        return _run_new_cli(list(argv))
    return _legacy_main(argv)


def _git_commit(changes: Iterable[FileChange]) -> None:
    rel_paths = [str(change.path.relative_to(REPO_ROOT)) for change in changes]
    subprocess.run(["git", "add", *rel_paths], cwd=REPO_ROOT, check=False)
    subprocess.run(
        ["git", "commit", "-m", "docs: sync analysis"],
        cwd=REPO_ROOT,
        check=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
