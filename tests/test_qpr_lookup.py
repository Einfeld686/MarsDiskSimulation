"""Unit tests for Planck-mean ``⟨Q_pr⟩`` lookups."""

import numpy as np
import pandas as pd
import pytest

from marsdisk.io import tables
from marsdisk.physics import radiation


@pytest.fixture()
def mock_qpr_table(tmp_path):
    df = pd.DataFrame(
        {
            "log10_s": [-6.0, -6.0, -5.0, -5.0],
            "T_M": [1200.0, 1300.0, 1200.0, 1300.0],
            "Q_pr": [0.1, 0.2, 0.3, 0.4],
        }
    )
    path = tmp_path / "qpr_planck.csv"
    df.to_csv(path, index=False)

    original_table = tables._QPR_TABLE
    original_table_path = tables._QPR_TABLE_PATH
    original_lookup = radiation._QPR_LOOKUP
    try:
        yield path
    finally:
        tables._QPR_TABLE = original_table
        tables._QPR_TABLE_PATH = original_table_path
        radiation._QPR_LOOKUP = original_lookup


def test_qpr_lookup_interpolates_from_table(mock_qpr_table):
    path = mock_qpr_table
    lookup = tables.load_qpr_table(path)

    s_vals = [1e-6, 1e-5]
    T_vals = [1200.0, 1300.0]
    grid_expectations = {
        (s_vals[0], T_vals[0]): 0.1,
        (s_vals[0], T_vals[1]): 0.2,
        (s_vals[1], T_vals[0]): 0.3,
        (s_vals[1], T_vals[1]): 0.4,
    }
    for (s, T), expected in grid_expectations.items():
        assert np.isclose(radiation.qpr_lookup(s, T, table=lookup), expected)

    mid_s = np.sqrt(s_vals[0] * s_vals[1])
    mid_T = 1250.0
    interpolated = radiation.qpr_lookup(mid_s, mid_T, table=lookup)

    s1, s2 = s_vals
    T1, T2 = T_vals
    ws = (mid_s - s1) / (s2 - s1)
    wT = (mid_T - T1) / (T2 - T1)
    q11 = grid_expectations[(s1, T1)]
    q12 = grid_expectations[(s1, T2)]
    q21 = grid_expectations[(s2, T1)]
    q22 = grid_expectations[(s2, T2)]
    expected_mid = (
        q11 * (1 - ws) * (1 - wT)
        + q21 * ws * (1 - wT)
        + q12 * (1 - ws) * wT
        + q22 * ws * wT
    )
    assert np.isclose(interpolated, expected_mid, atol=1e-12)

    cached_lookup = radiation.load_qpr_table(path)
    assert np.isclose(cached_lookup(mid_s, mid_T), interpolated)
    assert np.isclose(radiation.qpr_lookup(mid_s, mid_T), interpolated)

    rho = 1500.0
    beta_val = radiation.beta(mid_s, rho, mid_T)
    L_M = 4.0 * np.pi * radiation.constants.R_MARS**2 * radiation.constants.SIGMA_SB * mid_T**4
    manual = (
        3.0
        * L_M
        * interpolated
        / (16.0 * np.pi * radiation.constants.C * radiation.constants.G * radiation.constants.M_MARS * rho * mid_s)
    )
    assert np.isclose(beta_val, manual)


def test_qpr_lookup_requires_table(mock_qpr_table):
    path = mock_qpr_table
    lookup = tables.load_qpr_table(path)
    s = 2.0e-6
    T = 1250.0
    table_value = lookup(s, T)

    radiation.load_qpr_table(path)
    assert np.isclose(radiation.qpr_lookup(s, T), table_value)

    tables._QPR_TABLE = None
    tables._QPR_TABLE_PATH = None
    radiation._QPR_LOOKUP = None
    with pytest.raises(RuntimeError):
        radiation.qpr_lookup(s, T)

    with pytest.raises(ValueError):
        radiation.qpr_lookup(0.0, T)
    with pytest.raises(ValueError):
        radiation.qpr_lookup(s, 0.0)
