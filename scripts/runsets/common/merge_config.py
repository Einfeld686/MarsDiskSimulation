#!/usr/bin/env python3
"""Merge base/study YAML with optional overrides.txt into a single YAML file."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def _deep_update(base: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    for key, value in other.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _parse_scalar(value: str) -> Any:
    yaml = YAML(typ="safe")
    return yaml.load(value)


def _set_path(cfg: dict[str, Any], path: str, value: Any) -> None:
    cursor = cfg
    parts = path.split(".")
    for key in parts[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[parts[-1]] = value


def _load_overrides(path: Path) -> list[tuple[str, Any]]:
    overrides: list[tuple[str, Any]] = []
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        overrides.append((key.strip(), _parse_scalar(value.strip())))
    return overrides


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, required=True, help="Base YAML file")
    ap.add_argument("--study", type=Path, default=None, help="Study YAML file")
    ap.add_argument("--overrides", type=Path, default=None, help="Overrides text file")
    ap.add_argument("--out", type=Path, required=True, help="Output YAML file")
    args = ap.parse_args()

    yaml = YAML()
    cfg = yaml.load(args.base.read_text()) or {}
    if args.study:
        study = yaml.load(args.study.read_text()) or {}
        cfg = _deep_update(cfg, study)
    if args.overrides and args.overrides.exists():
        for path, value in _load_overrides(args.overrides):
            _set_path(cfg, path, value)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        yaml.dump(cfg, handle)


if __name__ == "__main__":
    main()
