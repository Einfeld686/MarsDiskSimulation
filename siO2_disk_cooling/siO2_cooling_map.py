"""CLI entry point for generating SiO2 cooling maps."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np

from .io_utils import ensure_outputs_dir, write_csv, write_log
from .model import CoolingParams, YEAR_SECONDS, compute_arrival_times, cooling_time_to_temperature
from .plotting import plot_arrival_map


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a SiO2 cooling arrival map.")
    parser.add_argument("--T0", type=float, default=4000.0, help="Initial Mars temperature [K]")
    parser.add_argument(
        "--t_max_years", type=float, default=2.0, help="Maximum simulation time [years]"
    )
    parser.add_argument("--dt_hours", type=float, default=6.0, help="Time step [hours]")
    parser.add_argument(
        "--r_min_Rmars", type=float, default=1.0, help="Minimum radius in units of R_Mars"
    )
    parser.add_argument(
        "--r_max_Rmars", type=float, default=2.4, help="Maximum radius in units of R_Mars"
    )
    parser.add_argument("--n_r", type=int, default=300, help="Number of radial samples")
    parser.add_argument(
        "--cell-width-Rmars",
        type=float,
        default=None,
        help="Radial cell width in units of R_Mars (overrides --n_r if set)",
    )
    parser.add_argument(
        "--marsdisk-config",
        type=str,
        default=None,
        help="Path to marsdisk YAML config for auto cell width (defaults to configs/base.yml if present)",
    )
    parser.add_argument("--no-log", action="store_true", help="Skip writing the text log")
    parser.add_argument("--no-plot", action="store_true", help="Skip writing the PNG plot")
    parser.add_argument(
        "--plot-mode",
        choices=["arrival", "phase"],
        default="arrival",
        help="Plot arrival times or solid/vapor fraction",
    )
    parser.add_argument(
        "--cooling-model",
        choices=["slab", "hyodo"],
        default="slab",
        help="Cooling model for Mars temperature (slab T^-3 or Hyodo linear flux).",
    )
    parser.add_argument(
        "--T_stop",
        type=float,
        default=None,
        help="If set, extend t_max_years so the Mars slab cools to this temperature [K] before stopping.",
    )
    parser.add_argument(
        "--span-margin-years",
        type=float,
        default=0.2,
        help="Extra padding added after reaching T_stop when --T_stop is provided [years].",
    )
    return parser.parse_args()


def _build_grids(
    t_max_years: float,
    dt_hours: float,
    r_min: float,
    r_max: float,
    n_r: int,
    cell_width_Rmars: Optional[float] = None,
) -> tuple[np.ndarray, np.ndarray]:
    if t_max_years <= 0.0:
        raise ValueError("t_max_years must be positive")
    if dt_hours <= 0.0:
        raise ValueError("dt_hours must be positive")
    if r_min <= 0.0 or r_max <= 0.0 or r_max <= r_min:
        raise ValueError("radius bounds must be positive and r_max > r_min")
    if cell_width_Rmars is None:
        if n_r <= 1:
            raise ValueError("n_r must be greater than 1")
    else:
        if cell_width_Rmars <= 0.0:
            raise ValueError("cell_width_Rmars must be positive")

    dt_s = dt_hours * 3600.0
    t_end_s = t_max_years * YEAR_SECONDS
    time_s = np.arange(0.0, t_end_s + 0.5 * dt_s, dt_s, dtype=float)
    if cell_width_Rmars is None:
        r_over_Rmars = np.linspace(r_min, r_max, n_r, dtype=float)
    else:
        edges = np.arange(r_min, r_max + cell_width_Rmars * 0.5, cell_width_Rmars, dtype=float)
        if edges[-1] < r_max:
            edges = np.append(edges, r_max)
        r_over_Rmars = 0.5 * (edges[:-1] + edges[1:])
    return time_s, r_over_Rmars


def _format_tag(T0: float) -> str:
    return f"T0{int(round(T0)):04d}K"


def _infer_cell_width_from_config(config_path: Path | None) -> Optional[float]:
    """Try to infer marsdisk cell width (R_Mars units) from a YAML config."""

    if config_path is None or not config_path.exists():
        return None
    try:
        from ruamel.yaml import YAML
    except Exception:
        return None
    try:
        yaml = YAML(typ="safe")
        with config_path.open("r", encoding="utf-8") as fh:
            cfg = yaml.load(fh)
    except Exception:
        return None
    geom = {}
    if isinstance(cfg, dict):
        geom = (
            cfg.get("disk", {}).get("geometry", {})
            if isinstance(cfg.get("disk"), dict) and isinstance(cfg.get("disk", {}).get("geometry"), dict)
            else {}
        )
    r_in = geom.get("r_in_RM")
    r_out = geom.get("r_out_RM")
    n_cells = geom.get("n_cells") or geom.get("n")
    if r_in is None or r_out is None or n_cells is None:
        return None
    try:
        span = float(r_out) - float(r_in)
        n_val = float(n_cells)
    except Exception:
        return None
    if span <= 0.0 or n_val <= 0.0:
        return None
    return span / n_val


def lookup_phase_state(
    temperature_K: float, pressure_Pa: Optional[float] = None, tau: Optional[float] = None
) -> Mapping[str, Any]:
    """Lightweight phase map compatible with ``marsdisk.physics.phase``.

    Self-shielding (``tau``) and ambient pressure both suppress the vapor fraction.
    """

    params = CoolingParams()
    T = float(temperature_K)
    pressure_bar = 0.0
    if pressure_Pa is not None:
        p_val = float(pressure_Pa)
        if np.isfinite(p_val):
            pressure_bar = max(p_val / 1.0e5, 0.0)
    tau_val: Optional[float] = None
    if tau is not None:
        tau_candidate = float(tau)
        if np.isfinite(tau_candidate):
            tau_val = max(tau_candidate, 0.0)

    if T <= params.T_glass:
        f_vap = 0.0
    elif T >= params.T_liquidus:
        f_vap = 1.0
    else:
        frac_T = (T - params.T_glass) / (params.T_liquidus - params.T_glass)
        if pressure_bar > 0.0:
            frac_T *= 1.0 / (1.0 + 0.2 * pressure_bar)
        if tau_val is not None:
            frac_T *= 1.0 / (1.0 + tau_val)
        f_vap = frac_T
    f_vap = float(np.clip(f_vap, 0.0, 1.0))
    state = "vapor" if f_vap >= 0.5 else "solid"
    return {
        "state": state,
        "f_vap": float(max(0.0, min(1.0, f_vap))),
        "temperature_K": T,
        "pressure_bar": pressure_bar,
        "tau": tau_val,
        "source": "siO2_cooling_map.lookup_phase_state",
    }


def main() -> None:
    args = _parse_args()
    params = CoolingParams()
    default_cfg = Path(__file__).resolve().parents[1] / "configs" / "base.yml"
    cfg_path = Path(args.marsdisk_config) if args.marsdisk_config else default_cfg
    t_max_years = float(args.t_max_years)
    if args.T_stop is not None:
        try:
            t_stop_s = cooling_time_to_temperature(float(args.T0), float(args.T_stop), params)
            t_stop_years = t_stop_s / YEAR_SECONDS + max(float(args.span_margin_years), 0.0)
            t_max_years = max(t_max_years, t_stop_years)
        except Exception:
            pass
    cell_width_auto = None if args.cell_width_Rmars is not None else _infer_cell_width_from_config(cfg_path)
    time_s, r_over_Rmars = _build_grids(
        t_max_years,
        args.dt_hours,
        args.r_min_Rmars,
        args.r_max_Rmars,
        args.n_r,
        args.cell_width_Rmars if args.cell_width_Rmars is not None else cell_width_auto,
    )

    arrival_glass_s, arrival_liquidus_s = compute_arrival_times(
        args.T0, params, r_over_Rmars, time_s, temperature_model=args.cooling_model
    )

    outdir = ensure_outputs_dir()
    tag = _format_tag(args.T0)
    csv_path = outdir / f"siO2_cooling_map_{tag}.csv"
    png_path = outdir / f"siO2_cooling_map_{tag}.png"
    log_path = outdir / f"log_{tag}.txt"

    write_csv(r_over_Rmars, arrival_glass_s, arrival_liquidus_s, csv_path)
    if not args.no_plot:
        plot_arrival_map(
            r_over_Rmars,
            time_s,
            arrival_glass_s,
            arrival_liquidus_s,
            png_path,
            T0=args.T0,
            params=params,
            mode=args.plot_mode,
        )
    if not args.no_log:
        write_log(args.T0, r_over_Rmars, arrival_glass_s, arrival_liquidus_s, log_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
