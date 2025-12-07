import json
from pathlib import Path

import numpy as np
import pytest
import pandas as pd

from marsdisk import schema
from marsdisk.physics import tempdriver
from marsdisk import run
from siO2_disk_cooling.model import YEAR_SECONDS

SECONDS_PER_DAY = 86400.0


def test_temperature_driver_prefers_radiation_override() -> None:
    radiation = schema.Radiation(TM_K=2300.0)

    info = tempdriver.autogenerate_temperature_table_if_needed(
        schema.Config(
            geometry=schema.Geometry(mode="0D"),
            disk=schema.Disk(
                geometry=schema.DiskGeometry(
                    r_in_RM=2.6,
                    r_out_RM=2.6,
                    r_profile="uniform",
                    p_index=0.0,
                )
            ),
            material=schema.Material(rho=3000.0),
            radiation=radiation,
            sizes=schema.Sizes(s_min=1.0e-8, s_max=1.0e-3, n_bins=8),
            initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
            dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
            psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
            qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
            numerics=schema.Numerics(t_end_years=0.01, dt_init=1.0),
            io=schema.IO(outdir=Path("out_dummy")),
        ),
        t_end_years=0.01,
        t_orb=10.0,
    )
    driver = tempdriver.resolve_temperature_driver(radiation, t_orb=10.0, prefer_driver=True)

    assert driver.source == "mars_temperature_driver.table"
    assert driver.mode == "table"
    assert driver.evaluate(0.0) == pytest.approx(2300.0)
    assert driver.evaluate(1.0e5) < 2300.0


def test_temperature_driver_table_interpolates_sample() -> None:
    table_path = Path(__file__).resolve().parents[1] / "data" / "mars_temperature_table_example.csv"
    driver_cfg = schema.MarsTemperatureDriverConfig(
        enabled=True,
        mode="table",
        table=schema.MarsTemperatureDriverTable(
            path=table_path,
            time_unit="day",
            column_time="time_day",
            column_temperature="T_K",
        ),
        extrapolation="hold",
    )
    radiation = schema.Radiation(TM_K=None, mars_temperature_driver=driver_cfg)

    driver = tempdriver.resolve_temperature_driver(radiation, t_orb=2.0 * np.pi)

    assert driver.source == "mars_temperature_driver.table"
    assert driver.mode == "table"
    assert driver.evaluate(0.0) == pytest.approx(2500.0)
    mid_time = 10.0 * SECONDS_PER_DAY
    assert driver.evaluate(mid_time) == pytest.approx(2475.0)
    later = 300.0 * SECONDS_PER_DAY
    assert driver.evaluate(later) == pytest.approx(2050.0)


def test_temperature_autogen_generates_table(tmp_path: Path) -> None:
    autogen_cfg = schema.MarsTemperatureAutogen(
        enabled=True,
        output_dir=tmp_path,
        dt_hours=1.0,
        min_years=0.05,
        time_margin_years=0.05,
        time_unit="day",
        column_time="time_day",
        column_temperature="T_K",
    )

    info = tempdriver.ensure_temperature_table(
        autogen_cfg,
        T0=3200.0,
        t_end_years=0.02,
        t_orb=2.0 * np.pi,
    )

    path = info["path"]
    assert path.exists()
    df = pd.read_csv(path)
    max_time_day = float(df["time_day"].max())
    required_s = 0.1 * YEAR_SECONDS
    assert max_time_day * SECONDS_PER_DAY >= required_s - SECONDS_PER_DAY
    assert float(df["T_K"].iloc[0]) == pytest.approx(3200.0)


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_autogen_used_in_run(tmp_path: Path) -> None:
    outdir = tmp_path / "autogen_run"
    autogen_cfg = schema.MarsTemperatureAutogen(
        enabled=True,
        output_dir=tmp_path,
        dt_hours=1.0,
        min_years=0.05,
        time_margin_years=0.02,
        time_unit="day",
        column_time="time_day",
        column_temperature="T_K",
    )
    driver_cfg = schema.MarsTemperatureDriverConfig(
        enabled=True,
        mode="table",
        table=schema.MarsTemperatureDriverTable(
            path=tmp_path / "placeholder.csv",
            time_unit="day",
            column_time="time_day",
            column_temperature="T_K",
        ),
        extrapolation="hold",
        autogenerate=autogen_cfg,
    )
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.6,
                r_out_RM=2.6,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        sizes=schema.Sizes(s_min=1.0e-8, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-6, dt_init=1.0, eval_per_step=False),
        io=schema.IO(outdir=outdir),
    )
    cfg.sinks.mode = "none"
    cfg.radiation = schema.Radiation(
        TM_K=4500.0,
        qpr_table_path=Path("data/qpr_table.csv"),
        mars_temperature_driver=driver_cfg,
    )

    run.run_zero_d(cfg)

    summary_path = outdir / "summary.json"
    summary = json.loads(summary_path.read_text())
    assert summary["T_M_source"] == "mars_temperature_driver.table"
    assert summary["T_M_used"] == pytest.approx(4500.0)
    generated_tables = list(tmp_path.glob("mars_temperature_T4500p0K.csv"))
    assert generated_tables, "autogen table should be created next to output_dir"
    df = pd.read_csv(generated_tables[0])
    assert df["T_K"].iloc[0] == pytest.approx(4500.0)
