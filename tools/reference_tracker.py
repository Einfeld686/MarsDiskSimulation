#!/usr/bin/env python3
"""Reference tracking and validation for paper preparation.

This tool scans the codebase for literature references and validates them
against the canonical registry (analysis/references.registry.json).

Usage:
    python -m tools.reference_tracker scan          # Scan code for references
    python -m tools.reference_tracker validate      # Check registry coverage
    python -m tools.reference_tracker export-bibtex # Export BibTeX for paper
    python -m tools.reference_tracker report        # Full reference report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ============================================================================
# Configuration
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "analysis" / "references.registry.json"
CODE_DIRS = [REPO_ROOT / "marsdisk"]
DOC_DIRS = [
    REPO_ROOT / "analysis" / "thesis",
    REPO_ROOT / "analysis" / "thesis_sections",
]
EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    "out",
    "agent_test",
    ".venv",
    "venv",
    "site-packages",
}

# Reference patterns to detect in code
PATTERNS = {
    # Formal Pandoc citations, including multi-cite clusters like [@Key; @Key2]
    "formal": re.compile(r"\[(@[^\]]+)\]"),
    # TeX citations like \cite{Key} or \citet[...]{Key1,Key2}
    "tex_cite": re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}"),
    # Author et al. (Year) style
    "informal_etal": re.compile(
        r"([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)?)\s+et\s+al\.\s*\((\d{4})\)"
    ),
    # Author & Author (Year) style
    "informal_pair": re.compile(
        r"([A-Z][a-z]+)\s*(?:&|and)\s*([A-Z][a-z]+)\s*\((\d{4})\)"
    ),
    # Author (Year) style
    "informal_single": re.compile(r"([A-Z][a-z]{2,})\s*\((\d{4})\)"),
    # Equation references like (E.013)
    "equation": re.compile(r"\(E\.(\d{3}[a-z]?)\)"),
}

CITE_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]+$")
PANDOC_KEY_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]+)")
FORMAL_STYLES = {"formal", "tex_cite"}


def _extract_pandoc_keys(raw: str) -> List[str]:
    return PANDOC_KEY_RE.findall(raw)

# Known informal -> formal key mappings (expand as needed)
INFORMAL_TO_KEY = {
    ("Strubbe", "Chiang", "2006"): "StrubbeChiang2006_ApJ648_652",
    ("Hyodo", "2018"): "Hyodo2018_ApJ860_150",
    ("Hyodo", "2017"): "Hyodo2017a_ApJ845_125",  # default to 2017a
    ("Pignatale", "2018"): "Pignatale2018_ApJ853_118",
    ("Ronnet", "2016"): "Ronnet2016_ApJ828_109",
    ("Canup", "Salmon", "2018"): "CanupSalmon2018_SciAdv4_eaar6887",
    ("Takeuchi", "Lin", "2003"): "TakeuchiLin2003_ApJ593_524",
    ("Takeuchi", "Lin", "2002"): "TakeuchiLin2002_ApJ581_1344",
    ("Crida", "Charnoz", "2012"): "CridaCharnoz2012_Science338_1196",
    ("Wyatt", "2008"): "Wyatt2008",
    ("Ohtsuki", "2002"): "Ohtsuki2002_Icarus155_436",
    ("Benz", "Asphaug", "1999"): "BenzAsphaug1999_Icarus142_5",
    ("Leinhardt", "Stewart", "2012"): "LeinhardtStewart2012_ApJ745_79",
    ("Stewart", "Leinhardt", "2009"): "StewartLeinhardt2009_ApJ691_L133",
    ("Krivov", "2006"): "Krivov2006_AA455_509",
    ("Dohnanyi", "1969"): "Dohnanyi1969_JGR74_2531",
    ("Burns", "1979"): "Burns1979_Icarus40_1",
    ("Kubaschewski", "1974"): "Kubaschewski1974",
    ("Shadmehri", "2008"): "Shadmehri2008_ApSS314_217",
    ("Fegley", "Schaefer", "2012"): "FegleySchaefer2012_arXiv",
    ("Kuramoto", "2024"): "Kuramoto2024",
}


# ============================================================================
# Data structures
# ============================================================================


@dataclass
class ReferenceLocation:
    """A single occurrence of a reference in code."""

    file: Path
    line: int
    key: str
    style: str  # "formal", "tex_cite", "informal_etal", etc.
    context: str  # surrounding text


@dataclass
class FunctionReference:
    """References associated with a specific function."""

    module: str
    function: str
    file: Path
    start_line: int
    end_line: int
    keys: List[str] = field(default_factory=list)
    equations: List[str] = field(default_factory=list)


@dataclass
class RegistryEntry:
    """A reference from the registry."""

    key: str
    short: str
    title: str
    doi: Optional[str]
    bibtex: str
    adopted_scope: str
    claims: List[str]


@dataclass
class ReferenceReport:
    """Complete reference analysis report."""

    code_refs: List[ReferenceLocation]
    function_refs: List[FunctionReference]
    registry_entries: Dict[str, RegistryEntry]
    keys_in_code: Set[str]
    keys_in_registry: Set[str]
    missing_from_registry: Set[str]
    unused_in_code: Set[str]
    informal_refs: List[ReferenceLocation]


# ============================================================================
# Registry loading
# ============================================================================


def load_registry() -> Dict[str, RegistryEntry]:
    """Load the canonical reference registry."""
    if not REGISTRY_PATH.exists():
        print(f"Warning: Registry not found at {REGISTRY_PATH}", file=sys.stderr)
        return {}

    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    entries = {}
    for ref in data.get("references", []):
        entry = RegistryEntry(
            key=ref.get("key", ""),
            short=ref.get("short", ""),
            title=ref.get("title", ""),
            doi=ref.get("doi"),
            bibtex=ref.get("bibtex", ""),
            adopted_scope=ref.get("adopted_scope", ""),
            claims=ref.get("claims", []),
        )
        entries[entry.key] = entry
    return entries


# ============================================================================
# Code scanning
# ============================================================================


def iter_python_files() -> List[Path]:
    """Yield all Python files in the code directories."""
    files = []
    for code_dir in CODE_DIRS:
        if not code_dir.exists():
            continue
        for py_file in code_dir.rglob("*.py"):
            if any(excl in py_file.parts for excl in EXCLUDED_DIRS):
                continue
            files.append(py_file)
    return files


def iter_markdown_files() -> List[Path]:
    """Yield markdown files that may contain citations."""
    files: list[Path] = []
    for doc_dir in DOC_DIRS:
        if not doc_dir.exists():
            continue
        for md_file in doc_dir.rglob("*.md"):
            if any(excl in md_file.parts for excl in EXCLUDED_DIRS):
                continue
            files.append(md_file)
    return files


def extract_references_from_file(file_path: Path) -> List[ReferenceLocation]:
    """Extract all reference citations from a text file."""
    refs = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return refs

    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        # Formal Pandoc citations like [@Key; @Key2]
        for match in PATTERNS["formal"].finditer(line):
            for key in _extract_pandoc_keys(match.group(1)):
                refs.append(
                    ReferenceLocation(
                        file=file_path,
                        line=i,
                        key=key,
                        style="formal",
                        context=line.strip(),
                    )
                )

        # TeX citations like \cite{Key1,Key2}
        for match in PATTERNS["tex_cite"].finditer(line):
            for raw_key in match.group(1).split(","):
                key = raw_key.strip()
                if not CITE_KEY_RE.match(key):
                    continue
                refs.append(
                    ReferenceLocation(
                        file=file_path,
                        line=i,
                        key=key,
                        style="tex_cite",
                        context=line.strip(),
                    )
                )

        # Informal "et al." references
        for match in PATTERNS["informal_etal"].finditer(line):
            author = match.group(1).split()[0]  # First author
            year = match.group(2)
            key = _resolve_informal_key(author, year)
            refs.append(
                ReferenceLocation(
                    file=file_path,
                    line=i,
                    key=key,
                    style="informal_etal",
                    context=line.strip(),
                )
            )

        # Informal "Author & Author (Year)" references
        for match in PATTERNS["informal_pair"].finditer(line):
            author1, author2, year = match.groups()
            key = _resolve_informal_key(author1, year, author2)
            refs.append(
                ReferenceLocation(
                    file=file_path,
                    line=i,
                    key=key,
                    style="informal_pair",
                    context=line.strip(),
                )
            )

    return refs


def _resolve_informal_key(author1: str, year: str, author2: str = None) -> str:
    """Attempt to resolve an informal reference to a registry key."""
    # Try various lookup combinations
    if author2:
        lookup_keys = [
            (author1, author2, year),
            (author2, author1, year),
            (author1, year),
        ]
    else:
        lookup_keys = [(author1, year)]

    for lk in lookup_keys:
        if lk in INFORMAL_TO_KEY:
            return INFORMAL_TO_KEY[lk]

    # Fallback: construct a plausible key
    if author2:
        return f"{author1}{author2}{year}"
    return f"{author1}{year}"


def extract_function_references(file_path: Path) -> List[FunctionReference]:
    """Extract references grouped by function/class."""
    func_refs = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return func_refs

    lines = content.split("\n")
    module_name = file_path.stem

    current_func = None
    func_start = 0
    func_lines: List[str] = []

    for i, line in enumerate(lines, start=1):
        # Detect function/method definitions
        if re.match(r"^(async\s+)?def\s+\w+", line) or re.match(r"^class\s+\w+", line):
            # Save previous function if exists
            if current_func and func_lines:
                refs = _extract_refs_from_docstring(func_lines)
                if refs["keys"] or refs["equations"]:
                    func_refs.append(
                        FunctionReference(
                            module=module_name,
                            function=current_func,
                            file=file_path,
                            start_line=func_start,
                            end_line=i - 1,
                            keys=refs["keys"],
                            equations=refs["equations"],
                        )
                    )

            # Start new function
            match = re.match(r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)", line)
            if match:
                current_func = match.group(1) or match.group(2)
                func_start = i
                func_lines = [line]
        elif current_func:
            func_lines.append(line)

    # Don't forget the last function
    if current_func and func_lines:
        refs = _extract_refs_from_docstring(func_lines)
        if refs["keys"] or refs["equations"]:
            func_refs.append(
                FunctionReference(
                    module=module_name,
                    function=current_func,
                    file=file_path,
                    start_line=func_start,
                    end_line=len(lines),
                    keys=refs["keys"],
                    equations=refs["equations"],
                )
            )

    return func_refs


def _extract_refs_from_docstring(lines: List[str]) -> Dict[str, List[str]]:
    """Extract reference keys and equation numbers from function lines."""
    text = "\n".join(lines)
    keys = []
    equations = []

    for match in PATTERNS["formal"].finditer(text):
        keys.extend(_extract_pandoc_keys(match.group(1)))

    for match in PATTERNS["tex_cite"].finditer(text):
        for raw_key in match.group(1).split(","):
            key = raw_key.strip()
            if not CITE_KEY_RE.match(key):
                continue
            keys.append(key)

    for match in PATTERNS["equation"].finditer(text):
        equations.append(f"E.{match.group(1)}")

    # Also check for informal references
    for match in PATTERNS["informal_etal"].finditer(text):
        author = match.group(1).split()[0]
        year = match.group(2)
        key = _resolve_informal_key(author, year)
        keys.append(key)

    return {"keys": list(set(keys)), "equations": list(set(equations))}


# ============================================================================
# Report generation
# ============================================================================


def generate_report() -> ReferenceReport:
    """Generate a complete reference analysis report."""
    registry = load_registry()
    code_refs = []
    function_refs = []

    for py_file in iter_python_files():
        code_refs.extend(extract_references_from_file(py_file))
        function_refs.extend(extract_function_references(py_file))

    for md_file in iter_markdown_files():
        code_refs.extend(extract_references_from_file(md_file))

    keys_in_code = {r.key for r in code_refs if r.style in FORMAL_STYLES}
    keys_in_registry = set(registry.keys())

    informal_refs = [r for r in code_refs if r.style not in FORMAL_STYLES]

    return ReferenceReport(
        code_refs=code_refs,
        function_refs=function_refs,
        registry_entries=registry,
        keys_in_code=keys_in_code,
        keys_in_registry=keys_in_registry,
        missing_from_registry=keys_in_code - keys_in_registry,
        unused_in_code=keys_in_registry - keys_in_code,
        informal_refs=informal_refs,
    )


# ============================================================================
# Output formatters
# ============================================================================


def print_scan_results(report: ReferenceReport) -> None:
    """Print scan results showing all references found."""
    print("=" * 70)
    print("REFERENCE SCAN RESULTS")
    print("=" * 70)

    print(f"\nTotal references found: {len(report.code_refs)}")
    print(f"Unique keys: {len(report.keys_in_code)}")
    print(f"Formal citation style: {sum(1 for r in report.code_refs if r.style in FORMAL_STYLES)}")
    print(f"Informal style: {len(report.informal_refs)}")

    print("\n--- References by file ---")
    by_file: Dict[Path, List[ReferenceLocation]] = {}
    for ref in report.code_refs:
        by_file.setdefault(ref.file, []).append(ref)

    for file_path, refs in sorted(by_file.items()):
        rel_path = file_path.relative_to(REPO_ROOT)
        print(f"\n{rel_path}:")
        for ref in refs:
            style_marker = "✓" if ref.style in FORMAL_STYLES else "⚠"
            print(f"  L{ref.line:4d} {style_marker} [{ref.key}]")


def print_validation_results(report: ReferenceReport) -> None:
    """Print validation results comparing code vs registry."""
    print("=" * 70)
    print("REGISTRY VALIDATION")
    print("=" * 70)

    print(f"\nKeys in code: {len(report.keys_in_code)}")
    print(f"Keys in registry: {len(report.keys_in_registry)}")

    if report.missing_from_registry:
        print(f"\n⚠ Missing from registry ({len(report.missing_from_registry)}):")
        for key in sorted(report.missing_from_registry):
            print(f"  - {key}")

    if report.unused_in_code:
        print(f"\n📚 In registry but not referenced in code ({len(report.unused_in_code)}):")
        for key in sorted(report.unused_in_code):
            entry = report.registry_entries.get(key)
            short = entry.short if entry else key
            print(f"  - {short}")

    if report.informal_refs:
        print(
            f"\n⚠ Informal references (should use [@Key] or \\cite{{Key}} format): {len(report.informal_refs)}"
        )
        for ref in report.informal_refs[:10]:  # Show first 10
            rel_path = ref.file.relative_to(REPO_ROOT)
            print(f"  {rel_path}:{ref.line} -> {ref.key}")
        if len(report.informal_refs) > 10:
            print(f"  ... and {len(report.informal_refs) - 10} more")


def print_function_mapping(report: ReferenceReport) -> None:
    """Print function-to-reference mapping."""
    print("=" * 70)
    print("FUNCTION → REFERENCE MAPPING")
    print("=" * 70)

    for func_ref in sorted(report.function_refs, key=lambda f: (f.module, f.function)):
        if func_ref.keys or func_ref.equations:
            print(f"\n{func_ref.module}.{func_ref.function}:")
            if func_ref.keys:
                print(f"  References: {', '.join(func_ref.keys)}")
            if func_ref.equations:
                print(f"  Equations: {', '.join(func_ref.equations)}")


def export_bibtex(report: ReferenceReport, output_path: Optional[Path] = None) -> str:
    """Export BibTeX entries for all referenced works."""
    bibtex_entries = []

    # Only export keys that are actually used in code
    for key in sorted(report.keys_in_code):
        entry = report.registry_entries.get(key)
        if entry and entry.bibtex:
            bibtex_entries.append(entry.bibtex)
        else:
            bibtex_entries.append(f"% WARNING: No BibTeX for {key}")

    content = "\n\n".join(bibtex_entries)

    if output_path:
        output_path.write_text(content, encoding="utf-8")
        print(f"BibTeX exported to {output_path}")

    return content


def print_full_report(report: ReferenceReport) -> None:
    """Print comprehensive reference report."""
    print_scan_results(report)
    print("\n")
    print_validation_results(report)
    print("\n")
    print_function_mapping(report)

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY FOR PAPER PREPARATION")
    print("=" * 70)

    coverage = len(report.keys_in_code & report.keys_in_registry) / max(
        len(report.keys_in_code), 1
    )
    print(f"\nRegistry coverage: {coverage:.1%}")

    if coverage < 1.0:
        print("⚠ Action required: Add missing references to registry")

    if report.informal_refs:
        print("⚠ Action required: Convert informal references to [@Key] format")

    print("\nTo export BibTeX for your paper:")
    print("  python -m tools.reference_tracker export-bibtex -o paper/references.bib")


# ============================================================================
# CLI
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Reference tracking and validation for paper preparation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scan command
    subparsers.add_parser("scan", help="Scan codebase for references")

    # Validate command
    subparsers.add_parser("validate", help="Validate references against registry")

    # Export command
    export_parser = subparsers.add_parser("export-bibtex", help="Export BibTeX")
    export_parser.add_argument(
        "-o", "--output", type=Path, help="Output file path"
    )

    # Report command
    subparsers.add_parser("report", help="Generate full reference report")

    # Function mapping
    subparsers.add_parser("functions", help="Show function-to-reference mapping")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    report = generate_report()

    if args.command == "scan":
        print_scan_results(report)
    elif args.command == "validate":
        print_validation_results(report)
    elif args.command == "export-bibtex":
        output = args.output or REPO_ROOT / "paper" / "references.bib"
        output.parent.mkdir(parents=True, exist_ok=True)
        export_bibtex(report, output)
    elif args.command == "functions":
        print_function_mapping(report)
    elif args.command == "report":
        print_full_report(report)


if __name__ == "__main__":
    main()
