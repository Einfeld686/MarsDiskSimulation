from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from marsdisk import run


BASE_CONFIG = Path("configs/innerdisk_collisions_only.yml")


def test_phase_map_missing_entrypoint_falls_back_to_threshold(tmp_path: Path) -> None:
    overrides = [
        f"io.outdir={tmp_path}",
        "phase.enabled=true",
        "phase.source=map",
        "phase.entrypoint=nonexistent.module:func",
        "physics_mode=collisions_only",
        "numerics.t_end_years=1.0e-6",
        "numerics.dt_init=0.5",
        "numerics.eval_per_step=true",
        "radiation.TM_K=1800.0",
        "disk.geometry.r_in_RM=2.4",
        "disk.geometry.r_out_RM=2.41",
    ]

    cfg = run.load_config(BASE_CONFIG, overrides=overrides)
    run.run_zero_d(cfg)

    series_path = tmp_path / "series" / "run.parquet"
    summary_path = tmp_path / "summary.json"
    assert series_path.exists(), "run.parquet missing"
    assert summary_path.exists(), "summary.json missing"

    series = pd.read_parquet(series_path)
    assert not series["phase_state"].isna().any()
    assert set(series["phase_method"].unique()) == {"threshold"}

    with summary_path.open("r", encoding="utf-8") as fh:
        summary = json.load(fh)
    method_usage = summary.get("phase_method_usage_time_s", {})
    map_time = method_usage.get("map", 0.0)
    assert map_time == 0.0
