"""PSD 時間発展スクリプトの互換ラッパー."""

from __future__ import annotations

from prototypes.psd.time_evolution import main  # noqa: F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())

