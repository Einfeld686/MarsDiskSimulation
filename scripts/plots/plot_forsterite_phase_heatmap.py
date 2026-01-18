"""Generate a time-radius heatmap of forsterite temperature."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from siO2_disk_cooling.model import CoolingParams, YEAR_SECONDS, dust_temperature


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a forsterite temperature heatmap.")
    parser.add_argument("--T0", type=float, default=4000.0, help="Initial Mars temperature [K]")
    return parser.parse_args()


def _load_forsterite_properties(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_base_config(path: Path) -> tuple[float, float, float]:
    if not path.exists():
        return 1.0, 2.7, 0.4
    try:
        from ruamel.yaml import YAML
    except Exception:
        return 1.0, 2.7, 0.4
    try:
        yaml = YAML(typ="safe")
        with path.open("r", encoding="utf-8") as fh:
            cfg = yaml.load(fh) or {}
    except Exception:
        return 1.0, 2.7, 0.4

    disk = cfg.get("disk", {}) if isinstance(cfg, dict) else {}
    geom = disk.get("geometry", {}) if isinstance(disk, dict) else {}
    phase = cfg.get("phase", {}) if isinstance(cfg, dict) else {}
    try:
        r_in = float(geom.get("r_in_RM", 1.0))
        r_out = float(geom.get("r_out_RM", 2.7))
    except Exception:
        r_in, r_out = 1.0, 2.7
    try:
        q_abs_mean = float(phase.get("q_abs_mean", 0.4))
    except Exception:
        q_abs_mean = 0.4
    return r_in, r_out, q_abs_mean


def main() -> int:
    args = _parse_args()
    repo_root = REPO_ROOT
    props_path = REPO_ROOT / "data/forsterite_material_data/forsterite_material_properties.json"
    config_path = REPO_ROOT / "configs" / "base.yml"

    props = _load_forsterite_properties(props_path)
    phase_switch = props.get("phase_switch", {}) if isinstance(props, dict) else {}
    try:
        T_melt = float(phase_switch.get("T_melt_K", 2163.0))
    except Exception:
        T_melt = 2163.0

    r_in, r_out, q_abs_mean = _load_base_config(config_path)
    r_out = min(r_out, 2.6)

    T0 = float(args.T0)
    t_max_years = 2.0
    dt_hours = 6.0
    n_r = 300

    dt_s = dt_hours * 3600.0
    time_s = np.arange(0.0, t_max_years * YEAR_SECONDS + 0.5 * dt_s, dt_s, dtype=float)
    r_over_Rmars = np.linspace(r_in, r_out, n_r, dtype=float)

    params = CoolingParams(q_abs_mean=q_abs_mean)
    T_dust = dust_temperature(
        r_over_Rmars * params.R_mars,
        time_s,
        T0,
        params,
        temperature_model="slab",
    )
    if T_dust.ndim == 1:
        T_dust = T_dust[:, np.newaxis]

    time_years = time_s / YEAR_SECONDS

    cmap = LinearSegmentedColormap.from_list(
        "forsterite_temp",
        [(0.0, "#2166ac"), (1.0, "#d73027")],
    )
    t_min = float(np.nanmin(T_dust))
    t_max = float(np.nanmax(T_dust))

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    mesh = ax.pcolormesh(
        time_years,
        r_over_Rmars,
        T_dust.T,
        shading="auto",
        cmap=cmap,
        vmin=t_min,
        vmax=t_max,
    )
    boundary_color = "#949593"
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label("Temperature [K]")
    phase_mask = (T_dust >= T_melt).astype(float)
    overlay = np.where(phase_mask > 0.5, 1.0, np.nan)
    ax.pcolormesh(
        time_years,
        r_over_Rmars,
        overlay.T,
        shading="auto",
        cmap=ListedColormap([boundary_color]),
        vmin=0.0,
        vmax=1.0,
        alpha=1.0,
        zorder=2,
    )
    ax.contour(
        time_years,
        r_over_Rmars,
        T_dust.T,
        levels=[T_melt],
        colors=boundary_color,
        linewidths=1.2,
        zorder=3,
    )
    ax.set_xlabel("Time [years]")
    ax.set_ylabel(r"r / R_Mars")
    ax.set_xlim(0.0, t_max_years)
    ax.set_ylim(r_over_Rmars.min(), r_over_Rmars.max())
    ax.grid(False)

    out_dir = REPO_ROOT / "figures" / "thesis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"forsterite_phase_heatmap_T0{int(T0):04d}K_2yr.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
