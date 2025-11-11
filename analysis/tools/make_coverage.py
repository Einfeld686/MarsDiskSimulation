#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "analysis"
COVERAGE_DIR = ANALYSIS_DIR / "coverage"

INVENTORY_PATH = ANALYSIS_DIR / "inventory.json"
SYMBOLS_RAW_PATH = ANALYSIS_DIR / "symbols.raw.txt"
EQUATIONS_PATH = ANALYSIS_DIR / "equations.md"
SINKS_DOC_PATH = ANALYSIS_DIR / "sinks_callgraph.md"

ANCHOR_PATTERN = re.compile(
    r"(marsdisk/[A-Za-z0-9_/\.-]+\.py)#([A-Za-z0-9_\.]+)"
)
UNIT_BRACKETS_PATTERN = re.compile(r"\[[^\]]*[A-Za-z][^\]]*\]")

AUTOGEN_BEGIN = "<!-- AUTOGEN"
AUTOGEN_END = "AUTOGEN-END -->"


@dataclass(frozen=True)
class SymbolRef:
    rel_path: str
    name: str


def load_inventory() -> List[dict]:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Missing inventory.json at {INVENTORY_PATH}")
    try:
        data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse inventory.json: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError("inventory.json must contain a list.")
    return data


def load_symbol_kinds() -> Dict[SymbolRef, str]:
    """Map symbols to rough kinds using symbols.raw.txt lines."""
    kinds: Dict[SymbolRef, str] = {}
    if not SYMBOLS_RAW_PATH.exists():
        return kinds
    for line in SYMBOLS_RAW_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        rel_path, _, declaration = parts
        decl = declaration.strip()
        name: Optional[str] = None
        if decl.startswith("def "):
            # def name(args)
            name = decl.split()[1].split("(")[0]
            kind = "function"
        elif decl.startswith("async def "):
            name = decl.split()[2].split("(")[0]
            kind = "function"
        elif decl.startswith("class "):
            name = decl.split()[1].split("(")[0].split(":")[0]
            kind = "class"
        else:
            continue
        if name:
            kinds[SymbolRef(rel_path, name)] = kind
    return kinds


def discover_markdown_paths() -> List[Path]:
    paths: List[Path] = []
    for path in ANALYSIS_DIR.glob("**/*.md"):
        if not path.is_file():
            continue
        if COVERAGE_DIR in path.parents:
            continue
        paths.append(path)
    return sorted(paths)


def collect_anchor_occurrences(paths: Sequence[Path]) -> List[Tuple[Path, SymbolRef]]:
    occurrences: List[Tuple[Path, SymbolRef]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in ANCHOR_PATTERN.finditer(text):
            rel_path = match.group(1)
            symbol = match.group(2)
            occurrences.append((path, SymbolRef(rel_path, symbol)))
    return occurrences


def classify_symbols(
    inventory: Sequence[dict],
    symbol_kinds: Dict[SymbolRef, str],
) -> Tuple[Dict[SymbolRef, dict], List[SymbolRef]]:
    all_symbols: Dict[SymbolRef, dict] = {}
    public_functions: List[SymbolRef] = []
    for entry in inventory:
        rel_path = entry.get("file_path")
        name = entry.get("symbol")
        signature = entry.get("signature", "")
        if not rel_path or not name:
            continue
        sym_ref = SymbolRef(rel_path, name)
        all_symbols[sym_ref] = entry

        # Filter for marsdisk functions excluding tests/private.
        if not rel_path.startswith("marsdisk/"):
            continue
        if "/tests/" in rel_path or rel_path.startswith("marsdisk/tests"):
            continue
        if name.startswith("_"):
            continue

        kind = symbol_kinds.get(sym_ref)
        if kind == "function":
            public_functions.append(sym_ref)
            continue

        # Fall back to signature heuristic for functions.
        if "(" in signature and signature.strip().startswith(f"{name}("):
            public_functions.append(sym_ref)

    return all_symbols, sorted(set(public_functions), key=lambda ref: (ref.rel_path, ref.name))


def compute_function_reference_rate(
    public_functions: Sequence[SymbolRef],
    occurrences: Sequence[Tuple[Path, SymbolRef]],
) -> Tuple[int, int, List[SymbolRef]]:
    referenced: Dict[SymbolRef, int] = {ref: 0 for ref in public_functions}
    for _, occ in occurrences:
        if occ in referenced:
            referenced[occ] += 1

    covered = sum(1 for count in referenced.values() if count > 0)
    total = len(public_functions)
    missing = [ref for ref, count in referenced.items() if count == 0]
    missing.sort(key=lambda ref: (ref.rel_path, ref.name))
    return covered, total, missing


def compute_anchor_consistency_rate(
    occurrences: Sequence[Tuple[Path, SymbolRef]],
    known_symbols: Dict[SymbolRef, dict],
) -> Tuple[int, int, List[Tuple[Path, SymbolRef]]]:
    total = len(occurrences)
    resolved = 0
    unresolved: List[Tuple[Path, SymbolRef]] = []
    for path, ref in occurrences:
        if ref.name == "__module__":
            resolved += 1
            continue
        if ref in known_symbols:
            resolved += 1
        else:
            unresolved.append((path, ref))
    return resolved, total, unresolved


def extract_sections_with_equations(content: str) -> List[str]:
    sections: List[str] = []
    current_lines: List[str] = []
    seen_heading = False
    for line in content.splitlines():
        if line.startswith("### "):
            if seen_heading and current_lines:
                sections.append("\n".join(current_lines).strip())
            current_lines = []
            seen_heading = True
            continue
        if seen_heading:
            current_lines.append(line)
    if seen_heading and current_lines:
        sections.append("\n".join(current_lines).strip())
    return sections


def extract_fenced_blocks(section: str) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    lines = section.splitlines()
    in_block = False
    lang = ""
    buffer: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_info = stripped[3:].strip().lower()
            if not in_block:
                in_block = True
                lang = fence_info
                buffer = []
            else:
                blocks.append((lang, "\n".join(buffer)))
                in_block = False
                lang = ""
                buffer = []
            continue
        if in_block:
            buffer.append(line)
    return blocks


def compute_equation_unit_rate(equations_path: Path) -> Tuple[int, int]:
    if not equations_path.exists():
        return 0, 0
    content = equations_path.read_text(encoding="utf-8")
    sections = extract_sections_with_equations(content)
    sections_with_equations = 0
    sections_with_units = 0

    for section in sections:
        fenced_blocks = [
            block for block in extract_fenced_blocks(section)
            if block[0] in {"latex", "math"}
        ]

        # Also capture $$ ... $$ inline blocks.
        inline_blocks = re.findall(r"\$\$(.*?)\$\$", section, flags=re.DOTALL)

        equation_bodies = [body for _, body in fenced_blocks]
        equation_bodies.extend(inline_blocks)

        if not equation_bodies:
            continue
        sections_with_equations += 1

        has_units = any(UNIT_BRACKETS_PATTERN.search(body) for body in equation_bodies)
        if has_units:
            sections_with_units += 1

    return sections_with_units, sections_with_equations


def extract_autogen_block(text: str) -> str:
    start = text.find(AUTOGEN_BEGIN)
    if start == -1:
        return ""
    start = text.find("-->", start)
    if start == -1:
        return ""
    start += 3  # Skip closing of comment
    end = text.find(AUTOGEN_END, start)
    if end == -1:
        # Fallback to rest of file if closing marker missing
        return text[start:].strip()
    return text[start:end].strip()


def compute_sinks_callgraph_flag(doc_path: Path) -> bool:
    if not doc_path.exists():
        return False
    text = doc_path.read_text(encoding="utf-8")
    block = extract_autogen_block(text)
    if not block:
        # Fallback: evaluate entire document.
        block = text

    anchors = {
        "marsdisk/run.py#": False,
        "marsdisk/physics/surface.py#": False,
        "marsdisk/physics/sinks.py#": False,
        "marsdisk/physics/sublimation.py#": False,
    }
    for anchor in anchors.keys():
        if anchor in block:
            anchors[anchor] = True

    return all(anchors.values())


def format_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def rate_to_percent(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def build_coverage_markdown(
    function_rate: Tuple[int, int],
    anchor_rate: Tuple[int, int],
    equation_rate: Tuple[int, int],
    sinks_flag: bool,
    holes: Sequence[SymbolRef],
) -> str:
    func_num, func_den = function_rate
    anchor_num, anchor_den = anchor_rate
    eq_num, eq_den = equation_rate

    func_rate = format_rate(func_num, func_den)
    anchor_ratio = format_rate(anchor_num, anchor_den)
    eq_ratio = format_rate(eq_num, eq_den)

    def ratio_text(num: int, den: int, rate: float) -> str:
        if den == 0:
            return "N/A"
        return f"{rate_to_percent(rate)} ({num}/{den})"

    rows = [
        "| Metric | Value | Target |",
        "| --- | --- | --- |",
        f"| Function reference rate | {ratio_text(func_num, func_den, func_rate)} | ≥ 70% |",
        f"| Anchor consistency rate | {ratio_text(anchor_num, anchor_den, anchor_ratio)} | = 100% |",
        f"| Equation unit coverage | {ratio_text(eq_num, eq_den, eq_ratio)} | — |",
        f"| Sinks callgraph documented | {'Yes' if sinks_flag else 'No'} | run→surface→sinks→sublimation |",
    ]

    hole_lines = []
    if holes:
        hole_lines.append("## Top Coverage Gaps")
        for ref in holes[:3]:
            hole_lines.append(f"- {ref.rel_path}#{ref.name}")
    else:
        hole_lines.append("## Top Coverage Gaps")
        hole_lines.append("- None (all tracked functions referenced)")

    preface = [
        "# Coverage Snapshot",
        "",
        "Baseline thresholds: function reference rate ≥ 70%, anchor consistency rate = 100%.",
        "",
    ]

    return "\n".join(preface + rows + [""] + hole_lines + [""])


def build_coverage_json(
    function_rate: Tuple[int, int],
    anchor_rate: Tuple[int, int],
    equation_rate: Tuple[int, int],
    sinks_flag: bool,
    holes: Sequence[SymbolRef],
) -> dict:
    func_num, func_den = function_rate
    anchor_num, anchor_den = anchor_rate
    eq_num, eq_den = equation_rate

    return {
        "function_reference_rate": {
            "numerator": func_num,
            "denominator": func_den,
            "rate": format_rate(func_num, func_den),
        },
        "anchor_consistency_rate": {
            "numerator": anchor_num,
            "denominator": anchor_den,
            "rate": format_rate(anchor_num, anchor_den),
        },
        "equation_unit_coverage": {
            "numerator": eq_num,
            "denominator": eq_den,
            "rate": format_rate(eq_num, eq_den),
        },
        "sinks_callgraph_documented": bool(sinks_flag),
        "holes": [f"{ref.rel_path}#{ref.name}" for ref in holes[:3]],
    }


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    inventory = load_inventory()
    symbol_kinds = load_symbol_kinds()
    all_symbols, public_functions = classify_symbols(inventory, symbol_kinds)

    markdown_paths = discover_markdown_paths()
    anchor_occurrences = collect_anchor_occurrences(markdown_paths)

    func_covered, func_total, missing = compute_function_reference_rate(public_functions, anchor_occurrences)
    anchor_resolved, anchor_total, unresolved = compute_anchor_consistency_rate(anchor_occurrences, all_symbols)
    eq_with_units, eq_sections = compute_equation_unit_rate(EQUATIONS_PATH)
    sinks_flag = compute_sinks_callgraph_flag(SINKS_DOC_PATH)

    coverage_md = build_coverage_markdown(
        (func_covered, func_total),
        (anchor_resolved, anchor_total),
        (eq_with_units, eq_sections),
        sinks_flag,
        missing,
    )
    coverage_json = build_coverage_json(
        (func_covered, func_total),
        (anchor_resolved, anchor_total),
        (eq_with_units, eq_sections),
        sinks_flag,
        missing,
    )

    write_text(COVERAGE_DIR / "coverage.md", coverage_md)
    write_json(COVERAGE_DIR / "coverage.json", coverage_json)

    if unresolved:
        unresolved_display = ", ".join(
            f"{path.relative_to(REPO_ROOT)}:{ref.rel_path}#{ref.name}"
            for path, ref in unresolved[:5]
        )
        print(f"WARNING: unresolved anchors detected: {unresolved_display}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
