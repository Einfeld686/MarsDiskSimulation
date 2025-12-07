"""Compatibility shim for the relocated make_qpr_table utility."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.qpr.make_qpr_table import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    from tools.qpr.make_qpr_table import main

    raise SystemExit(main())
