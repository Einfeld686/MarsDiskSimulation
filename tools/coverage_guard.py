"""Compatibility shim for the relocated coverage_guard."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow execution as a script from the repository root.
if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.pipeline.coverage_guard import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    from tools.pipeline.coverage_guard import main

    raise SystemExit(main())
