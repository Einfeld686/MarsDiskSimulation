from importlib import util
from pathlib import Path
import numpy as np
import sys

# load module
step1_path = Path(__file__).resolve().parents[1] / "Step1"
sys.path.append(str(step1_path))
spec = util.spec_from_file_location("ext_map", step1_path / "extended_static_map.py")
mod_map = util.module_from_spec(spec)
spec.loader.exec_module(mod_map)


def test_mass_fraction_blowout():
    S_vals = np.logspace(-6, -5, 2)
    Sigma_vals = np.logspace(2, 3, 2)
    S, SIG = np.meshgrid(S_vals, Sigma_vals)
    t_col = mod_map.collision_timescale_years(S, SIG, 3000, 2 * mod_map.R_MARS)
    F_blow = mod_map.mass_fraction_blowout_map(
        S,
        SIG,
        3000,
        1e-7,
        2e-6,
        1e-3,
        3.5,
        1e-9,
        t_col,
    )
    assert F_blow.shape == S.shape
    assert (F_blow >= 0).all() and (F_blow <= 1).all()
    assert not np.allclose(F_blow[0, 0], F_blow[0, 1])
    assert not np.allclose(F_blow[0, 0], F_blow[1, 0])
