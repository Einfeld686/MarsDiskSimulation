"""Thread-safety checks for shared caches used in cell-parallel runs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest

from marsdisk.io import tables
from marsdisk.physics import qstar, radiation


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
    cache_state = (radiation._QPR_CACHE_ENABLED, radiation._QPR_CACHE_MAXSIZE, radiation._QPR_CACHE_ROUND)
    try:
        yield path
    finally:
        tables._QPR_TABLE = original_table
        tables._QPR_TABLE_PATH = original_table_path
        radiation._QPR_LOOKUP = original_lookup
        radiation.configure_qpr_cache(
            enabled=cache_state[0],
            maxsize=cache_state[1],
            round_tol=cache_state[2],
        )


def test_qpr_cache_thread_safety(mock_qpr_table):
    path = mock_qpr_table
    lookup = tables.load_qpr_table(path)
    radiation.load_qpr_table(path)
    radiation.configure_qpr_cache(enabled=True, maxsize=16, round_tol=None)

    s_val = 2.0e-6
    T_val = 1250.0

    def call_lookup() -> float:
        return radiation.qpr_lookup(s_val, T_val, table=lookup)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: call_lookup(), range(64)))

    values = np.array(results, dtype=float)
    assert np.isfinite(values).all()
    assert np.allclose(values, values[0], rtol=0.0, atol=1e-12)


def test_qdstar_cache_thread_safety():
    s_arr = np.array([1.0e-3, 2.0e-3, 4.0e-3], dtype=float)
    rho = 3000.0
    v_kms = 3.5

    coeffs = qstar.get_coefficient_table()
    try:
        qstar.set_coefficient_table(coeffs)
        qstar.reset_velocity_clamp_stats()

        def call_qdstar() -> np.ndarray:
            return qstar.compute_q_d_star_array(s_arr, rho, v_kms)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: call_qdstar(), range(64)))

        baseline = results[0]
        for result in results[1:]:
            np.testing.assert_allclose(result, baseline, rtol=0.0, atol=1e-12)
        assert np.isfinite(baseline).all()
    finally:
        qstar.set_coefficient_table(coeffs)
        qstar.reset_velocity_clamp_stats()


def test_velocity_clamp_stats_thread_safety():
    s_arr = np.array([1.0e-3, 2.0e-3], dtype=float)
    rho = 3000.0
    v_kms = np.array([0.5, 10.0], dtype=float)
    n_calls = 32

    qstar.reset_velocity_clamp_stats()

    def call_qdstar() -> None:
        qstar.compute_q_d_star_array(s_arr, rho, v_kms)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: call_qdstar(), range(n_calls)))

    stats = qstar.get_velocity_clamp_stats()
    assert stats["below"] == n_calls
    assert stats["above"] == n_calls
