from pathlib import Path

from marsdisk.ops import assumption_trace


def test_build_assumption_trace_smoke(tmp_path: Path) -> None:
    index_path = tmp_path / "equations_index.jsonl"
    index_path.write_text('{"eq_id": "E.006", "heading": "surface_collisional_time"}\n', encoding="utf-8")

    records = assumption_trace.build_assumption_trace(
        index_path=index_path, equations_md=Path("analysis/equations.md")
    )
    eq_ids = {rec.eq_id for rec in records}
    assert "E.006" in eq_ids

    record = next(rec for rec in records if rec.eq_id == "E.006")
    assert record.source_doc == "analysis/equations.md"
    assert any("marsdisk/physics/surface.py" in path for path in record.code_path)

    jsonl_path = tmp_path / "assumption_trace.jsonl"
    md_path = tmp_path / "assumption_trace.md"
    assumption_trace.write_jsonl(records, jsonl_path)
    assumption_trace.write_markdown(records, md_path)
    assert jsonl_path.exists()
    assert md_path.exists()
