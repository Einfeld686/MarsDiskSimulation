from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run
from marsdisk.physics.phase import particle_temperature_equilibrium


def test_particle_temperature_equilibrium_matches_expected_scaling() -> None:
    T_mars = 2000.0
    q_abs = 0.4
    r = constants.R_MARS
    expected = T_mars * (q_abs ** 0.25) * math.sqrt(constants.R_MARS / (2.0 * r))
    result = particle_temperature_equilibrium(T_mars, r, q_abs)
    assert math.isclose(result, expected, rel_tol=1e-12, abs_tol=0.0)


def test_particle_temperature_equilibrium_rejects_nonpositive_radius() -> None:
    with pytest.raises(ValueError):
        particle_temperature_equilibrium(2000.0, 0.0, 0.4)


def test_phase_temperature_input_particle_is_recorded(tmp_path: Path) -> None:
    overrides = [
        f"io.outdir={tmp_path}",
        "numerics.t_end_orbits=1.0e-4",
        "numerics.t_end_years=null",
        "numerics.dt_init=10.0",
        "phase.enabled=true",
        "phase.temperature_input=particle",
        "phase.q_abs_mean=0.4",
        "radiation.mars_temperature_driver.enabled=false",
        "radiation.TM_K=2000.0",
        "disk.geometry.r_in_RM=1.5",
        "disk.geometry.r_out_RM=1.6",
    ]
    cfg = run.load_config(Path("configs/base.yml"), overrides=overrides)
    run.run_zero_d(cfg)

    series_path = tmp_path / "series" / "run.parquet"
    assert series_path.exists(), "run.parquet missing"
    df = pd.read_parquet(series_path)
    assert {"T_p_effective", "phase_temperature_input", "r_orbit_RM"}.issubset(df.columns)
    assert (df["phase_temperature_input"] == "particle").all()
    assert (df["T_p_effective"] < df["T_M_used"]).all()

    run_config_path = tmp_path / "run_config.json"
    assert run_config_path.exists(), "run_config.json missing"
    with run_config_path.open("r", encoding="utf-8") as fh:
        run_config = json.load(fh)
    phase_temp_cfg = run_config.get("phase_temperature", {})
    assert phase_temp_cfg.get("mode") == "particle"
    assert math.isclose(phase_temp_cfg.get("q_abs_mean", 0.0), 0.4, rel_tol=0.0, abs_tol=0.0)
    assert run_config["run_inputs"]["phase_temperature_input"] == "particle"
