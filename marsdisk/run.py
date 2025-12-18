"""Thin wrapper that forwards to the main zero-D runner implementation."""
from __future__ import annotations

from .run_zero_d import *  # noqa: F401,F403


if __name__ == "__main__":  # pragma: no cover - standard CLI entrypoint
    main()
