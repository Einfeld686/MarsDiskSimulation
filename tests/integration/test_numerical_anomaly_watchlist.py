"""Integration checks for numerical anomaly watchlist scenarios."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from marsdisk.run import load_config
from marsdisk import constants, grid

BASE_CONFIG = Path("configs/base.yml")

BASE_OVERRIDES = [
    "geometry.mode=1D",
    "geometry.Nr=2",
    "numerics.t_end_orbits=0.02",
    "numerics.t_end_years=null",
    "numerics.dt_init=50.0",
    "phase.enabled=false",
    "radiation.TM_K=2000.0",
    "supply.enabled=false",
    "io.streaming.enable=false",
]


def _run_one_d_case(tmp_path: Path, overrides: list[str]) -> tuple[dict[str, Any], pd.DataFrame, Path]:
    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.outdir = tmp_path
    cfg.io.debug_sinks = False
    import marsdisk.run_one_d as run_one_d_module

    run_one_d_module.run_one_d(cfg)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    run_df = pd.read_parquet(tmp_path / "series" / "run.parquet")
    return summary, run_df, tmp_path


def _reload_numba_modules(disable: bool) -> None:
    if disable:
        os.environ["MARSDISK_DISABLE_NUMBA"] = "1"
    else:
        os.environ.pop("MARSDISK_DISABLE_NUMBA", None)
    for name in (
        "marsdisk.physics.collisions_smol",
        "marsdisk.physics.smol",
        "marsdisk.physics.collide",
        "marsdisk.physics.psd",
        "marsdisk.physics.radiation",
        "marsdisk.io.tables",
        "marsdisk.run_one_d",
    ):
        module = importlib.import_module(name)
        importlib.reload(module)


def test_psd_history_non_negative(tmp_path: Path) -> None:
    _, _, outdir = _run_one_d_case(tmp_path, BASE_OVERRIDES)

    psd_hist = pd.read_parquet(outdir / "series" / "psd_hist.parquet")
    assert not psd_hist.empty
    for column in ("N_bin", "Sigma_bin", "Sigma_surf"):
        values = psd_hist[column].to_numpy(dtype=float)
        assert np.isfinite(values).all()
        assert (values >= -1.0e-12).all()


def test_mass_budget_recomputed_from_sigma(tmp_path: Path) -> None:
    _, run_df, _ = _run_one_d_case(tmp_path, BASE_OVERRIDES)
    cfg = load_config(BASE_CONFIG, overrides=BASE_OVERRIDES)

    r_in_m = float(cfg.disk.geometry.r_in_RM) * constants.R_MARS
    r_out_m = float(cfg.disk.geometry.r_out_RM) * constants.R_MARS
    n_cells = int(cfg.geometry.Nr)
    radial_grid = grid.RadialGrid.linear(r_in_m, r_out_m, n_cells)
    area_vals = np.asarray(radial_grid.areas, dtype=float)
    area_map = {idx: area_vals[idx] for idx in range(n_cells)}

    run_df = run_df.sort_values(["time", "cell_index"])
    run_df["cell_area"] = run_df["cell_index"].map(area_map)
    run_df["delta_mass_est"] = (
        run_df["dSigma_dt_total"].fillna(0.0)
        * run_df["smol_dt_eff"].fillna(0.0)
        * run_df["cell_area"]
        / constants.M_MARS
    )

    grouped = (
        run_df.groupby("time", as_index=False)
        .agg(
            mass_total_bins=("mass_total_bins", "sum"),
            delta_mass_est=("delta_mass_est", "sum"),
        )
        .sort_values("time")
    )
    assert not grouped.empty

    grouped["mass_total_prev"] = grouped["mass_total_bins"].shift(1)
    grouped["mass_delta_actual"] = grouped["mass_total_bins"] - grouped["mass_total_prev"]
    grouped = grouped.dropna()
    baseline = float(grouped["mass_total_bins"].iloc[0])
    assert baseline > 0.0

    residual = (grouped["mass_delta_actual"] + grouped["delta_mass_est"]).abs()
    rel_error = residual / baseline
    assert rel_error.max() <= 5.0e-3


@pytest.mark.skipif(os.name != "nt", reason="cell parallelism is Windows-only")
def test_cell_parallel_on_off_consistency(tmp_path: Path, monkeypatch) -> None:
    overrides = [
        "geometry.mode=1D",
        "geometry.Nr=4",
        "numerics.t_end_orbits=0.02",
        "numerics.t_end_years=null",
        "numerics.dt_init=50.0",
        "phase.enabled=false",
        "radiation.TM_K=2000.0",
        "supply.enabled=false",
        "io.streaming.enable=false",
    ]

    monkeypatch.setenv("MARSDISK_CELL_PARALLEL", "0")
    summary_off, _, outdir_off = _run_one_d_case(tmp_path / "off", overrides)
    run_config_off = json.loads((outdir_off / "run_config.json").read_text(encoding="utf-8"))
    assert run_config_off["cell_parallel"]["enabled"] is False

    monkeypatch.setenv("MARSDISK_CELL_PARALLEL", "1")
    monkeypatch.setenv("MARSDISK_CELL_JOBS", "2")
    monkeypatch.setenv("MARSDISK_CELL_MIN_CELLS", "2")
    summary_on, _, outdir_on = _run_one_d_case(tmp_path / "on", overrides)
    run_config_on = json.loads((outdir_on / "run_config.json").read_text(encoding="utf-8"))
    assert run_config_on["cell_parallel"]["enabled"] is True

    for key in ("M_loss", "M_out_cum", "mass_budget_max_error_percent"):
        assert np.isclose(
            float(summary_on[key]),
            float(summary_off[key]),
            rtol=1.0e-5,
            atol=1.0e-10,
        )


def test_numba_fallback_consistency(tmp_path: Path) -> None:
    overrides = BASE_OVERRIDES

    try:
        _reload_numba_modules(disable=False)
        summary_default, _, _ = _run_one_d_case(tmp_path / "numba", overrides)

        _reload_numba_modules(disable=True)
        summary_disabled, _, _ = _run_one_d_case(tmp_path / "no_numba", overrides)
    finally:
        _reload_numba_modules(disable=False)

    for key in ("M_loss", "M_out_cum", "mass_budget_max_error_percent"):
        assert np.isclose(
            float(summary_default[key]),
            float(summary_disabled[key]),
            rtol=1.0e-5,
            atol=1.0e-10,
        )
