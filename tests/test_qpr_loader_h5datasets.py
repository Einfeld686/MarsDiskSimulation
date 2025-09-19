"""Tests for reading ⟨Q_pr⟩ tables from raw HDF5 datasets."""

from __future__ import annotations

import builtins

import numpy as np
import pytest

from marsdisk.io import tables

try:
    import h5py as _h5py
except ImportError:  # pragma: no cover - optional dependency
    _h5py = None


def _write_three_dataset(path, qpr, log10s, temperatures):
    if _h5py is None:
        pytest.skip("h5py is required for dataset-based tests")
    with _h5py.File(path, "w") as handle:
        handle.create_dataset("qpr", data=qpr)
        handle.create_dataset("log10s", data=log10s)
        handle.create_dataset("T", data=temperatures)


@pytest.mark.skipif(_h5py is None, reason="h5py is required for dataset-based tests")
def test_load_qpr_table_from_h5datasets(tmp_path):
    path = tmp_path / "qpr_planck.h5"
    T = np.array([2000.0, 3000.0])
    log10s = np.array([-6.0, -5.0])
    qpr = np.array([[0.1, 0.3], [0.2, 0.4]])
    _write_three_dataset(path, qpr, log10s, T)

    original_table = tables._QPR_TABLE
    try:
        lookup = tables.load_qpr_table(path)
        s_vals = 10.0 ** log10s
        assert np.isclose(lookup(s_vals[0], T[0]), 0.1, atol=1e-12)
        assert np.isclose(lookup(s_vals[1], T[1]), 0.4, atol=1e-12)

        mid_s = 0.5 * (s_vals[0] + s_vals[1])
        mid_T = 0.5 * (T[0] + T[1])
        assert np.isclose(lookup(mid_s, mid_T), 0.25, atol=1e-12)
    finally:
        tables._QPR_TABLE = original_table


@pytest.mark.skipif(_h5py is None, reason="h5py is required for dataset-based tests")
def test_h5datasets_shape_mismatch(tmp_path):
    path = tmp_path / "bad_qpr.h5"
    T = np.array([2000.0, 3000.0])
    log10s = np.array([-6.0, -5.0])
    qpr = np.array([[0.1, 0.2]])  # shape mismatch
    _write_three_dataset(path, qpr, log10s, T)

    with pytest.raises(ValueError, match="Dataset 'qpr' has shape"):
        tables._read_qpr_frame_h5datasets(path)


def test_h5datasets_requires_h5py(monkeypatch, tmp_path):
    dummy_path = tmp_path / "dummy_qpr.h5"
    dummy_path.write_bytes(b"")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "h5py":
            raise ModuleNotFoundError("No module named 'h5py'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(
        ValueError,
        match="h5py is required to read HDF5 datasets 'qpr','log10s','T'",
    ):
        tables._read_qpr_frame_h5datasets(dummy_path)
