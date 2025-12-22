"""Streaming ON/OFF schema parity for 1D runs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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

    _, run_off, outdir_off = run_one_d_case(
        tmp_path / "off", overrides + ["io.streaming.enable=false"]
    )

    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, run_on, outdir_on = run_one_d_case(tmp_path / "on", overrides + ["io.streaming.enable=true"])

    assert set(run_on.columns) == set(run_off.columns)
    diag_off = pd.read_parquet(outdir_off / "series" / "diagnostics.parquet")
    diag_on = pd.read_parquet(outdir_on / "series" / "diagnostics.parquet")
    assert set(diag_on.columns) == set(diag_off.columns)
