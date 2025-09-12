from pathlib import Path
import math

import pytest

from marsdisk.physics import surface, supply
from marsdisk import run, schema


def test_step_surface_tau_zero_no_error():
    res = surface.step_surface(
        sigma_surf=0.0,
        prod_subblow_area_rate=0.0,
        eps_mix=0.0,
        dt=1.0,
        Omega=1.0,
        tau=0.0,
    )
    assert math.isfinite(res.sigma_surf)


def test_sigma_tau1_zero_kappa(monkeypatch):
    def fake_kappa(state):
        return 0.0

    monkeypatch.setattr(run.psd, "compute_kappa", fake_kappa)
    rc = run.RunConfig(r=1.0, Omega=1.0, eps_mix=0.0, prod_rate=0.0)
    rs = run.RunState(sigma_surf=0.0, psd_state={})
    rec = run.step(rc, rs, dt=1.0)
    assert math.isfinite(rec["outflux_surface"])


def test_supply_powerlaw_t0_zero():
    cfg = schema.Supply(
        mode="powerlaw",
        powerlaw=schema.SupplyPowerLaw(A_kg_m2_s=1.0, t0_s=0.0, index=0.0),
    )
    model = supply.SupplyModel(cfg)
    assert model.rate(10.0) == pytest.approx(1.0)


def test_run_zero_d_no_zerodivision(monkeypatch, tmp_path):
    cfg = run.load_config(Path("configs/base.yml"))
    monkeypatch.setattr(run, "MAX_STEPS", 1)
    monkeypatch.setattr(cfg.io, "outdir", tmp_path)
    run.run_zero_d(cfg)
