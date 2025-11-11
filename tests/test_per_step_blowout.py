import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, run, schema


def _build_config(
    outdir: Path,
    *,
    dt_init: float,
    eval_per_step: bool,
) -> schema.Config:
    """Return a configuration tuned for the per-step blow-out regression tests."""

    numerics = schema.Numerics(
        t_end_years=4.0e-4,
        dt_init=dt_init,
        eval_per_step=eval_per_step,
        orbit_rollup=True,
    )
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.6 * constants.R_MARS),
        material=schema.Material(rho=3200.0),
        temps=schema.Temps(T_M=2300.0),
        sizes=schema.Sizes(s_min=8.0e-7, s_max=5.0e-3, n_bins=32),
        initial=schema.Initial(mass_total=8.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.04, i0=0.01, t_damp_orbits=25.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.6, wavy_strength=0.2),
        qstar=schema.QStar(Qs=2.0e5, a_s=0.15, B=0.35, b_g=1.3, v_ref_kms=[1.0, 2.0]),
        numerics=numerics,
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.2e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        sinks=schema.Sinks(mode="sublimation", enable_sublimation=True),
        io=schema.IO(outdir=outdir),
    )
    return cfg


def _read_orbit_loss(outdir: Path) -> pd.DataFrame:
    roll_path = Path(outdir) / "orbit_rollup.csv"
    assert roll_path.exists(), "orbit_rollup.csv missing"
    df = pd.read_csv(roll_path)
    assert not df.empty, "orbit_rollup.csv must contain at least one completed orbit"
    return df


def _max_mass_budget_error(outdir: Path) -> float:
    budget_path = Path(outdir) / "checks" / "mass_budget.csv"
    df = pd.read_csv(budget_path)
    return float(np.max(df["error_percent"].to_numpy()))


@pytest.mark.slow
def test_orbit_rollup_agrees_between_timesteps(tmp_path: Path) -> None:
    cfg_fine = _build_config(tmp_path / "fine_dt", dt_init=3.0e3, eval_per_step=True)
    cfg_coarse = _build_config(tmp_path / "coarse_dt", dt_init=1.2e4, eval_per_step=True)

    run.run_zero_d(cfg_fine)
    run.run_zero_d(cfg_coarse)

    orbit_fine = _read_orbit_loss(cfg_fine.io.outdir)
    orbit_coarse = _read_orbit_loss(cfg_coarse.io.outdir)

    loss_fine = float(orbit_fine["M_loss_orbit"].iloc[0])
    loss_coarse = float(orbit_coarse["M_loss_orbit"].iloc[0])
    assert loss_fine > 0.0
    rel_diff = abs(loss_fine - loss_coarse) / loss_fine
    assert rel_diff < 0.01

    assert _max_mass_budget_error(cfg_fine.io.outdir) <= run.MASS_BUDGET_TOLERANCE_PERCENT
    assert _max_mass_budget_error(cfg_coarse.io.outdir) <= run.MASS_BUDGET_TOLERANCE_PERCENT

    summary_fine = json.loads((Path(cfg_fine.io.outdir) / "summary.json").read_text())
    summary_coarse = json.loads((Path(cfg_coarse.io.outdir) / "summary.json").read_text())
    assert summary_fine["orbits_completed"] >= 1
    assert summary_coarse["orbits_completed"] >= 1


def test_eval_per_step_toggle_changes_loss(tmp_path: Path) -> None:
    cfg_ref = _build_config(tmp_path / "per_step_true", dt_init=1.2e4, eval_per_step=True)
    cfg_legacy = _build_config(tmp_path / "per_step_false", dt_init=1.2e4, eval_per_step=False)

    run.run_zero_d(cfg_ref)
    run.run_zero_d(cfg_legacy)

    summary_ref = json.loads((Path(cfg_ref.io.outdir) / "summary.json").read_text())
    summary_legacy = json.loads((Path(cfg_legacy.io.outdir) / "summary.json").read_text())
    ref_loss = float(summary_ref["M_loss"])
    legacy_loss = float(summary_legacy["M_loss"])
    assert ref_loss > 0.0
    rel_shift = abs(ref_loss - legacy_loss) / ref_loss
    assert rel_shift > 0.01

    assert _max_mass_budget_error(cfg_ref.io.outdir) <= run.MASS_BUDGET_TOLERANCE_PERCENT
    assert _max_mass_budget_error(cfg_legacy.io.outdir) <= run.MASS_BUDGET_TOLERANCE_PERCENT
