from __future__ import annotations

import json

from agent_test import ci_guard_analysis


def _write_coverage(tmp_path, **overrides):
    payload = {
        "function_total": 10,
        "function_referenced": 6,
        "function_reference_rate": 0.6,
        "anchor_consistency_rate": {"numerator": 10, "denominator": 10, "rate": 1.0},
        "invalid_anchor_count": 0,
        "duplicate_anchor_count": 0,
        "top_gaps": ["marsdisk/io/writer.py#write_parquet"],
        "per_file": [
            {
                "file_path": "marsdisk/io/writer.py",
                "functions_referenced": 0,
                "functions_total": 1,
                "coverage_rate": 0.0,
                "unreferenced": ["write_parquet"],
            }
        ],
    }
    payload.update(overrides)
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(json.dumps(payload), encoding="utf-8")
    return coverage_path


def test_ci_guard_analysis_pass(tmp_path) -> None:
    coverage_path = _write_coverage(tmp_path)
    exit_code = ci_guard_analysis.main(
        ["--coverage", str(coverage_path), "--fail-under", "0.5"]
    )
    assert exit_code == 0


def test_ci_guard_analysis_anchor_failure(tmp_path) -> None:
    coverage_path = _write_coverage(
        tmp_path,
        anchor_consistency_rate={"numerator": 9, "denominator": 10, "rate": 0.9},
        invalid_anchor_count=1,
    )
    exit_code = ci_guard_analysis.main(
        [
            "--coverage",
            str(coverage_path),
            "--fail-under",
            "0.5",
            "--require-clean-anchors",
        ]
    )
    assert exit_code == 2
