from importlib import util
from pathlib import Path

import numpy as np

# load timescales module
step1_path = Path(__file__).resolve().parents[1] / "Step1"
spec = util.spec_from_file_location("timescales", step1_path / "timescales.py")
mod_ts = util.module_from_spec(spec)
spec.loader.exec_module(mod_ts)

R_MARS = 3.3895e6  # m


def test_collision_units():
    t_s = mod_ts.collision_timescale_sec(1e-5, 1e3, 3000, 6 * R_MARS)
    t_y = mod_ts.collision_timescale_years(1e-5, 1e3, 3000, 6 * R_MARS)
    assert np.isclose(t_y * mod_ts.SECONDS_PER_YEAR, t_s, rtol=1e-6)
