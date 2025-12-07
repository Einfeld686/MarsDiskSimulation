"""Compatibility shim for the relocated evaluation_system."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.pipeline.evaluation_system import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    from tools.pipeline.evaluation_system import main

    raise SystemExit(main())
