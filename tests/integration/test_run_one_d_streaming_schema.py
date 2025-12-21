"""Streaming ON/OFF schema parity for 1D runs."""

from __future__ import annotations

from pathlib import Path

from one_d_helpers import run_one_d_case


def test_run_one_d_streaming_schema_parity(tmp_path: Path, monkeypatch) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
    ]

    _, run_off, _ = run_one_d_case(tmp_path / "off", overrides + ["io.streaming.enable=false"])

    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, run_on, _ = run_one_d_case(tmp_path / "on", overrides + ["io.streaming.enable=true"])

    assert set(run_on.columns) == set(run_off.columns)
