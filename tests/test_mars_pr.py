from importlib import util
from pathlib import Path

spec = util.spec_from_file_location(
    "step1_test", Path(__file__).resolve().parents[1] / "Step1" / "test.py"
)
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

t_PR_mars = mod.t_PR_mars
t_PR = mod.t_PR
beta_sun = mod.beta_sun
R_MARS = mod.R_MARS


def test_mars_pr_faster_than_sun():
    s = 1e-6
    rho = 3000
    beta = beta_sun(s, rho)
    t_sun = t_PR(s, rho, beta)
    t_mars = t_PR_mars(s, rho, 3000, 1.0, 5 * R_MARS)
    assert t_mars < t_sun
