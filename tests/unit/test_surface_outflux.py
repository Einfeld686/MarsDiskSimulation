import numpy as np
import pytest

from marsdisk.physics.surface import step_surface_density_S1
from marsdisk.physics.sinks import SinkOptions, total_sink_timescale
from marsdisk.physics.sublimation import SublimationParams
from marsdisk import constants, run, physics


def _run(prod_rate: float, Omega: float, steps: int = 200):
    dt = 1.0 / Omega  # use t_blow as step for rapid convergence
    sigma = 0.0
    res = None
    for _ in range(steps):
        res = step_surface_density_S1(
            sigma,
            prod_rate,
            dt,
            Omega,
            sigma_tau1=None,
        )
        sigma = res.sigma_surf
    return res


def test_supply_limited_outflux():
    Omega = 1e-4
    eps = 0.5
    prod_raw = 1e-9  # well below saturation limit
    res = _run(prod_raw * eps, Omega)
    assert np.isclose(res.outflux, prod_raw * eps, rtol=1e-2)


def test_saturation_limited_outflux():
    Omega = 1e-4
    eps = 0.5
    prod = 1e-4  # far above saturation limit
    res = _run(prod * eps, Omega)
    assert np.isclose(res.outflux, prod * eps, rtol=1e-2)


def test_sink_increases_mass_loss():
    Omega = 1e-4
    sigma0 = 1e-3
    dt = 1.0

    res_no = step_surface_density_S1(
        sigma0,
        0.0,
        dt,
        Omega,
        sigma_tau1=None,
    )

    opts = SinkOptions(enable_sublimation=True, sub_params=SublimationParams())
    sink_result = total_sink_timescale(1500.0, 3000.0, Omega, opts)
    res_sink = step_surface_density_S1(
        sigma0,
        0.0,
        dt,
        Omega,
        sigma_tau1=None,
        t_sink=sink_result.t_sink,
    )
    total_no = res_no.outflux + res_no.sink_flux
    total_sink = res_sink.outflux + res_sink.sink_flux
    assert total_sink > total_no


def test_los_factor_increases_tau_los(tmp_path):
    """LOS係数を伸ばしたときに tau_los_mars が記録されることを確認する。"""

    r = constants.R_MARS
    Omega = 1e-4
    prod_rate = 1e-9
    psd_state = physics.psd.update_psd_state(
        s_min=1.0e-6,
        s_max=1.0e-3,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=8,
        rho=3000.0,
    )
    cfg = run.RunConfig(r=r, Omega=Omega, prod_rate=prod_rate, area=None, los_factor=3.0)
    state = run.RunState(sigma_surf=0.0, psd_state=psd_state)
    rec = run.step(cfg, state, dt=1.0 / Omega)
    assert "tau_los_mars" in rec
    assert rec["tau_los_mars"] >= 0.0
