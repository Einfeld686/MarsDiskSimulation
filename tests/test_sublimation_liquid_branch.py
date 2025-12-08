from __future__ import annotations

import math

from marsdisk.physics import sublimation


def test_p_sat_switches_to_liquid_branch() -> None:
    params = sublimation.SublimationParams(
        mode="hkl",
        psat_model="clausius",
        enable_liquid_branch=True,
        psat_liquid_switch_K=1900.0,
    )

    T_solid = 1600.0
    P_solid = sublimation.p_sat(T_solid, params)
    meta_solid = params._psat_last_selection or {}
    assert meta_solid.get("psat_branch") == "solid"
    assert math.isclose(P_solid, 10 ** (params.A - params.B / T_solid), rel_tol=1e-12)

    T_liquid = 2200.0
    P_liquid = sublimation.p_sat(T_liquid, params)
    meta_liquid = params._psat_last_selection or {}
    assert meta_liquid.get("psat_branch") == "liquid"
    expected_liquid = 10 ** (params.A_liq - params.B_liq / T_liquid)
    assert math.isclose(P_liquid, expected_liquid, rel_tol=1e-12)
