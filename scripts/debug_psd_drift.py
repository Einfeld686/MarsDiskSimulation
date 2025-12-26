from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from marsdisk.physics import psd


def _reference_rebin_dnds(
    psd_state: dict[str, np.ndarray | float],
    *,
    ds_dt: float,
    dt: float,
    floor: float,
) -> tuple[np.ndarray, np.ndarray]:
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    edges = np.asarray(psd_state["edges"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)

    ds_step = float(ds_dt * dt)
    counts = number * widths
    new_counts = np.zeros_like(counts)
    accum_sizes = np.zeros_like(counts)
    for idx, count in enumerate(counts):
        if count <= 0.0 or not np.isfinite(count):
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor:
            s_new = floor
        target = int(np.searchsorted(edges, s_new, side="right") - 1)
        target = max(0, min(target, new_counts.size - 1))
        new_counts[target] += count
        accum_sizes[target] += count * s_new

    new_sizes = sizes.copy()
    mask = new_counts > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_counts[mask]
    new_sizes = np.maximum(new_sizes, float(floor))
    new_number = np.zeros_like(number)
    new_number[mask] = new_counts[mask] / widths[mask]

    tmp_state = {"sizes": new_sizes, "widths": widths, "number": new_number}
    psd.sanitize_and_normalize_number(tmp_state)
    return np.asarray(tmp_state["number"], dtype=float), np.asarray(tmp_state["sizes"], dtype=float)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Debug PSD size drift rebinning.")
    parser.add_argument("--s-min", type=float, default=1.0e-6)
    parser.add_argument("--s-max", type=float, default=1.0e-5)
    parser.add_argument("--n-bins", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=1.7)
    parser.add_argument("--wavy-strength", type=float, default=0.0)
    parser.add_argument("--rho", type=float, default=3000.0)
    parser.add_argument("--ds-dt", type=float, default=1.0e-6)
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--floor", type=float, default=5.0e-7)
    parser.add_argument("--sigma-surf", type=float, default=1.0)
    parser.add_argument("--force-numpy", action="store_true", help="Disable numba path for PSD drift.")
    parser.add_argument("--outdir", type=Path, default=Path("out/debug_psd_drift"))
    args = parser.parse_args(argv)

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    psd_state = psd.update_psd_state(
        s_min=args.s_min,
        s_max=args.s_max,
        alpha=args.alpha,
        wavy_strength=args.wavy_strength,
        n_bins=args.n_bins,
        rho=args.rho,
    )
    psd.sanitize_and_normalize_number(psd_state, normalize=False)

    if args.force_numpy:
        psd._USE_NUMBA = False
        psd._NUMBA_FAILED = False

    number_ref, sizes_ref = _reference_rebin_dnds(
        psd_state, ds_dt=args.ds_dt, dt=args.dt, floor=args.floor
    )

    working = {k: np.array(v, copy=True) if isinstance(v, np.ndarray) else v for k, v in psd_state.items()}
    sigma_new, delta_sigma, diag = psd.apply_uniform_size_drift(
        working,
        ds_dt=args.ds_dt,
        dt=args.dt,
        floor=args.floor,
        sigma_surf=args.sigma_surf,
    )

    sizes_before = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number_before = np.asarray(psd_state["number"], dtype=float)
    number_impl = np.asarray(working["number"], dtype=float)
    sizes_impl = np.asarray(working["sizes"], dtype=float)

    counts_before = number_before * widths
    counts_impl = number_impl * widths
    counts_ref = number_ref * widths

    diff_number = number_impl - number_ref
    diff_sizes = sizes_impl - sizes_ref
    with np.errstate(divide="ignore", invalid="ignore"):
        rel_number = np.where(number_ref != 0.0, diff_number / number_ref, np.nan)

    df = pd.DataFrame(
        {
            "size_before_m": sizes_before,
            "size_impl_m": sizes_impl,
            "size_ref_m": sizes_ref,
            "width_m": widths,
            "number_before": number_before,
            "number_impl": number_impl,
            "number_ref": number_ref,
            "count_before": counts_before,
            "count_impl": counts_impl,
            "count_ref": counts_ref,
            "diff_number": diff_number,
            "rel_diff_number": rel_number,
            "diff_size_m": diff_sizes,
        }
    )
    df.to_csv(outdir / "psd_drift_bins.csv", index=False)

    summary = {
        "s_min": args.s_min,
        "s_max": args.s_max,
        "n_bins": args.n_bins,
        "alpha": args.alpha,
        "wavy_strength": args.wavy_strength,
        "rho": args.rho,
        "ds_dt": args.ds_dt,
        "dt": args.dt,
        "floor": args.floor,
        "sigma_surf": args.sigma_surf,
        "sigma_new": sigma_new,
        "delta_sigma": delta_sigma,
        "mass_ratio_impl": diag.get("mass_ratio"),
        "max_abs_diff_number": float(np.nanmax(np.abs(diff_number))),
        "max_rel_diff_number": float(np.nanmax(np.abs(rel_number))),
        "max_abs_diff_size": float(np.max(np.abs(diff_sizes))),
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
