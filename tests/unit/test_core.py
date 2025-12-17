import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import constants, grid
from marsdisk.io import tables, writer


def test_constants_values():
    assert constants.G > 0
    assert constants.M_MARS > 0
    assert constants.T_M_RANGE == (1500.0, 2500.0)


def test_grid_relations():
    r = 10 * constants.R_MARS
    om = grid.omega_kepler(r)
    vk = grid.v_kepler(r)
    assert np.isclose(vk, om * r)


def test_writer_and_tables(tmp_path: Path):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    pq_path = tmp_path / "out" / "series.parquet"
    writer.write_parquet(df, pq_path)
    assert pq_path.exists()

    summary_path = tmp_path / "out" / "summary.json"
    writer.write_summary({"x": 1}, summary_path)
    assert json.loads(summary_path.read_text())["x"] == 1

    mass_path = tmp_path / "out" / "mass.csv"
    writer.write_mass_budget([{ "m": 1.0 }], mass_path)
    assert mass_path.exists()

    qpr = tables.interp_qpr(1e-6, 2000.0)
    phi = tables.interp_phi(0.1, 0.5, 0.0)
    assert np.isfinite(qpr)
    assert np.isfinite(phi)
