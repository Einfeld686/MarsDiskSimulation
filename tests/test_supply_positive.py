from pathlib import Path

import pandas as pd

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
