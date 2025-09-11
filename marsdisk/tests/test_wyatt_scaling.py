import numpy as np

from marsdisk.physics.surface import wyatt_tcoll_S1


def test_wyatt_scaling_inverse_tau():
    Omega = 1e-4
    t1 = wyatt_tcoll_S1(1e-5, Omega)
    t2 = wyatt_tcoll_S1(1e-4, Omega)
    t3 = wyatt_tcoll_S1(1e-3, Omega)
    assert np.isclose(t1 / t2, 10.0)
    assert np.isclose(t2 / t3, 10.0)
