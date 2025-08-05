from importlib import util
from pathlib import Path

import numpy as np
import sys

# load modules
step1_path = Path(__file__).resolve().parents[1] / "Step1"
sys.path.append(str(step1_path))
spec_map = util.spec_from_file_location(
    "ext_map", step1_path / "extended_static_map.py"
)
mod_map = util.module_from_spec(spec_map)
spec_map.loader.exec_module(mod_map)

spec_ts = util.spec_from_file_location("timescales", step1_path / "timescales.py")
mod_ts = util.module_from_spec(spec_ts)
spec_ts.loader.exec_module(mod_ts)

R_MARS = mod_map.R_MARS


def test_f_blow_map_and_eta_loss_shape():
    S_vals = np.logspace(-6, -5, 2)
    Sigma_vals = np.logspace(2, 3, 2)
    S, SIG = np.meshgrid(S_vals, Sigma_vals)
    a_min = 1e-7
    a_bl = 2e-6
    a_max = 1e-3
    rho = 3000
    q = 3.5
    t_sim = 1.0
    r_disk = 2 * R_MARS

    F_blow = mod_map.mass_fraction_blowout_map(
        S, SIG, rho, a_min, a_bl, a_max, q, t_sim, r_disk
    )
    assert F_blow.shape == S.shape
    assert F_blow.max() <= 1.0

    beta_dummy = np.full_like(S, 0.1)
    t_col = mod_ts.collision_timescale(S, SIG, rho, r_disk)
    t_pr = mod_ts.pr_timescale_total(S, rho, beta_dummy, False, 3000, 1.0, r_disk)
    eta_loss = t_pr / (t_col + t_pr)
    assert eta_loss.shape == S.shape


def test_mass_fraction_blowout():
    S_vals = np.array([1e-6, 1e-4])
    Sigma_vals = np.array([1e2, 1e3])
    S, SIG = np.meshgrid(S_vals, Sigma_vals)
    F_blow = mod_map.mass_fraction_blowout_map(
        S,
        SIG,
        rho=3000,
        a_min=1e-7,
        a_bl=2e-6,
        a_max=1e-3,
        q=3.5,
        t_sim=1e-9,
        r_disk=2 * R_MARS,
    )
    # Sigma が大きいほど F_blow が大きい
    assert F_blow[1, 0] > F_blow[0, 0]
    # 粒径が大きくなると F_blow は小さくなる
    assert F_blow[1, 1] < F_blow[1, 0]
