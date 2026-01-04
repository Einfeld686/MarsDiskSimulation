"""CI guard for equation placeholders referenced in OCR outputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import ocr_output_migration as ocr

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = REPO_ROOT / "paper" / "pdf_extractor" / "outputs"


def test_eqn_placeholders_cover_internal_refs() -> None:
    if not OUTPUTS_DIR.exists():
        pytest.skip("pdf_extractor outputs not present")

    missing: list[str] = []
    for result_path in sorted(OUTPUTS_DIR.glob("*/result.md")):
        text = result_path.read_text(encoding="utf-8")
        placeholders = {m.group("num") for m in ocr.EQ_PLACEHOLDER_RE.finditer(text)}
        internal_labels = ocr._collect_internal_eq_labels(text.splitlines())
        for line_no, line in enumerate(text.splitlines(), start=1):
            groups = ocr._iter_eq_reference_groups(line)
            for match, labels, group_end in groups:
                if ocr._is_external_eq_reference(
                    line,
                    match,
                    group_end,
                    labels=labels,
                    internal_labels=internal_labels,
                ):
                    continue
                for label in labels:
                    if label not in placeholders:
                        missing.append(f"{result_path}:{line_no}:{label}")

    if missing:
        preview = ", ".join(missing[:20])
        suffix = " ..." if len(missing) > 20 else ""
        raise AssertionError(f"Missing eq placeholders for internal refs: {preview}{suffix}")
