from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from marsdisk import run, schema


@pytest.mark.filterwarnings("ignore:Q_pr table not found")
@pytest.mark.filterwarnings("ignore:Phi table not found")
def test_mass_budget_closure_with_blowout_and_sinks(tmp_path: Path) -> None:
    """Ensure combined (collisions+sinks) runs keep the mass budget closed."""

    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=1.0,
                r_out_RM=1.0,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=1200.0),
        radiation=schema.Radiation(TM_K=1700.0, Q_pr=1.0),
        sizes=schema.Sizes(s_min=1.0e-7, s_max=1.0e-3, n_bins=12),
        initial=schema.Initial(mass_total=1.0e-9, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=0.1, i0=0.01, t_damp_orbits=1.0, f_wake=1.0),
        psd=schema.PSD(alpha=1.5, wavy_strength=0.1),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-7, dt_init=1.5),
        supply=schema.Supply(const=schema.SupplyConst(prod_area_rate_kg_m2_s=5e-7)),
        io=schema.IO(outdir=tmp_path),
    )

    run.run_zero_d(cfg)

    df = pd.read_parquet(Path(tmp_path) / "series" / "run.parquet")
    assert len(df) == 3  # short integration over three steps

    mass_sum = (
        df["mass_total_bins"]
        + df["mass_lost_by_sinks"]
        + df["mass_lost_by_blowout"]
    )
    np.testing.assert_allclose(
        mass_sum,
        cfg.initial.mass_total,
        rtol=0.0,
        atol=1e-18,
    )

    # Blowout判定は有効であることを確認する（質量流出がゼロでもケースは blowout 扱い）。
    summary = json.loads((Path(tmp_path) / "summary.json").read_text())
    assert summary["case_status"] == "blowout"
    assert summary.get("sinks_active", False) is True
