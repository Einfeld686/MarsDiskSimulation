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
    collision_timescale_years,
    pr_timescale_total,
)


def blowout_radius(rho, qpr=1, beta_crit=0.5):  # FIX ブローアウト粒径
    """Burns79 Eq.(1) から β=beta_crit を満たす粒径 [m]"""
    return 5.7e-4 * qpr / (beta_crit * rho)


def norm_const_dohnanyi(Sigma, rho, a_min, a_max, q=3.5):
    """Dohnanyi 分布の正規化係数 C を返す."""
    k = (4 * np.pi * rho / 3) * (a_max ** (4 - q) - a_min ** (4 - q)) / (4 - q)
    return Sigma / k  # n(a)=C a^{-q}


def mass_fraction_blowout_map(S, SIG, rho, a_min, a_bl, a_max, q, t_sim, t_col):
    """吹き飛ばし質量分率 :math:`F_{\rm blow}` を返す.

    Compute the mass fraction of particles blown out of the system at each
    grid point ``(Σ, a_rep)``. The fraction is evaluated by

    .. math::

       F_{\rm blow}=f_{\rm mass}\left[1-\exp\left(-\frac{t_{\rm sim}}
       {t_{\rm col}(\Sigma,a_{\rm rep})}\right)\right],

    where ``t_col`` is the collision timescale in years and ``f_mass`` is the
    instantaneous mass fraction from the Dohnanyi size distribution.

    Parameters
    ----------
    S, SIG : ndarray
        メッシュグリッド上の代表粒径と表面密度 / meshgrids of representative
        grain size and surface density.
    rho : float
        粒子密度 [kg m^-3].
    a_min, a_bl, a_max : float
        サイズ分布の下限・ブローアウト・上限粒径 [m].
    q : float
        サイズ分布指数.
    t_sim : float
        評価時間 [yr].
    t_col : ndarray
        衝突時間スケール [yr]. ``S`` と同形状の配列を想定。

    Returns
    -------
    ndarray
        ``(n_\sigma, n_s)`` 形状の ``F_blow`` マップ / map of ``F_blow`` with
        shape ``(n_sigma, n_s)`` clipped to [0, 1].
    """
    # Dohnanyi 分布に基づく瞬時質量分率
    f_mass = (
      a_bl ** (4 - q) - a_min ** (4 - q)
    ) / (a_max ** (4 - q) - a_min ** (4 - q))

    F_blow = f_mass * (1.0 - np.exp(-t_sim / t_col))
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
    p.add_argument("--r_min", type=float, default=2.6,
        help="解析開始半径 [R_MARS]")
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
    # --- 旧 gamma プロファイルと排他にする新オプション ---
    p.add_argument("--profile_mode", choices=["piecewise","gamma"], default="piecewise",
        help="Σ プロファイルの種類 (内外二分 piecewise か従来 gamma)")

    # piecewise 用：内側一様 Σ
    p.add_argument("--r_transition", type=float, default=2.7,
        help="内外円盤の境界半径 [R_MARS]")
    p.add_argument("--Sigma_inner", type=float, default=5e3,
        help="内側円盤の一様表面密度 [kg m^-2]")

    # piecewise 用：外側 power-law Σ = Σ_outer0 (r/r_tr)^(-p_outer)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--Sigma_outer0", type=float, default=None,
        help="外側円盤基準表面密度 Σ(r=r_transition) [kg m^-2]")
    group.add_argument("--M_outer", type=float, default=None,
        help="外側円盤総質量 [火星質量単位]; 指定時 Σ_outer0 を自動計算")
    p.add_argument("--p_outer", type=float, default=5.0,
        help="外側円盤の指数 p (Σ∝r^{-p})")

    # 旧 gamma プロファイルを残す場合のみ必要
    p.add_argument("--Sigma0_in", type=float, default=1e4,
        help="[gamma モード専用] r_min での Σ_max [kg m^-2]")
    p.add_argument("--gamma", type=float, default=3.0,
        help="[gamma モード専用] Σ ∝ r^{-γ} の γ")
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
    p.add_argument(
        "--thick_disk",
        action="store_true",
        help="厚い円盤補正：t_col に係数を掛ける",
    )
    p.add_argument(
        "--testmode",
        action="store_true",
        help="テスト用高速モード",
    )
    args = p.parse_args()
    if args.testmode:
        args.n_s = 10
        args.n_sigma = 10
        args.r_max = args.r_min
    return args

# --- 内側一様 ＆ 外側 power-law プロファイルを計算 ---------------------------
def sigma_piecewise(r_Rmars, args):
    """半径 r [R_MARS] における Σ_max を返す (piecewise モード専用)."""
    if r_Rmars <= args.r_transition:
        return args.Sigma_inner
    # --- 外側基準 Σ_outer0 を決定 ---
    if args.Sigma_outer0 is not None:
        Sigma0 = args.Sigma_outer0
    else:
        # 総質量 M_outer [M_MARS] → Σ0 に変換
        if args.M_outer is None:
            raise ValueError("Sigma_outer0 か M_outer のどちらかを指定してください")
        r_tr = args.r_transition * R_MARS
        r_max = args.r_max * R_MARS
        p = args.p_outer
        denom = 2 * np.pi * r_tr**2 * ((r_max / r_tr)**(1 - p) - 1) / (1 - p)
        Sigma0 = args.M_outer * M_MARS / denom
    # power-law Σ
    return Sigma0 * (r_Rmars / args.r_transition) ** (-args.p_outer)


# ── メイン計算 ───────────────────────────
def calc_maps(args, suffix=""):
    """3 種の指標マップを計算し CSV/PNG を出力する.

    有効寿命と質量損失率 / Effective lifetime and mass-loss rate::

        \tau_{\rm eff}=\frac{t_{\rm col} t_{\rm PR}}{t_{\rm col}+t_{\rm PR}}\ [\rm yr]
        \eta_{\rm loss}=1-\exp\!\left(-\frac{t_{\rm sim}}{\tau_{\rm eff}}\right)
    """

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

    t_col = collision_timescale_years(S, SIG, args.rho, args.r_disk)
    # Wyatt05 式は厚い円盤で過小評価するので安全係数
    if getattr(args, "thick_disk", False):
      t_col *= 100      # ← 例：2桁くらい緩める
    
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
        S, SIG, args.rho, a_min, a_bl_eff, args.a_max, args.q, args.t_sim, t_col
    )
    F_blow = np.clip(F_blow, 0, 1)

    tau_eff = (t_col * t_pr_total) / (t_col + t_pr_total)
    eta_loss = 1.0 - np.exp(-args.t_sim / tau_eff)
    eta_loss = np.clip(eta_loss, 0.0, 1.0)
    assert eta_loss.shape == S.shape
    assert np.nanmax(eta_loss) <= 1.0

    tau0 = tau_integral(C, a_min, args.a_max, args.q)
    tau_eff_tau = tau_integral(C, a_bl_eff, args.a_max, args.q)
    R_tau_scalar = tau_eff_tau / tau0
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
        r_Rmars = r / R_MARS
        if args.profile_mode == "piecewise":
            Sigma_max = sigma_piecewise(r_Rmars, args)
        else:   # 従来 gamma モード
            Sigma_max = args.Sigma0_in * (r_Rmars / args.r_min) ** (-args.gamma)
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
                "profile": args.profile_mode,
            }
        )
        summaries.append(summary)
    os.makedirs("output", exist_ok=True)
    pd.DataFrame(summaries).to_csv("output/master_summary.csv", index=False)


if __name__ == "__main__":
    args = parse_args()
    if args.testmode:
        S_vals = np.logspace(-6, -5, 2)
        Sigma_vals = np.logspace(2, 3, 2)
        S, SIG = np.meshgrid(S_vals, Sigma_vals)
        F_blow = mass_fraction_blowout_map(
            S,
            SIG,
            3000,
            1e-7,
            2e-6,
            1e-3,
            3.5,
            1.0,
            2 * R_MARS,
        )
        assert F_blow.max() <= 1.0
        assert F_blow.shape == S.shape
    else:
        run_batch(args)
