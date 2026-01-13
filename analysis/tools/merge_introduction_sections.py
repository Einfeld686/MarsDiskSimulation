from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECTIONS_DIR = REPO_ROOT / "analysis" / "thesis_sections" / "01_introduction"
OUTPUT_PATH = REPO_ROOT / "analysis" / "thesis" / "introduction.md"
MANIFEST_PATH = SECTIONS_DIR / "manifest.txt"
SECTION_PATTERN = re.compile(r"^\d{2}_.+\.md$")

def _manifest_entries(manifest_path: Path) -> list[str]:
    entries: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    return entries


def _validate_entry(entry: str) -> None:
    if "/" in entry or "\\" in entry:
        raise ValueError(f"manifest entry must be a filename: {entry}")


def _paths_from_manifest(sections_dir: Path, manifest_path: Path) -> list[Path]:
    entries = _manifest_entries(manifest_path)
    if not entries:
        raise ValueError(f"manifest is empty: {manifest_path}")

    seen: set[str] = set()
    paths: list[Path] = []
    for entry in entries:
        _validate_entry(entry)
        if entry in seen:
            raise ValueError(f"duplicate manifest entry: {entry}")
        seen.add(entry)
        candidate = sections_dir / entry
        if not candidate.exists():
            raise ValueError(f"manifest entry not found: {candidate}")
        if not candidate.is_file():
            raise ValueError(f"manifest entry is not a file: {candidate}")
        paths.append(candidate)
    return paths


def collect_sections(sections_dir: Path, manifest_path: Path | None = None) -> list[Path]:
    if manifest_path is not None and manifest_path.exists():
        return _paths_from_manifest(sections_dir, manifest_path)
    return sorted(
        [
            path
            for path in sections_dir.iterdir()
            if path.is_file() and SECTION_PATTERN.match(path.name)
        ]
    )


def build_document(section_paths: list[Path]) -> str:
    parts: list[str] = []
    for path in section_paths:
        parts.append(path.read_text(encoding="utf-8").rstrip("\n"))
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge introduction section files into analysis/thesis/introduction.md."
    )
    parser.add_argument(
        "--sections-dir",
        type=Path,
        default=SECTIONS_DIR,
        help="Directory containing numbered section markdown files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="Optional manifest file listing section order.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Output path for the merged introduction document.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the merged document to disk.",
    )
    args = parser.parse_args(argv)

    if not args.sections_dir.exists():
        print(f"sections dir not found: {args.sections_dir}", file=sys.stderr)
        return 2

    try:
        section_paths = collect_sections(args.sections_dir, args.manifest)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not section_paths:
        print(f"no section files found in: {args.sections_dir}", file=sys.stderr)
        return 2

    content = build_document(section_paths)

    if args.write:
        args.output.write_text(content, encoding="utf-8")
        print(f"merge_introduction_sections: wrote {args.output}")
        return 0

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
