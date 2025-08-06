import subprocess
import sys
from pathlib import Path
from importlib import util

import numpy as np

step1_path = Path(__file__).resolve().parents[1] / "Step1"
sys.path.append(str(step1_path))
spec = util.spec_from_file_location("ext_map", step1_path / "extended_static_map.py")
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

R_MARS = mod.R_MARS
kappa_mass_averaged = mod.kappa_mass_averaged
sigma_from_mass = mod.sigma_from_mass


def test_tau_scaling():
    kappa = kappa_mass_averaged(3.5, 1e-6, 0.1, 3000)
    tau = kappa * sigma_from_mass(1e-15, 2 * np.pi * 5 * R_MARS * 1 * R_MARS)
    assert 1e-7 < tau < 1e-5


def test_mass_tau_script(tmp_path):
    script = step1_path / "extended_static_map.py"
    subprocess.run([sys.executable, str(script), "--n_M", "5"], cwd=tmp_path, check=True)
    out_dir = tmp_path / "output"
    assert (out_dir / "mass_tau_map.png").exists()
    assert (out_dir / "mass_tau_map.csv").exists()
