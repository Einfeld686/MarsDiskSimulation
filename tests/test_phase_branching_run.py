from __future__ import annotations

from pathlib import Path

import pandas as pd

from marsdisk import constants, run, schema


def _build_phase_config(outdir: Path, *, T_M: float) -> schema.Config:
    numerics = schema.Numerics(t_end_years=2.0e-4, dt_init=2.0e3, eval_per_step=True)
    phase_cfg = schema.PhaseConfig(
        enabled=True,
        source="threshold",
        thresholds=schema.PhaseThresholds(T_condense_K=1500.0, T_vaporize_K=1750.0, tau_ref=1.0),
    )
    hydro_cfg = schema.HydroEscapeConfig(enable=True, strength=5.0e-5, temp_power=1.0, T_ref_K=T_M)
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.6 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=T_M),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0, n_bins=24),
        initial=schema.Initial(mass_total=2.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=15.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.1),
        qstar=schema.QStar(Qs=2.0e6, a_s=0.3, B=0.2, b_g=1.2, v_ref_kms=[1.0, 2.0]),
        phase=phase_cfg,
        numerics=numerics,
        sinks=schema.Sinks(
            mode="sublimation",
            enable_sublimation=False,
            rp_blowout=schema.RPBlowoutConfig(enable=True),
            hydro_escape=hydro_cfg,
        ),
        radiation=schema.Radiation(source="mars", TM_K=T_M, qpr_table_path=Path("data/qpr_table.csv")),
        io=schema.IO(outdir=outdir, debug_sinks=False),
    )
    return cfg


def _load_run(outdir: Path) -> pd.DataFrame:
    path = Path(outdir) / "series" / "run.parquet"
    assert path.exists(), "run.parquet missing"
    return pd.read_parquet(path)


def test_sink_selection_is_mutually_exclusive(tmp_path: Path) -> None:
    cfg_vapor = _build_phase_config(tmp_path / "vapor_case", T_M=1900.0)
    cfg_solid = _build_phase_config(tmp_path / "solid_case", T_M=1600.0)

    run.run_zero_d(cfg_vapor)
    run.run_zero_d(cfg_solid)

    df_vapor = _load_run(cfg_vapor.io.outdir)
    df_solid = _load_run(cfg_solid.io.outdir)
    combined = pd.concat([df_vapor, df_solid], ignore_index=True)

    assert set(combined["sink_selected"].unique()).issubset({"rp_blowout", "hydro_escape", "none"})
    assert not ((combined["phase_state"] == "solid") & (combined["sink_selected"] == "hydro_escape")).any()
    assert not ((combined["phase_state"] == "vapor") & (combined["sink_selected"] == "rp_blowout")).any()
    hydro_mask = combined["sink_selected"] == "hydro_escape"
    assert not (hydro_mask & (combined["M_out_dot"] > 0.0)).any()
    assert not (
        (combined["sink_selected"] == "rp_blowout") & (combined["mass_lost_hydro_step"] > 0.0)
    ).any()
