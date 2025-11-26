from pathlib import Path

import numpy as np
import pytest

from marsdisk import schema
from marsdisk.physics import tempdriver

SECONDS_PER_DAY = 86400.0


def test_temperature_driver_prefers_radiation_override() -> None:
    temps = schema.Temps(T_M=2100.0)
    radiation = schema.Radiation(TM_K=2300.0)

    driver = tempdriver.resolve_temperature_driver(temps, radiation, t_orb=10.0)

    assert driver.source == "radiation.TM_K"
    assert driver.mode == "constant"
    assert driver.evaluate(0.0) == pytest.approx(2300.0)
    assert driver.evaluate(1.0e5) == pytest.approx(2300.0)


def test_temperature_driver_table_interpolates_sample() -> None:
    temps = schema.Temps(T_M=2100.0)
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

    driver = tempdriver.resolve_temperature_driver(temps, radiation, t_orb=2.0 * np.pi)

    assert driver.source == "mars_temperature_driver.table"
    assert driver.mode == "table"
    assert driver.evaluate(0.0) == pytest.approx(2500.0)
    mid_time = 10.0 * SECONDS_PER_DAY
    assert driver.evaluate(mid_time) == pytest.approx(2475.0)
    later = 300.0 * SECONDS_PER_DAY
    assert driver.evaluate(later) == pytest.approx(2050.0)
