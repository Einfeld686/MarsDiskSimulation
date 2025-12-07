import json
from pathlib import Path

import pytest

from marsdisk import run, schema


def _make_config(
    outdir: Path,
    *,
    TM_K: float | None = None,
    driver_constant: float | None = None,
) -> schema.Config:
    radiation = schema.Radiation(TM_K=TM_K) if TM_K is not None else schema.Radiation()
    if driver_constant is not None:
        radiation.mars_temperature_driver = schema.MarsTemperatureDriverConfig(
            enabled=True,
            mode="constant",
            constant=schema.MarsTemperatureDriverConstant(value_K=driver_constant),
    )
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.6,
                r_out_RM=2.6,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=radiation,
        sizes=schema.Sizes(s_min=1.0e-8, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-8, dt_init=1.0),
        io=schema.IO(outdir=outdir),
    )
    cfg.sinks.mode = "none"
    cfg.radiation.qpr_table_path = Path("data/qpr_table.csv")
    return cfg


def _run_and_load(cfg: schema.Config) -> dict:
    run.run_zero_d(cfg)
    summary_path = Path(cfg.io.outdir) / "summary.json"
    return json.loads(summary_path.read_text())


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_temperature_selection_prefers_radiation_override(tmp_path: Path) -> None:
    cfg = _make_config(
        tmp_path / "override_case",
        TM_K=2100.0,
        driver_constant=1800.0,
    )

    summary = _run_and_load(cfg)

    assert summary["T_M_source"] == "radiation.TM_K"
    assert summary["T_M_used"] == pytest.approx(2100.0)


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_temperature_selection_tracks_temps_when_no_override(tmp_path: Path) -> None:
    cfg_low = _make_config(tmp_path / "driver_low", driver_constant=1800.0)
    cfg_high = _make_config(tmp_path / "driver_high", driver_constant=2200.0)

    summary_low = _run_and_load(cfg_low)
    summary_high = _run_and_load(cfg_high)

    assert summary_low["T_M_source"] == "mars_temperature_driver.constant"
    assert summary_low["T_M_used"] == pytest.approx(1800.0)
    assert summary_high["T_M_source"] == "mars_temperature_driver.constant"
    assert summary_high["T_M_used"] == pytest.approx(2200.0)
    assert summary_high["s_blow_m"] > summary_low["s_blow_m"]
