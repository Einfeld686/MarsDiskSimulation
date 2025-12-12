#!/usr/bin/env python3
"""Report pending UNKNOWN_REF_REQUESTS entries (warn-only by default)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUESTS_PATH = Path("analysis/UNKNOWN_REF_REQUESTS.jsonl")


def load_requests(path: Path) -> list[dict]:
    """Load JSONL entries from the given path."""
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if pending requests exist",
    )
    args = parser.parse_args()

    entries = load_requests(REQUESTS_PATH)

    if not entries:
        print("No UNKNOWN_REF_REQUESTS.jsonl found.")
        return 0

    pending = [entry for entry in entries if not entry.get("resolved")]

    if pending:
        print(f"[WARN] Pending reference requests: {len(pending)}")
        for entry in pending[:5]:
            print(f"  - {entry.get('slug')}: {entry.get('type')}")
        if args.strict:
            return 1
    else:
        print("All reference requests resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
