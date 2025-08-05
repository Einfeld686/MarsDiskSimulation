#!/usr/bin/env python
"""拡張版の静的マップ生成スクリプト.

Dohnanyi 分布に基づき吹き飛ばし質量分率 F_blow、
放射圧除去質量比 η_loss、光学厚さ低下率 R_tau を算出する。

参照式
  • Dohnanyi (1969)      … サイズ分布 q=3.5
  • Burns et al. (1979)  … β⊙, P-R 式
  • Wyatt (2005)         … τ, t_col
  • Strubbe & Chiang (2006) … τ_eff/τ_0 評価
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import colors

# 既存関数・定数を再利用
from static_map import (
    G,
    c,
    sigma_SB,
    AU,
    M_MARS,
    R_MARS,
    M_SUN,
    A_MARS,
    SECONDS_PER_YEAR,
    beta_sun,
    beta_sun_to_mars,
    beta_mars,
    optical_depth,
    omega_kepler,
    t_collision,
    t_PR,
    t_PR_mars,
)


# ── 追加関数 ──────────────────────────────
def norm_const_dohnanyi(Sigma, rho, a_min, a_max, q=3.5):
    """Dohnanyi 分布の正規化係数 C を返す."""
    k = (4 * np.pi * rho / 3) * (a_max ** (4 - q) - a_min ** (4 - q)) / (4 - q)
    return Sigma / k  # n(a)=C a^{-q}


def mass_fraction_blowout(C, rho, a_min, a_bl, a_max, q=3.5):
    """吹き飛ばしで失われる質量分率 F_blow."""
    num = a_bl ** (4 - q) - a_min ** (4 - q)
    den = a_max ** (4 - q) - a_min ** (4 - q)
    return num / den


def tau_integral(C, a1, a2, q=3.5):
    """∫_{a1}^{a2} π a² n(a) da （解析解）."""
    return C * np.pi * (a2 ** (3 - q) - a1 ** (3 - q)) / (3 - q)


# ── CLI ────────────────────────────────────
def parse_args():
    """CLI パラメータの構築."""
    p = argparse.ArgumentParser()
    p.add_argument("--T_mars", type=float, default=3000,
                   help="有効温度 [K] (例: 3000)")
    p.add_argument("--r_disk", type=float, default=2 * R_MARS,
                   help="評価半径 [m] (例: 2*R_MARS)")
    p.add_argument("--rho", type=float, default=3000,
                   help="粒子密度 [kg m^-3]")
    p.add_argument("--qpr", type=float, default=1.0,
                   help="放射圧係数 Q_pr")
    p.add_argument("--include_mars_pr", choices=["yes", "no"],
                   default="yes",
                   help="火星起源 PR を t_PR に含めるか (yes/no)")
    p.add_argument("--Sigma_min", type=float, default=1e2,
                   help="表面密度下限 [kg m^-2]")
    p.add_argument("--Sigma_max", type=float, default=1e6,
                   help="表面密度上限 [kg m^-2]")
    p.add_argument("--n_s", type=int, default=400)
    p.add_argument("--n_sigma", type=int, default=400)
    p.add_argument("--a_min", type=float, default=1e-7,
                   help="最小粒径 [m]")
    p.add_argument("--a_max", type=float, default=1e-1,
                   help="最大粒径 [m]")
    p.add_argument("--q", type=float, default=3.5,
                   help="Dohnanyi 分布指数")
    p.add_argument("--t_sim", type=float, default=1e4,
                   help="質量損失評価用シミュレーション時間 [yr]")
    return p.parse_args()


# ── メイン計算 ───────────────────────────
def calc_maps(args):
    """3 種の指標マップを計算し CSV/PNG を出力する."""
    s_vals = np.logspace(np.log10(args.a_min), np.log10(args.a_max), args.n_s)
    Sigma_vals = np.logspace(np.log10(args.Sigma_min),
                             np.log10(args.Sigma_max), args.n_sigma)
    S, SIG = np.meshgrid(s_vals, Sigma_vals)

    beta_sun0 = beta_sun(S, args.rho)
    beta_sun_m = beta_sun_to_mars(S, args.rho, args.r_disk)
    beta_m = beta_mars(S, args.rho, args.T_mars, args.qpr)
    beta_eff = beta_sun_m + beta_m
    tau_geo = optical_depth(S, SIG, args.rho)

    t_col = t_collision(S, SIG, args.rho, args.r_disk) / SECONDS_PER_YEAR
    t_pr_sun = t_PR(S, args.rho, beta_sun0)
    if args.include_mars_pr == "yes":
        t_pr_m = t_PR_mars(S, args.rho, args.T_mars, args.qpr, args.r_disk)
        t_pr_total = 1 / (1 / t_pr_sun + 1 / t_pr_m)
    else:
        t_pr_total = t_pr_sun

    ratio = np.log10(t_pr_total / t_col)

    # Dohnanyi 分布に基づく各指標
    C = norm_const_dohnanyi(SIG, args.rho, args.a_min, args.a_max, args.q)
    a_bl = 5.7e-4 / (0.5 * args.rho) * (M_SUN / M_MARS) * (args.r_disk / A_MARS) ** 2
    a_bl_eff = max(a_bl, args.a_min)
    F_blow = mass_fraction_blowout(C, args.rho, args.a_min, a_bl_eff, args.a_max, args.q)
    F_blow = np.clip(F_blow, 0, 1)
    F_blow = np.full_like(S, F_blow)  # マップ用に 2D 化
    eta_loss = 1 - np.exp(-args.t_sim / t_col)
    tau0 = tau_integral(C, args.a_min, args.a_max, args.q)
    tau_eff = tau_integral(C, a_bl_eff, args.a_max, args.q)
    R_tau = tau_eff / tau0

    # ── 描画 ──────────────────────────────
    with np.errstate(divide="ignore"):
        logS = np.log10(S)
        logSIG = np.log10(SIG)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=True, sharey=True)
    data_list = [F_blow, eta_loss, R_tau]
    norms = [colors.Normalize(0, 0.1),
             colors.Normalize(0, 1),
             colors.Normalize(0, 1)]
    labels = [r"$F_{\rm blow}$",
              r"$\eta_{\rm loss}$",
              r"$R_{\tau}$"]
    titles = ["吹き飛ばし質量分率",
              "放射圧除去質量比",
              "光学厚さ低下率"]

    for ax, data, norm, lab, title in zip(axes, data_list, norms, labels, titles):
        pcm = ax.pcolormesh(logS, logSIG, data, cmap="RdYlBu",
                            norm=norm, shading="auto")
        fig.colorbar(pcm, ax=ax, label=lab)
        ax.contour(logS, logSIG, tau_geo, levels=[1], colors="white",
                   linestyles="--", linewidths=1)
        ax.contour(logS, logSIG, beta_eff, levels=[0.5], colors="red", linewidths=1)
        ax.contour(logS, logSIG, ratio, levels=[0], colors="cyan",
                   linestyles="-.", linewidths=1)
        ax.set_title(title)
        ax.set_xlabel(r"$\log_{10} a_{\rm rep}$ [m]")
    axes[0].set_ylabel(r"$\log_{10} \Sigma$ [kg m$^{-2}$]")

    pr_tag = "+MarsPR" if args.include_mars_pr == "yes" else ""
    os.makedirs("output", exist_ok=True)
    plt.tight_layout()
    plt.savefig(f"output/extended_maps{pr_tag}.png", dpi=300)
    plt.close(fig)

    # ── CSV 出力 ──────────────────────────
    df = pd.DataFrame({
        "a_rep_m": S.ravel(),
        "Sigma_kg_m2": SIG.ravel(),
        "tau": tau_geo.ravel(),
        "beta_sun_mars": beta_sun_m.ravel(),
        "beta_mars": beta_m.ravel(),
        "beta_eff": beta_eff.ravel(),
        "t_col_yr": t_col.ravel(),
        "t_PR_total_yr": t_pr_total.ravel(),
        "log10_ratio": ratio.ravel(),
        "F_blow": F_blow.ravel(),
        "eta_loss": eta_loss.ravel(),
        "R_tau": R_tau.ravel(),
    })
    df.to_csv("output/extended_disk_map.csv", index=False)
    return df


if __name__ == "__main__":
    args = parse_args()
    calc_maps(args)
