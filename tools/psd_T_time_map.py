"""温度×時間 PSD マップ生成スクリプトの互換ラッパー."""

from __future__ import annotations

from prototypes.psd.temperature_time_map import main  # noqa: F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())

