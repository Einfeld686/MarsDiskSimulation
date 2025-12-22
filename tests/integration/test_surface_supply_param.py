import json
import math
import numpy as np
import pandas as pd
import pytest

from pathlib import Path

from marsdisk import constants, grid, run
from marsdisk.physics import collisions_smol, psd, supply
import marsdisk.schema as schema
from marsdisk.schema import (
    Config,
    Geometry,
    Disk,
    DiskGeometry,
    Material,
    Radiation,
    Sizes,
    Initial,
    Dynamics,
    PSD,
    QStar,
    Numerics,
    Supply,
    SupplyConst,
    SupplyPowerLaw,
    SupplyTable,
    SupplyMixing,
    SupplyReservoir,
    SupplyFeedback,
    SupplyTemperature,
    IO,
)


def test_const_mode():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=5.0),
        mixing=SupplyMixing(epsilon_mix=0.5),
    )
    rate = supply.get_prod_area_rate(0.0, 1.0, cfg)
    assert rate == 2.5


def test_powerlaw_mode():
    cfg = Supply(
        mode="powerlaw",
        powerlaw=SupplyPowerLaw(A_kg_m2_s=2.0, t0_s=1.0, index=-1.0),
    )
    rate = supply.get_prod_area_rate(2.0, 1.0, cfg)
    expected = 0.05 * (2.0 * ((2.0 - 1.0) + 1.0e-12) ** -1.0)
    assert rate == pytest.approx(expected)


def test_table_mode(tmp_path):
    path = tmp_path / "rate.csv"
    pd.DataFrame({"t": [0.0, 10.0], "rate": [1.0, 3.0]}).to_csv(path, index=False)
    cfg = Supply(mode="table", table=SupplyTable(path=path))
    rate = supply.get_prod_area_rate(5.0, 1.0, cfg)
    assert rate == pytest.approx(0.05 * 2.0)


def test_reservoir_caps_rate_and_consumes_mass():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=2.0),
        mixing=SupplyMixing(epsilon_mix=1.0),
        reservoir=SupplyReservoir(mass_total_Mmars=1e-23, depletion_mode="hard_stop"),
    )
    state = supply.init_runtime_state(cfg, area=1.0, seconds_per_year=1.0)
    res1 = supply.evaluate_supply(0.0, 1.0, dt=1.0, spec=cfg, area=1.0, state=state, temperature_K=1800.0)
    assert res1.rate == pytest.approx(2.0)
    res2 = supply.evaluate_supply(1.0, 1.0, dt=10.0, spec=cfg, area=1.0, state=state, temperature_K=1800.0)
    assert res2.clipped_by_reservoir
    assert res2.rate < 2.0
    assert state.reservoir_mass_remaining_kg == pytest.approx(0.0)


def test_feedback_scales_supply_toward_target_tau():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=1.0),
        mixing=SupplyMixing(epsilon_mix=1.0),
        feedback=SupplyFeedback(enabled=True, target_tau=1.0, gain=1.0, response_time_years=1.0),
    )
    state = supply.init_runtime_state(cfg, area=1.0, seconds_per_year=1.0)
    res_low_tau = supply.evaluate_supply(
        0.0, 1.0, dt=0.5, spec=cfg, area=1.0, state=state, tau_for_feedback=0.2, temperature_K=1800.0
    )
    assert res_low_tau.feedback_scale > 1.0
    res_high_tau = supply.evaluate_supply(
        0.5, 1.0, dt=0.5, spec=cfg, area=1.0, state=state, tau_for_feedback=2.0, temperature_K=1800.0
    )
    assert res_high_tau.feedback_scale < res_low_tau.feedback_scale


def test_temperature_scaling_modulates_rate():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=1.0),
        mixing=SupplyMixing(epsilon_mix=1.0),
        temperature=SupplyTemperature(enabled=True, mode="scale", reference_K=2000.0, exponent=1.0),
    )
    state = supply.init_runtime_state(cfg, area=1.0, seconds_per_year=1.0)
    res_cool = supply.evaluate_supply(0.0, 1.0, dt=1.0, spec=cfg, area=1.0, state=state, temperature_K=1000.0)
    res_hot = supply.evaluate_supply(1.0, 1.0, dt=1.0, spec=cfg, area=1.0, state=state, temperature_K=4000.0)
    assert res_hot.rate > res_cool.rate


MASS_TOL = 5e-3


def test_smol_helper_ignores_tau_clip_and_budget():
    r = constants.R_MARS
    Omega = grid.omega_kepler(r)
    psd_state = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=1.0e-3,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=16,
        rho=3000.0,
    )
    prod_rate = 5.0e-7
    dt = 25.0
    sigma_tau1 = 1.0e-4
    sigma_surf = 1.0e-2

    res = collisions_smol.step_collisions_smol_0d(
        psd_state,
        sigma_surf=sigma_surf,
        dt=dt,
        prod_subblow_area_rate=prod_rate,
        r=r,
        Omega=Omega,
        a_blow=5.0e-6,
        rho=3000.0,
        e_value=0.01,
        i_value=0.005,
        sigma_tau1=sigma_tau1,
        enable_blowout=True,
        t_sink=None,
        ds_dt_val=None,
    )

    assert res.sigma_for_step == pytest.approx(sigma_surf)
    assert res.sigma_after > 0.0
    assert math.isfinite(res.mass_error)
    assert res.mass_error <= 5e-3


def _smol_cfg(outdir: Path, *, supply_cfg: Supply) -> Config:
    cfg = Config(
        geometry=Geometry(mode="0D"),
        disk=Disk(
            geometry=DiskGeometry(
                r_in_RM=1.0,
                r_out_RM=1.0,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=Material(rho=3000.0),
        radiation=Radiation(TM_K=1800.0),
        sizes=Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=12),
        initial=Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=PSD(alpha=1.5, wavy_strength=0.0),
        qstar=QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=Numerics(t_end_years=1.0e-8, dt_init=1.0, eval_per_step=False),
        supply=supply_cfg,
        io=IO(outdir=outdir),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = "smol"
    return cfg


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_supply_modes_preserve_columns_and_budget(tmp_path: Path) -> None:
    """Smolモードで各種供給モードの出力カラムと質量収支を確認する。"""

    supply_specs = [
        Supply(mode="const", const=SupplyConst(prod_area_rate_kg_m2_s=5.0e-7)),
        Supply(
            mode="powerlaw",
            powerlaw=SupplyPowerLaw(A_kg_m2_s=1.0e-6, t0_s=0.0, index=0.0),
        ),
    ]

    path = tmp_path / "tab.csv"
    pd.DataFrame({"t": [0.0, 5.0, 10.0], "rate": [0.0, 1.0e-6, 0.0]}).to_csv(path, index=False)
    supply_specs.append(Supply(mode="table", table=SupplyTable(path=path)))

    for idx, spec in enumerate(supply_specs):
        cfg = _smol_cfg(tmp_path / f"run_{idx}", supply_cfg=spec)
        # stretch LOS for the first spec to exercise tau_los path handling
        if idx == 0:
            if cfg.shielding is None:
                cfg.shielding = schema.Shielding()
            cfg.shielding.los_geometry.path_multiplier = 2.0
            cfg.shielding.los_geometry.h_over_r = 1.0
        run.run_zero_d(cfg)

        df = pd.read_parquet(Path(cfg.io.outdir) / "series" / "run.parquet")
        budget = pd.read_csv(Path(cfg.io.outdir) / "checks" / "mass_budget.csv")
        summary = json.loads((Path(cfg.io.outdir) / "summary.json").read_text())

        # required columns exist and are finite
        required_cols = (
            "prod_subblow_area_rate",
            "M_out_dot",
            "mass_lost_by_blowout",
            "M_sink_dot",
            "tau",
            "tau_los_mars",
        )
        for col in required_cols:
            assert col in df.columns
            assert df[col].notna().all()
            assert np.isfinite(df[col]).all()

        assert budget["error_percent"].abs().max() <= 0.5
        csv_max = float(budget["error_percent"].abs().max())
        assert summary["mass_budget_max_error_percent"] >= csv_max - 1e-12

        # supply shows up in production rate (non-negative)
        assert (df["prod_subblow_area_rate"] >= 0.0).all()
