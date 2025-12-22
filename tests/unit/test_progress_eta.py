"""Tests for CLI progress ETA smoothing and checkpoint restore."""

from __future__ import annotations

from marsdisk.runtime import progress as progress_mod


def _fake_monotonic(times):
    iterator = iter(times)

    def _next():
        return next(iterator)

    return _next


def test_progress_eta_prefers_recent_steps(monkeypatch, capsys):
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    monkeypatch.setattr(progress_mod.time, "monotonic", _fake_monotonic(times))
    reporter = progress_mod.ProgressReporter(total_steps=6, total_time_s=100.0, enabled=True)

    for step_no in range(4):
        reporter.update(step_no, sim_time_s=0.0, force=True)

    out = capsys.readouterr().out.strip().splitlines()
    assert out, "Expected progress output for ETA"
    assert "ETA 2s" in out[-1]


def test_progress_snapshot_restore(monkeypatch):
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    monkeypatch.setattr(progress_mod.time, "monotonic", _fake_monotonic(times))
    reporter = progress_mod.ProgressReporter(total_steps=5, total_time_s=10.0, enabled=True)

    for step_no in range(4):
        reporter.update(step_no, sim_time_s=0.0, force=True)

    state = reporter.snapshot_state()

    monkeypatch.setattr(progress_mod.time, "monotonic", _fake_monotonic([100.0]))
    restored = progress_mod.ProgressReporter(total_steps=5, total_time_s=10.0, enabled=True)
    restored.restore_state(state)

    assert restored.snapshot_state() == state
