"""CI guard for external equation reference audits."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import ocr_output_migration as ocr

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = REPO_ROOT / "paper" / "pdf_extractor" / "outputs"
AUDIT_PATH = OUTPUTS_DIR / "_checks" / "eqn_external_audit.tsv"


def _format_audit(rows: list[list[str]]) -> str:
    header = ["file", "line_no", "label", "strength", "reason", "evidence", "text"]
    return "\t".join(header) + "\n" + "\n".join("\t".join(row) for row in rows) + "\n"


def test_external_refs_have_strong_evidence() -> None:
    if not OUTPUTS_DIR.exists():
        pytest.skip("pdf_extractor outputs not present")

    rows = ocr._build_external_audit_rows(OUTPUTS_DIR)
    weak = [row for row in rows if row[3] == "weak"]
    assert not weak, f"weak external refs detected: {weak[:10]}"


def test_external_audit_report_up_to_date() -> None:
    if not OUTPUTS_DIR.exists():
        pytest.skip("pdf_extractor outputs not present")

    assert AUDIT_PATH.exists(), "eqn_external_audit.tsv is missing; run ocr_output_migration"
    rows = ocr._build_external_audit_rows(OUTPUTS_DIR)
    expected = _format_audit(rows)
    actual = AUDIT_PATH.read_text(encoding="utf-8")
    assert actual == expected, "eqn_external_audit.tsv is out of date; regenerate it"
