import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema

pytestmark = [
    pytest.mark.filterwarnings("ignore:Q_pr table not found"),
    pytest.mark.filterwarnings("ignore:Phi table not found"),
]


def _scenario_config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=1.3,
                r_out_RM=1.3,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=4000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=24),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=5.0,
            f_wake=1.0,
            rng_seed=9876,
            e_mode="fixed",
            i_mode="fixed",
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(
            t_end_years=1.0e-6,
            dt_init=1.0,
            eval_per_step=False,
            orbit_rollup=False,
        ),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.0e-5),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False),
    )
    cfg.sinks.mode = "sublimation"
    cfg.sinks.enable_sublimation = True
    cfg.sinks.enable_gas_drag = False
    return cfg


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_sublimation_only_disables_collisions_and_blowout(tmp_path: Path) -> None:
    cfg = _scenario_config(tmp_path / "sub_only")
    cfg.physics_mode = "sublimation_only"

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    series = pd.read_parquet(cfg.io.outdir / "series" / "run.parquet")

    assert summary["primary_scenario"] == "sublimation_only"
    assert summary["collisions_active"] is False
    assert summary["blowout_active"] is False
    assert summary["sinks_active"] is True
    assert summary["M_loss_from_sinks"] > 0.0
    assert series["M_out_dot"].max() == 0.0
    assert series["mass_lost_by_blowout"].max() == 0.0
    assert run_cfg["process_controls"]["collisions_active"] is False
    assert run_cfg["process_controls"]["sinks_active"] is True


def test_collisions_only_disables_sinks(tmp_path: Path) -> None:
    cfg = _scenario_config(tmp_path / "collisions_only")
    cfg.physics_mode = "collisions_only"
    cfg.sinks.enable_gas_drag = True

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    series = pd.read_parquet(cfg.io.outdir / "series" / "run.parquet")

    assert summary["primary_scenario"] == "collisions_only"
    assert summary["sinks_active"] is False
    assert summary["sublimation_active"] is False
    assert summary["blowout_active"] is True
    assert summary["M_loss_from_sinks"] == pytest.approx(0.0)
    assert summary["M_loss_from_sublimation"] == pytest.approx(0.0)
    assert series["mass_lost_by_sinks"].max() == 0.0
    assert series["M_out_dot"].max() > 0.0
    assert run_cfg["process_controls"]["collisions_active"] is True
    assert run_cfg["process_controls"]["sinks_active"] is False


def test_combined_mode_keeps_both_channels(tmp_path: Path) -> None:
    cfg = _scenario_config(tmp_path / "combined")

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    series = pd.read_parquet(cfg.io.outdir / "series" / "run.parquet")

    assert summary["primary_scenario"] == "combined"
    assert summary["collisions_active"] is True
    assert summary["sinks_active"] is True
    assert summary["blowout_active"] is True
    assert summary["M_loss"] == pytest.approx(
        summary["M_loss_from_sinks"] + summary["M_loss_rp_mars"], rel=1e-6
    )
    assert series["mass_lost_by_blowout"].iloc[-1] > 0.0
    assert series["mass_lost_by_sinks"].iloc[-1] > 0.0
    assert run_cfg["process_controls"]["primary_scenario"] == "combined"
    assert run_cfg["process_controls"]["sinks_active"] is True
