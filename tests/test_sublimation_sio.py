import json
import math

import pytest

from ruamel.yaml import YAML

from marsdisk import constants
from marsdisk.physics.sublimation import (
    SublimationParams,
    mass_flux_hkl,
    p_sat,
)


@pytest.fixture
def sio_params() -> SublimationParams:
    return SublimationParams(
        mode="hkl",
        psat_model="clausius",
        alpha_evap=0.007,
        mu=0.0440849,
        A=13.613,
        B=17850.0,
        P_gas=0.0,
        valid_K=(1270.0, 1600.0),
    )


def test_units_and_flux_dimension(sio_params: SublimationParams) -> None:
    T = 1500.0
    P_sat = p_sat(T, sio_params)
    expected_psat = 10 ** (13.613 - 17850.0 / T)
    assert pytest.approx(P_sat, rel=0.05) == expected_psat
    flux = mass_flux_hkl(T, sio_params)
    root = (sio_params.mu / (2.0 * math.pi * constants.R_GAS * T)) ** 0.5
    expected_flux = sio_params.alpha_evap * expected_psat * root
    assert pytest.approx(flux, rel=0.1) == expected_flux


def test_negative_pressure_gap_clamped(sio_params: SublimationParams) -> None:
    params = SublimationParams(
        mode="hkl",
        psat_model="clausius",
        alpha_evap=sio_params.alpha_evap,
        mu=sio_params.mu,
        A=sio_params.A,
        B=sio_params.B,
        P_gas=1.0e3,
    )
    flux = mass_flux_hkl(1500.0, params)
    assert flux == pytest.approx(0.0)


def test_tabulated_psat_interp(tmp_path) -> None:
    table_path = tmp_path / "sio_psat.csv"
    table_path.write_text(
        "T[K],log10P[Pa]\n"
        "1400,1.3\n"
        "1500,1.71\n"
        "1600,2.1\n",
        encoding="utf-8",
    )
    params = SublimationParams(
        mode="hkl",
        psat_model="tabulated",
        alpha_evap=0.007,
        mu=0.0440849,
        P_gas=0.0,
        psat_table_path=table_path,
    )
    P_1400 = p_sat(1400.0, params)
    P_1450 = p_sat(1450.0, params)
    P_1500 = p_sat(1500.0, params)

    assert P_1400 < P_1450 < P_1500
    assert P_1450 > 0.0


def test_auto_prefers_tabulated_within_range(tmp_path) -> None:
    table_path = tmp_path / "sio_psat.csv"
    table_path.write_text(
        "T[K],log10P[Pa]\n"
        "1400,1.30\n"
        "1500,1.71\n"
        "1600,2.05\n",
        encoding="utf-8",
    )
    params = SublimationParams(
        mode="hkl",
        psat_model="auto",
        alpha_evap=0.007,
        mu=0.0440849,
        A=13.613,
        B=17850.0,
        psat_table_path=table_path,
        valid_K=(1270.0, 1600.0),
    )
    P_auto = p_sat(1500.0, params)
    expected = 10 ** 1.71
    assert pytest.approx(P_auto, rel=0.02) == expected
    assert params.psat_model_resolved == "tabulated"
    assert params._psat_last_selection["log10P_tabulated"] == pytest.approx(1.71, rel=1e-6)


def test_auto_switches_to_local_clausius_fit(tmp_path) -> None:
    table_path = tmp_path / "sio_psat_rr.csv"
    table_path.write_text(
        "T[K],log10P[Pa]\n"
        "1400,1.30\n"
        "1600,1.95\n"
        "1800,2.20\n"
        "2000,2.45\n"
        "2200,2.70\n",
        encoding="utf-8",
    )
    params = SublimationParams(
        mode="hkl",
        psat_model="auto",
        alpha_evap=0.007,
        mu=0.0440849,
        A=13.613,
        B=17850.0,
        psat_table_path=table_path,
        valid_K=(1270.0, 1600.0),
    )
    P_auto = p_sat(2400.0, params)
    assert P_auto > 0.0
    assert params.psat_model_resolved == "clausius(local-fit)"
    meta = params._psat_last_selection
    assert meta["A_active"] is not None
    assert meta["B_active"] > 0.0
    assert meta["valid_K_active"][1] <= 2200.0


def test_auto_baseline_warns_when_out_of_range(caplog) -> None:
    params = SublimationParams(
        mode="hkl",
        psat_model="auto",
        alpha_evap=0.007,
        mu=0.0440849,
        A=13.613,
        B=17850.0,
        valid_K=(1270.0, 1600.0),
    )
    with caplog.at_level("WARNING"):
        flux = mass_flux_hkl(3000.0, params)
    assert flux >= 0.0
    assert params.psat_model_resolved == "clausius(baseline)"
    joined = " ".join(rec.message for rec in caplog.records)
    assert "Hyodo et al. 2017" in joined
    assert "Ferguson et al. (2012)" in joined


def test_run_config_records_psat_selection(tmp_path) -> None:
    table_path = tmp_path / "sio_psat_tab.csv"
    table_path.write_text(
        "T[K],log10P[Pa]\n"
        "700,0.85\n"
        "800,1.10\n"
        "900,1.35\n",
        encoding="utf-8",
    )

    outdir = tmp_path / "out"
    config_path = tmp_path / "config.yml"
    yaml = YAML()
    config = {
        "geometry": {"mode": "0D", "r": 2.2 * constants.R_MARS},
        "material": {"rho": 3000.0},
        "temps": {"T_M": 1600.0},
        "sizes": {"s_min": 1.0e-6, "s_max": 3.0, "n_bins": 20},
        "initial": {"mass_total": 1.0e-6, "s0_mode": "upper"},
        "dynamics": {
            "e0": 0.3,
            "i0": 0.05,
            "t_damp_orbits": 5.0,
            "f_wake": 1.5,
        },
        "psd": {"alpha": 1.83, "wavy_strength": 0.1},
        "qstar": {"Qs": 3.5e7, "a_s": 0.38, "B": 0.3, "b_g": 1.36, "v_ref_kms": [3.0, 5.0]},
        "surface": {"init_policy": "clip_by_tau1", "sigma_surf_init_override": None, "use_tcoll": True},
        "sinks": {
            "mode": "sublimation",
            "enable_sublimation": True,
            "T_sub": 1300.0,
            "sub_params": {
                "mode": "hkl",
                "psat_model": "auto",
                "alpha_evap": 0.007,
                "mu": 0.0440849,
                    "A": 13.613,
                    "B": 17850.0,
                    "valid_K": [650.0, 900.0],
        "psat_table_path": str(table_path),
                "eta_instant": 0.1,
                "dT": 50.0,
                "P_gas": 0.0,
            },
            "enable_gas_drag": False,
            "rho_g": 0.0,
        },
        "numerics": {
            "t_end_years": 1.0e-3,
            "dt_init": 10.0,
            "safety": 0.1,
            "atol": 1e-10,
            "rtol": 1e-6,
        },
        "io": {"outdir": str(outdir)},
    }
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh)

    from marsdisk import run as run_module

    run_module.main(["--config", str(config_path)])

    run_config_path = outdir / "run_config.json"
    assert run_config_path.exists()
    data = json.loads(run_config_path.read_text(encoding="utf-8"))
    prov = data["sublimation_provenance"]
    assert prov["psat_model"] == "auto"
    assert prov["psat_model_resolved"] == "tabulated"
    assert prov["psat_table_path"] == str(table_path)
    assert prov["psat_table_range_K"] == [700.0, 900.0]
    assert prov["A"] == pytest.approx(13.613, rel=1e-6)
    assert prov["B"] == pytest.approx(17850.0, rel=1e-6)
    assert prov["psat_table_buffer_K"] == pytest.approx(75.0, rel=1e-6)
    assert prov["T_req"] is not None
