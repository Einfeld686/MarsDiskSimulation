from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marsdisk import run
from marsdisk.physics import supply


def test_headroom_policy_spill_keeps_flux_nonzero() -> None:
    """spill policy keeps applying supply even when headroom is zero."""

    res_clip = supply.split_supply_with_deep_buffer(
        prod_rate_raw=1.0,
        dt=1.0,
        sigma_surf=1.0,
        sigma_tau1=1.0,
        sigma_deep=0.0,
        t_mix=None,
        deep_enabled=False,
        transport_mode="direct",
        headroom_gate="hard",
        headroom_policy="clip",
    )
    res_spill_direct = supply.split_supply_with_deep_buffer(
        prod_rate_raw=1.0,
        dt=1.0,
        sigma_surf=1.0,
        sigma_tau1=1.0,
        sigma_deep=0.0,
        t_mix=None,
        deep_enabled=False,
        transport_mode="direct",
        headroom_gate="hard",
        headroom_policy="spill",
    )
    res_spill_mixing = supply.split_supply_with_deep_buffer(
        prod_rate_raw=1.0,
        dt=1.0,
        sigma_surf=1.0,
        sigma_tau1=1.0,
        sigma_deep=0.0,
        t_mix=1.0,
        deep_enabled=True,
        transport_mode="deep_mixing",
        headroom_gate="hard",
        headroom_policy="spill",
    )

    assert res_clip.prod_rate_applied == pytest.approx(0.0)
    assert res_spill_direct.prod_rate_applied == pytest.approx(1.0)
    assert res_spill_direct.prod_rate_diverted == pytest.approx(0.0)
    assert res_spill_mixing.deep_to_surf_rate > 0.0


def test_spill_policy_runs_without_supply_drop(tmp_path: Path) -> None:
    """spill policy keeps supply_rate_applied>0 and reports spill diagnostics."""

    outdir = tmp_path / "spill_run"
    cfg = run.load_config(
        Path("configs/base.yml"),
        overrides=[
            "supply.enabled=true",
            "supply.headroom_policy=spill",
            "supply.const.prod_area_rate_kg_m2_s=10.0",
            "init_tau1.enabled=true",
            "init_tau1.scale_to_tau1=true",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=1e-2",
            "sinks.mode=\"none\"",
            "blowout.enabled=false",
            "numerics.t_end_years=1e-9",
            "numerics.dt_init=0.01",
            "io.streaming.enable=false",
            f"io.outdir={outdir}",
        ],
    )
    run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()

    cols = [
        "supply_rate_scaled",
        "supply_rate_applied",
        "supply_tau_clip_spill_rate",
        "Sigma_surf",
        "Sigma_tau1",
        "cum_mass_lost_tau_clip_spill",
    ]
    df = pd.read_parquet(series_path, columns=cols)

    assert (df["supply_rate_applied"] > 0).all()
    assert (df["Sigma_surf"] <= df["Sigma_tau1"] * 1.000001).all()
    assert df["supply_tau_clip_spill_rate"].gt(0).any()
    assert df["cum_mass_lost_tau_clip_spill"].iloc[-1] > 0
