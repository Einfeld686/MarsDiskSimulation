"""Build a first-pass assumption trace skeleton from equations metadata.

Phase 2 assembles one record per equation (E.xxx) by combining a JSONL
index and light-weight parsing of `analysis/equations.md`. The goal is
to emit a JSONL file usable by downstream tooling and a compact
Markdown table for human review.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class AssumptionRecord:
    """Structured representation of one equation's provenance."""

    eq_id: str
    source_doc: str = "analysis/equations.md"
    paper_ref: list[str] = field(default_factory=list)
    assumption_tags: list[str] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    code_path: list[str] = field(default_factory=list)
    run_stage: Optional[str] = None
    inputs: list[dict[str, str]] = field(default_factory=list)
    outputs: list[dict[str, str]] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    status: str = "draft"
    owner: Optional[str] = None
    last_checked: Optional[str] = None


def load_equation_index(path: Path) -> list[dict[str, Any]]:
    """Load equation index entries from a JSONL file."""

    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                entries.append(obj)
    return entries


def _iter_equation_blocks(lines: list[str]) -> Iterable[tuple[str, str, list[str]]]:
    """Yield (eq_id, header_rest, block_lines) for each equation block."""

    heading_re = re.compile(r"^###\s+\((E\.\d+)\)\s+(.*)$")
    anchors: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        match = heading_re.match(line)
        if match:
            anchors.append((idx, match.group(1), match.group(2)))
    for i, (start, eq_id, rest) in enumerate(anchors):
        end = anchors[i + 1][0] if i + 1 < len(anchors) else len(lines)
        yield eq_id, rest, lines[start:end]


def _clean_code_path(raw: str) -> str:
    """Normalize a code path string by trimming annotations."""

    cleaned = re.split(r"\s|\[", raw, maxsplit=1)[0]
    return cleaned.strip().rstrip("]")


def _extract_code_paths(header_rest: str, block_text: str) -> list[str]:
    """Return normalized code paths from the header and inline anchors."""

    paths: list[str] = []
    header_match = re.search(
        r"(marsdisk/[^\s:()]+\.py)(?::\s*([A-Za-z0-9_\-./]+))?", header_rest
    )
    if header_match:
        module = header_match.group(1)
        name = header_match.group(2)
        if name:
            paths.append(f"{module}#{name}")
        else:
            paths.append(module)

    inline_matches = re.findall(
        r"marsdisk/[A-Za-z0-9_./]+(?:#[A-Za-z0-9_]+)?", block_text
    )
    for match in inline_matches:
        paths.append(match)

    seen: set[str] = set()
    unique: list[str] = []
    for item in paths:
        normalized = _clean_code_path(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _extract_paper_refs(block_text: str) -> list[str]:
    """Return citation keys referenced inside a block."""

    refs: list[str] = []
    for match in re.findall(r"\[@([^\]]+)\]", block_text):
        for token in match.split(";"):
            token = token.strip().lstrip("@")
            if not token or token.lower().startswith("eq"):
                continue
            if token not in refs:
                refs.append(token)
    return refs


def _extract_assumption_tags(block_text: str) -> list[str]:
    """Infer basic assumption tags from free text."""

    tags: list[str] = []
    lowered = block_text.lower()
    if "gas-poor" in lowered or "gas poor" in lowered:
        tags.append("gas-poor")
    if "tl2003" in lowered or "takeuchi" in lowered:
        tags.append("TL2003")
    if " 0d" in lowered or "0d " in lowered or " 0d " in lowered:
        tags.append("0D")
    return tags


def _extract_config_keys(block_text: str) -> list[str]:
    """Collect backticked YAML-like keys."""

    keys: list[str] = []
    for match in re.findall(r"`([A-Za-z0-9_.]+)`", block_text):
        if match not in keys:
            keys.append(match)
    return keys


def _parse_symbols_table(block_lines: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Parse the Symbols table to infer inputs and outputs."""

    inputs: list[dict[str, str]] = []
    outputs: list[dict[str, str]] = []
    header_idx = None
    for idx, line in enumerate(block_lines):
        if line.strip().startswith("|Symbol|Meaning|Units|Defaults/Notes|"):
            header_idx = idx
            break
    if header_idx is None or header_idx + 2 >= len(block_lines):
        return inputs, outputs

    for line in block_lines[header_idx + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        symbol, meaning, units, notes = cells[:4]
        entry = {"name": symbol, "meaning": meaning, "units": units}
        notes_lower = notes.lower()
        if "return" in notes_lower or "returned" in notes_lower:
            outputs.append(entry)
        elif "input" in notes_lower or "must be" in notes_lower:
            inputs.append(entry)
    return inputs, outputs


def _guess_status(eq_id: str) -> str:
    """Return a coarse status based on known gaps."""

    needs_ref_ids = {"E.006", "E.007"}
    return "needs_ref" if eq_id in needs_ref_ids else "draft"


def _map_run_stage(code_paths: list[str]) -> Optional[str]:
    """Map a code path to a coarse run stage label."""

    if not code_paths:
        return None
    target = code_paths[0]
    if "physics/surface.py" in target:
        return "surface loop"
    if "physics/smol.py" in target:
        return "smol step"
    if "physics/fragments.py" in target or "physics/collide.py" in target:
        return "fragments"
    if "physics/shielding.py" in target or "io/tables.py" in target:
        return "radiation/shielding"
    if "run.py" in target:
        return "run_zero_d"
    module = Path(target).stem
    return module if module else None


def _parse_block(eq_id: str, header_rest: str, block_lines: list[str]) -> dict[str, Any]:
    """Extract structured fields from one equation block."""

    block_text = "\n".join(block_lines)
    code_path = _extract_code_paths(header_rest, block_text)
    paper_ref = _extract_paper_refs(block_text)
    assumption_tags = _extract_assumption_tags(block_text)
    config_keys = _extract_config_keys(block_text)
    inputs, outputs = _parse_symbols_table(block_lines)
    return {
        "eq_id": eq_id,
        "code_path": code_path,
        "paper_ref": paper_ref,
        "assumption_tags": assumption_tags,
        "config_keys": config_keys,
        "inputs": inputs,
        "outputs": outputs,
    }


def parse_equations_md(path: Path) -> dict[str, dict[str, Any]]:
    """Parse `analysis/equations.md` and return metadata per equation."""

    lines = path.read_text(encoding="utf-8").splitlines()
    records: dict[str, dict[str, Any]] = {}
    for eq_id, header_rest, block_lines in _iter_equation_blocks(lines):
        records[eq_id] = _parse_block(eq_id, header_rest, block_lines)
    return records


def build_assumption_trace(index_path: Path, equations_md: Path) -> list[AssumptionRecord]:
    """Build assumption trace records from an index and equations.md."""

    index_entries = load_equation_index(index_path)
    eq_meta = parse_equations_md(equations_md)

    records: list[AssumptionRecord] = []
    for entry in index_entries:
        eq_id = entry.get("eq_id")
        if not isinstance(eq_id, str):
            continue
        meta = eq_meta.get(eq_id, {})
        code_path = meta.get("code_path", []) or []
        record = AssumptionRecord(
            eq_id=eq_id,
            source_doc="analysis/equations.md",
            paper_ref=list(meta.get("paper_ref", [])),
            assumption_tags=list(meta.get("assumption_tags", [])),
            config_keys=list(meta.get("config_keys", [])),
            code_path=list(code_path),
            run_stage=_map_run_stage(code_path),
            inputs=list(meta.get("inputs", [])),
            outputs=list(meta.get("outputs", [])),
            tests=[],
            status=_guess_status(eq_id),
            owner=None,
            last_checked=None,
        )
        records.append(record)
    return records


def write_jsonl(records: Iterable[AssumptionRecord], path: Path) -> None:
    """Write records to JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def write_markdown(records: Iterable[AssumptionRecord], path: Path) -> None:
    """Render a compact Markdown table for quick review."""

    sorted_records = sorted(records, key=lambda rec: rec.eq_id)
    lines = [
        "> **文書種別**: メモ（自動生成サマリ）",
        "",
        "## Assumption Trace Summary",
        "",
        "|eq_id|paper_ref|code_path|assumption_tags|config_keys|status|",
        "|---|---|---|---|---|---|",
    ]
    for rec in sorted_records:
        refs = ", ".join(rec.paper_ref)
        paths = "<br>".join(rec.code_path)
        tags = ", ".join(rec.assumption_tags)
        cfgs = ", ".join(rec.config_keys)
        lines.append(
            f"|{rec.eq_id}|{refs}|{paths}|{tags}|{cfgs}|{rec.status}|"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build assumption trace skeleton.")
    parser.add_argument(
        "--index", required=True, type=Path, help="Path to equations_index.jsonl"
    )
    parser.add_argument(
        "--equations",
        type=Path,
        default=Path("analysis/equations.md"),
        help="Path to analysis/equations.md",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=Path("analysis/assumption_trace.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=Path("analysis/assumption_trace.md"),
        help="Output Markdown summary path",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    records = build_assumption_trace(args.index, args.equations)
    write_jsonl(records, args.jsonl)
    write_markdown(records, args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
