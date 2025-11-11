import math

import pytest

from marsdisk import constants
from marsdisk.physics.fragments import s_sub_boundary
from marsdisk.physics.sinks import SinkOptions, total_sink_timescale
from marsdisk.physics.sublimation import (
    SublimationParams,
    grain_temperature_graybody,
    s_sink_from_timescale,
)


def _kepler_omega(radius_m: float) -> float:
    return math.sqrt(constants.G * constants.M_MARS / radius_m**3)


def _make_params(**overrides) -> SublimationParams:
    params = SublimationParams(
        mode="hkl",
        alpha_evap=0.6,
        mu=0.04,
        A=12.5,
        B=5200.0,
        P_gas=0.0,
    )
    for key, value in overrides.items():
        setattr(params, key, value)
    return params


def test_s_sub_increases_towards_planet():
    T_M = 2200.0
    T_sub = 800.0
    rho = 3000.0

    r_inner = 1.5 * constants.R_MARS
    r_outer = 2.5 * constants.R_MARS

    Omega_inner = _kepler_omega(r_inner)
    Omega_outer = _kepler_omega(r_outer)
    t_inner = 2.0 * math.pi / Omega_inner
    t_outer = 2.0 * math.pi / Omega_outer

    params_inner = _make_params()
    setattr(params_inner, "runtime_orbital_radius_m", r_inner)
    params_outer = _make_params()
    setattr(params_outer, "runtime_orbital_radius_m", r_outer)

    s_sub_inner = s_sub_boundary(
        T_M,
        T_sub,
        t_ref=t_inner,
        rho=rho,
        sub_params=params_inner,
    )
    s_sub_outer = s_sub_boundary(
        T_M,
        T_sub,
        t_ref=t_outer,
        rho=rho,
        sub_params=params_outer,
    )

    assert s_sub_inner > s_sub_outer > 0.0


def test_s_sub_scales_with_alpha():
    T_M = 2100.0
    T_sub = 750.0
    rho = 2800.0
    r = 2.0 * constants.R_MARS
    Omega = _kepler_omega(r)
    t_orb = 2.0 * math.pi / Omega

    params_low = _make_params(alpha_evap=0.2)
    params_high = _make_params(alpha_evap=0.9)
    for params in (params_low, params_high):
        setattr(params, "runtime_orbital_radius_m", r)

    s_low = s_sub_boundary(
        T_M,
        T_sub,
        t_ref=t_orb,
        rho=rho,
        sub_params=params_low,
    )
    s_high = s_sub_boundary(
        T_M,
        T_sub,
        t_ref=t_orb,
        rho=rho,
        sub_params=params_high,
    )
    assert s_high > s_low > 0.0


def test_s_sink_matches_boundary_for_one_orbit():
    T_M = 2300.0
    rho = 3100.0
    r = 2.2 * constants.R_MARS
    Omega = _kepler_omega(r)
    t_orb = 2.0 * math.pi / Omega
    params = _make_params()
    setattr(params, "runtime_orbital_radius_m", r)

    T_d = grain_temperature_graybody(T_M, r)
    s_boundary = s_sub_boundary(
        T_M,
        params.T_sub,
        t_ref=t_orb,
        rho=rho,
        sub_params=params,
    )
    s_direct = s_sink_from_timescale(T_d, rho, t_orb, params)
    assert pytest.approx(s_direct, rel=1e-6) == s_boundary


def test_total_sink_timescale_returns_none_when_flux_zero():
    T_M = 1800.0
    rho = 3000.0
    r = 2.4 * constants.R_MARS
    Omega = _kepler_omega(r)
    params = _make_params(P_gas=1e6)  # ensure P_sat - P_gas <= 0
    setattr(params, "runtime_orbital_radius_m", r)

    sink_opts = SinkOptions(enable_sublimation=True, sub_params=params)
    result = total_sink_timescale(
        T_M,
        rho,
        Omega,
        sink_opts,
        s_ref=1e-6,
    )
    assert result.t_sink is None
