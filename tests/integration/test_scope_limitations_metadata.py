import json
from pathlib import Path

import pytest

from marsdisk import constants, run, schema

pytestmark = [
    pytest.mark.filterwarnings("ignore:Q_pr table not found"),
    pytest.mark.filterwarnings("ignore:Phi table not found"),
]


def _base_config(outdir: Path, *, window_years: float = 1.0e-6) -> schema.Config:
    """Return a minimal config tuned for fast runs."""

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
        scope=schema.Scope(region="inner", analysis_years=window_years),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=4000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=24),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=5.0,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
            rng_seed=9876,
            e_mode="fixed",
            i_mode="fixed",
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(
            t_end_years=window_years,
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


def test_scope_limitations_present_and_populated(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "default")

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    r_m = cfg.disk.geometry.r_in_RM * constants.R_MARS

    for payload in (summary, run_cfg):
        scope_limits = payload["scope_limitations"]
        scope = scope_limits["scope"]
        active = scope_limits["active_physics"]
        assert scope["region"] == "inner"
        assert scope["reference_radius_m"] == pytest.approx(r_m)
        assert scope["analysis_window_years"] == pytest.approx(cfg.scope.analysis_years)
        assert scope["radiation_source"] == "mars"
        assert scope["solar_radiation_enabled"] is False
        assert scope["solar_radiation_requested"] is False
        assert scope["inner_disk_scope"] is True
        assert scope["time_grid_summary"]["t_end_s"] > 0.0
        assert active["collisions_active"] is True
        assert active["rp_blowout_active"] is True
        assert active["sinks_active"] is True
        assert scope_limits["limitations"], "limitations block should not be empty"
    assert run_cfg["scope_limitations"]["limitation_codes"]


def test_single_process_flags_flow_into_scope_limitations(tmp_path: Path) -> None:
    cfg_sub = _base_config(tmp_path / "sub_only")
    cfg_sub.physics_mode = "sublimation_only"

    run.run_zero_d(cfg_sub)

    sub_summary = _read_json(cfg_sub.io.outdir / "summary.json")["scope_limitations"]["active_physics"]
    assert sub_summary["collisions_active"] is False
    assert sub_summary["rp_blowout_active"] is False
    assert sub_summary["sublimation_active"] is True

    cfg_col = _base_config(tmp_path / "collisions_only")
    cfg_col.physics_mode = "collisions_only"
    cfg_col.sinks.enable_gas_drag = True

    run.run_zero_d(cfg_col)

    col_summary = _read_json(cfg_col.io.outdir / "summary.json")["scope_limitations"]["active_physics"]
    col_config = _read_json(cfg_col.io.outdir / "run_config.json")["scope_limitations"]["active_physics"]
    assert col_summary["collisions_active"] is True
    assert col_summary["sublimation_active"] is False
    assert col_summary["sinks_active"] is False
    assert col_summary["rp_blowout_active"] is True
    assert col_config["enforce_collisions_only"] is True
    assert col_config["enforce_sublimation_only"] is False


def test_solar_radiation_request_is_recorded(tmp_path: Path) -> None:
    cfg = _base_config(tmp_path / "solar_requested")
    cfg.radiation = schema.Radiation(TM_K=4000.0, use_solar_rp=True)

    run.run_zero_d(cfg)

    scope_limits = _read_json(cfg.io.outdir / "summary.json")["scope_limitations"]["scope"]
    assert scope_limits["solar_radiation_requested"] is True
    assert scope_limits["solar_radiation_enabled"] is False
