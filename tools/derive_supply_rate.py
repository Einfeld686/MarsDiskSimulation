"""Utility to derive constant surface supply rates from μ, Σ_tau=1, and t_blow.

This script computes the raw production rate ``R_base`` such that

    R_base = μ Σ_tau=1 / (ε_mix t_blow)

where ``t_blow = 1 / Ω(r)`` when a radius is supplied.  Σ_tau=1 is前提として
火星視線方向の τ≲1 層（Σ_tau1_los）で評価した値を用いることを想定する。
The resulting value
can be plugged into ``supply.const.prod_area_rate_kg_m2_s``; the mixing factor
``ε_mix`` is excluded here because :func:`marsdisk.physics.supply.get_prod_area_rate`
applies it internally.

Examples
--------
Single value in text form:

    python -m tools.derive_supply_rate --mu 0.3 --sigma-tau1 1.0 --t-blow 1000 --epsilon-mix 1.0

YAML snippet:

    python -m tools.derive_supply_rate --mu 0.3 --sigma-tau1 1.0 --t-blow 1000 --format yaml

CSV grid over radius and μ (radius in Mars radii by default):

    python -m tools.derive_supply_rate --sigma-tau1 1.0 --epsilon-mix 0.5 \
        --r-grid "2.0,2.5,3.0" --mu-grid "0.1,0.3,1.0" --format csv
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional
from pathlib import Path

from ruamel.yaml import YAML

from marsdisk import constants, grid

DEFAULT_R_UNIT = "RM"  # Mars radii


@dataclass(frozen=True)
class SupplyInputs:
    mu: float
    sigma_tau1: float
    epsilon_mix: float
    t_blow: float


def _parse_float_list(raw: str) -> List[float]:
    return [float(x) for x in raw.split(",") if x.strip() != ""]


def _radius_to_meters(r_value: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "m":
        return r_value
    if unit in ("rm", "r_mars"):
        return r_value * constants.R_MARS
    raise ValueError(f"Unsupported radius unit: {unit}")


def _t_blow_from_radius(r_m: float) -> float:
    omega = grid.omega_kepler(r_m)
    if omega <= 0.0 or not math.isfinite(omega):
        raise ValueError("Computed non-positive Omega from radius")
    return 1.0 / omega


def compute_r_base(inputs: SupplyInputs) -> float:
    """Compute R_base = μ Σ_tau1 / (ε_mix t_blow) with validation."""
    if inputs.mu <= 0.0 or not math.isfinite(inputs.mu):
        raise ValueError("mu must be positive and finite")
    if inputs.sigma_tau1 <= 0.0 or not math.isfinite(inputs.sigma_tau1):
        raise ValueError("sigma_tau1 must be positive and finite")
    if inputs.epsilon_mix <= 0.0 or not math.isfinite(inputs.epsilon_mix):
        raise ValueError("epsilon_mix must be positive and finite")
    if inputs.t_blow <= 0.0 or not math.isfinite(inputs.t_blow):
        raise ValueError("t_blow must be positive and finite")
    return (inputs.mu * inputs.sigma_tau1) / (inputs.epsilon_mix * inputs.t_blow)


def _format_yaml(rate: float) -> str:
    return (
        "supply:\n"
        "  mode: \"const\"\n"
        "  const:\n"
        f"    prod_area_rate_kg_m2_s: {rate:.12e}\n"
    )


def _write_csv(
    rows: Iterable[dict],
    fieldnames: List[str],
    stream,
) -> None:
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Derive supply.const.prod_area_rate_kg_m2_s from μ, Σ_tau=1, and t_blow.",
    )
    parser.add_argument("--mu", type=float, help="Dimensionless μ = dotSigma_prod * t_blow / Σ_tau=1")
    parser.add_argument("--sigma-tau1", type=float, dest="sigma_tau1", help="Σ_{τ=1} in kg/m^2 (falls back to config/env)")
    parser.add_argument("--t-blow", type=float, dest="t_blow", help="Blow-out time-scale [s]. If omitted, supply radius.")
    parser.add_argument("--epsilon-mix", type=float, dest="epsilon_mix", help="Mixing efficiency ε_mix (falls back to config/env, default 1.0)")
    parser.add_argument("--r", type=float, help="Orbital radius. Used to compute t_blow when --t-blow is absent.")
    parser.add_argument("--r-unit", choices=["RM", "rm", "m", "R_MARS"], default=DEFAULT_R_UNIT, help="Radius unit (default: RM = Mars radii)")
    parser.add_argument("--format", choices=["text", "yaml", "csv"], default="text", help="Output format")
    parser.add_argument("--mu-grid", type=str, help="Comma-separated μ values for CSV/table output")
    parser.add_argument("--r-grid", type=str, help="Comma-separated radii for CSV/table output")
    parser.add_argument("--config", type=str, help="Optional YAML config to read epsilon_mix / sigma_tau1 defaults")
    return parser


def _resolve_t_blow(args) -> float:
    if args.t_blow is not None:
        return float(args.t_blow)
    if args.r is None:
        raise ValueError("Provide --t-blow or --r to compute t_blow from radius")
    r_m = _radius_to_meters(args.r, args.r_unit)
    return _t_blow_from_radius(r_m)


def _load_config_defaults(config_path: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if config_path is None:
        return None, None
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    yaml = YAML(typ="safe")
    data = yaml.load(path)
    if not isinstance(data, dict):
        return None, None
    epsilon_mix = None
    sigma_tau1 = None
    supply = data.get("supply")
    if isinstance(supply, dict):
        mixing = supply.get("mixing")
        if isinstance(mixing, dict):
            epsilon_mix = mixing.get("epsilon_mix", epsilon_mix)
    shielding = data.get("shielding")
    if isinstance(shielding, dict):
        sigma_tau1 = shielding.get("fixed_tau1_sigma", sigma_tau1)
    return epsilon_mix, sigma_tau1


def _single_output(args, rate: float) -> str:
    if args.format == "yaml":
        return _format_yaml(rate)
    return f"prod_area_rate_kg_m2_s={rate:.12e}"


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    cfg_eps, cfg_sigma = _load_config_defaults(args.config)
    env_sigma = os.environ.get("MARS_DISK_SIGMA_TAU1")
    env_eps = os.environ.get("MARS_DISK_EPSILON_MIX")

    sigma_tau1 = (
        args.sigma_tau1
        if args.sigma_tau1 is not None
        else (float(env_sigma) if env_sigma is not None else cfg_sigma)
    )
    epsilon_mix = (
        args.epsilon_mix
        if args.epsilon_mix is not None
        else (
            float(env_eps)
            if env_eps is not None
            else cfg_eps
            if cfg_eps is not None
            else 0.05
        )
    )
    if sigma_tau1 is None:
        raise ValueError(
            "sigma_tau1 is required (Σ_tau1_los along the Mars line of sight). "
            "Provide --sigma-tau1, set MARS_DISK_SIGMA_TAU1, or set shielding.fixed_tau1_sigma in the config."
        )

    if args.format == "csv":
        mu_values = _parse_float_list(args.mu_grid) if args.mu_grid else []
        r_values = _parse_float_list(args.r_grid) if args.r_grid else []
        if not mu_values:
            raise ValueError("--mu-grid is required for csv output")
        if not r_values:
            raise ValueError("--r-grid is required for csv output")
        if sigma_tau1 is None:
            raise ValueError("--sigma-tau1 is required (or provide via env/config) for csv output")
        sigma_val = sigma_tau1
        eps_val = epsilon_mix
        rows = []
        for r_val in r_values:
            r_m = _radius_to_meters(r_val, args.r_unit)
            t_blow = _t_blow_from_radius(r_m)
            for mu_val in mu_values:
                rate = compute_r_base(
                    SupplyInputs(
                        mu=mu_val,
                        sigma_tau1=sigma_val,
                        epsilon_mix=eps_val,
                        t_blow=t_blow,
                    )
                )
                rows.append(
                    {
                        "r": r_val,
                        "r_unit": args.r_unit,
                        "mu": mu_val,
                        "sigma_tau1": sigma_val,
                        "epsilon_mix": eps_val,
                        "t_blow": t_blow,
                        "prod_area_rate_kg_m2_s": rate,
                    }
                )
        _write_csv(
            rows,
            ["r", "r_unit", "mu", "sigma_tau1", "epsilon_mix", "t_blow", "prod_area_rate_kg_m2_s"],
            sys.stdout,
        )
        return 0

    if args.mu is None:
        raise ValueError("--mu is required for text/yaml output")
    if sigma_tau1 is None:
        raise ValueError("--sigma-tau1 is required (or provide via env/config)")

    t_blow = _resolve_t_blow(args)
    mu_val = args.mu
    sigma_val = sigma_tau1
    eps_val = epsilon_mix

    rate = compute_r_base(
        SupplyInputs(
            mu=mu_val,
            sigma_tau1=sigma_val,
            epsilon_mix=eps_val,
            t_blow=t_blow,
        )
    )
    sys.stdout.write(_single_output(args, rate) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via tests
    raise SystemExit(main())
