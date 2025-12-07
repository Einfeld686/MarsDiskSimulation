"""Compatibility shim for plotting helpers moved under tools/plotting/."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.plotting.base import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    # No CLI entry; import ensures compatibility for existing imports.
    pass
