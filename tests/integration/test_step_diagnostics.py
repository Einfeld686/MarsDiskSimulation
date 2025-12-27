from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import run, schema


def _build_config(outdir: Path, fmt: str) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.6,
                r_out_RM=2.6,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=1800.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=1.0,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
        ),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-7, dt_init=20.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(
            outdir=outdir,
            step_diagnostics=schema.StepDiagnostics(enable=True, format=fmt),
        ),
    )
    cfg.sinks.mode = "sublimation"
    cfg.sinks.enable_sublimation = True
    cfg.sinks.enable_gas_drag = True
    cfg.sinks.rho_g = 1.0e-8
    return cfg


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_step_diagnostics_file_and_mass_budget(tmp_path: Path, fmt: str) -> None:
    outdir = tmp_path / f"step_diag_{fmt}"
    cfg = _build_config(outdir, fmt)

    run.run_zero_d(cfg)

    ext = "jsonl" if fmt == "jsonl" else "csv"
    diag_path = outdir / "series" / f"step_diagnostics.{ext}"
    assert diag_path.exists(), f"Expected diagnostics file {diag_path} to be created"
    if fmt == "csv":
        df = pd.read_csv(diag_path)
    else:
        df = pd.read_json(diag_path, lines=True)
    assert not df.empty, "Diagnostics file should contain at least one row"

    required_cols = [
        "time",
        "sigma_surf",
        "tau_surf",
        "t_coll",
        "t_blow",
        "t_sink",
        "t_sink_sub",
        "t_sink_drag",
        "dM_blowout_step",
        "dM_sinks_step",
        "dM_sublimation_step",
        "dM_gas_drag_step",
        "mass_total_bins",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
    ]
    for col in required_cols:
        assert col in df.columns, f"{col} missing from diagnostics output"

    total_mass = (
        df["mass_total_bins"]
        + df["mass_lost_by_blowout"]
        + df["mass_lost_by_sinks"]
    ).to_numpy()
    assert np.allclose(
        total_mass,
        cfg.initial.mass_total,
        rtol=0.0,
        atol=1.0e-12,
    ), "Per-step mass accounting should conserve the initial mass"
