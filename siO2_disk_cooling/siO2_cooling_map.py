"""CLI entry point for generating SiO2 cooling maps."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .io_utils import ensure_outputs_dir, write_csv, write_log
from .model import CoolingParams, YEAR_SECONDS, compute_arrival_times
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
    parser.add_argument("--no-log", action="store_true", help="Skip writing the text log")
    parser.add_argument("--no-plot", action="store_true", help="Skip writing the PNG plot")
    return parser.parse_args()


def _build_grids(
    t_max_years: float, dt_hours: float, r_min: float, r_max: float, n_r: int
) -> tuple[np.ndarray, np.ndarray]:
    if t_max_years <= 0.0:
        raise ValueError("t_max_years must be positive")
    if dt_hours <= 0.0:
        raise ValueError("dt_hours must be positive")
    if r_min <= 0.0 or r_max <= 0.0 or r_max <= r_min:
        raise ValueError("radius bounds must be positive and r_max > r_min")
    if n_r <= 1:
        raise ValueError("n_r must be greater than 1")

    dt_s = dt_hours * 3600.0
    t_end_s = t_max_years * YEAR_SECONDS
    time_s = np.arange(0.0, t_end_s + 0.5 * dt_s, dt_s, dtype=float)
    r_over_Rmars = np.linspace(r_min, r_max, n_r, dtype=float)
    return time_s, r_over_Rmars


def _format_tag(T0: float) -> str:
    return f"T0{int(round(T0)):04d}K"


def lookup_phase_state(
    temperature_K: float, pressure_Pa: Optional[float] = None, tau: Optional[float] = None
) -> Dict[str, Any]:
    """Lightweight phase map compatible with ``marsdisk.physics.phase``."""

    params = CoolingParams()
    T = float(temperature_K)
    if T <= params.T_glass:
        f_vap = 0.0
    elif T >= params.T_liquidus:
        f_vap = 1.0
    else:
        f_vap = (T - params.T_glass) / (params.T_liquidus - params.T_glass)
    state = "vapor" if f_vap >= 0.5 else "solid"
    return {
        "state": state,
        "f_vap": float(max(0.0, min(1.0, f_vap))),
        "temperature_K": T,
        "pressure_bar": None if pressure_Pa is None else float(pressure_Pa) / 1.0e5,
        "tau": tau,
        "source": "siO2_cooling_map.lookup_phase_state",
    }


def main() -> None:
    args = _parse_args()
    params = CoolingParams()
    time_s, r_over_Rmars = _build_grids(
        args.t_max_years, args.dt_hours, args.r_min_Rmars, args.r_max_Rmars, args.n_r
    )

    arrival_glass_s, arrival_liquidus_s = compute_arrival_times(
        args.T0, params, r_over_Rmars, time_s
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
        )
    if not args.no_log:
        write_log(args.T0, r_over_Rmars, arrival_glass_s, arrival_liquidus_s, log_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
