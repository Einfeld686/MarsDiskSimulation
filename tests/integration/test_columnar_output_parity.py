"""Columnar record storage parity checks for 0D/1D outputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk.output_schema import (
    ONE_D_EXTRA_DIAGNOSTIC_KEYS,
    ONE_D_EXTRA_SERIES_KEYS,
    ZERO_D_DIAGNOSTIC_KEYS,
    ZERO_D_SERIES_KEYS,
)
from one_d_helpers import run_one_d_case, run_zero_d_case


def _assert_numeric_close(left: pd.DataFrame, right: pd.DataFrame, columns: list[str]) -> None:
    sort_keys = ["time"]
    if "cell_index" in left.columns and "cell_index" in right.columns:
        sort_keys = ["time", "cell_index"]
    left_sorted = left.sort_values(sort_keys).reset_index(drop=True)
    right_sorted = right.sort_values(sort_keys).reset_index(drop=True)
    for name in columns:
        lhs = left_sorted[name].to_numpy()
        rhs = right_sorted[name].to_numpy()
        assert np.allclose(lhs, rhs, rtol=1e-12, atol=0.0, equal_nan=True)


def _assert_column_equal(left: pd.DataFrame, right: pd.DataFrame, name: str) -> None:
    lhs = left[name].to_numpy()
    rhs = right[name].to_numpy()
    assert lhs.shape == rhs.shape
    assert np.array_equal(lhs, rhs, equal_nan=True)


def _assert_time_order(df: pd.DataFrame) -> None:
    time = df["time"].to_numpy()
    assert np.all(np.diff(time) >= 0.0)


def _assert_cell_index_order(df: pd.DataFrame) -> None:
    for _time_val, group in df.groupby("time", sort=False):
        values = group["cell_index"].to_numpy()
        assert np.all(np.diff(values) >= 0)


def _assert_nan_masks_equal(left: pd.DataFrame, right: pd.DataFrame, columns: list[str]) -> None:
    for name in columns:
        if name not in left.columns or name not in right.columns:
            continue
        lhs = left[name].isna().to_numpy()
        rhs = right[name].isna().to_numpy()
        assert np.array_equal(lhs, rhs)


def _assert_mass_budget_equal(row_dir: Path, col_dir: Path) -> None:
    row_path = row_dir / "checks" / "mass_budget.csv"
    col_path = col_dir / "checks" / "mass_budget.csv"
    row_df = pd.read_csv(row_path)
    col_df = pd.read_csv(col_path)
    for col in ("time", "error_percent", "mass_diff", "mass_lost"):
        if col not in row_df.columns or col not in col_df.columns:
            continue
        lhs = row_df[col].to_numpy()
        rhs = col_df[col].to_numpy()
        if col == "time":
            assert np.array_equal(lhs, rhs, equal_nan=True)
        else:
            assert np.allclose(lhs, rhs, rtol=1e-12, atol=0.0, equal_nan=True)


def test_columnar_zero_d_schema_parity(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=0D",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.streaming.enable=false",
    ]
    _, row_df, row_dir = run_zero_d_case(
        tmp_path / "row",
        overrides + ["io.record_storage_mode=row"],
    )
    _, col_df, col_dir = run_zero_d_case(
        tmp_path / "col",
        overrides + ["io.record_storage_mode=columnar"],
    )

    assert set(row_df.columns) == set(col_df.columns)
    assert all(name in col_df.columns for name in ZERO_D_SERIES_KEYS)
    diag_row = pd.read_parquet(row_dir / "series" / "diagnostics.parquet")
    diag_col = pd.read_parquet(col_dir / "series" / "diagnostics.parquet")
    assert set(diag_row.columns) == set(diag_col.columns)
    assert all(name in diag_col.columns for name in ZERO_D_DIAGNOSTIC_KEYS)
    _assert_numeric_close(row_df, col_df, ["time", "dt", "M_out_dot", "M_loss_cum"])
    _assert_time_order(row_df)
    _assert_time_order(col_df)
    _assert_column_equal(row_df, col_df, "time")
    _assert_nan_masks_equal(row_df, col_df, ["s_min", "t_coll_kernel_min", "sigma_tau1"])
    _assert_mass_budget_equal(row_dir, col_dir)
    assert (col_dir / "checks" / "mass_budget.csv").exists()


def test_columnar_one_d_schema_parity(tmp_path: Path) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.streaming.enable=false",
    ]
    _, row_df, row_dir = run_one_d_case(
        tmp_path / "row",
        overrides + ["io.record_storage_mode=row"],
    )
    _, col_df, col_dir = run_one_d_case(
        tmp_path / "col",
        overrides + ["io.record_storage_mode=columnar"],
    )

    assert set(row_df.columns) == set(col_df.columns)
    assert all(name in col_df.columns for name in ZERO_D_SERIES_KEYS)
    assert all(name in col_df.columns for name in ONE_D_EXTRA_SERIES_KEYS)
    diag_row = pd.read_parquet(row_dir / "series" / "diagnostics.parquet")
    diag_col = pd.read_parquet(col_dir / "series" / "diagnostics.parquet")
    assert set(diag_row.columns) == set(diag_col.columns)
    assert all(name in diag_col.columns for name in ZERO_D_DIAGNOSTIC_KEYS)
    assert all(name in diag_col.columns for name in ONE_D_EXTRA_DIAGNOSTIC_KEYS)
    _assert_numeric_close(row_df, col_df, ["time", "dt", "M_out_dot", "M_loss_cum"])
    _assert_time_order(row_df)
    _assert_time_order(col_df)
    _assert_cell_index_order(row_df)
    _assert_cell_index_order(col_df)
    _assert_column_equal(row_df, col_df, "time")
    _assert_column_equal(row_df, col_df, "cell_index")
    _assert_nan_masks_equal(row_df, col_df, ["s_min", "t_coll_kernel_min", "sigma_tau1"])
    _assert_mass_budget_equal(row_dir, col_dir)
    assert (col_dir / "checks" / "mass_budget.csv").exists()


def test_columnar_mass_budget_streaming(tmp_path: Path, monkeypatch) -> None:
    overrides = [
        "geometry.mode=0D",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.record_storage_mode=columnar",
        "io.streaming.enable=true",
    ]
    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, _, outdir = run_zero_d_case(tmp_path, overrides)
    assert (outdir / "checks" / "mass_budget.csv").exists()


def test_columnar_zero_d_streaming_order(tmp_path: Path, monkeypatch) -> None:
    overrides_base = [
        "geometry.mode=0D",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.record_storage_mode=columnar",
    ]
    _, off_df, _ = run_zero_d_case(
        tmp_path / "off",
        overrides_base + ["io.streaming.enable=false"],
    )
    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, on_df, _ = run_zero_d_case(
        tmp_path / "on",
        overrides_base + ["io.streaming.enable=true"],
    )
    _assert_time_order(off_df)
    _assert_time_order(on_df)
    _assert_column_equal(off_df, on_df, "time")


def test_columnar_one_d_mass_budget_streaming(tmp_path: Path, monkeypatch) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.record_storage_mode=columnar",
        "io.streaming.enable=true",
    ]
    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, _, outdir = run_one_d_case(tmp_path, overrides)
    assert (outdir / "checks" / "mass_budget.csv").exists()


def test_columnar_one_d_streaming_order(tmp_path: Path, monkeypatch) -> None:
    overrides_base = [
        "geometry.mode=1D",
        "geometry.Nr=2",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "io.record_storage_mode=columnar",
    ]
    _, off_df, _ = run_one_d_case(
        tmp_path / "off",
        overrides_base + ["io.streaming.enable=false"],
    )
    monkeypatch.setenv("FORCE_STREAMING_ON", "1")
    monkeypatch.setenv("FORCE_STREAMING_OFF", "0")
    _, on_df, _ = run_one_d_case(
        tmp_path / "on",
        overrides_base + ["io.streaming.enable=true"],
    )
    _assert_time_order(off_df)
    _assert_time_order(on_df)
    _assert_cell_index_order(off_df)
    _assert_cell_index_order(on_df)
    _assert_column_equal(off_df, on_df, "time")
    _assert_column_equal(off_df, on_df, "cell_index")
