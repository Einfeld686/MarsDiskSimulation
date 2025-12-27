#!/usr/bin/env python3
"""Plot the Planck-mean <Q_pr> table for the SiO2 bridge model."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper.plot_style import apply_default_style


def _load_table(path: Path) -> pd.DataFrame:
    """Load and sort the Q_pr table."""
    df = pd.read_csv(path)
    expected = {"T_M", "s", "Q_pr"}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")
    return df.sort_values(["T_M", "s"]).reset_index(drop=True)


def _plot_curves(
    ax: plt.Axes,
    df: pd.DataFrame,
    temps: np.ndarray,
    cmap,
    norm: Normalize,
    marker_size: float,
    label_inset: bool = False,
) -> None:
    """Shared helper to draw Q_pr(T, s) curves."""
    for T in temps:
        sub = df[df["T_M"] == T]
        ax.plot(
            sub["s"] * 1.0e6,
            sub["Q_pr"],
            color=cmap(norm(T)),
            marker="o",
            lw=1.6,
            ms=marker_size,
            alpha=0.9,
        )
    if label_inset:
        ax.set_title("Sub-micron to few microns", fontsize=9)


def plot_qpr(df: pd.DataFrame, outdir: Path, basename: str) -> List[Path]:
    """Create the main figure and return the written paths."""
    apply_default_style({"figure.figsize": (6.8, 4.2)})

    temps = np.unique(df["T_M"])
    cmap = plt.get_cmap("inferno")
    norm = Normalize(vmin=float(temps.min()), vmax=float(temps.max()))

    fig, ax = plt.subplots()
    _plot_curves(ax, df, temps, cmap, norm, marker_size=3.6)

    cbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, pad=0.02)
    cbar.set_label(r"Mars-facing blackbody temperature $T_{\rm M}$ [K]")

    ax.set_xscale("log")
    ax.set_xlim(df["s"].min() * 1.0e6 * 0.8, df["s"].max() * 1.0e6 * 1.2)
    ax.set_ylim(0.0, 1.05)
    ax.set_xlabel(r"Grain radius $s$ [$\mu$m]")
    ax.set_ylabel(r"Planck-mean $\langle Q_{\rm pr} \rangle$")
    ax.set_title(r"SiO$_2$ bridge model for $\langle Q_{\rm pr} \rangle$")

    ax.text(0.04, 0.86, "Rayleigh regime", transform=ax.transAxes, fontsize=9, color="#444")
    ax.text(0.66, 0.16, "Geometric optics limit", transform=ax.transAxes, fontsize=9, color="#444")

    s_min_um = df["s"].min() * 1.0e6
    q_min = df[df["s"] == df["s"].min()]["Q_pr"].max()
    ax.annotate(
        r"Absorption term ($c_{\rm abs}=0.1$) keeps"
        "\n"
        r"$\langle Q_{\rm pr} \rangle$ above zero at $s \sim 0.1\ \mu{\rm m}$",
        xy=(s_min_um, q_min),
        xytext=(0.56, 0.42),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": "#555", "lw": 0.8},
        fontsize=9,
        color="#333",
    )
    ax.text(
        0.79,
        0.80,
        r"Hotter $T_{\mathrm{M}}$",
        transform=ax.transAxes,
        fontsize=8,
        color=cmap(norm(temps.max())),
    )
    ax.text(
        0.79,
        0.72,
        r"Cooler $T_{\mathrm{M}}$",
        transform=ax.transAxes,
        fontsize=8,
        color=cmap(norm(temps.min())),
    )

    inset = inset_axes(ax, width="48%", height="50%", loc="lower right", borderpad=1.0)
    zoom_mask = (df["s"] * 1.0e6 >= 0.08) & (df["s"] * 1.0e6 <= 5.0)
    _plot_curves(inset, df.loc[zoom_mask], temps, cmap, norm, marker_size=3.0, label_inset=True)
    inset.set_xscale("log")
    inset.set_xlim(0.08, 5.0)
    inset.set_ylim(0.0, 1.05)
    inset.set_xticks([0.1, 0.3, 1.0, 3.0])
    inset.set_xticklabels(["0.1", "0.3", "1", "3"])
    inset.tick_params(labelsize=8)

    outdir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for ext in ("png", "pdf"):
        out_path = outdir / f"{basename}.{ext}"
        fig.savefig(out_path, bbox_inches="tight")
        outputs.append(out_path)
    plt.close(fig)
    return outputs


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv"),
        help="CSV table with columns: T_M [K], s [m], Q_pr [-]",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out/figures"),
        help="Directory to store the figure files",
    )
    parser.add_argument(
        "--basename",
        type=str,
        default="qpr_planck_sio2",
        help="Base name (without extension) for the outputs",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    df = _load_table(args.data)
    outputs = plot_qpr(df, args.outdir, args.basename)
    for path in outputs:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
