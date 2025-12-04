import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import pyarrow.parquet as pq

from marsdisk import constants, run, schema


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_run_zero_d_with_sinks_disabled(tmp_path: Path) -> None:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=1.0),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.1, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-8, dt_init=1.0),
        io=schema.IO(outdir=tmp_path),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = "smol"

    run.run_zero_d(cfg)

    series_path = Path(cfg.io.outdir) / "series" / "run.parquet"
    summary_path = Path(cfg.io.outdir) / "summary.json"

    df = pd.read_parquet(series_path)
    summary = json.loads(summary_path.read_text())

    case_status = summary["case_status"]

    expected_columns = {
        "mass_lost_by_sinks",
        "mass_lost_by_blowout",
        "beta_at_smin_config",
        "beta_at_smin_effective",
        "M_sink_dot",
        "dM_dt_surface_total",
        "dt_over_t_blow",
        "fast_blowout_factor",
        "fast_blowout_flag_gt3",
        "fast_blowout_flag_gt10",
        "fast_blowout_corrected",
        "dSigma_dt_blowout",
        "dSigma_dt_sinks",
        "dSigma_dt_total",
        "n_substeps",
        "M_out_dot_avg",
        "M_sink_dot_avg",
        "dM_dt_surface_total_avg",
        "chi_blow_eff",
        "fast_blowout_factor_avg",
    }
    assert expected_columns <= set(df.columns)
    assert df["mass_lost_by_sinks"].sum() == pytest.approx(0.0, abs=1e-20)
    assert df["mass_lost_by_sinks"].eq(0.0).all()
    assert df["M_sink_dot"].eq(0.0).all()
    assert np.allclose(df["dM_dt_surface_total"], df["M_out_dot"])
    assert np.allclose(
        df["dM_dt_surface_total"],
        df["M_out_dot"] + df["M_sink_dot"],
    )
    ratio = df["dt_over_t_blow"].to_numpy()
    dt = df["dt"].to_numpy()
    t_blow = df["t_blow"].to_numpy()
    assert np.allclose(ratio, dt / t_blow)
    factor = df["fast_blowout_factor"].to_numpy()
    alias = df["fast_blowout_ratio"].to_numpy()
    assert np.all(factor >= 0.0)
    if case_status == "blowout":
        expected_factor = 1.0 - np.exp(-ratio)
        assert np.allclose(factor, expected_factor)
        np.testing.assert_allclose(alias, ratio, rtol=1e-12, atol=0.0)
        np.testing.assert_allclose(
            df["fast_blowout_factor_avg"], expected_factor, rtol=1e-6, atol=0.0
        )
    else:
        assert np.allclose(factor, 0.0)
        assert np.allclose(alias, 0.0)
        expected_factor = 1.0 - np.exp(-ratio)
        np.testing.assert_allclose(
            df["fast_blowout_factor_avg"], expected_factor, rtol=1e-6, atol=0.0
        )
    mask_gt3 = ratio > (run.FAST_BLOWOUT_RATIO_THRESHOLD + 1e-12)
    mask_gt10 = ratio > (run.FAST_BLOWOUT_RATIO_STRICT + 1e-12)
    assert np.array_equal(df["fast_blowout_flag_gt3"].to_numpy(), mask_gt3)
    assert np.array_equal(df["fast_blowout_flag_gt10"].to_numpy(), mask_gt10)
    assert df["fast_blowout_corrected"].eq(False).all()
    assert df["n_substeps"].eq(1).all()
    assert np.allclose(df["chi_blow_eff"], 1.0)

    # surface-rate to planetary-scale rate consistency
    area = math.pi * cfg.geometry.r ** 2
    dSigma_total = df["dSigma_dt_total"].to_numpy()
    dSigma_blowout = df["dSigma_dt_blowout"].to_numpy()
    dSigma_sinks = df["dSigma_dt_sinks"].to_numpy()
    np.testing.assert_allclose(dSigma_total, dSigma_blowout + dSigma_sinks, rtol=1e-12, atol=0.0)
    rate_total_final = df["dM_dt_surface_total"].to_numpy()
    expected_rate_total = dSigma_total * area / constants.M_MARS
    np.testing.assert_allclose(rate_total_final, expected_rate_total, rtol=1e-6, atol=0.0)
    rate_total_avg = df["dM_dt_surface_total_avg"].to_numpy()
    np.testing.assert_allclose(
        rate_total_avg,
        df["M_out_dot_avg"].to_numpy() + df["M_sink_dot_avg"].to_numpy(),
        rtol=1e-12,
        atol=0.0,
    )

    pq_file = pq.ParquetFile(series_path)
    metadata = pq_file.schema_arrow.metadata or {}
    assert b"units" in metadata and b"definitions" in metadata
    units = json.loads(metadata[b"units"].decode("utf-8"))
    definitions = json.loads(metadata[b"definitions"].decode("utf-8"))
    for key in ("M_sink_dot", "dM_dt_surface_total"):
        assert key in units and units[key] == "M_Mars s^-1"
        assert key in definitions
    assert units["fast_blowout_factor"] == "dimensionless"
    assert "loss fraction" in definitions["fast_blowout_factor"].lower()
    assert definitions["dM_dt_surface_total"].startswith("Total surface-layer mass-loss rate")

    required_summary_keys = {
        "s_min_components",
        "beta_at_smin_config",
        "beta_at_smin_effective",
        "beta_threshold",
        "T_M_source",
        "case_status",
    }
    assert required_summary_keys <= summary.keys()
    assert {"config", "blowout", "effective"} <= summary["s_min_components"].keys()

    expected_status = "blowout" if summary["beta_at_smin_config"] >= summary["beta_threshold"] else "ok"
    assert summary["case_status"] in {"blowout", "ok"}
    assert summary["case_status"] == expected_status
