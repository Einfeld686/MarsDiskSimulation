"""Numba無効化時のフォールバックパスを検証するユニットテスト。"""

from __future__ import annotations

import importlib
import numpy as np


def test_fragment_tensor_fallback_with_numba_disabled(monkeypatch) -> None:
    # 環境変数で numba を無効化した状態でリロード
    import marsdisk.physics.collisions_smol as collisions_smol

    monkeypatch.setenv("MARSDISK_DISABLE_NUMBA", "1")
    collisions_smol = importlib.reload(collisions_smol)

    assert collisions_smol._USE_NUMBA is False

    sizes = np.array([1.0e-4, 2.0e-4, 4.0e-4])
    widths = np.array([0.5e-4, 1.0e-4, 2.0e-4])
    edges = np.empty(sizes.size + 1, dtype=float)
    edges[:-1] = np.maximum(sizes - 0.5 * widths, 0.0)
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    masses = np.array([1.0e-9, 8.0e-9, 6.4e-8])
    Y = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel=1.0, rho=3000.0
    )

    # フォールバック経路でも有限の非零テンソルが返ること
    assert Y.shape == (3, 3, 3)
    assert np.isfinite(Y).all()
    assert np.any(Y > 0.0)

    # 環境を元に戻しておく
    monkeypatch.delenv("MARSDISK_DISABLE_NUMBA", raising=False)
    importlib.reload(collisions_smol)
