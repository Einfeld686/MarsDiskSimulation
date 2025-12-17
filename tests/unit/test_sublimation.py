import math
import pytest

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
