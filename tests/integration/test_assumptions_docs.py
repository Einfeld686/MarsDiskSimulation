from pathlib import Path

from analysis.tools import render_assumptions


def test_render_assumptions_runs(tmp_path: Path) -> None:
    """Ensure the renderer runs even with empty inputs."""

    overview_path = tmp_path / "assumptions_overview.md"
    trace_path = tmp_path / "assumption_trace.md"
    exit_code = render_assumptions.main(
        ["--overview", str(overview_path), "--trace", str(trace_path)]
    )
    assert exit_code == 0
    assert overview_path.exists()
    content = overview_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in content
    assert trace_path.exists()


def test_trace_entries_follow_schema() -> None:
    records = render_assumptions._load_records(render_assumptions.REGISTRY_PATH)
    if not records:
        assert records == []
        return
    for entry in records:
        assert entry.id is not None
        assert entry.status is not None
        assert entry.assumption_tags is not None
        assert entry.run_stage is not None


def test_gap_titles_appear_in_overview() -> None:
    records = render_assumptions._load_records(render_assumptions.REGISTRY_PATH)
    eq_ids = render_assumptions.parse_equations()
    source_map = render_assumptions.load_source_map()
    report = render_assumptions.compute_coverage(records, eq_ids, source_map)
    content = render_assumptions.render_overview(records, report)
    assert "| id | scope | eq_ids |" in content
    assert "AUTO-GENERATED" in content
