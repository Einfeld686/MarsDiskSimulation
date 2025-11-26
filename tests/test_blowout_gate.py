import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema


def test_compute_gate_factor_bounds() -> None:
    assert run._compute_gate_factor(10.0, 1.0) == pytest.approx(1.0 / 11.0)
    assert run._compute_gate_factor(10.0, 0.0) == 1.0
    assert run._compute_gate_factor(float("nan"), 1.0) == 1.0
    assert run._compute_gate_factor(10.0, None) == 1.0
    assert run._compute_gate_factor(None, 10.0) == 1.0


def _build_gate_config(outdir: Path, gate_mode: str) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.5 * constants.R_MARS),
        material=schema.Material(rho=1500.0),
        temps=schema.Temps(T_M=4000.0),
        sizes=schema.Sizes(s_min=5.0e-7, s_max=1.0e-2, n_bins=16),
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
        sinks=schema.Sinks(mode="sublimation", enable_sublimation=True),
        io=schema.IO(outdir=outdir, debug_sinks=False, correct_fast_blowout=False),
        blowout=schema.Blowout(gate_mode=gate_mode),
    )
    return cfg


def test_gate_reduces_outflux_with_sublimation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_none = _build_gate_config(tmp_path / "gate_none", "none")
    cfg_gate = _build_gate_config(tmp_path / "gate_active", "sublimation_competition")

    monkeypatch.setattr(run.sizes, "eval_ds_dt_sublimation", lambda T, rho, params: -1.0e-8)

    run.run_zero_d(cfg_none)
    run.run_zero_d(cfg_gate)

    df_none = pd.read_parquet(Path(cfg_none.io.outdir) / "series" / "run.parquet")
    df_gate = pd.read_parquet(Path(cfg_gate.io.outdir) / "series" / "run.parquet")

    assert df_none["blowout_gate_factor"].eq(1.0).all()
    assert df_gate["blowout_gate_factor"].max() < 1.0
    assert df_gate["M_loss_cum"].iloc[-1] < df_none["M_loss_cum"].iloc[-1]

    summary_gate = json.loads((Path(cfg_gate.io.outdir) / "summary.json").read_text())
    assert summary_gate["blowout_gate_mode"] == "sublimation_competition"


def _build_collision_config(outdir: Path, gate_mode: str) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.5 * constants.R_MARS),
        material=schema.Material(rho=1500.0),
        temps=schema.Temps(T_M=4000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-2, n_bins=24),
        initial=schema.Initial(mass_total=1.0e-6, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=10.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.6, wavy_strength=0.1),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=5.0e-4, dt_init=1.0e3),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.0e-3),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        sinks=schema.Sinks(mode="none"),
        io=schema.IO(outdir=outdir),
        blowout=schema.Blowout(gate_mode=gate_mode),
    )
    cfg.surface.use_tcoll = True
    cfg.surface.sigma_surf_init_override = 10.0
    return cfg


def test_gate_reduces_outflux_with_collisions(tmp_path: Path) -> None:
    cfg_none = _build_collision_config(tmp_path / "coll_none", "none")
    cfg_gate = _build_collision_config(tmp_path / "coll_gate", "collision_competition")

    run.run_zero_d(cfg_none)
    run.run_zero_d(cfg_gate)

    df_none = pd.read_parquet(Path(cfg_none.io.outdir) / "series" / "run.parquet")
    df_gate = pd.read_parquet(Path(cfg_gate.io.outdir) / "series" / "run.parquet")

    assert df_gate["blowout_gate_factor"].min() < 1.0
    assert df_gate["M_loss_cum"].iloc[-1] < df_none["M_loss_cum"].iloc[-1]
