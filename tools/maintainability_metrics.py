#!/usr/bin/env python3
"""Run maintainability metrics (radon/jscpd) and emit a short summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None


def _rank_complexity(value: int) -> str:
    if value <= 5:
        return "A"
    if value <= 10:
        return "B"
    if value <= 20:
        return "C"
    if value <= 30:
        return "D"
    if value <= 40:
        return "E"
    return "F"


def _summarize_radon(data: dict[str, Any]) -> dict[str, Any]:
    total_blocks = 0
    total_complexity = 0.0
    max_complexity = 0.0
    grade_counts = {grade: 0 for grade in ["A", "B", "C", "D", "E", "F"]}

    for blocks in data.values():
        for block in blocks:
            complexity = block.get("complexity")
            if complexity is None:
                continue
            try:
                value = float(complexity)
            except (TypeError, ValueError):
                continue
            total_blocks += 1
            total_complexity += value
            max_complexity = max(max_complexity, value)
            grade_counts[_rank_complexity(int(round(value)))] += 1

    avg_complexity = total_complexity / total_blocks if total_blocks else 0.0
    return {
        "status": "ok",
        "blocks": total_blocks,
        "avg_complexity": avg_complexity,
        "max_complexity": max_complexity,
        "grade_counts": grade_counts,
    }


def _run_radon(repo_root: Path, target: str) -> dict[str, Any]:
    result = _run([sys.executable, "-m", "radon", "cc", "-j", target], cwd=repo_root)
    if result is None:
        return {"status": "missing", "reason": "radon executable not found"}
    if result.returncode != 0:
        return {
            "status": "error",
            "reason": "radon command failed",
            "stderr": result.stderr.strip(),
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "reason": "failed to parse radon output",
            "stderr": result.stderr.strip(),
        }
    return _summarize_radon(data)


def _run_jscpd(repo_root: Path, target: str, ignore: list[str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="jscpd_") as tmpdir:
        output_dir = Path(tmpdir)
        cmd = [
            "npx",
            "-y",
            "jscpd",
            "--reporters",
            "json",
            "--output",
            str(output_dir),
            "--format",
            "python",
            "--silent",
            "--gitignore",
        ]
        for pattern in ignore:
            cmd.extend(["--ignore", pattern])
        cmd.append(target)
        result = _run(cmd, cwd=repo_root)
        if result is None:
            return {"status": "missing", "reason": "npx executable not found"}
        if result.returncode != 0:
            return {
                "status": "error",
                "reason": "jscpd command failed",
                "stderr": result.stderr.strip(),
            }
        report_path = output_dir / "jscpd-report.json"
        if not report_path.exists():
            return {
                "status": "error",
                "reason": "jscpd report not found",
            }
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "reason": "failed to parse jscpd report",
            }
        stats = data.get("statistics", {}).get("total", {})
        return {
            "status": "ok",
            "duplication_percent": stats.get("percentage"),
            "duplicated_lines": stats.get("duplicatedLines"),
            "total_lines": stats.get("lines"),
            "clones": stats.get("clones"),
        }


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run maintainability metrics.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="marsdisk",
        help="Target path to analyze.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    target = args.target
    ignore = [
        "**/.venv/**",
        "**/__pycache__/**",
        "**/.git/**",
        "**/out/**",
        "**/tmp/**",
        "**/tmp_debug*/**",
        "**/agent_test/**",
    ]

    payload = {
        "radon": _run_radon(repo_root, target),
        "jscpd": _run_jscpd(repo_root, target, ignore),
        "target": target,
        "ignore": ignore,
    }

    if args.out is not None:
        output_path = (repo_root / args.out).resolve()
        if not output_path.is_relative_to(repo_root):
            print(f"error: output path must be within repo: {output_path}", file=sys.stderr)
            return 2
        _write_output(output_path, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    sys.exit(main())
