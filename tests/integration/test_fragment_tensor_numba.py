import numpy as np
import pytest

from marsdisk.physics import collisions_smol
from marsdisk.warnings import NumericalWarning


def _sample_inputs():
    sizes = np.array([1.0e-6, 2.0e-6, 5.0e-6], dtype=float)
    widths = np.array([0.6e-6, 1.2e-6, 2.5e-6], dtype=float)
    edges = np.empty(sizes.size + 1, dtype=float)
    edges[:-1] = np.maximum(sizes - 0.5 * widths, 0.0)
    edges[-1] = sizes[-1] + 0.5 * widths[-1]
    rho = 3000.0
    masses = (4.0 / 3.0) * np.pi * rho * sizes**3
    v_rel = 10.0  # m/s
    return sizes, edges, masses, v_rel, rho


@pytest.mark.skipif(
    not getattr(collisions_smol, "_NUMBA_AVAILABLE", False),
    reason="Numba unavailable; numba vs python parity not applicable",
)
def test_fragment_tensor_numba_matches_python():
    sizes, edges, masses, v_rel, rho = _sample_inputs()
    y_numba = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel, rho, use_numba=True
    )
    y_py = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel, rho, use_numba=False
    )
    assert np.allclose(y_numba, y_py)

    # Mass fractions should sum to 1 for valid (i, j) pairs.
    m1 = masses[:, None]
    m2 = masses[None, :]
    valid = (m1 > 0.0) & (m2 > 0.0) & (m1 + m2 > 0.0)
    pair_sums = y_numba.sum(axis=0)
    assert np.allclose(pair_sums[valid], 1.0)
    assert np.all(pair_sums[~valid] == 0.0)


@pytest.mark.skipif(
    not getattr(collisions_smol, "_NUMBA_AVAILABLE", False),
    reason="Numba unavailable; fallback path not exercised",
)
def test_fragment_tensor_numba_failure_falls_back(monkeypatch):
    sizes, edges, masses, v_rel, rho = _sample_inputs()
    monkeypatch.setattr(collisions_smol, "_NUMBA_FAILED", False)

    def _explode(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(collisions_smol, "fill_fragment_tensor_numba", _explode)

    with pytest.warns(NumericalWarning, match="numba kernel failed"):
        y_fallback = collisions_smol._fragment_tensor(
            sizes, masses, edges, v_rel, rho, use_numba=True
        )
    y_py = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel, rho, use_numba=False
    )
    assert np.allclose(y_fallback, y_py)
