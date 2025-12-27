import json
import numpy as np
import pandas as pd
import pytest

from marsdisk import run
from marsdisk import run_zero_d


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_optical_depth_targets_los_tau(tmp_path) -> None:
    """optical_depth should set Sigma_surf0 so that LOS τ≈tau0_target at start."""

    outdir = tmp_path / "los_tau1"
    cfg = run.load_config(
        "configs/sweep_temp_supply/temp_supply_T4000_eps1.yml",
        overrides=[
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "optical_depth.tau0_target=1.0",
            "supply.enabled=false",
            "numerics.t_end_years=1e-9",
            "numerics.dt_init=20",
            "shielding.mode=psitau",
        ],
    )

    run.run_zero_d(cfg)

    df = pd.read_parquet(outdir / "series" / "run.parquet")
    sigma0 = df["Sigma_surf0"].iloc[0]
    run_cfg = json.loads((outdir / "run_config.json").read_text())
    kappa_eff0 = run_cfg["optical_depth"]["kappa_eff0"]
    los_factor = run_zero_d._resolve_los_factor(cfg.shielding.los_geometry)
    target_tau = cfg.optical_depth.tau0_target
    expected_sigma0 = target_tau / (kappa_eff0 * los_factor)

    assert sigma0 is not None
    assert np.isfinite(sigma0) and sigma0 > 0
    assert np.isclose(sigma0, expected_sigma0, rtol=0.1, atol=0.0)
