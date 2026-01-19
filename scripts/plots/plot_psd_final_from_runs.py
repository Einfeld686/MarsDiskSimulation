#!/usr/bin/env python3
"""Render final PSD shape from run outputs using the PSD model and final s_min."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import matplotlib
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from marsdisk.physics import psd
from paper.plot_style import apply_default_style


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot final PSD distributions derived from run outputs."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(
            "out/temp_supply_sweep_1d/20260113-162712__6031b1edd__seed1709094340"
        ),
        help="Root directory containing run subdirectories.",
    )
    parser.add_argument(
        "--filter",
        dest="name_filter",
        default="i00p05",
        help="Substring used to select run directories (default: i00p05).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("figures/thesis"),
        help="Output directory for PSD figures.",
    )
    parser.add_argument(
        "--reduce",
        choices=["median", "mean"],
        default="median",
        help="Aggregation used to collapse 1D cell values (default: median).",
    )
    return parser.parse_args()


def _read_config(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "run_config.json"
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = data.get("config")
    if not isinstance(cfg, dict):
        raise ValueError(f"config field missing in {path}")
    return cfg


def _select_runs(run_root: Path, name_filter: str) -> Iterable[Path]:
    if not run_root.exists():
        raise FileNotFoundError(run_root)
    for child in sorted(run_root.iterdir()):
        if not child.is_dir():
            continue
        if name_filter and name_filter not in child.name:
            continue
        yield child


def _final_s_min(run_dir: Path, reduce_mode: str) -> Tuple[float, float]:
    path = run_dir / "series" / "run.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path, columns=["time", "s_min_effective", "s_min"])
    final_time = float(df["time"].max())
    sub = df[df["time"] == final_time]
    if sub.empty:
        raise ValueError(f"no rows at final time in {path}")
    s_min_col = "s_min_effective" if "s_min_effective" in sub.columns else "s_min"
    if reduce_mode == "mean":
        s_min_val = float(sub[s_min_col].mean())
    else:
        s_min_val = float(sub[s_min_col].median())
    return s_min_val, final_time


def _build_psd(cfg: Dict[str, Any], s_min: float) -> Dict[str, np.ndarray]:
    sizes_cfg = cfg.get("sizes", {})
    psd_cfg = cfg.get("psd", {})
    mat_cfg = cfg.get("material", {})
    s_max = float(sizes_cfg.get("s_max", 1.0))
    n_bins = int(sizes_cfg.get("n_bins", 40))
    alpha = float(psd_cfg.get("alpha", 1.83))
    wavy_strength = float(psd_cfg.get("wavy_strength", 0.0))
    rho = float(mat_cfg.get("rho", 3000.0))
    psd_state = psd.update_psd_state(
        s_min=s_min,
        s_max=s_max,
        alpha=alpha,
        wavy_strength=wavy_strength,
        n_bins=n_bins,
        rho=rho,
    )
    sizes = np.asarray(psd_state.get("sizes"), dtype=float)
    widths = np.asarray(psd_state.get("widths"), dtype=float)
    number = np.asarray(psd_state.get("number"), dtype=float)
    if sizes.size == 0 or widths.size != sizes.size or number.size != sizes.size:
        raise ValueError("PSD state has inconsistent sizes/widths/number arrays")
    mass_proxy = number * (sizes**3) * widths
    total_mass = float(np.sum(mass_proxy))
    if not np.isfinite(total_mass) or total_mass <= 0.0:
        raise ValueError("PSD mass proxy is invalid")
    mass_fraction = mass_proxy / total_mass
    return {
        "sizes": sizes,
        "mass_fraction": mass_fraction,
    }


def _plot_psd(out_path: Path, sizes: np.ndarray, mass_fraction: np.ndarray, title: str) -> None:
    mask = np.isfinite(sizes) & np.isfinite(mass_fraction) & (sizes > 0.0) & (mass_fraction > 0.0)
    sizes = sizes[mask]
    mass_fraction = mass_fraction[mask]
    if sizes.size == 0:
        raise ValueError("PSD arrays are empty after filtering")

    fig, ax = plt.subplots()
    ax.plot(sizes, mass_fraction, color="#1f4e79")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("size s [m]")
    ax.set_ylabel("mass fraction per bin [arb]")
    ax.grid(True, which="both", alpha=0.25)
    ax.set_title(title, fontsize=11)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> int:
    args = _parse_args()
    apply_default_style({"figure.figsize": (6.5, 4.0)})

    run_dirs = list(_select_runs(args.run_root, args.name_filter))
    if not run_dirs:
        print(f"[error] no runs matched under {args.run_root}", file=sys.stderr)
        return 1

    for run_dir in run_dirs:
        try:
            cfg = _read_config(run_dir)
            s_min_val, final_time = _final_s_min(run_dir, args.reduce)
            psd_state = _build_psd(cfg, s_min_val)
        except Exception as exc:
            print(f"[warn] skip {run_dir.name}: {exc}", file=sys.stderr)
            continue
        title = f"{run_dir.name} (t={final_time/3.15576e7:.2f} yr, s_min={s_min_val:.2e} m)"
        out_path = args.outdir / f"psd_final_{run_dir.name}.png"
        _plot_psd(out_path, psd_state["sizes"], psd_state["mass_fraction"], title)
        print(f"[info] wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
