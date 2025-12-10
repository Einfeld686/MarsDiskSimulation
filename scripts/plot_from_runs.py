#!/usr/bin/env python3
"""
figure_tasks.json で指示された run ディレクトリから簡易図を生成するユーティリティ。

サポートする mode:
- beta_timeseries: time vs beta_at_smin_effective と M_out_dot を2軸でプロット
- mass_budget: checks/mass_budget.csv から error_percent をプロット
- psd_wavy: time vs s_min と tau を重ね、wavy の兆候を観察する簡易図

出力先は既定で最初の run ディレクトリ配下の figures/。--output-dir で上書き可。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paper.plot_style import apply_default_style


def plot_beta_timeseries(runs: List[Path], params: Dict[str, Any], output_dir: Path, fig_id: str) -> Path:
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    for run in runs:
        df = pd.read_parquet(run / "series" / "run.parquet")
        label = run.name
        ax1.plot(df["time"], df["beta_at_smin_effective"], label=f"{label} β_eff")
        if "M_out_dot" in df.columns:
            ax2.plot(df["time"], df["M_out_dot"], linestyle="--", label=f"{label} M_out")
    ax1.set_xlabel("time [s]")
    ax1.set_ylabel("beta_at_smin_effective")
    ax2.set_ylabel("M_out_dot [M_Mars s^-1]")
    ax1.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    ax1.set_title(f"{fig_id}: beta_timeseries")
    output_dir.mkdir(parents=True, exist_ok=True)
    outpath = output_dir / f"{fig_id}.png"
    fig.tight_layout()
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    return outpath


def plot_mass_budget(runs: List[Path], params: Dict[str, Any], output_dir: Path, fig_id: str) -> Path:
    fig, ax = plt.subplots()
    for run in runs:
        csv_path = run / "checks" / "mass_budget.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        label = run.name
        ax.plot(df["time"], df["error_percent"], label=f"{label} error%")
    ax.axhline(0.5, color="red", linestyle="--", alpha=0.6, label="tolerance 0.5%")
    ax.axhline(-0.5, color="red", linestyle="--", alpha=0.6)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("mass_budget error [%]")
    ax.legend(fontsize=9)
    ax.set_title(f"{fig_id}: mass_budget")
    output_dir.mkdir(parents=True, exist_ok=True)
    outpath = output_dir / f"{fig_id}.png"
    fig.tight_layout()
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    return outpath


def plot_psd_wavy(runs: List[Path], params: Dict[str, Any], output_dir: Path, fig_id: str) -> Path:
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    for run in runs:
        df = pd.read_parquet(run / "series" / "run.parquet")
        label = run.name
        ax1.plot(df["time"], df["s_min"], label=f"{label} s_min")
        if "tau" in df.columns:
            ax2.plot(df["time"], df["tau"], linestyle="--", label=f"{label} tau")
    ax1.set_xlabel("time [s]")
    ax1.set_ylabel("s_min [m]")
    ax2.set_ylabel("tau")
    ax1.legend(loc="upper left", fontsize=9)
    ax2.legend(loc="upper right", fontsize=9)
    ax1.set_title(f"{fig_id}: psd_wavy proxy")
    output_dir.mkdir(parents=True, exist_ok=True)
    outpath = output_dir / f"{fig_id}.png"
    fig.tight_layout()
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    return outpath


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate figures from run directories")
    parser.add_argument("--fig-id", required=True)
    parser.add_argument("--runs", nargs="+", required=True, help="paths to run output directories")
    parser.add_argument("--params-json", default="{}", help="JSON string of params (mode key required)")
    parser.add_argument("--output-dir", type=Path, help="destination for figures (default: runs[0]/figures)")
    args = parser.parse_args()

    params = json.loads(args.params_json)
    mode = params.get("mode")
    if not mode:
        raise SystemExit("params_json must include mode")

    run_paths = [Path(p).resolve() for p in args.runs]
    outdir = args.output_dir or (run_paths[0] / "figures")
    apply_default_style()

    if mode == "beta_timeseries":
        outpath = plot_beta_timeseries(run_paths, params, outdir, args.fig_id)
    elif mode == "mass_budget":
        outpath = plot_mass_budget(run_paths, params, outdir, args.fig_id)
    elif mode == "psd_wavy":
        outpath = plot_psd_wavy(run_paths, params, outdir, args.fig_id)
    else:
        raise SystemExit(f"unsupported mode: {mode}")

    print(f"[plot_from_runs] wrote {outpath}")


if __name__ == "__main__":
    main()
