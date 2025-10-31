#!/usr/bin/env python3
"""Inspect DocSyncAgent defaults and validate root-cause hypotheses."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_SYNC_PATH = REPO_ROOT / "tools" / "doc_sync_agent.py"
DEFAULT_COVERAGE_PATH = Path(__file__).resolve().parent / "reports" / "coverage.json"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "reports" / "root_cause_probe.md"

REQUIRED_DOCS = [
    "analysis/overview.md",
    "analysis/run-recipes.md",
    "analysis/sinks_callgraph.md",
]


@dataclass
class DocSyncDefaults:
    """Container for DocSyncAgent defaults."""

    doc_paths: List[str]
    rg_pattern: str
    skip_dirs: List[str]


def extract_doc_sync_defaults(path: Path) -> DocSyncDefaults:
    """Parse *path* and return the defaults of interest."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    def find_assignment(name: str) -> ast.AST:
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        return node.value
        raise ValueError(f"Could not locate assignment for {name}")

    doc_paths_value = find_assignment("DEFAULT_DOC_PATHS")
    rg_pattern_value = find_assignment("RG_PATTERN")
    skip_dirs_value = find_assignment("SKIP_DIR_NAMES")

    doc_paths = sorted(ast.literal_eval(doc_paths_value))
    rg_pattern = ast.literal_eval(rg_pattern_value)
    skip_dirs_raw = ast.literal_eval(skip_dirs_value)
    skip_dirs = sorted(skip_dirs_raw)

    return DocSyncDefaults(doc_paths=doc_paths, rg_pattern=rg_pattern, skip_dirs=skip_dirs)


def load_coverage(path: Path) -> dict:
    """Load the coverage report JSON."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def format_defaults_section(defaults: DocSyncDefaults) -> List[str]:
    """Render a section describing DocSyncAgent defaults."""
    lines = ["## DocSyncAgent Defaults", ""]
    lines.append("```json")
    payload = {
        "DEFAULT_DOC_PATHS": defaults.doc_paths,
        "RG_PATTERN": defaults.rg_pattern,
        "SKIP_DIR_NAMES": defaults.skip_dirs,
    }
    lines.append(json.dumps(payload, indent=2))
    lines.append("```")
    lines.append("")
    return lines


def evaluate_hypotheses(defaults: DocSyncDefaults) -> List[str]:
    """Generate markdown describing hypotheses A–C."""
    lines: List[str] = []

    # Hypothesis A
    missing_docs = [doc for doc in REQUIRED_DOCS if doc not in defaults.doc_paths]
    result = "OK" if not missing_docs else "NG"
    lines.append("## Hypothesis A – DEFAULT_DOC_PATHS coverage")
    lines.append(f"- Result: {result}")
    if missing_docs:
        lines.append(f"- Missing documents: {', '.join(missing_docs)}")
    else:
        lines.append("- All required analysis documents are listed.")
    lines.append("")

    # Hypothesis B
    pattern_tokens = defaults.rg_pattern.split("|")
    interesting_tokens = [token for token in pattern_tokens if token.strip()]
    contains_grid_terms = any("omega" in token or "grid" in token for token in interesting_tokens)
    lines.append("## Hypothesis B – RG_PATTERN selectivity")
    if contains_grid_terms:
        lines.append("- Result: OK – pattern already contains grid-related terms.")
    else:
        lines.append("- Result: NG – pattern omits grid-related keywords (e.g. 'omega').")
    lines.append(f"- Current pattern tokens: {', '.join(interesting_tokens)}")
    lines.append("")

    # Hypothesis C
    suspicious_dirs = [entry for entry in defaults.skip_dirs if "marsdisk" in entry or "analysis" in entry]
    lines.append("## Hypothesis C – SKIP_DIR_NAMES exclusions")
    if suspicious_dirs:
        lines.append("- Result: NG – potential over-filtering detected.")
        lines.append(f"- Entries needing review: {', '.join(suspicious_dirs)}")
    else:
        lines.append("- Result: OK – no marsdisk/analysis entries are skipped.")
    lines.append("")

    return lines


def summarise_grid_coverage(coverage: dict) -> List[str]:
    """Summarise whether grid functions remain unreferenced."""
    lines = ["## Grid Function Coverage Check"]
    if not coverage:
        lines.append("- Coverage report not found; run rc_compare.py first.")
        lines.append("")
        return lines

    target_names = {"omega_kepler", "v_kepler", "omega", "v_keplerian"}
    unreferenced_entries = [
        entry for entry in coverage.get("unreferenced", [])
        if entry["file"] == "marsdisk/grid.py" and entry["name"] in target_names
    ]
    if unreferenced_entries:
        lines.append("- Result: NG – the following grid functions lack anchors:")
        for entry in unreferenced_entries:
            lines.append(
                f"  - `{entry['name']}` at `marsdisk/grid.py:{entry['lineno']}`"
            )
    else:
        lines.append("- Result: OK – grid functions are referenced in analysis docs.")
    lines.append("")
    return lines


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe DocSyncAgent defaults and record root cause observations."
    )
    parser.add_argument(
        "--doc-sync",
        type=Path,
        default=DOC_SYNC_PATH,
        help="Path to tools/doc_sync_agent.py (default: %(default)s).",
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=DEFAULT_COVERAGE_PATH,
        help="Path to coverage.json produced by rc_compare.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Markdown report destination (default: %(default)s).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    doc_sync_path = (
        args.doc_sync
        if args.doc_sync.is_absolute()
        else (REPO_ROOT / args.doc_sync)
    ).resolve()
    defaults = extract_doc_sync_defaults(doc_sync_path)

    coverage_path = (
        args.coverage
        if args.coverage.is_absolute()
        else (Path(__file__).resolve().parent / args.coverage)
    ).resolve()
    coverage = load_coverage(coverage_path)

    output_path = (
        args.output
        if args.output.is_absolute()
        else (Path(__file__).resolve().parent / args.output)
    ).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = ["# Root Cause Probe", ""]
    lines.extend(format_defaults_section(defaults))
    lines.extend(evaluate_hypotheses(defaults))
    lines.extend(summarise_grid_coverage(coverage))

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[rc_root_cause_probe] Report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
