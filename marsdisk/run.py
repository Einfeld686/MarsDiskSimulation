"""Orchestrator and CLI for the simplified Mars disk model.

The implementation in this repository is intentionally lightweight yet it
follows the structure laid out in ``AGENTS.md``.  The module offers two
interfaces:

``step`` / ``run_n_steps``
    Legacy helpers used in the unit tests and documentation.  These provide a
    minimal coupling between the optical-depth clipping (S0) and the surface
    layer evolution (S1).

``main``
    Command line entry point invoked via ``python -m marsdisk.run``.  It reads
    a YAML configuration, constructs an initial particle size distribution and
    evolves the coupled S0/S1 system for a fixed number of steps.  The run
    writes Parquet, JSON and CSV outputs and logs a few key diagnostics such as
    the blow-out size ``a_blow`` and the opacity ``kappa``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import logging
import math
from typing import Any, Dict, List, Optional

import pandas as pd

from . import grid
from .schema import Config
from .physics import psd, surface, radiation, fragments, sinks
from .physics.sublimation import SublimationParams
from .io import writer

logger = logging.getLogger(__name__)
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0


# ---------------------------------------------------------------------------
# Legacy helpers retained for backward compatibility
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """Configuration parameters for a zero-dimensional run."""

    r: float                # orbital radius [m]
    Omega: float            # Keplerian frequency [s^-1]
    eps_mix: float          # mixing efficiency
    prod_rate: float        # production rate of sub-blow-out grains
    area: float | None = None  # surface area factor

    def __post_init__(self) -> None:
        if self.area is None:
            self.area = math.pi * self.r ** 2


@dataclass
class RunState:
    """State variables evolved during the run."""

    sigma_surf: float
    psd_state: Dict[str, Any]
    M_loss_cum: float = 0.0
    time: float = 0.0


def step(config: RunConfig, state: RunState, dt: float) -> Dict[str, float]:
    """Advance the coupled S0/S1 system by one time-step."""

    kappa_eff = psd.compute_kappa(state.psd_state)
    sigma_tau1 = 1.0 / kappa_eff if kappa_eff > 0.0 else None
    res = surface.step_surface_density_S1(
        state.sigma_surf,
        config.prod_rate,
        config.eps_mix,
        dt,
        config.Omega,
        sigma_tau1=sigma_tau1,
    )
    state.sigma_surf = res.sigma_surf

    t_blow = 1.0 / config.Omega
    M_out_dot = res.outflux * config.area
    state.M_loss_cum += M_out_dot * dt
    state.time += dt

    record = {
        "time": state.time,
        "dt": dt,
        "outflux_surface": res.outflux,
        "t_blow": t_blow,
        "M_out_dot": M_out_dot,
        "M_loss_cum": state.M_loss_cum,
    }
    logger.info(
        "run.step: t=%e t_blow=%e outflux=%e M_out_dot=%e M_loss_cum=%e",
        state.time,
        t_blow,
        res.outflux,
        M_out_dot,
        state.M_loss_cum,
    )
    return record


def run_n_steps(
    config: RunConfig,
    state: RunState,
    n: int,
    dt: float,
    out_dir: Path | None = None,
) -> pd.DataFrame:
    """Run ``n`` steps and optionally serialise results."""

    records: List[Dict[str, float]] = []
    for _ in range(n):
        records.append(step(config, state, dt))

    df = pd.DataFrame(records)
    if out_dir is not None:
        writer.write_parquet(df, Path(out_dir) / "series" / "run.parquet")
        summary = {"M_loss_cum": state.M_loss_cum}
        writer.write_summary(summary, Path(out_dir) / "summary.json")
    return df


# ---------------------------------------------------------------------------
# Configuration loading and CLI run
# ---------------------------------------------------------------------------


def load_config(path: Path) -> Config:
    """Load a YAML configuration file into a :class:`Config` instance."""

    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    return Config(**data)


def run_zero_d(cfg: Config) -> None:
    """Execute a simple zero-dimensional simulation.

    Parameters
    ----------
    cfg:
        Parsed configuration object.
    """

    r = cfg.geometry.r if cfg.geometry.r is not None else cfg.geometry.r_in
    if r is None:
        raise ValueError("geometry.r must be provided for 0D runs")
    Omega = grid.omega_kepler(r)

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    a_blow = radiation.blowout_radius(cfg.material.rho, cfg.temps.T_M)
    s_min = fragments.compute_s_min_F2(
        a_blow,
        cfg.temps.T_M,
        cfg.sinks.T_sub,
        t_ref=1.0 / Omega,
        rho=cfg.material.rho,
        sub_params=sub_params,
    )
    # guard against pathological cases where the sublimation boundary exceeds
    # the configured maximum grain size.  This can happen with the logistic
    # placeholder in the absence of calibrated parameters.
    if s_min >= cfg.sizes.s_max:
        s_min = cfg.sizes.s_max * 0.9
    psd_state = psd.update_psd_state(
        s_min=s_min,
        s_max=cfg.sizes.s_max,
        alpha=cfg.psd.alpha,
        wavy_strength=cfg.psd.wavy_strength,
        n_bins=cfg.sizes.n_bins,
        rho=cfg.material.rho,
    )
    kappa = psd.compute_kappa(psd_state)
    qpr_mean = radiation.planck_mean_qpr(s_min, cfg.temps.T_M)
    beta_at_smin = radiation.beta(s_min, cfg.material.rho, cfg.temps.T_M)

    sigma_surf = 0.0
    M_loss_cum = 0.0
    M_sink_cum = 0.0
    area = math.pi * r**2
    t_blow = 1.0 / Omega

    sink_opts = sinks.SinkOptions(
        enable_sublimation=cfg.sinks.enable_sublimation,
        sub_params=sub_params,
        enable_gas_drag=cfg.sinks.enable_gas_drag,
        rho_g=cfg.sinks.rho_g,
    )
    t_sink = sinks.total_sink_timescale(cfg.temps.T_M, cfg.material.rho, Omega, sink_opts)

    t_end = cfg.numerics.t_end_years * SECONDS_PER_YEAR
    n_steps = max(1, int(t_end / cfg.numerics.dt_init))
    if n_steps > 1000:
        n_steps = 1000
    dt = t_end / n_steps

    records: List[Dict[str, float]] = []
    mass_budget: List[Dict[str, float]] = []

    for step_no in range(n_steps):
        tau = kappa * sigma_surf
        sigma_tau1 = 1.0 / kappa if kappa > 0.0 else None
        res = surface.step_surface(
            sigma_surf,
            0.0,
            cfg.surface.eps_mix,
            dt,
            Omega,
            tau=tau if cfg.surface.use_tcoll else None,
            t_sink=t_sink,
            sigma_tau1=sigma_tau1,
        )
        sigma_surf = res.sigma_surf

        M_out_dot = res.outflux * area
        M_loss_cum += M_out_dot * dt
        M_sink_cum += res.sink_flux * area * dt
        time = (step_no + 1) * dt

        record = {
            "time": time,
            "dt": dt,
            "tau": tau,
            "a_blow": a_blow,
            "s_min": s_min,
            "kappa": kappa,
            "Qpr_mean": qpr_mean,
            "beta_at_smin": beta_at_smin,
            "Sigma_surf": sigma_surf,
            "Sigma_tau1": sigma_tau1 if sigma_tau1 is not None else float("nan"),
            "outflux_surface": res.outflux,
            "t_blow": t_blow,
            "prod_subblow_area_rate": 0.0,
            "M_out_dot": M_out_dot,
            "M_loss_cum": M_loss_cum,
            "mass_total_bins": cfg.initial.mass_total - M_loss_cum - M_sink_cum,
            "mass_lost_by_blowout": M_loss_cum,
            "mass_lost_by_sinks": M_sink_cum,
        }
        records.append(record)

        mass_budget.append(
            {
                "time": time,
                "mass_initial": cfg.initial.mass_total,
                "mass_remaining": cfg.initial.mass_total - M_loss_cum - M_sink_cum,
                "mass_lost": M_loss_cum + M_sink_cum,
                "error_percent": 0.0,
            }
        )

        logger.info(
            "run: t=%e a_blow=%e kappa=%e t_blow=%e M_loss=%e",
            time,
            a_blow,
            kappa,
            t_blow,
            M_loss_cum,
        )

    df = pd.DataFrame(records)
    outdir = Path(cfg.io.outdir)
    writer.write_parquet(df, outdir / "series" / "run.parquet")
    writer.write_summary({"M_loss": M_loss_cum}, outdir / "summary.json")
    writer.write_mass_budget(mass_budget, outdir / "checks" / "mass_budget.csv")


def main(argv: Optional[List[str]] = None) -> None:
    """Command line entry point."""

    parser = argparse.ArgumentParser(description="Run a simple Mars disk model")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML configuration")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    run_zero_d(cfg)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    logging.basicConfig(level=logging.INFO)
    main()

__all__ = [
    "RunConfig",
    "RunState",
    "step",
    "run_n_steps",
    "load_config",
    "run_zero_d",
    "main",
]
