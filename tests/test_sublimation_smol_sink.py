import json
from pathlib import Path

import pandas as pd
import pytest

from marsdisk import constants, run, schema


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_smol_sublimation_sink_mass_budget(tmp_path: Path) -> None:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.0 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=1800.0),
        sizes=schema.Sizes(s_min=1.0e-6, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=2.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-9, dt_init=1.0),
        io=schema.IO(
            outdir=tmp_path,
            step_diagnostics=schema.StepDiagnostics(enable=True),
        ),
        blowout=schema.Blowout(enabled=False),
    )
    cfg.disk = schema.Disk(geometry=schema.DiskGeometry(r_in_RM=1.5, r_out_RM=2.5, r_profile="uniform", p_index=0.0))
    cfg.inner_disk_mass = schema.InnerDiskMass(use_Mmars_ratio=True, M_in_ratio=1.0e-8)
    cfg.process.primary = "sublimation_only"
    cfg.sinks.enable_sublimation = True
    cfg.sinks.enable_gas_drag = False
    cfg.sinks.sublimation_location = "smol"
    cfg.sinks.sub_params.mode = "logistic"

    run.run_zero_d(cfg)

    series_path = Path(cfg.io.outdir) / "series" / "run.parquet"
    diag_path = Path(cfg.io.outdir) / "series" / "step_diagnostics.csv"
    summary_path = Path(cfg.io.outdir) / "summary.json"

    df = pd.read_parquet(series_path)
    step_diag = pd.read_csv(diag_path)
    summary = json.loads(summary_path.read_text())

    row = df.iloc[0]
    diag_row = step_diag.iloc[0]

    mass_loss_diag = float(diag_row["dM_sublimation_step"])
    mass_loss_series = float(row["mass_lost_sinks_step"])
    mass_lost_cum = float(row["mass_lost_by_sinks"])
    mass_drop_bins = float(cfg.initial.mass_total - row["mass_total_bins"])

    assert mass_loss_diag > 0.0
    assert mass_loss_series == pytest.approx(mass_loss_diag, rel=1e-6, abs=0.0)
    assert mass_lost_cum == pytest.approx(mass_loss_diag, rel=1e-6, abs=0.0)
    assert mass_drop_bins == pytest.approx(mass_loss_diag, rel=1e-6, abs=1e-24)
    assert float(row["mass_lost_by_blowout"]) == pytest.approx(0.0, abs=0.0)
    assert float(summary["M_loss_from_sublimation"]) >= mass_loss_diag
