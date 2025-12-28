import math
import numpy as np
import pytest

from marsdisk.physics import sublimation
from marsdisk.physics.sublimation import SublimationParams, s_sink_from_timescale
from marsdisk.physics.fragments import s_sub_boundary, compute_s_min_F2


def test_s_sink_from_timescale_logistic():
    params = SublimationParams()  # logistic placeholder
    size = s_sink_from_timescale(1300.0, rho=2.0, t_ref=10.0, params=params)
    assert pytest.approx(size) == params.eta_instant * 10.0 * math.exp(0.0) / 2.0


def test_s_sub_boundary_fallback_warning():
    with pytest.warns(UserWarning):
        s = s_sub_boundary(1500.0)
    assert s == pytest.approx(1e-3)


def test_compute_s_min_F2_uses_max():
    params = SublimationParams()
    with pytest.warns(DeprecationWarning):
        s_min = compute_s_min_F2(
            a_blow=1.0,
            T=1300.0,
            t_ref=10.0,
            rho=2.0,
            sub_params=params,
        )
    assert s_min == pytest.approx(1.0)


def test_sublimation_sink_scalar_matches_array():
    sizes = np.array([1.0e-6, 2.0e-6, 4.0e-6])
    N_k = np.array([1.0, 2.0, 1.5])
    rho = 3000.0
    m_k = (4.0 / 3.0) * np.pi * rho * sizes**3
    ds_dt = -1.0e-9
    S_scalar, mass_scalar = sublimation.sublimation_sink_from_dsdt(sizes, N_k, ds_dt, m_k)
    ds_dt_k = np.full_like(sizes, ds_dt)
    S_array, mass_array = sublimation.sublimation_sink_from_dsdt(sizes, N_k, ds_dt_k, m_k)
    assert np.allclose(S_scalar, S_array)
    assert mass_scalar == pytest.approx(mass_array)
