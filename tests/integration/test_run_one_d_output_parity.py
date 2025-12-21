"""1D output parity checks against baseline artefact requirements."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.pipeline.evaluation_system import (
    ORBIT_ROLLUP_COLUMNS,
    REQUIRED_RUN_CONFIG_FIELDS,
    REQUIRED_SERIES_COLUMNS,
    REQUIRED_SUMMARY_FIELDS,
    SERIES_COLUMN_ALIASES,
)

from one_d_helpers import run_one_d_case


def test_run_one_d_required_outputs(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.streaming.enable=false",
    ]
    summary, run_df, outdir = run_one_d_case(tmp_path, overrides)

    assert all(name in run_df.columns for name in REQUIRED_SERIES_COLUMNS)
    for alias_group in SERIES_COLUMN_ALIASES:
        assert any(col in run_df.columns for col in alias_group)

    assert all(name in summary for name in REQUIRED_SUMMARY_FIELDS)

    run_config = json.loads((outdir / "run_config.json").read_text(encoding="utf-8"))
    assert all(name in run_config for name in REQUIRED_RUN_CONFIG_FIELDS)

    rollup = pd.read_csv(outdir / "orbit_rollup.csv")
    assert all(name in rollup.columns for name in ORBIT_ROLLUP_COLUMNS)
