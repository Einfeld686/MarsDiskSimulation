from __future__ import annotations

import pytest

from marsdisk.physics import supply


def test_deep_buffer_accumulates_when_headroom_zero() -> None:
    res = supply.split_supply_with_deep_buffer(
        prod_rate_raw=2.0,
        dt=1.0,
        sigma_surf=1.0,
        sigma_tau1=1.0,
        sigma_deep=0.0,
        t_mix=10.0,
        deep_enabled=True,
    )

    assert res.prod_rate_applied == pytest.approx(0.0)
    assert res.prod_rate_diverted == pytest.approx(2.0)
    assert res.sigma_deep == pytest.approx(2.0)


def test_deep_buffer_mixes_back_on_timescale() -> None:
    first = supply.split_supply_with_deep_buffer(
        prod_rate_raw=2.0,
        dt=1.0,
        sigma_surf=1.0,
        sigma_tau1=1.0,
        sigma_deep=0.0,
        t_mix=10.0,
        deep_enabled=True,
    )
    res = supply.split_supply_with_deep_buffer(
        prod_rate_raw=0.0,
        dt=1.0,
        sigma_surf=0.0,
        sigma_tau1=1.0,
        sigma_deep=first.sigma_deep,
        t_mix=2.0,
        deep_enabled=True,
    )

    assert res.prod_rate_applied == pytest.approx(1.0)
    assert res.deep_to_surf_rate == pytest.approx(1.0)
    assert res.sigma_deep == pytest.approx(1.0)
