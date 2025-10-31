#!/usr/bin/env python3
"""Extract public code symbols from the marsdisk package via the AST."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "marsdisk"
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "reports" / "ast_symbols.json"


SKIP_DIR_NAMES = {
    "__pycache__",
    ".venv",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
}


@dataclass(frozen=True)
class SymbolRecord:
    """Lightweight container describing a discovered symbol."""

    name: str
    file: Path
    lineno: int
    end_lineno: int
    kind: str


def discover_python_files(root: Path, include_tests: bool) -> Iterator[Path]:
    """Yield Python source files beneath *root* respecting the tests toggle."""
    for path in sorted(root.rglob("*.py")):
        if not include_tests and any(part == "tests" for part in path.parts):
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def is_trivial_init(path: Path, tree: ast.Module) -> bool:
    """Return True if the module is an __init__ with only imports/docstring."""
    if path.name != "__init__.py":
        return False

    def node_is_trivial(node: ast.stmt) -> bool:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Str, ast.Constant)):
            return isinstance(node.value.value, str)
        return False

    return all(node_is_trivial(stmt) for stmt in tree.body)


def symbol_kind(node: ast.AST) -> str:
    """Return a human-readable kind label for a symbol node."""
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    return "function"


def compute_end_lineno(node: ast.AST) -> int:
    """Best-effort estimate of the end line for *node*."""
    if hasattr(node, "end_lineno") and getattr(node, "end_lineno") is not None:
        return int(getattr(node, "end_lineno"))
    latest = getattr(node, "lineno", 0)
    for child in ast.walk(node):
        lineno = getattr(child, "lineno", None)
        if lineno is not None:
            latest = max(latest, int(lineno))
    return latest


def collect_symbols(
    path: Path,
    *,
    include_private: bool,
    skip_trivial_init: bool,
) -> List[SymbolRecord]:
    """Parse *path* and return symbol records filtered by visibility."""
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print(f"[rc_scan_ast] Skipping {path}: {exc}")
        return []
    if skip_trivial_init and is_trivial_init(path, tree):
        return []

    symbols: List[SymbolRecord] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if not include_private and name.startswith("_"):
                continue
            end_lineno = compute_end_lineno(node)
            symbols.append(
                SymbolRecord(
                    name=name,
                    file=path,
                    lineno=int(node.lineno),
                    end_lineno=end_lineno,
                    kind=symbol_kind(node),
                )
            )
    return symbols


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan marsdisk Python sources and emit a JSON report of top-level "
            "function and class definitions."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Source tree to scan (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write the JSON report (default: %(default)s).",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include symbols whose names start with an underscore.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include files located under any tests/ directory.",
    )
    parser.add_argument(
        "--keep-trivial-inits",
        action="store_true",
        help="Keep __init__.py modules that only expose imports or docstrings.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    source_root = args.root.resolve() if args.root.is_absolute() else (REPO_ROOT / args.root).resolve()
    if not source_root.exists():
        parser.error(f"Source root {source_root} does not exist.")

    symbols: List[SymbolRecord] = []
    for path in discover_python_files(source_root, include_tests=args.include_tests):
        symbols.extend(
            collect_symbols(
                path,
                include_private=args.include_private,
                skip_trivial_init=not args.keep_trivial_inits,
            )
        )

    output_path = args.output if args.output.is_absolute() else (Path(__file__).resolve().parent / args.output)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_root": str(source_root),
        "symbol_count": len(symbols),
        "symbols": [
            {
                "name": symbol.name,
                "file": str(symbol.file.relative_to(REPO_ROOT)),
                "lineno": symbol.lineno,
                "end_lineno": symbol.end_lineno,
                "kind": symbol.kind,
            }
            for symbol in symbols
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[rc_scan_ast] Wrote {len(symbols)} symbols to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
