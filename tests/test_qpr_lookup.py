import numpy as np
import pandas as pd
from marsdisk.physics import radiation
from marsdisk.io import tables


def test_qpr_lookup_fallback_and_table(tmp_path):
    s = 1e-6
    T = 3000.0
    orig_table = tables._QPR_TABLE
    orig_lookup = radiation._QPR_LOOKUP
    try:
        tables._QPR_TABLE = None
        radiation._QPR_LOOKUP = tables.interp_qpr
        assert np.isclose(radiation.qpr_lookup(s, T), tables._approx_qpr(s, T))
        df = pd.DataFrame({
            "log10_s": [-6, -6, -5, -5],
            "T_M": [3000, 3100, 3000, 3100],
            "Q_pr": [0.1, 0.2, 0.3, 0.4],
        })
        path = tmp_path / "qpr_planck.csv"
        df.to_csv(path, index=False)
        radiation.load_qpr_table(path)
        assert np.isclose(radiation.qpr_lookup(1e-6, 3000), 0.1)
        val = radiation.qpr_lookup(3.16227766017e-6, 3050)
        assert np.isclose(val, 0.25, atol=1e-6)
    finally:
        tables._QPR_TABLE = orig_table
        radiation._QPR_LOOKUP = orig_lookup

