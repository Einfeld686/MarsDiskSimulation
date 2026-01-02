"""Scan sources and normalise assumption registry entries.

Steps (per docs/plan/20251209_assumption_autotrace_plan.md):
- load equations (E.xxx) as the canonical eq_id dictionary
- load source_map / inventory as primary code anchors (fallback to rg/ASTは未実装)
- load registry (legacy/new混在) を正規化し scope/provenance 等のデフォルトを補完
- 計算したカバレッジ指標を表示し、正常化した registry を書き戻す

Usage:
    PYTHONPATH=. python -m analysis.tools.scan_assumptions
    PYTHONPATH=. python -m analysis.tools.scan_assumptions --out analysis/assumption_registry.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from analysis.assumption_registry import (
    AssumptionRecord,
    Provenance,
    dump_registry,
    load_registry,
)

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
EQUATIONS_MD = ANALYSIS / "equations.md"
SOURCE_MAP = ANALYSIS / "source_map.json"
INVENTORY = ANALYSIS / "inventory.json"
REGISTRY_PATH = ANALYSIS / "assumption_registry.jsonl"

# run_zero_d.py 段階との対応を固定（フェーズ1用の初期マップ）
RUN_STAGE_HINTS = [
    ("init_ei", "init_ei"),
    ("time_grid", "time_grid"),
    ("physics_controls", "physics_controls"),
    ("surface", "surface_loop"),
    ("smol", "smol_kernel"),
    ("collisions_smol", "smol_kernel"),
    ("shielding", "physics_controls"),
    ("psd", "physics_controls"),
]

# テスト自動補完のゆるいヒント（無ければ追加するだけで既存は保持）
TEST_HINTS = {
    "blowout": ["tests/integration/test_scalings.py", "tests/integration/test_fast_blowout.py"],
    "shield": ["tests/integration/test_radiation_shielding_logging.py", "tests/integration/test_blowout_gate.py"],
    "psd": ["tests/integration/test_psd_kappa.py", "tests/integration/test_surface_outflux_wavy.py"],
    "tcoll": ["tests/integration/test_scalings.py", "tests/integration/test_phase3_surface_blowout.py"],
    "sublim": ["tests/integration/test_sinks_none.py", "tests/integration/test_sublimation_phase_gate.py"],
    "radius": ["tests/integration/test_scope_limitations_metadata.py"],
}


@dataclass
class CoverageReport:
    equation_coverage: float = 0.0
    eq_total: int = 0
    eq_covered: int = 0
    function_reference_rate: float = 0.0
    function_total: int = 0
    function_covered: int = 0
    anchor_consistency_rate: float = 0.0
    anchors_checked: int = 0
    anchors_consistent: int = 0


def parse_equations(path: Path = EQUATIONS_MD) -> list[str]:
    eq_ids: list[str] = []
    if not path.exists():
        return eq_ids
    heading_re = re.compile(r"^###\s+\((E\.\d+)\)")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = heading_re.match(line.strip())
        if m:
            eq_ids.append(m.group(1))
    return eq_ids


def load_source_map(path: Path = SOURCE_MAP) -> dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_inventory(path: Path = INVENTORY) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _normalise_codepath(cp: str) -> str:
    """Drop line numbers and symbols for comparison."""

    cp = cp.split("#", 1)[0]
    if ":" in cp:
        base, *_ = cp.split(":", 1)
        return base
    return cp


def _parse_span(cp: str) -> Optional[Tuple[int, int, str]]:
    """Return (start, end, base_path) if cp has line spans."""

    m = re.match(r"(.+?):(\d+)-(\d+)$", cp)
    if not m:
        return None
    base = m.group(1)
    start = int(m.group(2))
    end = int(m.group(3))
    return start, end, base


def guess_scope(record: AssumptionRecord) -> str:
    if record.scope:
        return record.scope
    tags = " ".join(record.assumption_tags).lower()
    keys = " ".join(record.config_keys)
    if "gas_poor" in tags or "ops:" in tags:
        return "project_default"
    if any(k.lower().startswith("allow") or ".enable" in k.lower() for k in record.config_keys):
        return "toggle"
    return "module_default"


def fill_defaults(records: list[AssumptionRecord]) -> list[AssumptionRecord]:
    filled: list[AssumptionRecord] = []
    for rec in records:
        scope = guess_scope(rec)
        provenance = rec.provenance
        if provenance.source_kind not in ("equation", "config", "code_comment", "test"):
            provenance = Provenance(
                source_kind="equation",
                paper_key=provenance.paper_key,
                unknown_slug=provenance.unknown_slug,
                note=provenance.note,
            )
        # ensure eq_ids unique and sorted
        eq_ids = sorted({eid for eid in rec.eq_ids if eid})
        # fill run_stage if missing using hints
        run_stage = list(rec.run_stage)
        if not run_stage:
            stage_hits = []
            text = " ".join(rec.config_keys + rec.code_path + rec.assumption_tags + [rec.id])
            for key, stage in RUN_STAGE_HINTS:
                if key in text:
                    stage_hits.append(stage)
            run_stage = sorted(set(stage_hits))
        # add test hints if none
        tests = list(rec.tests)
        if not tests:
            hint_text = " ".join(rec.assumption_tags + [rec.id])
            for key, suggested in TEST_HINTS.items():
                if key in hint_text:
                    tests.extend(suggested)
        filled.append(
            AssumptionRecord(
                id=rec.id,
                title=rec.title,
                description=rec.description,
                scope=scope,
                eq_ids=eq_ids,
                assumption_tags=list(rec.assumption_tags),
                config_keys=list(rec.config_keys),
                code_path=list(rec.code_path),
                run_stage=run_stage,
                provenance=provenance,
                tests=sorted(set(tests)),
                outputs=list(rec.outputs),
                status=rec.status,
                last_checked=rec.last_checked,
            )
        )
    return filled


def compute_coverage(records: list[AssumptionRecord], eq_ids: list[str], source_map: dict) -> CoverageReport:
    report = CoverageReport()
    eq_set = set(eq_ids)
    covered = set(eid for rec in records for eid in rec.eq_ids if eid in eq_set)
    report.eq_total = len(eq_set)
    report.eq_covered = len(covered)
    report.equation_coverage = (report.eq_covered / report.eq_total) if report.eq_total else 0.0

    # function_reference_rate: source_map keys vs registry code_path (base paths)
    registry_paths = {_normalise_codepath(cp) for rec in records for cp in rec.code_path if cp}
    source_paths = {_normalise_codepath(k) for k in source_map.keys()}
    intersect = registry_paths & source_paths
    report.function_total = len(source_paths)
    report.function_covered = len(intersect)
    report.function_reference_rate = (report.function_covered / report.function_total) if report.function_total else 0.0

    # anchor_consistency_rate: line spans vs source_map spans (±5行許容)
    anchors_checked = 0
    anchors_consistent = 0
    span_map: dict[str, list[Tuple[int, int]]] = {}
    for key, meta in source_map.items():
        base = _normalise_codepath(key)
        span = meta.get("span")
        if isinstance(span, list) and len(span) == 2:
            span_map.setdefault(base, []).append((int(span[0]), int(span[1])))
    for rec in records:
        for cp in rec.code_path:
            parsed = _parse_span(cp)
            if not parsed:
                continue
            start, end, base = parsed
            anchors_checked += 1
            spans = span_map.get(base, [])
            for s_start, s_end in spans:
                if start >= s_start - 5 and end <= s_end + 5:
                    anchors_consistent += 1
                    break
    report.anchors_checked = anchors_checked
    report.anchors_consistent = anchors_consistent
    report.anchor_consistency_rate = (anchors_consistent / anchors_checked) if anchors_checked else 0.0
    return report


def align_code_paths(records: list[AssumptionRecord], source_map: dict) -> list[AssumptionRecord]:
    """Replace/augment code_path spans using source_map (improves anchor consistency)."""

    span_map: dict[str, list[Tuple[int, int]]] = {}
    for key, meta in source_map.items():
        base = _normalise_codepath(key)
        span = meta.get("span")
        if isinstance(span, list) and len(span) == 2:
            span_map.setdefault(base, []).append((int(span[0]), int(span[1])))

    aligned: list[AssumptionRecord] = []
    for rec in records:
        new_paths: list[str] = []
        for cp in rec.code_path:
            parsed = _parse_span(cp)
            base = _normalise_codepath(cp)
            spans = span_map.get(base, [])
            chosen = None
            if spans:
                # pick the widest span for stability
                s_start, s_end = max(spans, key=lambda x: x[1] - x[0])
                chosen = f"{base}:{s_start}-{s_end}"
            if parsed:
                _, _, base_parsed = parsed
                if base_parsed in span_map:
                    new_paths.append(chosen or cp)
                else:
                    new_paths.append(cp)
            else:
                new_paths.append(chosen or cp)
        aligned.append(
            AssumptionRecord(
                id=rec.id,
                title=rec.title,
                description=rec.description,
                scope=rec.scope,
                eq_ids=list(rec.eq_ids),
                assumption_tags=list(rec.assumption_tags),
                config_keys=list(rec.config_keys),
                code_path=sorted(set(new_paths)),
                run_stage=list(rec.run_stage),
                provenance=rec.provenance,
                tests=list(rec.tests),
                outputs=list(rec.outputs),
                status=rec.status,
                last_checked=rec.last_checked,
            )
        )
    return aligned


def _print_report(report: CoverageReport) -> None:
    print(f"equation_coverage: {report.eq_covered}/{report.eq_total} = {report.equation_coverage:.3f}")
    print(f"function_reference_rate: {report.function_covered}/{report.function_total} = {report.function_reference_rate:.3f}")
    print(f"anchor_consistency_rate: {report.anchors_consistent}/{report.anchors_checked} = {report.anchor_consistency_rate:.3f}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Normalise assumption registry and compute coverage.")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Input registry path (JSONL)")
    parser.add_argument("--out", type=Path, default=REGISTRY_PATH, help="Output path for normalised registry")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output file")
    args = parser.parse_args(argv)

    eq_ids = parse_equations(EQUATIONS_MD)
    source_map = load_source_map(SOURCE_MAP)
    _ = load_inventory(INVENTORY)  # reserved for future AST/rg phase

    records = load_registry(args.registry)
    records = fill_defaults(records)
    records = align_code_paths(records, source_map)
    report = compute_coverage(records, eq_ids, source_map)
    _print_report(report)

    if not args.dry_run:
        dump_registry(records, args.out)
        print(f"wrote normalised registry to {args.out}")
    else:
        print("dry-run: registry not written")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
