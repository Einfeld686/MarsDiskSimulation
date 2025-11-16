#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "analysis"
INVENTORY_PATH = ANALYSIS_DIR / "inventory.json"
TARGET_DOC = ANALYSIS_DIR / "sinks_callgraph.md"

AUTOGEN_START = "<!-- AUTOGEN:CALLGRAPH START -->"
AUTOGEN_END = "<!-- AUTOGEN:CALLGRAPH END -->"


@dataclass(frozen=True)
class SymbolKey:
    rel_path: str
    symbol: str


def load_inventory() -> Dict[SymbolKey, dict]:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Missing inventory file: {INVENTORY_PATH}")
    try:
        items = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - configuration error
        raise RuntimeError(f"Failed to parse inventory.json: {exc}") from exc
    if not isinstance(items, list):
        raise RuntimeError("inventory.json must contain a list of symbol entries.")
    mapping: Dict[SymbolKey, dict] = {}
    for entry in items:
        key = SymbolKey(entry["file_path"], entry["symbol"])
        mapping[key] = entry
    return mapping


def ensure_symbols_present(inv: Dict[SymbolKey, dict], symbols: Iterable[SymbolKey]) -> None:
    missing = [key for key in symbols if key not in inv]
    if missing:
        missing_str = ", ".join(f"{key.rel_path}#{key.symbol}" for key in missing)
        raise RuntimeError(f"Missing symbols in inventory: {missing_str}")


def make_node_label(key: SymbolKey) -> str:
    return f"{key.symbol}<br/>{key.rel_path}"


def build_mermaid(inv: Dict[SymbolKey, dict]) -> str:
    nodes = {
        "run_zero_d": SymbolKey("marsdisk/run.py", "run_zero_d"),
        "step_surface": SymbolKey("marsdisk/physics/surface.py", "step_surface"),
        "total_sink_timescale": SymbolKey("marsdisk/physics/sinks.py", "total_sink_timescale"),
        "mass_flux_hkl": SymbolKey("marsdisk/physics/sublimation.py", "mass_flux_hkl"),
        "s_sink_from_timescale": SymbolKey("marsdisk/physics/sublimation.py", "s_sink_from_timescale"),
        "step_surface_density": SymbolKey("marsdisk/physics/surface.py", "step_surface_density_S1"),
    }

    ensure_symbols_present(inv, nodes.values())

    node_lines = [
        f'    {node_id}["{make_node_label(symbol)}"]'
        for node_id, symbol in nodes.items()
    ]

    edges = [
        ("run_zero_d", "total_sink_timescale", "mode='sublimation' で有効化"),
        ("run_zero_d", "step_surface", "t_sink を渡す (None でシンク無効)"),
        ("step_surface", "step_surface_density", "Strubbe–Chiang 衝突後に委譲"),
        ("total_sink_timescale", "step_surface", "返値 t_sink / None"),
        ("total_sink_timescale", "mass_flux_hkl", "HK ルート (蒸発率)"),
        ("mass_flux_hkl", "s_sink_from_timescale", "即時蒸発サイズ s_sink"),
        ("s_sink_from_timescale", "total_sink_timescale", "τ_sink を再構成"),
        ("step_surface", "run_zero_d", "outflux / sink_flux を返却"),
    ]

    edge_lines = [
        f"    {src} -->|{label}| {dst}"
        for src, dst, label in edges
    ]

    mermaid_lines = ["```mermaid", "flowchart TD"]
    mermaid_lines.extend(node_lines)
    mermaid_lines.extend(edge_lines)
    mermaid_lines.append("```")
    return "\n".join(mermaid_lines)


def inject_autogen_block(original: str, block: str) -> str:
    autogen_block = f"{AUTOGEN_START}\n{block}\n{AUTOGEN_END}"
    pattern = re.compile(
        rf"{re.escape(AUTOGEN_START)}.*?{re.escape(AUTOGEN_END)}",
        flags=re.DOTALL,
    )
    if pattern.search(original):
        return pattern.sub(autogen_block, original, count=1)

    insertion_anchor = "## HK Boundary"
    idx = original.find(insertion_anchor)
    if idx == -1:
        idx = len(original)
    else:
        idx = original.rfind("\n", 0, idx)
        if idx == -1:
            idx = original.find(insertion_anchor)
    prefix = original[:idx].rstrip("\n")
    suffix = original[idx:]
    return f"{prefix}\n\n{autogen_block}\n\n{suffix.lstrip()}"


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Mermaid call graph for the sublimation sink pathway."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes to sinks_callgraph.md (default: dry-run).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    inventory = load_inventory()
    mermaid_block = build_mermaid(inventory)

    doc_text = TARGET_DOC.read_text(encoding="utf-8")
    updated_text = inject_autogen_block(doc_text, mermaid_block)

    if args.write:
        if updated_text != doc_text:
            TARGET_DOC.write_text(updated_text, encoding="utf-8")
            print("make_sinks_callgraph: wrote sinks_callgraph.md")
        else:
            print("make_sinks_callgraph: no changes")
    else:
        sys.stdout.write(updated_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
