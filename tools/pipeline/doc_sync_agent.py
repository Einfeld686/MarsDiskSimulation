"""互換性のための薄いラッパー。

実体は ``marsdisk.ops.doc_sync_agent`` に移動済み。
このファイルは tools/doc_sync_agent.py および AGENTS.md 標準手順
(python -m tools.doc_sync_agent) からの呼び出しを維持するために残す。
"""

from __future__ import annotations

from marsdisk.ops.doc_sync_agent import main  # noqa: F401

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
