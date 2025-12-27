from pathlib import Path
import json

import pandas as pd
import pytest

from marsdisk import run


def test_supply_positive_with_wide_tau_cap(tmp_path: Path) -> None:
    """Const supply remains positive when Sigma_tau1 cap is generous."""

    outdir = tmp_path / "out"
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "radiation.TM_K=6000",
            "radiation.mars_temperature_driver.table.path=data/mars_temperature_T6000p0K.csv",
            "supply.enabled=true",
            "supply.mode=const",
            "supply.const.mu_orbit10pct=1.0",
            "supply.const.orbit_fraction_at_mu1=0.10",
            "supply.mixing.epsilon_mix=1.0",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=1000",
            "optical_depth.tau_stop=1.0e6",
        ],
    )
    run.run_zero_d(cfg)
    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()
    df = pd.read_parquet(series_path, columns=["prod_subblow_area_rate"])
    assert (df["prod_subblow_area_rate"] >= 0.0).all()
    assert df["prod_subblow_area_rate"].max() > 0.0


def test_reservoir_depletes_and_records_metadata(tmp_path: Path) -> None:
    """Finite reservoir runs dry and leaves depletion metadata in outputs."""

    outdir = tmp_path / "out_reservoir"
    reservoir_mass = 1.0e-25
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "radiation.TM_K=4000",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=auto",
            "supply.enabled=true",
            "supply.mode=const",
            "supply.const.mu_orbit10pct=1.0",
            "supply.const.orbit_fraction_at_mu1=0.10",
            "supply.reservoir.enabled=true",
            f"supply.reservoir.mass_total_Mmars={reservoir_mass}",
            "supply.reservoir.depletion_mode=taper",
            "supply.reservoir.taper_fraction=0.5",
            "optical_depth.tau_stop=1.0e6",
        ],
    )
    run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    summary_path = outdir / "summary.json"
    run_config_path = outdir / "run_config.json"
    assert series_path.exists()
    assert summary_path.exists()
    assert run_config_path.exists()

    df = pd.read_parquet(series_path, columns=["prod_subblow_area_rate", "supply_reservoir_remaining_Mmars"])
    assert df["supply_reservoir_remaining_Mmars"].iloc[-1] == pytest.approx(0.0, abs=1e-18)
    assert df["prod_subblow_area_rate"].iloc[-1] <= 1e-18

    summary = json.loads(summary_path.read_text())
    assert summary["supply_reservoir_enabled"] is True
    assert summary["supply_reservoir_mass_total_Mmars"] == pytest.approx(reservoir_mass)
    assert summary["supply_reservoir_remaining_Mmars"] == pytest.approx(0.0, abs=1e-18)
    assert summary["supply_reservoir_mass_used_Mmars"] == pytest.approx(reservoir_mass, rel=0.2)
    assert summary["supply_reservoir_depletion_time_s"] is not None

    run_cfg = json.loads(run_config_path.read_text())
    supply_cfg = run_cfg["supply"]
    assert supply_cfg["reservoir_enabled"] is True
    assert supply_cfg["reservoir_mass_total_Mmars"] == pytest.approx(reservoir_mass)
    assert supply_cfg["reservoir_remaining_Mmars_final"] == pytest.approx(0.0, abs=1e-18)
    assert supply_cfg["reservoir_depletion_time_s"] is not None
    assert supply_cfg["reservoir_mass_used_Mmars"] == pytest.approx(reservoir_mass, rel=0.2)


def test_supply_feedback_tau_los_updates_scale(tmp_path: Path) -> None:
    """tau_los feedback produces finite errors and scales the supply multiplier."""

    outdir = tmp_path / "out_feedback_tau_los"
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "numerics.t_end_years=1e-5",
            "numerics.dt_init=10",
            "shielding.los_geometry.h_over_r=0.1",
            "shielding.los_geometry.path_multiplier=1.0",
            "optical_depth.tau0_target=2.0",
            "supply.feedback.enabled=true",
            "supply.feedback.target_tau=1.0",
            "supply.feedback.gain=1.0",
            "supply.feedback.response_time_years=1e-6",
            "supply.feedback.min_scale=0.1",
            "supply.feedback.max_scale=5.0",
            "supply.feedback.tau_field=tau_los",
        ],
    )
    run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()
    df = pd.read_parquet(
        series_path,
        columns=[
            "supply_feedback_error",
            "supply_feedback_scale",
            "tau_los_mars",
        ],
    )
    finite_err = df["supply_feedback_error"].dropna()
    assert not finite_err.empty
    first_idx = finite_err.index[0]
    tau_los_val = df.loc[first_idx, "tau_los_mars"]
    expected_err = (1.0 - tau_los_val) / 1.0
    assert finite_err.iloc[0] == pytest.approx(expected_err)
    scales = df["supply_feedback_scale"].dropna()
    assert (scales - 1.0).abs().max() > 1e-6


def test_mu_orbit10pct_scales_supply(tmp_path: Path) -> None:
    """mu_orbit10pct should map to a fixed dotSigma_prod using the reference tau."""

    outdir = tmp_path / "out_mu_scale"
    mu_value = 2.0
    orbit_fraction = 0.10
    cfg = run.load_config(
        Path("configs/mars_0d_supply_sweep.yaml"),
        overrides=[
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "io.streaming.enable=false",
            "numerics.t_end_orbits=1.0",
            "numerics.dt_init=auto",
            "supply.enabled=true",
            "supply.mode=const",
            f"supply.const.mu_orbit10pct={mu_value}",
            f"supply.const.orbit_fraction_at_mu1={orbit_fraction}",
            "supply.mixing.epsilon_mix=0.25",
            "supply.feedback.enabled=false",
            "supply.temperature.enabled=false",
            "surface.collision_solver=smol",
            "surface.use_tcoll=false",
            "blowout.enabled=false",
            "phase.enabled=false",
            "optical_depth.tau_stop=1.0e6",
            "sinks.mode=\"none\"",
            "sinks.enable_sublimation=false",
            "sinks.enable_gas_drag=false",
        ],
    )
    run.run_zero_d(cfg)

    df = pd.read_parquet(
        outdir / "series" / "run.parquet",
        columns=[
            "Sigma_surf",
            "Sigma_surf0",
            "dotSigma_prod",
            "dt",
            "t_orb_s",
        ],
    )
    run_config = json.loads((outdir / "run_config.json").read_text())
    sigma_ref = float(run_config["sigma_surf_mu_reference"])
    t_orb = float(df["t_orb_s"].iloc[0])
    expected_dotSigma = mu_value * orbit_fraction * sigma_ref / t_orb
    active = df["dotSigma_prod"].fillna(0.0) > 0.0
    assert active.any()
    dotSigma_measured = float(df.loc[active, "dotSigma_prod"].median())
    assert dotSigma_measured == pytest.approx(expected_dotSigma, rel=1e-3)

    delta_sigma = float(df["Sigma_surf"].iloc[-1] - df["Sigma_surf"].iloc[0])
    assert delta_sigma > 0.0


def test_run_config_written_before_runtime_failure(monkeypatch, tmp_path: Path) -> None:
    """Even when the run aborts early, the run_config snapshot is emitted."""

    outdir = tmp_path / "out_failure_config"
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
        ],
    )

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced failure for test")

    monkeypatch.setattr(run.radiation, "load_qpr_table", _boom)
    with pytest.raises(RuntimeError):
        run.run_zero_d(cfg)

    assert (outdir / "run_config.json").exists()
