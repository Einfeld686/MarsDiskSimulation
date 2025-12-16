"""
温度軸ベースの「標準セット」可視化。

推奨パネル構成:
- 温度 vs M_out_dot（瞬時損失率）
- 累積損失（総量／blowout／sinks）
- 表層の満杯度（Sigma_surf, Sigma_tau1, headroom）
- 時間尺度比 t_coll / t_blow とステップ解像度 dt / t_blow
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

from .common import column_or_default, ensure_plot_path, load_series, load_summary, select_temperature


def _resolve_axis(df, use_time: bool) -> tuple[np.ndarray, str]:
    temps = None if use_time else select_temperature(df)
    if temps is not None:
        return temps, "T_M [K]"
    if "time" in df.columns:
        return np.asarray(df["time"], dtype=float), "time [s]"
    return np.arange(len(df), dtype=float), "index"


def _compute_headroom(df) -> np.ndarray:
    headroom = column_or_default(df, "headroom", np.nan)
    if np.isnan(headroom).all() and "Sigma_tau1" in df.columns and "Sigma_surf" in df.columns:
        headroom = np.asarray(df["Sigma_tau1"] - df["Sigma_surf"], dtype=float)
    return headroom


def _compute_tcoll_over_tblow(df) -> np.ndarray:
    ts_ratio = column_or_default(df, "ts_ratio", np.nan)  # t_blow / t_coll
    ratio = np.where(ts_ratio > 0.0, 1.0 / ts_ratio, np.nan)
    if np.all(np.isnan(ratio)) and "t_coll" in df.columns and "t_blow" in df.columns:
        t_coll = np.asarray(df["t_coll"], dtype=float)
        t_blow = np.asarray(df["t_blow"], dtype=float)
        valid = (t_coll > 0.0) & (t_blow > 0.0)
        ratio = np.full(len(df), np.nan, dtype=float)
        ratio[valid] = t_coll[valid] / t_blow[valid]
    return ratio


def plot_standard(run_dir: Path, out: Path | None = None, max_points: int | None = 4000, use_time: bool = False) -> Path:
    cols = [
        "time",
        "dt",
        "T_M_used",
        "M_out_dot",
        "M_loss_cum",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "Sigma_surf",
        "Sigma_tau1",
        "headroom",
        "t_coll",
        "t_blow",
        "ts_ratio",
        "dt_over_t_blow",
        "tau",
    ]
    df = load_series(run_dir, columns=cols, max_points=max_points)
    if df.empty:
        raise RuntimeError(f"series not found or empty: {run_dir}")

    x, xlabel = _resolve_axis(df, use_time=use_time)
    headroom = _compute_headroom(df)
    tcoll_over_tblow = _compute_tcoll_over_tblow(df)
    dt_over_t_blow = column_or_default(df, "dt_over_t_blow", np.nan)

    M_out_dot = column_or_default(df, "M_out_dot", 0.0)
    M_loss_cum = column_or_default(df, "M_loss_cum", 0.0)
    mass_lost_blow = column_or_default(df, "mass_lost_by_blowout", 0.0)
    mass_lost_sinks = column_or_default(df, "mass_lost_by_sinks", 0.0)
    sigma_surf = column_or_default(df, "Sigma_surf", np.nan)
    sigma_tau1 = column_or_default(df, "Sigma_tau1", np.nan)

    summary = load_summary(run_dir)

    fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True)

    axes[0].plot(x, M_out_dot, label="M_out_dot", color="tab:red", lw=1.2)
    axes[0].set_ylabel("M_Mars s$^{-1}$")
    axes[0].legend(loc="upper right")
    axes[0].set_title("瞬時損失率")

    axes[1].plot(x, M_loss_cum, label="M_loss_cum (total)", lw=1.2, color="tab:blue")
    axes[1].plot(x, mass_lost_blow, label="mass_lost_by_blowout", lw=1.0, color="tab:orange")
    axes[1].plot(x, mass_lost_sinks, label="mass_lost_by_sinks", lw=1.0, color="tab:green")
    axes[1].set_ylabel("M_Mars")
    axes[1].legend(loc="upper left")
    axes[1].set_title("累積損失")

    ax3 = axes[2]
    ax3.plot(x, sigma_surf, label="Sigma_surf", color="tab:green", lw=1.0)
    ax3.plot(x, sigma_tau1, label="Sigma_tau1", color="tab:gray", lw=1.0, linestyle="--")
    ax3.set_ylabel("kg m$^{-2}$")
    ax3.legend(loc="upper left")
    ax3.set_title("表層と τ=1 上限")
    ax3b = ax3.twinx()
    ax3b.plot(x, headroom, label="headroom", color="tab:blue", alpha=0.7)
    ax3b.set_ylabel("headroom")
    ax3b.legend(loc="upper right")

    ax4 = axes[3]
    ax4.plot(x, tcoll_over_tblow, label="t_coll / t_blow", color="tab:purple", lw=1.0)
    ax4.plot(x, dt_over_t_blow, label="dt / t_blow", color="tab:brown", lw=0.8, linestyle="--", alpha=0.8)
    ax4.set_ylabel("ratio")
    ax4.set_yscale("log")
    ax4.legend(loc="upper right")
    ax4.set_title("時間尺度の比")

    axes[-1].set_xlabel(xlabel)

    title_parts = [run_dir.name]
    if "M_loss" in summary:
        title_parts.append(f"M_loss={summary['M_loss']:.3e} M_Mars")
    if "mass_budget_max_error_percent" in summary:
        title_parts.append(f"mass_err={summary['mass_budget_max_error_percent']:.3f}%")
    fig.suptitle(" / ".join(title_parts))
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out_path = ensure_plot_path(run_dir, out, "standard.png")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="温度軸ベースの標準可視化を生成します。")
    parser.add_argument("--run-dir", type=Path, required=True, help="run ディレクトリ (series/run.parquet を含む)")
    parser.add_argument("--out", type=Path, default=None, help="出力ファイルパス。未指定なら run_dir/plots/standard.png")
    parser.add_argument("--max-points", type=int, default=4000, help="プロット前に間引く最大サンプル数")
    parser.add_argument("--use-time", action="store_true", help="温度ではなく time を横軸に使う")
    args = parser.parse_args()

    plot_standard(args.run_dir, out=args.out, max_points=args.max_points, use_time=args.use_time)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
