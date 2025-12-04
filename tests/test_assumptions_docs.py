from pathlib import Path

from analysis.tools import render_assumptions


def test_render_assumptions_runs(tmp_path: Path) -> None:
    """Ensure the renderer runs even with empty inputs."""

    out_path = tmp_path / "assumptions_overview.md"
    exit_code = render_assumptions.main(["--output", str(out_path)])
    assert exit_code == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in content


def test_trace_entries_follow_schema() -> None:
    traces = render_assumptions.load_traces(render_assumptions.discover_trace_files())
    if not traces:
        assert traces == []
        return
    for entry in traces:
        assert entry.eq_id is not None
        assert entry.assumption_tags is not None
        assert entry.config_keys is not None
        assert entry.code_path is not None
        assert entry.status is not None


def test_gap_titles_appear_in_overview() -> None:
    traces = render_assumptions.load_traces(render_assumptions.discover_trace_files())
    gaps = render_assumptions.load_gap_list()
    content = render_assumptions.render_overview(traces, gaps)
    titles = [gap.title for gap in gaps[:3]]
    for title in titles:
        assert title in content
