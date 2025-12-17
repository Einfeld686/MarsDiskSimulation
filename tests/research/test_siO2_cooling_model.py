from __future__ import annotations

import numpy as np
import pytest

from siO2_disk_cooling.model import (
    CoolingParams,
    arrival_time_for_threshold,
    dust_temperature,
    mars_temperature,
)


def test_mars_temperature_monotonic_decrease() -> None:
    params = CoolingParams()
    time_s = np.linspace(0.0, 1.0e6, 50)
    temps = mars_temperature(time_s, 4000.0, params)
    assert np.all(np.diff(temps) <= 0.0)


def test_dust_temperature_monotonic_decrease_single_radius() -> None:
    params = CoolingParams()
    time_s = np.linspace(0.0, 1.0e6, 40)
    temps = dust_temperature(params.R_mars * 1.5, time_s, 3000.0, params)
    assert temps.shape == time_s.shape
    assert np.all(np.diff(temps) <= 0.0)


def test_arrival_time_for_threshold() -> None:
    time_s = np.array([0.0, 10.0, 20.0, 30.0])
    temps = np.array([2000.0, 1500.0, 1000.0, 500.0])
    threshold = 900.0
    arrival = arrival_time_for_threshold(1.0, time_s, temps, threshold)
    assert arrival == pytest.approx(30.0)
