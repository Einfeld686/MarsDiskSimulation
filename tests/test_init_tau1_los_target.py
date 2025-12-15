import numpy as np
import pandas as pd
import pytest

from marsdisk import run


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_init_tau1_targets_los_tau(tmp_path) -> None:
    """init_tau1 should set Σ_tau1 so that LOS τ≈target at start."""

    outdir = tmp_path / "los_tau1"
    cfg = run.load_config(
        "configs/sweep_temp_supply/temp_supply_T4000_eps1.yml",
        overrides=[
            f"io.outdir={outdir}",
            "init_tau1.enabled=true",
            "init_tau1.scale_to_tau1=true",
            "init_tau1.tau_field=los",
            "init_tau1.target_tau=1.0",
            "supply.enabled=false",
            "numerics.t_end_years=1e-9",
            "numerics.dt_init=20",
            "shielding.mode=psitau",
        ],
    )

    run.run_zero_d(cfg)

    df = pd.read_parquet(outdir / "series" / "run.parquet")
    sigma_tau1 = df["Sigma_tau1"].iloc[0]
    tau0 = df["tau"].iloc[0]
    kappa0 = df["kappa"].iloc[0]
    los_factor = cfg.shielding.los_geometry.path_multiplier / cfg.shielding.los_geometry.h_over_r
    target_tau = cfg.init_tau1.target_tau
    expected_sigma_tau1 = target_tau / (kappa0 * los_factor)

    assert sigma_tau1 is not None
    assert np.isfinite(sigma_tau1) and sigma_tau1 > 0
    assert np.isclose(tau0, target_tau, rtol=0.1, atol=0.1)
    assert np.isclose(sigma_tau1, expected_sigma_tau1, rtol=0.1, atol=0.0)
