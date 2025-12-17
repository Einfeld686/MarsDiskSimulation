from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run


BASE_CONFIG = Path("configs/base.yml")
DEFAULT_ENTRYPOINT = "siO2_disk_cooling.siO2_cooling_map:lookup_phase_state"


def _run_case(tmp_path: Path, *, T_M: float, r_RM: float) -> tuple[pd.Series, pd.DataFrame]:
    outdir = tmp_path
    overrides = [
        f"io.outdir={outdir}",
        "sinks.mode=sublimation",
        "sinks.enable_sublimation=true",
        "sinks.sub_params.mode=logistic",
        "physics_mode=sublimation_only",
        "phase.enabled=true",
        "phase.source=map",
        f"phase.entrypoint={DEFAULT_ENTRYPOINT}",
        "blowout.enabled=false",
        "numerics.t_end_years=1e-9",
        "numerics.dt_init=1.0",
        f"radiation.TM_K={T_M}",
        f"disk.geometry.r_in_RM={r_RM}",
        f"disk.geometry.r_out_RM={r_RM + 1.0e-6}",
        "io.step_diagnostics.enable=true",
        "io.step_diagnostics.format=csv",
    ]
    cfg = run.load_config(BASE_CONFIG, overrides=overrides)
    run.run_zero_d(cfg)
    series = pd.read_parquet(outdir / "series" / "run.parquet")
    step_diag = pd.read_csv(outdir / "series" / "step_diagnostics.csv")
    return series.iloc[-1], step_diag


def test_solid_phase_allows_sublimation_with_siO2_map(tmp_path: Path) -> None:
    row, step_diag = _run_case(tmp_path / "sol", T_M=1400.0, r_RM=3.5)
    assert row["phase_bulk_state"] == "solid_dominated"
    assert bool(row["sublimation_blocked_by_phase"]) is False
    raw = float(row["ds_dt_sublimation_raw"])
    applied = float(row["ds_dt_sublimation"])
    assert raw < 0.0
    assert applied == pytest.approx(raw, rel=1e-6, abs=1e-12)
    assert row["phase_bulk_f_solid"] >= row["phase_bulk_f_liquid"]
