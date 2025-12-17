import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema

pytestmark = [
    pytest.mark.filterwarnings("ignore:Q_pr table not found"),
    pytest.mark.filterwarnings("ignore:Phi table not found"),
]


def _phase9_config(
    outdir: Path,
    *,
    analysis_years: float = 2.0,
    t_end_years: float | None = 1.0e-6,
    dt_init: float = 1.0,
    prod_area_rate: float = 1.0e-3,
) -> schema.Config:
    cfg = schema.Config(
        scope=schema.Scope(region="inner", analysis_years=analysis_years),
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
        initial=schema.Initial(mass_total=1.0e-6, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=5.0,
            f_wake=1.0,
            rng_seed=2025,
            e_mode="fixed",
            i_mode="fixed",
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(
            t_end_years=t_end_years,
            dt_init=dt_init,
            eval_per_step=False,
            orbit_rollup=False,
        ),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=prod_area_rate),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False),
    )
    cfg.sinks.mode = "sublimation"
    cfg.sinks.enable_sublimation = True
    cfg.sinks.enable_gas_drag = False
    cfg.surface.collision_solver = "surface_ode"
    return cfg


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_sublimation_only_zeroes_blowout_flux_and_sets_metadata(tmp_path: Path) -> None:
    cfg = _phase9_config(tmp_path / "sub_only")
    cfg.physics_mode = "sublimation_only"

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    series = pd.read_parquet(cfg.io.outdir / "series" / "run.parquet")

    assert summary["primary_process"] == "sublimation_only"
    assert summary["collisions_active"] is False
    assert summary["blowout_active"] is False
    assert series["M_out_dot"].abs().max() == 0.0
    assert series["mass_lost_by_blowout"].max() == 0.0
    assert run_cfg["process_controls"]["primary_process"] == "sublimation_only"
    assert run_cfg["process_controls"]["collisions_active"] is False
    assert run_cfg["process_overview"]["blowout_active"] is False
    assert run_cfg["solar_radiation"]["enabled"] is False


def test_collisions_only_enables_blowout_and_disables_sinks(tmp_path: Path) -> None:
    cfg = _phase9_config(tmp_path / "collisions_only")
    cfg.physics_mode = "collisions_only"
    cfg.sinks.enable_gas_drag = True

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")
    series = pd.read_parquet(cfg.io.outdir / "series" / "run.parquet")

    assert summary["primary_process"] == "collisions_only"
    assert summary["collisions_active"] is True
    assert summary["sinks_active"] is False
    assert summary["blowout_active"] is True
    assert summary["M_loss_from_sinks"] == pytest.approx(0.0)
    assert series["mass_lost_by_sinks"].max() == 0.0
    assert summary["case_status"] == "blowout"
    assert run_cfg["process_controls"]["sinks_active"] is False
    assert run_cfg["process_controls"]["blowout_active"] is True
    assert run_cfg["solar_radiation"]["enabled"] is False


def test_scope_region_guard_rejects_outer_disk(tmp_path: Path) -> None:
    cfg = _phase9_config(tmp_path / "bad_scope")
    cfg.scope.region = "outer"  # type: ignore[assignment]

    with pytest.raises(ValueError, match="scope.region must be 'inner'"):
        run.run_zero_d(cfg)


def test_analysis_window_defaults_to_scope_when_t_end_missing(tmp_path: Path) -> None:
    cfg = _phase9_config(
        tmp_path / "analysis_window",
        analysis_years=2.0,
        t_end_years=None,
        dt_init=5.0e6,
        prod_area_rate=0.0,
    )
    cfg.physics_mode = "collisions_only"
    cfg.sinks.mode = "none"

    run.run_zero_d(cfg)

    summary = _read_json(cfg.io.outdir / "summary.json")
    run_cfg = _read_json(cfg.io.outdir / "run_config.json")

    expected_t_end = pytest.approx(cfg.scope.analysis_years * run.SECONDS_PER_YEAR)
    assert summary["analysis_window_years"] == pytest.approx(cfg.scope.analysis_years)
    assert summary["time_grid"]["basis"] == "t_end_years"
    assert summary["time_grid"]["t_end_s"] == expected_t_end
    assert run_cfg["scope_controls"]["analysis_window_years"] == pytest.approx(
        cfg.scope.analysis_years
    )
    assert run_cfg["time_grid"]["t_end_basis"] == "t_end_years"
    assert run_cfg["time_grid"]["t_end_s"] == expected_t_end
    assert run_cfg["scope_controls"]["inner_disk_scope"] is True
    assert run_cfg["radiation_provenance"]["use_solar_rp"] is False


def test_mass_loss_is_comparable_between_solo_runs(tmp_path: Path) -> None:
    base_kwargs = dict(t_end_years=2.0e-6, dt_init=1.0, prod_area_rate=1.0e-3)

    cfg_sub = _phase9_config(tmp_path / "sub_run", **base_kwargs)
    cfg_sub.physics_mode = "sublimation_only"
    run.run_zero_d(cfg_sub)

    cfg_col = _phase9_config(tmp_path / "coll_run", **base_kwargs)
    cfg_col.physics_mode = "collisions_only"
    run.run_zero_d(cfg_col)

    sub_summary = _read_json(cfg_sub.io.outdir / "summary.json")
    col_summary = _read_json(cfg_col.io.outdir / "summary.json")
    sub_cfg = _read_json(cfg_sub.io.outdir / "run_config.json")
    col_cfg = _read_json(cfg_col.io.outdir / "run_config.json")

    assert col_summary["case_status"] == "blowout"
    assert sub_summary["case_status"] != "blowout"
    assert col_summary["blowout_active"] is True
    assert sub_summary["blowout_active"] is False
    assert sub_summary["primary_process"] == "sublimation_only"
    assert col_summary["primary_process"] == "collisions_only"
    assert sub_summary["radiation_field"] == "mars"
    assert col_summary["radiation_field"] == "mars"
    assert sub_cfg["time_grid"]["t_end_s"] == pytest.approx(
        col_cfg["time_grid"]["t_end_s"]
    )
    assert sub_cfg["process_controls"]["primary_process"] == "sublimation_only"
    assert col_cfg["process_controls"]["primary_process"] == "collisions_only"

    cfg_col_repeat = _phase9_config(tmp_path / "coll_run_repeat", **base_kwargs)
    cfg_col_repeat.physics_mode = "collisions_only"
    run.run_zero_d(cfg_col_repeat)
    col_repeat = _read_json(cfg_col_repeat.io.outdir / "summary.json")

    assert col_repeat["M_loss"] == pytest.approx(col_summary["M_loss"])
