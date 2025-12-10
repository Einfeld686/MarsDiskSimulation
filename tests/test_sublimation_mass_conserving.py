import math

import numpy as np

from marsdisk import constants, grid
from marsdisk.physics import collisions_smol, psd


def test_mass_conserving_sublimation_redirects_to_blowout() -> None:
    """ds/dt で blowout を跨いだ分が昇華シンクではなく blowout に振替される。"""

    psd_state = psd.update_psd_state(
        s_min=2.0e-6,
        s_max=3.0e-6,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=8,
        rho=3000.0,
    )
    sigma_surf = 1.0  # kg/m^2
    ds_dt = -1.0e-6  # m/s, crosses a_blow within dt
    dt = 10.0
    a_blow = 1.5e-6

    res = collisions_smol.step_collisions_smol_0d(
        psd_state,
        sigma_surf,
        dt=dt,
        prod_subblow_area_rate=0.0,
        r=constants.R_MARS,
        Omega=grid.omega_kepler(constants.R_MARS),
        a_blow=a_blow,
        rho=3000.0,
        e_value=0.01,
        i_value=0.005,
        sigma_tau1=None,
        enable_blowout=True,
        t_sink=None,
        ds_dt_val=ds_dt,
        s_min_effective=a_blow,
        dynamics_cfg=None,
        tau_eff=None,
        collisions_enabled=False,
        mass_conserving_sublimation=True,
    )

    assert res.mass_loss_rate_sublimation == 0.0
    assert math.isfinite(res.mass_loss_rate_blowout) and res.mass_loss_rate_blowout > 0.0
    assert res.dSigma_dt_blowout > 0.0
    assert res.dSigma_dt_sublimation == 0.0
