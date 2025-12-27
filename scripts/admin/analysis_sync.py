from __future__ import annotations

import sys

from marsdisk.ops.doc_sync_agent import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
