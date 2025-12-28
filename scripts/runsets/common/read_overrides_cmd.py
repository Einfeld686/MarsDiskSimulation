#!/usr/bin/env python3
"""Emit CMD-friendly SET lines for selected overrides keys."""
from __future__ import annotations

import argparse
from pathlib import Path


KEY_MAP = {
    "io.archive.enabled": "ARCHIVE_ENABLED_EXPECTED",
    "io.archive.dir": "ARCHIVE_DIR_EXPECTED",
    "io.archive.merge_target": "ARCHIVE_MERGE_TARGET",
    "io.archive.verify_level": "ARCHIVE_VERIFY_LEVEL",
    "io.archive.keep_local": "ARCHIVE_KEEP_LOCAL",
}


def _load_overrides(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip()
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, type=Path, help="Overrides file path.")
    ap.add_argument("--out", type=Path, default=None, help="Output cmd file path.")
    args = ap.parse_args()

    if not args.file.exists():
        return 2

    data = _load_overrides(args.file)
    lines = []
    for key, var in KEY_MAP.items():
        if key in data:
            value = data[key].replace('"', "")
            lines.append(f'set "{var}={value}"')
    if args.out is None:
        for line in lines:
            print(line)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
