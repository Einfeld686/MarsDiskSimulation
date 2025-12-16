from __future__ import annotations

import json
from pathlib import Path
import pytest

from marsdisk.ops import doc_sync_agent


def test_scan_generates_inventory(tmp_path) -> None:
    output_path = tmp_path / "inventory.json"
    exit_code = doc_sync_agent.main(["scan", "--root", ".", "--write", str(output_path)])
    assert exit_code == 0

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) > 50
    for entry in data:
        assert entry["file_path"].startswith("marsdisk/")
        assert entry["kind"] in {"function", "async_function", "class"}
        assert entry["line_no"] <= entry["end_line"]
    assert any(
        entry["file_path"] == "marsdisk/run.py" and entry["symbol"] == "run_zero_d"
        for entry in data
    )


def test_refs_and_coverage_pipeline(tmp_path) -> None:
    inv_path = tmp_path / "inventory.json"
    refs_path = tmp_path / "doc_refs.json"
    coverage_json = tmp_path / "coverage.json"
    coverage_md = tmp_path / "coverage.md"

    assert doc_sync_agent.main(["scan", "--root", ".", "--write", str(inv_path)]) == 0

    docs = [
        "analysis/equations.md",
        "analysis/overview.md",
        "analysis/slides_outline.md",
        "analysis/run_catalog.md",
        "analysis/figures_catalog.md",
        "analysis/glossary.md",
        "analysis/literature_map.md",
        "analysis/run-recipes.md",
        "analysis/sinks_callgraph.md",
        "analysis/AI_USAGE.md",
        "analysis/CHANGELOG.md",
    ]
    assert (
        doc_sync_agent.main(
            ["refs", "--docs", *docs, "--write", str(refs_path)]
        )
        == 0
    )

    assert (
        doc_sync_agent.main(
            [
                "coverage",
                "--inv",
                str(inv_path),
                "--refs",
                str(refs_path),
                "--write-json",
                str(coverage_json),
                "--write-md",
                str(coverage_md),
            ]
        )
        == 0
    )

    coverage_data = json.loads(coverage_json.read_text(encoding="utf-8"))
    assert coverage_data["function_total"] > 0
    assert coverage_data["function_referenced"] <= coverage_data["function_total"]
    assert "anchor_consistency_rate" in coverage_data
    assert coverage_data["anchor_consistency_rate"]["denominator"] >= 0
    assert coverage_data["invalid_anchor_count"] >= coverage_data["line_anchor_reversed_count"]
    assert coverage_md.read_text(encoding="utf-8").startswith("# Coverage Snapshot")


def test_equations_mapping(tmp_path) -> None:
    inv_path = tmp_path / "inventory.json"
    eq_map_path = tmp_path / "equation_code_map.json"

    assert doc_sync_agent.main(["scan", "--root", ".", "--write", str(inv_path)]) == 0
    assert (
        doc_sync_agent.main(
            [
                "equations",
                "--equations",
                "analysis/equations.md",
                "--inventory",
                str(inv_path),
                "--write",
                str(eq_map_path),
            ]
        )
        == 0
    )

    payload = json.loads(eq_map_path.read_text(encoding="utf-8"))
    assert payload["stats"]["total_equations"] >= 1
    assert "equations" in payload and isinstance(payload["equations"], list)
    assert "unmapped_equations" in payload and isinstance(payload["unmapped_equations"], list)


def test_equations_mapping_with_ml(tmp_path) -> None:
    pytest.importorskip("sklearn")
    inv_path = tmp_path / "inventory.json"
    eq_map_path = tmp_path / "equation_code_map.json"

    assert doc_sync_agent.main(["scan", "--root", ".", "--write", str(inv_path)]) == 0
    exit_code = doc_sync_agent.main(
        [
            "equations",
            "--equations",
            "analysis/equations.md",
            "--inventory",
            str(inv_path),
            "--write",
            str(eq_map_path),
            "--with-ml-suggest",
            "--ml-threshold",
            "0.0",
            "--ml-top",
            "1",
        ]
    )
    assert exit_code == 0
    payload = json.loads(eq_map_path.read_text(encoding="utf-8"))
    assert "ml_suggested_refs" in payload
    assert isinstance(payload["ml_suggested_refs"], list)
    if payload["ml_suggested_refs"]:
        first = payload["ml_suggested_refs"][0]
        assert "priority" in first
        assert first["priority"] is None or isinstance(first["priority"], int)


def test_autostub_inserts_stubs(tmp_path) -> None:
    coverage_payload = {
        "function_total": 2,
        "function_referenced": 0,
        "function_reference_rate": 0.0,
        "anchor_consistency_rate": {"numerator": 0, "denominator": 0, "rate": 1.0},
        "per_file": [
            {
                "file_path": "marsdisk/io/writer.py",
                "functions_referenced": 0,
                "functions_total": 1,
                "coverage_rate": 0.0,
                "unreferenced": ["write_parquet"],
            },
            {
                "file_path": "marsdisk/physics/radiation.py",
                "functions_referenced": 0,
                "functions_total": 1,
                "coverage_rate": 0.0,
                "unreferenced": ["beta"],
            },
        ],
        "top_gaps": [
            "marsdisk/io/writer.py#write_parquet",
            "marsdisk/physics/radiation.py#beta",
        ],
    }
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(json.dumps(coverage_payload), encoding="utf-8")

    overview_copy = tmp_path / "overview.md"
    overview_copy.write_text(
        "## I/O\n\n### existing_section ─ placeholder\n- 参照: [marsdisk/io/writer.py:109–117]\n",
        encoding="utf-8",
    )
    run_recipes_copy = tmp_path / "run-recipes.md"
    run_recipes_copy.write_text("# run-recipes\n\nExisting instructions.\n", encoding="utf-8")

    assert (
        doc_sync_agent.main(
            [
                "autostub",
                "--coverage",
                str(coverage_path),
                "--top",
                "2",
                    "--overview",
                    str(overview_copy),
                    "--run-recipes",
                    str(run_recipes_copy),
                ]
            )
            == 0
        )

    updated_overview = overview_copy.read_text(encoding="utf-8")
    updated_run_recipes = run_recipes_copy.read_text(encoding="utf-8")
    assert "### write_parquet ─" in updated_overview
    assert "- 参照: [marsdisk/io/writer.py:" in updated_overview
    assert "### beta ─" in updated_run_recipes
    assert "- 手順: TODO" in updated_run_recipes
    assert "- 参照: [marsdisk/physics/radiation.py:" in updated_run_recipes

    # Idempotency: re-run command and ensure files remain unchanged.
    assert (
        doc_sync_agent.main(
            [
                "autostub",
                "--coverage",
                str(coverage_path),
                "--top",
                "2",
                "--overview",
                str(overview_copy),
                "--run-recipes",
                str(run_recipes_copy),
            ]
        )
        == 0
    )
    assert updated_overview == overview_copy.read_text(encoding="utf-8")
    assert updated_run_recipes == run_recipes_copy.read_text(encoding="utf-8")
