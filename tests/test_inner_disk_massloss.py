from __future__ import annotations

from pathlib import Path

import numpy as np
from ruamel.yaml import YAML

from marsdisk import constants, schema
from marsdisk.analysis.inner_disk_runner import run_inner_disk_sweep


def _build_config(outdir: Path, *, sinks_mode: str, enable_sublimation: bool, enable_gas_drag: bool) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D", r=2.6 * constants.R_MARS),
        material=schema.Material(rho=3000.0),
        temps=schema.Temps(T_M=1800.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=12),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.05, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-5, dt_init=20.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=5.0e-10),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, step_diagnostics=schema.StepDiagnostics(enable=True, format="csv")),
        radiation=schema.Radiation(Q_pr=1.0),
    )
    cfg.sinks.mode = sinks_mode
    cfg.sinks.enable_sublimation = enable_sublimation
    cfg.sinks.enable_gas_drag = enable_gas_drag
    return cfg


def _write_yaml(cfg: schema.Config, path: Path) -> Path:
    yaml = YAML()
    yaml.default_flow_style = False
    payload = cfg.model_dump(mode="json")
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(payload, fh)
    return path


def test_inner_disk_sweep_runs_and_collects_massloss(tmp_path: Path) -> None:
    cfg_paths = []
    labels = []
    for idx, params in enumerate(
        [
            {"sinks_mode": "none", "enable_sublimation": False, "enable_gas_drag": False},
            {"sinks_mode": "sublimation", "enable_sublimation": True, "enable_gas_drag": True},
            {"sinks_mode": "sublimation", "enable_sublimation": True, "enable_gas_drag": False},
        ]
    ):
        label = f"case_{idx}"
        cfg = _build_config(tmp_path / f"out_{label}", **params)
        path = _write_yaml(cfg, tmp_path / f"{label}.yml")
        cfg_paths.append(path)
        labels.append(label)

    df = run_inner_disk_sweep(
        cfg_paths,
        labels=labels,
        t_end_years=1.0e-5,
        enable_step_diagnostics=True,
        append_label_to_outdir=False,
    )

    required_cols = [
        "label",
        "M_init",
        "M_loss_total",
        "M_loss_sinks",
        "M_loss_subl",
        "M_remain",
        "f_loss",
        "f_subl",
    ]
    for col in required_cols:
        assert col in df.columns, f"{col}列が欠落しています"

    assert list(df["label"]) == labels
    for col in ["M_loss_total", "M_loss_sinks", "M_loss_subl", "M_remain", "f_loss", "f_subl", "M_init"]:
        values = df[col].to_numpy(dtype=float)
        assert np.isfinite(values).all(), f"{col} に非有限値が含まれています: {values}"

    closure = df["M_remain"] + df["M_loss_total"]
    error_percent = np.abs((df["M_init"] - closure) / df["M_init"]) * 100.0
    assert (error_percent < 1.0).all(), "M_init が M_remain+M_loss_total と1%以内で一致しません"
