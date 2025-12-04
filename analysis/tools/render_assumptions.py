"""Render human-friendly assumption overview from machine-readable traces.

検索で見つかった仮定トレースファイル（JSON/JSONL）を読み込み、
`analysis/assumptions_overview.md` を自動生成する。入力が見つからない場合でも、
空の一覧を生成して DocSync/coverage のフローを壊さない。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "analysis"
OUTPUT_MD = ANALYSIS_DIR / "assumptions_overview.md"

TRACE_PATTERNS = [
    "analysis/assumption_trace.json",
    "analysis/assumption_trace.jsonl",
    "analysis/assumption_trace.yaml",
    "analysis/assumption_trace.yml",
    "analysis/assumption_trace.*",
    "analysis/traceability/assumptions.*",
]

GAP_LIST_CANDIDATES = [
    ANALYSIS_DIR / "assumption_trace_gap_list.md",
    REPO_ROOT / "out" / "plan" / "assumption_trace_gap_list.md",
]

REQUIRED_FIELDS = [
    "eq_id",
    "assumption_tags",
    "config_keys",
    "code_path",
    "status",
]

GLOBAL_TAG_DESC = {
    "gas-poor": "ガスに乏しい衝突起源円盤を既定とする前提。",
    "0D": "半径を固定した0Dモードのみを対象とする前提。",
    "TL2003": "Takeuchi & Lin (2003) のガスリッチ前提。標準では無効。",
    "t_blow_eq_1_over_Omega": "滞在時間を t_blow=1/Ω と近似する前提。",
    "tau_thin": "光学的に薄い(τ≪1)層を仮定する前提。",
}


@dataclass
class TraceEntry:
    eq_id: str
    paper_ref: list[str]
    assumption_tags: list[str]
    config_keys: list[str]
    code_path: list[str]
    run_stage: Optional[str]
    inputs: list[Any]
    outputs: list[Any]
    tests: list[str]
    status: str


@dataclass
class GapItem:
    title: str
    description: str


def discover_trace_files() -> list[Path]:
    """Return the first matching trace file paths."""

    found: list[Path] = []
    for pattern in TRACE_PATTERNS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and path not in found:
                found.append(path)
    return found


def load_json_or_jsonl(path: Path) -> list[dict]:
    """Load a JSON or JSONL file into a list of dicts."""

    if path.suffix.lower() == ".jsonl":
        items: list[dict] = []
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
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def coerce_entry(raw: dict) -> TraceEntry:
    """Ensure required fields exist and normalise missing data."""

    return TraceEntry(
        eq_id=str(raw.get("eq_id", "")),
        paper_ref=list(raw.get("paper_ref", []) or []),
        assumption_tags=list(raw.get("assumption_tags", []) or []),
        config_keys=list(raw.get("config_keys", []) or []),
        code_path=list(raw.get("code_path", []) or []),
        run_stage=raw.get("run_stage"),
        inputs=list(raw.get("inputs", []) or []),
        outputs=list(raw.get("outputs", []) or []),
        tests=list(raw.get("tests", []) or []),
        status=str(raw.get("status", "draft")),
    )


def load_traces(paths: list[Path]) -> list[TraceEntry]:
    """Load the first available trace file, or return an empty list."""

    for path in paths:
        items = load_json_or_jsonl(path)
        if items:
            return [coerce_entry(item) for item in items]
    return []


def load_gap_list() -> list[GapItem]:
    """Load gap list entries if available."""

    for candidate in GAP_LIST_CANDIDATES:
        if candidate.exists():
            entries: list[GapItem] = []
            bullet_re = re.compile(r"^- \*\*(.+?)\*\*[:：](.+)$")
            for line in candidate.read_text(encoding="utf-8").splitlines():
                m = bullet_re.match(line.strip())
                if not m:
                    continue
                title = m.group(1).strip()
                desc = m.group(2).strip()
                entries.append(GapItem(title=title, description=desc))
            return entries
    return []


def group_by_tag(traces: list[TraceEntry]) -> dict[str, list[TraceEntry]]:
    groups: dict[str, list[TraceEntry]] = defaultdict(list)
    for entry in traces:
        for tag in entry.assumption_tags:
            groups[tag].append(entry)
    return groups


def render_overview(traces: list[TraceEntry], gaps: list[GapItem]) -> str:
    """Render the Markdown content."""

    lines: list[str] = []
    lines.append("> **文書種別**: 解説（自動生成）")
    lines.append("> AUTO-GENERATED: DO NOT EDIT BY HAND. Run `python -m analysis.tools.render_assumptions`.")
    lines.append("")
    lines.append("## 0. この文書の目的")
    lines.append(
        "仮定トレースの機械可読データ（assumption_trace.*）から、タグ・設定・コードパスを人間が確認しやすい形でまとめる。"
    )
    lines.append(
        "数式本文は `analysis/equations.md` が唯一のソースであり、本書では eq_id とラベルだけを参照する。UNKNOWN_REF_REQUESTS の slug は TODO(REF:slug) として維持する。"
    )
    lines.append("")

    # Section 1: global tags
    lines.append("## 1. グローバルな仮定ラベル一覧")
    tag_groups = group_by_tag(traces)
    if not tag_groups:
        lines.append("- 仮定トレースが未登録（0件）。")
    else:
        for tag, desc in GLOBAL_TAG_DESC.items():
            if tag in tag_groups:
                entries = tag_groups[tag]
                eqs = ", ".join(sorted({e.eq_id for e in entries if e.eq_id}))
                cfgs = ", ".join(sorted({cfg for e in entries for cfg in e.config_keys}))
                lines.append(f"- `{tag}`: {desc} 例: eq_id=({eqs}) / config_keys=({cfgs})")
    lines.append("")

    # Section 2: gap-aligned blocks
    lines.append("## 2. ブロック別の仮定メモ")
    if not gaps:
        lines.append("- ギャップメモ未登録。")
    else:
        for idx, gap in enumerate(gaps, start=1):
            lines.append(f"### 2.{idx} {gap.title}")
            lines.append(f"- 概要: {gap.description}")
            related = [
                t
                for t in traces
                if gap.title.split("（")[0] in " ".join(t.assumption_tags + [t.eq_id])
                or any(gap.title.split("（")[0] in cp for cp in t.code_path)
            ]
            if not related:
                lines.append("- 関連するトレース: 未登録 (TODO/needs_ref)")
                lines.append("")
                continue
            eqs = ", ".join(sorted({t.eq_id for t in related if t.eq_id}))
            tags = ", ".join(sorted({tag for t in related for tag in t.assumption_tags}))
            cfgs = ", ".join(sorted({cfg for t in related for cfg in t.config_keys}))
            codes = "; ".join(
                f"{cp} ({t.run_stage})" if t.run_stage else cp for t in related for cp in t.code_path
            )
            outs = ", ".join(sorted({str(o) for t in related for o in t.outputs}))
            tests = ", ".join(sorted({test for t in related for test in t.tests}))
            lines.append(f"- eq_id: {eqs if eqs else '未特定'}")
            lines.append(f"- assumption_tags: {tags if tags else '未特定'}")
            lines.append(f"- config_keys: {cfgs if cfgs else '未特定'}")
            lines.append(f"- code_path/run_stage: {codes if codes else '未特定'}")
            lines.append(f"- outputs: {outs if outs else '未特定'}")
            lines.append(f"- tests: {tests if tests else '未特定'}")
            lines.append("")

    # Section 3: outstanding
    lines.append("## 3. 今後埋めるべきギャップ")
    pending = [t for t in traces if t.status != "ok"]
    if not pending:
        lines.append("- 未解決のエントリはありません。")
    else:
        for t in pending:
            lines.append(
                f"- {t.eq_id}: status={t.status}, tags={', '.join(t.assumption_tags)}, code={', '.join(t.code_path)}"
            )
    lines.append("")
    return "\n".join(lines)


def write_overview(content: str, path: Path = OUTPUT_MD) -> None:
    path.write_text(content, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render assumptions_overview.md from trace data.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_MD,
        help="Output Markdown path (default: analysis/assumptions_overview.md)",
    )
    args = parser.parse_args(argv)

    trace_files = discover_trace_files()
    traces = load_traces(trace_files)
    gaps = load_gap_list()
    content = render_overview(traces, gaps)
    write_overview(content, args.output)
    print(f"[INFO] assumptions_overview.md generated with {len(traces)} entries from {trace_files[:1] if trace_files else 'none'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
