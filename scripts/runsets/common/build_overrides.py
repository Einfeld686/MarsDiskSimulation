#!/usr/bin/env python3
"""Merge override lines from multiple files.

Priority follows input order: later files win. Output is one key=value per line.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Iterator


def _iter_pairs(paths: Iterable[Path]) -> Iterator[tuple[str, str]]:
    for path in paths:
        # Try UTF-8 first, then fall back to system default encoding
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="cp932")  # Japanese Windows
            except UnicodeDecodeError:
                text = path.read_text(encoding="latin-1")  # Last resort
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            yield key, value


def _merge_pairs(pairs: Iterable[tuple[str, str]]) -> tuple[list[str], dict[str, str]]:
    order: list[str] = []
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            try:
                order.remove(key)
            except ValueError:
                pass
        order.append(key)
        values[key] = value
    return order, values


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--file",
        action="append",
        type=Path,
        required=True,
        dest="files",
        help="Override file (key=value per line). Later files win.",
    )
    ap.add_argument("--out", default=None, type=Path, help="Optional output file path.")
    args = ap.parse_args()

    order, values = _merge_pairs(_iter_pairs(args.files))
    lines = [f"{key}={values[key]}" for key in order]
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines)
        if text:
            text += "\n"
        args.out.write_text(text, encoding="utf-8")
        return
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
