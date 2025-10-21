import numpy as np

from marsdisk.physics.surface import step_surface_density_S1
from marsdisk.physics.sinks import SinkOptions, total_sink_timescale
from marsdisk.physics.sublimation import SublimationParams


def _run(prod_rate: float, Omega: float, Sigma_tau1: float, steps: int = 200):
    dt = 1.0 / Omega  # use t_blow as step for rapid convergence
    sigma = 0.0
    res = None
    for _ in range(steps):
        res = step_surface_density_S1(
            sigma,
            prod_rate,
            dt,
            Omega,
            sigma_tau1=Sigma_tau1,
        )
        sigma = res.sigma_surf
    return res


def test_supply_limited_outflux():
    Omega = 1e-4
    Sigma_tau1 = 1e-3
    eps = 0.5
    prod_raw = 1e-9  # well below saturation limit
    res = _run(prod_raw * eps, Omega, Sigma_tau1)
    assert np.isclose(res.outflux, prod_raw * eps, rtol=1e-2)


def test_saturation_limited_outflux():
    Omega = 1e-4
    Sigma_tau1 = 1e-3
    eps = 0.5
    prod = 1e-4  # far above saturation limit
    res = _run(prod * eps, Omega, Sigma_tau1)
    assert np.isclose(res.outflux, Sigma_tau1 * Omega, rtol=1e-2)


def test_sink_increases_mass_loss():
    Omega = 1e-4
    Sigma_tau1 = 1e-3
    sigma0 = Sigma_tau1
    dt = 1.0

    res_no = step_surface_density_S1(
        sigma0,
        0.0,
        dt,
        Omega,
        sigma_tau1=Sigma_tau1,
    )

    opts = SinkOptions(enable_sublimation=True, sub_params=SublimationParams())
    sink_result = total_sink_timescale(1500.0, 3000.0, Omega, opts)
    res_sink = step_surface_density_S1(
        sigma0,
        0.0,
        dt,
        Omega,
        sigma_tau1=Sigma_tau1,
        t_sink=sink_result.t_sink,
    )
    total_no = res_no.outflux + res_no.sink_flux
    total_sink = res_sink.outflux + res_sink.sink_flux
    assert total_sink > total_no
