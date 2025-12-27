from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk import constants, grid, run, schema
from marsdisk.physics import psd, radiation


def _build_config(outdir: Path, *, chi_blow: float, tm_k: float, q_pr: float, s_min: float, s_max: float, n_bins: int) -> schema.Config:
    cfg = schema.Config(
        geometry=schema.Geometry(mode="0D"),
        disk=schema.Disk(
            geometry=schema.DiskGeometry(
                r_in_RM=2.5,
                r_out_RM=2.5,
                r_profile="uniform",
                p_index=0.0,
            )
        ),
        material=schema.Material(rho=3000.0),
        radiation=schema.Radiation(TM_K=tm_k, Q_pr=q_pr),
        sizes=schema.Sizes(s_min=s_min, s_max=s_max, n_bins=n_bins),
        initial=schema.Initial(mass_total=1.0e-10, s0_mode="upper"),
        dynamics=schema.Dynamics(e0=1.0e-4, i0=5.0e-5, t_damp_orbits=1.0e3, f_wake=1.0),
        psd=schema.PSD(alpha=1.7, wavy_strength=0.0),
        qstar=schema.QStar(Qs=1.0e5, a_s=0.1, B=0.3, b_g=1.36, v_ref_kms=[1.0, 2.0]),
        numerics=schema.Numerics(t_end_years=1.0e-4, dt_init=200.0),
        supply=schema.Supply(
            mode="const",
            const=schema.SupplyConst(prod_area_rate_kg_m2_s=0.0),
            mixing=schema.SupplyMixing(epsilon_mix=1.0),
        ),
        io=schema.IO(outdir=outdir, quiet=True),
    )
    cfg.sinks.mode = "none"
    cfg.surface.collision_solver = "smol"
    cfg.chi_blow = chi_blow
    return cfg


def _first_positive(series: pd.Series) -> float:
    values = series.to_numpy()
    for value in values:
        if value > 0.0 and np.isfinite(value):
            return float(value)
    return float(values[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Debug chi_blow scaling in Smol blowout.")
    parser.add_argument("--chi-fast", type=float, default=0.5)
    parser.add_argument("--chi-slow", type=float, default=2.0)
    parser.add_argument("--tm-k", type=float, default=4000.0)
    parser.add_argument("--q-pr", type=float, default=1.0)
    parser.add_argument("--s-min", type=float, default=1.0e-8)
    parser.add_argument("--s-max", type=float, default=1.0e-4)
    parser.add_argument("--n-bins", type=int, default=24)
    parser.add_argument("--outdir", type=Path, default=Path("out/debug_blowout_chi"))
    parser.add_argument("--skip-run", action="store_true", help="Skip run_zero_d and only emit PSD/blowout diagnostics.")
    args = parser.parse_args(argv)

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    r = 2.5 * constants.R_MARS
    Omega = grid.omega_kepler(r)

    a_blow = radiation.blowout_radius(3000.0, args.tm_k, Q_pr=args.q_pr)
    s_min_effective = max(args.s_min, a_blow)
    psd_state = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=args.s_max,
        alpha=1.7,
        wavy_strength=0.0,
        n_bins=args.n_bins,
        rho=3000.0,
    )
    edges = np.asarray(psd_state["edges"], dtype=float)
    centers = np.asarray(psd_state["sizes"], dtype=float)
    n_edges_blow = int(np.sum(edges[:-1] <= a_blow))
    n_centers_blow = int(np.sum(centers <= a_blow))

    summary = {
        "tm_k": args.tm_k,
        "q_pr": args.q_pr,
        "a_blow_m": float(a_blow),
        "s_min_config": args.s_min,
        "s_min_effective": float(s_min_effective),
        "n_bins": args.n_bins,
        "edge0_m": float(edges[0]),
        "center0_m": float(centers[0]),
        "n_edges_blowout": n_edges_blow,
        "n_centers_blowout": n_centers_blow,
        "Omega": float(Omega),
    }

    if not args.skip_run:
        cfg_fast = _build_config(outdir / "chi_fast", chi_blow=args.chi_fast, tm_k=args.tm_k, q_pr=args.q_pr, s_min=args.s_min, s_max=args.s_max, n_bins=args.n_bins)
        cfg_slow = _build_config(outdir / "chi_slow", chi_blow=args.chi_slow, tm_k=args.tm_k, q_pr=args.q_pr, s_min=args.s_min, s_max=args.s_max, n_bins=args.n_bins)

        run.run_zero_d(cfg_fast)
        run.run_zero_d(cfg_slow)

        series_fast = pd.read_parquet(Path(cfg_fast.io.outdir) / "series" / "run.parquet")
        series_slow = pd.read_parquet(Path(cfg_slow.io.outdir) / "series" / "run.parquet")

        rate_fast = _first_positive(series_fast["dSigma_dt_blowout"])
        rate_slow = _first_positive(series_slow["dSigma_dt_blowout"])

        summary.update(
            {
                "rate_fast_first_positive": rate_fast,
                "rate_slow_first_positive": rate_slow,
                "rate_ratio_fast_over_slow": rate_fast / rate_slow if rate_slow > 0.0 else float("nan"),
                "chi_fast": args.chi_fast,
                "chi_slow": args.chi_slow,
            }
        )

        series_fast[["time", "dSigma_dt_blowout", "blowout_beta_gate"]].to_csv(
            outdir / "series_fast.csv", index=False
        )
        series_slow[["time", "dSigma_dt_blowout", "blowout_beta_gate"]].to_csv(
            outdir / "series_slow.csv", index=False
        )

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
