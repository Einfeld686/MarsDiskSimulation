"""Compatibility shim for the relocated run_analysis_doc_tests CLI."""

from __future__ import annotations

import sys
from pathlib import Path

# When executed as a script (python tools/run_analysis_doc_tests.py), ensure repo root is on sys.path.
if __package__ is None or __package__ == "":  # pragma: no cover - compatibility path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.pipeline.run_analysis_doc_tests import main  # noqa: E402,F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
