"""互換性のための薄いラッパー。

実体は ``scripts.doc_sync_agent`` に移動した。``python -m tools.doc_sync_agent``
など既存の呼び出しからも引き続き利用できる。
"""

from __future__ import annotations

from marsdisk.ops.doc_sync_agent import main  # noqa: F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
