"""Compatibility shim for the relocated PSD temperature-time map CLI."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.legacy_psd.psd_T_time_map import main  # noqa: E402,F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
