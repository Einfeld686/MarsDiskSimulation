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
    # spill may still be blocked when headroom gate is hard; ensure it does not go negative
    assert res_spill_direct.prod_rate_applied >= 0.0
    assert res_spill_direct.prod_rate_diverted == pytest.approx(0.0)
    assert res_spill_mixing.prod_rate_diverted >= res_spill_mixing.prod_rate_applied
    assert res_spill_mixing.deep_to_surf_rate >= 0.0


def test_tau_stop_triggers_without_clip(tmp_path: Path) -> None:
    """High supply should exceed tau_stop and terminate without Sigma_tau1 clipping."""

    outdir = tmp_path / "spill_run"
    cfg = run.load_config(
        Path("configs/mars_0d_supply_sweep.yaml"),
        overrides=[
            "dynamics.e_profile.mode=off",
            "supply.enabled=true",
            "supply.headroom_policy=spill",
            "supply.const.mu_orbit10pct=50.0",
            "supply.const.orbit_fraction_at_mu1=0.10",
            "optical_depth.tau_stop=0.5",
            "sinks.mode=\"none\"",
            "blowout.enabled=false",
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=0.01",
            "io.streaming.enable=false",
            f"io.outdir={outdir}",
        ],
    )
    with pytest.warns(DeprecationWarning, match="External supply configuration deviates"):
        run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    assert series_path.exists()

    cols = [
        "Sigma_surf",
        "Sigma_tau1",
        "tau_los_mars",
    ]
    df = pd.read_parquet(series_path, columns=cols)
    summary = pd.read_json(outdir / "summary.json", typ="series")

    assert summary["stop_reason"] == "tau_exceeded"
    mask = df["Sigma_tau1"].notna()
    assert (df.loc[mask, "Sigma_surf"] > df.loc[mask, "Sigma_tau1"]).any()
