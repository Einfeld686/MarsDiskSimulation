from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk.physics import collisions_smol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Debug powerlaw supply injection slope.")
    parser.add_argument("--s-min", type=float, default=1.0e-6)
    parser.add_argument("--s-max", type=float, default=1.0e-4)
    parser.add_argument("--n-bins", type=int, default=12)
    parser.add_argument("--rho", type=float, default=3000.0)
    parser.add_argument("--prod-rate", type=float, default=1.0e-9)
    parser.add_argument("--q", type=float, default=3.5)
    parser.add_argument("--s-inj-min", type=float, default=None)
    parser.add_argument("--s-inj-max", type=float, default=None)
    parser.add_argument("--outdir", type=Path, default=Path("out/debug_supply_powerlaw"))
    args = parser.parse_args(argv)

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    edges = np.geomspace(args.s_min, args.s_max, args.n_bins + 1)
    sizes = np.sqrt(edges[:-1] * edges[1:])
    widths = edges[1:] - edges[:-1]
    m_bin = (4.0 / 3.0) * np.pi * args.rho * sizes**3

    s_inj_min = args.s_inj_min if args.s_inj_min is not None else args.s_min
    s_inj_max = args.s_inj_max if args.s_inj_max is not None else args.s_max

    source = collisions_smol.supply_mass_rate_to_number_source(
        args.prod_rate,
        sizes,
        m_bin,
        s_min_eff=args.s_min,
        widths=widths,
        mode="powerlaw_bins",
        s_inj_min=s_inj_min,
        s_inj_max=s_inj_max,
        q=args.q,
    )

    dnds = np.where(widths > 0.0, source / widths, 0.0)
    dmds = np.where(widths > 0.0, source * m_bin / widths, 0.0)
    mask = dnds > 0.0
    slope_dnds = float("nan")
    slope_dmds = float("nan")
    if np.sum(mask) >= 2:
        slope_dnds, intercept_dnds = np.polyfit(np.log(sizes[mask]), np.log(dnds[mask]), 1)
        slope_dmds, intercept_dmds = np.polyfit(np.log(sizes[mask]), np.log(dmds[mask]), 1)
    else:
        intercept_dnds = float("nan")
        intercept_dmds = float("nan")

    df = pd.DataFrame(
        {
            "size_m": sizes,
            "width_m": widths,
            "mass_kg": m_bin,
            "source_1_s": source,
            "dnds_1_m_s": dnds,
            "dmds_kg_m_s": dmds,
            "log_size": np.log(sizes),
            "log_dnds": np.where(dnds > 0.0, np.log(dnds), np.nan),
            "log_dmds": np.where(dmds > 0.0, np.log(dmds), np.nan),
        }
    )
    df.to_csv(outdir / "powerlaw_injection_bins.csv", index=False)

    summary = {
        "s_min": args.s_min,
        "s_max": args.s_max,
        "n_bins": args.n_bins,
        "rho": args.rho,
        "prod_rate": args.prod_rate,
        "q": args.q,
        "s_inj_min": s_inj_min,
        "s_inj_max": s_inj_max,
        "slope_dnds": slope_dnds,
        "intercept_dnds": intercept_dnds,
        "slope_dmds": slope_dmds,
        "intercept_dmds": intercept_dmds,
        "nonzero_bins": int(np.sum(mask)),
        "mass_rate_check": float(np.sum(source * m_bin)),
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
