from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk.physics import collisions_smol, fragments, qstar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Debug fragment tensor largest-remnant mapping.")
    parser.add_argument("--s-min", type=float, default=1.0e-6)
    parser.add_argument("--s-max", type=float, default=4.0e-6)
    parser.add_argument("--n-bins", type=int, default=3)
    parser.add_argument("--rho", type=float, default=3000.0)
    parser.add_argument("--alpha-frag", type=float, default=3.5)
    parser.add_argument("--v-rel", type=str, default="3000,5000,7000")
    parser.add_argument("--use-numba", action="store_true")
    parser.add_argument("--outdir", type=Path, default=Path("out/debug_fragment_tensor"))
    args = parser.parse_args(argv)

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    edges = np.geomspace(args.s_min, args.s_max, args.n_bins + 1)
    sizes = np.sqrt(edges[:-1] * edges[1:])
    widths = edges[1:] - edges[:-1]
    masses = (4.0 / 3.0) * np.pi * args.rho * sizes**3

    v_list = [float(item.strip()) for item in args.v_rel.split(",") if item.strip()]
    rows = []
    summary_rows = []

    for v_rel in v_list:
        v_matrix = np.full((sizes.size, sizes.size), float(v_rel))
        q_star = qstar.compute_q_d_star_array(np.maximum.outer(sizes, sizes), args.rho, v_matrix / 1.0e3)
        q_r = fragments.q_r_array(masses[:, None], masses[None, :], v_matrix)
        f_lr = fragments.largest_remnant_fraction_array(q_r, q_star)

        Y = collisions_smol._fragment_tensor(
            sizes,
            masses,
            edges,
            float(v_rel),
            args.rho,
            alpha_frag=args.alpha_frag,
            use_numba=args.use_numba,
        )

        diff_lr = []
        diff_sum = []
        for i in range(sizes.size):
            for j in range(sizes.size):
                k_lr = max(i, j)
                y_lr = float(Y[k_lr, i, j])
                f_lr_val = float(f_lr[i, j])
                y_sum = float(np.sum(Y[:, i, j]))
                rows.append(
                    {
                        "v_rel_m_s": float(v_rel),
                        "i": i,
                        "j": j,
                        "k_lr": k_lr,
                        "f_lr": f_lr_val,
                        "y_lr": y_lr,
                        "y_lr_minus_f_lr": y_lr - f_lr_val,
                        "y_sum": y_sum,
                        "y_sum_minus_1": y_sum - 1.0,
                    }
                )
                diff_lr.append(abs(y_lr - f_lr_val))
                diff_sum.append(abs(y_sum - 1.0))

        summary_rows.append(
            {
                "v_rel_m_s": float(v_rel),
                "max_abs_y_lr_minus_f_lr": float(np.max(diff_lr)) if diff_lr else 0.0,
                "max_abs_y_sum_minus_1": float(np.max(diff_sum)) if diff_sum else 0.0,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(outdir / "fragment_tensor_pairs.csv", index=False)
    summary = {
        "s_min": args.s_min,
        "s_max": args.s_max,
        "n_bins": args.n_bins,
        "rho": args.rho,
        "alpha_frag": args.alpha_frag,
        "use_numba": bool(args.use_numba),
        "v_rel_list": v_list,
        "per_v_rel": summary_rows,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
