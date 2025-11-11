import json
from pathlib import Path

import pytest

from marsdisk import run, schema


def _build_config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=1.5),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=2000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=8),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-7, dt_init=10.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-9),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=True),
    )
    cfg.sinks.mode = "sublimation"
    cfg.sinks.enable_sublimation = True
    return cfg


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_debug_sinks_trace_outputs_jsonl(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)

    run.run_zero_d(cfg)

    trace_path = Path(cfg.io.outdir) / "debug" / "sinks_trace.jsonl"
    assert trace_path.exists(), "Expected sinks_trace.jsonl to be generated"
    lines = trace_path.read_text().splitlines()
    assert lines, "Trace file should contain at least one record"
    for line in lines:
        record = json.loads(line)
        assert "time_s" in record and isinstance(record["time_s"], (float, int))
        assert "T_M_K" in record and isinstance(record["T_M_K"], (float, int))
        assert "total_sink_dm_dt_kg_s" in record

    summary_path = Path(cfg.io.outdir) / "summary.json"
    summary = json.loads(summary_path.read_text())
    assert "M_loss_from_sinks" in summary
    assert "M_loss_from_sublimation" in summary
    assert summary["M_loss_from_sublimation"] <= summary["M_loss_from_sinks"]
    assert summary["M_loss_from_sinks"] <= summary["M_loss"]
