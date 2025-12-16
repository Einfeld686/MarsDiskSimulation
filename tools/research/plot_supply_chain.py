"""
供給→表層→損失の流れとクリップ挙動をまとめて可視化するスクリプト。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

from .common import column_or_default, ensure_plot_path, load_series, select_temperature


def _axis(run_dir: Path, df, use_time: bool):
    temps = None if use_time else select_temperature(df)
    if temps is not None:
        return temps, "T_M [K]"
    if "time" in df.columns:
        return np.asarray(df["time"], dtype=float), "time [s]"
    return np.arange(len(df), dtype=float), "index"


def plot_supply_chain(run_dir: Path, out: Path | None = None, max_points: int | None = 4000, use_time: bool = False) -> Path:
    cols = [
        "time",
        "T_M_used",
        "supply_rate_nominal",
        "supply_rate_scaled",
        "supply_rate_applied",
        "prod_rate_diverted_to_deep",
        "deep_to_surf_flux",
        "supply_tau_clip_spill_rate",
        "supply_clip_factor",
        "supply_headroom",
        "supply_feedback_scale",
        "sigma_deep",
        "Sigma_surf",
        "Sigma_tau1",
        "tau",
    ]
    df = load_series(run_dir, columns=cols, max_points=max_points)
    if df.empty:
        raise RuntimeError(f"series not found or empty: {run_dir}")

    x, xlabel = _axis(run_dir, df, use_time=use_time)
    supply_scaled = column_or_default(df, "supply_rate_scaled", 0.0)
    supply_applied = column_or_default(df, "supply_rate_applied", 0.0)
    supply_nominal = column_or_default(df, "supply_rate_nominal", 0.0)
    diverted = column_or_default(df, "prod_rate_diverted_to_deep", 0.0)
    deep_to_surf = column_or_default(df, "deep_to_surf_flux", 0.0)
    spill = np.clip(column_or_default(df, "supply_tau_clip_spill_rate", 0.0), 0.0, None)

    rejected = np.clip(supply_scaled - supply_applied, 0.0, None)
    clip_factor = column_or_default(df, "supply_clip_factor", np.nan)
    headroom = column_or_default(df, "supply_headroom", np.nan)
    feedback = column_or_default(df, "supply_feedback_scale", np.nan)
    sigma_deep = column_or_default(df, "sigma_deep", np.nan)
    sigma_surf = column_or_default(df, "Sigma_surf", np.nan)
    sigma_tau1 = column_or_default(df, "Sigma_tau1", np.nan)
    tau = column_or_default(df, "tau", np.nan)

    sigma_deep_norm = sigma_deep.copy()
    if np.isfinite(sigma_deep_norm).any():
        baseline = np.nanmax([np.nanmax(sigma_deep_norm), np.nanmax(np.abs(sigma_deep_norm[:10]))])
        if baseline > 0:
            sigma_deep_norm = sigma_deep_norm / baseline

    fig = plt.figure(figsize=(12, 12))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.9], hspace=0.35, wspace=0.25)

    ax11 = fig.add_subplot(gs[0, 0])
    ax11.plot(x, supply_nominal, label="supply_rate_nominal", color="tab:gray", lw=0.9, alpha=0.8)
    ax11.plot(x, supply_scaled, label="supply_rate_scaled", color="tab:blue", lw=1.1)
    ax11.set_ylabel("kg m$^{-2}$ s$^{-1}$")
    ax11.set_title("供給 (nominal / scaled)")
    ax11.legend(loc="upper right")

    ax12 = fig.add_subplot(gs[0, 1])
    ax12.plot(x, supply_applied, label="supply_rate_applied", color="tab:green", lw=1.1)
    ax12.plot(x, diverted, label="prod_rate_diverted_to_deep", color="tab:orange", lw=1.0)
    ax12.plot(x, deep_to_surf, label="deep_to_surf_flux", color="tab:red", lw=0.9, alpha=0.8)
    ax12.set_ylabel("kg m$^{-2}$ s$^{-1}$")
    ax12.set_title("表層・深部フラックス")
    ax12.legend(loc="upper right")

    ax21 = fig.add_subplot(gs[1, 0])
    ax21.plot(x, rejected, label="rejected (scaled-applied)", color="tab:red", lw=1.0)
    if np.isfinite(spill).any():
        ax21.plot(x, spill, label="supply_tau_clip_spill_rate", color="tab:purple", lw=0.9, linestyle="--")
    ax21.set_ylabel("kg m$^{-2}$ s$^{-1}$")
    ax21.set_title("拒否・溢れた供給")
    ax21.legend(loc="upper right")

    ax22 = fig.add_subplot(gs[1, 1])
    applied_pos = np.clip(supply_applied, 0.0, None)
    diverted_pos = np.clip(diverted, 0.0, None)
    rejected_pos = rejected
    ax22.stackplot(
        x,
        applied_pos,
        diverted_pos,
        rejected_pos,
        labels=["applied", "diverted_to_deep", "rejected"],
        colors=["tab:green", "tab:orange", "tab:red"],
        alpha=0.7,
    )
    ax22.set_ylabel("kg m$^{-2}$ s$^{-1}$")
    ax22.set_title("フラックス構成（積み上げ）")
    ax22.legend(loc="upper right")

    ax31 = fig.add_subplot(gs[2, 0])
    ax31.plot(x, clip_factor, label="supply_clip_factor", color="tab:blue", lw=1.1)
    ax31.plot(x, feedback, label="supply_feedback_scale", color="tab:brown", lw=0.9, linestyle="--")
    ax31.set_ylabel("scale / factor")
    ax31.set_title("クリップ係数とフィードバック")
    ax31.set_ylim(0.0, max(1.05, np.nanmax([clip_factor, feedback]) if np.isfinite(clip_factor).any() else 1.05))
    ax31.legend(loc="upper right")
    ax31b = ax31.twinx()
    ax31b.plot(x, tau, label="tau", color="tab:gray", alpha=0.6)
    ax31b.axhline(0.9, color="tab:gray", linestyle=":", lw=0.8)
    ax31b.set_ylabel("tau")
    ax31b.legend(loc="lower right")

    ax32 = fig.add_subplot(gs[2, 1])
    ax32.plot(x, sigma_surf, label="Sigma_surf", color="tab:green", lw=1.0)
    ax32.plot(x, sigma_tau1, label="Sigma_tau1", color="tab:gray", lw=0.9, linestyle="--")
    ax32.plot(x, sigma_deep_norm, label="sigma_deep (norm)", color="tab:blue", lw=1.0, alpha=0.8)
    ax32.set_ylabel("kg m$^{-2}$ (norm.)")
    ax32.set_title("満杯度と深部バッファ")
    ax32.legend(loc="upper right")

    for ax in fig.axes:
        if ax in (ax22,):
            continue
        ax.grid(True, linestyle=":", alpha=0.4)

    fig.supxlabel(xlabel)
    fig.suptitle(f"{run_dir.name} supply→surface→loss", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out_path = ensure_plot_path(run_dir, out, "supply_chain.png")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="供給チェーンの可視化を生成します。")
    parser.add_argument("--run-dir", type=Path, required=True, help="run ディレクトリ")
    parser.add_argument("--out", type=Path, default=None, help="出力ファイル。未指定なら run_dir/plots/supply_chain.png")
    parser.add_argument("--max-points", type=int, default=4000, help="最大サンプル数（間引き）")
    parser.add_argument("--use-time", action="store_true", help="温度ではなく time を横軸に使う")
    args = parser.parse_args()

    plot_supply_chain(args.run_dir, out=args.out, max_points=args.max_points, use_time=args.use_time)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
