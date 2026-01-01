#!/usr/bin/env python3
"""Lint docs/plan for absolute paths and missing repo references."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class Finding:
    kind: str
    file: Path
    line: int
    raw: str
    normalized: str | None = None
    detail: str | None = None


DEFAULT_PREFIXES = [
    "analysis/",
    "analysis/outputs/",
    "configs/",
    "data/",
    "docs/",
    "marsdisk/",
    "scripts/",
    "siO2_disk_cooling/",
    "slides/",
    "tables/",
    "tests/",
    "tools/",
    "out/",
    "paper/",
    "agent_test/",
    "tmp/",
    "_configs/",
    ".github/",
    ".devcontainer/",
    "devcontainer/",
    "github/",
    "./",
    "../",
]

FILE_URL_RE = re.compile(r"file://[^\s`\"'()<>\[\]]+")
WIN_ABS_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s`\"'()<>\[\]]+")
TILDE_ABS_RE = re.compile(r"(?<![A-Za-z0-9])~/(?:[^\s`\"'()<>\[\]]+)")
POSIX_ABS_RE = re.compile(
    r"(?<![A-Za-z0-9])/(?:[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.<>%{}$*+,:-]+)*)"
)


def build_prefix_regex(prefixes: list[str]) -> re.Pattern[str]:
    escaped = "|".join(re.escape(prefix) for prefix in prefixes)
    return re.compile(
        rf"(?<![A-Za-z0-9_])(?P<path>(?:{escaped})[^\s`\"'()<>\[\]]+)"
    )


def normalize_token(token: str) -> str:
    token = token.strip("`\"'(),;:")
    token = token.rstrip(".")
    if "#" in token:
        token = token.split("#", 1)[0]
    if ":" in token and not re.match(r"^[A-Za-z]:[\\/]", token):
        token = token.split(":", 1)[0]
    return token


def is_placeholder(token: str) -> bool:
    return any(mark in token for mark in ("<", ">", "{", "}", "*", "$", "...", "?"))


def iter_absolute_matches(line: str) -> list[str]:
    matches: list[str] = []
    for pattern in (FILE_URL_RE, WIN_ABS_RE, TILDE_ABS_RE, POSIX_ABS_RE):
        for match in pattern.finditer(line):
            if pattern is POSIX_ABS_RE:
                if match.start() >= 3 and line[match.start() - 3 : match.start()] == "://":
                    continue
                if match.start() > 0:
                    prefix = line[match.start() - 1]
                    if prefix not in " \t([{\"'`":
                        continue
                if re.fullmatch(r"/[A-Za-z]{1,2}", match.group(0)):
                    continue
            matches.append(match.group(0))
    return matches


def scan_file(path: Path, root: Path, rel_re: re.Pattern[str]) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for raw in iter_absolute_matches(line):
            if raw in ("/", "//"):
                continue
            findings.append(Finding("absolute", path, lineno, raw))
        for match in rel_re.finditer(line):
            raw = match.group("path")
            token = normalize_token(raw)
            if not token:
                continue
            if is_placeholder(token):
                continue
            resolved = (root / token).resolve(strict=False)
            if not resolved.is_relative_to(root):
                findings.append(
                    Finding(
                        "missing",
                        path,
                        lineno,
                        raw,
                        normalized=token,
                        detail="outside_repo",
                    )
                )
                continue
            if not resolved.exists():
                findings.append(
                    Finding(
                        "missing",
                        path,
                        lineno,
                        raw,
                        normalized=token,
                    )
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root (default: repo root)",
    )
    parser.add_argument(
        "--plan-dir",
        default=Path("docs/plan"),
        type=Path,
        help="Plan directory to scan (default: docs/plan)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    plan_dir = (root / args.plan_dir).resolve()

    if not plan_dir.exists():
        print(f"[ERROR] Plan directory not found: {plan_dir}")
        return 2

    rel_re = build_prefix_regex(DEFAULT_PREFIXES)

    findings: list[Finding] = []
    for path in sorted(plan_dir.rglob("*.md")):
        findings.extend(scan_file(path, root, rel_re))

    if not findings:
        print("Plan lint: OK")
        return 0

    abs_findings = [f for f in findings if f.kind == "absolute"]
    missing_findings = [f for f in findings if f.kind == "missing"]

    if abs_findings:
        print(f"[ERROR] Absolute paths detected: {len(abs_findings)}")
        for finding in abs_findings:
            relpath = finding.file.relative_to(root)
            print(f"  - {relpath}:{finding.line}: {finding.raw}")

    if missing_findings:
        print(f"[ERROR] Missing paths detected: {len(missing_findings)}")
        for finding in missing_findings:
            relpath = finding.file.relative_to(root)
            suffix = f" ({finding.detail})" if finding.detail else ""
            normalized = finding.normalized or finding.raw
            print(f"  - {relpath}:{finding.line}: {normalized}{suffix}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
