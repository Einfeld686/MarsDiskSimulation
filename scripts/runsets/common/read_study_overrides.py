#!/usr/bin/env python3
"""Emit CMD-friendly SET lines from a study YAML file."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def _join_list(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)


def _emit(lines: list[str], key: str, value: Any) -> None:
    if value is None:
        return
    val = _join_list(value).replace('"', "")
    lines.append(f'set "{key}={val}"')


def _format_extra_cases(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            if isinstance(item, (list, tuple)):
                if len(item) < 3:
                    continue
                parts.append(",".join(str(v) for v in item[:3]))
            else:
                parts.append(str(item))
        return ";".join(parts)
    return str(value)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--study", required=True, help="Path to study YAML.")
    ap.add_argument("--out", default=None, help="Optional output cmd file path.")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else None
    lines: list[str] = []

    try:
        from ruamel.yaml import YAML  # type: ignore
    except Exception:
        if out_path is not None:
            _write_lines(out_path, lines)
        return 0

    path = Path(args.study)
    if not path.exists():
        if out_path is not None:
            _write_lines(out_path, lines)
        return 0

    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8")) or {}

    _emit(lines, "T_LIST", data.get("T_LIST_RAW", data.get("T_LIST")))
    _emit(lines, "EPS_LIST", data.get("EPS_LIST_RAW", data.get("EPS_LIST")))
    _emit(lines, "TAU_LIST", data.get("TAU_LIST_RAW", data.get("TAU_LIST")))
    extra_cases = _format_extra_cases(data.get("EXTRA_CASES_RAW", data.get("EXTRA_CASES")))
    if extra_cases is not None:
        _emit(lines, "EXTRA_CASES", extra_cases)
    _emit(lines, "SWEEP_TAG", data.get("SWEEP_TAG"))
    _emit(lines, "END_MODE", data.get("END_MODE"))
    _emit(lines, "COOL_TO_K", data.get("COOL_TO_K"))
    _emit(lines, "COOL_MARGIN_YEARS", data.get("COOL_MARGIN_YEARS"))
    _emit(lines, "COOL_SEARCH_YEARS", data.get("COOL_SEARCH_YEARS"))
    _emit(lines, "COOL_MODE", data.get("COOL_MODE"))
    _emit(lines, "T_END_YEARS", data.get("T_END_YEARS"))
    _emit(lines, "T_END_SHORT_YEARS", data.get("T_END_SHORT_YEARS"))

    if out_path is not None:
        _write_lines(out_path, lines)
        return 0

    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
