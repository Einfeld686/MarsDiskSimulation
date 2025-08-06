#!/usr/bin/env python
"""拡張版の静的マップ：質量-光学深さマップを生成する."""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from static_map import (
    G,
    c,
    sigma_SB,
    AU,
    M_MARS,
    R_MARS,
    M_SUN,
    A_MARS,
    kappa_mass_averaged,
)
from timescales import collision_timescale_years


# --- 既存ロジックの関数群 ----------------------------------------------
def blowout_radius(
    rho,
    qpr=1.0,
    r_disk_Rmars=1.0,
    T_mars=3000,
    include_mars_pr=False,
    beta_crit=0.5,
):
    """ブローアウト粒径 [m] を計算する."""

    a_sun = 5.7e-4 * qpr / (beta_crit * rho)
    if not include_mars_pr:
        return a_sun

    r_m = r_disk_Rmars * R_MARS
    L_mars = 4 * np.pi * R_MARS**2 * sigma_SB * T_mars**4
    K_mars = (3 * L_mars * qpr) / (16 * np.pi * G * M_MARS * c)
    K_sun = 5.7e-4 * qpr * (M_SUN / M_MARS) * (r_m / A_MARS) ** 2
    return (K_sun + K_mars) / (beta_crit * rho)


def mass_fraction_blowout_map(S, SIG, rho, a_min, a_bl, a_max, q, t_sim, t_col):
    """吹き飛ばし質量分率 :math:`F_{\rm blow}` を返す."""

    f_mass = (a_bl ** (4 - q) - a_min ** (4 - q)) / (
        a_max ** (4 - q) - a_min ** (4 - q)
    )

    F_blow = f_mass * (1.0 - np.exp(-t_sim / t_col))
    return np.clip(F_blow, 0.0, 1.0)


# --- 新規関数 ----------------------------------------------------------
def sigma_from_mass(M_disk_Mm, area_m2):
    return M_disk_Mm * M_MARS / area_m2  # kg m^-2


def annulus_area(args):
    return 2 * np.pi * args.r_disk * R_MARS * args.dr_fixed * R_MARS


def disk_area(args, M_disk_Mm):
    r_in = R_MARS
    r_out = args.r_disk * R_MARS
    p = args.p_outer
    denom = 2 * np.pi * (r_out ** (2 - p) - r_in ** (2 - p)) / (2 - p)
    C = (M_disk_Mm * M_MARS) / denom
    sigma_r = C * (r_out ** (-p))
    return (M_disk_Mm * M_MARS) / sigma_r


def blowout_and_tcol(Sigma, a_bl, args):
    r_m = args.r_disk * R_MARS
    t_col = collision_timescale_years(a_bl, Sigma, args.rho, r_m)
    a_min = 0.05 * a_bl
    f_mass = (a_bl ** (4 - args.q) - a_min ** (4 - args.q)) / (
        args.a_max ** (4 - args.q) - a_min ** (4 - args.q)
    )
    F_blow = f_mass * (1.0 - np.exp(-args.t_sim / t_col))
    return np.clip(F_blow, 0.0, 1.0), t_col


def parse_args():
    import argparse, textwrap

    p = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """
        Create a mass–optical‑depth map (M–τ) with blow‑out fraction colouring.
        """
        ),
    )
    # 質量軸パラメータ
    p.add_argument("--M_min", type=float, default=1e-9, help="Min disk mass [M_M]")
    p.add_argument("--M_max", type=float, default=1e-5, help="Max disk mass [M_M]")
    p.add_argument("--n_M", type=int, default=50, help="Number of mass bins")
    # 面積モード
    p.add_argument(
        "--area_mode",
        choices=["annulus", "disk"],
        default="annulus",
        help="annulus: use r_disk & dr_fixed; disk: integrate piece‑wise profile",
    )
    p.add_argument(
        "--r_disk",
        type=float,
        default=5.0,
        help="Annulus centre radius [R_MARS] (area_mode=annulus)",
    )
    p.add_argument(
        "--dr_fixed",
        type=float,
        default=1.0,
        help="Annulus width [R_MARS] (area_mode=annulus)",
    )
    p.add_argument(
        "--p_outer",
        type=float,
        default=5.0,
        help="Sigma ∝ r^{-p} (area_mode=disk)",
    )

    # 物理パラメータ（既存を存続）
    p.add_argument("--rho", type=float, default=3000)
    p.add_argument("--q", type=float, default=3.5)
    p.add_argument("--a_max", type=float, default=0.1)
    p.add_argument("--T_mars", type=float, default=250)
    p.add_argument("--qpr", type=float, default=1.0)
    p.add_argument("--include_mars_pr", action="store_true")
    p.add_argument("--t_sim", type=float, default=100.0)
    return p.parse_args()


def calc_mass_tau_map(args):
    M_vals = np.logspace(np.log10(args.M_min), np.log10(args.M_max), args.n_M)
    tau_arr, Fb_arr, tcol_arr = [], [], []
    for M in M_vals:
        if args.area_mode == "annulus":
            area = annulus_area(args)
        else:
            area = disk_area(args, M)
        Sigma = sigma_from_mass(M, area)
        a_bl = blowout_radius(
            args.rho,
            args.qpr,
            args.r_disk,
            args.T_mars,
            args.include_mars_pr,
        )
        a_min = 0.05 * a_bl
        kappa = kappa_mass_averaged(args.q, a_min, args.a_max, args.rho)
        tau = kappa * Sigma
        F_blow, t_col = blowout_and_tcol(Sigma, a_bl, args)
        tau_arr.append(tau)
        Fb_arr.append(F_blow)
        tcol_arr.append(t_col)

    fig, ax = plt.subplots(figsize=(6, 5))
    sc = ax.scatter(
        np.log10(tau_arr), np.log10(M_vals), c=Fb_arr, cmap="viridis", vmin=0, vmax=1
    )
    ax.set_xlabel(r"$\log_{10}\tau$")
    ax.set_ylabel(r"$\log_{10}\,M_{\rm disk}/M_{\rm M}$")
    fig.colorbar(sc, label=r"$F_{\rm blow}$")
    os.makedirs("output", exist_ok=True)
    fig.tight_layout()
    fig.savefig("output/mass_tau_map.png")
    plt.close(fig)
    pd.DataFrame(
        {
            "M_disk[M_M]": M_vals,
            "tau": tau_arr,
            "F_blow": Fb_arr,
            "t_col[yr]": tcol_arr,
        }
    ).to_csv("output/mass_tau_map.csv", index=False)


def main():
    args = parse_args()
    calc_mass_tau_map(args)


if __name__ == "__main__":
    main()

