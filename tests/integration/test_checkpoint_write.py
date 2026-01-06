from pathlib import Path

import pytest

from marsdisk import run, schema
from marsdisk.io import checkpoint as checkpoint_io

pytestmark = [
    pytest.mark.filterwarnings("ignore:Q_pr table not found"),
    pytest.mark.filterwarnings("ignore:Phi table not found"),
]


def _checkpoint_config(outdir: Path) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=1.3,
                r_out_RM=1.3,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=3000.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=16),
        initial=schema.Initial(mass_total=1.0e-8, s0_mode="upper"),
        dynamics=schema.Dynamics(
            e0=0.05,
            i0=0.01,
            t_damp_orbits=5.0,
            f_wake=1.0,
            e_profile=schema.DynamicsEccentricityProfile(mode="off"),
            rng_seed=13579,
        ),
        psd=schema.PSD(alpha=1.8, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(
            t_end_years=2.0e-6,
            dt_init=1.0,
            eval_per_step=False,
            orbit_rollup=False,
            checkpoint=schema.Checkpoint(
                enabled=True,
                interval_years=5.0e-7,
                keep_last_n=3,
                format="pickle",
            ),
        ),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=1.0e-5),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, debug_sinks=False, quiet=True),
    )
    cfg.sinks.mode = "none"
    return cfg


def test_checkpoint_written(tmp_path: Path) -> None:
    cfg = _checkpoint_config(tmp_path / "checkpoint_run")
    run.run_zero_d(cfg)

    checkpoint_dir = cfg.io.outdir / "checkpoints"
    checkpoints = sorted(checkpoint_dir.glob("ckpt_step_*.pkl"))
    assert checkpoints, "Expected at least one checkpoint file"
    assert checkpoint_io.find_latest_checkpoint(checkpoint_dir) is not None
