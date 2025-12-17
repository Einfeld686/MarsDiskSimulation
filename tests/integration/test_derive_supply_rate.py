from __future__ import annotations

import io
import csv
from contextlib import redirect_stdout
from pathlib import Path
import os

import pytest

from tools import derive_supply_rate
from marsdisk import constants, grid


def run_cli(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        derive_supply_rate.main(argv)
    return buf.getvalue().strip()


def test_compute_r_base_scalar():
    inputs = derive_supply_rate.SupplyInputs(
        mu=0.5, sigma_tau1=1.0e2, epsilon_mix=1.0, t_blow=1.0e3
    )
    rate = derive_supply_rate.compute_r_base(inputs)
    assert rate == pytest.approx(5.0e-2)


def test_cli_text_output():
    out = run_cli(
        [
            "--mu",
            "0.5",
            "--sigma-tau1",
            "1.0e2",
            "--t-blow",
            "1000",
            "--epsilon-mix",
            "1.0",
        ]
    )
    assert out.startswith("prod_area_rate_kg_m2_s=")
    value = float(out.split("=")[1])
    assert value == pytest.approx(5.0e-2)


def test_csv_grid_output():
    # Use radius grid (in RM) and mu grid, rely on omega_kepler for t_blow
    out = run_cli(
        [
            "--sigma-tau1",
            "10.0",
            "--epsilon-mix",
            "1.0",
            "--r-grid",
            "2.0,2.5",
            "--mu-grid",
            "0.1,0.2",
            "--format",
            "csv",
        ]
    )
    rows = list(csv.DictReader(io.StringIO(out)))
    assert len(rows) == 4  # 2 radii × 2 mu
    # Check one row numerically
    first = rows[0]
    r_rm = float(first["r"])
    mu_val = float(first["mu"])
    sigma_tau1 = float(first["sigma_tau1"])
    t_blow = float(first["t_blow"])
    rate_csv = float(first["prod_area_rate_kg_m2_s"])

    r_m = r_rm * constants.R_MARS
    omega = grid.omega_kepler(r_m)
    t_blow_ref = 1.0 / omega
    rate_ref = (mu_val * sigma_tau1) / (t_blow_ref)

    assert t_blow == pytest.approx(t_blow_ref)
    assert rate_csv == pytest.approx(rate_ref)


def test_config_defaults(tmp_path, monkeypatch):
    cfg = {
        "supply": {"mixing": {"epsilon_mix": 0.5}},
        "shielding": {"fixed_tau1_sigma": 200.0},
    }
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text(
        "supply:\n"
        "  mixing:\n"
        "    epsilon_mix: 0.5\n"
        "shielding:\n"
        "  fixed_tau1_sigma: 200.0\n"
    )
    out = run_cli(
        [
            "--mu",
            "0.5",
            "--t-blow",
            "1000",
            "--config",
            str(cfg_path),
        ]
    )
    value = float(out.split("=")[1])
    # R_base = (0.5 * 200) / (0.5 * 1000) = 0.2
    assert value == pytest.approx(0.2)


def test_env_defaults(monkeypatch):
    monkeypatch.setenv("MARS_DISK_SIGMA_TAU1", "50")
    monkeypatch.setenv("MARS_DISK_EPSILON_MIX", "2.0")
    out = run_cli(
        [
            "--mu",
            "0.5",
            "--t-blow",
            "1000",
        ]
    )
    value = float(out.split("=")[1])
    # R_base = (0.5 * 50) / (2.0 * 1000) = 0.0125
    assert value == pytest.approx(0.0125)
