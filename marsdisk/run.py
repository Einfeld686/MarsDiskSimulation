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
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
import numpy as np

from . import grid
from .schema import Config
from .physics import (
    psd,
    surface,
    radiation,
    sinks,
    supply,
    initfields,
    shielding,
    sizes,
)
from .io import writer, tables
from .physics.sublimation import SublimationParams, p_sat, grain_temperature_graybody
from . import constants

logger = logging.getLogger(__name__)
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
MAX_STEPS = 5000
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0


def _parse_override_value(raw: str) -> Any:
    """Return a Python value parsed from a CLI override string."""

    text = raw.strip()
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None
    if lower in {"nan"}:
        return float("nan")
    if lower in {"inf", "+inf", "+infinity", "infinity"}:
        return float("inf")
    if lower in {"-inf", "-infinity"}:
        return float("-inf")
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def _apply_overrides_dict(payload: Dict[str, Any], overrides: Sequence[str]) -> Dict[str, Any]:
    """Apply dotted-path overrides to a configuration dictionary."""

    if not overrides:
        return payload
    for item in overrides:
        if not isinstance(item, str):  # pragma: no cover - defensive
            continue
        key, sep, value_str = item.partition("=")
        if not sep:
            raise ValueError(f"Invalid override '{item}'; expected path=value")
        path = key.strip()
        if not path:
            raise ValueError(f"Invalid override '{item}'; empty path")
        if path.startswith("physics."):
            path = path[len("physics.") :]
        parts = [segment for segment in path.split(".") if segment]
        if not parts:
            raise ValueError(f"Invalid override '{item}'; empty path")
        target: Any = payload
        for segment in parts[:-1]:
            if isinstance(target, dict):
                if segment not in target or target[segment] is None:
                    target[segment] = {}
                target = target[segment]
            else:
                raise TypeError(
                    f"Cannot traverse into non-mapping for override '{item}' at '{segment}'"
                )
        final_key = parts[-1]
        value = _parse_override_value(value_str)
        if isinstance(target, dict):
            target[final_key] = value
        else:
            raise TypeError(f"Cannot set override '{item}'; target is not a mapping")
    return payload


def _resolve_temperature(cfg: Config) -> tuple[float, str]:
    """Return the Mars-facing temperature used for radiation calculations."""

    if cfg.radiation is not None and cfg.radiation.TM_K is not None:
        return cfg.radiation.TM_K, "radiation.TM_K"
    return cfg.temps.T_M, "temps.T_M"


def _safe_float(value: Any) -> Optional[float]:
    """Return ``value`` cast to float when finite, otherwise ``None``."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


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


def _auto_chi_blow(beta: float, qpr: float) -> float:
    """Return an automatic chi_blow scaling based on β and ⟨Q_pr⟩."""

    if not math.isfinite(beta) or beta <= 0.0:
        beta = 0.5
    if not math.isfinite(qpr) or qpr <= 0.0:
        qpr = 1.0
    beta_ratio = beta / 0.5
    chi_beta = 1.0 / (1.0 + 0.5 * (beta_ratio - 1.0))
    chi_beta = max(0.1, chi_beta)
    chi_qpr = min(max(qpr, 0.5), 1.5)
    chi = chi_beta * chi_qpr
    return float(min(max(chi, 0.5), 2.0))


def _fast_blowout_correction_factor(ratio: float) -> float:
    """Return the effective loss fraction ``f_fast = 1 - exp(-Δt/t_blow)``.

    This quantity represents the integrated hazard of an exponential decay
    process over a finite step ``Δt``.  It is bounded within ``[0, 1]`` and
    captures the fraction of the surface reservoir removed by blow-out during
    the step when the rate is resolved exactly.
    """

    if ratio <= 0.0 or math.isinf(ratio):
        return 0.0 if ratio <= 0.0 else 1.0
    # numerically stable evaluation of 1 - exp(-ratio)
    value = -math.expm1(-ratio)
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _resolve_time_grid(numerics: Any, Omega: float, t_orb: float) -> tuple[float, float, float, int, Dict[str, Any]]:
    """Return (t_end, dt_nominal, dt_step, n_steps, info) for the integrator."""

    if numerics.t_end_orbits is not None:
        t_end = float(numerics.t_end_orbits) * t_orb
        t_end_basis = "t_end_orbits"
        t_end_input = float(numerics.t_end_orbits)
    elif numerics.t_end_years is not None:
        t_end = float(numerics.t_end_years) * SECONDS_PER_YEAR
        t_end_basis = "t_end_years"
        t_end_input = float(numerics.t_end_years)
    else:  # pragma: no cover - validated upstream, safeguard for runtime configs
        raise ValueError("numerics must provide t_end_years or t_end_orbits")

    if not math.isfinite(t_end) or t_end <= 0.0:
        raise ValueError("Resolved integration duration must be positive and finite")

    dt_input = numerics.dt_init
    dt_mode = "auto" if isinstance(dt_input, str) and dt_input.lower() == "auto" else "explicit"
    dt_sources: Dict[str, float] = {}
    t_blow_nominal = float("inf")
    if Omega > 0.0 and math.isfinite(Omega):
        t_blow_nominal = 1.0 / Omega

    if dt_mode == "auto":
        candidates: List[float] = []
        if math.isfinite(t_blow_nominal) and t_blow_nominal > 0.0:
            value = 0.05 * t_blow_nominal
            dt_sources["0.05*t_blow"] = value
            if value > 0.0 and math.isfinite(value):
                candidates.append(value)
        value = t_end / 200.0
        dt_sources["t_end/200"] = value
        if value > 0.0 and math.isfinite(value):
            candidates.append(value)
        if not candidates:
            dt_nominal = t_end
        else:
            dt_nominal = min(candidates)
        dt_nominal = max(min(dt_nominal, t_end), 1.0e-9)
    else:
        dt_nominal = float(dt_input)
        if not math.isfinite(dt_nominal) or dt_nominal <= 0.0:
            raise ValueError("dt_init must be positive and finite")
        dt_sources["explicit"] = dt_nominal

    n_steps = max(1, int(math.ceil(t_end / max(dt_nominal, 1.0e-9))))
    dt_step = t_end / n_steps

    info = {
        "t_end_basis": t_end_basis,
        "t_end_input": t_end_input,
        "t_end_seconds": t_end,
        "dt_mode": dt_mode,
        "dt_input": dt_input,
        "dt_sources": dt_sources,
        "dt_nominal": dt_nominal,
        "dt_step": dt_step,
        "t_blow_nominal": t_blow_nominal if math.isfinite(t_blow_nominal) else None,
        "n_steps": n_steps,
    }
    return t_end, dt_nominal, dt_step, n_steps, info


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


def load_config(path: Path, overrides: Optional[Sequence[str]] = None) -> Config:
    """Load a YAML configuration file into a :class:`Config` instance."""

    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    source_path = Path(path).resolve()
    with source_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if overrides:
        if not isinstance(data, dict):
            raise TypeError(
                "Configuration overrides require the YAML root to be a mapping"
            )
        data = _apply_overrides_dict(data, overrides)
    cfg = Config(**data)
    try:
        setattr(cfg, "_source_path", source_path)
    except Exception:
        pass
    return cfg


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

    config_source_path_raw = getattr(cfg, "_source_path", None)
    config_source_path: Optional[Path] = None
    if config_source_path_raw:
        try:
            config_source_path = Path(config_source_path_raw).resolve()
        except Exception:
            config_source_path = None

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

    r_source = "geometry.r"
    if cfg.geometry.r is not None:
        r = cfg.geometry.r
    elif getattr(cfg.geometry, "runtime_orbital_radius_rm", None) is not None:
        r = float(cfg.geometry.runtime_orbital_radius_rm) * constants.R_MARS
        r_source = "geometry.runtime_orbital_radius_rm"
        try:
            cfg.geometry.r = r
        except Exception:
            pass
    elif cfg.disk is not None:
        r = (
            0.5
            * (cfg.disk.geometry.r_in_RM + cfg.disk.geometry.r_out_RM)
            * constants.R_MARS
        )
        r_source = "disk.geometry"
    elif cfg.geometry.r_in is not None:
        r = cfg.geometry.r_in
        r_source = "geometry.r_in"
    else:
        raise ValueError("geometry.r must be provided for 0D runs")
    Omega = grid.omega_kepler(r)
    if Omega <= 0.0:
        raise ValueError("Computed Keplerian frequency must be positive")
    t_orb = 2.0 * math.pi / Omega
    r_RM = r / constants.R_MARS

    qpr_override = None
    qpr_table_path_resolved: Optional[Path] = None
    if cfg.radiation:
        qpr_table_path_resolved = cfg.radiation.qpr_table_resolved
        if qpr_table_path_resolved is not None:
            radiation.load_qpr_table(qpr_table_path_resolved)
        if cfg.radiation.Q_pr is not None:
            qpr_override = cfg.radiation.Q_pr
    active_qpr_table = tables.get_qpr_table_path()
    if qpr_table_path_resolved is None and active_qpr_table is not None:
        qpr_table_path_resolved = active_qpr_table
    if qpr_override is None and qpr_table_path_resolved is None:
        raise RuntimeError(
            "⟨Q_pr⟩ lookup table not initialised. Provide radiation.qpr_table_path "
            "or place a table under marsdisk/io/data."
        )
    T_use, T_M_source = _resolve_temperature(cfg)
    rho_used = cfg.material.rho

    phi_tau_fn = None
    phi_table_path_resolved: Optional[Path] = None
    shielding_mode_resolved = "psitau"
    if cfg.shielding:
        shielding_mode_resolved = cfg.shielding.mode_resolved
        phi_table_path_resolved = cfg.shielding.table_path_resolved
        if phi_table_path_resolved is not None:
            phi_tau_fn = shielding.load_phi_table(phi_table_path_resolved)
        if shielding_mode_resolved == "off":
            phi_tau_fn = None

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    setattr(sub_params, "runtime_orbital_radius_m", r)
    setattr(sub_params, "runtime_t_orb_s", t_orb)
    setattr(sub_params, "runtime_Omega", Omega)

    def _lookup_qpr(size: float) -> float:
        """Return ⟨Q_pr⟩ for the provided grain size using the active source."""

        size_eff = max(float(size), 1.0e-12)
        if qpr_override is not None:
            return float(qpr_override)
        return float(radiation.qpr_lookup(size_eff, T_use))

    def _resolve_blowout(
        size_floor: float,
        initial: Optional[float] = None,
    ) -> tuple[float, float]:
        """Return (⟨Q_pr⟩, s_blow) respecting the supplied minimum size."""

        if qpr_override is not None:
            qpr_val = float(qpr_override)
            s_blow_val = radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val)
            return qpr_val, float(max(size_floor, s_blow_val))

        s_eval = float(initial if initial is not None else size_floor)
        s_eval = float(max(size_floor, s_eval, 1.0e-12))
        for _ in range(6):
            qpr_val = float(radiation.qpr_lookup(s_eval, T_use))
            s_blow_val = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val))
            s_eval = float(max(size_floor, s_blow_val, 1.0e-12))
        qpr_final = float(radiation.qpr_lookup(s_eval, T_use))
        s_blow_final = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_final))
        return qpr_final, float(max(size_floor, s_blow_final))

    def _psd_mass_peak() -> float:
        """Return the size corresponding to the peak mass content."""

        try:
            sizes = np.asarray(psd_state.get("sizes"), dtype=float)
            number = np.asarray(psd_state.get("number"), dtype=float)
        except Exception:
            return float("nan")
        if sizes.size == 0 or number.size != sizes.size:
            return float("nan")
        mass_proxy = sizes**3 * number
        if mass_proxy.size == 0:
            return float("nan")
        idx = int(np.argmax(mass_proxy))
        if idx < 0 or idx >= sizes.size:
            return float("nan")
        return float(sizes[idx])

    blowout_enabled = bool(getattr(getattr(cfg, "blowout", None), "enabled", True))
    freeze_kappa = bool(getattr(cfg.radiation, "freeze_kappa", False)) if cfg.radiation else False
    freeze_sigma = bool(getattr(cfg.surface, "freeze_sigma", False))
    shielding_mode = shielding_mode_resolved
    tau_fixed_cfg: Optional[float] = None
    sigma_tau1_fixed_cfg: Optional[float] = None
    if cfg.shielding is not None:
        tau_fixed_cfg = getattr(cfg.shielding, "fixed_tau1_tau", None)
        sigma_tau1_fixed_cfg = getattr(cfg.shielding, "fixed_tau1_sigma", None)
    psd_floor_mode = getattr(getattr(cfg.psd, "floor", None), "mode", "fixed")

    s_min_config = cfg.sizes.s_min
    qpr_for_blow, a_blow = _resolve_blowout(s_min_config)
    if psd_floor_mode == "none":
        s_min_effective = float(s_min_config)
    else:
        s_min_effective = max(s_min_config, a_blow)
    s_min_floor_dynamic = float(s_min_effective)
    evolve_min_size_enabled = bool(getattr(cfg.sizes, "evolve_min_size", False))
    s_min_evolved_value = s_min_effective
    s_min_components = {
        "config": float(s_min_config),
        "blowout": float(a_blow),
        "effective": float(s_min_effective),
        "floor_mode": str(psd_floor_mode),
        "floor_dynamic": float(s_min_floor_dynamic),
    }
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
    kappa_surf_initial = float(kappa_surf)
    qpr_at_smin_config = _lookup_qpr(s_min_config)
    qpr_mean = _lookup_qpr(s_min_effective)
    beta_at_smin_config = radiation.beta(
        s_min_config, rho_used, T_use, Q_pr=qpr_at_smin_config
    )
    beta_at_smin_effective = radiation.beta(
        s_min_effective, rho_used, T_use, Q_pr=qpr_mean
    )
    beta_threshold = radiation.BLOWOUT_BETA_THRESHOLD
    case_status = "blowout" if beta_at_smin_config >= beta_threshold else "ok"
    if case_status != "blowout":
        logger.info(
            "Blow-out threshold not met at s_min_config=%.3e m (β=%.3f)",
            s_min_config,
            beta_at_smin_config,
        )
    if not blowout_enabled:
        case_status = "no_blowout"

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
    sigma_surf_reference = float(sigma_surf)
    tau_initial = float(kappa_surf_initial * sigma_surf_reference)
    tau_fixed_target = (
        float(tau_fixed_cfg) if tau_fixed_cfg is not None else tau_initial
    )
    sigma_tau1_fixed_target = (
        float(sigma_tau1_fixed_cfg)
        if sigma_tau1_fixed_cfg is not None
        else None
    )
    M_loss_cum = 0.0
    M_sink_cum = 0.0
    M_sublimation_cum = 0.0
    if cfg.disk is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        area = math.pi * (r_out_d**2 - r_in_d**2)
    else:
        area = math.pi * r**2
    chi_config_raw = getattr(cfg, "chi_blow", 1.0)
    chi_config = chi_config_raw
    chi_config_str = str(chi_config_raw)
    if isinstance(chi_config, str):
        chi_config_lower = chi_config.lower()
        if chi_config_lower == "auto":
            chi_blow_eff = _auto_chi_blow(beta_at_smin_effective, qpr_mean)
        else:
            raise ValueError("chi_blow string value must be 'auto'")
        chi_config_str = "auto"
    else:
        chi_blow_eff = float(chi_config)
        if chi_blow_eff <= 0.0:
            raise ValueError("chi_blow must be positive")
        chi_config_str = f"{chi_config_raw}"
    chi_blow_eff = float(min(max(chi_blow_eff, 0.5), 2.0))
    t_blow = chi_blow_eff / Omega

    sink_opts = sinks.SinkOptions(
        enable_sublimation=cfg.sinks.enable_sublimation,
        sub_params=sub_params,
        enable_gas_drag=cfg.sinks.enable_gas_drag,
        rho_g=cfg.sinks.rho_g,
    )

    supply_spec = cfg.supply

    t_end, dt_nominal, dt_initial_step, n_steps, time_grid_info = _resolve_time_grid(
        cfg.numerics,
        Omega,
        t_orb,
    )
    dt = dt_initial_step
    if n_steps > MAX_STEPS:
        n_steps = MAX_STEPS
        dt = t_end / n_steps
        time_grid_info["n_steps"] = n_steps
        time_grid_info["dt_step"] = dt
        time_grid_info["dt_capped_by_max_steps"] = True

    records: List[Dict[str, float]] = []
    psd_hist_records: List[Dict[str, float]] = []
    diagnostics: List[Dict[str, Any]] = []
    mass_budget: List[Dict[str, float]] = []
    mass_budget_violation: Optional[Dict[str, float]] = None
    violation_triggered = False
    debug_sinks_enabled = bool(getattr(cfg.io, "debug_sinks", False))
    correct_fast_blowout = bool(getattr(cfg.io, "correct_fast_blowout", False))
    substep_fast_enabled = bool(getattr(cfg.io, "substep_fast_blowout", False))
    substep_max_ratio = float(getattr(cfg.io, "substep_max_ratio", 1.0))
    if substep_max_ratio <= 0.0:
        raise ValueError("io.substep_max_ratio must be positive")
    debug_records: List[Dict[str, Any]] = []
    eval_per_step = bool(getattr(cfg.numerics, "eval_per_step", True))
    orbit_rollup_enabled = bool(getattr(cfg.numerics, "orbit_rollup", True))
    dt_over_t_blow_cfg = getattr(cfg.numerics, "dt_over_t_blow_max", None)
    dt_over_t_blow_max = (
        float(dt_over_t_blow_cfg)
        if dt_over_t_blow_cfg is not None
        else float("inf")
    )
    monitor_dt_ratio = math.isfinite(dt_over_t_blow_max) and dt_over_t_blow_max > 0.0

    orbit_time_accum = 0.0
    orbit_loss_blow = 0.0
    orbit_loss_sink = 0.0
    orbits_completed = 0
    orbit_rollup_rows: List[Dict[str, float]] = []

    Omega_step = Omega
    t_orb_step = t_orb
    a_blow_step = a_blow
    qpr_mean_step = qpr_mean
    qpr_for_blow_step = qpr_for_blow

    for step_no in range(n_steps):
        time_start = step_no * dt
        time = time_start

        if eval_per_step or step_no == 0:
            Omega_step = grid.omega_kepler(r)
            if Omega_step <= 0.0:
                raise ValueError("Computed Keplerian frequency must be positive")
            t_orb_step = 2.0 * math.pi / Omega_step
            setattr(sub_params, "runtime_t_orb_s", t_orb_step)
            setattr(sub_params, "runtime_Omega", Omega_step)

            qpr_for_blow, a_blow_step = _resolve_blowout(
                s_min_config,
                initial=float(psd_state.get("s_min", s_min_effective)),
            )
            qpr_for_blow_step = qpr_for_blow
            if psd_floor_mode == "none":
                s_min_blow = float(s_min_config)
            else:
                s_min_blow = max(s_min_config, a_blow_step)
            if psd_floor_mode == "none":
                s_min_effective = float(s_min_config)
            elif psd_floor_mode == "evolve_smin":
                s_min_effective = max(s_min_blow, s_min_floor_dynamic)
            else:
                s_min_effective = s_min_blow
                s_min_floor_dynamic = float(max(s_min_floor_dynamic, s_min_effective))
            psd_state["s_min"] = s_min_effective
            s_min_components["blowout"] = float(a_blow_step)
            s_min_components["effective"] = float(s_min_effective)
            s_min_components["floor_dynamic"] = float(s_min_floor_dynamic)
            qpr_mean_step = _lookup_qpr(s_min_effective)
            beta_at_smin_effective = radiation.beta(
                s_min_effective,
                rho_used,
                T_use,
                Q_pr=qpr_mean_step,
            )

        t_blow_step = chi_blow_eff / Omega_step if Omega_step > 0.0 else float("inf")

        T_grain = grain_temperature_graybody(T_use, r)
        ds_dt_val = 0.0
        sublimation_active = bool(
            getattr(cfg.sinks, "enable_sublimation", False)
            or cfg.sinks.mode == "sublimation"
        )
        if sublimation_active:
            try:
                ds_dt_val = sizes.eval_ds_dt_sublimation(T_grain, rho_used, sub_params)
            except ValueError:
                ds_dt_val = 0.0
        floor_for_step = s_min_effective
        if psd_floor_mode == "none":
            floor_for_step = float(s_min_config)
        elif psd_floor_mode == "evolve_smin":
            delta_floor = abs(ds_dt_val) * dt
            candidate = max(
                s_min_floor_dynamic,
                s_min_effective,
                s_min_floor_dynamic + delta_floor,
                s_min_config,
            )
            if psd_floor_mode != "none":
                candidate = max(candidate, a_blow_step)
            s_min_floor_dynamic = float(candidate)
            floor_for_step = max(s_min_effective, s_min_floor_dynamic)
            s_min_effective = floor_for_step
            s_min_components["floor_dynamic"] = float(s_min_floor_dynamic)
            s_min_components["effective"] = float(s_min_effective)
            psd_state["s_min"] = s_min_effective
        sigma_surf, delta_sigma_sub, erosion_diag = psd.apply_uniform_size_drift(
            psd_state,
            ds_dt=ds_dt_val,
            dt=dt,
            floor=floor_for_step,
            sigma_surf=sigma_surf,
        )
        kappa_surf = psd.compute_kappa(psd_state)
        if freeze_kappa:
            kappa_surf = kappa_surf_initial
        dSigma_dt_sublimation = delta_sigma_sub / dt if dt > 0.0 else 0.0
        mass_loss_sublimation_step = delta_sigma_sub * area / constants.M_MARS
        if mass_loss_sublimation_step < 0.0:
            mass_loss_sublimation_step = 0.0
        if mass_loss_sublimation_step > 0.0:
            M_sink_cum += mass_loss_sublimation_step
            M_sublimation_cum += mass_loss_sublimation_step

        if cfg.sinks.mode == "none":
            sink_result = sinks.SinkTimescaleResult(
                t_sink=None,
                components={"sublimation": None, "gas_drag": None},
                dominant_sink=None,
                T_eval=T_grain,
                s_ref=SINK_REF_SIZE,
            )
        else:
            sink_result = sinks.total_sink_timescale(
                T_use,
                rho_used,
                Omega_step,
                sink_opts,
                s_ref=SINK_REF_SIZE,
            )
        t_sink_total_value = sink_result.t_sink
        t_sink_step = t_sink_total_value
        t_sink_surface_only = t_sink_step
        if sink_result.components:
            non_sub_times: List[float] = []
            for name, value in sink_result.components.items():
                if name == "sublimation":
                    continue
                val = _safe_float(value)
                if val is not None and val > 0.0:
                    non_sub_times.append(val)
            if non_sub_times:
                t_sink_surface_only = float(min(non_sub_times))
            else:
                t_sink_surface_only = None
        t_sink_step = t_sink_surface_only

        if blowout_enabled and t_blow_step > 0.0:
            fast_blowout_ratio = dt / t_blow_step
            if monitor_dt_ratio and fast_blowout_ratio > dt_over_t_blow_max:
                logger.warning(
                    "dt/t_blow=%.2f exceeds numerics.dt_over_t_blow_max=%.2f",
                    fast_blowout_ratio,
                    dt_over_t_blow_max,
                )
            fast_blowout_factor_calc = (
                _fast_blowout_correction_factor(fast_blowout_ratio)
                if math.isfinite(fast_blowout_ratio)
                else 1.0
            )
            fast_blowout_flag = fast_blowout_ratio > FAST_BLOWOUT_RATIO_THRESHOLD
            fast_blowout_flag_strict = fast_blowout_ratio > FAST_BLOWOUT_RATIO_STRICT
            substep_active = bool(
                substep_fast_enabled and fast_blowout_ratio > substep_max_ratio
            )
            n_substeps = 1
            if substep_active:
                n_substeps = int(math.ceil(dt / (substep_max_ratio * t_blow_step)))
            dt_sub = dt / n_substeps
            ratio_sub = dt_sub / t_blow_step
            fast_blowout_factor_sub = (
                _fast_blowout_correction_factor(ratio_sub)
                if math.isfinite(ratio_sub)
                else 1.0
            )
            apply_correction = fast_blowout_flag and (correct_fast_blowout or substep_active)
        else:
            fast_blowout_ratio = 0.0
            fast_blowout_factor_calc = 0.0
            fast_blowout_flag = False
            fast_blowout_flag_strict = False
            substep_active = False
            n_substeps = 1
            dt_sub = dt
            ratio_sub = 0.0
            fast_blowout_factor_sub = 0.0
            apply_correction = False
        fast_blowout_applied = False

        kappa_eff = kappa_surf
        sigma_tau1_limit = None
        prod_rate_last = 0.0
        outflux_surface = 0.0
        sink_flux_surface = 0.0
        time_sub = time_start
        if freeze_sigma:
            sigma_surf = sigma_surf_reference
        sigma_before_step = sigma_surf
        total_prod_surface = 0.0
        total_sink_surface = 0.0
        fast_factor_numer = 0.0
        fast_factor_denom = 0.0

        tau_last = None
        phi_effective_last = None
        for _sub_idx in range(n_substeps):
            if freeze_sigma:
                sigma_surf = sigma_surf_reference
            sigma_for_tau = sigma_surf
            tau = kappa_surf * sigma_for_tau
            tau_eval = tau
            phi_value = None
            if shielding_mode == "off":
                kappa_eff = kappa_surf
                sigma_tau1_limit = float("inf")
            elif shielding_mode == "fixed_tau1":
                tau_target = tau_fixed_target
                if not math.isfinite(tau_target):
                    tau_target = tau_eval
                if sigma_tau1_fixed_target is not None:
                    sigma_tau1_limit = float(sigma_tau1_fixed_target)
                    if kappa_surf > 0.0 and not math.isfinite(tau_target):
                        tau_target = kappa_surf * sigma_tau1_limit
                if phi_tau_fn is not None:
                    kappa_eff = shielding.effective_kappa(kappa_surf, tau_target, phi_tau_fn)
                else:
                    kappa_eff = kappa_surf
                if sigma_tau1_fixed_target is None:
                    if kappa_eff <= 0.0:
                        sigma_tau1_limit = float("inf")
                    else:
                        sigma_tau1_limit = float(tau_target / max(kappa_eff, 1.0e-30))
                tau_eval = tau_target
            else:
                tau_eval = tau
                if phi_tau_fn is not None:
                    kappa_eff = shielding.effective_kappa(kappa_surf, tau_eval, phi_tau_fn)
                    sigma_tau1_limit = shielding.sigma_tau1(kappa_eff)
                else:
                    kappa_eff, sigma_tau1_limit = shielding.apply_shielding(
                        kappa_surf, tau_eval, 0.0, 0.0
                    )
            if kappa_surf > 0.0 and kappa_eff is not None:
                phi_value = kappa_eff / kappa_surf
            phi_effective_last = phi_value
            tau_last = tau_eval
            tau_for_coll = None if (not cfg.surface.use_tcoll or tau <= TAU_MIN) else tau
            prod_rate = supply.get_prod_area_rate(time_sub, r, supply_spec)
            prod_rate_last = prod_rate
            total_prod_surface += prod_rate * dt_sub
            res = surface.step_surface(
                sigma_surf,
                prod_rate,
                dt_sub,
                Omega_step,
                tau=tau_for_coll,
                t_sink=t_sink_step,
                sigma_tau1=sigma_tau1_limit,
                enable_blowout=blowout_enabled,
            )
            sigma_surf = res.sigma_surf
            outflux_surface = res.outflux
            sink_flux_surface = res.sink_flux
            if freeze_sigma:
                sigma_surf = sigma_surf_reference
            if apply_correction:
                outflux_surface *= fast_blowout_factor_sub
                fast_blowout_applied = True
            total_sink_surface += sink_flux_surface * dt_sub
            fast_factor_numer += fast_blowout_factor_sub * dt_sub
            fast_factor_denom += dt_sub
            time_sub += dt_sub

        time = time_sub
        if freeze_sigma:
            sigma_surf = sigma_surf_reference

        loss_total_surface = sigma_before_step + total_prod_surface - sigma_surf
        loss_total_surface = max(loss_total_surface, 0.0)
        sink_surface_total = max(total_sink_surface, 0.0)
        blow_surface_total = max(loss_total_surface - sink_surface_total, 0.0)
        if not blowout_enabled:
            blow_surface_total = 0.0

        sink_mass_total = sink_surface_total * area / constants.M_MARS
        blow_mass_total = blow_surface_total * area / constants.M_MARS
        M_loss_cum += blow_mass_total
        M_sink_cum += sink_mass_total
        if sink_result.sublimation_fraction > 0.0:
            M_sublimation_cum += sink_mass_total * sink_result.sublimation_fraction

        mass_loss_sinks_step_total = mass_loss_sublimation_step + sink_mass_total
        M_out_dot_avg = blow_mass_total / dt if dt > 0.0 else 0.0
        M_sink_dot_avg = mass_loss_sinks_step_total / dt if dt > 0.0 else 0.0
        dM_dt_surface_total_avg = M_out_dot_avg + M_sink_dot_avg
        fast_blowout_factor_avg = (
            fast_factor_numer / fast_factor_denom
            if fast_factor_denom > 0.0
            else fast_blowout_factor_calc
        )

        outflux_mass_rate_kg = outflux_surface * area
        sink_mass_rate_kg = sink_flux_surface * area
        sink_mass_rate_kg_total = sink_mass_rate_kg + (
            mass_loss_sublimation_step * constants.M_MARS / dt if dt > 0.0 else 0.0
        )
        M_out_dot = outflux_mass_rate_kg / constants.M_MARS
        M_sink_dot = sink_mass_rate_kg_total / constants.M_MARS
        dM_dt_surface_total = M_out_dot + M_sink_dot
        dSigma_dt_blowout = outflux_surface
        dSigma_dt_sinks = sink_flux_surface + dSigma_dt_sublimation
        dSigma_dt_total = dSigma_dt_blowout + dSigma_dt_sinks
        dt_over_t_blow = fast_blowout_ratio
        fast_blowout_factor_record = (
            fast_blowout_factor_calc if case_status == "blowout" else 0.0
        )
        fast_blowout_ratio_alias = (
            fast_blowout_ratio if case_status == "blowout" else 0.0
        )
        if not blowout_enabled:
            outflux_mass_rate_kg = 0.0
            M_out_dot = 0.0
            dSigma_dt_blowout = 0.0
            dt_over_t_blow = 0.0
            fast_blowout_factor_avg = 0.0
            fast_blowout_factor_record = 0.0
            fast_blowout_ratio_alias = 0.0

        orbit_time_accum += dt
        orbit_loss_blow += blow_mass_total
        orbit_loss_sink += mass_loss_sinks_step_total
        if orbit_rollup_enabled and t_orb_step > 0.0:
            while orbit_time_accum >= t_orb_step and orbit_time_accum > 0.0:
                fraction = t_orb_step / orbit_time_accum
                M_orbit_blow = orbit_loss_blow * fraction
                M_orbit_sink = orbit_loss_sink * fraction
                orbits_completed += 1
                mass_loss_frac = float("nan")
                if cfg.initial.mass_total > 0.0:
                    mass_loss_frac = (M_orbit_blow + M_orbit_sink) / cfg.initial.mass_total
                orbit_rollup_rows.append(
                    {
                        "orbit_index": orbits_completed,
                        "time_s": time,
                        "t_orb_s": t_orb_step,
                        "M_out_orbit": M_orbit_blow,
                        "M_sink_orbit": M_orbit_sink,
                        "M_loss_orbit": M_orbit_blow + M_orbit_sink,
                        "M_out_per_orbit": M_orbit_blow / t_orb_step,
                        "M_sink_per_orbit": M_orbit_sink / t_orb_step,
                        "M_loss_per_orbit": (M_orbit_blow + M_orbit_sink) / t_orb_step,
                        "mass_loss_frac_per_orbit": mass_loss_frac,
                        "M_out_cum": M_loss_cum,
                        "M_sink_cum": M_sink_cum,
                        "M_loss_cum": M_loss_cum + M_sink_cum,
                        "r_RM": r_RM,
                        "T_M": T_use,
                        "slope_dlnM_dlnr": None,
                    }
                )
                orbit_time_accum -= t_orb_step
                orbit_loss_blow = max(orbit_loss_blow - M_orbit_blow, 0.0)
                orbit_loss_sink = max(orbit_loss_sink - M_orbit_sink, 0.0)

        if evolve_min_size_enabled:
            s_min_evolved_value = psd.evolve_min_size(
                s_min_evolved_value,
                dt=dt,
                model=getattr(cfg.sizes, "dsdt_model", None),
                params=getattr(cfg.sizes, "dsdt_params", None),
                T=T_use,
                rho=rho_used,
                s_floor=s_min_effective,
                sublimation_params=sub_params,
            )

        if debug_sinks_enabled:
            debug_records.append(
                {
                    "step": int(step_no),
                    "time_s": time,
                    "dt_s": dt,
                    "dt_sub_s": dt_sub,
                    "T_M_K": T_use,
                    "T_d_graybody_K": sink_result.T_eval,
                    "T_source": T_M_source,
                    "r_m": r,
                    "r_RM": r_RM,
                    "t_sink_s": t_sink_step,
                    "dominant_sink": sink_result.dominant_sink,
                    "sublimation_timescale_s": sink_result.components.get("sublimation"),
                    "gas_drag_timescale_s": sink_result.components.get("gas_drag"),
                    "total_sink_dm_dt_kg_s": sink_mass_rate_kg_total,
                    "sublimation_dm_dt_kg_s": (
                        sink_mass_rate_kg_total
                        if sink_result.dominant_sink == "sublimation"
                        else 0.0
                    ),
                    "cum_sink_mass_kg": M_sink_cum * constants.M_MARS,
                    "cum_sublimation_mass_kg": M_sublimation_cum * constants.M_MARS,
                    "blowout_mass_rate_kg_s": outflux_mass_rate_kg,
                    "cum_blowout_mass_kg": M_loss_cum * constants.M_MARS,
                    "ds_dt_sublimation_m_s": ds_dt_val,
                    "sigma_loss_sublimation_kg_m2": delta_sigma_sub,
                    "M_loss_components_Mmars": {
                        "blowout": M_loss_cum,
                        "sinks": M_sink_cum,
                        "total": M_loss_cum + M_sink_cum,
                    },
                    "sinks_mode": cfg.sinks.mode,
                    "enable_sublimation": cfg.sinks.enable_sublimation,
                    "enable_gas_drag": cfg.sinks.enable_gas_drag,
                    "rho_particle_kg_m3": rho_used,
                    "rho_gas_kg_m3": cfg.sinks.rho_g,
                    "sink_components_timescale_s": sink_result.components,
                    "T_eval_sink_K": sink_result.T_eval,
                    "dt_over_t_blow": dt_over_t_blow,
                    "fast_blowout_corrected": fast_blowout_applied,
                    "fast_blowout_factor": fast_blowout_factor_record,
                    "fast_blowout_ratio": fast_blowout_ratio_alias,
                    "n_substeps": int(n_substeps),
                    "substep_active": substep_active,
                    "fast_blowout_factor_avg": fast_blowout_factor_avg,
                    "chi_blow_eff": chi_blow_eff,
                    "Q_pr_blow": qpr_for_blow_step,
                    "s_ref_m": sink_result.s_ref,
                }
            )

        tau = kappa_surf * sigma_surf
        record = {
            "time": time,
            "dt": dt,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "r_m": r,
            "r_RM": r_RM,
            "r_source": r_source,
            "dt_over_t_blow": dt_over_t_blow,
            "tau": tau,
            "a_blow_step": a_blow_step,
            "a_blow": a_blow_step,
            "s_min": s_min_effective,
            "kappa": kappa_eff,
            "Qpr_mean": qpr_mean_step,
            "beta_at_smin_config": beta_at_smin_config,
            "beta_at_smin_effective": beta_at_smin_effective,
            "beta_threshold": beta_threshold,
            "Sigma_surf": sigma_surf,
            "Sigma_tau1": sigma_tau1_limit,
            "outflux_surface": outflux_surface,
            "sink_flux_surface": sink_flux_surface,
            "t_blow": t_blow_step,
            "prod_subblow_area_rate": prod_rate_last,
            "M_out_dot": M_out_dot,
            "M_sink_dot": M_sink_dot,
            "dM_dt_surface_total": dM_dt_surface_total,
            "M_out_dot_avg": M_out_dot_avg,
            "M_sink_dot_avg": M_sink_dot_avg,
            "dM_dt_surface_total_avg": dM_dt_surface_total_avg,
            "fast_blowout_factor_avg": fast_blowout_factor_avg,
            "dSigma_dt_blowout": dSigma_dt_blowout,
            "dSigma_dt_sinks": dSigma_dt_sinks,
            "dSigma_dt_total": dSigma_dt_total,
            "dSigma_dt_sublimation": dSigma_dt_sublimation,
            "M_loss_cum": M_loss_cum + M_sink_cum,
            "mass_total_bins": cfg.initial.mass_total - (M_loss_cum + M_sink_cum),
            "mass_lost_by_blowout": M_loss_cum,
            "mass_lost_by_sinks": M_sink_cum,
            "mass_lost_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_sublimation_step": mass_loss_sublimation_step,
            "fast_blowout_factor": fast_blowout_factor_record,
            "fast_blowout_corrected": fast_blowout_applied,
            "fast_blowout_flag_gt3": fast_blowout_flag,
            "fast_blowout_flag_gt10": fast_blowout_flag_strict,
            "fast_blowout_ratio": fast_blowout_ratio_alias,
            "n_substeps": int(n_substeps),
            "chi_blow_eff": chi_blow_eff,
            "case_status": case_status,
            "s_blow_m": a_blow_step,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean_step,
            "Q_pr_blow": qpr_for_blow_step,
            "s_min_effective": s_min_effective,
            "s_min_config": s_min_config,
            "s_min_effective_gt_config": s_min_effective > s_min_config,
            "T_source": T_M_source,
            "T_M_used": T_use,
            "ds_dt_sublimation": ds_dt_val,
        }
        if evolve_min_size_enabled:
            record["s_min_evolved"] = s_min_evolved_value
        records.append(record)

        try:
            sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
            number_arr = np.asarray(psd_state.get("number"), dtype=float)
        except Exception:
            sizes_arr = np.empty(0, dtype=float)
            number_arr = np.empty(0, dtype=float)
        if sizes_arr.size and number_arr.size == sizes_arr.size:
            for idx, (size_val, number_val) in enumerate(zip(sizes_arr, number_arr)):
                psd_hist_records.append(
                    {
                        "time": time,
                        "bin_index": int(idx),
                        "s_bin_center": float(size_val),
                        "N_bin": float(number_val),
                        "Sigma_surf": sigma_surf,
                    }
                )

        F_abs_geom = constants.SIGMA_SB * (T_use**4) * (constants.R_MARS / r) ** 2
        phi_effective_diag = phi_effective_last
        if phi_effective_diag is None and kappa_surf > 0.0:
            phi_effective_diag = kappa_eff / kappa_surf

        sigma_diag = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_eff_diag = None
        if kappa_eff is not None and math.isfinite(kappa_eff):
            tau_eff_diag = kappa_eff * sigma_diag
        s_peak_value = _psd_mass_peak()
        F_abs_qpr = F_abs_geom * qpr_mean_step
        diag_entry = {
            "time": time,
            "dt": dt,
            "dt_over_t_blow": dt_over_t_blow,
            "r_m_used": r,
            "r_RM_used": r_RM,
            "F_abs_geom": F_abs_geom,
            "F_abs_geom_qpr": F_abs_qpr,
            "F_abs": F_abs_qpr,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "t_sink_total_s": _safe_float(t_sink_total_value),
            "t_sink_surface_s": float(t_sink_step) if t_sink_step is not None else None,
            "t_sink_sublimation_s": _safe_float(sink_result.components.get("sublimation")),
            "t_sink_gas_drag_s": _safe_float(sink_result.components.get("gas_drag")),
            "mass_loss_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_by_sinks": M_sink_cum,
            "mass_loss_sublimation_step": mass_loss_sublimation_step,
            "sigma_tau1": sigma_tau1_limit,
            "tau_vertical": tau_last,
            "kappa_eff": kappa_eff,
            "kappa_surf": kappa_surf,
            "phi_effective": phi_effective_diag,
            "psi_shield": phi_effective_diag,
            "sigma_surf": sigma_diag,
            "kappa_Planck": kappa_surf,
            "tau_eff": tau_eff_diag,
            "s_min": s_min_effective,
            "s_peak": s_peak_value,
            "area_m2": area,
            "prod_subblow_area_rate": prod_rate_last,
            "s_min_effective": s_min_effective,
            "qpr_mean": qpr_mean_step,
            "chi_blow_eff": chi_blow_eff,
            "ds_step_uniform": erosion_diag.get("ds_step"),
            "mass_ratio_uniform": erosion_diag.get("mass_ratio"),
            "M_out_cum": M_loss_cum,
            "M_sink_cum": M_sink_cum,
            "M_loss_cum": M_loss_cum + M_sink_cum,
        }
        diagnostics.append(diag_entry)

        mass_initial = cfg.initial.mass_total
        mass_remaining = mass_initial - (M_loss_cum + M_sink_cum)
        mass_lost = M_loss_cum + M_sink_cum
        mass_diff = mass_initial - mass_remaining - mass_lost
        error_percent = 0.0
        if mass_initial != 0.0:
            error_percent = abs(mass_diff / mass_initial) * 100.0
        budget_entry = {
            "time": time,
            "mass_initial": mass_initial,
            "mass_remaining": mass_remaining,
            "mass_lost": mass_lost,
            "mass_diff": mass_diff,
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
            "run: t=%e a_blow=%.3e kappa=%e t_blow=%e M_loss[M_Mars]=%e",
            time,
            a_blow_step,
            kappa_eff,
            t_blow_step,
            M_loss_cum + M_sink_cum,
        )

    qpr_mean = qpr_mean_step
    a_blow = a_blow_step
    Omega = Omega_step
    t_orb = t_orb_step
    qpr_blow_final = _lookup_qpr(max(s_min_config, a_blow))

    df = pd.DataFrame(records)
    outdir = Path(cfg.io.outdir)
    writer.write_parquet(df, outdir / "series" / "run.parquet")
    if psd_hist_records:
        psd_hist_df = pd.DataFrame(psd_hist_records)
        writer.write_parquet(psd_hist_df, outdir / "series" / "psd_hist.parquet")
    if diagnostics:
        diag_df = pd.DataFrame(diagnostics)
        writer.write_parquet(diag_df, outdir / "series" / "diagnostics.parquet")
    if orbit_rollup_enabled:
        writer.write_orbit_rollup(orbit_rollup_rows, outdir / "orbit_rollup.csv")
    mass_budget_max_error = max((entry["error_percent"] for entry in mass_budget), default=0.0)
    dt_over_t_blow_median = float("nan")
    if not df.empty and "dt_over_t_blow" in df.columns:
        dt_over_t_blow_median = float(df["dt_over_t_blow"].median())
    summary = {
        "M_loss": (M_loss_cum + M_sink_cum),
        "M_loss_from_sinks": M_sink_cum,
        "M_loss_from_sublimation": M_sublimation_cum,
        "M_out_cum": M_loss_cum,
        "M_sink_cum": M_sink_cum,
        "orbits_completed": orbits_completed,
        "case_status": case_status,
        "beta_threshold": beta_threshold,
        "beta_at_smin_config": beta_at_smin_config,
        "beta_at_smin_effective": beta_at_smin_effective,
        "beta_at_smin": beta_at_smin_config if beta_at_smin_config is not None else beta_at_smin_effective,
        "s_blow_m": a_blow,
        "chi_blow_input": chi_config_str,
        "chi_blow_eff": chi_blow_eff,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean,
        "Q_pr_blow": qpr_blow_final,
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "T_M_used": T_use,
        "T_M_used[K]": T_use,
        "T_M_source": T_M_source,
        "r_m_used": r,
        "r_RM_used": r_RM,
        "r_source": r_source,
        "phi_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
        "shielding_mode": shielding_mode,
        "mass_budget_max_error_percent": mass_budget_max_error,
        "dt_over_t_blow_median": dt_over_t_blow_median,
        "config_source_path": str(config_source_path) if config_source_path is not None else None,
        "s_min_effective": s_min_effective,
        "s_min_effective[m]": s_min_effective,
        "s_min_config": s_min_config,
        "s_min_effective_gt_config": s_min_effective > s_min_config,
        "s_min_components": s_min_components,
        "enforce_mass_budget": enforce_mass_budget,
        "time_grid": {
            "basis": time_grid_info.get("t_end_basis"),
            "t_end_input": time_grid_info.get("t_end_input"),
            "t_end_s": time_grid_info.get("t_end_seconds"),
            "dt_mode": time_grid_info.get("dt_mode"),
            "dt_input": time_grid_info.get("dt_input"),
            "dt_nominal_s": time_grid_info.get("dt_nominal"),
            "dt_step_s": dt,
            "n_steps": time_grid_info.get("n_steps"),
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
        },
    }
    if orbits_completed > 0:
        summary["M_out_mean_per_orbit"] = M_loss_cum / orbits_completed
        summary["M_sink_mean_per_orbit"] = M_sink_cum / orbits_completed
        summary["M_loss_mean_per_orbit"] = (M_loss_cum + M_sink_cum) / orbits_completed
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

    if (
        getattr(sub_params, "_psat_last_selection", None) is None
        and sub_params.mode.lower() in {"hkl", "hkl_timescale"}
    ):
        try:
            p_sat(max(T_use, 1.0), sub_params)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "Unable to resolve psat selection for provenance at T=%.1f K: %s",
                T_use,
                exc,
            )

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
            "T_M_source": T_M_source,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean,
            "Q_pr_blow": qpr_blow_final,
            "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
            "phi_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
            "r_m_used": r,
            "r_RM_used": r_RM,
            "r_source": r_source,
            "rng_seed": int(seed),
            "rng_seed_expr": seed_expr,
            "rng_seed_basis": seed_basis,
            "input_config_path": str(config_source_path) if config_source_path is not None else None,
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
            "dt_input": time_grid_info.get("dt_input"),
            "dt_mode": time_grid_info.get("dt_mode"),
            "dt_nominal_s": time_grid_info.get("dt_nominal"),
            "dt_step_s": time_grid_info.get("dt_step"),
            "t_end_s": time_grid_info.get("t_end_seconds"),
            "t_end_basis": time_grid_info.get("t_end_basis"),
            "t_end_input": time_grid_info.get("t_end_input"),
            "n_steps": time_grid_info.get("n_steps"),
            "max_steps": MAX_STEPS,
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "t_blow_nominal_s": time_grid_info.get("t_blow_nominal"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
            "scheme": "fixed-step implicit-Euler (S1)",
        },
        "physics_controls": {
            "blowout_enabled": blowout_enabled,
            "freeze_kappa": freeze_kappa,
            "freeze_sigma": freeze_sigma,
            "shielding_mode": shielding_mode,
            "shielding_tau_fixed": tau_fixed_cfg,
            "shielding_sigma_tau1_fixed": sigma_tau1_fixed_cfg,
            "shielding_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
            "psd_floor_mode": psd_floor_mode,
        },
    }
    qpr_source = "override" if qpr_override is not None else "table"
    run_config["radiation_provenance"] = {
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "Q_pr_override": qpr_override,
        "Q_pr_source": qpr_source,
        "Q_pr_blow": qpr_blow_final,
        "T_M_source": T_M_source,
    }
    psat_selection = getattr(sub_params, "_psat_last_selection", None) or {}
    psat_model_resolved = (
        psat_selection.get("psat_model_resolved")
        or sub_params.psat_model_resolved
        or sub_params.psat_model
    )
    psat_table_path = psat_selection.get("psat_table_path") or (
        str(sub_params.psat_table_path) if sub_params.psat_table_path else None
    )
    valid_config = (
        list(sub_params.valid_K) if sub_params.valid_K is not None else None
    )
    valid_active = psat_selection.get("valid_K_active")
    if isinstance(valid_active, tuple):
        valid_active = list(valid_active)
    psat_table_range = psat_selection.get("psat_table_range_K")
    if isinstance(psat_table_range, tuple):
        psat_table_range = list(psat_table_range)

    run_config["sublimation_provenance"] = {
        "sublimation_formula": "HKL",
        "mode": sub_params.mode,
        "psat_model": sub_params.psat_model,
        "psat_model_resolved": psat_model_resolved,
        "psat_selection_reason": psat_selection.get("selection_reason"),
        "alpha_evap": sub_params.alpha_evap,
        "mu": sub_params.mu,
        "A": (
            psat_selection["A_active"]
            if psat_selection.get("A_active") is not None
            else sub_params.A
        ),
        "B": (
            psat_selection["B_active"]
            if psat_selection.get("B_active") is not None
            else sub_params.B
        ),
        "P_gas": sub_params.P_gas,
        "valid_K_config": valid_config,
        "valid_K_active": valid_active,
        "psat_table_path": psat_table_path,
        "psat_table_range_K": psat_table_range,
        "psat_table_monotonic": psat_selection.get("monotonic"),
        "psat_table_buffer_K": sub_params.psat_table_buffer_K,
        "local_fit_window_K": sub_params.local_fit_window_K,
        "min_points_local_fit": sub_params.min_points_local_fit,
        "T_req": psat_selection.get("T_req"),
        "P_sat_Pa": psat_selection.get("P_sat_Pa"),
        "log10P": psat_selection.get("log10P"),
        "log10P_tabulated": psat_selection.get("log10P_tabulated"),
        "eta_instant": sub_params.eta_instant,
        "runtime_radius_m": r,
        "runtime_t_orb_s": t_orb,
    }
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
    parser.add_argument(
        "--override",
        action="append",
        nargs="+",
        metavar="PATH=VALUE",
        help=(
            "Apply configuration overrides using dotted paths; e.g. "
            "--override physics.blowout.enabled=false"
        ),
    )
    args = parser.parse_args(argv)

    override_list: List[str] = []
    if args.override:
        for group in args.override:
            override_list.extend(group)
    cfg = load_config(args.config, overrides=override_list)
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
