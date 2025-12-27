import numpy as np
import pytest

from marsdisk.io import tables
from marsdisk.physics import radiation


@pytest.fixture(autouse=True)
def _reset_qpr_fallback() -> None:
    radiation.configure_qpr_fallback(strict=False)
    yield
    radiation.configure_qpr_fallback(strict=False)


def _clear_qpr_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(radiation, "_QPR_LOOKUP", None, raising=False)
    monkeypatch.setattr(tables, "_QPR_TABLE", None, raising=False)
    monkeypatch.setattr(tables, "_QPR_TABLE_PATH", None, raising=False)


def test_planck_mean_qpr_fallback_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_qpr_tables(monkeypatch)
    val = radiation.planck_mean_qpr(1.0e-6, 2000.0)
    assert val == pytest.approx(radiation.DEFAULT_Q_PR)


def test_qpr_lookup_array_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_qpr_tables(monkeypatch)
    sizes = np.array([1.0e-6, 2.0e-6], dtype=float)
    vals = radiation.qpr_lookup_array(sizes, 2000.0)
    assert np.allclose(vals, radiation.DEFAULT_Q_PR)


def test_planck_mean_qpr_strict_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_qpr_tables(monkeypatch)
    radiation.configure_qpr_fallback(strict=True)
    with pytest.raises(RuntimeError, match="qpr_strict"):
        radiation.planck_mean_qpr(1.0e-6, 2000.0)
