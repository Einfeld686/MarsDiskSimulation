import json
import math
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema

TOL_REL = 5e-3


def _build_config(outdir: Path, mode: str) -> schema.Config:
    """Construct a configuration for the requested diagnostic mode."""

    base_io = schema.IO(
        outdir=outdir,
        debug_sinks=False,
        correct_fast_blowout=(mode == "fast_blowout"),
    )
    numerics = schema.Numerics(
        t_end_years=5.0e-4 if mode == "fast_blowout" else 8.0e-5,
        dt_init=1.6e4 if mode == "fast_blowout" else 600.0,
    )
    supply = schema.Supply(
        mode="const",
        const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-9),
        mixing=schema.SupplyMixing(epsilon_mix=1.0),
    )

    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.5 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=5.0e-3, n_bins=24),
        initial=schema.Initial(mass_total=5.0e-6, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=10.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.1),
        qstar=schema.QStar(Qs=1.0e6, a_s=0.3, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=numerics,
        supply=supply,
        io=base_io,
    )

    if mode == "sinks_off":
        cfg.sinks.mode = "none"
        cfg.sinks.enable_sublimation = False
    elif mode == "sublimation":
        cfg.sinks.mode = "sublimation"
        cfg.sinks.enable_sublimation = True
        cfg.sinks.T_sub = 1250.0
        cfg.sinks.sub_params.alpha_evap = 0.02
        cfg.sinks.sub_params.eta_instant = 0.2
    elif mode == "fast_blowout":
        cfg.sinks.mode = "none"
        cfg.sinks.enable_sublimation = False
    else:
        raise ValueError(f"Unknown test mode {mode}")

    return cfg


@pytest.mark.parametrize(
    "mode",
    ["sinks_off", "sublimation", "fast_blowout"],
)
def test_mass_flux_integrates_to_cumulative_loss(tmp_path: Path, mode: str) -> None:
    outdir = tmp_path / mode
    cfg = _build_config(outdir, mode)
    run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()
    df = pd.read_parquet(series_path)
    assert not df.empty

    # Validate instantaneous bookkeeping
    rate_mismatch = (
        df["dM_dt_surface_total_avg"] - (df["M_out_dot_avg"] + df["M_sink_dot_avg"])
    ).abs()
    assert rate_mismatch.max() < 1e-10

    integrated = float((df["dM_dt_surface_total_avg"] * df["dt"]).sum())
    total_loss = float(df["M_loss_cum"].iloc[-1])
    assert total_loss > 0.0
    rel_err = abs(integrated - total_loss) / total_loss
    assert rel_err < TOL_REL

    blowout_loss = float(df["mass_lost_by_blowout"].iloc[-1])
    sink_loss = float(df["mass_lost_by_sinks"].iloc[-1])
    rel_err_components = abs(total_loss - (blowout_loss + sink_loss)) / total_loss
    assert rel_err_components < TOL_REL

    if mode == "fast_blowout":
        summary = json.loads((outdir / "summary.json").read_text())
        ratio = float(df["dt_over_t_blow"].iloc[-1])
        assert ratio > 3.0
        factor = float(df["fast_blowout_factor"].iloc[-1])
        expected = -math.expm1(-ratio)
        if summary["case_status"] == "blowout":
            assert factor == pytest.approx(expected, rel=1e-6)
        else:
            assert factor == pytest.approx(0.0, abs=1e-12)

    budget_path = outdir / "checks" / "mass_budget.csv"
    assert budget_path.exists()
    budget_df = pd.read_csv(budget_path)
    assert (budget_df["error_percent"] <= budget_df["tolerance_percent"] + 1e-9).all()
