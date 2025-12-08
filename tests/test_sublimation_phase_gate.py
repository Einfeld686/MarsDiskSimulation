from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marsdisk import run


BASE_CONFIG = Path("configs/base.yml")


def _run_phase_case(
    tmp_path: Path, entrypoint: str, *, enable_step_diag: bool = True, extra_overrides: list[str] | None = None
) -> tuple[pd.Series, pd.DataFrame | None]:
    outdir = tmp_path
    overrides = [
        f"io.outdir={outdir}",
        "sinks.mode=sublimation",
        "sinks.enable_sublimation=true",
        "sinks.sub_params.mode=logistic",
        "physics_mode=sublimation_only",
        "phase.enabled=true",
        "phase.source=map",
        f"phase.entrypoint={entrypoint}",
        "blowout.enabled=false",
        "numerics.t_end_years=1e-9",
        "numerics.dt_init=1.0",
        "radiation.TM_K=2000.0",
    ]
    if extra_overrides:
        overrides.extend(extra_overrides)
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
    row, diag_df = _run_phase_case(
        tmp_path / "liquid",
        "tests.phase_map_stub:lookup_phase_liquid",
        extra_overrides=[
            "phase.allow_liquid_hkl=false",
            "sinks.sub_params.enable_liquid_branch=false",
        ],
    )
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


def test_liquid_phase_allows_hkl_when_enabled(tmp_path: Path) -> None:
    extra = [
        "sinks.sub_params.mode=hkl",
        "sinks.sub_params.psat_model=clausius",
        "sinks.sub_params.enable_liquid_branch=true",
        "sinks.sub_params.psat_liquid_switch_K=1500.0",
        "phase.allow_liquid_hkl=true",
    ]
    row, diag_df = _run_phase_case(
        tmp_path / "liquid_hkl",
        "tests.phase_map_stub:lookup_phase_liquid",
        extra_overrides=extra,
    )
    assert row["phase_bulk_state"] == "liquid_dominated"
    assert bool(row["sublimation_blocked_by_phase"]) is False
    assert row["ds_dt_sublimation_raw"] < 0.0
    assert row["ds_dt_sublimation"] == pytest.approx(row["ds_dt_sublimation_raw"])
    assert diag_df is not None
    diag_row = diag_df.iloc[-1]
    assert bool(diag_row["sublimation_blocked_by_phase"]) is False
    assert diag_row["phase_state_step"] == "vapor"
    assert diag_row["ds_dt_sublimation"] == pytest.approx(diag_row["ds_dt_sublimation_raw"])
