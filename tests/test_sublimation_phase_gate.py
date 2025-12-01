from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marsdisk import run


BASE_CONFIG = Path("configs/base.yml")


def _run_phase_case(tmp_path: Path, entrypoint: str, *, enable_step_diag: bool = True) -> tuple[pd.Series, pd.DataFrame | None]:
    outdir = tmp_path
    overrides = [
        f"io.outdir={outdir}",
        "sinks.mode=sublimation",
        "sinks.enable_sublimation=true",
        "sinks.sub_params.mode=logistic",
        "process.primary=sublimation_only",
        "phase.enabled=true",
        "phase.source=map",
        f"phase.map.entrypoint={entrypoint}",
        "blowout.enabled=false",
        "numerics.t_end_years=1e-9",
        "numerics.dt_init=1.0",
        "temps.T_M=2000.0",
    ]
    if enable_step_diag:
        overrides.extend(
            [
                "io.step_diagnostics.enable=true",
                "io.step_diagnostics.format=csv",
            ]
        )
    cfg = run.load_config(BASE_CONFIG, overrides=overrides)
    run.run_zero_d(cfg)
    df = pd.read_parquet(outdir / "series" / "run.parquet")
    step_diag_df: pd.DataFrame | None = None
    if enable_step_diag:
        diag_path = outdir / "series" / "step_diagnostics.csv"
        assert diag_path.exists(), f"step diagnostics missing at {diag_path}"
        step_diag_df = pd.read_csv(diag_path)
    return df.iloc[-1], step_diag_df


def test_liquid_phase_blocks_sublimation(tmp_path: Path) -> None:
    row, diag_df = _run_phase_case(tmp_path / "liquid", "tests.phase_map_stub:lookup_phase_liquid")
    assert row["phase_bulk_state"] == "liquid_dominated"
    assert row["ds_dt_sublimation_raw"] < 0.0
    assert row["ds_dt_sublimation"] == pytest.approx(0.0)
    assert bool(row["sublimation_blocked_by_phase"]) is True
    assert diag_df is not None
    diag_row = diag_df.iloc[-1]
    assert diag_row["phase_bulk_state"] == "liquid_dominated"
    assert diag_row["phase_state_step"] == "vapor"
    assert bool(diag_row["sublimation_blocked_by_phase"]) is True
    assert diag_row["ds_dt_sublimation_raw"] < 0.0
    assert diag_row["ds_dt_sublimation"] == pytest.approx(0.0)


def test_solid_phase_uses_raw_sublimation(tmp_path: Path) -> None:
    row, diag_df = _run_phase_case(tmp_path / "solid", "tests.phase_map_stub:lookup_phase_solid")
    assert row["phase_bulk_state"] == "solid_dominated"
    assert row["ds_dt_sublimation_raw"] == pytest.approx(row["ds_dt_sublimation"])
    assert row["ds_dt_sublimation_raw"] < 0.0
    assert bool(row["sublimation_blocked_by_phase"]) is False
    assert diag_df is not None
    diag_row = diag_df.iloc[-1]
    assert diag_row["phase_bulk_state"] == "solid_dominated"
    assert diag_row["phase_state_step"] == "solid"
    assert bool(diag_row["sublimation_blocked_by_phase"]) is False
    assert diag_row["ds_dt_sublimation_raw"] == pytest.approx(diag_row["ds_dt_sublimation"])
    assert diag_row["ds_dt_sublimation_raw"] < 0.0
