"""Phase 3: propagate assumption gaps into structured trackers.

This tool:
- parses `analysis/assumption_trace_gap_list.md`
- maps each gap to candidate equations, code paths, and config keys
- ensures `analysis/UNKNOWN_REF_REQUESTS.jsonl` contains an entry per gap
- optionally upserts placeholder assumption-trace records with status=needs_ref
- refreshes an auto-generated memo block in `analysis/overview.md`

Usage:
    PYTHONPATH=. python analysis/tools/assumption_trace_phase3.py
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
GAP_LIST_DEFAULT = ROOT / "analysis" / "assumption_trace_gap_list.md"
UNKNOWN_REF_PATH = ROOT / "analysis" / "UNKNOWN_REF_REQUESTS.jsonl"
ASSUMPTION_TRACE_PATH = ROOT / "analysis" / "assumption_trace.jsonl"
OVERVIEW_PATH = ROOT / "analysis" / "overview.md"


@dataclass
class Gap:
    """Structured representation of one gap entry."""

    label: str
    title: str
    description: str
    needed_info: str
    slug: str
    eq_ids: list[str]
    paper_refs: list[str]
    code_paths: list[str]
    config_keys: list[str]
    priority: str = "medium"


def normalise_label(text: str) -> str:
    """Return a lowercase ASCII-ish label suitable for slugs."""

    cleaned = re.sub(r"[^\w]+", "_", text)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or "gap"


def parse_gap_list(path: Path) -> list[Gap]:
    """Parse the gap list markdown into Gap objects."""

    if not path.exists():
        raise FileNotFoundError(f"Gap list not found: {path}")

    content = path.read_text(encoding="utf-8").splitlines()
    gaps: list[Gap] = []
    bullet_re = re.compile(r"^- \*\*(.+?)\*\*[:：](.+)$")
    for line in content:
        m = bullet_re.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        rest = m.group(2).strip()
        needed_info = ""
        desc = rest
        if "必要情報" in rest:
            parts = re.split(r"必要情報[:：]", rest, maxsplit=1)
            desc = parts[0].strip()
            needed_info = parts[1].strip() if len(parts) > 1 else ""
        label = normalise_label(title)
        slug = f"gap_{label}_v1"
        gaps.append(
            Gap(
                label=label,
                title=title,
                description=desc,
                needed_info=needed_info,
                slug=slug,
                eq_ids=[],
                paper_refs=[],
                code_paths=[],
                config_keys=[],
            )
        )
    return gaps


def _iter_equation_blocks(text: str) -> Iterable[tuple[str, str]]:
    """Yield (eq_id, block_text) for each equation in analysis/equations.md."""

    lines = text.splitlines()
    heading_re = re.compile(r"^###\s+\((E\.\d+)\)")
    anchors: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            anchors.append((idx, m.group(1)))
    for i, (start, eq_id) in enumerate(anchors):
        end = anchors[i + 1][0] if i + 1 < len(anchors) else len(lines)
        block = "\n".join(lines[start:end])
        yield eq_id, block


def _keywords_for_gap(gap: Gap) -> list[str]:
    """Return heuristic keywords to search for."""

    lowered = gap.label
    if "blow" in lowered:
        return ["t_blow", "beta", "a_blow", "blowout", "fast_blowout"]
    if "shield" in lowered or "gate" in lowered:
        return ["phi", "Phi(", "tau_gate", "psi_shield", "gate_mode", "tau=1"]
    if "wavy" in lowered or "psd" in lowered:
        return ["wavy", "psd", "s_min_effective", "psd.floor", "wavy_strength"]
    if "coll" in lowered:
        return ["t_coll", "Wyatt", "Ohtsuki", "collision", "use_tcoll"]
    if "sublim" in lowered or "gasdrag" in lowered or "gas_drag" in lowered:
        return ["sinks", "sublimation", "gas_drag", "TL2003", "rp_blowout"]
    if "radius" in lowered or "geometry" in lowered:
        return ["disk.geometry", "0D"]
    return [gap.label]


def map_gaps_to_equations(gaps: list[Gap], equations_md: Path) -> None:
    """Populate eq_ids and paper_refs for gaps using analysis/equations.md."""

    if not equations_md.exists():
        return
    text = equations_md.read_text(encoding="utf-8")
    blocks = list(_iter_equation_blocks(text))
    for gap in gaps:
        keywords = _keywords_for_gap(gap)
        eq_hits: list[str] = []
        paper_refs: list[str] = []
        for eq_id, block in blocks:
            lower_block = block.lower()
            if any(keyword.lower() in lower_block for keyword in keywords):
                eq_hits.append(eq_id)
                for ref in re.findall(r"\[@([^\]]+)\]", block):
                    for token in ref.split(";"):
                        token = token.strip().lstrip("@")
                        if token and token not in paper_refs:
                            paper_refs.append(token)
        gap.eq_ids = eq_hits
        gap.paper_refs = paper_refs


def search_code_paths(gaps: list[Gap], code_roots: Sequence[Path]) -> None:
    """Populate code_paths heuristically from code files."""

    for gap in gaps:
        keywords = _keywords_for_gap(gap)
        hits: list[str] = []
        for root in code_roots:
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                lower_text = text.lower()
                if not any(k.lower() in lower_text for k in keywords):
                    continue
                for match in re.finditer(r"^def\s+([A-Za-z0-9_]+)", text, flags=re.MULTILINE):
                    func_name = match.group(1)
                    context_start = max(0, match.start() - 200)
                    context_end = min(len(text), match.end() + 200)
                    context = text[context_start:context_end].lower()
                    if any(k.lower() in context for k in keywords):
                        entry = f"{path.relative_to(ROOT)}:{func_name}"
                        if entry not in hits:
                            hits.append(entry)
                # Fallback: module-level match
                if not hits and any(k.lower() in lower_text for k in keywords):
                    entry = f"{path.relative_to(ROOT)}"
                    if entry not in hits:
                        hits.append(entry)
        gap.code_paths = hits


def search_config_keys(gaps: list[Gap], config_root: Path) -> None:
    """Collect related config keys from configs/*.yml."""

    if not config_root.exists():
        return
    config_texts = []
    for path in config_root.glob("*.yml"):
        config_texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    joined = "\n".join(config_texts).lower()
    known_keys = [
        "blowout.enabled",
        "radiation.source",
        "radiation.tau_gate.enable",
        "io.correct_fast_blowout",
        "shielding.mode",
        "shielding.table_path",
        "psd.floor.mode",
        "psd.wavy_strength",
        "sinks.mode",
        "sinks.enable_gas_drag",
        "sinks.enable_sublimation",
        "disk.geometry.r_in_rm",
        "disk.geometry.r_out_rm",
        "surface.use_tcoll",
    ]
    for gap in gaps:
        keys: list[str] = []
        for key in known_keys:
            if key.lower() in joined and any(k in key.lower() for k in _keywords_for_gap(gap)):
                keys.append(key)
        gap.config_keys = keys


def load_unknown_refs(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load UNKNOWN_REF_REQUESTS.jsonl into a slug->record mapping."""

    if not path.exists():
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        slug = obj.get("slug")
        if isinstance(slug, str):
            records[slug] = obj
    return records


def upsert_unknown_refs(path: Path, gaps: list[Gap]) -> Dict[str, Dict[str, Any]]:
    """Ensure one unknown-ref entry per gap."""

    records = load_unknown_refs(path)
    out_lines: list[str] = []
    for gap in gaps:
        slug = gap.slug
        priority = "high" if any(
            token in gap.label for token in ["blow", "shield", "coll"]
        ) else "medium"
        where = (
            f"analysis/equations.md:{','.join(gap.eq_ids)}"
            if gap.eq_ids
            else (gap.code_paths[0] if gap.code_paths else "analysis/assumption_trace_gap_list.md")
        )
        summary = f"{gap.title}: {gap.description} / 必要情報: {gap.needed_info}"
        record = records.get(slug, {})
        record.update(
            {
                "slug": slug,
                "type": "assumption",
                "where": where,
                "assumptions": summary,
                "priority": priority,
            }
        )
        records[slug] = record
    for slug, obj in records.items():
        out_lines.append(json.dumps(obj, ensure_ascii=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return records


def load_assumption_trace(path: Path) -> list[Dict[str, Any]]:
    """Load existing assumption_trace.jsonl if present."""

    if not path.exists():
        return []
    items: list[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _map_run_stage_from_code(code_path: str) -> Optional[str]:
    if "surface.py" in code_path:
        return "surface loop"
    if "smol.py" in code_path:
        return "smol step"
    if "fragments.py" in code_path or "collide.py" in code_path:
        return "fragments"
    if "shielding.py" in code_path or "io/tables.py" in code_path:
        return "radiation/shielding"
    if "run.py" in code_path:
        return "run_zero_d"
    return None


def upsert_assumption_trace(path: Path, gaps: list[Gap]) -> list[Dict[str, Any]]:
    """Insert placeholder assumption-trace records with status=needs_ref."""

    existing = load_assumption_trace(path)
    updated: list[Dict[str, Any]] = []
    # Map for idempotency using (eq_id, slug_tag)
    seen_keys: set[tuple[str, str]] = set()
    for item in existing:
        tags = item.get("assumption_tags", []) or []
        slug_tags = [t for t in tags if t.startswith("gap:")]
        key = (item.get("eq_id", ""), slug_tags[0] if slug_tags else "")
        seen_keys.add(key)
        updated.append(item)

    for gap in gaps:
        slug_tag = f"gap:{gap.slug}"
        eq_ids = gap.eq_ids or [f"TODO(REF:{gap.slug})"]
        for eq_id in eq_ids:
            key = (eq_id, slug_tag)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            code_path = gap.code_paths
            run_stage = _map_run_stage_from_code(code_path[0]) if code_path else None
            record = {
                "eq_id": eq_id,
                "source_doc": "analysis/equations.md",
                "paper_ref": gap.paper_refs,
                "assumption_tags": [slug_tag],
                "config_keys": gap.config_keys,
                "code_path": code_path,
                "run_stage": run_stage,
                "inputs": [],
                "outputs": [],
                "tests": [],
                "status": "needs_ref",
                "owner": None,
                "last_checked": None,
            }
            updated.append(record)

    lines = [json.dumps(item, ensure_ascii=False) for item in updated]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def render_overview_block(gaps: list[Gap]) -> str:
    """Render the auto-generated memo block for overview.md."""

    lines = [
        "@-- BEGIN:ASSUMPTION_GAPS_AUTO --",
        "## 未整理の前提と TODO（自動生成）",
        "",
    ]
    for gap in gaps:
        eq_display = ", ".join(gap.eq_ids) if gap.eq_ids else "未特定"
        code_display = gap.code_paths[0] if gap.code_paths else "未特定"
        lines.append(
            f"- {gap.title}: slug=`{gap.slug}`, status=needs_ref, eq_id≈{eq_display}, code≈{code_display}"
        )
    lines.append("")
    lines.append("（このブロックは `analysis/tools/assumption_trace_phase3.py` により自動生成されます。手編集しないでください。）")
    lines.append("@-- END:ASSUMPTION_GAPS_AUTO --")
    return "\n".join(lines) + "\n"


def update_overview(path: Path, block: str) -> None:
    """Insert or replace the sentinel block in overview.md."""

    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    begin = "@-- BEGIN:ASSUMPTION_GAPS_AUTO --"
    end = "@-- END:ASSUMPTION_GAPS_AUTO --"
    if begin in text and end in text:
        new_text = re.sub(
            rf"{re.escape(begin)}.*?{re.escape(end)}",
            block.strip(),
            text,
            flags=re.DOTALL,
        )
    else:
        new_text = text.rstrip() + "\n\n" + block
    path.write_text(new_text, encoding="utf-8")


def find_gap_list_path() -> Path:
    """Return the gap list path, preferring analysis/ then out/plan/."""

    primary = GAP_LIST_DEFAULT
    if primary.exists():
        return primary
    fallback = ROOT / "out" / "plan" / "assumption_trace_gap_list.md"
    if fallback.exists():
        return fallback
    raise FileNotFoundError("assumption_trace_gap_list.md not found in analysis/ or out/plan/")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3 assumption-trace propagation")
    parser.add_argument(
        "--gap-list",
        type=Path,
        default=None,
        help="Path to assumption_trace_gap_list.md (default: analysis/… or out/plan/…)",
    )
    parser.add_argument(
        "--equations",
        type=Path,
        default=ROOT / "analysis" / "equations.md",
        help="Path to analysis/equations.md",
    )
    args = parser.parse_args(argv)

    try:
        gap_list_path = args.gap_list or find_gap_list_path()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1

    gaps = parse_gap_list(gap_list_path)
    map_gaps_to_equations(gaps, args.equations)
    search_code_paths(gaps, [ROOT / "marsdisk"])
    search_config_keys(gaps, ROOT / "configs")

    upsert_unknown_refs(UNKNOWN_REF_PATH, gaps)
    upsert_assumption_trace(ASSUMPTION_TRACE_PATH, gaps)
    overview_block = render_overview_block(gaps)
    update_overview(OVERVIEW_PATH, overview_block)
    print(f"[INFO] processed {len(gaps)} gaps; outputs updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
