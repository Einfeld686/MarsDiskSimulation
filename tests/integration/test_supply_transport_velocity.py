from __future__ import annotations

from math import sqrt
from pathlib import Path

import pandas as pd
from pandas.api.types import is_bool_dtype
import pytest

from marsdisk import run
from marsdisk.physics import collisions_smol, supply


def test_supply_velocity_blend_and_weight() -> None:
    """Effective e/i follow the configured blend and weight modes."""

    e_base, i_base = 0.1, 0.05
    e_sup, i_sup = 0.2, 0.1
    e_rms, i_rms = collisions_smol._blend_supply_velocity(e_base, i_base, e_sup, i_sup, weight=0.5, mode="rms")
    assert e_rms == pytest.approx(sqrt(0.5 * e_base**2 + 0.5 * e_sup**2))
    assert i_rms == pytest.approx(sqrt(0.5 * i_base**2 + 0.5 * i_sup**2))

    weight_delta = collisions_smol._supply_velocity_weight(delta_sigma=2.0, sigma_prev=8.0, mode="delta_sigma")
    weight_ratio = collisions_smol._supply_velocity_weight(delta_sigma=2.0, sigma_prev=8.0, mode="sigma_ratio")
    assert weight_delta == pytest.approx(0.2)
    assert weight_ratio == pytest.approx(0.25)


def test_deep_mixing_transport_routes_via_deep_buffer() -> None:
    """deep_mixing sends raw supply into deep and mixes back on t_mix."""

    res = supply.split_supply_with_deep_buffer(
        prod_rate_raw=1.0,
        dt=1.0,
        sigma_surf=0.0,
        sigma_tau1=None,
        sigma_deep=0.0,
        t_mix=2.0,
        deep_enabled=True,
        transport_mode="deep_mixing",
    )

    assert res.prod_rate_into_deep == pytest.approx(1.0)
    assert res.deep_to_surf_rate == pytest.approx(0.5)
    assert res.prod_rate_diverted == pytest.approx(0.5)
    assert res.sigma_deep == pytest.approx(0.5)


def test_run_outputs_supply_visibility_columns(tmp_path: Path) -> None:
    """run.parquet carries new supply diagnostics and kernel velocity columns."""

    outdir = tmp_path / "out_vis"
    cfg = run.load_config(
        Path("configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"),
        overrides=[
            "numerics.t_end_years=1e-6",
            "numerics.dt_init=1",
            f"io.outdir={outdir}",
            "dynamics.e_profile.mode=off",
            "radiation.TM_K=4000",
            "shielding.mode=fixed_tau1",
            "shielding.fixed_tau1_sigma=auto",
            "supply.transport.mode=deep_mixing",
            "supply.transport.t_mix_orbits=0.5",
            "supply.injection.velocity.mode=fixed_ei",
            "supply.injection.velocity.e_inj=0.2",
            "supply.injection.velocity.i_inj=0.1",
            "supply.injection.velocity.blend_mode=linear",
        ],
    )
    with pytest.warns(DeprecationWarning, match="External supply configuration deviates"):
        run.run_zero_d(cfg)

    series_path = outdir / "series" / "run.parquet"
    diag_path = outdir / "series" / "diagnostics.parquet"
    assert series_path.exists()
    assert diag_path.exists()

    df_series = pd.read_parquet(
        series_path,
        columns=[
            "supply_visibility_factor",
            "supply_blocked_by_headroom",
            "supply_mixing_limited",
            "prod_rate_into_deep",
            "deep_to_surf_flux_attempt",
            "deep_to_surf_flux_applied",
            "e_kernel_base",
            "e_kernel_supply",
            "e_kernel_effective",
            "supply_velocity_weight_w",
        ],
    )
    assert df_series["supply_visibility_factor"].notna().any()
    assert set(df_series.columns).issuperset({"e_kernel_base", "e_kernel_effective"})

    df_diag = pd.read_parquet(
        diag_path,
        columns=["supply_transport_mode", "deep_to_surf_flux_attempt", "supply_mixing_limited"],
    )
    assert (df_diag["supply_transport_mode"] == "deep_mixing").any()
    assert df_diag["deep_to_surf_flux_attempt"].notna().any()
    assert is_bool_dtype(df_diag["supply_mixing_limited"])
