#!/usr/bin/env python3
"""Emit a random 31-bit integer seed for CMD usage."""
from __future__ import annotations

import secrets


def main() -> int:
    print(secrets.randbelow(2**31))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
