from importlib import util
from pathlib import Path

import numpy as np
import pandas as pd


def _load_sweep_module():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "sweep_heatmaps.py"
    spec = util.spec_from_file_location("sweep_heatmaps", script_path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


SWEEP = _load_sweep_module()


def test_map1_definition_range():
    definition = SWEEP.create_map_definition("1")
    assert definition.map_key == "1"
    assert definition.output_stub == "map1"
    assert len(definition.param_x.values) == 21
    assert np.isclose(definition.param_x.values[0], 1.0)
    assert np.isclose(definition.param_x.values[-1], 3.0)
    assert len(definition.param_y.values) == 101
    assert np.isclose(definition.param_y.values[0], 1000.0)
    assert np.isclose(definition.param_y.values[-1], 6000.0)


def test_map1b_definition_range():
    definition = SWEEP.create_map_definition("1b")
    assert definition.map_key == "1b"
    assert definition.output_stub == "map1b"
    assert len(definition.param_x.values) == 21
    assert np.isclose(definition.param_x.values[0], 5.0)
    assert np.isclose(definition.param_x.values[-1], 7.0)
    assert len(definition.param_y.values) == 101
    assert np.isclose(definition.param_y.values[0], 1000.0)
    assert np.isclose(definition.param_y.values[-1], 6000.0)


def test_validate_map1_results_successful_case():
    data = []
    r_values = [1.0, 1.1]
    temps = [1000.0, 1050.0, 1100.0, 1150.0]
    for r in r_values:
        for idx, T in enumerate(temps):
            status = "blowout" if idx >= 2 else "failed"
            mass = np.nan
            mass_per_r2 = np.nan
            if status == "blowout":
                mass = 1.0e-5 * (r ** 2)
                mass_per_r2 = mass / (r ** 2)
            data.append(
                {
                    "map_id": "1",
                    "case_id": f"case_{r}_{T}",
                    "run_status": "success",
                    "case_status": status,
                    "param_x_value": r,
                    "param_y_value": T,
                    "total_mass_lost_Mmars": mass,
                    "mass_per_r2": mass_per_r2,
                    "beta_at_smin": 0.6 if status == "blowout" else 0.4,
                    "beta_threshold": 0.5,
                }
            )
    df = pd.DataFrame(data)
    validation = SWEEP.validate_map1_results(df)
    assert validation["low_temp_band"]["ok"]
    assert validation["mass_per_r2"]["ok"]
    assert validation["low_temp_band"]["reentry_r_values"] == []
    assert validation["low_temp_band"]["beta_violations_r_values"] == []
    assert validation["mass_per_r2"]["max_relative_spread"] <= SWEEP.DEFAULT_TOL_MASS_PER_R2


def test_validate_map1_results_detects_reentry():
    data = []
    temps = [1000.0, 1050.0, 1100.0]
    statuses = ["failed", "blowout", "failed"]
    for status, T in zip(statuses, temps, strict=True):
        mass = 1.0e-5 if status == "blowout" else np.nan
        mass_per_r2 = 1.0e-5 if status == "blowout" else np.nan
        data.append(
            {
                "map_id": "1",
                "case_id": f"case_{status}_{T}",
                "run_status": "success",
                "case_status": status,
                "param_x_value": 1.0,
                "param_y_value": T,
                "total_mass_lost_Mmars": mass,
                "mass_per_r2": mass_per_r2,
                "beta_at_smin": 0.4 if status != "blowout" else 0.6,
                "beta_threshold": 0.5,
            }
        )
    df = pd.DataFrame(data)
    validation = SWEEP.validate_map1_results(df)
    assert not validation["low_temp_band"]["ok"]
    assert 1.0 in validation["low_temp_band"]["reentry_r_values"]
