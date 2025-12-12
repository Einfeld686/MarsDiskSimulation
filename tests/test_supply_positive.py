from pathlib import Path
import json

import pandas as pd
import pytest

from marsdisk import run


def test_supply_positive_with_wide_tau_cap(tmp_path: Path) -> None:
    """Const supply remains positive when Sigma_tau1 cap is generous."""

    outdir = tmp_path / "out"
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
            f"io.outdir={outdir}",
            "radiation.TM_K=6000",
            "radiation.mars_temperature_driver.table.path=data/mars_temperature_T6000p0K.csv",
            "supply.enabled=true",
            "supply.mode=const",
            "supply.const.prod_area_rate_kg_m2_s=1.0e-10",
            "supply.mixing.epsilon_mix=1.0",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=1000",
        ],
    )
    run.run_zero_d(cfg)
    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()
    df = pd.read_parquet(series_path, columns=["prod_subblow_area_rate"])
    assert (df["prod_subblow_area_rate"] > 0.0).all()


def test_reservoir_depletes_and_records_metadata(tmp_path: Path) -> None:
    """Finite reservoir runs dry and leaves depletion metadata in outputs."""

    outdir = tmp_path / "out_reservoir"
    reservoir_mass = 1.0e-25
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
            f"io.outdir={outdir}",
            "radiation.TM_K=4000",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=auto",
            "supply.enabled=true",
            "supply.mode=const",
            "supply.const.prod_area_rate_kg_m2_s=1.0e-10",
            "supply.reservoir.enabled=true",
            f"supply.reservoir.mass_total_Mmars={reservoir_mass}",
            "supply.reservoir.depletion_mode=taper",
            "supply.reservoir.taper_fraction=0.5",
        ],
    )
    run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    summary_path = outdir / "summary.json"
    run_config_path = outdir / "run_config.json"
    assert series_path.exists()
    assert summary_path.exists()
    assert run_config_path.exists()

    df = pd.read_parquet(series_path, columns=["prod_subblow_area_rate", "supply_reservoir_remaining_Mmars"])
    assert df["supply_reservoir_remaining_Mmars"].iloc[-1] == pytest.approx(0.0, abs=1e-18)
    assert df["prod_subblow_area_rate"].iloc[-1] <= 1e-18

    summary = json.loads(summary_path.read_text())
    assert summary["supply_reservoir_enabled"] is True
    assert summary["supply_reservoir_mass_total_Mmars"] == pytest.approx(reservoir_mass)
    assert summary["supply_reservoir_remaining_Mmars"] == pytest.approx(0.0, abs=1e-18)
    assert summary["supply_reservoir_mass_used_Mmars"] == pytest.approx(reservoir_mass, rel=0.2)
    assert summary["supply_reservoir_depletion_time_s"] is not None

    run_cfg = json.loads(run_config_path.read_text())
    supply_cfg = run_cfg["supply"]
    assert supply_cfg["reservoir_enabled"] is True
    assert supply_cfg["reservoir_mass_total_Mmars"] == pytest.approx(reservoir_mass)
    assert supply_cfg["reservoir_remaining_Mmars_final"] == pytest.approx(0.0, abs=1e-18)
    assert supply_cfg["reservoir_depletion_time_s"] is not None
    assert supply_cfg["reservoir_mass_used_Mmars"] == pytest.approx(reservoir_mass, rel=0.2)
