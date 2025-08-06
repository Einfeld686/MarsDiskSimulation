from importlib import util
from pathlib import Path
import sys
import pytest

step1_path = Path(__file__).resolve().parents[1] / "Step1"
sys.path.append(str(step1_path))
spec = util.spec_from_file_location("ext_map", step1_path / "extended_static_map.py")
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_blowout_radius_with_mars_pr():
    rho = 3000
    r_disk = 2.6  # [R_MARS]
    a_old = mod.blowout_radius(rho, qpr=1.0, r_disk_Rmars=r_disk, T_mars=3000, include_mars_pr=False)
    expected = 5.7e-4 / (0.5 * rho)
    assert a_old == pytest.approx(expected)

    a_new = mod.blowout_radius(rho, qpr=1.0, r_disk_Rmars=r_disk, T_mars=3000, include_mars_pr=True)
    assert a_new > a_old
    assert a_new / a_old > 2.0
