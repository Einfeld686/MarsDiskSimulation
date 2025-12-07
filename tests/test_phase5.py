import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema


def _phase5_base_config(outdir: Path) -> schema.Config:
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
        radiation=schema.Radiation(TM_K=2000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=16),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=5.0,
            f_wake=1.0,
            rng_seed=54321,
            e_mode="fixed",
            i_mode="fixed",
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(
            t_end_years=1.0e-7,
            dt_init=1.0,
            eval_per_step=False,
            orbit_rollup=False,
        ),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=0.0),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False),
    )
    cfg.sinks.mode = "none"
    cfg.phase5.compare.mode_a = "collisions_only"
    cfg.phase5.compare.mode_b = "sublimation_only"
    cfg.phase5.compare.label_a = "collisions"
    cfg.phase5.compare.label_b = "sublimation"
    return cfg


def _read_summary(outdir: Path) -> dict:
    with (outdir / "summary.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_run_config(outdir: Path) -> dict:
    with (outdir / "run_config.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_collisions_only_disables_sinks(tmp_path: Path) -> None:
    cfg = _phase5_base_config(tmp_path / "collisions")
    cfg.sinks.mode = "sublimation"
    cfg.sinks.enable_sublimation = True
    cfg.physics_mode = "collisions_only"

    run.run_zero_d(cfg)
    summary = _read_summary(cfg.io.outdir)
    run_cfg = _read_run_config(cfg.io.outdir)

    assert summary["M_loss_from_sinks"] == pytest.approx(0.0)
    assert summary["M_loss_from_sublimation"] == pytest.approx(0.0)
    assert summary["physics_mode"] == "collisions_only"
    assert summary["physics_mode_source"] == "config"
    assert run_cfg["physics_mode"] == "collisions_only"
    assert run_cfg["physics_mode_resolution"]["resolved_mode"] == "collisions_only"
    assert run_cfg["physics_mode_resolution"]["source"] == "config"


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_phase5_comparison_outputs_combined_series(tmp_path: Path) -> None:
    outdir = tmp_path / "phase5_compare"
    cfg = _phase5_base_config(outdir)
    cfg.phase5.compare.enable = True
    cfg.phase5.compare.duration_years = cfg.numerics.t_end_years

    run.run_phase5_comparison(cfg)

    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()
    df = pd.read_parquet(series_path)
    assert set(df["variant"].unique()) == {"sublimation", "collisions"}

    summary = _read_summary(outdir)
    compare_block = summary["phase5"]["compare"]
    assert compare_block["enabled"] is True
    assert {entry["variant"] for entry in compare_block["variants"]} == {
        "sublimation",
        "collisions",
    }
    assert summary.get("comparison_mode") == "phase5_physics_modes"

    comp_csv = outdir / "series" / "orbit_rollup_comparison.csv"
    assert comp_csv.exists()
    comp_df = pd.read_csv(comp_csv)
    assert set(comp_df["variant"]) == {"sublimation", "collisions"}


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_variant_column_absent_when_not_comparing(tmp_path: Path) -> None:
    cfg = _phase5_base_config(tmp_path / "no_compare")
    cfg.phase5.compare.enable = False

    run.run_zero_d(cfg)

    series_path = Path(cfg.io.outdir) / "series" / "run.parquet"
    df = pd.read_parquet(series_path)
    assert "variant" not in df.columns


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_physics_mode_config_applies(tmp_path: Path) -> None:
    cfg = _phase5_base_config(tmp_path / "physics_mode_cfg")
    cfg.physics_mode = "collisions_only"

    run.run_zero_d(cfg)
    summary = _read_summary(cfg.io.outdir)
    run_cfg = _read_run_config(cfg.io.outdir)

    assert summary["physics_mode"] == "collisions_only"
    assert summary["physics_mode_source"] == "config"
    assert summary["physics"]["mode"] == "collisions_only"
    assert summary["physics"]["source"] == "config"
    assert run_cfg["physics_mode"] == "collisions_only"
    assert run_cfg["physics_mode_source"] == "config"
    assert run_cfg["physics_mode_resolution"]["resolved_mode"] == "collisions_only"
    assert run_cfg["physics_mode_resolution"]["source"] == "config"


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_cli_override_wins_over_config(tmp_path: Path) -> None:
    cfg = _phase5_base_config(tmp_path / "cli_override")
    cfg.physics_mode = "sublimation_only"
    run.run_zero_d(
        cfg,
        physics_mode_override="collisions_only",
        physics_mode_source_override="cli",
    )
    summary = _read_summary(cfg.io.outdir)
    run_cfg = _read_run_config(cfg.io.outdir)

    assert summary["physics_mode"] == "collisions_only"
    assert summary["physics_mode_source"] == "cli"
    assert summary["physics"]["mode"] == "collisions_only"
    assert summary["physics"]["source"] == "cli"
    assert run_cfg["physics_mode"] == "collisions_only"
    assert run_cfg["physics_mode_source"] == "cli"
    assert run_cfg["physics_mode_resolution"]["resolved_mode"] == "collisions_only"
    assert run_cfg["physics_mode_resolution"]["source"] == "cli"
