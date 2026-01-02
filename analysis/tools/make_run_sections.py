#!/usr/bin/env python3
"""Generate run_py_sections.md from inventory.json.

This script creates a section map of marsdisk/run_zero_d.py to help AI agents
navigate the large file efficiently. The output uses
AUTOGEN markers so that line numbers are updated automatically when
DocSyncAgent runs.

Usage:
    python -m analysis.tools.make_run_sections --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "analysis"
INVENTORY_PATH = ANALYSIS_DIR / "inventory.json"
TARGET_DOC = ANALYSIS_DIR / "run_py_sections.md"
RUN_PY_PATH = "marsdisk/run_zero_d.py"
RUN_ORCHESTRATOR_PATH = "marsdisk/orchestrator.py"


AUTOGEN_START = "<!-- AUTOGEN:RUN_SECTIONS START -->"
AUTOGEN_END = "<!-- AUTOGEN:RUN_SECTIONS END -->"


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    line_no: int
    end_line: Optional[int]
    signature: str
    brief_usage: str


def load_inventory() -> Dict[str, List[SymbolInfo]]:
    """Load inventory.json and group symbols by file path."""
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Missing inventory file: {INVENTORY_PATH}")
    items = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise RuntimeError("inventory.json must contain a list of symbol entries.")
    
    by_file: Dict[str, List[SymbolInfo]] = {}
    for entry in items:
        file_path = entry.get("file_path", "")
        symbol = entry.get("symbol", "")
        line_no = entry.get("line_no", 0)
        end_line = entry.get("end_line")
        signature = entry.get("signature", "")
        brief = entry.get("brief_usage", "")
        
        info = SymbolInfo(symbol, line_no, end_line, signature, brief)
        by_file.setdefault(file_path, []).append(info)
    
    return by_file


def get_run_py_symbols(inventory: Dict[str, List[SymbolInfo]]) -> List[SymbolInfo]:
    """Extract and sort symbols from run_zero_d.py."""
    # Prefer run_zero_d symbols for the overview
    symbols = inventory.get(RUN_PY_PATH, [])
    if not symbols:
        symbols = inventory.get(RUN_ORCHESTRATOR_PATH, [])
    return sorted(symbols, key=lambda s: s.line_no)



def categorize_symbol(sym: SymbolInfo) -> str:
    """Return a category label for grouping."""
    name = sym.symbol
    if name == "run_zero_d":
        return "main_driver"
    if name.startswith("_"):
        return "helper"
    if name[0].isupper():
        return "class"
    return "function"


def build_sections_table(symbols: List[SymbolInfo]) -> str:
    """Build markdown tables describing file structure."""
    lines = []
    
    # Separate top-level vs run_zero_d nested
    top_level = []
    nested = []
    in_run_zero_d = False
    run_zero_d_start = 0
    run_zero_d_end = 0
    
    for sym in symbols:
        if sym.symbol == "run_zero_d":
            in_run_zero_d = True
            run_zero_d_start = sym.line_no
            run_zero_d_end = sym.end_line or sym.line_no
            top_level.append(sym)
        elif in_run_zero_d and sym.line_no <= run_zero_d_end:
            nested.append(sym)
        else:
            if in_run_zero_d and sym.line_no > run_zero_d_end:
                in_run_zero_d = False
            top_level.append(sym)
    
    # Build top-level table
    lines.append("## 1. トップレベル構造\n")
    lines.append("| シンボル | 行 | 種別 | 概要 |")
    lines.append("|---------|-----|------|------|")
    
    for sym in top_level:
        cat = categorize_symbol(sym)
        cat_jp = {"main_driver": "メイン", "helper": "ヘルパー", "class": "クラス", "function": "関数"}.get(cat, cat)
        brief = sym.brief_usage[:50] + "..." if len(sym.brief_usage) > 50 else sym.brief_usage
        if sym.end_line:
            lines.append(f"| `{sym.symbol}` | L{sym.line_no}–{sym.end_line} | {cat_jp} | {brief} |")
        else:
            lines.append(f"| `{sym.symbol}` | L{sym.line_no} | {cat_jp} | {brief} |")
    
    # Build nested functions table
    if nested:
        lines.append("\n## 2. `run_zero_d()` 内部のネスト関数\n")
        lines.append("| 関数名 | 行 | 概要 |")
        lines.append("|--------|-----|------|")
        
        for sym in nested:
            brief = sym.brief_usage[:60] + "..." if len(sym.brief_usage) > 60 else sym.brief_usage
            if sym.end_line:
                lines.append(f"| `{sym.symbol}` | L{sym.line_no}–{sym.end_line} | {brief} |")
            else:
                lines.append(f"| `{sym.symbol}` | L{sym.line_no} | {brief} |")
    
    # Key sections based on known structure
    lines.append("\n## 3. 主要セクション（目安）\n")
    lines.append("> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。\n")
    
    # Find key markers
    run_zero_d_sym = next((s for s in symbols if s.symbol == "run_zero_d"), None)
    main_sym = next((s for s in symbols if s.symbol == "main"), None)
    orchestrate_sym = next((s for s in symbols if s.symbol == "OrchestratorContext"), None)
    
    if orchestrate_sym:
        lines.append(f"- **`OrchestratorContext`**: L{orchestrate_sym.line_no}–{orchestrate_sym.end_line or '?'} (実行コンテキスト管理)")
    if run_zero_d_sym:
        lines.append(f"- **`run_zero_d()`**: L{run_zero_d_sym.line_no}–{run_zero_d_sym.end_line or '?'} (メイン実行ドライバ)")
    if main_sym:
        lines.append(f"- **`main()`**: L{main_sym.line_no}–{main_sym.end_line or '?'} (CLI エントリポイント)")

    
    # Find streaming/checkpoint classes
    streaming = next((s for s in symbols if s.symbol == "StreamingState"), None)
    if streaming:
        lines.append(f"- **`StreamingState`**: L{streaming.line_no}–{streaming.end_line or '?'} (ストリーミング出力管理)")
    
    history = next((s for s in symbols if s.symbol == "ZeroDHistory"), None)
    if history:
        lines.append(f"- **`ZeroDHistory`**: L{history.line_no}–{history.end_line or '?'} (ステップ履歴管理)")
    
    return "\n".join(lines)


def build_exploration_guide(symbols: List[SymbolInfo]) -> str:
    """Build a guide for common exploration tasks."""
    lines = []
    lines.append("\n## 4. 探索ガイド\n")
    lines.append("| 調べたいこと | 参照シンボル | 備考 |")
    lines.append("|-------------|-------------|------|")
    
    guides = [
        ("設定ロード", "load_config", "YAML→Config変換"),
        ("時間グリッド", "resolve_time_grid", "dt, n_steps決定"),
        ("シード解決", "resolve_seed", "RNG初期化"),
        ("高速ブローアウト補正", "fast_blowout_correction_factor", "dt/t_blow補正"),
        ("進捗表示", "ProgressReporter", "プログレスバー"),
        ("履歴書き出し", "_write_zero_d_history", "Parquet/CSV出力"),
        ("Phase5比較", "run_phase5_comparison", "バリアント比較"),
    ]

    
    for task, sym_name, note in guides:
        sym = next((s for s in symbols if s.symbol == sym_name), None)
        if sym:
            lines.append(f"| {task} | [`{sym_name}`](L{sym.line_no}) | {note} |")
        else:
            lines.append(f"| {task} | `{sym_name}` | {note} (未検出) |")
    
    return "\n".join(lines)


def build_full_document(symbols: List[SymbolInfo]) -> str:
    """Build the complete markdown document."""
    header = """# run_zero_d.py 内部セクション対応表

> **文書種別**: リファレンス（Diátaxis: Reference）
> **自動生成**: このドキュメントは `analysis/tools/make_run_sections.py` により自動生成されます。
> 手動編集しないでください。

本ドキュメントは `marsdisk/run_zero_d.py` の内部構造をセクション別に分類し、
AIエージェントがコード検索を効率化するためのマップを提供します。

---

"""
    
    sections_table = build_sections_table(symbols)
    exploration_guide = build_exploration_guide(symbols)
    
    footer = """

---

## 5. 関連ドキュメント

- [physics_flow.md](file:///analysis/physics_flow.md): 計算フローのシーケンス図
- [sinks_callgraph.md](file:///analysis/sinks_callgraph.md): シンク呼び出しグラフ
- [overview.md](file:///analysis/overview.md): モジュール責務
- [equations.md](file:///analysis/equations.md): 物理式リファレンス

---

*最終更新: inventory.json から自動生成*
"""
    
    return header + sections_table + exploration_guide + footer


def inject_autogen_block(original: str, block: str) -> str:
    """Replace the AUTOGEN block in the document."""
    autogen_block = f"{AUTOGEN_START}\n{block}\n{AUTOGEN_END}"
    pattern = re.compile(
        rf"{re.escape(AUTOGEN_START)}.*?{re.escape(AUTOGEN_END)}",
        flags=re.DOTALL,
    )
    if pattern.search(original):
        return pattern.sub(autogen_block, original, count=1)
    
    # If no autogen block, return the full new document
    return block


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate run_py_sections.md from inventory.json."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes to run_py_sections.md (default: dry-run).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    
    inventory = load_inventory()
    symbols = get_run_py_symbols(inventory)
    
    if not symbols:
        print(f"WARNING: No symbols found for {RUN_PY_PATH} in inventory.json", file=sys.stderr)
        return 1
    
    doc_content = build_full_document(symbols)
    
    if args.write:
        if TARGET_DOC.exists():
            existing = TARGET_DOC.read_text(encoding="utf-8")
            updated = inject_autogen_block(existing, doc_content)
        else:
            updated = doc_content
        
        TARGET_DOC.write_text(updated, encoding="utf-8")
        print(f"make_run_sections: wrote {TARGET_DOC.name} ({len(symbols)} symbols)")
    else:
        sys.stdout.write(doc_content)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
