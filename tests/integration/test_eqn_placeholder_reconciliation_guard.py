"""CI guard for eqn_placeholder_reconciliation.tsv."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import ocr_output_migration as ocr

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = REPO_ROOT / "paper" / "pdf_extractor" / "outputs"
RECON_PATH = OUTPUTS_DIR / "_checks" / "eqn_placeholder_reconciliation.tsv"


def _format_reconciliation(rows: list[list[str]]) -> str:
    header = ["file", "line_no", "label", "status", "action", "text"]
    return "\t".join(header) + "\n" + "\n".join("\t".join(row) for row in rows) + "\n"


def test_eqn_placeholder_reconciliation_missing_zero() -> None:
    if not OUTPUTS_DIR.exists():
        pytest.skip("pdf_extractor outputs not present")

    rows = ocr._build_eq_placeholder_reconciliation(OUTPUTS_DIR)
    missing = [row for row in rows if row[3] == "missing"]
    assert not missing, f"missing eq placeholders detected: {missing[:20]}"


def test_eqn_placeholder_reconciliation_up_to_date() -> None:
    if not OUTPUTS_DIR.exists():
        pytest.skip("pdf_extractor outputs not present")

    assert RECON_PATH.exists(), "eqn_placeholder_reconciliation.tsv is missing; run ocr_output_migration"
    rows = ocr._build_eq_placeholder_reconciliation(OUTPUTS_DIR)
    expected = _format_reconciliation(rows)
    actual = RECON_PATH.read_text(encoding="utf-8")
    assert actual == expected, "eqn_placeholder_reconciliation.tsv is out of date; regenerate it"
