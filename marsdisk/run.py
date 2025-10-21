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

import argparse
import logging
import math
import random
import subprocess
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
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
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6


def _resolve_temperature(cfg: Config) -> tuple[float, str]:
    """Return the Mars-facing temperature used for radiation calculations."""

    if cfg.radiation is not None and cfg.radiation.TM_K is not None:
        return cfg.radiation.TM_K, "radiation.TM_K"
    return cfg.temps.T_M, "temps.T_M"


def _derive_seed_components(cfg: Config) -> str:
    parts: list[str] = []
    parts.append(f"geometry.r={getattr(cfg.geometry, 'r', None)!r}")
    if cfg.disk is not None:
        parts.append(
            f"disk.r_in_RM={cfg.disk.geometry.r_in_RM!r},r_out_RM={cfg.disk.geometry.r_out_RM!r}"
        )
    parts.append(f"temps.T_M={cfg.temps.T_M!r}")
    parts.append(f"initial.mass_total={cfg.initial.mass_total!r}")
    return "|".join(parts)


def _resolve_seed(cfg: Config) -> tuple[int, str, str]:
    """Return the RNG seed, seed expression description, and basis."""

    if cfg.dynamics.rng_seed is not None:
        seed_val = int(cfg.dynamics.rng_seed)
        return seed_val, "cfg.dynamics.rng_seed", "user"

    basis = _derive_seed_components(cfg)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    seed_val = int(digest[:8], 16) % (2**31)
    safe_basis = basis.replace("'", r"\'")
    expr = f"sha256('{safe_basis}') % 2**31"
    return seed_val, expr, basis


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


class MassBudgetViolationError(RuntimeError):
    """Raised when the mass budget tolerance is exceeded."""


def run_zero_d(cfg: Config, *, enforce_mass_budget: bool = False) -> None:
    """Execute a simple zero-dimensional simulation.

    Parameters
    ----------
    cfg:
        Parsed configuration object.
    """

    seed, seed_expr, seed_basis = _resolve_seed(cfg)
    random.seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    e0_effective = cfg.dynamics.e0
    i0_effective = cfg.dynamics.i0
    delta_r_sample = None

    if cfg.dynamics.e_mode == "mars_clearance":
        if cfg.geometry.r is None:
            raise ValueError(
                "dynamics.e_mode='mars_clearance' requires geometry.r in meters"
            )
        a_m = cfg.geometry.r
        dr_min = cfg.dynamics.dr_min_m
        dr_max = cfg.dynamics.dr_max_m
        if dr_min is not None and dr_max is not None:
            if dr_min > dr_max:
                raise ValueError(
                    "dynamics.dr_min_m must be smaller than dynamics.dr_max_m in meters"
                )
            if cfg.dynamics.dr_dist == "uniform":
                delta_r_sample = float(rng.uniform(dr_min, dr_max))
            else:
                if dr_min <= 0.0 or dr_max <= 0.0:
                    raise ValueError(
                        "loguniform Δr sampling requires positive meter bounds"
                    )
                log_min = math.log(dr_min)
                log_max = math.log(dr_max)
                delta_r_sample = float(math.exp(rng.uniform(log_min, log_max)))
        elif dr_min is not None:
            delta_r_sample = float(dr_min)
        elif dr_max is not None:
            delta_r_sample = float(dr_max)
        else:
            raise ValueError(
                "dynamics.dr_min_m or dynamics.dr_max_m must be specified in meters "
                "when using e_mode='mars_clearance'"
            )
        e0_sample = 1.0 - (constants.R_MARS + delta_r_sample) / a_m
        e0_clamped = float(np.clip(e0_sample, 0.0, 0.999999))
        if not math.isclose(e0_clamped, e0_sample, rel_tol=0.0, abs_tol=1e-12):
            logger.warning(
                "Sampled eccentricity %.6f clamped to %.6f to stay within [0, 0.999999]",
                e0_sample,
                e0_clamped,
            )
        e0_effective = e0_clamped
        cfg.dynamics.e0 = e0_effective

    i_center_rad = float(np.deg2rad(cfg.dynamics.obs_tilt_deg))
    spread_rad = float(np.deg2rad(cfg.dynamics.i_spread_deg))
    if cfg.dynamics.i_mode == "obs_tilt_spread":
        if spread_rad > 0.0:
            lower = max(i_center_rad - spread_rad, 0.0)
            upper = min(i_center_rad + spread_rad, 0.5 * np.pi)
            if lower >= upper:
                i_sample = lower
            else:
                i_sample = float(rng.uniform(lower, upper))
        else:
            i_sample = i_center_rad
        i_clamped = float(np.clip(i_sample, 0.0, 0.5 * np.pi))
        if not math.isclose(i_clamped, i_sample, rel_tol=0.0, abs_tol=1e-12):
            logger.warning(
                "Sampled inclination %.6f rad clamped to %.6f rad to stay within [0, pi/2]",
                i_sample,
                i_clamped,
            )
        i0_effective = i_clamped
        cfg.dynamics.i0 = i0_effective

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
    if Omega <= 0.0:
        raise ValueError("Computed Keplerian frequency must be positive")
    t_orb = 2.0 * math.pi / Omega

    qpr_override = None
    if cfg.radiation and cfg.radiation.qpr_table is not None:
        tables.load_qpr_table(cfg.radiation.qpr_table)
    if cfg.radiation and cfg.radiation.Q_pr is not None:
        qpr_override = cfg.radiation.Q_pr
    T_use, T_M_source = _resolve_temperature(cfg)
    rho_used = cfg.material.rho

    phi_tau_fn = None
    if cfg.shielding and cfg.shielding.phi_table:
        phi_tau_fn = shielding.load_phi_table(cfg.shielding.phi_table)

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    setattr(sub_params, "runtime_orbital_radius_m", r)
    setattr(sub_params, "runtime_t_orb_s", t_orb)
    setattr(sub_params, "runtime_Omega", Omega)
    a_blow = radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_override)
    s_min_config = cfg.sizes.s_min
    s_sub_component = 0.0
    if cfg.sinks.mode != "none" and cfg.sinks.enable_sublimation:
        # Documented in analysis/sinks_callgraph.md: HK boundary lifts s_min
        # through fragments.s_sub_boundary and feeds summary s_min_components.
        s_sub_component = fragments.s_sub_boundary(
            T_use,
            cfg.sinks.T_sub,
            t_ref=t_orb,
            rho=rho_used,
            sub_params=sub_params,
        )
    s_min_components = {
        "config": float(s_min_config),
        "blowout": float(a_blow),
        "sublimation": float(s_sub_component),
    }
    s_min_pre_clip = max(s_min_components["blowout"], s_min_components["sublimation"])
    s_min_effective = max(s_min_components["config"], s_min_pre_clip)
    # guard against pathological cases where the sublimation boundary exceeds
    # the configured maximum grain size.  This can happen with the logistic
    # placeholder in the absence of calibrated parameters.
    if s_min_effective >= cfg.sizes.s_max:
        s_min_effective = cfg.sizes.s_max * 0.9
    s_min_components["effective"] = float(s_min_effective)
    if s_min_effective > s_min_config:
        logger.info(
            "Effective s_min raised from config value %.3e m to %.3e m",
            s_min_config,
            s_min_effective,
        )
    psd_state = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=cfg.sizes.s_max,
        alpha=cfg.psd.alpha,
        wavy_strength=cfg.psd.wavy_strength,
        n_bins=cfg.sizes.n_bins,
        rho=rho_used,
    )
    kappa_surf = psd.compute_kappa(psd_state)
    qpr_mean = radiation.planck_mean_qpr(s_min_effective, T_use, Q_pr=qpr_override)
    beta_at_smin_config = radiation.beta(s_min_config, rho_used, T_use, Q_pr=qpr_override)
    beta_at_smin_effective = radiation.beta(
        s_min_effective, rho_used, T_use, Q_pr=qpr_override
    )
    beta_threshold = radiation.BLOWOUT_BETA_THRESHOLD
    case_status = "blowout" if beta_at_smin_config >= beta_threshold else "ok"
    if case_status != "blowout":
        logger.info(
            "Blow-out threshold not met at s_min_config=%.3e m (β=%.3f)",
            s_min_config,
            beta_at_smin_config,
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
    M_sublimation_cum = 0.0
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

    supply_spec = cfg.supply

    t_end = cfg.numerics.t_end_years * SECONDS_PER_YEAR
    n_steps = max(1, math.ceil(t_end / max(cfg.numerics.dt_init, 1.0)))
    if n_steps > MAX_STEPS:
        n_steps = MAX_STEPS
    dt = t_end / n_steps

    records: List[Dict[str, float]] = []
    mass_budget: List[Dict[str, float]] = []
    mass_budget_violation: Optional[Dict[str, float]] = None
    violation_triggered = False
    debug_sinks_enabled = bool(getattr(cfg.io, "debug_sinks", False))
    debug_records: List[Dict[str, Any]] = []

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
        if cfg.sinks.mode == "none":
            sink_result = sinks.SinkTimescaleResult(
                t_sink=None,
                components={"sublimation": None, "gas_drag": None},
                dominant_sink=None,
                T_eval=T_use,
                s_ref=SINK_REF_SIZE,
            )
        else:
            sink_result = sinks.total_sink_timescale(
                T_use,
                rho_used,
                Omega,
                sink_opts,
                s_ref=SINK_REF_SIZE,
            )
        t_sink = sink_result.t_sink
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

        outflux_mass_rate_kg = res.outflux * area
        sink_mass_rate_kg = res.sink_flux * area
        # kg/s -> M_Mars/s
        M_out_dot = outflux_mass_rate_kg / constants.M_MARS
        M_sink_dot = sink_mass_rate_kg / constants.M_MARS
        # integrate as M_Mars
        M_loss_cum += M_out_dot * dt
        M_sink_cum += M_sink_dot * dt
        if sink_result.sublimation_fraction > 0.0:
            M_sublimation_cum += M_sink_dot * dt * sink_result.sublimation_fraction
        time = (step_no + 1) * dt

        if debug_sinks_enabled:
            T_d = sink_result.T_eval if sink_result.t_sink is not None else None
            debug_records.append(
                {
                    "step": int(step_no),
                    "time_s": time,
                    "dt_s": dt,
                    "T_M_K": T_use,
                    "T_d_graybody_K": T_d,
                    "T_source": T_M_source,
                    "r_m": r,
                    "t_sink_s": t_sink,
                    "dominant_sink": sink_result.dominant_sink,
                    "sublimation_timescale_s": sink_result.components.get("sublimation"),
                    "gas_drag_timescale_s": sink_result.components.get("gas_drag"),
                    "total_sink_dm_dt_kg_s": sink_mass_rate_kg,
                    "sublimation_dm_dt_kg_s": (
                        sink_mass_rate_kg if sink_result.dominant_sink == "sublimation" else 0.0
                    ),
                    "cum_sink_mass_kg": M_sink_cum * constants.M_MARS,
                    "cum_sublimation_mass_kg": M_sublimation_cum * constants.M_MARS,
                    "blowout_mass_rate_kg_s": outflux_mass_rate_kg,
                    "cum_blowout_mass_kg": M_loss_cum * constants.M_MARS,
                    "M_loss_components_Mmars": {
                        "blowout": M_loss_cum,
                        "sinks": M_sink_cum,
                        "total": M_loss_cum + M_sink_cum,
                    },
                    "sinks_mode": cfg.sinks.mode,
                    "enable_sublimation": cfg.sinks.enable_sublimation,
                    "enable_gas_drag": cfg.sinks.enable_gas_drag,
                    "s_ref_m": sink_result.s_ref,
                }
            )

        record = {
            "time": time,
            "dt": dt,
            "tau": tau,
            "a_blow": a_blow,
            "s_min": s_min_effective,
            "kappa": kappa_eff,
            "Qpr_mean": qpr_mean,
            "beta_at_smin_config": beta_at_smin_config,
            "beta_at_smin_effective": beta_at_smin_effective,
            "beta_threshold": beta_threshold,
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
            "T_source": T_M_source,
            "T_M_used": T_use,
        }
        records.append(record)

        mass_initial = cfg.initial.mass_total
        mass_remaining = mass_initial - (M_loss_cum + M_sink_cum)
        mass_lost = M_loss_cum + M_sink_cum
        mass_diff = mass_initial - mass_remaining - mass_lost
        error_percent = 0.0
        if mass_initial != 0.0:
            # NOTE: `error_percent` is recorded for diagnostics and may be
            # enforced via the ``--enforce-mass-budget`` CLI flag.
            error_percent = abs(mass_diff / mass_initial) * 100.0
        budget_entry = {
            "time": time,
            "mass_initial": mass_initial,      # M_Mars
            "mass_remaining": mass_remaining,  # M_Mars
            "mass_lost": mass_lost,            # M_Mars
            "mass_diff": mass_diff,            # M_Mars
            "error_percent": error_percent,
            "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
        }
        mass_budget.append(budget_entry)

        if (
            mass_initial != 0.0
            and error_percent > MASS_BUDGET_TOLERANCE_PERCENT
            and mass_budget_violation is None
        ):
            mass_budget_violation = {
                "time": time,
                "error_percent": error_percent,
                "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
                "mass_initial": mass_initial,
                "mass_remaining": mass_remaining,
                "mass_lost": mass_lost,
                "mass_diff": mass_diff,
            }
            logger.error(
                "Mass budget tolerance exceeded at t=%.3e s (err=%.3f%% > %.3f%%)",
                time,
                error_percent,
                MASS_BUDGET_TOLERANCE_PERCENT,
            )
            if enforce_mass_budget:
                violation_triggered = True
                break

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
        "M_loss_from_sinks": M_sink_cum,
        "M_loss_from_sublimation": M_sublimation_cum,
        "case_status": case_status,
        "beta_threshold": beta_threshold,
        "beta_at_smin_config": beta_at_smin_config,
        "beta_at_smin_effective": beta_at_smin_effective,
        "beta_at_smin": beta_at_smin_config if beta_at_smin_config is not None else beta_at_smin_effective,
        "s_blow_m": a_blow,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean,
        "T_M_used": T_use,
        "T_M_used[K]": T_use,
        "T_M_source": T_M_source,
        "s_min_effective": s_min_effective,
        "s_min_effective[m]": s_min_effective,
        "s_min_config": s_min_config,
        "s_min_effective_gt_config": s_min_effective > s_min_config,
        "s_min_components": s_min_components,
        "enforce_mass_budget": enforce_mass_budget,
    }
    if mass_budget_violation is not None:
        summary["mass_budget_violation"] = mass_budget_violation
    writer.write_summary(summary, outdir / "summary.json")
    writer.write_mass_budget(mass_budget, outdir / "checks" / "mass_budget.csv")
    if debug_sinks_enabled and debug_records:
        debug_dir = outdir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        trace_path = debug_dir / "sinks_trace.jsonl"
        with trace_path.open("w", encoding="utf-8") as fh:
            for row in debug_records:
                fh.write(json.dumps(row) + "\n")
    e0_effective = cfg.dynamics.e0
    i0_effective = cfg.dynamics.i0

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
            "T_M_used": T_use,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean,
            "rng_seed": int(seed),
            "rng_seed_expr": seed_expr,
            "rng_seed_basis": seed_basis,
        },
        "init_ei": {
            "e_mode": cfg.dynamics.e_mode,
            "dr_min_m": cfg.dynamics.dr_min_m,
            "dr_max_m": cfg.dynamics.dr_max_m,
            "dr_dist": cfg.dynamics.dr_dist,
            "delta_r_sample_m": delta_r_sample,
            "e0_applied": e0_effective,
            "i_mode": cfg.dynamics.i_mode,
            "obs_tilt_deg": cfg.dynamics.obs_tilt_deg,
            "i_spread_deg": cfg.dynamics.i_spread_deg,
            "i0_applied_rad": i0_effective,
            "seed_used": int(seed),
            "e_formula_SI": "e = 1 - (R_MARS + Δr)/a; [Δr, a, R_MARS]: meters",
            "a_m_source": "geometry.r",
        },
        "git": _gather_git_info(),
        "time_grid": {
            "dt_s": float(cfg.numerics.dt_init),
            "t_end_s": float(t_end),
            "max_steps": MAX_STEPS,
            "scheme": "fixed-step implicit-Euler (S1)",
        },
    }
    run_config.update(
        {
            "sublimation_formula": "HK: Phi = alpha * P_vap(Td) * sqrt(mu/(2*pi*Rgas*Td)); Td=TM*sqrt(R/(2r))",
            "HK_mode": sub_params.mode,
            "HK_alpha_used": sub_params.alpha_evap,
            "HK_mu_used": sub_params.mu,
            "HK_A_used": sub_params.A,
            "HK_B_used": sub_params.B,
            "HK_Pgas_used": sub_params.P_gas,
            "HK_eta_instant_used": sub_params.eta_instant,
            "HK_AB_source": (
                "cfg.sinks.sub_params"
                if sub_params.A is not None and sub_params.B is not None
                else "not supplied"
            ),
            "HK_runtime_radius_m": r,
            "HK_runtime_t_orb_s": t_orb,
        }
    )
    writer.write_run_config(run_config, outdir / "run_config.json")

    if violation_triggered:
        raise MassBudgetViolationError(
            "Mass budget tolerance exceeded; see summary.json for details"
        )


def main(argv: Optional[List[str]] = None) -> None:
    """Command line entry point."""

    parser = argparse.ArgumentParser(description="Run a simple Mars disk model")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML configuration")
    parser.add_argument(
        "--enforce-mass-budget",
        action="store_true",
        help=(
            "Abort the run when the mass budget tolerance (%.3f%%) is exceeded"
            % MASS_BUDGET_TOLERANCE_PERCENT
        ),
    )
    parser.add_argument(
        "--sinks",
        choices=["none", "sublimation"],
        help="Override sinks.mode from the CLI (defaults to configuration file)",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.sinks is not None:
        cfg.sinks.mode = args.sinks
    run_zero_d(cfg, enforce_mass_budget=args.enforce_mass_budget)


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
    "MassBudgetViolationError",
]
