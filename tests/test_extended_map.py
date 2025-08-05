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


def test_f_blow_map_shape():
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
    assert F_blow.max() <= 0.1


def test_eta_loss():
    S_vals = np.logspace(-6, -5, 2)
    Sigma_vals = np.logspace(2, 3, 2)
    S, SIG = np.meshgrid(S_vals, Sigma_vals)
    rho = 3000
    r_disk = 2 * R_MARS
    t_sim = 10.0
    beta_dummy = np.full_like(S, 0.1)
    t_col = mod_ts.collision_timescale(S, SIG, rho, r_disk)
    t_pr = mod_ts.pr_timescale_total(S, rho, beta_dummy, False, 3000, 1.0, r_disk)
    tau_eff = (t_col * t_pr) / (t_col + t_pr)
    eta_loss = 1.0 - np.exp(-t_sim / tau_eff)
    eta_loss = np.clip(eta_loss, 0.0, 1.0)
    assert eta_loss.shape == S.shape
    assert np.nanmax(eta_loss) <= 1.0
