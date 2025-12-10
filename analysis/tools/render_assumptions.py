"""Render assumption docs from assumption_registry.jsonl.

Outputs:
- analysis/assumptions_overview.md （全自動生成）
- analysis/assumption_trace.md の自動ブロック (@-- BEGIN:ASSUMPTION_REGISTRY --〜END)

Registry は `analysis/assumption_registry.jsonl`（新スキーマ）を単一ソースとし、
equations/source_map のカバレッジを併せて表示する。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Tuple

from analysis.assumption_registry import AssumptionRecord, load_registry
from analysis.tools.scan_assumptions import (
    CoverageReport,
    compute_coverage,
    load_source_map,
    parse_equations,
)

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
REGISTRY_PATH = ANALYSIS / "assumption_registry.jsonl"
ASSUMPTIONS_OVERVIEW = ANALYSIS / "assumptions_overview.md"
ASSUMPTION_TRACE = ANALYSIS / "assumption_trace.md"
AUTO_BEGIN = "<!-- @-- BEGIN:ASSUMPTION_REGISTRY -- -->"
AUTO_END = "<!-- @-- END:ASSUMPTION_REGISTRY -- -->"


def _render_table(records: Iterable[AssumptionRecord]) -> list[str]:
    lines = []
    lines.append("| id | scope | eq_ids | tags | config_keys | run_stage | provenance | status |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for rec in records:
        prov = rec.provenance
        prov_text = prov.paper_key or prov.unknown_slug or prov.source_kind
        lines.append(
            "| {id} | {scope} | {eqs} | {tags} | {cfg} | {stage} | {prov} | {status} |".format(
                id=rec.id,
                scope=rec.scope or "-",
                eqs=", ".join(rec.eq_ids) if rec.eq_ids else "-",
                tags=", ".join(rec.assumption_tags) if rec.assumption_tags else "-",
                cfg=", ".join(rec.config_keys) if rec.config_keys else "-",
                stage=", ".join(rec.run_stage) if rec.run_stage else "-",
                prov=prov_text or "-",
                status=rec.status,
            )
        )
    return lines


def render_overview(records: list[AssumptionRecord], report: CoverageReport) -> str:
    lines: list[str] = []
    lines.append("> **文書種別**: 解説（自動生成）")
    lines.append("> AUTO-GENERATED: DO NOT EDIT BY HAND. Run `python -m analysis.tools.render_assumptions`.")
    lines.append("")
    lines.append("## 0. この文書の目的")
    lines.append(
        "仮定トレースの機械可読データ（assumption_registry.jsonl）から、タグ・設定・コードパスを人間が確認しやすい形でまとめる。"
    )
    lines.append(
        "数式本文は `analysis/equations.md` が唯一のソースであり、本書では eq_id とラベルだけを参照する。UNKNOWN_REF_REQUESTS の slug は TODO(REF:slug) として維持する。"
    )
    lines.append("")

    lines.append("## 1. カバレッジ指標")
    lines.append(f"- equation_coverage: {report.eq_covered}/{report.eq_total} = {report.equation_coverage:.3f}")
    lines.append(
        f"- function_reference_rate: {report.function_covered}/{report.function_total} = {report.function_reference_rate:.3f}"
    )
    lines.append(
        f"- anchor_consistency_rate: {report.anchors_consistent}/{report.anchors_checked} = {report.anchor_consistency_rate:.3f}"
    )
    lines.append("")

    lines.append("## 2. レコード一覧")
    lines.extend(_render_table(records))
    lines.append("")
    return "\n".join(lines)


def render_trace_block(records: list[AssumptionRecord]) -> str:
    lines: list[str] = []
    lines.append("### 自動生成セクション（assumption_registry.jsonl 由来）")
    lines.extend(_render_table(records))
    lines.append("")
    return "\n".join(lines)


def _replace_block(path: Path, content: str) -> None:
    """Replace or append the auto block in assumption_trace.md."""

    if not path.exists():
        base_lines = [
            "> **文書種別**: 解説（Diátaxis: Explanation）",
            "",
            "## 自動生成サマリ",
        ]
        text = "\n".join(base_lines) + "\n"
    else:
        text = path.read_text(encoding="utf-8")
    if AUTO_BEGIN in text and AUTO_END in text:
        begin_idx = text.index(AUTO_BEGIN)
        end_idx = text.index(AUTO_END)
        if end_idx < begin_idx:
            end_idx = begin_idx
        prefix = text[:begin_idx]
        suffix = text[end_idx + len(AUTO_END) :]
        new_text = prefix + AUTO_BEGIN + "\n" + content + AUTO_END + suffix
    else:
        if not text.endswith("\n"):
            text += "\n"
        new_text = text + f"\n{AUTO_BEGIN}\n{content}{AUTO_END}\n"
    path.write_text(new_text, encoding="utf-8")


def _load_records(path: Path) -> list[AssumptionRecord]:
    return load_registry(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render assumption docs from registry.")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Path to assumption_registry.jsonl")
    parser.add_argument("--overview", type=Path, default=ASSUMPTIONS_OVERVIEW, help="Path to assumptions_overview.md")
    parser.add_argument("--trace", type=Path, default=ASSUMPTION_TRACE, help="Path to assumption_trace.md")
    args = parser.parse_args(argv)

    records = _load_records(args.registry)
    eq_ids = parse_equations()
    source_map = load_source_map()
    report = compute_coverage(records, eq_ids, source_map)

    overview_md = render_overview(records, report)
    args.overview.write_text(overview_md, encoding="utf-8")

    trace_block = render_trace_block(records)
    _replace_block(args.trace, trace_block)

    print(f"Rendered {args.overview} and updated auto block in {args.trace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
