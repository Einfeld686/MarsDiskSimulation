#!/usr/bin/env python3
"""Emit a timestamp token for cmd runsets."""
from __future__ import annotations

import argparse
from datetime import datetime


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--format",
        default="%Y%m%d-%H%M%S",
        help="strftime format string (default: %%Y%%m%%d-%%H%%M%%S).",
    )
    args = ap.parse_args()
    print(datetime.now().strftime(args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
