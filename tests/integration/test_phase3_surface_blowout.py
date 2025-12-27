import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import run, schema


def _base_surface_cfg(outdir: Path, *, s_min: float = 1.0e-6, prod_rate: float = 1.0e-9, t_end_years: float = 5.0e-4, dt_init: float = 400.0, T_M: float = 2000.0) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.5,
                r_out_RM=2.5,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=T_M),
        sizes=schema.Sizes(s_min=s_min, s_max=1.0e-2, n_bins=32),
        initial=schema.Initial(mass_total=1.0e-5, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=10.0,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
        ),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=t_end_years, dt_init=dt_init),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=prod_rate),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False, correct_fast_blowout=False),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = "smol"
    cfg.shielding = schema.Shielding(mode="off")
    return cfg


def test_blowout_inactive_when_smin_above_blowout(tmp_path: Path) -> None:
    cfg = _base_surface_cfg(tmp_path / "inactive", s_min=5.0e-3, prod_rate=5.0e-10)
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert np.allclose(df["outflux_surface"], 0.0)
    assert np.allclose(df["mass_lost_surface_solid_marsRP_step"], 0.0)
    assert np.all(df["blowout_beta_gate"] == False)  # noqa: E712


def test_surface_layer_stops_when_tau_exceeded(tmp_path: Path) -> None:
    cfg = _base_surface_cfg(tmp_path / "active", s_min=5.0e-8, prod_rate=2.5e-9, dt_init=200.0, T_M=3200.0)
    cfg.optical_depth.tau_stop = 0.5
    run.run_zero_d(cfg)

    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    assert summary["stop_reason"] == "tau_exceeded"
    assert summary["stop_tau_los"] is not None


def test_blowout_disabled_in_vapor_state(tmp_path: Path) -> None:
    cfg = _base_surface_cfg(tmp_path / "vapor", s_min=5.0e-7, prod_rate=1.0e-9, T_M=2300.0)
    cfg.phase = schema.PhaseConfig(
        enabled=True,
        source="threshold",
        thresholds=schema.PhaseThresholds(T_condense_K=1500.0, T_vaporize_K=1600.0),
    )
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert np.allclose(df["outflux_surface"], 0.0)
    assert np.all(df["blowout_phase_allowed"] == False)  # noqa: E712


def test_solar_toggle_forced_off(tmp_path: Path) -> None:
    cfg = _base_surface_cfg(tmp_path / "solar_toggle")
    cfg.radiation = schema.Radiation(TM_K=cfg.radiation.TM_K, use_mars_rp=True, use_solar_rp=True)
    run.run_zero_d(cfg)

    summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())
    solar_section = summary["solar_radiation"]
    assert solar_section["requested"] is True
    assert solar_section["enabled"] is False


def test_mass_budget_and_fast_factor_stable(tmp_path: Path) -> None:
    cfg = _base_surface_cfg(tmp_path / "stability", s_min=8.0e-7, prod_rate=1.5e-9, t_end_years=2.0, dt_init=5.0e5)
    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
    assert np.all((df["fast_blowout_factor"] >= 0.0) & (df["fast_blowout_factor"] <= 1.0))
    assert np.allclose(df["M_loss_surface_solid_marsRP"], df["mass_lost_by_blowout"])

    budget = pd.read_csv(Path(cfg.io.outdir) / "checks" / "mass_budget.csv")
    assert budget["error_percent"].abs().max() <= run.MASS_BUDGET_TOLERANCE_PERCENT + 1e-6


def test_los_shielding_reduces_phi(tmp_path: Path) -> None:
    """LOS経路を伸ばすと Φ が小さくなることを確認する。"""

    # baseline (los_factor=1)
    cfg_base = _base_surface_cfg(tmp_path / "los_base", s_min=5.0e-7, prod_rate=1.0e-9, dt_init=500.0)
    cfg_base.shielding = schema.Shielding()  # psitau, los_factor=1
    run.run_zero_d(cfg_base)

    # los stretched
    cfg_los = _base_surface_cfg(tmp_path / "los_stretched", s_min=5.0e-7, prod_rate=1.0e-9, dt_init=500.0)
    cfg_los.shielding = schema.Shielding()
    cfg_los.shielding.los_geometry.path_multiplier = 3.0  # f_los > 1
    cfg_los.shielding.los_geometry.h_over_r = 1.0
    run.run_zero_d(cfg_los)

    diag_base = pd.read_parquet(Path(cfg_base.io.outdir) / "series" / "diagnostics.parquet")
    diag_los = pd.read_parquet(Path(cfg_los.io.outdir) / "series" / "diagnostics.parquet")

    # Φ=κ_eff/κ_surf が LOS 伸長で小さくなる（同一設定で比較）
    phi_base = diag_base["phi_effective"].median()
    phi_los = diag_los["phi_effective"].median()
    assert phi_los <= phi_base + 1e-12

    # τ_los_mars が有限で非負になっていることを確認
    tau_los = diag_los["tau_los_mars"].median()
    assert np.isfinite(tau_los)
    assert tau_los >= 0.0
