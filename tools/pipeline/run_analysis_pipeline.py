#!/usr/bin/env python3
"""Run the full analysis/documentation pipeline with a single command.

This helper wraps the steps mandated in ``AGENTS.md``: DocSyncAgent,
documentation tests, and the evaluation system.  A small JSON stamp is
written under ``analysis/`` to provide traceability of the last execution.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence

STAMP_PATH = Path("analysis/.analysis_pipeline_stamp")


def _run_step(label: str, command: Sequence[str]) -> None:
    """Execute ``command`` and stream stdout/stderr to the console."""

    print(f"[analysis-pipeline] {label}: {' '.join(command)}")
    subprocess.run(command, check=True)


def _write_stamp(outdir: str, steps: Sequence[str]) -> None:
    """Persist a JSON stamp recording the last pipeline execution."""

    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "outdir": outdir,
        "steps": list(steps),
    }
    STAMP_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run DocSyncAgent, analysis doc tests, and the evaluation system."
    )
    parser.add_argument(
        "--outdir",
        default="out",
        help="Simulation output directory passed to tools.evaluation_system (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    python = sys.executable
    steps: List[tuple[str, List[str]]] = [
        ("doc_sync", [python, "-m", "tools.doc_sync_agent", "--all", "--write"]),
        ("doc_tests", [python, "tools/run_analysis_doc_tests.py"]),
        ("evaluation", [python, "-m", "tools.evaluation_system", "--outdir", args.outdir]),
    ]

    for label, command in steps:
        _run_step(label, command)

    _write_stamp(args.outdir, [label for label, _ in steps])


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    main()
