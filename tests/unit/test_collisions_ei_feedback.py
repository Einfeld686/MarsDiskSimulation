import math

import pytest

from marsdisk.physics import collisions_smol
from marsdisk.schema import Dynamics


def test_compute_ei_damping_relaxes_toward_equilibrium():
    dyn = Dynamics(
        e0=0.6,
        i0=0.3,
        t_damp_orbits=0.0,
        f_wake=1.0,
        eps_restitution=0.5,
    )
    e_next, i_next, t_damp, e_target = collisions_smol._compute_ei_damping(
        e_curr=0.6,
        i_curr=0.3,
        dt=20.0,
        tau_eff=0.5,
        a_orbit_m=1.0,
        v_k=2.0,
        dynamics_cfg=dyn,
        t_coll_ref=10.0,
        eps_restitution=0.5,
    )

    assert e_next is not None and i_next is not None
    assert e_target is not None
    assert t_damp is not None and math.isclose(t_damp, 40.0)
    assert e_target < 0.6
    assert e_target <= e_next <= 0.6
    assert math.isfinite(e_next) and math.isfinite(i_next)
    assert i_next / e_next == pytest.approx(0.5, rel=1e-6)
