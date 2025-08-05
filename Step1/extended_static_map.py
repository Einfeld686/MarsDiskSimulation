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

from timescales import (
    convert_sec_to_year,
    collision_timescale,
    pr_timescale_total,
)


def blowout_radius(rho, qpr=1, beta_crit=0.5):  # FIX ブローアウト粒径
    """Burns79 Eq.(1) から β=beta_crit を満たす粒径 [m]"""
    return 5.7e-4 * qpr / (beta_crit * rho)


def norm_const_dohnanyi(Sigma, rho, a_min, a_max, q=3.5):
    """Dohnanyi 分布の正規化係数 C を返す."""
    k = (4 * np.pi * rho / 3) * (a_max ** (4 - q) - a_min ** (4 - q)) / (4 - q)
    return Sigma / k  # n(a)=C a^{-q}


def mass_fraction_blowout_map(S, SIG, rho, a_min, a_bl, a_max, q, t_sim, r_disk):
    r"""Calculate the mass fraction lost by blowout.

    各格子点での吹き飛ばし質量分率 :math:`F_{\rm blow}` を計算する。

    .. math::
        F_{\rm blow} = f_{\rm mass}\left[1-\exp\left(-\frac{t_{\rm sim}}
        {t_{\rm col}(\Sigma, a_{\rm rep})}\right)\right]

    Parameters
    ----------
    S, SIG : ndarray
        Representative grain size and surface density meshgrid /
        代表粒径と表面密度のメッシュグリッド.
    rho : float
        Particle density [kg m^-3] / 粒子密度.
    a_min, a_bl, a_max : float
        Minimum size, blowout size, maximum size [m] /
        サイズ分布下限・ブローアウト粒径・上限 [m].
    q : float
        Power-law index of size distribution / Dohnanyi 分布指数.
    t_sim : float
        Simulation time [yr] / 評価時間 [年].
    r_disk : float
        Disk radius from Mars [m] / 評価半径 [m].

    Returns
    -------
    ndarray
        形状 :code:`(n_\sigma, n_s)` の :math:`F_{\rm blow}` マップ.
    """

    f_mass = (a_bl ** (4 - q) - a_min ** (4 - q)) / (
        a_max ** (4 - q) - a_min ** (4 - q)
    )
    t_col = t_collision(S, SIG, rho, r_disk) / SECONDS_PER_YEAR
    F_blow = f_mass * (1 - np.exp(-t_sim / t_col))
    return np.clip(F_blow, 0.0, 1.0)


def tau_integral(C, a1, a2, q=3.5):
    """∫_{a1}^{a2} π a² n(a) da （解析解）."""
    return C * np.pi * (a2 ** (3 - q) - a1 ** (3 - q)) / (3 - q)


# ── CLI ────────────────────────────────────
def parse_args():
    """CLI パラメータの構築."""
    p = argparse.ArgumentParser()
    p.add_argument(
        "--T_mars",
        type=float,
        default=3000,
        help="有効温度 [K] (例: 3000)",
    )
    p.add_argument(
        "--rho",
        type=float,
        default=3000,
        help="粒子密度 [kg m^-3]",
    )
    p.add_argument(
        "--qpr",
        type=float,
        default=1.0,
        help="放射圧係数 Q_pr",
    )
    p.add_argument(
        "--include_mars_pr",
        choices=["yes", "no"],
        default="no",
        help="火星起源 PR を t_PR に含めるか (yes/no)",
    )
    # ── 半径バッチ処理用パラメータ ──
    p.add_argument(
        "--r_min",
        type=float,
        default=2.6,
        help="解析開始半径 [R_MARS]",
    )
    p.add_argument(
        "--r_max",
        type=float,
        default=10.0,
        help="解析終了半径 [R_MARS]",
    )
    p.add_argument(
        "--dr",
        type=float,
        default=1.0,
        help="半径刻み幅 [R_MARS]",
    )
    p.add_argument(
        "--Sigma0_in",
        type=float,
        default=1e4,
        help="r=r_min における \u03a3_max [kg m^-2]",
    )
    p.add_argument(
        "--gamma",
        type=float,
        default=3.0,
        help="\u03a3(r) = \u03a30 (r/r_min)^{-\u03b3} の指数 \u03b3",
    )
    p.add_argument("--n_s", type=int, default=400)
    p.add_argument("--n_sigma", type=int, default=400)
    p.add_argument(
        "--a_max",
        type=float,
        default=1e-1,
        help="最大粒径 [m]",
    )  # a_min は動的計算
    p.add_argument(
        "--q",
        type=float,
        default=3.5,
        help="Dohnanyi 分布指数",
    )
    p.add_argument(
        "--t_sim",
        type=float,
        default=1e4,
        help="質量損失評価用シミュレーション時間 [yr]",
    )
    return p.parse_args()


# ── メイン計算 ───────────────────────────
def calc_maps(args, suffix=""):
    """3 種の指標マップを計算し CSV/PNG を出力する."""

    a_bl = blowout_radius(args.rho, args.qpr)
    a_min = 0.05 * a_bl
    s_vals = np.logspace(np.log10(a_min), np.log10(args.a_max), args.n_s)
    Sigma_vals = np.logspace(
        np.log10(args.Sigma_min), np.log10(args.Sigma_max), args.n_sigma
    )
    S, SIG = np.meshgrid(s_vals, Sigma_vals)

    beta_sun0 = beta_sun(S, args.rho)
    beta_sun_m = beta_sun_to_mars(S, args.rho, args.r_disk)
    beta_m = beta_mars(S, args.rho, args.T_mars, args.qpr)
    beta_eff = beta_sun_m + beta_m
    tau_geo = optical_depth(S, SIG, args.rho)

    t_col = collision_timescale(S, SIG, args.rho, args.r_disk)
    t_pr_total = pr_timescale_total(
        S,
        args.rho,
        beta_sun0,
        args.include_mars_pr == "yes",
        args.T_mars,
        args.qpr,
        args.r_disk,
    )

    ratio = np.log10(t_pr_total / t_col)

    # Dohnanyi 分布に基づく各指標
    C = norm_const_dohnanyi(Sigma_vals, args.rho, a_min, args.a_max, args.q)
    a_bl_eff = np.maximum(a_bl, a_min)
    F_blow = mass_fraction_blowout_map(
        S, SIG, args.rho, a_min, a_bl_eff, args.a_max, args.q, args.t_sim, args.r_disk
    )
    F_blow = np.clip(F_blow, 0, 1)

    eta_loss = t_pr_total / (t_col + t_pr_total)

    tau0 = tau_integral(C, a_min, args.a_max, args.q)
    tau_eff = tau_integral(C, a_bl_eff, args.a_max, args.q)
    R_tau_scalar = tau_eff / tau0
    R_tau = np.tile(R_tau_scalar[:, None], (1, args.n_s))

    # ── 描画 ──────────────────────────────
    with np.errstate(divide="ignore"):
        logS = np.log10(S)
        logSIG = np.log10(SIG)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=True, sharey=True)
    data_list = [F_blow, eta_loss, R_tau]
    norms = [colors.Normalize(0, 0.1), colors.Normalize(0, 1), colors.Normalize(0, 1)]
    labels = [r"$F_{\rm blow}$", r"$\eta_{\rm loss}$", r"$R_{\tau}$"]
    titles = ["吹き飛ばし質量分率", "放射圧除去質量比", "光学厚さ低下率"]

    for ax, data, norm, lab, title in zip(axes, data_list, norms, labels, titles):
        pcm = ax.pcolormesh(
            logS, logSIG, data, cmap="RdYlBu", norm=norm, shading="auto"
        )
        fig.colorbar(pcm, ax=ax, label=lab)
        ax.contour(
            logS,
            logSIG,
            tau_geo,
            levels=[1],
            colors="white",
            linestyles="--",
            linewidths=1,
        )
        ax.contour(logS, logSIG, beta_eff, levels=[0.5], colors="red", linewidths=1)
        ax.contour(
            logS,
            logSIG,
            ratio,
            levels=[0],
            colors="cyan",
            linestyles="-.",
            linewidths=1,
        )
        ax.set_title(title)
        ax.set_xlabel(r"$\log_{10} a_{\rm rep}$ [m]")
    axes[0].set_ylabel(r"$\log_{10} \Sigma$ [kg m$^{-2}$]")

    pr_tag = "+MarsPR" if args.include_mars_pr == "yes" else ""
    os.makedirs("output", exist_ok=True)
    plt.tight_layout()
    plt.savefig(f"output/extended_maps{suffix}{pr_tag}.png", dpi=300)
    plt.close(fig)

    # ── CSV 出力 ──────────────────────────
    df = pd.DataFrame(
        {
            "a_rep_m": S.ravel(),
            "Sigma_kg_m2": SIG.ravel(),
            "tau": tau_geo.ravel(),
            "beta_sun_mars": beta_sun_m.ravel(),
            "beta_mars": beta_m.ravel(),
            "beta_eff": beta_eff.ravel(),
            "t_col_yr": t_col.ravel(),
            "t_PR_total_yr": t_pr_total.ravel(),
            "log10_ratio": ratio.ravel(),
            "a_bl_m": np.full(S.size, a_bl),
            "F_blow": F_blow.ravel(),
            "eta_loss": eta_loss.ravel(),
            "R_tau": R_tau.ravel(),
        }
    )
    df.to_csv(f"output/extended_disk_map{suffix}.csv", index=False)

    # 代表値の抽出（a_bl 粒径・\u03a3_max）
    a_rep = a_bl
    a_idx = np.argmin(np.abs(s_vals - a_rep))
    summary = {
        "a_bl_m": float(a_bl),
        "F_blow_rep": float(F_blow[-1, a_idx]),
        "eta_loss_rep": float(eta_loss[-1, a_idx]),
        "R_tau_rep": float(R_tau[-1, a_idx]),
    }
    return df, summary


def run_batch(args):
    """半径ごとのマップ計算をバッチ実行する."""
    radius_list = np.arange(args.r_min, args.r_max + args.dr, args.dr) * R_MARS
    summaries = []
    for r in radius_list:
        Sigma_max = args.Sigma0_in * (r / (args.r_min * R_MARS)) ** (-args.gamma)
        Sigma_min = Sigma_max / 1e3
        iter_args = argparse.Namespace(**vars(args))
        iter_args.r_disk = r
        iter_args.Sigma_max = Sigma_max
        iter_args.Sigma_min = Sigma_min
        suffix = f"_r{r / R_MARS:.1f}R"
        _, summary = calc_maps(iter_args, suffix)
        summary.update(
            {
                "r_Rmars": r / R_MARS,
                "r_km": r / 1e3,
                "Sigma_max": Sigma_max,
                "Sigma_min": Sigma_min,
            }
        )
        summaries.append(summary)
    os.makedirs("output", exist_ok=True)
    pd.DataFrame(summaries).to_csv("output/master_summary.csv", index=False)


if __name__ == "__main__":
    import sys
    if "--testmode" in sys.argv:
        S_vals = np.logspace(-6, -5, 2)
        Sigma_vals = np.logspace(2, 3, 2)
        S, SIG = np.meshgrid(S_vals, Sigma_vals)
        F_blow = mass_fraction_blowout_map(
            S,
            SIG,
            rho=3000,
            a_min=1e-7,
            a_bl=2e-6,
            a_max=1e-3,
            q=3.5,
            t_sim=1.0,
            r_disk=2 * R_MARS,
        )
        assert F_blow.max() <= 1.0
        assert F_blow.shape == S.shape
        print("testmode passed")
    else:
        args = parse_args()
        run_batch(args)
