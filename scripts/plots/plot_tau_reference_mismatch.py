#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk.io import tables
from marsdisk.physics import shielding


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Visualize the mismatch between tau0_target and mu_reference_tau via "
            "sigma_ref/Sigma_surf0 and kappa_eff0/kappa_eff_ref ratios."
        )
    )
    parser.add_argument(
        "--tau0-min",
        type=float,
        default=1.0e-2,
        help="Minimum tau0_target value (log-spaced).",
    )
    parser.add_argument(
        "--tau0-max",
        type=float,
        default=1.0e2,
        help="Maximum tau0_target value (log-spaced).",
    )
    parser.add_argument(
        "--mu-min",
        type=float,
        default=1.0e-2,
        help="Minimum mu_reference_tau value (log-spaced).",
    )
    parser.add_argument(
        "--mu-max",
        type=float,
        default=1.0e2,
        help="Maximum mu_reference_tau value (log-spaced).",
    )
    parser.add_argument(
        "--grid",
        type=int,
        default=120,
        help="Number of grid points per axis.",
    )
    parser.add_argument(
        "--phi-table",
        type=str,
        default=None,
        help="Optional tau-only Phi(tau) table (CSV with tau,phi).",
    )
    parser.add_argument(
        "--w0",
        type=float,
        default=0.5,
        help="Single-scattering albedo w0 for full Phi table (ignored with --phi-table).",
    )
    parser.add_argument(
        "--g",
        type=float,
        default=0.0,
        help="Asymmetry parameter g for full Phi table (ignored with --phi-table).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="out/figures/tau_reference_mismatch.png",
        help="Output image path.",
    )
    return parser


def _phi_fn(phi_table: str | None, w0: float, g: float):
    if phi_table:
        return shielding.load_phi_table(Path(phi_table))

    def _phi_full(tau: float) -> float:
        return tables.interp_phi(float(tau), float(w0), float(g))

    return _phi_full


def _logspace(min_val: float, max_val: float, n: int) -> np.ndarray:
    if min_val <= 0.0 or max_val <= 0.0:
        raise ValueError("tau ranges must be positive for log spacing")
    return np.logspace(np.log10(min_val), np.log10(max_val), n)


def _compute_ratios(
    tau0_vals: np.ndarray,
    mu_vals: np.ndarray,
    phi_fn,
) -> tuple[np.ndarray, np.ndarray]:
    phi_vec = np.vectorize(phi_fn, otypes=[float])
    phi_tau0 = phi_vec(tau0_vals)
    phi_mu = phi_vec(mu_vals)

    eps = 1.0e-12
    phi_tau0 = np.clip(phi_tau0, eps, 1.0)
    phi_mu = np.clip(phi_mu, eps, 1.0)

    kappa_ratio = phi_tau0[None, :] / phi_mu[:, None]
    sigma_ratio = (mu_vals[:, None] / tau0_vals[None, :]) * kappa_ratio
    return sigma_ratio, kappa_ratio


def _plot_heatmap(ax, x_vals, y_vals, log_ratio, title, cmap="coolwarm"):
    norm = TwoSlopeNorm(vcenter=0.0, vmin=np.nanmin(log_ratio), vmax=np.nanmax(log_ratio))
    mesh = ax.pcolormesh(x_vals, y_vals, log_ratio, shading="auto", cmap=cmap, norm=norm)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_xlabel("tau0_target")
    ax.set_ylabel("mu_reference_tau")
    return mesh


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    tau0_vals = _logspace(args.tau0_min, args.tau0_max, args.grid)
    mu_vals = _logspace(args.mu_min, args.mu_max, args.grid)

    phi_fn = _phi_fn(args.phi_table, args.w0, args.g)
    sigma_ratio, kappa_ratio = _compute_ratios(tau0_vals, mu_vals, phi_fn)

    log_sigma = np.log10(sigma_ratio)
    log_kappa = np.log10(kappa_ratio)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    m1 = _plot_heatmap(
        axes[0],
        tau0_vals,
        mu_vals,
        log_sigma,
        "log10(sigma_ref / Sigma_surf0)",
    )
    m2 = _plot_heatmap(
        axes[1],
        tau0_vals,
        mu_vals,
        log_kappa,
        "log10(kappa_eff0 / kappa_eff_ref)",
    )

    diag_min = max(args.tau0_min, args.mu_min)
    diag_max = min(args.tau0_max, args.mu_max)
    if diag_min < diag_max:
        diag = np.logspace(np.log10(diag_min), np.log10(diag_max), 200)
        for ax in axes:
            ax.plot(diag, diag, color="black", linestyle="--", linewidth=1.0, alpha=0.8)

    fig.colorbar(m1, ax=axes[0], shrink=0.9)
    fig.colorbar(m2, ax=axes[1], shrink=0.9)

    if args.phi_table:
        phi_label = f"phi_table={args.phi_table}"
    else:
        phi_label = f"phi_mode=full_table w0={args.w0:.2f} g={args.g:.2f}"
    fig.suptitle(
        f"tau0_target vs mu_reference_tau mismatch ({phi_label})",
        fontsize=10,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
