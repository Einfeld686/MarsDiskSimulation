"""CI guard for provenance coverage."""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "analysis" / "references.registry.json"
SOURCE_MAP_PATH = REPO_ROOT / "analysis" / "source_map.json"
EQUATIONS_PATH = REPO_ROOT / "analysis" / "equations.md"


def _load_registry() -> Dict[str, Dict[str, object]]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = payload.get("references", [])
    assert entries, "references.registry.json must list at least one entry"
    registry: Dict[str, Dict[str, object]] = {}
    for item in entries:
        key = item.get("key")
        assert key, f"registry entry missing key: {item}"
        registry[key] = item
    return registry


def test_source_map_links_known_keys() -> None:
    registry = _load_registry()
    data = json.loads(SOURCE_MAP_PATH.read_text(encoding="utf-8"))
    assert data, "source_map.json should not be empty"
    for anchor, entry in data.items():
        refs: List[str] = entry.get("references", [])
        todos: List[str] = entry.get("todos", [])
        if refs:
            for ref in refs:
                assert (
                    ref in registry
                ), f"{anchor} references unknown key {ref}; add it to references.registry.json"
        else:
            assert todos, f"{anchor} lacks references and todos; add TODO slug or reference"


def test_equations_have_reference_or_todo() -> None:
    text = EQUATIONS_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"^### \((E\.\d{3})\) (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    assert matches, "no (E.xxx) headings detected"
    missing: List[str] = []
    todo_only: List[str] = []
    for idx, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]
        if "[@" in block:
            continue
        if "TODO(REF:" in block:
            todo_only.append(label)
            continue
        missing.append(label)
    if todo_only:
        warnings.warn(
            f"Equations without confirmed references: {', '.join(todo_only)}",
            UserWarning,
            stacklevel=1,
        )
    assert not missing, f"Equations missing provenance tags: {', '.join(missing)}"


def _extract_equation_block(label: str) -> str:
    text = EQUATIONS_PATH.read_text(encoding="utf-8")
    heading_pattern = re.compile(r"^### \((E\.\d{3})\) ", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))
    for idx, match in enumerate(matches):
        if match.group(1) == label:
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            return text[start:end]
    raise AssertionError(f"Equation {label} not found in analysis/equations.md")


def test_e043_references_hyodo() -> None:
    block = _extract_equation_block("E.043")
    assert "Hyodo2018_ApJ860_150" in block, "E.043 must cite Hyodo et al. (2018)"


def test_e042_references_hyodo() -> None:
    block = _extract_equation_block("E.042")
    assert "Hyodo2018_ApJ860_150" in block, "E.042 must cite Hyodo et al. (2018)"


def test_e006_references_strubbe_chiang() -> None:
    block = _extract_equation_block("E.006")
    assert "StrubbeChiang2006_ApJ648_652" in block, "E.006 must cite Strubbe & Chiang (2006)"
