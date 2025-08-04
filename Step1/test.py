#!/usr/bin/env python
"""
Static τ–β–timescale map around Mars (giant-impact epoch)

参照式
  • Burns et al. (1979)  …… β⊙
  • Hyodo et al. (2018) …β_Mars, 衝突ディスク
  • Wyatt (2005)        …… τ, t_col
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors

# ── physical constants ─────────────────────────
G = 6.67430e-11       # m^3 kg^-1 s^-2
c = 2.99792458e8      # m s^-1
sigma_SB = 5.670374419e-8  # W m^-2 K^-4
AU = 1.496e11         # m

# ── Mars / Sun parameters ──────────────────────
M_MARS = 6.4171e23    # kg
R_MARS = 3.3895e6     # m
M_SUN = 1.9885e30     # kg
A_MARS = 1.52 * AU    # orbital radius of Mars [m]

SECONDS_PER_YEAR = 365.25 * 24 * 3600  # s


def beta_sun(s, rho):
    """Solar radiation pressure parameter β⊙.

    Parameters
    ----------
    s : ndarray
        Particle radius [m].
    rho : float
        Particle density [kg m^-3].

    Returns
    -------
    ndarray
        β⊙ (dimensionless).
    """
    # 出典: Burns+79 Eq.(1)
    return 5.7e-4 / (rho * s)


def beta_sun_to_mars(s, rho, r_disk):
    """Convert β⊙ to the Mars gravity field.

    Parameters
    ----------
    s : ndarray
        Particle radius [m].
    rho : float
        Particle density [kg m^-3].
    r_disk : float
        Disk radius from Mars [m].

    Returns
    -------
    ndarray
        β⊙ relative to Mars (dimensionless).
    """
    # 出典: Burns+79 Eq.(1)
    return beta_sun(s, rho) * (M_SUN / M_MARS) * (r_disk / A_MARS) ** 2


def beta_mars(s, rho, T_mars, Q_pr=1.0):
    """Radiation pressure parameter β_Mars.

    Parameters
    ----------
    s : ndarray
        Particle radius [m].
    rho : float
        Particle density [kg m^-3].
    T_mars : float
        Effective temperature of Mars [K].
    Q_pr : float, optional
        Radiation pressure efficiency, by default 1.

    Returns
    -------
    ndarray
        β_Mars (dimensionless).
    """
    # 出典: Hyodo+18 Eq.(5)
    L_mars = 4 * np.pi * R_MARS ** 2 * sigma_SB * T_mars ** 4
    return (3 * L_mars * Q_pr) / (16 * np.pi * G * M_MARS * c * rho * s)


def optical_depth(s, Sigma, rho):
    """Geometric optical depth τ_geo.

    Parameters
    ----------
    s : ndarray
        Particle radius meshgrid [m].
    Sigma : ndarray
        Surface density meshgrid [kg m^-2].
    rho : float
        Particle density [kg m^-3].

    Returns
    -------
    ndarray
        Geometric optical depth.
    """
    # 出典: Wyatt05 Eq.(6)
    return 3 * Sigma / (4 * rho * s)


def omega_kepler(r_disk):
    """Keplerian angular frequency around Mars.

    Parameters
    ----------
    r_disk : float
        Disk radius from Mars [m].

    Returns
    -------
    float
        Angular frequency [s^-1].
    """
    return np.sqrt(G * M_MARS / r_disk ** 3)


def t_collision(s, Sigma, rho, r_disk):
    """Collision timescale.

    Parameters
    ----------
    s : ndarray
        Particle radius meshgrid [m].
    Sigma : ndarray
        Surface density meshgrid [kg m^-2].
    rho : float
        Particle density [kg m^-3].
    r_disk : float
        Disk radius from Mars [m].

    Returns
    -------
    ndarray
        Collision timescale [s].
    """
    # 出典: Wyatt05 Eq.(16)
    Omega = omega_kepler(r_disk)
    return 4 * rho * s / (3 * Sigma * Omega)


def t_PR(s, rho, beta_sun_val):
    """Poynting–Robertson drag timescale at Mars.

    Parameters
    ----------
    s : ndarray
        Particle radius [m].
    rho : float
        Particle density [kg m^-3].
    beta_sun_val : ndarray
        Solar radiation pressure parameter β⊙.

    Returns
    -------
    ndarray
        P-R drag timescale [yr].
    """
    # 出典: Burns+79 Eq.(3)
    return 400 * (rho / 3000) * (s / 1e-6) * (A_MARS / AU) ** 2 / beta_sun_val


def parse_args():
    """CLI パラメータの構築."""
    p = argparse.ArgumentParser()
    p.add_argument("--T_mars", type=float, default=3000,
                   help="有効温度 [K] (例: 3000)")
    p.add_argument("--r_disk", type=float, default=5 * R_MARS,
                   help="評価半径 [m] (例: 5*R_MARS)")
    p.add_argument("--rho", type=float, default=3000,
                   help="粒子密度 [kg m^-3]")
    p.add_argument("--qpr", type=float, default=1.0,
                   help="放射圧係数 Q_pr")
    p.add_argument("--n_s", type=int, default=400)
    p.add_argument("--n_sigma", type=int, default=400)
    return p.parse_args()


def main():
    """Generate τ–β–timescale map and save CSV/PNG."""
    args = parse_args()

    s_vals = np.logspace(-6, 0, args.n_s)
    Sigma_vals = np.logspace(2, 6, args.n_sigma)
    S, SIG = np.meshgrid(s_vals, Sigma_vals)

    beta_sun0 = beta_sun(S, args.rho)
    beta_sun_m = beta_sun_to_mars(S, args.rho, args.r_disk)
    beta_m = beta_mars(S, args.rho, args.T_mars, args.qpr)
    beta_eff = beta_sun_m + beta_m
    tau = optical_depth(S, SIG, args.rho)

    Omega = omega_kepler(args.r_disk)
    t_col = t_collision(S, SIG, args.rho, args.r_disk) / SECONDS_PER_YEAR
    t_pr = t_PR(S, args.rho, beta_sun0)
    ratio = np.log10(t_pr / t_col)

    fig, ax = plt.subplots(figsize=(8, 6))
    abs_max = np.nanmax(np.abs(ratio))
    norm = colors.TwoSlopeNorm(vcenter=0, vmin=-abs_max, vmax=abs_max)
    pcm = ax.pcolormesh(np.log10(S), np.log10(SIG), ratio,
                        cmap="RdBu", norm=norm, shading="auto")
    fig.colorbar(pcm, ax=ax,
                 label=r"$\log_{10}(t_{\rm PR}/t_{\rm col})$")

    ax.contour(np.log10(S), np.log10(SIG), tau, levels=[1], colors="white",
               linestyles="--", linewidths=1)
    ax.contour(np.log10(S), np.log10(SIG), beta_eff, levels=[0.5],
               colors="red", linewidths=1)
    ax.contour(np.log10(S), np.log10(SIG), ratio, levels=[0],
               colors="cyan", linestyles="-.", linewidths=1)

    ax.set_xlabel(r"$\log_{10} s$ [m]")
    ax.set_ylabel(r"$\log_{10} \Sigma$ [kg m$^{-2}$]")
    ax.set_title("Static timescale map around Mars")

    os.makedirs("output", exist_ok=True)
    plt.savefig("output/map_tau_beta.png", dpi=300)
    plt.close(fig)

    df = pd.DataFrame({
        "s_m": S.ravel(),
        "Sigma_kg_m2": SIG.ravel(),
        "tau": tau.ravel(),
        "beta_sun_mars": beta_sun_m.ravel(),
        "beta_mars": beta_m.ravel(),
        "beta_eff": beta_eff.ravel(),
        "t_col_yr": t_col.ravel(),
        "t_PR_yr": t_pr.ravel(),
        "log10_ratio": ratio.ravel(),
    })
    df.to_csv("output/disk_map.csv", index=False)


if __name__ == "__main__":
    main()
