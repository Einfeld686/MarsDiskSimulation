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
import random
import subprocess
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from . import grid
from .schema import Config
from .physics import (
    psd,
    surface,
    radiation,
    fragments,
    sinks,
    supply,
    initfields,
    shielding,
)
from .io import writer, tables
from .physics.sublimation import SublimationParams
from . import constants

logger = logging.getLogger(__name__)
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
MAX_STEPS = 1000
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345


# ---------------------------------------------------------------------------
# Legacy helpers retained for backward compatibility
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """Configuration parameters for a zero-dimensional run."""

    r: float                # orbital radius [m]
    Omega: float            # Keplerian frequency [s^-1]
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

    kappa_surf = psd.compute_kappa(state.psd_state)
    tau = kappa_surf * state.sigma_surf
    kappa_eff, sigma_tau1 = shielding.apply_shielding(kappa_surf, tau, 0.0, 0.0)
    if kappa_eff <= KAPPA_MIN:
        sigma_tau1 = None
    res = surface.step_surface_density_S1(
        state.sigma_surf,
        config.prod_rate,
        dt,
        config.Omega,
        sigma_tau1=sigma_tau1,
    )
    state.sigma_surf = res.sigma_surf

    t_blow = 1.0 / config.Omega
    # kg/s -> M_Mars/s
    M_out_dot = (res.outflux * config.area) / constants.M_MARS
    state.M_loss_cum += M_out_dot * dt
    state.time += dt

    record = {
        "time": state.time,
        "dt": dt,
        "outflux_surface": res.outflux,
        "sink_flux_surface": res.sink_flux,
        "t_blow": t_blow,
        "M_out_dot": M_out_dot,  # M_Mars/s
        "M_loss_cum": state.M_loss_cum,  # M_Mars
    }
    logger.info(
        "run.step: t=%e t_blow=%e outflux=%e M_out_dot[M_Mars/s]=%e M_loss_cum[M_Mars]=%e",
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
        summary = {"M_loss": state.M_loss_cum}  # M_Mars
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


def _gather_git_info() -> Dict[str, Any]:
    """Return basic git metadata for provenance recording."""

    repo_root = Path(__file__).resolve().parents[1]
    info: Dict[str, Any] = {}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["commit"] = "unknown"
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["branch"] = "unknown"
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=repo_root, text=True
        )
        info["dirty"] = bool(status.strip())
    except Exception:
        info["dirty"] = None
    return info


def run_zero_d(cfg: Config) -> None:
    """Execute a simple zero-dimensional simulation.

    Parameters
    ----------
    cfg:
        Parsed configuration object.
    """

    random.seed(DEFAULT_SEED)
    np.random.seed(DEFAULT_SEED)

    if cfg.geometry.r is not None:
        r = cfg.geometry.r
    elif cfg.disk is not None:
        r = (
            0.5
            * (cfg.disk.geometry.r_in_RM + cfg.disk.geometry.r_out_RM)
            * constants.R_MARS
        )
    elif cfg.geometry.r_in is not None:
        r = cfg.geometry.r_in
    else:
        raise ValueError("geometry.r must be provided for 0D runs")
    Omega = grid.omega_kepler(r)

    qpr_override = None
    if cfg.radiation and cfg.radiation.qpr_table is not None:
        tables.load_qpr_table(cfg.radiation.qpr_table)
    if cfg.radiation and cfg.radiation.Q_pr is not None:
        qpr_override = cfg.radiation.Q_pr
    T_M = (
        cfg.radiation.TM_K
        if cfg.radiation and cfg.radiation.TM_K is not None
        else cfg.temps.T_M
    )
    rho_used = cfg.material.rho

    phi_tau_fn = None
    if cfg.shielding and cfg.shielding.phi_table:
        phi_tau_fn = shielding.load_phi_table(cfg.shielding.phi_table)

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    a_blow = radiation.blowout_radius(rho_used, T_M, Q_pr=qpr_override)
    s_min = fragments.compute_s_min_F2(
        a_blow,
        T_M,
        cfg.sinks.T_sub,
        t_ref=1.0 / Omega,
        rho=rho_used,
        sub_params=sub_params,
    )
    # guard against pathological cases where the sublimation boundary exceeds
    # the configured maximum grain size.  This can happen with the logistic
    # placeholder in the absence of calibrated parameters.
    if s_min >= cfg.sizes.s_max:
        s_min = cfg.sizes.s_max * 0.9
    s_min_config = cfg.sizes.s_min
    s_min_effective = s_min
    if s_min_effective > s_min_config:
        logger.info(
            "Effective s_min raised from config value %.3e m to %.3e m",
            s_min_config,
            s_min_effective,
        )
    psd_state = psd.update_psd_state(
        s_min=s_min,
        s_max=cfg.sizes.s_max,
        alpha=cfg.psd.alpha,
        wavy_strength=cfg.psd.wavy_strength,
        n_bins=cfg.sizes.n_bins,
        rho=rho_used,
    )
    kappa_surf = psd.compute_kappa(psd_state)
    qpr_mean = radiation.planck_mean_qpr(s_min, T_M, Q_pr=qpr_override)
    beta_at_smin = radiation.beta(s_min, rho_used, T_M, Q_pr=qpr_override)
    case_status = "blowout" if beta_at_smin >= radiation.BLOWOUT_BETA_THRESHOLD else "failed"
    if case_status != "blowout":
        logger.warning(
            "Blow-out threshold not met at s_min=%.3e m (β=%.3f)", s_min, beta_at_smin
        )

    if cfg.disk is not None and cfg.inner_disk_mass is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        if cfg.inner_disk_mass.use_Mmars_ratio:
            M_in = cfg.inner_disk_mass.M_in_ratio * constants.M_MARS
        else:
            M_in = cfg.inner_disk_mass.M_in_ratio
        sigma_func = initfields.sigma_from_Minner(
            M_in,
            r_in_d,
            r_out_d,
            cfg.disk.geometry.p_index,
        )
        sigma_mid = sigma_func(r)
        kappa_for_init = kappa_surf
        if phi_tau_fn is not None:
            tau_mid = kappa_surf * sigma_mid
            kappa_for_init = shielding.effective_kappa(kappa_surf, tau_mid, phi_tau_fn)
        sigma_surf = initfields.surf_sigma_init(
            sigma_mid,
            kappa_for_init,
            cfg.surface.init_policy,
            sigma_override=cfg.surface.sigma_surf_init_override,
        )
    else:
        sigma_surf = 0.0
    M_loss_cum = 0.0
    M_sink_cum = 0.0
    if cfg.disk is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        area = math.pi * (r_out_d**2 - r_in_d**2)
    else:
        area = math.pi * r**2
    t_blow = 1.0 / Omega

    sink_opts = sinks.SinkOptions(
        enable_sublimation=cfg.sinks.enable_sublimation,
        sub_params=sub_params,
        enable_gas_drag=cfg.sinks.enable_gas_drag,
        rho_g=cfg.sinks.rho_g,
    )
    t_sink = sinks.total_sink_timescale(T_M, rho_used, Omega, sink_opts)

    supply_spec = cfg.supply

    t_end = cfg.numerics.t_end_years * SECONDS_PER_YEAR
    n_steps = max(1, math.ceil(t_end / max(cfg.numerics.dt_init, 1.0)))
    if n_steps > MAX_STEPS:
        n_steps = MAX_STEPS
    dt = t_end / n_steps

    records: List[Dict[str, float]] = []
    mass_budget: List[Dict[str, float]] = []

    for step_no in range(n_steps):
        time = step_no * dt
        tau = kappa_surf * sigma_surf
        if phi_tau_fn is not None:
            kappa_eff = shielding.effective_kappa(kappa_surf, tau, phi_tau_fn)
            sigma_tau1_limit = shielding.sigma_tau1(kappa_eff)
        else:
            kappa_eff, sigma_tau1_limit = shielding.apply_shielding(kappa_surf, tau, 0.0, 0.0)
        tau_for_coll = None if (not cfg.surface.use_tcoll or tau <= TAU_MIN) else tau
        prod_rate = supply.get_prod_area_rate(time, r, supply_spec)
        res = surface.step_surface(
            sigma_surf,
            prod_rate,
            dt,
            Omega,
            tau=tau_for_coll,
            t_sink=t_sink,
            sigma_tau1=sigma_tau1_limit,
        )
        sigma_surf = res.sigma_surf

        # kg/s -> M_Mars/s
        M_out_dot = (res.outflux * area) / constants.M_MARS
        M_sink_dot = (res.sink_flux * area) / constants.M_MARS
        # integrate as M_Mars
        M_loss_cum += M_out_dot * dt
        M_sink_cum += M_sink_dot * dt
        time = (step_no + 1) * dt

        record = {
            "time": time,
            "dt": dt,
            "tau": tau,
            "a_blow": a_blow,
            "s_min": s_min,
            "kappa": kappa_eff,
            "Qpr_mean": qpr_mean,
            "beta_at_smin": beta_at_smin,
            "beta_threshold": radiation.BLOWOUT_BETA_THRESHOLD,
            "Sigma_surf": sigma_surf,
            "Sigma_tau1": sigma_tau1_limit,
            "outflux_surface": res.outflux,
            "sink_flux_surface": res.sink_flux,
            "t_blow": t_blow,
            "prod_subblow_area_rate": prod_rate,
            "M_out_dot": M_out_dot,                                                # M_Mars/s
            "M_loss_cum": M_loss_cum + M_sink_cum,                                 # M_Mars
            "mass_total_bins": cfg.initial.mass_total - (M_loss_cum + M_sink_cum), # M_Mars
            "mass_lost_by_blowout": M_loss_cum,                                    # M_Mars
            "mass_lost_by_sinks": M_sink_cum,                                      # M_Mars
            "case_status": case_status,
            "s_blow_m": a_blow,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean,
            "s_min_effective": s_min_effective,
            "s_min_config": s_min_config,
            "s_min_effective_gt_config": s_min_effective > s_min_config,
        }
        records.append(record)

        mass_initial = cfg.initial.mass_total
        mass_remaining = mass_initial - (M_loss_cum + M_sink_cum)
        mass_lost = M_loss_cum + M_sink_cum
        mass_diff = mass_initial - mass_remaining - mass_lost
        error_percent = 0.0
        if mass_initial != 0.0:
            error_percent = abs(mass_diff / mass_initial) * 100.0
        mass_budget.append(
            {
                "time": time,
                "mass_initial": mass_initial,      # M_Mars
                "mass_remaining": mass_remaining,  # M_Mars
                "mass_lost": mass_lost,            # M_Mars
                "error_percent": error_percent,
            }
        )

        logger.info(
            "run: t=%e a_blow=%e kappa=%e t_blow=%e M_loss[M_Mars]=%e",
            time,
            a_blow,
            kappa_eff,
            t_blow,
            M_loss_cum + M_sink_cum,
        )

    df = pd.DataFrame(records)
    outdir = Path(cfg.io.outdir)
    writer.write_parquet(df, outdir / "series" / "run.parquet")
    summary = {
        "M_loss": (M_loss_cum + M_sink_cum),
        "case_status": case_status,
        "beta_threshold": radiation.BLOWOUT_BETA_THRESHOLD,
        "beta_at_smin": beta_at_smin,
        "s_blow_m": a_blow,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean,
        "T_M_used": T_M,
        "s_min_effective": s_min_effective,
        "s_min_config": s_min_config,
        "s_min_effective_gt_config": s_min_effective > s_min_config,
    }
    writer.write_summary(summary, outdir / "summary.json")
    writer.write_mass_budget(mass_budget, outdir / "checks" / "mass_budget.csv")
    run_config = {
        "beta_formula": "beta = 3 σ_SB T_M^4 R_M^2 Q_pr / (4 G M_M c ρ s)",
        "s_blow_formula": "s_blow = 3 σ_SB T_M^4 R_M^2 Q_pr / (2 G M_M c ρ)",
        "defaults": {
            "Q_pr": radiation.DEFAULT_Q_PR,
            "rho": radiation.DEFAULT_RHO,
            "T_M_range_K": list(radiation.T_M_RANGE),
            "beta_threshold": radiation.BLOWOUT_BETA_THRESHOLD,
        },
        "constants": {
            "G": constants.G,
            "C": constants.C,
            "SIGMA_SB": constants.SIGMA_SB,
            "M_MARS": constants.M_MARS,
            "R_MARS": constants.R_MARS,
        },
        "run_inputs": {
            "T_M_used": T_M,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean,
        },
        "git": _gather_git_info(),
    }
    writer.write_run_config(run_config, outdir / "run_config.json")


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
