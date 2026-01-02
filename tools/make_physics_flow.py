#!/usr/bin/env python3
"""Generate analysis/physics_flow.md from a template."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
TEMPLATE_PATH = ANALYSIS_DIR / "templates" / "physics_flow_template.md"
OUTPUT_PATH = ANALYSIS_DIR / "physics_flow.md"

PLACEHOLDERS: dict[str, str] = {
    "TOOL_PATH": "tools/make_physics_flow.py",
    "RUN_SECTIONS_PATH": "analysis/run_py_sections.md",
    "SCHEMA_PATH": "marsdisk/schema.py",
    "DATAFLOW_PATH": "analysis/overview.md",
}


def _ensure_sources_exist() -> None:
    missing = []
    for key, rel_path in PLACEHOLDERS.items():
        if key == "TOOL_PATH":
            path = REPO_ROOT / rel_path
        else:
            path = REPO_ROOT / rel_path
        if not path.exists():
            missing.append(str(path))
    if not TEMPLATE_PATH.exists():
        missing.append(str(TEMPLATE_PATH))
    if missing:
        raise FileNotFoundError("Missing required source(s): " + ", ".join(missing))


def _render_template(text: str) -> str:
    rendered = text
    for key, value in PLACEHOLDERS.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    unresolved = re.findall(r"{{\s*[^}]+\s*}}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {sorted(set(unresolved))}")
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def _build_document() -> str:
    _ensure_sources_exist()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _render_template(template)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate analysis/physics_flow.md.")
    parser.add_argument("--write", action="store_true", help="Write the generated document.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if the file is out of date.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.write and args.check:
        raise SystemExit("Choose either --write or --check.")
    if not args.write and not args.check:
        raise SystemExit("Specify --write or --check.")

    rendered = _build_document()
    existing = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None

    if args.check:
        if existing != rendered:
            sys.stderr.write("physics_flow.md is out of date. Run tools/make_physics_flow.py --write\n")
            return 1
        return 0

    if existing != rendered:
        OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
