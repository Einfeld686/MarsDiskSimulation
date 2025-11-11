import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, run, schema


def _build_fast_blowout_config(
    outdir: Path,
    *,
    correct: bool,
    substep: bool = False,
    substep_ratio: float = 1.0,
) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.5 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-2, n_bins=16),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=10.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=5.0e-4, dt_init=1.6e4),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-10),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(
            outdir=outdir,
            debug_sinks=False,
            correct_fast_blowout=correct,
            substep_fast_blowout=substep,
            substep_max_ratio=substep_ratio,
        ),
    )
    cfg.sinks.mode = "none"
    return cfg


def test_fast_blowout_factor_samples() -> None:
    ratios = [0.1, 1.0, 10.0]
    expected = [1.0 - math.exp(-r) for r in ratios]
    for ratio, target in zip(ratios, expected):
        value = run._fast_blowout_correction_factor(ratio)
        assert value == pytest.approx(target, rel=1e-6, abs=1e-9)


def test_fast_blowout_disabled_matches_baseline(tmp_path: Path) -> None:
    cfg = _build_fast_blowout_config(tmp_path, correct=False)

    run.run_zero_d(cfg)

    series_path = Path(cfg.io.outdir) / "series" / "run.parquet"
    df = pd.read_parquet(series_path)
    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())

    assert (df["fast_blowout_corrected"] == False).all()  # noqa: E712
    ratio = df["dt_over_t_blow"].iloc[-1]
    assert ratio > 3.0
    factor = df["fast_blowout_factor"].iloc[-1]
    expected_factor = 1.0 - math.exp(-ratio)
    if summary["case_status"] == "blowout":
        assert factor == pytest.approx(expected_factor, rel=1e-6)
        np.testing.assert_allclose(
            df["fast_blowout_ratio"], df["dt_over_t_blow"], rtol=1e-12, atol=0.0
        )
    else:
        assert factor == 0.0
        assert df["fast_blowout_ratio"].eq(0.0).all()
    omega = df["Omega_s"].iloc[-1]
    sigma = df["Sigma_surf"].iloc[-1]
    outflux = df["outflux_surface"].iloc[-1]
    assert outflux == pytest.approx(sigma * omega, rel=1e-9)
    assert "fast_blowout_factor_avg" in df.columns
    if summary["case_status"] == "blowout":
        assert df["fast_blowout_factor_avg"].iloc[-1] == pytest.approx(expected_factor, rel=1e-6)
    else:
        assert df["fast_blowout_factor_avg"].iloc[-1] == pytest.approx(expected_factor, rel=1e-6)
    assert df["n_substeps"].eq(1).all()


def test_fast_blowout_toggle_scales_outflux(tmp_path: Path) -> None:
    cfg_off = _build_fast_blowout_config(tmp_path / "off", correct=False)
    cfg_on = _build_fast_blowout_config(tmp_path / "on", correct=True)

    run.run_zero_d(cfg_off)
    run.run_zero_d(cfg_on)

    df_off = pd.read_parquet(Path(cfg_off.io.outdir) / "series" / "run.parquet")
    df_on = pd.read_parquet(Path(cfg_on.io.outdir) / "series" / "run.parquet")
    summary_off = json.loads((Path(cfg_off.io.outdir) / "summary.json").read_text())
    summary_on = json.loads((Path(cfg_on.io.outdir) / "summary.json").read_text())

    ratio = df_off["dt_over_t_blow"].to_numpy()
    ratio_on = df_on["dt_over_t_blow"].to_numpy()
    np.testing.assert_allclose(ratio_on, ratio, rtol=1e-12)
    factor = 1.0 - np.exp(-ratio)
    if summary_off["case_status"] == "blowout" and summary_on["case_status"] == "blowout":
        np.testing.assert_allclose(df_off["fast_blowout_factor"], factor, rtol=1e-6)
        np.testing.assert_allclose(df_on["fast_blowout_factor"], factor, rtol=1e-6)
        np.testing.assert_allclose(df_off["fast_blowout_ratio"], ratio, rtol=1e-12, atol=0.0)
        np.testing.assert_allclose(df_on["fast_blowout_ratio"], ratio, rtol=1e-12, atol=0.0)
        np.testing.assert_allclose(df_off["fast_blowout_factor_avg"], factor, rtol=1e-6)
        np.testing.assert_allclose(df_on["fast_blowout_factor_avg"], factor, rtol=1e-6)
    else:
        assert np.allclose(df_off["fast_blowout_factor"], 0.0)
        assert np.allclose(df_on["fast_blowout_factor"], 0.0)
        assert np.allclose(df_off["fast_blowout_ratio"], 0.0)
        assert np.allclose(df_on["fast_blowout_ratio"], 0.0)
        np.testing.assert_allclose(df_off["fast_blowout_factor_avg"], factor, rtol=1e-6)
        np.testing.assert_allclose(df_on["fast_blowout_factor_avg"], factor, rtol=1e-6)

    mask_gt3 = ratio > (run.FAST_BLOWOUT_RATIO_THRESHOLD + 1e-9)
    mask_gt10 = ratio > (run.FAST_BLOWOUT_RATIO_STRICT + 1e-9)

    assert np.all(~df_off["fast_blowout_corrected"].to_numpy())
    assert np.array_equal(df_on["fast_blowout_corrected"].to_numpy(), mask_gt3)
    assert np.array_equal(df_off["fast_blowout_flag_gt3"].to_numpy(), mask_gt3)
    assert np.array_equal(df_on["fast_blowout_flag_gt3"].to_numpy(), mask_gt3)
    assert np.array_equal(df_off["fast_blowout_flag_gt10"].to_numpy(), mask_gt10)
    assert np.array_equal(df_on["fast_blowout_flag_gt10"].to_numpy(), mask_gt10)

    scale = np.where(mask_gt3, factor, 1.0)
    np.testing.assert_allclose(df_on["outflux_surface"], df_off["outflux_surface"] * scale, rtol=1e-6)
    np.testing.assert_allclose(df_on["M_out_dot"].to_numpy(), df_off["M_out_dot"].to_numpy() * scale, rtol=1e-6)

    dt = df_off["dt"].to_numpy()
    expected_cum = np.cumsum(df_off["M_out_dot"].to_numpy() * scale * dt)
    rel_diff_cum = abs(df_on["M_loss_cum"].iloc[-1] - expected_cum[-1]) / abs(expected_cum[-1])
    assert rel_diff_cum < 0.05
    rel_diff_blow = abs(df_on["mass_lost_by_blowout"].iloc[-1] - expected_cum[-1]) / abs(expected_cum[-1])
    assert rel_diff_blow < 0.05
    np.testing.assert_allclose(df_on["mass_lost_by_sinks"].to_numpy(), 0.0, atol=1e-20)
    np.testing.assert_allclose(df_off["mass_lost_by_sinks"].to_numpy(), 0.0, atol=1e-20)

    for column in ("Sigma_surf", "Sigma_tau1", "tau", "s_min"):
        np.testing.assert_allclose(
            df_on[column].to_numpy(),
            df_off[column].to_numpy(),
            rtol=1e-9,
            atol=1e-12,
            equal_nan=True,
        )

    assert df_off["n_substeps"].eq(1).all()
    assert df_on["n_substeps"].eq(1).all()


def test_fast_blowout_substepping_matches_correction(tmp_path: Path) -> None:
    cfg_correct = _build_fast_blowout_config(tmp_path / "correct", correct=True)
    cfg_sub = _build_fast_blowout_config(
        tmp_path / "substep",
        correct=True,
        substep=True,
        substep_ratio=1.0,
    )

    run.run_zero_d(cfg_correct)
    run.run_zero_d(cfg_sub)

    df_correct = pd.read_parquet(Path(cfg_correct.io.outdir) / "series" / "run.parquet")
    df_sub = pd.read_parquet(Path(cfg_sub.io.outdir) / "series" / "run.parquet")

    loss_correct = float(df_correct["M_loss_cum"].iloc[-1])
    loss_sub = float(df_sub["M_loss_cum"].iloc[-1])
    assert loss_correct > 0.0
    rel_diff = abs(loss_correct - loss_sub) / loss_correct
    assert rel_diff < 0.05

    assert df_correct["n_substeps"].eq(1).all()
    assert df_sub["n_substeps"].max() > 1
    assert "fast_blowout_factor_avg" in df_sub.columns


def test_chi_blow_auto_range(tmp_path: Path) -> None:
    cfg = _build_fast_blowout_config(tmp_path / "auto", correct=False)
    cfg.chi_blow = "auto"
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    chi_series = df["chi_blow_eff"].to_numpy()
    assert np.all(chi_series >= 0.5)
    assert np.all(chi_series <= 2.0)
    assert 0.5 <= float(summary["chi_blow_eff"]) <= 2.0
