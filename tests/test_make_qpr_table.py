"""Planck平均Q_prテーブル生成ユーティリティのテスト。Planck 平均⟨Q_pr⟩."""
import numpy as np

from marsdisk.ops.make_qpr_table import compute_planck_mean_qpr


def test_small_grain_qpr_increases_with_temperature():
    s_values = np.geomspace(1.0e-9, 1.0e-6, num=6)
    temperatures = np.array([1500.0, 2500.0, 3500.0], dtype=float)

    qpr = compute_planck_mean_qpr(s_values, temperatures)

    assert qpr.shape == (temperatures.size, s_values.size)
    assert np.all(qpr >= 0.0)
    assert np.all(qpr <= 1.0)
    assert qpr[-1, 0] > qpr[0, 0]
