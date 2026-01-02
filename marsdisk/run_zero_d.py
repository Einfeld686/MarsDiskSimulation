"""CLI entry point and orchestration for the Mars disk zero-D simulation."""
from __future__ import annotations

import argparse
import atexit
import copy
import logging
import math
import random
import shutil
import subprocess
import textwrap
import hashlib
import json
import sys
import time
import warnings
import weakref
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, cast
import os

import pandas as pd
import numpy as np
from . import config_utils, grid
from .config_utils import (
    normalise_physics_mode as _normalise_physics_mode,
    merge_physics_section as _merge_physics_section,
    gather_git_info as _gather_git_info,
    configure_logging as _configure_logging,
)
from .orchestrator import (
    resolve_time_grid as _resolve_time_grid,
    resolve_seed as _resolve_seed,
    human_bytes as _human_bytes,
    memory_estimate as _memory_estimate,
)
from .schema import Config
from .runtime import (
    ColumnarBuffer,
    ProgressReporter,
    ZeroDHistory,
    ensure_finite_kappa as _ensure_finite_kappa,
    safe_float as _safe_float,
    float_or_nan as _float_or_nan,
    format_exception_short as _format_exception_short,
    log_stage,
)
from .runtime.helpers import (
    compute_phase_tau_fields,
    resolve_feedback_tau_field as _resolve_feedback_tau_field,
    resolve_los_factor as _resolve_los_factor,
    compute_gate_factor,
    fast_blowout_correction_factor,
    auto_chi_blow as _auto_chi_blow,
    series_stats as _series_stats,
)
from .runtime.legacy_steps import RunConfig, RunState, step, run_n_steps
from .physics import (
    psd,
    surface,
    radiation,
    sinks,
    supply,
    initfields,
    shielding,
    sizes,
    tempdriver,
    phase as phase_mod,
    smol,
    dynamics,
    collide,
    qstar,
    collisions_smol,
    eccentricity,
)
from . import physics_step
from .io import writer, tables, checkpoint as checkpoint_io, archive as archive_mod
from .io.diagnostics import write_zero_d_history as _write_zero_d_history, safe_float as _safe_float
from .io.streaming import (
    StreamingState,
    MEMORY_RUN_ROW_BYTES,
    MEMORY_PSD_ROW_BYTES,
    MEMORY_DIAG_ROW_BYTES,
)
from .output_schema import ZERO_D_DIAGNOSTIC_KEYS, ZERO_D_SERIES_KEYS
from .physics.sublimation import SublimationParams, p_sat, grain_temperature_graybody, sublimation_sink_from_dsdt
from . import constants
from .errors import ConfigurationError, PhysicsError, NumericalError, MarsDiskError

logger = logging.getLogger(__name__)
SECONDS_PER_YEAR = constants.SECONDS_PER_YEAR
MAX_STEPS = constants.MAX_STEPS
AUTO_MAX_MARGIN = 0.05
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0
EXTENDED_DIAGNOSTICS_VERSION = "extended-minimal-v1"

# Legacy aliases preserved for external callers/tests
_compute_gate_factor = compute_gate_factor
_fast_blowout_correction_factor = fast_blowout_correction_factor


@dataclass
class SmolSinkWorkspace:
    n_bins: int
    zeros_kernel: np.ndarray
    zeros_frag: np.ndarray
    zeros_source: np.ndarray
    ds_dt_buf: np.ndarray
    imex: smol.ImexWorkspace


@dataclass
class SupplyStepResult:
    supply_res: "supply.SupplyEvalResult"
    split_res: "supply.SupplySplitResult"
    prod_rate_raw: float
    supply_rate_nominal: float
    supply_rate_scaled: float


@dataclass
class SurfaceSupplyStepResult:
    shield_step: physics_step.ShieldingStepResult
    supply_step: SupplyStepResult
    enable_blowout_sub: bool
    t_sink_current: float | None


def _get_smol_sink_workspace(
    workspace: SmolSinkWorkspace | None,
    n_bins: int,
) -> SmolSinkWorkspace:
    if workspace is None or workspace.n_bins != n_bins:
        return SmolSinkWorkspace(
            n_bins=n_bins,
            zeros_kernel=np.zeros((n_bins, n_bins), dtype=float),
            zeros_frag=np.zeros((n_bins, n_bins, n_bins), dtype=float),
            zeros_source=np.zeros(n_bins, dtype=float),
            ds_dt_buf=np.zeros(n_bins, dtype=float),
            imex=smol.ImexWorkspace(
                gain=np.zeros(n_bins, dtype=float),
                loss=np.zeros(n_bins, dtype=float),
            ),
        )
    workspace.zeros_source.fill(0.0)
    return workspace


def _apply_supply_step(
    *,
    time_now: float,
    r: float,
    dt: float,
    supply_spec: "supply.Supply",
    area: float,
    supply_state: "supply.SupplyRuntimeState | None",
    tau_for_feedback: float | None,
    temperature_K: float,
    allow_supply: bool,
    sigma_surf: float,
    sigma_tau1: float | None,
    sigma_deep: float,
    t_mix: float | None,
    deep_enabled: bool,
    transport_mode: str,
    headroom_gate: str,
    headroom_policy: str,
    t_blow: float | None,
) -> SupplyStepResult:
    supply_res = supply.evaluate_supply(
        time_now,
        r,
        dt,
        supply_spec,
        area=area,
        state=supply_state,
        tau_for_feedback=tau_for_feedback,
        temperature_K=temperature_K,
        apply_reservoir=allow_supply,
    )
    prod_rate_raw = supply_res.rate if allow_supply else 0.0
    supply_rate_nominal = supply_res.mixed_rate if allow_supply else 0.0
    supply_rate_scaled = supply_res.rate if allow_supply else 0.0
    split_res = supply.split_supply_with_deep_buffer(
        prod_rate_raw,
        dt,
        sigma_surf,
        sigma_tau1,
        sigma_deep,
        t_mix=t_mix,
        deep_enabled=deep_enabled,
        transport_mode=transport_mode,
        headroom_gate=headroom_gate,
        headroom_policy=headroom_policy,
        t_blow=t_blow,
    )
    return SupplyStepResult(
        supply_res=supply_res,
        split_res=split_res,
        prod_rate_raw=prod_rate_raw,
        supply_rate_nominal=supply_rate_nominal,
        supply_rate_scaled=supply_rate_scaled,
    )


def _apply_shielding_and_supply(
    *,
    time_now: float,
    r: float,
    dt: float,
    sigma_surf: float,
    kappa_surf: float,
    collisions_active_step: bool,
    shielding_mode: str,
    phi_tau_fn: Callable[[float], float] | None,
    tau_fixed_target: float | None,
    sigma_tau1_fixed_target: float | None,
    los_factor: float,
    use_tcoll: bool,
    enable_blowout_step: bool,
    sink_timescale_active: bool,
    t_sink_step_effective: float | None,
    supply_spec: "supply.SupplySpec",
    area: float,
    supply_state: "supply.SupplyRuntimeState",
    temperature_K: float,
    allow_supply: bool,
    sigma_deep: float,
    t_mix: float | None,
    deep_enabled: bool,
    transport_mode: str,
    headroom_gate: str,
    headroom_policy: str,
    t_blow: float | None,
) -> SurfaceSupplyStepResult:
    shield_step = physics_step.compute_shielding_step(
        kappa_surf,
        sigma_surf,
        collisions_active=collisions_active_step,
        shielding_mode=shielding_mode,
        phi_tau_fn=phi_tau_fn,
        tau_fixed=tau_fixed_target,
        sigma_tau1_fixed=sigma_tau1_fixed_target,
        los_factor=los_factor,
        use_tcoll=use_tcoll,
    )
    enable_blowout_sub = enable_blowout_step and collisions_active_step
    t_sink_current = t_sink_step_effective if sink_timescale_active else None
    supply_step = _apply_supply_step(
        time_now=time_now,
        r=r,
        dt=dt,
        supply_spec=supply_spec,
        area=area,
        supply_state=supply_state,
        tau_for_feedback=shield_step.tau_los,
        temperature_K=temperature_K,
        allow_supply=allow_supply,
        sigma_surf=sigma_surf,
        sigma_tau1=None,
        sigma_deep=sigma_deep,
        t_mix=t_mix,
        deep_enabled=deep_enabled,
        transport_mode=transport_mode,
        headroom_gate=headroom_gate,
        headroom_policy=headroom_policy,
        t_blow=t_blow,
    )
    return SurfaceSupplyStepResult(
        shield_step=shield_step,
        supply_step=supply_step,
        enable_blowout_sub=enable_blowout_sub,
        t_sink_current=t_sink_current,
    )


def _apply_blowout_correction(
    outflux_surface: float,
    *,
    factor: float,
    apply: bool,
) -> tuple[float, bool]:
    if apply:
        return outflux_surface * factor, True
    return outflux_surface, False


def _apply_blowout_gate(
    blow_surface_total: float,
    outflux_surface: float,
    *,
    enable_blowout: bool,
    gate_enabled: bool,
    gate_factor: float,
) -> tuple[float, float]:
    if enable_blowout and gate_enabled:
        return blow_surface_total * gate_factor, outflux_surface * gate_factor
    return blow_surface_total, outflux_surface


def _resolve_t_coll_step(
    *,
    collision_solver_mode: str,
    collisions_active: bool,
    tau_los_last: float | None,
    los_factor: float,
    Omega: float,
    t_coll_kernel_last: float | None,
) -> float | None:
    if not collisions_active or tau_los_last is None or tau_los_last <= TAU_MIN or Omega <= 0.0:
        return None
    if collision_solver_mode == "smol":
        t_coll_candidate = t_coll_kernel_last
    else:
        try:
            tau_vert = float(tau_los_last) / max(los_factor, 1.0)
            if tau_vert > TAU_MIN:
                t_coll_candidate = surface.wyatt_tcoll_S1(tau_vert, Omega)
            else:
                t_coll_candidate = None
        except Exception:
            t_coll_candidate = None
    if t_coll_candidate is not None and math.isfinite(t_coll_candidate) and t_coll_candidate > 0.0:
        return float(t_coll_candidate)
    return None


def _reset_collision_runtime_state() -> None:
    """Clear per-run collision caches and warning state."""

    collisions_smol.reset_collision_caches()
    collisions_smol._F_KE_MISMATCH_WARNED = False


def _get_max_steps() -> int:
    """Return MAX_STEPS, honoring overrides applied to the marsdisk.run shim."""

    # Prefer an override applied to the shim module (used by tests via monkeypatch).
    run_module = sys.modules.get("marsdisk.run")
    candidate = getattr(run_module, "MAX_STEPS", None) if run_module is not None else None
    if candidate is None:
        candidate = globals().get("MAX_STEPS", MAX_STEPS)
    try:
        return int(candidate)
    except Exception:
        return MAX_STEPS


def _log_stage(label: str, *, extra: Mapping[str, Any] | None = None) -> None:
    """Emit coarse progress markers for debugging long runs."""

    log_stage(logger, label, extra=extra)


def _model_fields_set(model: Any) -> set[str]:
    """Return explicitly-set fields for a Pydantic model (v1/v2 compatible)."""

    if model is None:
        return set()
    fields_set = getattr(model, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(model, "__fields_set__", set())
    return set(fields_set or set())


def _surface_energy_floor(
    gamma_J_m2: float,
    eta: float,
    alpha: float,
    rho: float,
    v_rel: float,
    s0: float,
    s_max: float,
) -> float:
    """Return surface-energy-limited minimum size (Krijt & Kama general form).

    Guards on invalid inputs and caps at s_max.
    """

    if (
        alpha <= 3.0
        or alpha >= 4.0
        or gamma_J_m2 <= 0.0
        or eta <= 0.0
        or rho <= 0.0
        or v_rel <= 0.0
        or s0 <= 0.0
        or s_max <= 0.0
    ):
        return 0.0
    factor = (1.0 / s0) + (eta * rho * v_rel * v_rel) / (24.0 * gamma_J_m2)
    prefactor = (alpha - 3.0) / (4.0 - alpha)
    rhs = prefactor * factor * (s_max ** (4.0 - alpha))
    if rhs <= 0.0 or not math.isfinite(rhs):
        return 0.0
    exponent = 1.0 / (3.0 - alpha)
    s_floor = rhs ** exponent
    if not math.isfinite(s_floor):
        return 0.0
    if s_floor > s_max:
        return float(s_max)
    return float(max(s_floor, 0.0))


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
        data = config_utils.apply_overrides_dict(data, overrides)
    if isinstance(data, dict):
        data = _merge_physics_section(data)
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


class MassBudgetViolationError(NumericalError):
    """Raised when the mass budget tolerance is exceeded."""




def run_zero_d(
    cfg: Config,
    *,
    enforce_mass_budget: bool = False,
    physics_mode_override: Optional[str] = None,
    physics_mode_source_override: Optional[str] = None,
) -> None:
    """Execute the full-feature zero-dimensional simulation.

    This is the production driver: it resolves configuration, builds PSD
    floors, advances the coupled physics, and emits the on-disk artifacts.
    The lightweight :func:`step` / :func:`run_n_steps` helpers remain available
    for tutorial or unit-test scenarios.

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
    outdir = Path(cfg.io.outdir)

    scope_cfg = getattr(cfg, "scope", None)
    process_cfg = getattr(cfg, "process", None)
    physics_mode_cfg = getattr(cfg, "physics_mode", None)
    primary_process_cfg = _normalise_physics_mode(physics_mode_cfg)
    physics_mode = _normalise_physics_mode(physics_mode_override or physics_mode_cfg)
    physics_mode_source = "cli" if physics_mode_override is not None else "config"
    if physics_mode_source_override:
        physics_mode_source = physics_mode_source_override

    run_config_path = outdir / "run_config.json"
    energy_series_path = outdir / "series" / "energy.csv"
    energy_budget_path = outdir / "checks" / "energy_budget.csv"
    energy_parquet_path = outdir / "series" / "energy.parquet"

    def _write_run_config_snapshot(status: str, extra: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {
            "status": status,
            "physics_mode": physics_mode,
            "physics_mode_source": physics_mode_source,
            "config_source_path": str(config_source_path) if config_source_path else None,
            "outdir": str(outdir),
            "config": cfg.model_dump(mode="json"),
        }
        auto_tune_info = getattr(cfg, "_auto_tune_info", None)
        if auto_tune_info is not None:
            payload["auto_tune"] = auto_tune_info
        supply_feedback_snapshot = getattr(getattr(cfg, "supply", None), "feedback", None)
        if supply_feedback_snapshot is not None:
            try:
                payload["supply_feedback"] = supply_feedback_snapshot.model_dump()
            except Exception:
                payload["supply_feedback"] = str(supply_feedback_snapshot)
        if extra:
            payload.update(extra)
        try:
            writer.write_run_config(payload, run_config_path)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to write %s run_config snapshot to %s: %s", status, run_config_path, exc)

    _write_run_config_snapshot("pre_run")
    fields_set = getattr(cfg, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(cfg, "__fields_set__", set())
    primary_field_explicit = "physics_mode" in fields_set
    scope_region = getattr(scope_cfg, "region", "inner") if scope_cfg else "inner"
    analysis_window_years = float(getattr(scope_cfg, "analysis_years", 2.0)) if scope_cfg else 2.0
    if scope_region != "inner":
        raise ConfigurationError("scope.region must be 'inner' during the inner-disk campaign")
    primary_scenario = physics_mode if physics_mode in {"sublimation_only", "collisions_only"} else "combined"
    primary_process = primary_scenario
    state_tagging_enabled = bool(
        getattr(getattr(process_cfg, "state_tagging", None), "enabled", False)
    )
    state_phase_tag = "solid" if state_tagging_enabled else None
    inner_scope_flag = scope_region == "inner"
    radiation_field = "mars"
    radiation_cfg = getattr(cfg, "radiation", None)
    solar_rp_requested = False
    mars_rp_enabled_cfg = True
    if radiation_cfg is not None:
        source_raw = getattr(radiation_cfg, "source", "mars")
        radiation_field = str(source_raw).lower()
        mars_rp_enabled_cfg = bool(getattr(radiation_cfg, "use_mars_rp", True))
        solar_rp_requested = bool(getattr(radiation_cfg, "use_solar_rp", False))
        if radiation_field == "off":
            mars_rp_enabled_cfg = False
    if not mars_rp_enabled_cfg:
        radiation_field = "off"
    if solar_rp_requested:
        logger.info("radiation: solar radiation toggle requested but disabled (gas-poor scope)")
    if cfg.numerics.t_end_years is None and cfg.numerics.t_end_orbits is None:
        cfg.numerics.t_end_years = analysis_window_years
    logger.debug(
        "[stage] config_resolved scope=%s physics_mode=%s",
        scope_region,
        physics_mode,
    )
    logger.info(
        "scope=%s, window=%.3f yr, radiation=%s, physics_mode=%s, scenario=%s%s",
        scope_region,
        analysis_window_years,
        radiation_field,
        physics_mode,
        primary_scenario,
        " (state_tag=solid)" if state_tagging_enabled else "",
    )
    qstar_cfg = getattr(cfg, "qstar", None)
    qstar_coeff_units_used = getattr(qstar_cfg, "coeff_units", "ba99_cgs") if qstar_cfg is not None else "ba99_cgs"
    qstar_coeff_units_source = "default"
    if qstar_cfg is not None:
        qstar_fields_set = getattr(qstar_cfg, "model_fields_set", None)
        if qstar_fields_set is None:
            qstar_fields_set = getattr(qstar_cfg, "__fields_set__", set())
    else:
        qstar_fields_set = set()
    if qstar_cfg is not None and "coeff_units" in qstar_fields_set:
        qstar_coeff_units_source = "config"
    qstar_mu_gravity_used = getattr(qstar_cfg, "mu_grav", qstar.get_gravity_velocity_mu()) if qstar_cfg is not None else qstar.get_gravity_velocity_mu()
    qstar_mu_gravity_source = "default"
    if qstar_cfg is not None and "mu_grav" in qstar_fields_set:
        qstar_mu_gravity_source = "config"
    qstar.reset_velocity_clamp_stats()
    qstar.set_coeff_unit_system(qstar_coeff_units_used)
    qstar.set_gravity_velocity_mu(qstar_mu_gravity_used)
    qstar_coeff_override = bool(getattr(qstar_cfg, "override_coeffs", False)) if qstar_cfg is not None else False
    qstar_coeff_scale = float(getattr(qstar_cfg, "coeff_scale", 1.0)) if qstar_cfg is not None else 1.0
    qstar_coeff_table_source = "default"
    qstar_coeff_scale_applied = False
    if qstar_cfg is not None and qstar_coeff_override:
        coeff_table_cfg = getattr(qstar_cfg, "coeff_table", None)
        if coeff_table_cfg:
            qstar.set_coefficient_table(coeff_table_cfg)
            qstar_coeff_table_source = "config_table"
        else:
            v_refs = [float(v) for v in getattr(qstar_cfg, "v_ref_kms", []) or []]
            if not v_refs:
                raise ConfigurationError(
                    "qstar.override_coeffs=true requires v_ref_kms or coeff_table"
                )
            qstar_coeff_table = {
                float(v_ref): (
                    float(qstar_cfg.Qs) * qstar_coeff_scale,
                    float(qstar_cfg.a_s),
                    float(qstar_cfg.B) * qstar_coeff_scale,
                    float(qstar_cfg.b_g),
                )
                for v_ref in v_refs
            }
            qstar.set_coefficient_table(qstar_coeff_table)
            qstar_coeff_table_source = "config_broadcast"
            qstar_coeff_scale_applied = True
    else:
        qstar.reset_coefficient_table()
    if qstar_coeff_units_source == "default":
        logger.info(
            "qstar.coeff_units not specified; defaulting to '%s' (BA99 cgs evaluation with cm,g/cm^3,erg/g).",
            qstar_coeff_units_used,
        )
    if radiation_cfg is not None:
        qpr_cache_cfg = getattr(radiation_cfg, "qpr_cache", None)
        round_tol_cfg = getattr(qpr_cache_cfg, "round_tol", None) if qpr_cache_cfg is not None else None
        radiation.configure_qpr_cache(
            enabled=bool(getattr(qpr_cache_cfg, "enabled", True)) if qpr_cache_cfg is not None else True,
            maxsize=int(getattr(qpr_cache_cfg, "maxsize", 256)) if qpr_cache_cfg is not None else 256,
            round_tol=float(round_tol_cfg) if round_tol_cfg is not None and float(round_tol_cfg) > 0.0 else None,
        )
        radiation.configure_qpr_fallback(
            strict=bool(getattr(radiation_cfg, "qpr_strict", False)),
        )
    else:
        radiation.configure_qpr_cache(enabled=False, maxsize=0)
        radiation.configure_qpr_fallback(strict=False)
    enforce_collisions_only = primary_scenario == "collisions_only"
    enforce_sublimation_only = primary_scenario == "sublimation_only"
    collisions_active = not enforce_sublimation_only
    diagnostics_cfg = getattr(cfg, "diagnostics", None)
    extended_diag_cfg = getattr(diagnostics_cfg, "extended_diagnostics", None)
    extended_diag_enabled = bool(getattr(extended_diag_cfg, "enable", False))
    extended_diag_version = getattr(
        extended_diag_cfg, "schema_version", EXTENDED_DIAGNOSTICS_VERSION
    )

    seed, seed_expr, seed_basis = _resolve_seed(cfg)
    random.seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    r, r_RM, r_source = config_utils.resolve_reference_radius(cfg)
    Omega = grid.omega_kepler(r)
    if Omega <= 0.0:
        raise PhysicsError("Computed Keplerian frequency must be positive")
    t_orb = 2.0 * math.pi / Omega

    e_profile_value, e_profile_meta = eccentricity.evaluate_e_profile(
        getattr(cfg.dynamics, "e_profile", None),
        r_m=r,
        r_RM=r_RM,
        log=logger,
    )
    if e_profile_value is not None:
        e0_effective = float(e_profile_value)
        cfg.dynamics.e0 = e0_effective
    else:
        e0_effective = cfg.dynamics.e0
    i0_effective = cfg.dynamics.i0
    delta_r_sample = None

    if cfg.dynamics.e_mode == "mars_clearance":
        a_m = r
        dr_min = cfg.dynamics.dr_min_m
        dr_max = cfg.dynamics.dr_max_m
        if dr_min is not None and dr_max is not None:
            if dr_min > dr_max:
                raise ConfigurationError(
                    "dynamics.dr_min_m must be smaller than dynamics.dr_max_m in meters"
                )
            if cfg.dynamics.dr_dist == "uniform":
                delta_r_sample = float(rng.uniform(dr_min, dr_max))
            else:
                if dr_min <= 0.0 or dr_max <= 0.0:
                    raise ConfigurationError(
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
            raise ConfigurationError(
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
    r_RM = r / constants.R_MARS

    qpr_override = None
    qpr_table_path_resolved: Optional[Path] = None
    qpr_strict = False
    if cfg.radiation:
        qpr_table_path_resolved = cfg.radiation.qpr_table_resolved
        if qpr_table_path_resolved is not None:
            radiation.load_qpr_table(qpr_table_path_resolved)
        if cfg.radiation.Q_pr is not None:
            qpr_override = cfg.radiation.Q_pr
        qpr_strict = bool(getattr(cfg.radiation, "qpr_strict", False))
    active_qpr_table = tables.get_qpr_table_path()
    if qpr_table_path_resolved is None and active_qpr_table is not None:
        qpr_table_path_resolved = active_qpr_table
    if qpr_override is None and qpr_table_path_resolved is None:
        if qpr_strict:
            raise RuntimeError(
                "⟨Q_pr⟩ lookup table not initialised and radiation.qpr_strict=true. "
                "Provide radiation.qpr_table_path or radiation.Q_pr."
            )
        logger.warning("⟨Q_pr⟩ lookup table not initialised; using DEFAULT_Q_PR=1.")
    numerics_cfg = getattr(cfg, "numerics", None)
    t_end_years_cfg = 0.0
    if numerics_cfg is not None:
        if getattr(numerics_cfg, "t_end_years", None) is not None:
            t_end_years_cfg = float(getattr(numerics_cfg, "t_end_years", 0.0) or 0.0)
        elif getattr(numerics_cfg, "t_end_orbits", None) is not None:
            t_end_years_cfg = (
                float(getattr(numerics_cfg, "t_end_orbits", 0.0) or 0.0) * t_orb / SECONDS_PER_YEAR
            )
        temp_stop_target = getattr(numerics_cfg, "t_end_until_temperature_K", None)
        temp_pad_years = float(getattr(numerics_cfg, "t_end_temperature_margin_years", 0.0) or 0.0)
        if temp_stop_target is not None:
            span_years = tempdriver.estimate_autogen_horizon_years(
                cfg.radiation,
                T_stop_K=float(temp_stop_target),
                margin_years=temp_pad_years,
                fallback_years=t_end_years_cfg,
            )
            if span_years is not None:
                t_end_years_cfg = max(t_end_years_cfg, float(span_years))
    temp_autogen_info = tempdriver.autogenerate_temperature_table_if_needed(
        cfg.radiation,
        t_end_years=t_end_years_cfg,
        t_orb=t_orb,
    )
    temp_runtime = tempdriver.resolve_temperature_driver(
        cfg.radiation, t_orb=t_orb, prefer_driver=bool(temp_autogen_info)
    )
    T_use = temp_runtime.initial_value
    T_M_source = temp_runtime.source
    logger.debug(
        "[stage] temperature_driver_ready source=%s T_init=%.2f",
        T_M_source,
        T_use,
    )
    logger.info(
        "Mars temperature driver resolved: source=%s mode=%s enabled=%s T_init=%.2f K",
        temp_runtime.source,
        temp_runtime.mode,
        temp_runtime.enabled,
        T_use,
    )
    rho_used = cfg.material.rho

    phi_tau_fn = None
    phi_table_path_resolved: Optional[Path] = None
    shielding_mode_resolved = "psitau"
    auto_max_margin = AUTO_MAX_MARGIN
    if cfg.shielding:
        shielding_mode_resolved = cfg.shielding.mode_resolved
        phi_table_path_resolved = cfg.shielding.table_path_resolved
        if phi_table_path_resolved is not None:
            phi_tau_fn = shielding.load_phi_table(phi_table_path_resolved)
        if shielding_mode_resolved == "off":
            phi_tau_fn = None
        try:
            margin_cfg = float(getattr(cfg.shielding, "auto_max_margin", AUTO_MAX_MARGIN))
            if margin_cfg < 0.0:
                raise ConfigurationError("shielding.auto_max_margin must be non-negative")
            auto_max_margin = margin_cfg
        except Exception:
            auto_max_margin = AUTO_MAX_MARGIN
    los_geom_cfg = getattr(cfg.shielding, "los_geometry", None) if cfg.shielding else None
    los_factor = _resolve_los_factor(los_geom_cfg)

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    setattr(sub_params, "runtime_orbital_radius_m", r)
    setattr(sub_params, "runtime_t_orb_s", t_orb)
    setattr(sub_params, "runtime_Omega", Omega)
    gas_pressure_pa = float(getattr(sub_params, "P_gas", 0.0) or 0.0)

    phase_cfg = getattr(cfg, "phase", None)
    phase_controller = phase_mod.PhaseEvaluator.from_config(phase_cfg, logger=logger)
    phase_temperature_input_mode = "mars_surface"
    phase_q_abs_mean = 0.4
    phase_tau_field = "los"
    phase_temperature_formula = "T_p = T_M * q_abs_mean^0.25 * sqrt(R_M/(2 r))"
    if phase_cfg is not None:
        phase_temperature_input_mode = str(getattr(phase_cfg, "temperature_input", phase_temperature_input_mode))
        phase_q_abs_mean = float(getattr(phase_cfg, "q_abs_mean", phase_q_abs_mean))
        phase_tau_field = str(getattr(phase_cfg, "tau_field", phase_tau_field))
    if phase_temperature_input_mode:
        phase_temperature_input_mode = phase_temperature_input_mode.strip().lower()
    if phase_temperature_input_mode not in {"mars_surface", "particle"}:
        logger.warning(
            "Unknown phase.temperature_input=%s; defaulting to 'mars_surface'", phase_temperature_input_mode
        )
        phase_temperature_input_mode = "mars_surface"
    phase_tau_field = phase_tau_field.strip().lower()
    if phase_tau_field != "los":
        logger.warning("phase.tau_field=%s ignored; LOS-only evaluation is enforced", phase_tau_field)
        phase_tau_field = "los"
    if not math.isfinite(phase_q_abs_mean) or phase_q_abs_mean <= 0.0:
        raise PhysicsError("phase.q_abs_mean must be positive and finite")
    allow_liquid_hkl = bool(getattr(phase_cfg, "allow_liquid_hkl", True)) if phase_cfg else True
    hydro_cfg = getattr(cfg.sinks, "hydro_escape", None)
    tau_gate_cfg = getattr(cfg.radiation, "tau_gate", None) if cfg.radiation else None
    tau_gate_enabled = bool(getattr(tau_gate_cfg, "enable", False)) if tau_gate_cfg else False
    tau_gate_threshold = (
        float(getattr(tau_gate_cfg, "tau_max", 1.0)) if tau_gate_enabled else float("inf")
    )

    qpr_cache_T = None
    qpr_cache_sizes_id: int | None = None
    qpr_cache_sizes: np.ndarray | None = None
    qpr_cache_values: np.ndarray | None = None

    def _refresh_qpr_cache() -> None:
        """Precompute ⟨Q_pr⟩ for the current PSD sizes when T changes."""

        nonlocal qpr_cache_T, qpr_cache_sizes_id, qpr_cache_sizes, qpr_cache_values
        if qpr_override is not None:
            qpr_cache_T = T_use
            qpr_cache_sizes_id = id(psd_state.get("sizes"))
            qpr_cache_sizes = None
            qpr_cache_values = None
            return

        sizes_ref = psd_state.get("sizes")
        if sizes_ref is None:
            qpr_cache_sizes = None
            qpr_cache_values = None
            return
        sizes_arr = np.asarray(sizes_ref, dtype=float)
        if sizes_arr.size == 0:
            qpr_cache_sizes = None
            qpr_cache_values = None
            return
        if (qpr_cache_T != T_use) or (qpr_cache_sizes_id != id(sizes_ref)):
            qpr_cache_T = T_use
            qpr_cache_sizes_id = id(sizes_ref)
            qpr_cache_sizes = sizes_arr
            qpr_cache_values = radiation.qpr_lookup_array(sizes_arr, T_use)

    def _lookup_qpr(size: float) -> float:
        """Return ⟨Q_pr⟩ for the provided grain size using the active source."""

        size_eff = max(float(size), 1.0e-12)
        if qpr_override is not None:
            return float(qpr_override)
        _refresh_qpr_cache()
        if qpr_cache_sizes is not None and qpr_cache_values is not None and qpr_cache_T == T_use:
            # Exact match against cached PSD sizes.
            matches = np.nonzero(np.isclose(qpr_cache_sizes, size_eff, rtol=0.0, atol=1.0e-30))[0]
            if matches.size:
                return float(qpr_cache_values[int(matches[0])])
        return float(radiation.qpr_lookup(size_eff, T_use))

    def _lookup_qpr_cached(size: float, T_M: float) -> float:
        """Adapter for physics_step to reuse the step-local Q_pr cache."""

        _ = T_M
        return _lookup_qpr(size)

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

    blowout_cfg = getattr(cfg, "blowout", None)
    blowout_enabled_cfg = bool(getattr(blowout_cfg, "enabled", True)) if blowout_cfg else True
    blowout_target_phase = str(getattr(blowout_cfg, "target_phase", "solid_only")) if blowout_cfg else "solid_only"
    blowout_layer_mode = str(getattr(blowout_cfg, "layer", "surface_tau_le_1")) if blowout_cfg else "surface_tau_le_1"
    blowout_gate_mode = str(getattr(blowout_cfg, "gate_mode", "none")).lower() if blowout_cfg else "none"
    if blowout_gate_mode not in {"none", "sublimation_competition", "collision_competition"}:
        raise ConfigurationError(f"Unknown blowout.gate_mode={blowout_gate_mode!r}")
    blowout_enabled = blowout_enabled_cfg
    rp_blowout_cfg = getattr(cfg.sinks, "rp_blowout", None)
    rp_blowout_enabled = bool(getattr(rp_blowout_cfg, "enable", True)) if rp_blowout_cfg else True
    blowout_enabled = (
        blowout_enabled
        and collisions_active
        and rp_blowout_enabled
        and mars_rp_enabled_cfg
    )
    if radiation_field == "off":
        blowout_enabled = False
    gate_enabled = blowout_gate_mode != "none"
    if blowout_gate_mode == "collision_competition" and not bool(getattr(cfg.surface, "use_tcoll", True)):
        logger.warning(
            "blowout.gate_mode='collision_competition' requested but surface.use_tcoll=False; gate will ignore collisions"
        )
    freeze_kappa = bool(getattr(cfg.radiation, "freeze_kappa", False)) if cfg.radiation else False
    freeze_sigma = bool(getattr(cfg.surface, "freeze_sigma", False))
    shielding_mode = shielding_mode_resolved
    tau_fixed_cfg: Optional[float] = None
    sigma_tau1_fixed_cfg_raw = getattr(cfg.shielding, "fixed_tau1_sigma", None)
    sigma_tau1_mode_auto = (
        isinstance(sigma_tau1_fixed_cfg_raw, str) and sigma_tau1_fixed_cfg_raw.lower() == "auto"
    )
    sigma_tau1_mode_auto_max = (
        isinstance(sigma_tau1_fixed_cfg_raw, str) and sigma_tau1_fixed_cfg_raw.lower() == "auto_max"
    )
    shielding_auto_max_active = bool(sigma_tau1_mode_auto_max)
    sigma_tau1_fixed_cfg: Optional[float] = None
    if cfg.shielding is not None:
        tau_fixed_cfg = getattr(cfg.shielding, "fixed_tau1_tau", None)
        if not isinstance(sigma_tau1_fixed_cfg_raw, str):
            sigma_tau1_fixed_cfg = cast(Optional[float], sigma_tau1_fixed_cfg_raw)
    psd_floor_mode = getattr(getattr(cfg.psd, "floor", None), "mode", "fixed")
    collision_solver_mode = str(getattr(cfg.surface, "collision_solver", "surface_ode") or "surface_ode")
    if collision_solver_mode not in {"surface_ode", "smol"}:
        raise ConfigurationError(f"Unknown surface.collision_solver={collision_solver_mode!r}")

    s_min_config = cfg.sizes.s_min
    rad_init = physics_step.compute_radiation_parameters(
        s_min_config,
        rho_used,
        T_use,
        qpr_override=qpr_override,
    )
    a_blow = float(rad_init.a_blow)
    a_blow_effective = float(max(s_min_config, a_blow))
    qpr_for_blow = (
        float(qpr_override)
        if qpr_override is not None
        else float(radiation.qpr_lookup(max(a_blow, 1.0e-12), T_use))
    )
    if psd_floor_mode == "none":
        s_min_effective = float(s_min_config)
    else:
        s_min_effective = float(max(s_min_config, a_blow_effective))
    s_min_floor_dynamic = float(s_min_effective)
    evolve_min_size_enabled = bool(getattr(cfg.sizes, "evolve_min_size", False))
    s_min_evolved_value = s_min_effective
    s_min_surface_energy: float | None = 0.0
    s_min_components = {
        "config": float(s_min_config),
        "blowout": float(a_blow),
        "blowout_raw": float(a_blow),
        "blowout_effective": float(a_blow_effective),
        "effective": float(s_min_effective),
        "floor_mode": str(psd_floor_mode),
        "floor_dynamic": float(s_min_floor_dynamic),
    }
    if getattr(getattr(cfg, "surface_energy", None), "enabled", False):
        gamma_se = float(getattr(cfg.surface_energy, "gamma_J_m2", 1.0))
        eta_se = float(getattr(cfg.surface_energy, "eta", 0.1))
        alpha_se = float(getattr(cfg.psd, "alpha", 3.5))
        s_max_se = float(getattr(cfg.sizes, "s_max", 1.0))
        s0_override = getattr(cfg.surface_energy, "collider_size_m", None)
        s0_se = float(s0_override) if s0_override is not None else s_max_se
        f_lf_se = float(getattr(cfg.surface_energy, "largest_fragment_mass_fraction", 0.5))
        if not (0.0 < f_lf_se <= 1.0):
            raise ConfigurationError("surface_energy.largest_fragment_mass_fraction must be in (0, 1]")
        s_max_frag = s0_se * (f_lf_se ** (1.0 / 3.0))
        v_rel_floor = dynamics.v_rel_pericenter(e0_effective, v_k=r * Omega)
        s_min_surface_energy = _surface_energy_floor(
            gamma_J_m2=gamma_se,
            eta=eta_se,
            alpha=alpha_se,
            rho=rho_used,
            v_rel=v_rel_floor,
            s0=s0_se,
            s_max=s_max_frag,
        )
        if s_min_surface_energy > s_max_se:
            logger.warning(
                "surface_energy floor exceeds s_max (%.3e > %.3e); capping to s_max",
                s_min_surface_energy,
                s_max_se,
            )
            s_min_surface_energy = s_max_se
        s_min_effective = max(s_min_effective, s_min_surface_energy)
        s_min_components["surface_energy"] = float(s_min_surface_energy)
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
    s0_mode_value = str(getattr(cfg.initial, "s0_mode", "upper") or "upper").lower()
    if s0_mode_value == "mono":
        # Force a mono-disperse initial PSD at 1.5 m (user-requested baseline).
        n_bins = psd_state["sizes"].size
        s_mono = 1.5
        psd_state["sizes"] = np.full(n_bins, s_mono, dtype=float)
        psd_state["s"] = psd_state["sizes"]
        psd_state["widths"] = np.ones(n_bins, dtype=float)
        psd_state["number"] = np.ones(n_bins, dtype=float)
        psd_state["n"] = psd_state["number"]
        psd_state["edges"] = np.linspace(0.0, float(n_bins), n_bins + 1)
        psd_state["s_min"] = s_mono
        psd_state["s_max"] = s_mono
        psd_state["sizes_version"] = int(psd_state.get("sizes_version", 0)) + 1
    elif s0_mode_value in {"melt_lognormal_mixture", "melt_truncated_powerlaw"}:
        melt_cfg = getattr(cfg.initial, "melt_psd", None)
        if melt_cfg is None:
            raise ConfigurationError("initial.melt_psd must be provided when using melt_* s0_mode")
        melt_mode = str(getattr(melt_cfg, "mode", "lognormal_mixture") or "lognormal_mixture")
        if s0_mode_value == "melt_lognormal_mixture":
            mass_weights = psd.mass_weights_lognormal_mixture(
                psd_state["sizes"],
                psd_state["widths"],
                f_fine=getattr(melt_cfg, "f_fine", 0.0),
                s_fine=getattr(melt_cfg, "s_fine", 1.0e-4),
                s_meter=getattr(melt_cfg, "s_meter", 1.5),
                width_dex=getattr(melt_cfg, "width_dex", 0.3),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
        else:
            mass_weights = psd.mass_weights_truncated_powerlaw(
                psd_state["sizes"],
                psd_state["widths"],
                alpha_solid=getattr(melt_cfg, "alpha_solid", 3.5),
                s_min_solid=getattr(melt_cfg, "s_min_solid", s_min_effective),
                s_max_solid=getattr(melt_cfg, "s_max_solid", cfg.sizes.s_max),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
            melt_mode = "truncated_powerlaw"
        if melt_mode != "lognormal_mixture" and s0_mode_value == "melt_lognormal_mixture":
            logger.warning("s0_mode=%s but initial.melt_psd.mode=%s; using lognormal mixture from s0_mode", s0_mode_value, melt_mode)
        if melt_mode != "truncated_powerlaw" and s0_mode_value == "melt_truncated_powerlaw":
            logger.warning("s0_mode=%s but initial.melt_psd.mode=%s; using truncated power-law from s0_mode", s0_mode_value, melt_mode)
        psd_state = psd.apply_mass_weights(
            psd_state,
            mass_weights,
            rho=rho_used,
        )
        psd_state["s_min"] = s_min_effective
    elif s0_mode_value != "upper":
        raise ConfigurationError(f"Unknown initial.s0_mode={s0_mode_value!r}")
    psd.ensure_psd_state_contract(psd_state)
    psd.sanitize_and_normalize_number(psd_state, normalize=False)
    kappa_surf = _ensure_finite_kappa(psd.compute_kappa(psd_state), label="kappa_surf_initial")
    kappa_surf_initial = float(kappa_surf)
    kappa_eff0 = kappa_surf_initial
    optical_depth_cfg = getattr(cfg, "optical_depth", None)
    optical_depth_enabled = optical_depth_cfg is not None
    optical_tau0_target = None
    optical_tau_stop = None
    optical_tau_stop_tol = None
    optical_tau_field = "tau_los"
    sigma_surf0_target = None
    if optical_depth_enabled:
        optical_tau0_target = float(getattr(optical_depth_cfg, "tau0_target", 1.0))
        optical_tau_stop = float(getattr(optical_depth_cfg, "tau_stop", 1.0))
        optical_tau_stop_tol = float(getattr(optical_depth_cfg, "tau_stop_tol", 1.0e-6))
        optical_tau_field = str(getattr(optical_depth_cfg, "tau_field", "tau_los"))
        if optical_tau_field != "tau_los":
            raise ConfigurationError("optical_depth.tau_field must be 'tau_los' in v1")
        if optical_tau0_target <= 0.0 or not math.isfinite(optical_tau0_target):
            raise ConfigurationError("optical_depth.tau0_target must be positive and finite")
        if optical_tau_stop is None or optical_tau_stop <= 0.0 or not math.isfinite(optical_tau_stop):
            raise ConfigurationError("optical_depth.tau_stop must be positive and finite")
        if optical_tau_stop_tol is None or optical_tau_stop_tol < 0.0 or not math.isfinite(optical_tau_stop_tol):
            raise ConfigurationError("optical_depth.tau_stop_tol must be non-negative and finite")
        phi0 = float(phi_tau_fn(optical_tau0_target)) if phi_tau_fn is not None else 1.0
        kappa_eff0 = float(phi0 * kappa_surf_initial)
        if not math.isfinite(kappa_eff0) or kappa_eff0 <= 0.0:
            raise ConfigurationError("optical_depth requires a positive finite kappa_eff0")
        sigma_surf0_target = float(optical_tau0_target / (kappa_eff0 * los_factor))
        if not math.isfinite(sigma_surf0_target) or sigma_surf0_target < 0.0:
            raise ConfigurationError("optical_depth produced invalid Sigma_surf0")

    mu_reference_tau = None
    sigma_surf_mu_ref = None
    supply_const_cfg = getattr(getattr(cfg, "supply", None), "const", None)
    if supply_const_cfg is not None:
        mu_reference_tau = float(getattr(supply_const_cfg, "mu_reference_tau", 1.0))
        if mu_reference_tau <= 0.0 or not math.isfinite(mu_reference_tau):
            raise ConfigurationError("supply.const.mu_reference_tau must be positive and finite")
        phi_ref = float(phi_tau_fn(mu_reference_tau)) if phi_tau_fn is not None else 1.0
        kappa_eff_ref = float(phi_ref * kappa_surf_initial)
        if not math.isfinite(kappa_eff_ref) or kappa_eff_ref <= 0.0:
            raise ConfigurationError("mu_reference_tau requires a positive finite kappa_eff_ref")
        sigma_surf_mu_ref = float(mu_reference_tau / (kappa_eff_ref * los_factor))
    qpr_at_smin_config = _lookup_qpr(s_min_config)
    qpr_mean = _lookup_qpr(s_min_effective)
    beta_at_smin_config = radiation.beta(
        s_min_config, rho_used, T_use, Q_pr=qpr_at_smin_config
    )
    beta_at_smin_effective = radiation.beta(
        s_min_effective, rho_used, T_use, Q_pr=qpr_mean
    )
    beta_threshold = radiation.BLOWOUT_BETA_THRESHOLD
    beta_gate_active = beta_at_smin_effective >= beta_threshold
    case_status = "blowout" if beta_at_smin_config >= beta_threshold else "ok"
    if case_status != "blowout":
        logger.info(
            "Blow-out threshold not met at s_min_config=%.3e m (β=%.3f)",
            s_min_config,
            beta_at_smin_config,
        )
    if not blowout_enabled:
        case_status = "no_blowout"
    logger.debug(
        "[stage] psd_init s_min_effective=%.3e kappa0=%.3e",
        s_min_effective,
        kappa_surf_initial,
    )

    init_tau1_enabled = bool(
        getattr(cfg, "init_tau1", None) is not None and getattr(cfg.init_tau1, "enabled", False)
    )
    if optical_depth_enabled and init_tau1_enabled:
        logger.warning("optical_depth enabled; init_tau1.enabled is ignored in favour of tau0_target")
        init_tau1_enabled = False
    tau_field = getattr(cfg.init_tau1, "tau_field", "los") if init_tau1_enabled else "los"
    target_tau_init = float(getattr(cfg.init_tau1, "target_tau", 1.0) if init_tau1_enabled else 1.0)
    target_tau_init = target_tau_init if math.isfinite(target_tau_init) and target_tau_init > 0.0 else 1.0
    los_scale = los_factor if tau_field == "los" else 1.0
    sigma_tau1_unity = None
    sigma_override_applied = cfg.surface.sigma_surf_init_override
    if optical_depth_enabled and sigma_surf0_target is not None:
        sigma_override_applied = sigma_surf0_target
        if cfg.surface.sigma_surf_init_override is not None:
            logger.warning("surface.sigma_surf_init_override ignored because optical_depth is enabled")
    optical_depth_override_active = optical_depth_enabled and sigma_surf0_target is not None

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
        if kappa_for_init > 0.0 and math.isfinite(kappa_for_init):
            sigma_tau1_unity = target_tau_init / (kappa_for_init * los_scale)
        if init_tau1_enabled and sigma_tau1_unity is not None and math.isfinite(sigma_tau1_unity):
            sigma_override_applied = sigma_tau1_unity
        sigma_surf = initfields.surf_sigma_init(
            sigma_mid,
            kappa_for_init,
            cfg.surface.init_policy,
            sigma_override=sigma_override_applied,
        )
    elif init_tau1_enabled:
        # inner_disk_mass=null but init_tau1.enabled: compute sigma directly from kappa
        # Use raw kappa_surf (not shielding-adjusted) since tau_initial at L1699 uses kappa_surf_initial
        kappa_for_init = kappa_surf
        if kappa_for_init > 0.0 and math.isfinite(kappa_for_init):
            sigma_tau1_unity = target_tau_init / (kappa_for_init * los_scale)
            sigma_surf = sigma_tau1_unity
            logger.info(
                "init_tau1 without inner_disk_mass: sigma_surf=%.3e (target_tau=%.2f, kappa=%.3e, los_scale=%.2f)",
                sigma_surf,
                target_tau_init,
                kappa_for_init,
                los_scale,
            )
        else:
            sigma_surf = 0.0
            logger.warning("init_tau1 without inner_disk_mass: kappa_for_init<=0, sigma_surf=0")
    else:
        if sigma_override_applied is not None:
            sigma_surf = float(sigma_override_applied)
        else:
            sigma_surf = 0.0
    sigma_surf_init_raw = float(sigma_surf)
    tau_initial = float(kappa_surf_initial * sigma_surf_init_raw)
    tau_fixed_target = float(tau_fixed_cfg) if tau_fixed_cfg is not None else tau_initial
    sigma_tau1_fixed_target = float(sigma_tau1_fixed_cfg) if sigma_tau1_fixed_cfg is not None else None
    sigma_tau1_cap_init = None
    sigma_tau1_mode_label = "fixed" if sigma_tau1_fixed_cfg is not None else "none"
    if cfg.shielding is not None and (sigma_tau1_mode_auto or sigma_tau1_mode_auto_max):
        if sigma_tau1_mode_auto_max:
            logger.warning(
                "shielding.fixed_tau1_sigma=auto_max is debug-only; use only for diagnostic runs (margin=%.3f)",
                auto_max_margin,
            )
        tau_eval_auto = tau_initial * los_factor
        if phi_tau_fn is not None:
            kappa_eff0 = shielding.effective_kappa(kappa_surf_initial, tau_eval_auto, phi_tau_fn)
        if kappa_eff0 > 0.0 and math.isfinite(kappa_eff0):
            base_sigma_tau1 = target_tau_init / (kappa_eff0 * los_scale)
            if sigma_tau1_mode_auto:
                sigma_tau1_mode_label = "auto"
                sigma_tau1_fixed_target = base_sigma_tau1
                logger.info(
                    "shielding.fixed_tau1_sigma=auto -> Sigma_tau1=1/kappa_eff(t0)=%.3e (kappa_eff0=%.3e)",
                    sigma_tau1_fixed_target,
                    kappa_eff0,
                )
            else:
                sigma_tau1_mode_label = "auto_max"
                sigma_tau1_fixed_target = (
                    max(base_sigma_tau1, sigma_surf_init_raw) * (1.0 + auto_max_margin)
                )
                logger.info(
                    "shielding.fixed_tau1_sigma=auto_max -> Sigma_tau1=%.3e (base=%.3e, sigma_init=%.3e, margin=%.2f)",
                    sigma_tau1_fixed_target,
                    base_sigma_tau1,
                    sigma_surf_init_raw,
                    auto_max_margin,
                )
            sigma_tau1_cap_init = sigma_tau1_fixed_target
        else:
            logger.warning(
                "shielding.fixed_tau1_sigma=%s requested but kappa_eff0<=0 or non-finite (%.3e); leaving Sigma_tau1 unset",
                "auto_max" if sigma_tau1_mode_auto_max else "auto",
                kappa_eff0,
            )
    if sigma_tau1_cap_init is None:
        sigma_tau1_cap_init = sigma_tau1_fixed_target if sigma_tau1_fixed_target is not None else sigma_tau1_unity
    sigma_surf_reference = sigma_surf_init_raw
    initial_sigma_clipped = False
    if (
        init_tau1_enabled
        and getattr(cfg.init_tau1, "scale_to_tau1", False)
        and sigma_tau1_cap_init is not None
        and math.isfinite(sigma_tau1_cap_init)
    ):
        cap_with_margin = sigma_tau1_cap_init * (1.0 - auto_max_margin)
        cap_with_margin = cap_with_margin if cap_with_margin > 0.0 else sigma_tau1_cap_init
        if sigma_surf_reference > cap_with_margin:
            logger.warning(
                "init_tau1.scale_to_tau1: sigma_surf_init=%.3e clamped to %.3e (cap=%.3e)",
                sigma_surf_reference,
                cap_with_margin,
                sigma_tau1_cap_init,
            )
            sigma_surf_reference = cap_with_margin
            initial_sigma_clipped = True
    elif sigma_tau1_cap_init is not None and math.isfinite(sigma_tau1_cap_init):
        if sigma_surf_reference > sigma_tau1_cap_init:
            initial_sigma_clipped = True
            logger.warning(
                "initial sigma_surf=%.3e exceeds Sigma_tau1=%.3e with scale_to_tau1 disabled; headroom may be zero",
                sigma_surf_reference,
                sigma_tau1_cap_init,
            )
    sigma_surf = float(sigma_surf_reference)
    sigma_deep = 0.0
    headroom_initial = None
    if sigma_tau1_cap_init is not None and math.isfinite(sigma_tau1_cap_init):
        headroom_initial = float(sigma_tau1_cap_init - sigma_surf)
        log_level = logging.WARNING if headroom_initial <= 0.0 else logging.INFO
        logger.log(
            log_level,
            "initial Sigma_surf=%.3e kg/m^2, Sigma_tau1=%.3e -> headroom=%.3e kg/m^2",
            sigma_surf,
            sigma_tau1_cap_init,
            headroom_initial,
        )
    tau_initial = float(kappa_surf_initial * sigma_surf_reference)
    M_loss_cum = 0.0
    M_sink_cum = 0.0
    M_spill_cum = 0.0
    M_sublimation_cum = 0.0
    M_hydro_cum = 0.0
    if cfg.disk is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        area = math.pi * (r_out_d**2 - r_in_d**2)
        if area <= 0.0 or not math.isfinite(area):
            if (
                math.isfinite(r_in_d)
                and math.isfinite(r_out_d)
                and math.isclose(r_in_d, r_out_d, rel_tol=1.0e-12, abs_tol=0.0)
            ):
                area = math.pi * r**2
            else:
                logger.warning(
                    "Disk area is non-positive (r_in=%.3e m, r_out=%.3e m); falling back to π r^2 for 0D area.",
                    r_in_d,
                    r_out_d,
                )
                area = math.pi * r**2
    else:
        area = math.pi * r**2
    mass_total_original = cfg.initial.mass_total
    mass_total_applied = mass_total_original
    if (init_tau1_enabled or initial_sigma_clipped or optical_depth_override_active) and area > 0.0:
        mass_total_applied = float(sigma_surf_reference * area / constants.M_MARS)
        cfg.initial.mass_total = mass_total_applied
    chi_config_raw = getattr(cfg, "chi_blow", 1.0)
    chi_config = chi_config_raw
    chi_config_str = str(chi_config_raw)
    if isinstance(chi_config, str):
        chi_config_lower = chi_config.lower()
        if chi_config_lower == "auto":
            chi_blow_eff = _auto_chi_blow(beta_at_smin_effective, qpr_mean)
        else:
            raise ConfigurationError("chi_blow string value must be 'auto'")
        chi_config_str = "auto"
    else:
        chi_blow_eff = float(chi_config)
        if chi_blow_eff <= 0.0:
            raise ConfigurationError("chi_blow must be positive")
        chi_config_str = f"{chi_config_raw}"
    chi_blow_eff = float(min(max(chi_blow_eff, 0.5), 2.0))
    t_blow = chi_blow_eff / Omega

    sinks_mode_value = getattr(cfg.sinks, "mode", "sublimation")
    sinks_enabled_cfg = sinks_mode_value != "none"
    sublimation_location_raw = getattr(cfg.sinks, "sublimation_location", "surface")
    sublimation_location = str(sublimation_location_raw or "surface").lower()
    if sublimation_location not in {"surface", "smol", "both"}:
        raise ConfigurationError(
            f"sinks.sublimation_location must be 'surface', 'smol' or 'both' (got {sublimation_location!r})"
        )
    sublimation_to_surface = sublimation_location in {"surface", "both"}
    sublimation_to_smol = sublimation_location in {"smol", "both"}
    sublimation_enabled_cfg = bool(
        sinks_enabled_cfg
        and (
            getattr(cfg.sinks, "enable_sublimation", False)
            or sinks_mode_value == "sublimation"
        )
    )
    gas_drag_enabled_cfg = bool(
        sinks_enabled_cfg and getattr(cfg.sinks, "enable_gas_drag", False)
    )
    mass_conserving_sublimation = bool(getattr(sub_params, "mass_conserving", False))
    sink_opts = sinks.SinkOptions(
        enable_sublimation=sublimation_enabled_cfg,
        sub_params=sub_params,
        enable_gas_drag=gas_drag_enabled_cfg,
        rho_g=cfg.sinks.rho_g if gas_drag_enabled_cfg else 0.0,
    )
    if enforce_collisions_only:
        sink_opts.enable_sublimation = False
        sink_opts.enable_gas_drag = False
    sink_opts_surface = copy.deepcopy(sink_opts)
    sink_opts_surface.enable_sublimation = bool(
        sink_opts.enable_sublimation and sublimation_to_surface and not enforce_collisions_only
    )
    sink_opts_surface.enable_gas_drag = bool(sink_opts.enable_gas_drag and not enforce_collisions_only)
    if enforce_sublimation_only:
        sublimation_active_flag = True
    elif enforce_collisions_only:
        sublimation_active_flag = False
    else:
        sublimation_active_flag = sublimation_enabled_cfg
    sink_timescale_active = bool(
        (sink_opts_surface.enable_sublimation or sink_opts_surface.enable_gas_drag)
        and not enforce_collisions_only
    )
    sinks_active = bool(sublimation_active_flag or sink_timescale_active)

    supply_spec = cfg.supply
    supply_enabled_cfg = bool(getattr(supply_spec, "enabled", True))
    supply_mode_value = getattr(supply_spec, "mode", "const")
    supply_headroom_policy = getattr(supply_spec, "headroom_policy", "clip")
    supply_headroom_policy = str(supply_headroom_policy or "clip").lower()
    supply_headroom_enabled = supply_headroom_policy not in {"none", "off", "disabled"}
    if optical_depth_enabled and supply_headroom_enabled:
        logger.info("optical_depth enabled: disabling headroom policy '%s'", supply_headroom_policy)
        supply_headroom_policy = "none"
        supply_headroom_enabled = False
    supply_epsilon_mix = getattr(getattr(supply_spec, "mixing", None), "epsilon_mix", None)
    supply_const_rate = getattr(getattr(supply_spec, "const", None), "prod_area_rate_kg_m2_s", None)
    supply_const_tfill = getattr(getattr(supply_spec, "const", None), "auto_from_tau1_tfill_years", None)
    supply_mu_orbit_cfg = getattr(getattr(supply_spec, "const", None), "mu_orbit10pct", None)
    supply_orbit_fraction = getattr(getattr(supply_spec, "const", None), "orbit_fraction_at_mu1", None)
    supply_injection_cfg = getattr(supply_spec, "injection", None)
    supply_injection_mode = getattr(supply_injection_cfg, "mode", "min_bin") if supply_injection_cfg else "min_bin"
    supply_injection_s_min = getattr(supply_injection_cfg, "s_inj_min", None) if supply_injection_cfg else None
    supply_injection_s_max = getattr(supply_injection_cfg, "s_inj_max", None) if supply_injection_cfg else None
    supply_injection_q = float(getattr(supply_injection_cfg, "q", 3.5)) if supply_injection_cfg else 3.5
    supply_velocity_cfg = getattr(supply_injection_cfg, "velocity", None) if supply_injection_cfg else None
    supply_velocity_mode = getattr(supply_velocity_cfg, "mode", "inherit") if supply_velocity_cfg else "inherit"
    supply_velocity_e_inj = getattr(supply_velocity_cfg, "e_inj", None) if supply_velocity_cfg else None
    supply_velocity_i_inj = getattr(supply_velocity_cfg, "i_inj", None) if supply_velocity_cfg else None
    supply_velocity_vrel_factor = getattr(supply_velocity_cfg, "vrel_factor", None) if supply_velocity_cfg else None
    supply_velocity_blend_mode = getattr(supply_velocity_cfg, "blend_mode", "rms") if supply_velocity_cfg else "rms"
    supply_velocity_weight_mode = getattr(supply_velocity_cfg, "weight_mode", "delta_sigma") if supply_velocity_cfg else "delta_sigma"
    supply_injection_weights = None
    if supply_injection_mode == "initial_psd":
        sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
        widths_arr = np.asarray(psd_state.get("widths"), dtype=float)
        number_raw = psd_state.get("number")
        if number_raw is None:
            number_raw = psd_state.get("n")
        if number_raw is None:
            raise ConfigurationError("initial_psd supply injection requires PSD number densities")
        number_arr = np.asarray(number_raw, dtype=float)
        if (
            sizes_arr.shape != widths_arr.shape
            or sizes_arr.shape != number_arr.shape
            or sizes_arr.size == 0
        ):
            raise ConfigurationError(
                "initial_psd supply injection requires sizes/widths/number arrays with matching shapes"
            )
        weights = sizes_arr**3 * widths_arr * number_arr
        weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
        if float(np.sum(weights)) <= 0.0:
            raise ConfigurationError("initial_psd supply injection requires positive mass weights from the initial PSD")
        supply_injection_weights = weights
    supply_transport_cfg = getattr(supply_spec, "transport", None)
    supply_transport_mode = getattr(supply_transport_cfg, "mode", "direct") if supply_transport_cfg else "direct"
    supply_transport_headroom_gate = (
        getattr(supply_transport_cfg, "headroom_gate", "hard") if supply_transport_cfg else "hard"
    )
    supply_deep_tmix_orbits = (
        getattr(supply_transport_cfg, "t_mix_orbits", None) if supply_transport_cfg else None
    )
    if supply_deep_tmix_orbits is None:
        supply_deep_tmix_orbits = (
            getattr(supply_injection_cfg, "deep_reservoir_tmix_orbits", None) if supply_injection_cfg else None
        )
    if supply_transport_mode == "deep_mixing" and supply_deep_tmix_orbits is None:
        raise ConfigurationError("supply.transport.t_mix_orbits must be set and positive when mode='deep_mixing'")
    supply_deep_enabled = bool(
        supply_transport_mode == "deep_mixing"
        or (
            supply_deep_tmix_orbits is not None
            and math.isfinite(float(supply_deep_tmix_orbits))
            and float(supply_deep_tmix_orbits) > 0.0
        )
    )
    supply_effective_rate = None
    supply_reservoir_cfg = getattr(supply_spec, "reservoir", None)
    supply_reservoir_enabled = bool(getattr(supply_reservoir_cfg, "enabled", False)) if supply_reservoir_cfg else False
    supply_reservoir_mass_total = getattr(supply_reservoir_cfg, "mass_total_Mmars", None)
    supply_reservoir_mode = getattr(supply_reservoir_cfg, "depletion_mode", None)
    supply_reservoir_taper_fraction = None
    if supply_reservoir_cfg is not None:
        supply_reservoir_taper_fraction = getattr(
            supply_reservoir_cfg,
            "taper_fraction",
            getattr(supply_reservoir_cfg, "smooth_fraction", None),
        )
    supply_feedback_cfg = getattr(supply_spec, "feedback", None)
    supply_feedback_enabled = bool(getattr(supply_feedback_cfg, "enabled", False)) if supply_feedback_cfg else False
    supply_feedback_tau_field = _resolve_feedback_tau_field(
        getattr(supply_feedback_cfg, "tau_field", "tau_los") if supply_feedback_cfg else "tau_los"
    )
    supply_feedback_target = getattr(supply_feedback_cfg, "target_tau", None) if supply_feedback_cfg else None
    supply_feedback_gain = getattr(supply_feedback_cfg, "gain", None) if supply_feedback_cfg else None
    supply_feedback_response_yr = getattr(supply_feedback_cfg, "response_time_years", None) if supply_feedback_cfg else None
    if not supply_feedback_enabled and supply_feedback_cfg is not None:
        feedback_fields_set = getattr(supply_feedback_cfg, "model_fields_set", None)
        if feedback_fields_set is None:
            feedback_fields_set = getattr(supply_feedback_cfg, "__fields_set__", set())
        non_default_fields = {field for field in feedback_fields_set if field != "enabled"}
        if non_default_fields:
            logger.warning(
                "supply.feedback.* provided (%s) but feedback.enabled is false; feedback loop will be inactive",
                ", ".join(sorted(non_default_fields)),
            )
    supply_temperature_cfg = getattr(supply_spec, "temperature", None)
    supply_temperature_mode = getattr(supply_temperature_cfg, "mode", None) if supply_temperature_cfg else None
    supply_temperature_enabled = bool(getattr(supply_temperature_cfg, "enabled", False)) if supply_temperature_cfg else False
    supply_temperature_table_path = (
        getattr(getattr(supply_temperature_cfg, "table", None), "path", None) if supply_temperature_cfg else None
    )
    supply_temperature_value_kind = (
        getattr(getattr(supply_temperature_cfg, "table", None), "value_kind", None)
        if supply_temperature_cfg
        else None
    )
    try:
        # Optional: derive const rate from mu_orbit10pct and the initial surface density.
        if (
            supply_enabled_cfg
            and supply_mode_value == "const"
            and supply_mu_orbit_cfg is not None
        ):
            if sigma_surf_mu_ref is None or not math.isfinite(sigma_surf_mu_ref):
                raise ConfigurationError(
                    "supply.const.mu_orbit10pct requires a finite Sigma_ref from mu_reference_tau"
                )
            if supply_epsilon_mix is None or supply_epsilon_mix <= 0.0:
                raise ConfigurationError("supply.mixing.epsilon_mix must be positive when using mu_orbit10pct")
            orbit_fraction = 0.10 if supply_orbit_fraction is None else float(supply_orbit_fraction)
            if orbit_fraction <= 0.0 or not math.isfinite(orbit_fraction):
                raise ConfigurationError("supply.const.orbit_fraction_at_mu1 must be positive and finite")
            supply_orbit_fraction = orbit_fraction
            epsilon_mix = float(supply_epsilon_mix)
            dotSigma_target = float(supply_mu_orbit_cfg) * orbit_fraction * float(sigma_surf_mu_ref) / float(t_orb)
            supply_const_rate = dotSigma_target / epsilon_mix
            logger.info(
                "Derived supply.const.prod_area_rate_kg_m2_s=%.3e from mu_orbit10pct=%.3f, "
                "orbit_fraction=%.3f, Sigma_ref=%.3e kg/m^2 (tau_ref=%.3f), epsilon_mix=%.3f (dotSigma_prod=%.3e)",
                supply_const_rate,
                supply_mu_orbit_cfg,
                orbit_fraction,
                sigma_surf_mu_ref,
                mu_reference_tau,
                epsilon_mix,
                dotSigma_target,
            )
        elif (
            supply_enabled_cfg
            and supply_mode_value == "const"
            and supply_const_tfill is not None
            and sigma_tau1_cap_init is not None
            and math.isfinite(sigma_tau1_cap_init)
            and supply_epsilon_mix is not None
            and supply_epsilon_mix > 0.0
        ):
            supply_const_rate = float(sigma_tau1_cap_init) / (
                float(supply_const_tfill) * SECONDS_PER_YEAR * float(supply_epsilon_mix)
            )
            logger.info(
                "Derived supply.const.prod_area_rate_kg_m2_s=%.3e from Sigma_tau1=%.3e kg/m^2, "
                "t_fill=%.3f yr, epsilon_mix=%.3f",
                supply_const_rate,
                sigma_tau1_cap_init,
                supply_const_tfill,
                supply_epsilon_mix,
            )
        if supply_enabled_cfg and supply_mode_value == "const":
            if supply_const_rate is not None and supply_epsilon_mix is not None:
                supply_effective_rate = float(supply_const_rate) * float(supply_epsilon_mix)
        if supply_const_rate is not None and hasattr(supply_spec, "const"):
            setattr(supply_spec.const, "prod_area_rate_kg_m2_s", float(supply_const_rate))
    except Exception:
        supply_effective_rate = None
    supply_table_path = getattr(getattr(supply_spec, "table", None), "path", None)
    supply_state = supply.init_runtime_state(supply_spec, area, seconds_per_year=SECONDS_PER_YEAR)
    supply_state.feedback_tau_field = supply_feedback_tau_field
    supply_reservoir_enabled = bool(getattr(supply_state, "reservoir_enabled", supply_reservoir_enabled))
    logger.debug(
        "[stage] supply_ready mode=%s epsilon_mix=%s",
        supply_mode_value,
        supply_epsilon_mix,
    )
    pending_deprecation_warnings: List[str] = []
    deprecated_supply_messages: List[str] = []
    if supply_enabled_cfg:
        if not optical_depth_enabled:
            deprecated_supply_messages.append("optical_depth disabled")
        if supply_mode_value != "const":
            deprecated_supply_messages.append(f"supply.mode='{supply_mode_value}'")
        if supply_const_tfill is not None:
            deprecated_supply_messages.append("supply.const.auto_from_tau1_tfill_years set")
        if supply_orbit_fraction is not None and math.isfinite(float(supply_orbit_fraction)):
            if abs(float(supply_orbit_fraction) - 0.10) > 1.0e-6:
                deprecated_supply_messages.append(
                    f"supply.const.orbit_fraction_at_mu1={float(supply_orbit_fraction):.3g}"
                )
        supply_mu_reference_tau = getattr(supply_const_cfg, "mu_reference_tau", None)
        if supply_mu_reference_tau is not None and math.isfinite(float(supply_mu_reference_tau)):
            if abs(float(supply_mu_reference_tau) - 1.0) > 1.0e-6:
                deprecated_supply_messages.append(
                    f"supply.const.mu_reference_tau={float(supply_mu_reference_tau):.3g}"
                )
        supply_fields_set = _model_fields_set(supply_spec)
        if "headroom_policy" in supply_fields_set:
            deprecated_supply_messages.append(f"supply.headroom_policy='{supply_headroom_policy}'")
        if supply_injection_cfg is not None:
            default_injection = supply_injection_cfg.__class__()
            injection_flags: List[str] = []
            if supply_injection_mode != default_injection.mode:
                injection_flags.append(f"mode='{supply_injection_mode}'")
            if supply_injection_s_min is not None:
                injection_flags.append(f"s_inj_min={float(supply_injection_s_min):.3g}")
            if supply_injection_s_max is not None:
                injection_flags.append(f"s_inj_max={float(supply_injection_s_max):.3g}")
            if not math.isclose(float(supply_injection_q), float(default_injection.q), rel_tol=1e-9, abs_tol=0.0):
                injection_flags.append(f"q={float(supply_injection_q):.3g}")
            deep_tmix_cfg = getattr(supply_injection_cfg, "deep_reservoir_tmix_orbits", None)
            if deep_tmix_cfg is not None and math.isfinite(float(deep_tmix_cfg)) and float(deep_tmix_cfg) > 0.0:
                injection_flags.append(f"deep_reservoir_tmix_orbits={float(deep_tmix_cfg):.3g}")
            if (
                injection_flags == [f"mode='{supply_injection_mode}'"]
                and supply_injection_mode == "initial_psd"
            ):
                injection_flags = []
            if injection_flags:
                deprecated_supply_messages.append(f"supply.injection ({', '.join(injection_flags)})")
            default_velocity = getattr(default_injection, "velocity", None)
            if supply_velocity_cfg is not None and default_velocity is not None:
                velocity_flags: List[str] = []
                if supply_velocity_mode != default_velocity.mode:
                    velocity_flags.append(f"mode='{supply_velocity_mode}'")
                if supply_velocity_e_inj is not None:
                    velocity_flags.append(f"e_inj={float(supply_velocity_e_inj):.3g}")
                if supply_velocity_i_inj is not None:
                    velocity_flags.append(f"i_inj={float(supply_velocity_i_inj):.3g}")
                if supply_velocity_vrel_factor is not None:
                    velocity_flags.append(f"vrel_factor={float(supply_velocity_vrel_factor):.3g}")
                if supply_velocity_blend_mode != default_velocity.blend_mode:
                    velocity_flags.append(f"blend_mode='{supply_velocity_blend_mode}'")
                if supply_velocity_weight_mode != default_velocity.weight_mode:
                    velocity_flags.append(f"weight_mode='{supply_velocity_weight_mode}'")
                if velocity_flags:
                    deprecated_supply_messages.append(
                        f"supply.injection.velocity ({', '.join(velocity_flags)})"
                    )
        transport_flags: List[str] = []
        if supply_transport_mode != "direct":
            transport_flags.append(f"mode='{supply_transport_mode}'")
        if supply_transport_headroom_gate != "hard":
            transport_flags.append(f"headroom_gate='{supply_transport_headroom_gate}'")
        if (
            supply_deep_tmix_orbits is not None
            and math.isfinite(float(supply_deep_tmix_orbits))
            and float(supply_deep_tmix_orbits) > 0.0
        ):
            transport_flags.append(f"t_mix_orbits={float(supply_deep_tmix_orbits):.3g}")
        if transport_flags:
            deprecated_supply_messages.append(f"supply.transport ({', '.join(transport_flags)})")
        feedback_fields_set = _model_fields_set(supply_feedback_cfg)
        feedback_non_default = bool(feedback_fields_set - {"enabled"})
        if supply_feedback_enabled or feedback_non_default:
            deprecated_supply_messages.append("supply.feedback configured")
        temperature_fields_set = _model_fields_set(supply_temperature_cfg)
        temperature_non_default = bool(temperature_fields_set - {"enabled"})
        if supply_temperature_enabled or temperature_non_default:
            deprecated_supply_messages.append("supply.temperature configured")
        reservoir_fields_set = _model_fields_set(supply_reservoir_cfg)
        reservoir_non_default = bool(reservoir_fields_set - {"enabled"})
        reservoir_mass = (
            float(supply_reservoir_mass_total)
            if supply_reservoir_mass_total is not None and math.isfinite(float(supply_reservoir_mass_total))
            else None
        )
        if supply_reservoir_enabled or reservoir_non_default or (reservoir_mass is not None and reservoir_mass > 0.0):
            deprecated_supply_messages.append("supply.reservoir configured")
    if deprecated_supply_messages:
        pending_deprecation_warnings.append(
            "External supply configuration deviates from the default optical_depth + mu_orbit10pct scheme "
            "(docs/plan/20251220_optical_depth_external_supply_impl_plan.md; "
            "~/.codex/plans/marsdisk-tau-sweep-phi-off.md). "
            "Non-default settings are deprecated removal candidates; use for sensitivity studies only. "
            f"Detected: {', '.join(deprecated_supply_messages)}."
        )
    if getattr(cfg.init_tau1, "scale_to_tau1", False):
        pending_deprecation_warnings.append(
            "init_tau1.scale_to_tau1 is deprecated; use optical_depth.tau0_target and tau_stop instead "
            "(docs/plan/20251220_optical_depth_external_supply_impl_plan.md)."
        )

    t_end, dt_nominal, dt_initial_step, n_steps, time_grid_info = _resolve_time_grid(
        cfg.numerics,
        Omega,
        t_orb,
        temp_runtime=temp_runtime,
    )
    logger.debug(
        "[stage] time_grid_ready t_end=%.3e dt=%.3e n_steps=%d",
        t_end,
        dt_initial_step,
        n_steps,
    )
    dt = dt_initial_step
    max_steps = _get_max_steps()
    if n_steps > max_steps:
        n_steps = max_steps
        dt = t_end / n_steps
        time_grid_info["n_steps"] = n_steps
        time_grid_info["dt_step"] = dt
        time_grid_info["dt_capped_by_max_steps"] = True

    checkpoint_cfg = getattr(cfg.numerics, "checkpoint", None)
    resume_cfg = getattr(cfg.numerics, "resume", None)
    checkpoint_enabled = bool(checkpoint_cfg and getattr(checkpoint_cfg, "enabled", False))
    checkpoint_interval_s = (
        float(getattr(checkpoint_cfg, "interval_years", 1.0) or 1.0) * SECONDS_PER_YEAR
        if checkpoint_enabled
        else float("inf")
    )
    checkpoint_format = str(getattr(checkpoint_cfg, "format", "pickle") or "pickle")
    checkpoint_keep_last = int(getattr(checkpoint_cfg, "keep_last_n", 3) or 0)
    checkpoint_dir = (
        Path(checkpoint_cfg.path) if checkpoint_cfg and getattr(checkpoint_cfg, "path", None) else Path(cfg.io.outdir) / "checkpoints"
    )
    resume_enabled = bool(resume_cfg and getattr(resume_cfg, "enabled", False))
    resume_path = Path(resume_cfg.from_path) if resume_enabled and getattr(resume_cfg, "from_path", None) else None
    start_step = 0
    time_offset = 0.0
    progress_state_from_ckpt: Optional[Dict[str, Any]] = None

    quiet_mode = bool(getattr(cfg.io, "quiet", False))
    progress_cfg = getattr(cfg.io, "progress", None)
    progress_enabled = bool(getattr(progress_cfg, "enable", False)) if progress_cfg else False
    progress_refresh = (
        float(getattr(progress_cfg, "refresh_seconds", 1.0))
        if progress_cfg is not None
        else 1.0
    )
    memory_hint_short: Optional[str] = None
    memory_hint_header: Optional[str] = None
    if progress_enabled:
        n_bins_cfg = int(getattr(cfg.sizes, "n_bins", 0) or 0)
        psd_history_enabled_hint = bool(getattr(cfg.io, "psd_history", True))
        psd_history_stride_hint = int(getattr(cfg.io, "psd_history_stride", 1) or 1)
        if psd_history_stride_hint < 1:
            psd_history_stride_hint = 1
        step_diag_cfg_hint = getattr(cfg.io, "step_diagnostics", None)
        step_diag_enabled_hint = (
            bool(getattr(step_diag_cfg_hint, "enable", False)) if step_diag_cfg_hint else False
        )
        memory_hint_short, memory_hint_header = _memory_estimate(
            n_steps,
            n_bins_cfg,
            n_cells=1,
            psd_history_enabled=psd_history_enabled_hint,
            psd_history_stride=psd_history_stride_hint,
            diagnostics_enabled=True,
            mass_budget_enabled=True,
            mass_budget_cells_enabled=False,
            step_diag_enabled=step_diag_enabled_hint,
        )
    progress = ProgressReporter(
        n_steps,
        t_end,
        refresh_seconds=max(progress_refresh, 0.1),
        enabled=progress_enabled,
        memory_hint=memory_hint_short,
        memory_header=memory_hint_header,
    )
    progress.emit_header()

    resume_applied = False
    checkpoint_next_time = checkpoint_interval_s
    if resume_enabled:
        resolved_resume = resume_path if resume_path is not None else checkpoint_io.find_latest_checkpoint(checkpoint_dir)
        if resolved_resume is None:
            logger.warning("resume.enabled=true but no checkpoint found under %s", checkpoint_dir)
        else:
            try:
                state_ckpt = checkpoint_io.load_checkpoint(resolved_resume)
                start_step = int(state_ckpt.step_no) + 1
                checkpoint_next_time = float(state_ckpt.time_s) + checkpoint_interval_s
                if not math.isclose(state_ckpt.dt_s, dt, rel_tol=1e-6, abs_tol=0.0):
                    logger.warning(
                        "Checkpoint dt=%.6e differs from current dt=%.6e; continuing with current dt",
                        state_ckpt.dt_s,
                        dt,
                    )
                time_offset = float(state_ckpt.time_s) - dt * start_step
                sigma_surf = float(state_ckpt.sigma_surf)
                sigma_deep = float(state_ckpt.sigma_deep)
                s_min_effective = float(state_ckpt.s_min_effective)
                s_min_floor_dynamic = float(state_ckpt.s_min_floor_dynamic)
                s_min_evolved_value = float(state_ckpt.s_min_evolved_value)
                psd_state = copy.deepcopy(state_ckpt.psd_state)
                M_loss_cum = float(state_ckpt.M_loss_cum)
                M_sink_cum = float(state_ckpt.M_sink_cum)
                M_spill_cum = float(state_ckpt.M_spill_cum)
                M_sublimation_cum = float(state_ckpt.M_sublimation_cum)
                M_hydro_cum = float(state_ckpt.M_hydro_cum)
                restored_supply_state = state_ckpt.supply_state_as_runtime()
                if restored_supply_state is not None and supply_state is not None:
                    for key, value in asdict(restored_supply_state).items():
                        if hasattr(supply_state, key):
                            setattr(supply_state, key, value)
                try:
                    np.random.set_state(state_ckpt.rng_state_numpy)
                except Exception:
                    logger.warning("Failed to restore numpy RNG state from checkpoint")
                try:
                    rng.bit_generator.state = state_ckpt.rng_state_generator
                except Exception:
                    logger.warning("Failed to restore default_rng state from checkpoint")
                try:
                    random.setstate(state_ckpt.rng_state_python)
                except Exception:
                    logger.warning("Failed to restore Python RNG state from checkpoint")
                progress_state_from_ckpt = getattr(state_ckpt, "progress_state", None)
                resume_applied = True
                logger.info(
                    "Resumed from checkpoint %s at step=%d time=%.3e s (offset=%.3e s)",
                    resolved_resume,
                    start_step,
                    state_ckpt.time_s,
                    time_offset,
                )
            except Exception as exc:
                logger.error("Failed to load checkpoint %s: %s", resolved_resume, exc)
    else:
        checkpoint_next_time = checkpoint_interval_s

    if quiet_mode:
        warnings.filterwarnings("ignore")
        logging.getLogger().setLevel(logging.WARNING)
    for message in pending_deprecation_warnings:
        warnings.warn(message, DeprecationWarning, stacklevel=2)
    if resume_applied and progress_enabled:
        progress.restore_state(progress_state_from_ckpt)
        progress.update(
            max(start_step - 1, 0),
            max(time_offset + start_step * dt, 0.0),
            force=True,
        )

    step_diag_cfg = getattr(cfg.io, "step_diagnostics", None)
    step_diag_enabled = bool(getattr(step_diag_cfg, "enable", False)) if step_diag_cfg else False
    step_diag_format = str(getattr(step_diag_cfg, "format", "csv") or "csv").lower()
    if step_diag_format not in {"csv", "jsonl"}:
        raise ConfigurationError("io.step_diagnostics.format must be either 'csv' or 'jsonl'")
    step_diag_path_cfg = getattr(step_diag_cfg, "path", None) if step_diag_cfg else None
    step_diag_path: Optional[Path] = None
    if step_diag_enabled:
        if step_diag_path_cfg is not None:
            step_diag_path = Path(step_diag_path_cfg)
            if not step_diag_path.is_absolute():
                step_diag_path = Path(cfg.io.outdir) / step_diag_path
        else:
            ext = "jsonl" if step_diag_format == "jsonl" else "csv"
            step_diag_path = Path(cfg.io.outdir) / "series" / f"step_diagnostics.{ext}"

    def _env_flag(name: str) -> Optional[bool]:
        raw = os.environ.get(name)
        if raw is None:
            return None
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on", "enable", "enabled"}:
            return True
        if value in {"0", "false", "no", "off", "disable", "disabled"}:
            return False
        return None

    streaming_cfg = getattr(cfg.io, "streaming", None)
    force_streaming_off = False
    force_streaming_on = False
    io_streaming_flag = _env_flag("IO_STREAMING")
    if io_streaming_flag is False:
        force_streaming_off = True
    elif io_streaming_flag is True:
        force_streaming_on = True
    env_force_off = _env_flag("FORCE_STREAMING_OFF")
    env_force_on = _env_flag("FORCE_STREAMING_ON")
    if env_force_off is True:
        force_streaming_off = True
    if env_force_on is True:
        force_streaming_on = True

    streaming_enabled_cfg = bool(
        streaming_cfg
        and getattr(streaming_cfg, "enable", True)
        and not getattr(streaming_cfg, "opt_out", False)
    )
    streaming_enabled = streaming_enabled_cfg
    if force_streaming_on:
        streaming_enabled = True
    if force_streaming_off:
        streaming_enabled = False

    streaming_memory_limit_gb = float(getattr(streaming_cfg, "memory_limit_gb", 10.0) or 10.0)
    streaming_step_interval = int(getattr(streaming_cfg, "step_flush_interval", 10000) or 0)
    streaming_compression = str(getattr(streaming_cfg, "compression", "snappy") or "snappy")
    streaming_merge_at_end = bool(getattr(streaming_cfg, "merge_at_end", True))
    streaming_cleanup_chunks = bool(getattr(streaming_cfg, "cleanup_chunks", True))

    archive_cfg = getattr(cfg.io, "archive", None)
    archive_enabled_cfg = bool(archive_cfg and getattr(archive_cfg, "enabled", False))
    archive_enabled = archive_enabled_cfg
    archive_forced_off = False
    archive_forced_on = False
    io_archive_flag = _env_flag("IO_ARCHIVE")
    if io_archive_flag is False:
        archive_enabled = False
        archive_forced_off = True
    elif io_archive_flag is True:
        archive_enabled = True
        archive_forced_on = True
    archive_dir_raw = getattr(archive_cfg, "dir", None) if archive_cfg else None
    archive_dir = Path(archive_dir_raw).expanduser() if archive_dir_raw else None
    archive_trigger = str(getattr(archive_cfg, "trigger", "post_finalize") or "post_finalize").lower()
    archive_merge_target = str(getattr(archive_cfg, "merge_target", "external") or "external").lower()
    archive_verify = bool(getattr(archive_cfg, "verify", True)) if archive_cfg else True
    archive_verify_level = str(getattr(archive_cfg, "verify_level", "standard_plus") or "standard_plus")
    archive_keep_local = str(getattr(archive_cfg, "keep_local", "metadata") or "metadata").lower()
    archive_mode = str(getattr(archive_cfg, "mode", "copy") or "copy").lower()
    archive_record_volume_info = bool(getattr(archive_cfg, "record_volume_info", True)) if archive_cfg else True
    archive_warn_slow_mb_s = getattr(archive_cfg, "warn_slow_mb_s", 40.0) if archive_cfg else 40.0
    archive_warn_slow_min_gb = getattr(archive_cfg, "warn_slow_min_gb", 5.0) if archive_cfg else 5.0
    archive_min_free_gb = getattr(archive_cfg, "min_free_gb", None) if archive_cfg else None
    archive_root_resolved: Optional[Path] = None
    archive_dest_dir: Optional[Path] = None
    if archive_dir is not None:
        try:
            archive_root_resolved = archive_dir.resolve()
            archive_dest_dir = archive_mod.resolve_archive_dest(archive_root_resolved, outdir)
        except Exception:
            archive_root_resolved = None
            archive_dest_dir = None

    streaming_merge_outdir: Optional[Path] = None
    if archive_enabled and archive_merge_target == "external" and archive_dest_dir is not None:
        streaming_merge_outdir = archive_dest_dir
        if archive_trigger == "post_finalize":
            streaming_cleanup_chunks = False
    psd_history_enabled = bool(getattr(cfg.io, "psd_history", True))
    psd_history_stride = int(getattr(cfg.io, "psd_history_stride", 1) or 1)
    if psd_history_stride < 1:
        psd_history_stride = 1
    streaming_merge_completed: Optional[bool] = None
    series_columns = list(ZERO_D_SERIES_KEYS)
    diagnostic_columns = list(ZERO_D_DIAGNOSTIC_KEYS)
    record_storage_mode = str(getattr(cfg.io, "record_storage_mode", "row") or "row").lower()
    if record_storage_mode not in {"row", "columnar"}:
        record_storage_mode = "row"
    columnar_enabled = record_storage_mode == "columnar"
    if _env_flag("MARSDISK_DISABLE_COLUMNAR") is True:
        columnar_enabled = False
    streaming_state = StreamingState(
        enabled=streaming_enabled,
        outdir=Path(cfg.io.outdir),
        merge_outdir=streaming_merge_outdir,
        compression=streaming_compression,
        memory_limit_gb=streaming_memory_limit_gb,
        step_flush_interval=streaming_step_interval,
        merge_at_end=streaming_merge_at_end,
        cleanup_chunks=streaming_cleanup_chunks,
        step_diag_enabled=step_diag_enabled,
        step_diag_path=step_diag_path,
        step_diag_format=step_diag_format,
        series_columns=series_columns,
        diagnostic_columns=diagnostic_columns,
    )

    energy_streaming_cfg = getattr(getattr(cfg.diagnostics, "energy_bookkeeping", None), "stream", True)
    energy_bookkeeping_enabled_cfg = bool(getattr(getattr(cfg.diagnostics, "energy_bookkeeping", None), "enabled", False))
    energy_streaming_enabled = streaming_state.enabled and bool(energy_streaming_cfg) and energy_bookkeeping_enabled_cfg
    if streaming_state.enabled:
        streaming_state.chunk_start_step = start_step
        if streaming_state.mass_budget_path.exists():
            streaming_state.mass_budget_header_written = True

    last_step_index = max(start_step - 1, -1)
    history = ZeroDHistory()
    if columnar_enabled:
        history.records = ColumnarBuffer()
        history.diagnostics = ColumnarBuffer()

    def _build_checkpoint_state(step_no: int, time_after_step: float) -> checkpoint_io.CheckpointState:
        supply_payload: Dict[str, Any] = {}
        if supply_state is not None:
            supply_payload = asdict(supply_state)
            supply_payload.pop("temperature_table", None)
        progress_payload = progress.snapshot_state()
        return checkpoint_io.CheckpointState(
            version=1,
            step_no=step_no,
            time_s=time_after_step,
            dt_s=dt,
            sigma_surf=float(sigma_surf),
            sigma_deep=float(sigma_deep),
            s_min_effective=float(s_min_effective),
            s_min_floor_dynamic=float(s_min_floor_dynamic),
            s_min_evolved_value=float(s_min_evolved_value),
            M_loss_cum=float(M_loss_cum),
            M_sink_cum=float(M_sink_cum),
            M_spill_cum=float(M_spill_cum),
            M_sublimation_cum=float(M_sublimation_cum),
            M_hydro_cum=float(M_hydro_cum),
            psd_state=copy.deepcopy(psd_state),
            supply_state=supply_payload,
            rng_state_numpy=np.random.get_state(),
            rng_state_generator=copy.deepcopy(rng.bit_generator.state),
            rng_state_python=random.getstate(),
            progress_state=progress_payload,
        )

    def _streaming_cleanup_on_exit() -> None:
        """Flush remaining streaming buffers and merge chunks on shutdown."""

        if not streaming_state.enabled:
            return
        try:
            final_idx = last_step_index if last_step_index >= 0 else streaming_state.chunk_start_step
            streaming_state.flush(history, final_idx)
            if streaming_state.merge_at_end:
                streaming_state.merge_chunks()
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            short_msg = _format_exception_short(exc)
            logger.error(
                "Streaming cleanup failed during shutdown (%s): %s",
                exc.__class__.__name__,
                short_msg,
            )
            logger.debug("Streaming cleanup full exception", exc_info=exc)

    if streaming_state.enabled:
        weakref.finalize(history, _streaming_cleanup_on_exit)
        if streaming_state.merge_at_end:
            atexit.register(_streaming_cleanup_on_exit)

    records = history.records
    psd_hist_records = history.psd_hist_records
    diagnostics = history.diagnostics
    mass_budget = history.mass_budget
    energy_series: List[Dict[str, float]] = []
    energy_budget: List[Dict[str, float]] = []
    last_mass_budget_entry: Optional[Dict[str, Any]] = None
    step_diag_records = history.step_diag_records
    debug_sinks_enabled = bool(getattr(cfg.io, "debug_sinks", False))
    correct_fast_blowout = bool(getattr(cfg.io, "correct_fast_blowout", False))
    substep_fast_enabled = bool(getattr(cfg.io, "substep_fast_blowout", False))
    substep_max_ratio_raw = getattr(cfg.io, "substep_max_ratio", None)
    substep_max_ratio = 1.0 if substep_max_ratio_raw is None else float(substep_max_ratio_raw)
    if substep_max_ratio <= 0.0:
        raise ConfigurationError("io.substep_max_ratio must be positive")
    debug_records = history.debug_records
    eval_per_step = bool(getattr(cfg.numerics, "eval_per_step", True))
    eval_requires_step = eval_per_step or temp_runtime.enabled
    orbit_rollup_enabled = bool(getattr(cfg.numerics, "orbit_rollup", True))
    dt_over_t_blow_cfg = getattr(cfg.numerics, "dt_over_t_blow_max", None)
    dt_over_t_blow_max = (
        float(dt_over_t_blow_cfg)
        if dt_over_t_blow_cfg is not None
        else float("inf")
    )
    monitor_dt_ratio = math.isfinite(dt_over_t_blow_max) and dt_over_t_blow_max > 0.0
    stop_on_blowout_below_smin = bool(getattr(cfg.numerics, "stop_on_blowout_below_smin", False))
    blowout_stop_threshold = float(s_min_config)

    orbit_time_accum = 0.0
    orbit_loss_blow = 0.0
    orbit_loss_sink = 0.0
    orbits_completed = 0
    orbit_rollup_rows = history.orbit_rollup_rows
    phase_usage = defaultdict(float)
    phase_method_usage = defaultdict(float)
    sink_branch_usage = defaultdict(float)

    Omega_step = Omega
    t_orb_step = t_orb
    a_blow_step = a_blow
    a_blow_effective_step = a_blow_effective
    qpr_mean_step = qpr_mean
    qpr_for_blow_step = qpr_for_blow

    temperature_track = history.temperature_track
    beta_track = history.beta_track
    ablow_track = history.ablow_track
    blowout_effective_warned = False
    gate_factor_track = history.gate_factor_track
    t_solid_track = history.t_solid_track
    tau_gate_block_time = history.tau_gate_block_time
    total_time_elapsed = max(history.total_time_elapsed, time_offset)
    extended_total_rate_track = history.extended_total_rate_track
    extended_total_rate_time_track = history.extended_total_rate_time_track
    extended_ts_ratio_track = history.extended_ts_ratio_track
    supply_feedback_track: List[float] = []
    supply_temperature_scale_track: List[float] = []
    supply_reservoir_remaining_track: List[float] = []
    supply_rate_nominal_track: List[float] = []
    supply_rate_scaled_track: List[float] = []
    supply_rate_applied_track: List[float] = []
    supply_headroom_track: List[float] = []
    supply_clip_factor_track: List[float] = []
    supply_visibility_track: List[float] = []
    supply_blocked_track: List[bool] = []
    supply_mixing_block_track: List[bool] = []
    supply_spill_rate_track: List[float] = []
    supply_rate_scaled_initial: Optional[float] = None
    supply_clip_time = 0.0
    supply_clip_streak = 0
    supply_clip_warn_threshold = 1000
    supply_clip_events: List[Dict[str, float]] = []
    supply_reservoir_depleted_time: Optional[float] = None
    supply_visibility_eps = 1.0e-30
    supply_headroom_eps = 1.0e-18
    dt_over_t_blow_values: List[float] = []
    mass_budget_max_error = 0.0
    steps_since_flush = 0
    t_mix_seconds_current: Optional[float] = None
    sigma_tau1_limit_last_finite: Optional[float] = None
    phase_bulk_state_last: Optional[str] = None
    phase_bulk_f_liquid_last: Optional[float] = None
    phase_bulk_f_solid_last: Optional[float] = None
    phase_bulk_f_vapor_last: Optional[float] = None
    last_time_value = time_offset + (start_step - 1) * dt if start_step > 0 else 0.0
    early_stop_reason: Optional[str] = None
    early_stop_step: Optional[int] = None
    early_stop_time_s: Optional[float] = None
    tau_stop_los_value: Optional[float] = None
    energy_sum_rel = 0.0
    energy_sum_diss = 0.0
    energy_sum_ret = 0.0
    energy_last_row: Optional[Dict[str, float]] = None
    energy_count = 0
    _reset_collision_runtime_state()
    smol_sink_workspace: SmolSinkWorkspace | None = None

    def _mark_reservoir_depletion(current_time: float) -> None:
        """Record the first time the finite reservoir is exhausted."""

        nonlocal supply_reservoir_depleted_time
        if supply_reservoir_depleted_time is not None:
            return
        if (
            supply_state is not None
            and supply_state.reservoir_enabled
            and supply_state.reservoir_mass_remaining_kg is not None
            and supply_state.reservoir_mass_remaining_kg <= 0.0
        ):
            supply_reservoir_depleted_time = current_time

    def _update_sigma_tau1_last_finite(value: Optional[float]) -> None:
        """Track the last finite Σ_τ=1 cap without changing runtime behaviour."""

        nonlocal sigma_tau1_limit_last_finite
        if value is not None and math.isfinite(value):
            sigma_tau1_limit_last_finite = float(value)

    for step_no in range(start_step, n_steps):
        time_start = time_offset + step_no * dt
        time = time_start
        T_use = temp_runtime.evaluate(time)
        temperature_track.append(T_use)
        rad_flux_step = constants.SIGMA_SB * (T_use**4)
        T_p_effective = phase_mod.particle_temperature_equilibrium(
            T_use,
            r,
            phase_q_abs_mean,
        )
        temperature_for_phase = (
            T_p_effective if phase_temperature_input_mode == "particle" else T_use
        )
        gate_factor = 1.0
        t_solid_step = None
        mass_err_percent_step = None
        smol_sigma_before = None
        smol_sigma_after = None
        smol_sigma_loss = None
        smol_dt_eff = None
        smol_mass_error = None
        smol_prod_mass_rate = None
        smol_extra_mass_loss_rate = None
        smol_mass_budget_delta = None
        smol_gain_mass_rate = None
        smol_loss_mass_rate = None
        smol_sink_mass_rate = None
        smol_source_mass_rate = None
        supply_rate_nominal_current: Optional[float] = None
        supply_rate_scaled_current: Optional[float] = None
        supply_rate_applied_current: Optional[float] = None
        prod_rate_raw_current: Optional[float] = None
        prod_rate_diverted_current: float = 0.0
        prod_rate_into_deep_current: float = 0.0
        deep_to_surf_flux_attempt_current: float = 0.0
        deep_to_surf_flux_current: float = 0.0
        spill_rate_current: float = 0.0
        mass_loss_spill_step = 0.0
        supply_visibility_factor_current: Optional[float] = None
        supply_blocked_by_headroom_flag = False
        supply_mixing_limited_flag = False
        headroom_current: Optional[float] = None
        clip_factor_current: float = float("nan")
        diverted_mass_step = 0.0
        deep_to_surf_mass_step = 0.0
        deep_to_surf_attempt_mass_step = 0.0
        prod_into_deep_mass_step = 0.0
        sigma_deep_before = sigma_deep
        stop_after_record = False

        if eval_requires_step or step_no == 0:
            Omega_step = grid.omega_kepler(r)
            if Omega_step <= 0.0:
                raise PhysicsError("Computed Keplerian frequency must be positive")
            t_orb_step = 2.0 * math.pi / Omega_step
            if supply_deep_enabled:
                t_mix_seconds_current = float(supply_deep_tmix_orbits) * t_orb_step
            else:
                t_mix_seconds_current = None
            setattr(sub_params, "runtime_t_orb_s", t_orb_step)
            setattr(sub_params, "runtime_Omega", Omega_step)

            blowout_init = float(psd_state.get("s_min", s_min_config))
            rad_blow = physics_step.compute_radiation_parameters(
                s_min_effective,
                rho_used,
                T_use,
                qpr_override=qpr_override,
                initial=blowout_init,
            )
            a_blow_step = float(rad_blow.a_blow)
            a_blow_effective_step = float(max(s_min_config, a_blow_step))
            qpr_for_blow = (
                float(qpr_override)
                if qpr_override is not None
                else float(radiation.qpr_lookup(max(a_blow_step, 1.0e-12), T_use))
            )
            if (
                not blowout_effective_warned
                and a_blow_effective_step > a_blow_step * (1.0 + 1.0e-12)
            ):
                logger.info(
                    "s_blow_m now records the raw blow-out radius; use s_blow_m_effective for the "
                    "size-floor-clipped value."
                )
                blowout_effective_warned = True
            qpr_for_blow_step = qpr_for_blow
            if psd_floor_mode == "none":
                s_min_blow = float(s_min_config)
            else:
                s_min_blow = float(a_blow_effective_step)
            if psd_floor_mode == "none":
                s_min_effective = float(psd_state.get("s_min", s_min_config))
            elif psd_floor_mode == "evolve_smin":
                s_min_effective = max(s_min_blow, s_min_floor_dynamic)
            else:
                s_min_effective = s_min_blow
                s_min_floor_dynamic = float(max(s_min_floor_dynamic, s_min_effective))
            psd_state["s_min"] = s_min_effective
            s_min_components["blowout"] = float(a_blow_step)
            s_min_components["blowout_raw"] = float(a_blow_step)
            s_min_components["blowout_effective"] = float(a_blow_effective_step)
            s_min_components["effective"] = float(s_min_effective)
            s_min_components["floor_dynamic"] = float(s_min_floor_dynamic)
            rad_step = physics_step.compute_radiation_parameters(
                s_min_effective,
                rho_used,
                T_use,
                qpr_override=qpr_override,
                qpr_lookup_fn=_lookup_qpr_cached,
                a_blow_override=a_blow_step,
            )
            qpr_mean_step = float(rad_step.qpr_mean)
            beta_at_smin_effective = float(rad_step.beta)
            beta_gate_active = beta_at_smin_effective >= beta_threshold
        beta_track.append(beta_at_smin_effective)
        ablow_track.append(a_blow_step)

        if stop_on_blowout_below_smin and a_blow_step <= blowout_stop_threshold:
            early_stop_reason = "a_blow_below_s_min_config"
            early_stop_step = step_no
            early_stop_time_s = time
            total_time_elapsed = time
            logger.info(
                "Early stop triggered: a_blow=%.3e m dropped below s_min_config=%.3e m at t=%.3e s (step %d)",
                a_blow_step,
                blowout_stop_threshold,
                time,
                step_no,
            )
            break

        t_blow_step = chi_blow_eff / Omega_step if Omega_step > 0.0 else float("inf")

        sigma_for_tau_phase = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_phase_used, tau_phase_los = compute_phase_tau_fields(
            kappa_surf,
            sigma_for_tau_phase,
            los_factor,
            phase_tau_field,
        )
        phase_decision, phase_bulk_step = phase_controller.evaluate_with_bulk(
            temperature_for_phase,
            pressure_Pa=gas_pressure_pa,
            tau=tau_phase_used,
            radius_m=r,
            time_s=time,
            T0_K=temp_runtime.initial_value,
        )
        phase_state_step = phase_decision.state
        phase_method_step = phase_decision.method
        phase_reason_step = phase_decision.reason
        phase_f_vap_step = phase_decision.f_vap
        phase_payload_step = dict(phase_decision.payload)
        phase_payload_step["tau_input_before_psd"] = tau_phase_used
        phase_payload_step["tau_phase_los"] = tau_phase_los
        phase_payload_step["tau_phase_used"] = tau_phase_used
        phase_payload_step["phase_tau_field"] = phase_tau_field
        phase_payload_step["phase_temperature_input"] = phase_temperature_input_mode
        phase_payload_step["phase_temperature_used_K"] = temperature_for_phase
        phase_payload_step["T_p_effective"] = T_p_effective
        phase_payload_step["phase_temperature_formula"] = phase_temperature_formula
        phase_payload_step["phase_bulk_state"] = phase_bulk_step.state
        phase_payload_step["phase_bulk_f_liquid"] = phase_bulk_step.f_liquid
        phase_payload_step["phase_bulk_f_solid"] = phase_bulk_step.f_solid
        phase_payload_step["phase_bulk_f_vapor"] = phase_bulk_step.f_vapor
        phase_payload_step["allow_liquid_hkl"] = allow_liquid_hkl
        tau_phase_los_last = tau_phase_los
        tau_phase_used_last = tau_phase_used
        phase_usage[phase_state_step] += dt
        phase_method_usage[phase_method_step] += dt

        liquid_block_collisions = phase_bulk_step.state == "liquid_dominated"
        collisions_active_step = bool(collisions_active and not liquid_block_collisions)
        phase_payload_step["collisions_blocked_by_phase"] = bool(liquid_block_collisions)
        # Delay external supply by one global step and block it in liquid-dominated regions.
        allow_supply_step = (
            step_no > 0 and phase_state_step == "solid" and not liquid_block_collisions
        )
        energy_columns: dict[str, float] = {}

        ds_dt_raw = 0.0
        ds_dt_val = 0.0
        sigma_loss_sublimation_blow = 0.0
        T_grain = None
        sublimation_blocked_by_phase = False
        sublimation_active = sublimation_active_flag
        liquid_block_step = (
            sublimation_active
            and phase_bulk_step.state == "liquid_dominated"
            and not allow_liquid_hkl
        )
        sublimation_res = physics_step.compute_sublimation(
            T_use,
            r,
            rho_used,
            sub_params,
            phase_state="liquid_dominated" if liquid_block_step else "solid",
            enabled=sublimation_active,
        )
        T_grain = sublimation_res.T_grain
        ds_dt_raw = sublimation_res.ds_dt_raw
        sublimation_blocked_by_phase = bool(liquid_block_step and ds_dt_raw < 0.0)
        ds_dt_val = 0.0 if liquid_block_step else ds_dt_raw
        sublimation_surface_active_step = bool(
            sublimation_active and sublimation_to_surface and not sublimation_blocked_by_phase
        )
        sublimation_smol_active_step = bool(
            sublimation_active and sublimation_to_smol and not sublimation_blocked_by_phase
        )
        floor_for_step = s_min_effective
        if psd_floor_mode == "none":
            floor_for_step = 0.0 if (mass_conserving_sublimation and ds_dt_val < 0.0) else float(s_min_config)
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
            ds_dt=ds_dt_val if sublimation_surface_active_step else 0.0,
            dt=dt,
            floor=floor_for_step,
            sigma_surf=sigma_surf,
        )
        psd.sanitize_and_normalize_number(psd_state, normalize=False)
        if mass_conserving_sublimation and ds_dt_val < 0.0:
            sigma_loss_sublimation_blow = delta_sigma_sub
            delta_sigma_sub = 0.0
        kappa_surf = _ensure_finite_kappa(psd.compute_kappa(psd_state), label="kappa_surf_step")
        if freeze_kappa:
            kappa_surf = kappa_surf_initial
        dSigma_dt_sublimation = delta_sigma_sub / dt if dt > 0.0 else 0.0
        mass_loss_sublimation_step = delta_sigma_sub * area / constants.M_MARS
        if mass_loss_sublimation_step < 0.0:
            mass_loss_sublimation_step = 0.0
        if mass_loss_sublimation_step > 0.0 and sublimation_surface_active_step:
            M_sink_cum += mass_loss_sublimation_step
            M_sublimation_cum += mass_loss_sublimation_step

        if cfg.sinks.mode == "none" or not sink_timescale_active:
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
                Omega_step,
                sink_opts_surface,
                s_ref=SINK_REF_SIZE,
            )
        t_sink_total_value = sink_result.t_sink
        t_sink_surface_only = t_sink_total_value
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

        sigma_for_tau_phase = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_los_value = kappa_surf * sigma_for_tau_phase * los_factor
        tau_los = float(tau_los_value) if math.isfinite(tau_los_value) else 0.0
        phase_payload_step["tau_mars_line_of_sight"] = tau_los
        tau_gate_block_step = bool(
            tau_gate_enabled
            and math.isfinite(tau_los)
            and tau_los >= tau_gate_threshold
        )
        phase_allows_step = not (
            blowout_target_phase == "solid_only" and phase_state_step != "solid"
        )
        enable_blowout_step = bool(
            collisions_active_step
            and blowout_enabled
            and beta_gate_active
            and phase_allows_step
            and not tau_gate_block_step
        )
        hydro_timescale_step = None
        sink_selected_step = "rp_blowout" if enable_blowout_step else "none"
        if phase_controller.enabled and phase_state_step == "vapor":
            hydro_timescale_step = phase_mod.hydro_escape_timescale(
                hydro_cfg,
                T_use,
                phase_f_vap_step,
            )
            if hydro_timescale_step is not None:
                sink_selected_step = "hydro_escape"
        if enable_blowout_step and hydro_timescale_step is not None:
            raise RuntimeError(
                "Blow-out and hydrodynamic escape sinks cannot be active simultaneously"
            )
        sink_branch_usage[sink_selected_step] += dt
        phase_state_last = phase_state_step
        phase_method_last = phase_method_step
        phase_reason_last = phase_reason_step
        phase_payload_last = dict(phase_payload_step)
        phase_f_vap_last = phase_f_vap_step
        phase_bulk_state_last = phase_bulk_step.state
        phase_bulk_f_liquid_last = phase_bulk_step.f_liquid
        phase_bulk_f_solid_last = phase_bulk_step.f_solid
        phase_bulk_f_vapor_last = phase_bulk_step.f_vapor
        sink_selected_last = sink_selected_step
        tau_gate_block_last = tau_gate_block_step
        hydro_timescale_last = hydro_timescale_step
        tau_los_last = tau_los
        phase_payload_last["sink_selected"] = sink_selected_step
        phase_payload_last["tau_gate_blocked"] = tau_gate_block_step
        phase_payload_last["sublimation_blocked_by_phase"] = bool(sublimation_blocked_by_phase)
        phase_payload_last["collisions_blocked_by_phase"] = bool(liquid_block_collisions)
        phase_allows_last = phase_allows_step
        beta_gate_last = beta_gate_active

        if sink_selected_step == "hydro_escape" and hydro_timescale_step is not None:
            t_sink_step_effective = hydro_timescale_step
        elif phase_controller.enabled and phase_state_step == "vapor":
            t_sink_step_effective = None
        else:
            t_sink_step_effective = t_sink_surface_only

        substep_active = False
        substep_requested = False
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
            substep_requested = bool(
                substep_fast_enabled
                and collision_solver_mode == "surface_ode"
                and fast_blowout_ratio > substep_max_ratio
            )
            if substep_requested:
                n_substeps = int(math.ceil(dt / (substep_max_ratio * t_blow_step)))
                dt_sub = dt / n_substeps
                substep_active = True
            else:
                n_substeps = 1
                dt_sub = dt
                substep_active = False
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
            n_substeps = 1
            dt_sub = dt
            ratio_sub = 0.0
            fast_blowout_factor_sub = 0.0
            apply_correction = False
        fast_blowout_applied = False

        kappa_eff = kappa_surf
        sigma_tau1_limit = None
        sigma_tau1_active_last = None
        prod_rate_last = 0.0
        supply_diag_last = None
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
        e_kernel_step = None
        i_kernel_step = None
        e_kernel_base_step = None
        i_kernel_base_step = None
        e_kernel_supply_step = None
        i_kernel_supply_step = None
        supply_velocity_weight_step = None
        e_state_next_step = None
        i_state_next_step = None
        e_damp_target_step = None
        t_damp_applied_step = None

        tau_los_last = None
        tau_phase_los_last: Optional[float] = None
        tau_phase_used_last: Optional[float] = None
        phi_effective_last = None
        hydro_mass_total = 0.0
        mass_loss_sublimation_smol_step = 0.0
        mass_loss_rate_sublimation_smol = 0.0
        mass_err_percent_step = 0.0
        sigma_loss_smol = 0.0
        t_coll_kernel_last = None
        surface_active = collisions_active_step or sink_timescale_active
        sigma_before_step = sigma_surf
        if collision_solver_mode == "surface_ode":
            if surface_active:
                for _sub_idx in range(n_substeps):
                    if freeze_sigma:
                        sigma_surf = sigma_surf_reference
                    shield_supply = _apply_shielding_and_supply(
                        time_now=time_sub,
                        r=r,
                        dt=dt_sub,
                        sigma_surf=sigma_surf,
                        kappa_surf=kappa_surf,
                        collisions_active_step=collisions_active_step,
                        shielding_mode=shielding_mode,
                        phi_tau_fn=phi_tau_fn,
                        tau_fixed_target=tau_fixed_target,
                        sigma_tau1_fixed_target=sigma_tau1_fixed_target,
                        los_factor=los_factor,
                        use_tcoll=bool(getattr(cfg.surface, "use_tcoll", False)),
                        enable_blowout_step=enable_blowout_step,
                        sink_timescale_active=sink_timescale_active,
                        t_sink_step_effective=t_sink_step_effective,
                        supply_spec=supply_spec,
                        area=area,
                        supply_state=supply_state,
                        temperature_K=T_use,
                        allow_supply=allow_supply_step,
                        sigma_deep=sigma_deep,
                        t_mix=t_mix_seconds_current,
                        deep_enabled=supply_deep_enabled,
                        transport_mode=supply_transport_mode,
                        headroom_gate=supply_transport_headroom_gate,
                        headroom_policy=supply_headroom_policy,
                        t_blow=t_blow_step,
                    )
                    shield_step = shield_supply.shield_step
                    tau_eval_los = shield_step.tau_los
                    kappa_eff = shield_step.kappa_eff
                    sigma_tau1_limit = shield_step.sigma_tau1
                    phi_value = shield_step.phi_effective
                    _update_sigma_tau1_last_finite(sigma_tau1_limit)
                    phi_effective_last = phi_value
                    tau_los_last = tau_eval_los
                    enable_blowout_sub = shield_supply.enable_blowout_sub
                    t_sink_current = shield_supply.t_sink_current
                    tau_for_coll = shield_step.tau_for_coll
                    supply_step = shield_supply.supply_step
                    prod_rate_raw_current = supply_step.prod_rate_raw
                    supply_rate_nominal_current = supply_step.supply_rate_nominal
                    supply_rate_scaled_current = supply_step.supply_rate_scaled
                    if supply_rate_scaled_initial is None and math.isfinite(supply_step.supply_res.rate):
                        supply_rate_scaled_initial = float(supply_step.supply_res.rate)
                    sigma_tau1_active = None
                    sigma_tau1_active_last = sigma_tau1_active
                    split_res = supply_step.split_res
                    prod_rate = split_res.prod_rate_applied
                    prod_rate_last = prod_rate
                    prod_rate_diverted_current = split_res.prod_rate_diverted
                    prod_rate_into_deep_current = split_res.prod_rate_into_deep
                    deep_to_surf_flux_attempt_current = split_res.deep_to_surf_flux_attempt
                    deep_to_surf_flux_current = split_res.deep_to_surf_rate
                    sigma_deep = split_res.sigma_deep
                    headroom_current = split_res.headroom
                    supply_rate_applied_current = prod_rate
                    supply_diag_last = supply_step.supply_res
                    _mark_reservoir_depletion(time_sub)
                    diverted_mass_step += prod_rate_diverted_current * dt_sub
                    prod_into_deep_mass_step += prod_rate_into_deep_current * dt_sub
                    deep_to_surf_mass_step += deep_to_surf_flux_current * dt_sub
                    deep_to_surf_attempt_mass_step += deep_to_surf_flux_attempt_current * dt_sub
                    total_prod_surface += prod_rate * dt_sub
                    surface_res = physics_step.step_surface_layer(
                        sigma_surf,
                        prod_rate,
                        dt_sub,
                        Omega_step,
                        tau=tau_for_coll,
                        t_sink=t_sink_current,
                        sigma_tau1=sigma_tau1_active,
                        enable_blowout=enable_blowout_sub,
                        chi_blow=chi_blow_eff,
                    )
                    sigma_surf = surface_res.sigma_surf
                    outflux_surface = surface_res.outflux
                    sink_flux_surface = surface_res.sink_flux
                    if sink_selected_step == "hydro_escape" and hydro_timescale_step is not None:
                        hydro_mass_total += sink_flux_surface * dt_sub * area / constants.M_MARS
                    if freeze_sigma:
                        sigma_surf = sigma_surf_reference
                    total_sink_surface += sink_flux_surface * dt_sub
                    fast_factor_numer += fast_blowout_factor_sub * dt_sub
                    fast_factor_denom += dt_sub
                    time_sub += dt_sub
                if apply_correction:
                    outflux_surface, corrected = _apply_blowout_correction(
                        outflux_surface,
                        factor=fast_blowout_factor_sub,
                        apply=True,
                    )
                    fast_blowout_applied = fast_blowout_applied or corrected
            else:
                time_sub = time_start + dt
                tau_los_last = kappa_surf * sigma_surf * los_factor
                sigma_tau1_limit = None
                kappa_eff = kappa_surf
                sigma_tau1_active_last = None
            surface_update = physics_step.SurfaceUpdateResult(
                sigma_surf=sigma_surf,
                outflux_surface=outflux_surface,
                sink_flux_surface=sink_flux_surface,
                t_blow=t_blow_step,
                t_coll=None,
                prod_rate_effective=prod_rate_last,
                mass_error=0.0,
            )
            sigma_surf = surface_update.sigma_surf
            outflux_surface = surface_update.outflux_surface
            sink_flux_surface = surface_update.sink_flux_surface
            prod_rate_last = surface_update.prod_rate_effective
        else:
            if surface_active:
                if freeze_sigma:
                    sigma_surf = sigma_surf_reference
                shield_supply = _apply_shielding_and_supply(
                    time_now=time_start,
                    r=r,
                    dt=dt,
                    sigma_surf=sigma_surf,
                    kappa_surf=kappa_surf,
                    collisions_active_step=collisions_active_step,
                    shielding_mode=shielding_mode,
                    phi_tau_fn=phi_tau_fn,
                    tau_fixed_target=tau_fixed_target,
                    sigma_tau1_fixed_target=sigma_tau1_fixed_target,
                    los_factor=los_factor,
                    use_tcoll=bool(getattr(cfg.surface, "use_tcoll", False)),
                    enable_blowout_step=enable_blowout_step,
                    sink_timescale_active=sink_timescale_active,
                    t_sink_step_effective=t_sink_step_effective,
                    supply_spec=supply_spec,
                    area=area,
                    supply_state=supply_state,
                    temperature_K=T_use,
                    allow_supply=allow_supply_step,
                    sigma_deep=sigma_deep,
                    t_mix=t_mix_seconds_current,
                    deep_enabled=supply_deep_enabled,
                    transport_mode=supply_transport_mode,
                    headroom_gate=supply_transport_headroom_gate,
                    headroom_policy=supply_headroom_policy,
                    t_blow=t_blow_step,
                )
                shield_step = shield_supply.shield_step
                tau_eval_los = shield_step.tau_los
                kappa_eff = shield_step.kappa_eff
                sigma_tau1_limit = shield_step.sigma_tau1
                phi_value = shield_step.phi_effective
                _update_sigma_tau1_last_finite(sigma_tau1_limit)
                phi_effective_last = phi_value
                tau_los_last = tau_eval_los
                enable_blowout_sub = shield_supply.enable_blowout_sub
                t_sink_current = shield_supply.t_sink_current
                supply_step = shield_supply.supply_step
                prod_rate_raw_current = supply_step.prod_rate_raw
                supply_rate_nominal_current = supply_step.supply_rate_nominal
                supply_rate_scaled_current = supply_step.supply_rate_scaled
                if supply_rate_scaled_initial is None and math.isfinite(supply_step.supply_res.rate):
                    supply_rate_scaled_initial = float(supply_step.supply_res.rate)
                sigma_tau1_active = None
                sigma_tau1_active_last = sigma_tau1_active
                split_res = supply_step.split_res
                prod_rate = split_res.prod_rate_applied
                prod_rate_last = prod_rate
                prod_rate_diverted_current = split_res.prod_rate_diverted
                prod_rate_into_deep_current = split_res.prod_rate_into_deep
                deep_to_surf_flux_attempt_current = split_res.deep_to_surf_flux_attempt
                deep_to_surf_flux_current = split_res.deep_to_surf_rate
                sigma_deep = split_res.sigma_deep
                headroom_current = split_res.headroom
                supply_rate_applied_current = prod_rate
                supply_diag_last = supply_step.supply_res
                _mark_reservoir_depletion(time_start)
                diverted_mass_step += prod_rate_diverted_current * dt
                prod_into_deep_mass_step += prod_rate_into_deep_current * dt
                deep_to_surf_mass_step += deep_to_surf_flux_current * dt
                deep_to_surf_attempt_mass_step += deep_to_surf_flux_attempt_current * dt
                sigma_before_step = sigma_surf
                if collisions_active_step:
                    t_coll_step = t_coll_kernel_last
                    collision_ctx = collisions_smol.CollisionStepContext(
                        time_orbit=collisions_smol.TimeOrbitParams(
                            dt=dt,
                            Omega=Omega_step,
                            r=r,
                            t_blow=t_blow_step,
                        ),
                        material=collisions_smol.MaterialParams(
                            rho=rho_used,
                            a_blow=a_blow_step,
                            s_min_effective=s_min_effective,
                        ),
                        dynamics=collisions_smol.DynamicsParams(
                            e_value=e0_effective,
                            i_value=i0_effective,
                            dynamics_cfg=cfg.dynamics,
                            tau_eff=tau_eval_los,
                        ),
                        supply=collisions_smol.SupplyParams(
                            prod_subblow_area_rate=prod_rate,
                            supply_injection_mode=supply_injection_mode,
                            supply_s_inj_min=supply_injection_s_min,
                            supply_s_inj_max=supply_injection_s_max,
                            supply_q=supply_injection_q,
                            supply_mass_weights=supply_injection_weights,
                            supply_velocity_cfg=supply_velocity_cfg,
                        ),
                        control=collisions_smol.CollisionControlFlags(
                            enable_blowout=enable_blowout_sub,
                            collisions_enabled=collisions_active_step,
                            mass_conserving_sublimation=mass_conserving_sublimation,
                            headroom_policy=supply_headroom_policy,
                            sigma_tau1=sigma_tau1_active,
                            t_sink=t_sink_current if sink_timescale_active else None,
                            ds_dt_val=ds_dt_val if sublimation_smol_active_step else None,
                            energy_bookkeeping_enabled=bool(getattr(cfg.diagnostics.energy_bookkeeping, "enabled", False)),
                            eps_restitution=float(getattr(cfg.dynamics, "eps_restitution", 0.5)),
                            f_ke_cratering=float(getattr(cfg.dynamics, "f_ke_cratering", 0.1)),
                            f_ke_fragmentation=getattr(cfg.dynamics, "f_ke_fragmentation", None),
                        ),
                        sigma_surf=sigma_surf,
                        enable_e_damping=bool(getattr(cfg.dynamics, "enable_e_damping", False)),
                        t_coll_for_damp=t_coll_step,
                    )
                    smol_res = collisions_smol.step_collisions(collision_ctx, psd_state)
                    psd_state = smol_res.psd_state
                    sigma_surf = smol_res.sigma_after
                    t_coll_kernel_last = smol_res.t_coll_kernel
                    e_kernel_step = smol_res.e_kernel_used
                    i_kernel_step = smol_res.i_kernel_used
                    e_kernel_base_step = smol_res.e_kernel_base
                    i_kernel_base_step = smol_res.i_kernel_base
                    e_kernel_supply_step = smol_res.e_kernel_supply
                    i_kernel_supply_step = smol_res.i_kernel_supply
                    supply_velocity_weight_step = smol_res.supply_velocity_weight
                    e_state_next_step = smol_res.e_next
                    i_state_next_step = smol_res.i_next
                    e_damp_target_step = smol_res.e_eq_target
                    t_damp_applied_step = smol_res.t_damp_used
                    if bool(getattr(cfg.dynamics, "enable_e_damping", False)) and smol_res.e_next is not None:
                        e0_effective = float(smol_res.e_next)
                        i0_effective = float(
                            smol_res.i_next if smol_res.i_next is not None else i0_effective
                        )
                    sigma_loss_smol = max(sigma_loss_smol, 0.0) + max(smol_res.sigma_loss, 0.0)
                    prod_rate_last = smol_res.prod_mass_rate_effective
                    supply_rate_applied_current = prod_rate_last
                    total_prod_surface = smol_res.prod_mass_rate_effective * dt
                    outflux_surface = smol_res.dSigma_dt_blowout
                    spill_rate_current = smol_res.mass_loss_rate_spill
                    mass_loss_spill_step = (
                        spill_rate_current * dt * area / constants.M_MARS if dt > 0.0 else 0.0
                    )
                    if apply_correction:
                        outflux_surface, corrected = _apply_blowout_correction(
                            outflux_surface,
                            factor=fast_blowout_factor_sub,
                            apply=True,
                        )
                        fast_blowout_applied = fast_blowout_applied or corrected
                    clip_rate = max(
                        smol_res.dSigma_dt_sinks
                        - smol_res.mass_loss_rate_sinks
                        - smol_res.mass_loss_rate_sublimation
                        - smol_res.mass_loss_rate_spill,
                        0.0,
                    )
                    sink_flux_surface = (
                        smol_res.mass_loss_rate_sinks
                        + smol_res.mass_loss_rate_sublimation
                        + smol_res.mass_loss_rate_spill
                        + clip_rate
                    )
                    total_sink_surface = smol_res.dSigma_dt_sinks * dt
                    mass_loss_rate_sublimation_smol = smol_res.mass_loss_rate_sublimation
                    mass_loss_sublimation_smol_step = (
                        mass_loss_rate_sublimation_smol * dt * area / constants.M_MARS
                    )
                    fast_factor_numer = fast_blowout_factor_sub * dt
                    fast_factor_denom = dt
                    mass_err_percent_step = smol_res.mass_error * 100.0
                    smol_sigma_before = smol_res.sigma_before
                    smol_sigma_after = smol_res.sigma_after
                    smol_sigma_loss = smol_res.sigma_loss
                    smol_dt_eff = smol_res.dt_eff
                    smol_mass_error = smol_res.mass_error
                    smol_prod_mass_rate = smol_res.prod_mass_rate_effective
                    smol_extra_mass_loss_rate = (
                        smol_res.mass_loss_rate_blowout
                        + smol_res.mass_loss_rate_sinks
                        + smol_res.mass_loss_rate_sublimation
                    )
                    smol_gain_mass_rate = smol_res.gain_mass_rate
                    smol_loss_mass_rate = smol_res.loss_mass_rate
                    smol_sink_mass_rate = smol_res.sink_mass_rate
                    smol_source_mass_rate = smol_res.source_mass_rate
                    budget_dt = smol_dt_eff if smol_dt_eff and smol_dt_eff > 0.0 else dt
                    smol_mass_budget_delta = (
                        smol_sigma_after + budget_dt * smol_extra_mass_loss_rate
                        - (smol_sigma_before + budget_dt * smol_prod_mass_rate)
                    )
                    energy_columns = {}
                    if smol_res.energy_stats is not None:
                        stats_vec = smol_res.energy_stats
                        energy_columns = {
                            "E_rel_step": float(stats_vec[0]),
                            "E_dissipated_step": float(stats_vec[1]),
                            "E_retained_step": float(stats_vec[2]),
                            "f_ke_mean": float(stats_vec[3]),
                            "f_ke_energy": float(stats_vec[4]),
                            "F_lf_mean": float(stats_vec[5]),
                            "n_cratering": float(stats_vec[6]),
                            "n_fragmentation": float(stats_vec[7]),
                            "frac_cratering": float(stats_vec[8]),
                            "frac_fragmentation": float(stats_vec[9]),
                            "f_ke_eps_mismatch": float(smol_res.f_ke_eps_mismatch)
                            if smol_res.f_ke_eps_mismatch is not None
                            else 0.0,
                        }
                else:
                    prod_rate_last = prod_rate
                    total_prod_surface = prod_rate * dt
                    sink_step = surface.step_surface_sink_only(
                        sigma_surf,
                        prod_rate,
                        dt,
                        t_sink=t_sink_current,
                    )
                    sigma_surf = sink_step.sigma_surf
                    outflux_surface = 0.0
                    sink_flux_surface = sink_step.sink_flux
                    total_sink_surface = sink_flux_surface * dt
                    sigma_loss_smol = 0.0
                    mass_loss_rate_sublimation_smol = 0.0
                    mass_loss_sublimation_smol_step = 0.0
                    mass_err_percent_step = 0.0
                    fast_factor_numer = fast_blowout_factor_sub * dt
                    fast_factor_denom = dt
                time_sub = time_start + dt
            else:
                time_sub = time_start + dt
                tau_los_last = kappa_surf * sigma_surf * los_factor
                sigma_tau1_limit = None
                kappa_eff = kappa_surf
                sigma_tau1_active_last = None
            surface_update = physics_step.SurfaceUpdateResult(
                sigma_surf=sigma_surf,
                outflux_surface=outflux_surface,
                sink_flux_surface=sink_flux_surface,
                t_blow=t_blow_step,
                t_coll=t_coll_kernel_last,
                prod_rate_effective=prod_rate_last,
                mass_error=mass_err_percent_step / 100.0 if mass_err_percent_step is not None else 0.0,
            )
            sigma_surf = surface_update.sigma_surf
            outflux_surface = surface_update.outflux_surface
            sink_flux_surface = surface_update.sink_flux_surface
            prod_rate_last = surface_update.prod_rate_effective

        if sink_timescale_active:
            t_sink_step = t_sink_step_effective
        else:
            t_sink_step = None

        time = time_sub
        if dt > 0.0:
            prod_rate_diverted_current = diverted_mass_step / dt
            deep_to_surf_flux_current = deep_to_surf_mass_step / dt
            prod_rate_into_deep_current = prod_into_deep_mass_step / dt
            deep_to_surf_flux_attempt_current = deep_to_surf_attempt_mass_step / dt
        if sublimation_smol_active_step and collision_solver_mode != "smol":
            # Sublimation-to-Smol path: gated by phase and sigma_surf>0 to avoid
            # changing the existing surface sink semantics.
            sizes_arr, widths_arr, m_k, N_k, scale_to_sigma = smol.psd_state_to_number_density(
                psd_state,
                sigma_surf,
                rho_fallback=rho_used,
            )
            if N_k.size and sigma_surf > 0.0:
                ds_dt_fill = ds_dt_val if ds_dt_val is not None else 0.0
                S_sub_k, mass_loss_rate_sub = sublimation_sink_from_dsdt(
                    sizes_arr,
                    N_k,
                    ds_dt_fill,
                    m_k,
                )
                mass_loss_rate_sublimation_smol = mass_loss_rate_sub
                if np.any(S_sub_k):
                    n_bins_smol = sizes_arr.size
                    smol_sink_workspace = _get_smol_sink_workspace(smol_sink_workspace, n_bins_smol)
                    N_new_smol, _smol_dt_eff, _smol_mass_err = smol.step_imex_bdf1_C3(
                        N_k,
                        smol_sink_workspace.zeros_kernel,
                        smol_sink_workspace.zeros_frag,
                        smol_sink_workspace.zeros_source,
                        m_k,
                        prod_subblow_mass_rate=0.0,
                        dt=dt,
                        S_external_k=None,
                        S_sublimation_k=S_sub_k,
                        extra_mass_loss_rate=mass_loss_rate_sub,
                        workspace=smol_sink_workspace.imex,
                    )
                    sigma_before_smol = sigma_surf
                    psd_state, sigma_after_smol, sigma_loss_smol = smol.number_density_to_psd_state(
                        N_new_smol,
                        psd_state,
                        sigma_before_smol,
                        widths=widths_arr,
                        m=m_k,
                        scale_to_sigma=scale_to_sigma,
                    )
                    sigma_surf = sigma_after_smol
                    sigma_loss_smol = max(sigma_loss_smol, 0.0)
                    mass_loss_sublimation_smol_step = sigma_loss_smol * area / constants.M_MARS
                    if sigma_loss_smol > 0.0 and dt > 0.0:
                        mass_loss_rate_sublimation_smol = sigma_loss_smol / dt
                    if mass_loss_sublimation_smol_step > 0.0:
                        M_sink_cum += mass_loss_sublimation_smol_step
                        M_sublimation_cum += mass_loss_sublimation_smol_step
        if freeze_sigma:
            sigma_surf = sigma_surf_reference

        if blowout_gate_mode == "sublimation_competition":
            if (
                ds_dt_val < 0.0
                and math.isfinite(ds_dt_val)
                and math.isfinite(s_min_effective)
            ):
                candidate = s_min_effective / abs(ds_dt_val)
                if candidate > 0.0 and math.isfinite(candidate):
                    t_solid_step = candidate
        elif blowout_gate_mode == "collision_competition":
            if tau_los_last is not None and tau_los_last > TAU_MIN and Omega_step > 0.0:
                tau_vert = float(tau_los_last) / max(los_factor, 1.0)
                if tau_vert > TAU_MIN:
                    candidate = 1.0 / (Omega_step * tau_vert)
                    if candidate > 0.0 and math.isfinite(candidate):
                        t_solid_step = candidate
        if gate_enabled and enable_blowout_step:
            gate_factor = _compute_gate_factor(t_blow_step, t_solid_step)

        if collisions_active_step:
            loss_total_surface = sigma_before_step + total_prod_surface - sigma_surf
            loss_total_surface = max(loss_total_surface, 0.0)
            if (
                collision_solver_mode == "smol"
                and smol_dt_eff is not None
                and smol_dt_eff > 0.0
                and smol_dt_eff < dt
            ):
                dt_smol = smol_dt_eff
                blow_surface_total = max(outflux_surface, 0.0) * dt_smol
                sink_surface_total = max(sink_flux_surface, 0.0) * dt_smol
                loss_total_surface = blow_surface_total + sink_surface_total
            elif collision_solver_mode == "smol" and dt > 0.0:
                sink_rate = max(total_sink_surface / dt, 0.0)
                blow_rate = max(outflux_surface, 0.0)
                rate_total = blow_rate + sink_rate
                if rate_total > 0.0:
                    blow_surface_total = loss_total_surface * (blow_rate / rate_total)
                    sink_surface_total = loss_total_surface - blow_surface_total
                else:
                    sink_surface_total = max(total_sink_surface, 0.0)
                    blow_surface_total = max(loss_total_surface - sink_surface_total, 0.0)
            else:
                sink_surface_total = max(total_sink_surface, 0.0)
                blow_surface_total = max(loss_total_surface - sink_surface_total, 0.0)
            if not enable_blowout_step:
                blow_surface_total = 0.0
        else:
            loss_total_surface = sigma_before_step + total_prod_surface - sigma_surf
            loss_total_surface = max(loss_total_surface, 0.0)
            sink_surface_total = max(total_sink_surface, 0.0)
            blow_surface_total = 0.0

        if sigma_loss_sublimation_blow > 0.0:
            blow_surface_total += sigma_loss_sublimation_blow
            if dt > 0.0:
                outflux_surface += sigma_loss_sublimation_blow / dt

        blow_surface_total, outflux_surface = _apply_blowout_gate(
            blow_surface_total,
            outflux_surface,
            enable_blowout=enable_blowout_step,
            gate_enabled=gate_enabled,
            gate_factor=gate_factor,
        )

        t_solid_track.append(float(t_solid_step) if t_solid_step is not None else float("nan"))
        gate_factor_track.append(float(gate_factor))

        sink_mass_total = sink_surface_total * area / constants.M_MARS
        sink_mass_total_effective = sink_mass_total
        if collision_solver_mode == "smol":
            sink_mass_total_effective = max(
                sink_mass_total - mass_loss_sublimation_smol_step, 0.0
            )
        blow_mass_total = blow_surface_total * area / constants.M_MARS
        mass_loss_surface_solid_step = blow_mass_total
        if collisions_active_step:
            M_loss_cum += blow_mass_total
        M_sink_cum += sink_mass_total_effective
        if mass_loss_spill_step > 0.0:
            M_spill_cum += mass_loss_spill_step
        if sink_timescale_active and sink_result.sublimation_fraction > 0.0:
            M_sublimation_cum += sink_mass_total * sink_result.sublimation_fraction
        M_hydro_cum += hydro_mass_total
        if collision_solver_mode == "smol" and mass_loss_sublimation_smol_step > 0.0:
            M_sink_cum += mass_loss_sublimation_smol_step
            M_sublimation_cum += mass_loss_sublimation_smol_step

        mass_loss_sublimation_step_total = mass_loss_sublimation_step + mass_loss_sublimation_smol_step
        mass_loss_sinks_step_total = (
            mass_loss_sublimation_step_total + sink_mass_total_effective
        )
        mass_loss_hydro_step = hydro_mass_total
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
        if collision_solver_mode == "smol":
            sink_mass_rate_kg = max(
                sink_mass_rate_kg - mass_loss_rate_sublimation_smol * area, 0.0
            )
        sink_mass_rate_kg_total = sink_mass_rate_kg
        if dt > 0.0:
            sink_mass_rate_kg_total += mass_loss_sublimation_step * constants.M_MARS / dt
            sink_mass_rate_kg_total += mass_loss_rate_sublimation_smol * area
        M_out_dot = outflux_mass_rate_kg / constants.M_MARS
        M_sink_dot = sink_mass_rate_kg_total / constants.M_MARS
        dM_dt_surface_total = M_out_dot + M_sink_dot
        dSigma_dt_blowout = outflux_surface
        sink_flux_nosub = max(sink_flux_surface - mass_loss_rate_sublimation_smol, 0.0)
        dSigma_dt_sinks = sink_flux_nosub + dSigma_dt_sublimation + mass_loss_rate_sublimation_smol
        dSigma_dt_total = dSigma_dt_blowout + dSigma_dt_sinks
        dt_over_t_blow = fast_blowout_ratio
        if math.isfinite(dt_over_t_blow):
            dt_over_t_blow_values.append(float(dt_over_t_blow))
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
        dSigma_dt_sublimation_total = dSigma_dt_sublimation + mass_loss_rate_sublimation_smol
        sigma_loss_total_sub = delta_sigma_sub + sigma_loss_smol
        mass_loss_sublimation_step_diag = mass_loss_sublimation_step_total

        if energy_columns:
            energy_row = {"time": float(time), **energy_columns}
            E_rel = energy_columns.get("E_rel_step", 0.0)
            E_diss = energy_columns.get("E_dissipated_step", 0.0)
            E_ret = energy_columns.get("E_retained_step", 0.0)
            denom_E = E_rel if E_rel != 0.0 else 1.0
            E_err = abs(E_diss + E_ret - E_rel) / abs(denom_E)
            warn_thresh = 1.0e-12
            err_thresh = 1.0e-6
            if E_err > err_thresh:
                err_flag = "error"
            elif E_err > warn_thresh:
                err_flag = "warning"
            else:
                err_flag = "ok"
            energy_sum_rel += float(E_rel)
            energy_sum_diss += float(E_diss)
            energy_sum_ret += float(E_ret)
            energy_last_row = dict(energy_row)
            energy_count += 1
            energy_budget_row = {
                "step": step_no,
                "time": float(time),
                "dt": float(dt),
                "E_rel_step": float(E_rel),
                "E_dissipated_step": float(E_diss),
                "E_retained_step": float(E_ret),
                "f_ke_mean": float(energy_columns.get("f_ke_mean", 0.0)),
                "F_lf_mean": float(energy_columns.get("F_lf_mean", 0.0)),
                "n_cratering": float(energy_columns.get("n_cratering", 0.0)),
                "n_fragmentation": float(energy_columns.get("n_fragmentation", 0.0)),
                "frac_cratering": float(energy_columns.get("frac_cratering", 0.0)),
                "frac_fragmentation": float(energy_columns.get("frac_fragmentation", 0.0)),
                "eps_restitution": float(getattr(cfg.dynamics, "eps_restitution", 0.5)),
                "f_ke_eps_mismatch": float(energy_columns.get("f_ke_eps_mismatch", 0.0)),
                "E_numerical_error_relative": float(E_err),
                "error_flag": err_flag,
            }
            if energy_streaming_enabled:
                writer.append_csv(
                    [energy_row],
                    energy_series_path,
                    header=not energy_series_path.exists(),
                )
                writer.append_csv(
                    [energy_budget_row],
                    energy_budget_path,
                    header=not energy_budget_path.exists(),
                )
            else:
                energy_series.append(energy_row)
                energy_budget.append(energy_budget_row)

        orbit_time_accum += dt
        orbit_loss_blow += blow_mass_total
        orbit_loss_sink += mass_loss_sinks_step_total
        if orbit_rollup_enabled and t_orb_step > 0.0:
            while orbit_time_accum >= t_orb_step and orbit_time_accum > 0.0:
                orbit_time_accum_before = orbit_time_accum
                fraction = t_orb_step / orbit_time_accum_before
                M_orbit_blow = orbit_loss_blow * fraction
                M_orbit_sink = orbit_loss_sink * fraction
                orbits_completed += 1
                mass_loss_frac = float("nan")
                if cfg.initial.mass_total > 0.0:
                    mass_loss_frac = (M_orbit_blow + M_orbit_sink) / cfg.initial.mass_total
                time_s_end = time - max(orbit_time_accum_before - t_orb_step, 0.0)
                orbit_rollup_rows.append(
                    {
                        "orbit_index": orbits_completed,
                        "time_s": time,
                        "time_s_end": time_s_end,
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
                    "ds_dt_sublimation_raw_m_s": ds_dt_raw,
                    "sigma_loss_sublimation_kg_m2": sigma_loss_total_sub,
                    "M_loss_components_Mmars": {
                        "blowout": M_loss_cum,
                        "blowout_surface_solid_marsRP": M_loss_cum,
                        "sinks": M_sink_cum,
                        "total": M_loss_cum + M_sink_cum,
                    },
                    "phase_state": phase_state_last,
                    "phase_method": phase_method_last,
                    "phase_reason": phase_reason_last,
                    "phase_f_vap": phase_f_vap_last,
                    "phase_bulk_state": phase_bulk_state_last,
                    "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
                    "phase_bulk_f_solid": phase_bulk_f_solid_last,
                    "tau_mars_line_of_sight": tau_los_last,
                    "tau_gate_blocked": tau_gate_block_last,
                    "sink_selected": sink_selected_last,
                    "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
                    "hydro_timescale_s": _safe_float(hydro_timescale_last),
                    "mass_loss_hydro_step": mass_loss_hydro_step,
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
        sigma_diag = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_eff_diag = None
        if kappa_eff is not None and math.isfinite(kappa_eff):
            tau_eff_diag = kappa_eff * sigma_diag
        if (
            optical_depth_enabled
            and optical_tau_stop is not None
            and phase_state_last == "solid"
        ):
            kappa_for_stop = kappa_eff if kappa_eff is not None and math.isfinite(kappa_eff) else kappa_surf
            tau_stop_los_current = float(kappa_for_stop * sigma_surf * los_factor)
            if math.isfinite(tau_stop_los_current) and tau_stop_los_current > optical_tau_stop * (
                1.0 + float(optical_tau_stop_tol or 0.0)
            ):
                stop_after_record = True
                tau_stop_los_value = tau_stop_los_current
        if supply_headroom_enabled and sigma_tau1_limit is not None and math.isfinite(sigma_tau1_limit):
            headroom_current = float(max(sigma_tau1_limit - min(sigma_diag, sigma_tau1_limit), 0.0))
        else:
            headroom_current = None
        if supply_rate_scaled_current is None and supply_diag_last is not None:
            supply_rate_scaled_current = supply_diag_last.rate
        if supply_rate_nominal_current is None and supply_diag_last is not None:
            supply_rate_nominal_current = supply_diag_last.mixed_rate
        if supply_rate_applied_current is None:
            supply_rate_applied_current = _safe_float(prod_rate_last)
        else:
            supply_rate_applied_current = _safe_float(supply_rate_applied_current)
        if prod_rate_raw_current is None and supply_diag_last is not None:
            prod_rate_raw_current = _safe_float(supply_diag_last.rate)
        if (
            supply_rate_applied_current is not None
            and supply_rate_scaled_current is not None
            and supply_rate_scaled_current > 0.0
        ):
            clip_factor_current = float(
                max(supply_rate_applied_current, 0.0) / max(supply_rate_scaled_current, 1.0e-30)
            )
        visibility_factor_current = None
        if prod_rate_raw_current is not None:
            visibility_factor_current = float(
                max(supply_rate_applied_current if supply_rate_applied_current is not None else 0.0, 0.0)
                / max(prod_rate_raw_current, supply_visibility_eps)
            )
        supply_blocked_by_headroom_flag = bool(
            supply_headroom_enabled
            and prod_rate_raw_current is not None
            and prod_rate_raw_current > 0.0
            and headroom_current is not None
            and headroom_current <= supply_headroom_eps
            and (supply_rate_applied_current is None or supply_rate_applied_current <= supply_visibility_eps)
        )
        supply_mixing_limited_flag = bool(
            supply_transport_mode == "deep_mixing"
            and prod_rate_raw_current is not None
            and prod_rate_raw_current > 0.0
            and not supply_blocked_by_headroom_flag
            and (supply_rate_applied_current is None or supply_rate_applied_current <= supply_visibility_eps)
        )
        supply_rate_nominal_track.append(_safe_float(supply_rate_nominal_current))
        supply_rate_scaled_track.append(_safe_float(supply_rate_scaled_current))
        supply_rate_applied_track.append(_safe_float(supply_rate_applied_current))
        supply_headroom_track.append(_safe_float(headroom_current))
        supply_clip_factor_track.append(_safe_float(clip_factor_current))
        supply_spill_rate_track.append(_safe_float(spill_rate_current))
        supply_visibility_track.append(_safe_float(visibility_factor_current))
        supply_blocked_track.append(bool(supply_blocked_by_headroom_flag))
        supply_mixing_block_track.append(bool(supply_mixing_limited_flag))
        clip_blocked = supply_blocked_by_headroom_flag or supply_mixing_limited_flag
        clip_reason = "mixing" if supply_mixing_limited_flag and not supply_blocked_by_headroom_flag else "headroom"
        if clip_blocked and dt > 0.0:
            supply_clip_time += dt
            supply_clip_streak += 1
            if supply_clip_streak == supply_clip_warn_threshold:
                def _clip_fmt(val: Optional[float]) -> float:
                    try:
                        v = float(val)
                        return v if math.isfinite(v) else float("nan")
                    except Exception:
                        return float("nan")

                temp_scale_warn = supply_diag_last.temperature_scale if supply_diag_last else None
                feedback_scale_warn = supply_diag_last.feedback_scale if supply_diag_last else None
                supply_clip_events.append(
                    {
                        "time": float(time),
                        "Sigma_surf": _clip_fmt(sigma_diag),
                        "Sigma_tau1": _clip_fmt(sigma_tau1_limit),
                        "headroom": _clip_fmt(headroom_current),
                        "supply_scaled": _clip_fmt(supply_rate_scaled_current),
                        "supply_visibility_factor": _clip_fmt(visibility_factor_current),
                        "temperature_scale": _clip_fmt(temp_scale_warn),
                        "feedback_scale": _clip_fmt(feedback_scale_warn),
                        "sigma_deep": _clip_fmt(sigma_deep),
                        "prod_rate_diverted": _clip_fmt(prod_rate_diverted_current),
                        "prod_rate_raw": _clip_fmt(prod_rate_raw_current),
                        "prod_rate_applied": _clip_fmt(supply_rate_applied_current),
                        "prod_rate_into_deep": _clip_fmt(prod_rate_into_deep_current),
                        "deep_to_surf_flux_attempt": _clip_fmt(deep_to_surf_flux_attempt_current),
                        "deep_to_surf_flux_applied": _clip_fmt(deep_to_surf_flux_current),
                        "sigma_deep_before": _clip_fmt(sigma_deep_before),
                        "reason": clip_reason,
                        "transport_mode": supply_transport_mode,
                    }
                )
        else:
            supply_clip_streak = 0
        t_coll_step = _resolve_t_coll_step(
            collision_solver_mode=collision_solver_mode,
            collisions_active=collisions_active_step,
            tau_los_last=tau_los_last,
            los_factor=los_factor,
            Omega=Omega_step,
            t_coll_kernel_last=t_coll_kernel_last,
        )
        ts_ratio_value = None
        if (
            t_coll_step is not None
            and t_coll_step > 0.0
            and t_blow_step is not None
            and t_blow_step > 0.0
            and math.isfinite(t_blow_step)
        ):
            ts_ratio_value = float(t_blow_step / t_coll_step)
        tau_record = tau_los_last
        if tau_record is None:
            tau_record = float(kappa_surf * sigma_surf * los_factor)
        # Force optional numeric/string fields to concrete types to stabilise streaming chunk schemas.
        _series_optional_float_keys = {
            "t_coll",
            "ts_ratio",
            "Sigma_surf0",
            "Sigma_tau1",
            "Sigma_tau1_active",
            "sigma_tau1",
            "Sigma_tau1_last_finite",
            "tau_phase_los",
            "tau_phase_used",
            "t_solid_s",
            "prod_subblow_area_rate_raw",
            "dotSigma_prod",
            "mu_orbit10pct",
            "epsilon_mix",
            "prod_rate_raw",
            "supply_rate_nominal",
            "supply_rate_scaled",
            "supply_headroom",
            "headroom",
            "supply_clip_factor",
            "supply_visibility_factor",
            "supply_temperature_scale",
            "supply_temperature_value",
            "supply_feedback_scale",
            "supply_feedback_error",
            "supply_reservoir_remaining_Mmars",
            "supply_reservoir_fraction",
            "phi_effective",
            "phi_used",
            "kappa_eff",
            "kappa_surf",
            "phase_f_vap",
            "phase_bulk_f_liquid",
            "phase_bulk_f_solid",
            "phase_bulk_f_vapor",
            "M_sink_cum",
            "e_kernel_used",
            "i_kernel_used",
            "e_kernel_base",
            "i_kernel_base",
            "e_kernel_supply",
            "i_kernel_supply",
            "e_kernel_effective",
            "i_kernel_effective",
            "supply_velocity_weight_w",
            "s_min_surface_energy",
            "e_state_next",
            "i_state_next",
            "t_damp_collisions",
            "e_eq_target",
        }
        _series_optional_string_keys = {
            "phase_tau_field",
            "phase_temperature_input",
            "supply_transport_mode",
            "tau_phase_used",
            "case_status",
            "T_M_source",
            "T_source",
            "phase_state",
            "phase_method",
            "phase_reason",
            "phase_bulk_state",
            "blowout_layer_mode",
            "blowout_target_phase",
            "sink_selected",
            "supply_temperature_value_kind",
        }

        record = {
            "time": time,
            "dt": dt,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "t_coll": t_coll_step,
            "ts_ratio": ts_ratio_value,
            "r_m": r,
            "r_RM": r_RM,
            "r_orbit_RM": r_RM,
            "r_source": r_source,
            "T_M_used": T_use,
            "T_M_source": T_M_source,
            "T_p_effective": T_p_effective,
            "phase_temperature_input": phase_temperature_input_mode,
            "rad_flux_Mars": rad_flux_step,
            "dt_over_t_blow": dt_over_t_blow,
            "tau": tau_record,
            "tau_los_mars": tau_record,
            "a_blow_step": a_blow_step,
            "a_blow": a_blow_step,
            "a_blow_at_smin": a_blow_step,
            "s_min": s_min_effective,
            "s_min_surface_energy": s_min_surface_energy,
            "kappa": kappa_eff,
            "kappa_eff": kappa_eff,
            "kappa_surf": kappa_surf,
            "Qpr_mean": qpr_mean_step,
            "Q_pr_at_smin": qpr_mean_step,
            "beta_at_smin_config": beta_at_smin_config,
            "beta_at_smin_effective": beta_at_smin_effective,
            "beta_at_smin": beta_at_smin_effective,
            "beta_threshold": beta_threshold,
            "Sigma_surf": sigma_surf,
            "sigma_surf": sigma_surf,
            "Sigma_surf0": sigma_surf0_target,
            "Sigma_tau1": sigma_tau1_limit,
            "Sigma_tau1_active": sigma_tau1_active_last,
            "sigma_tau1": sigma_tau1_limit,
            "Sigma_tau1_last_finite": sigma_tau1_limit_last_finite,
            "tau_phase_los": tau_phase_los_last,
            "tau_phase_used": tau_phase_used_last,
            "phase_tau_field": phase_tau_field,
            "sigma_deep": sigma_deep,
            "headroom": _safe_float(headroom_current),
            "outflux_surface": outflux_surface,
            "t_solid_s": t_solid_step,
            "blowout_gate_factor": gate_factor,
            "sink_flux_surface": sink_flux_surface,
            "t_blow": t_blow_step,
            "prod_subblow_area_rate": prod_rate_last,
            "prod_subblow_area_rate_raw": supply_diag_last.raw_rate if supply_diag_last else None,
            "dotSigma_prod": _safe_float(supply_rate_scaled_current),
            "mu_orbit10pct": supply_mu_orbit_cfg,
            "epsilon_mix": supply_epsilon_mix,
            "prod_rate_raw": _safe_float(prod_rate_raw_current),
            "prod_rate_applied_to_surf": _safe_float(supply_rate_applied_current),
            "prod_rate_diverted_to_deep": _safe_float(prod_rate_diverted_current),
            "prod_rate_into_deep": _safe_float(prod_rate_into_deep_current),
            "deep_to_surf_flux_attempt": _safe_float(deep_to_surf_flux_attempt_current),
            "deep_to_surf_flux": _safe_float(deep_to_surf_flux_current),
            "deep_to_surf_flux_applied": _safe_float(deep_to_surf_flux_current),
            "supply_rate_nominal": _safe_float(supply_rate_nominal_current),
            "supply_rate_scaled": _safe_float(supply_rate_scaled_current),
            "supply_rate_applied": _safe_float(supply_rate_applied_current),
            "supply_tau_clip_spill_rate": _safe_float(spill_rate_current),
            "supply_headroom": _safe_float(headroom_current),
            "supply_clip_factor": _safe_float(clip_factor_current),
            "supply_visibility_factor": _safe_float(visibility_factor_current),
            "supply_blocked_by_headroom": bool(supply_blocked_by_headroom_flag),
            "supply_mixing_limited": bool(supply_mixing_limited_flag),
            "supply_transport_mode": supply_transport_mode,
            "e_kernel_used": _safe_float(e_kernel_step),
            "i_kernel_used": _safe_float(i_kernel_step),
            "e_kernel_base": _safe_float(e_kernel_base_step),
            "i_kernel_base": _safe_float(i_kernel_base_step),
            "e_kernel_supply": _safe_float(e_kernel_supply_step),
            "i_kernel_supply": _safe_float(i_kernel_supply_step),
            "e_kernel_effective": _safe_float(e_kernel_step),
            "i_kernel_effective": _safe_float(i_kernel_step),
            "e_state_next": _safe_float(e_state_next_step),
            "i_state_next": _safe_float(i_state_next_step),
            "t_damp_collisions": _safe_float(t_damp_applied_step),
            "e_eq_target": _safe_float(e_damp_target_step),
            "supply_velocity_weight_w": _safe_float(supply_velocity_weight_step),
            "supply_temperature_scale": supply_diag_last.temperature_scale if supply_diag_last else None,
            "supply_temperature_value": supply_diag_last.temperature_value if supply_diag_last else None,
            "supply_temperature_value_kind": supply_diag_last.temperature_value_kind if supply_diag_last else None,
            "supply_feedback_scale": supply_diag_last.feedback_scale if supply_diag_last else None,
            "supply_feedback_error": supply_diag_last.feedback_error if supply_diag_last else None,
            "supply_reservoir_remaining_Mmars": supply_diag_last.reservoir_remaining_Mmars if supply_diag_last else None,
            "supply_reservoir_fraction": supply_diag_last.reservoir_fraction if supply_diag_last else None,
            "supply_reservoir_clipped": bool(supply_diag_last.clipped_by_reservoir) if supply_diag_last else False,
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
            "dSigma_dt_sublimation": dSigma_dt_sublimation_total,
            "M_loss_cum": M_loss_cum + M_sink_cum,
            "mass_total_bins": cfg.initial.mass_total - (M_loss_cum + M_sink_cum),
            "mass_lost_by_blowout": M_loss_cum,
            "mass_lost_by_sinks": M_sink_cum,
            "M_sink_cum": M_sink_cum,
            "mass_lost_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_sublimation_step": mass_loss_sublimation_step_diag,
            "mass_lost_hydro_step": mass_loss_hydro_step,
            "mass_lost_tau_clip_spill_step": mass_loss_spill_step,
            "cum_mass_lost_tau_clip_spill": M_spill_cum,
            "mass_lost_surface_solid_marsRP_step": mass_loss_surface_solid_step,
            "M_loss_rp_mars": M_loss_cum,
            "M_loss_surface_solid_marsRP": M_loss_cum,
            "M_loss_hydro": M_hydro_cum,
            "fast_blowout_factor": fast_blowout_factor_record,
            "fast_blowout_corrected": fast_blowout_applied,
            "fast_blowout_flag_gt3": fast_blowout_flag,
            "fast_blowout_flag_gt10": fast_blowout_flag_strict,
            "fast_blowout_ratio": fast_blowout_ratio_alias,
            "n_substeps": int(n_substeps),
            "substep_active": bool(substep_active),
            "chi_blow_eff": chi_blow_eff,
            "case_status": case_status,
            "s_blow_m": a_blow_step,
            "s_blow_m_effective": a_blow_effective_step,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean_step,
            "Q_pr_blow": qpr_for_blow_step,
            "s_min_effective": s_min_effective,
            "s_min_config": s_min_config,
            "s_min_effective_gt_config": s_min_effective > s_min_config,
            "T_source": T_M_source,
            "T_M_used": T_use,
            "ds_dt_sublimation": ds_dt_val,
            "ds_dt_sublimation_raw": ds_dt_raw,
            "phi_effective": phi_effective_last,
            "phi_used": phi_effective_last,
            "e_kernel_used": _safe_float(e_kernel_step),
            "i_kernel_used": _safe_float(i_kernel_step),
            "e_kernel_base": _safe_float(e_kernel_base_step),
            "i_kernel_base": _safe_float(i_kernel_base_step),
            "e_kernel_supply": _safe_float(e_kernel_supply_step),
            "i_kernel_supply": _safe_float(i_kernel_supply_step),
            "e_kernel_effective": _safe_float(e_kernel_step),
            "i_kernel_effective": _safe_float(i_kernel_step),
            "supply_velocity_weight_w": _safe_float(supply_velocity_weight_step),
            "phase_state": phase_state_last,
            "phase_f_vap": phase_f_vap_last,
            "phase_method": phase_method_last,
            "phase_reason": phase_reason_last,
            "phase_bulk_state": phase_bulk_state_last,
            "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
            "phase_bulk_f_solid": phase_bulk_f_solid_last,
            "phase_bulk_f_vapor": phase_bulk_f_vapor_last,
            "tau_mars_line_of_sight": tau_los_last,
            "tau_gate_blocked": tau_gate_block_last,
            "blowout_beta_gate": beta_gate_last,
            "blowout_phase_allowed": phase_allows_last,
            "blowout_layer_mode": blowout_layer_mode,
            "blowout_target_phase": blowout_target_phase,
            "sink_selected": sink_selected_last,
            "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
        }
        if "energy_columns" in locals():
            record.update(energy_columns)
        for key in _series_optional_float_keys:
            if key in record:
                record[key] = _float_or_nan(record.get(key))
        for key in _series_optional_string_keys:
            if key in record:
                val = record.get(key)
                record[key] = "" if val is None else str(val)
        if extended_diag_enabled:
            record.update(
                {
                    "mloss_blowout_rate": M_out_dot,
                    "mloss_sink_rate": M_sink_dot,
                    "mloss_total_rate": dM_dt_surface_total,
                    "cum_mloss_blowout": M_loss_cum,
                    "cum_mloss_sink": M_sink_cum,
                    "cum_mloss_total": M_loss_cum + M_sink_cum,
                    "beta_eff": beta_at_smin_effective,
                    "kappa_eff": kappa_eff,
                    "tau_eff": tau_eff_diag,
                }
            )
            extended_total_rate_track.append(dM_dt_surface_total)
            extended_total_rate_time_track.append(time)
            if ts_ratio_value is not None and math.isfinite(ts_ratio_value):
                extended_ts_ratio_track.append(ts_ratio_value)
        if evolve_min_size_enabled:
            record["s_min_evolved"] = s_min_evolved_value
        if supply_diag_last is not None:
            if math.isfinite(supply_diag_last.feedback_scale):
                supply_feedback_track.append(float(supply_diag_last.feedback_scale))
            if math.isfinite(supply_diag_last.temperature_scale):
                supply_temperature_scale_track.append(float(supply_diag_last.temperature_scale))
            if supply_diag_last.reservoir_remaining_Mmars is not None:
                supply_reservoir_remaining_track.append(float(supply_diag_last.reservoir_remaining_Mmars))
        records.append(record)

        if psd_history_enabled and (psd_history_stride <= 1 or step_no % psd_history_stride == 0):
            try:
                sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
                widths_arr = np.asarray(psd_state.get("widths"), dtype=float)
                number_arr = np.asarray(psd_state.get("number"), dtype=float)
            except Exception:
                sizes_arr = np.empty(0, dtype=float)
                widths_arr = np.empty(0, dtype=float)
                number_arr = np.empty(0, dtype=float)
            if sizes_arr.size and number_arr.size == sizes_arr.size and widths_arr.size == sizes_arr.size:
                mass_weight_bins = number_arr * (sizes_arr ** 3) * widths_arr
                mass_weight_total = float(np.sum(mass_weight_bins))
                if not math.isfinite(mass_weight_total) or mass_weight_total <= 0.0:
                    mass_frac = np.zeros_like(mass_weight_bins)
                else:
                    mass_frac = mass_weight_bins / mass_weight_total
                for idx, (size_val, number_val, f_mass_val) in enumerate(zip(sizes_arr, number_arr, mass_frac)):
                    psd_hist_records.append(
                        {
                            "time": time,
                            "bin_index": int(idx),
                            "s_bin_center": float(size_val),
                            "N_bin": float(number_val),
                            "Sigma_bin": float(f_mass_val * sigma_surf),
                            "f_mass": float(f_mass_val),
                            "Sigma_surf": sigma_surf,
                        }
                    )

        F_abs_geom = constants.SIGMA_SB * (T_use**4) * (constants.R_MARS / r) ** 2
        phi_effective_diag = phi_effective_last
        if phi_effective_diag is None and kappa_surf > 0.0:
            phi_effective_diag = kappa_eff / kappa_surf

        s_peak_value = _psd_mass_peak()
        F_abs_qpr = F_abs_geom * qpr_mean_step
        tau_los_diag = tau_los_last if tau_los_last is not None else tau_record
        _diag_optional_float_keys = {
            "sigma_tau1",
            "sigma_tau1_active",
            "Sigma_tau1_last_finite",
            "tau_phase_los",
            "tau_phase_used",
            "t_sink_total_s",
            "t_sink_surface_s",
            "t_sink_sublimation_s",
            "t_sink_gas_drag_s",
            "prod_subblow_area_rate_raw",
            "supply_rate_nominal",
            "supply_rate_scaled",
            "supply_tau_clip_spill_rate",
            "supply_headroom",
            "headroom",
            "supply_clip_factor",
            "prod_rate_raw",
            "prod_rate_applied_to_surf",
            "prod_rate_diverted_to_deep",
            "prod_rate_into_deep",
            "deep_to_surf_flux_attempt",
            "deep_to_surf_flux",
            "deep_to_surf_flux_applied",
            "supply_temperature_scale",
            "supply_temperature_value",
            "supply_feedback_scale",
            "supply_feedback_error",
            "supply_reservoir_remaining_Mmars",
            "supply_reservoir_fraction",
            "s_min_effective",
            "phi_effective",
            "chi_blow_eff",
            "ds_step_uniform",
            "mass_ratio_uniform",
            "smol_dt_eff",
            "smol_sigma_before",
            "smol_sigma_after",
            "smol_sigma_loss",
            "smol_prod_mass_rate",
            "smol_extra_mass_loss_rate",
            "smol_mass_budget_delta",
            "smol_mass_error",
            "smol_gain_mass_rate",
            "smol_loss_mass_rate",
            "smol_sink_mass_rate",
            "smol_source_mass_rate",
            "hydro_timescale_s",
            "mass_loss_surface_solid_step",
            "ds_dt_sublimation",
            "ds_dt_sublimation_raw",
        }
        _diag_optional_string_keys = {
            "phase_tau_field",
            "phase_temperature_input",
            "tau_phase_used",
            "supply_transport_mode",
            "phase_state",
            "phase_method",
            "phase_reason",
            "phase_bulk_state",
            "supply_temperature_value_kind",
            "phase_payload",
        }

        diag_entry = {
            "time": time,
            "dt": dt,
            "dt_over_t_blow": dt_over_t_blow,
            "r_m_used": r,
            "r_RM_used": r_RM,
            "T_M_used": T_use,
            "T_p_effective": T_p_effective,
            "phase_temperature_input": phase_temperature_input_mode,
            "phase_temperature_used_K": temperature_for_phase,
            "rad_flux_Mars": rad_flux_step,
            "F_abs_geom": F_abs_geom,
            "F_abs_geom_qpr": F_abs_qpr,
            "F_abs": F_abs_qpr,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "t_solid_s": t_solid_step,
            "t_sink_total_s": _safe_float(t_sink_total_value),
            "t_sink_surface_s": float(t_sink_step) if t_sink_step is not None else None,
            "t_sink_sublimation_s": _safe_float(sink_result.components.get("sublimation")),
            "t_sink_gas_drag_s": _safe_float(sink_result.components.get("gas_drag")),
            "mass_loss_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_by_sinks": M_sink_cum,
            "mass_loss_sublimation_step": mass_loss_sublimation_step_diag,
            "sigma_tau1": sigma_tau1_limit,
            "sigma_tau1_active": sigma_tau1_active_last,
            "Sigma_tau1_last_finite": sigma_tau1_limit_last_finite,
            "tau_los_mars": tau_los_diag,
            "tau_phase_los": tau_phase_los_last,
            "tau_phase_used": tau_phase_used_last,
            "phase_tau_field": phase_tau_field,
            "kappa_eff": kappa_eff,
            "kappa_surf": kappa_surf,
            "phi_effective": phi_effective_diag,
            "psi_shield": phi_effective_diag,
            "sigma_surf": sigma_diag,
            "sigma_deep": sigma_deep,
            "kappa_Planck": kappa_surf,
            "tau_eff": tau_eff_diag,
            "s_min": s_min_effective,
            "a_blow_at_smin": a_blow_step,
            "beta_at_smin_effective": beta_at_smin_effective,
            "beta_at_smin": beta_at_smin_effective,
            "Q_pr_at_smin": qpr_mean_step,
            "s_peak": s_peak_value,
            "area_m2": area,
            "prod_subblow_area_rate": prod_rate_last,
            "prod_subblow_area_rate_raw": supply_diag_last.raw_rate if supply_diag_last else None,
            "supply_rate_nominal": _safe_float(supply_rate_nominal_current),
            "supply_rate_scaled": _safe_float(supply_rate_scaled_current),
            "supply_rate_applied": _safe_float(supply_rate_applied_current),
            "supply_tau_clip_spill_rate": _safe_float(spill_rate_current),
            "supply_headroom": _safe_float(headroom_current),
            "supply_clip_factor": _safe_float(clip_factor_current),
            "headroom": _safe_float(headroom_current),
            "prod_rate_raw": _safe_float(prod_rate_raw_current),
            "prod_rate_applied_to_surf": _safe_float(supply_rate_applied_current),
            "prod_rate_diverted_to_deep": _safe_float(prod_rate_diverted_current),
            "prod_rate_into_deep": _safe_float(prod_rate_into_deep_current),
            "deep_to_surf_flux_attempt": _safe_float(deep_to_surf_flux_attempt_current),
            "deep_to_surf_flux": _safe_float(deep_to_surf_flux_current),
            "deep_to_surf_flux_applied": _safe_float(deep_to_surf_flux_current),
            "supply_visibility_factor": _safe_float(visibility_factor_current),
            "supply_blocked_by_headroom": bool(supply_blocked_by_headroom_flag),
            "supply_mixing_limited": bool(supply_mixing_limited_flag),
            "supply_transport_mode": supply_transport_mode,
            "supply_temperature_scale": supply_diag_last.temperature_scale if supply_diag_last else None,
            "supply_temperature_value": supply_diag_last.temperature_value if supply_diag_last else None,
            "supply_temperature_value_kind": supply_diag_last.temperature_value_kind if supply_diag_last else None,
            "supply_feedback_scale": supply_diag_last.feedback_scale if supply_diag_last else None,
            "supply_feedback_error": supply_diag_last.feedback_error if supply_diag_last else None,
            "supply_reservoir_remaining_Mmars": supply_diag_last.reservoir_remaining_Mmars if supply_diag_last else None,
            "supply_reservoir_fraction": supply_diag_last.reservoir_fraction if supply_diag_last else None,
            "supply_reservoir_clipped": bool(supply_diag_last.clipped_by_reservoir) if supply_diag_last else False,
            "s_min_effective": s_min_effective,
            "qpr_mean": qpr_mean_step,
            "chi_blow_eff": chi_blow_eff,
            "ds_step_uniform": erosion_diag.get("ds_step"),
            "mass_ratio_uniform": erosion_diag.get("mass_ratio"),
            "M_out_cum": M_loss_cum,
            "M_sink_cum": M_sink_cum,
            "M_loss_cum": M_loss_cum + M_sink_cum,
            "cum_mass_lost_tau_clip_spill": M_spill_cum,
            "M_loss_surface_solid_marsRP": M_loss_cum,
            "M_hydro_cum": M_hydro_cum,
            "phase_state": phase_state_last,
            "phase_method": phase_method_last,
            "phase_reason": phase_reason_last,
            "phase_f_vap": phase_f_vap_last,
            "phase_bulk_state": phase_bulk_state_last,
            "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
            "phase_bulk_f_solid": phase_bulk_f_solid_last,
            "phase_bulk_f_vapor": phase_bulk_f_vapor_last,
            "phase_payload": phase_payload_last,
            "ds_dt_sublimation": ds_dt_val,
            "ds_dt_sublimation_raw": ds_dt_raw,
            "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
            "tau_mars_line_of_sight": tau_los_last,
            "tau_gate_blocked": tau_gate_block_last,
            "blowout_beta_gate": beta_gate_last,
            "blowout_phase_allowed": phase_allows_last,
            "blowout_layer_mode": blowout_layer_mode,
            "blowout_target_phase": blowout_target_phase,
            "sink_selected": sink_selected_last,
            "hydro_timescale_s": _safe_float(hydro_timescale_last),
            "mass_loss_surface_solid_step": mass_loss_surface_solid_step,
            "smol_dt_eff": smol_dt_eff,
            "smol_sigma_before": smol_sigma_before,
            "smol_sigma_after": smol_sigma_after,
            "smol_sigma_loss": smol_sigma_loss,
            "smol_prod_mass_rate": smol_prod_mass_rate,
            "smol_extra_mass_loss_rate": smol_extra_mass_loss_rate,
            "smol_mass_budget_delta": smol_mass_budget_delta,
            "smol_mass_error": smol_mass_error,
            "smol_gain_mass_rate": smol_gain_mass_rate,
            "smol_loss_mass_rate": smol_loss_mass_rate,
            "smol_sink_mass_rate": smol_sink_mass_rate,
            "smol_source_mass_rate": smol_source_mass_rate,
            "blowout_gate_factor": gate_factor,
        }
        for key in _diag_optional_float_keys:
            if key in diag_entry:
                diag_entry[key] = _float_or_nan(diag_entry.get(key))
        for key in _diag_optional_string_keys:
            if key in diag_entry:
                val = diag_entry.get(key)
                diag_entry[key] = "" if val is None else str(val)
        diagnostics.append(diag_entry)

        mass_initial = cfg.initial.mass_total
        mass_remaining = mass_initial - (M_loss_cum + M_sink_cum)
        mass_lost = M_loss_cum + M_sink_cum
        mass_diff = mass_initial - mass_remaining - mass_lost
        mass_diff_percent = 0.0
        if mass_initial != 0.0:
            mass_diff_percent = abs(mass_diff / mass_initial) * 100.0
        error_percent = mass_diff_percent
        if mass_err_percent_step is not None:
            error_percent = max(mass_err_percent_step, mass_diff_percent)
        mass_budget_max_error = max(mass_budget_max_error, error_percent)
        budget_entry = {
            "time": time,
            "mass_initial": mass_initial,
            "mass_remaining": mass_remaining,
            "mass_lost": mass_lost,
            "mass_diff": mass_diff,
            "error_percent": error_percent,
            "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
            "mass_loss_rp_mars": M_loss_cum,
            "mass_loss_hydro_drag": M_hydro_cum,
            "mass_loss_surface_solid_marsRP": M_loss_cum,
            "mass_loss_tau_clip_spill": M_spill_cum,
        }
        if extended_diag_enabled:
            channels_total = M_loss_cum + M_sink_cum
            denom = abs(channels_total) if abs(channels_total) > 0.0 else 1.0
            delta_channels = ((mass_lost - channels_total) / denom) * 100.0
            budget_entry["delta_mloss_vs_channels"] = delta_channels
        last_mass_budget_entry = budget_entry
        mass_budget.append(budget_entry)
        if step_diag_enabled:
            tau_surf_val = (
                tau_los_last if tau_los_last is not None else kappa_surf * sigma_diag * los_factor
            )
            tau_surf_val = _safe_float(tau_surf_val)
            sink_sub_timescale = sink_result.components.get("sublimation")
            sink_drag_timescale = sink_result.components.get("gas_drag")
            dM_sub = mass_loss_sublimation_step_diag
            dM_drag = 0.0
            if sink_result.dominant_sink == "sublimation":
                dM_sub += sink_mass_total
            elif sink_result.dominant_sink == "gas_drag":
                dM_drag = sink_mass_total
            step_diag_records.append(
                {
                    "time": float(time),
                    "sigma_surf": float(sigma_diag),
                    "tau_surf": tau_surf_val,
                    "t_coll": _safe_float(t_coll_step),
                    "t_blow": _safe_float(t_blow_step),
                    "t_sink": _safe_float(t_sink_step),
                    "t_sink_sub": _safe_float(sink_sub_timescale),
                    "t_sink_drag": _safe_float(sink_drag_timescale),
                    "phase_state_step": phase_state_last,
                    "phase_bulk_state": phase_bulk_state_last,
                    "phase_bulk_f_liquid": _safe_float(phase_bulk_f_liquid_last),
                    "phase_bulk_f_solid": _safe_float(phase_bulk_f_solid_last),
                    "phase_bulk_f_vapor": _safe_float(phase_bulk_f_vapor_last),
                    "ds_dt_sublimation": _safe_float(ds_dt_val),
                    "ds_dt_sublimation_raw": _safe_float(ds_dt_raw),
                    "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
                    "dM_blowout_step": float(mass_loss_surface_solid_step),
                    "dM_sinks_step": float(mass_loss_sinks_step_total),
                    "dM_sublimation_step": float(dM_sub),
                    "dM_gas_drag_step": float(dM_drag),
                    "mass_total_bins": float(mass_remaining),
                    "mass_lost_by_blowout": float(M_loss_cum),
                    "mass_lost_by_sinks": float(M_sink_cum),
                }
            )

        total_time_elapsed += dt
        if tau_gate_block_last:
            tau_gate_block_time += dt

        time_after_step = time + dt
        if checkpoint_enabled and time_after_step >= checkpoint_next_time:
            ckpt_ext = ".pkl" if checkpoint_format == "pickle" else ".json"
            ckpt_path = checkpoint_dir / f"ckpt_step_{step_no:09d}{ckpt_ext}"
            try:
                state_ckpt = _build_checkpoint_state(step_no, time_after_step)
                checkpoint_io.save_checkpoint(ckpt_path, state_ckpt, fmt=checkpoint_format)
                checkpoint_io.prune_checkpoints(checkpoint_dir, checkpoint_keep_last)
                checkpoint_next_time += checkpoint_interval_s
            except Exception as exc:
                logger.error("Failed to write checkpoint %s: %s", ckpt_path, exc)

        last_step_index = step_no
        last_time_value = time_after_step
        progress.update(step_no, time_after_step)

        if (
            mass_initial != 0.0
            and error_percent > MASS_BUDGET_TOLERANCE_PERCENT
            and history.mass_budget_violation is None
        ):
            history.mass_budget_violation = {
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
                history.violation_triggered = True
                break

        if stop_after_record:
            early_stop_reason = "tau_exceeded"
            early_stop_step = step_no
            early_stop_time_s = time + dt
            total_time_elapsed = time + dt
            logger.info(
                "Early stop triggered: tau_los=%.3e exceeded tau_stop=%.3e at t=%.3e s (step %d)",
                tau_stop_los_value if tau_stop_los_value is not None else float("nan"),
                optical_tau_stop,
                time + dt,
                step_no,
            )
            break

        if not quiet_mode and not progress_enabled and logger.isEnabledFor(logging.INFO):
            logger.info(
                "run: t=%e a_blow=%.3e kappa=%e t_blow=%e M_loss[M_Mars]=%e",
                time,
                a_blow_step,
                kappa_eff,
                t_blow_step,
                M_loss_cum + M_sink_cum,
            )

        steps_since_flush += 1
        if streaming_state.should_flush(history, steps_since_flush):
            streaming_state.flush(history, step_no)
            steps_since_flush = 0

    if last_step_index >= 0:
        progress.finish(last_step_index, last_time_value)

    final_step_index = last_step_index if last_step_index >= 0 else 0
    merge_status_message: Optional[str] = None
    if streaming_state.enabled:
        streaming_state.flush(history, final_step_index)

    if orbit_rollup_enabled and not orbit_rollup_rows:
        # Fallback rollup for short integrations that do not complete a full orbit.
        mass_loss_frac = float("nan")
        if cfg.initial.mass_total > 0.0:
            mass_loss_frac = (orbit_loss_blow + orbit_loss_sink) / cfg.initial.mass_total
        denom = t_orb_step if t_orb_step > 0.0 else float("nan")
        orbit_rollup_rows.append(
            {
                "orbit_index": 1,
                "time_s": time,
                "time_s_end": time,
                "t_orb_s": t_orb_step,
                "M_out_orbit": orbit_loss_blow,
                "M_sink_orbit": orbit_loss_sink,
                "M_loss_orbit": orbit_loss_blow + orbit_loss_sink,
                "M_out_per_orbit": orbit_loss_blow / denom if math.isfinite(denom) else float("nan"),
                "M_sink_per_orbit": orbit_loss_sink / denom if math.isfinite(denom) else float("nan"),
                "M_loss_per_orbit": (orbit_loss_blow + orbit_loss_sink) / denom if math.isfinite(denom) else float("nan"),
                "mass_loss_frac_per_orbit": mass_loss_frac,
                "M_out_cum": M_loss_cum,
                "M_sink_cum": M_sink_cum,
                "M_loss_cum": M_loss_cum + M_sink_cum,
                "r_RM": r_RM,
                "T_M": T_use,
                "slope_dlnM_dlnr": None,
            }
        )
        orbits_completed = max(orbits_completed, 1)

    history.tau_gate_block_time = tau_gate_block_time
    history.total_time_elapsed = total_time_elapsed

    if supply_clip_events:
        clip_fraction_percent = (
            (supply_clip_time / total_time_elapsed) * 100.0 if total_time_elapsed > 0.0 else float("nan")
        )
        example = supply_clip_events[0]
        example_reason = example.get("reason", "headroom")
        example_mode = example.get("transport_mode", supply_transport_mode)
        logger.warning(
            "supply visibility suppressed in %d streaks (threshold=%d steps, mode=%s, reason=%s); "
            "total_clip_time=%.3e s (%.2f%% of run). "
            "example: t=%.3e s Sigma_surf=%.3e Sigma_tau1=%.3e headroom=%.3e supply_scaled=%.3e temp_scale=%.3f feedback_scale=%.3f vis=%.3e",
            len(supply_clip_events),
            supply_clip_warn_threshold,
            example_mode,
            example_reason,
            supply_clip_time,
            clip_fraction_percent,
            example.get("time", float("nan")),
            example.get("Sigma_surf", float("nan")),
            example.get("Sigma_tau1", float("nan")),
            example.get("headroom", float("nan")),
            example.get("supply_scaled", float("nan")),
            example.get("temperature_scale", float("nan")),
            example.get("feedback_scale", float("nan")),
            example.get("supply_visibility_factor", float("nan")),
        )

    qpr_mean = qpr_mean_step
    a_blow = a_blow_step
    a_blow_effective = max(s_min_config, a_blow)
    Omega = Omega_step
    t_orb = t_orb_step
    qpr_blow_final = _lookup_qpr(max(a_blow, 1.0e-12))

    df: Optional[pd.DataFrame] = None
    if not streaming_state.enabled:
        if isinstance(records, ColumnarBuffer):
            table = records.to_table(ensure_columns=series_columns)
            df = table.to_pandas()
        else:
            df = pd.DataFrame(records)
        _write_zero_d_history(
            cfg,
            df,
            history,
            step_diag_enabled=step_diag_enabled,
            step_diag_format=step_diag_format,
            step_diag_path_cfg=step_diag_path_cfg,
            step_diag_path=step_diag_path,
            orbit_rollup_enabled=orbit_rollup_enabled,
            extended_diag_enabled=extended_diag_enabled,
            series_columns=series_columns,
            diagnostic_columns=diagnostic_columns,
        )
    else:
        try:
            streaming_state.merge_chunks()
            if streaming_state.merge_at_end:
                streaming_merge_completed = True
                merge_status_message = "streaming merge completed"
                logger.info("Streaming merge completed for %s", cfg.io.outdir)
        except Exception as exc:
            streaming_merge_completed = False
            merge_status_message = "streaming merge failed"
            short_msg = _format_exception_short(exc)
            logger.error(
                "Streaming merge failed for %s (%s): %s",
                cfg.io.outdir,
                exc.__class__.__name__,
                short_msg,
            )
            logger.debug("Streaming merge full exception for %s", cfg.io.outdir, exc_info=exc)
    outdir = Path(cfg.io.outdir)
    dt_over_t_blow_median = float("nan")
    if dt_over_t_blow_values:
        dt_over_t_blow_median = float(np.median(np.asarray(dt_over_t_blow_values, dtype=float)))

    def _first_finite(values: List[Optional[float]]) -> Optional[float]:
        for val in values:
            try:
                candidate = float(val)  # type: ignore[arg-type]
            except Exception:
                continue
            if math.isfinite(candidate):
                return candidate
        return None

    T_min, T_median, T_max = _series_stats(temperature_track)
    beta_min, beta_median, beta_max = _series_stats(beta_track)
    ablow_min, ablow_median, ablow_max = _series_stats(ablow_track)
    gate_min, gate_median, gate_max = _series_stats(gate_factor_track)
    tsolid_min, tsolid_median, tsolid_max = _series_stats(t_solid_track)
    supply_feedback_min, supply_feedback_median, supply_feedback_max = _series_stats(supply_feedback_track)
    supply_temp_scale_min, supply_temp_scale_median, supply_temp_scale_max = _series_stats(supply_temperature_scale_track)
    supply_reservoir_min, supply_reservoir_median, supply_reservoir_max = _series_stats(supply_reservoir_remaining_track)
    supply_headroom_min, supply_headroom_median, supply_headroom_max = _series_stats(supply_headroom_track)
    supply_clip_factor_min, supply_clip_factor_median, supply_clip_factor_max = _series_stats(supply_clip_factor_track)
    supply_visibility_min, supply_visibility_median, supply_visibility_max = _series_stats(supply_visibility_track)
    supply_spill_rate_min, supply_spill_rate_median, supply_spill_rate_max = _series_stats(supply_spill_rate_track)
    supply_blocked_fraction = (
        float(np.mean(np.asarray(supply_blocked_track, dtype=float))) if supply_blocked_track else float("nan")
    )
    supply_mixing_fraction = (
        float(np.mean(np.asarray(supply_mixing_block_track, dtype=float))) if supply_mixing_block_track else float("nan")
    )
    supply_spill_active_fraction = (
        float(np.mean(np.asarray(supply_spill_rate_track, dtype=float) > supply_visibility_eps))
        if supply_spill_rate_track
        else float("nan")
    )
    supply_clip_time_fraction = (
        float(supply_clip_time / total_time_elapsed)
        if total_time_elapsed > 0.0
        else float("nan")
    )
    supply_rate_nominal_inferred = supply_effective_rate
    if supply_rate_nominal_inferred is None:
        supply_rate_nominal_inferred = _first_finite(supply_rate_nominal_track)
    supply_rate_scaled_initial_final = supply_rate_scaled_initial
    if supply_rate_scaled_initial_final is None:
        supply_rate_scaled_initial_final = _first_finite(supply_rate_scaled_track)
    extended_max_rate = float("nan")
    extended_max_rate_time = None
    extended_median_ts_ratio = float("nan")
    tau_gate_block_fraction = (
        float(tau_gate_block_time / total_time_elapsed)
        if total_time_elapsed > 0.0
        else float("nan")
    )
    if extended_diag_enabled:
        for rate_val, time_val in zip(extended_total_rate_track, extended_total_rate_time_track):
            if not math.isfinite(rate_val):
                continue
            if not math.isfinite(extended_max_rate) or rate_val > extended_max_rate:
                extended_max_rate = float(rate_val)
                extended_max_rate_time = float(time_val)
        if extended_ts_ratio_track:
            ts_arr = np.asarray(extended_ts_ratio_track, dtype=float)
            ts_arr = ts_arr[np.isfinite(ts_arr)]
            if ts_arr.size:
                extended_median_ts_ratio = float(np.median(ts_arr))
    reservoir_remaining_final = supply_state.reservoir_remaining_Mmars() if supply_state else None
    reservoir_fraction_final = supply_state.reservoir_fraction() if supply_state else None
    reservoir_mass_used = None
    if supply_reservoir_mass_total is not None and reservoir_remaining_final is not None:
        reservoir_mass_used = max(float(supply_reservoir_mass_total - reservoir_remaining_final), 0.0)
    process_overview = {
        "primary_process_cfg": primary_process_cfg,
        "primary_process_resolved": primary_process,
        "primary_scenario": primary_scenario,
        "primary_field_explicit": primary_field_explicit,
        "collisions_active": collisions_active,
        "sinks_mode": sinks_mode_value,
        "sinks_enabled_cfg": sinks_enabled_cfg,
        "sinks_active": bool(sublimation_active_flag or sink_timescale_active),
        "sink_timescale_active": sink_timescale_active,
        "sublimation_dsdt_active": sublimation_active_flag,
        "sublimation_sink_active": sink_opts.enable_sublimation and not enforce_collisions_only,
        "gas_drag_sink_active": sink_opts.enable_gas_drag and not enforce_collisions_only,
        "blowout_active": blowout_enabled,
        "rp_blowout_enabled": rp_blowout_enabled,
        "collision_solver": collision_solver_mode,
        "shielding_mode": shielding_mode,
        "shielding_auto_max_active": shielding_auto_max_active,
        "supply_enabled": supply_enabled_cfg,
        "supply_mode": supply_mode_value,
        "supply_headroom_policy": supply_headroom_policy,
        "supply_reservoir_enabled": supply_reservoir_enabled,
        "supply_feedback_enabled": supply_feedback_enabled,
        "supply_reservoir_mode": supply_reservoir_mode,
        "supply_reservoir_mass_total_Mmars": supply_reservoir_mass_total,
        "supply_reservoir_remaining_Mmars": reservoir_remaining_final,
        "supply_reservoir_fraction_final": reservoir_fraction_final,
        "supply_reservoir_mass_used_Mmars": reservoir_mass_used,
        "supply_reservoir_depletion_time_s": supply_reservoir_depleted_time,
        "supply_reservoir_taper_fraction": supply_reservoir_taper_fraction,
        "supply_temperature_enabled": supply_temperature_enabled,
        "supply_temperature_mode": supply_temperature_mode,
    }
    wyatt_collisional_timescale_active = bool(
        collisions_active
        and getattr(cfg.surface, "use_tcoll", True)
        and collision_solver_mode != "smol"
    )
    active_sinks_list: List[str] = []
    if sink_opts.enable_sublimation:
        active_sinks_list.append("sublimation")
    if sink_opts.enable_gas_drag:
        active_sinks_list.append("gas_drag")
    if getattr(hydro_cfg, "enable", False) and sink_timescale_active:
        active_sinks_list.append("hydro_escape")
    inner_scope_mode = (
        "optically_thick_surface_only" if blowout_layer_mode == "surface_tau_le_1" else blowout_layer_mode
    )
    tau_gate_mode = "tau_clipped" if tau_gate_enabled else "off"
    time_grid_summary = {
        "t_start_s": 0.0,
        "t_end_s": time_grid_info.get("t_end_seconds"),
        "t_end_actual_s": total_time_elapsed,
        "dt_s": time_grid_info.get("dt_step", dt),
        "dt_nominal_s": time_grid_info.get("dt_nominal"),
        "n_steps": time_grid_info.get("n_steps"),
        "dt_mode": time_grid_info.get("dt_mode"),
    }
    time_grid_summary["terminated_early"] = early_stop_reason is not None
    time_grid_summary["early_stop_reason"] = early_stop_reason
    time_grid_summary["early_stop_step"] = early_stop_step
    limitations_list = [
        "Inner-disk only; outer or highly eccentric debris is out of scope.",
        "Radiation pressure source is fixed to Mars; solar/other external sources are ignored even when requested.",
        f"Time horizon is short (~{analysis_window_years:.3g} yr); long-term tidal or viscous evolution is not modelled.",
        "Collisional cascade and sublimation are toggled via physics_mode switches rather than a fully coupled solver.",
        "Assumes an optically thick inner surface with tau<=1 clipping; vertical/outer tenuous structure is not resolved.",
        "PSD uses a three-slope core with optional wavy correction and blow-out/sublimation floors; no self-consistent halo is evolved.",
    ]
    if shielding_auto_max_active:
        limitations_list.append(
            "DEBUG: shielding.fixed_tau1_sigma=auto_max applied (headroom diagnostic; production use discouraged)."
        )
    scope_limitations_base = {
        "scope": {
            "region": scope_region,
            "reference_radius_m": r,
            "reference_radius_source": r_source,
            "analysis_window_years": analysis_window_years,
            "radiation_source": radiation_field,
            "solar_radiation_enabled": False,
            "solar_radiation_requested": solar_rp_requested,
            "inner_disk_scope": inner_scope_flag,
            "inner_disk_scope_mode": inner_scope_mode,
            "tau_gate": {
                "enabled": tau_gate_enabled,
                "tau_max": tau_gate_threshold if tau_gate_enabled else None,
                "mode": tau_gate_mode,
            },
            "shielding_mode": shielding_mode,
            "time_grid_summary": time_grid_summary,
        },
        "active_physics": {
            "primary_scenario": primary_scenario,
            "physics_mode": physics_mode,
            "collisions_active": collisions_active,
            "sublimation_active": sublimation_active_flag,
            "sinks_active": bool(sublimation_active_flag or sink_timescale_active),
            "rp_blowout_active": blowout_enabled,
            "wyatt_collisional_timescale_active": wyatt_collisional_timescale_active,
            "active_sinks": active_sinks_list,
        },
        "limitations": limitations_list,
    }
    scope_limitations_summary = copy.deepcopy(scope_limitations_base)
    scope_limitations_config = copy.deepcopy(scope_limitations_base)
    scope_limitations_config["scope"].update(
        {
            "analysis_window_basis": time_grid_info.get("t_end_basis"),
            "time_grid_dt_mode": time_grid_info.get("dt_mode"),
            "radiation_use_mars_rp": mars_rp_enabled_cfg,
            "radiation_use_solar_rp": solar_rp_requested,
        }
    )
    scope_limitations_config["active_physics"].update(
        {
            "enforce_sublimation_only": enforce_sublimation_only,
            "enforce_collisions_only": enforce_collisions_only,
            "sinks_mode": sinks_mode_value,
            "sinks_enabled_cfg": sinks_enabled_cfg,
            "sink_timescale_active": sink_timescale_active,
            "blowout_enabled_cfg": blowout_enabled_cfg,
            "rp_blowout_enabled_cfg": rp_blowout_enabled,
            "shielding_mode": shielding_mode,
            "freeze_kappa": freeze_kappa,
            "freeze_sigma": freeze_sigma,
            "tau_gate_enabled": tau_gate_enabled,
        }
    )
    scope_limitations_config["limitation_codes"] = [
        "inner_disk_only",
        "mars_rp_only",
        "short_timescale",
        "mode_switching_not_fully_coupled",
        "optically_thick_surface",
        "simplified_psd_floor",
    ]
    summary = {
        "M_loss": (M_loss_cum + M_sink_cum),
        "M_loss_from_sinks": M_sink_cum,
        "M_loss_from_sublimation": M_sublimation_cum,
        "M_loss_tau_clip_spill": M_spill_cum,
        "M_loss_rp_mars": M_loss_cum,
        "M_loss_surface_solid_marsRP": M_loss_cum,
        "M_loss_hydro_escape": M_hydro_cum,
        "M_out_cum": M_loss_cum,
        "M_sink_cum": M_sink_cum,
        "orbits_completed": orbits_completed,
        "case_status": case_status,
        "beta_threshold": beta_threshold,
        "beta_at_smin_config": beta_at_smin_config,
        "beta_at_smin_effective": beta_at_smin_effective,
        "s_blow_m": a_blow,
        "s_blow_m_effective": a_blow_effective,
        "blowout_gate_mode": blowout_gate_mode,
        "chi_blow_input": chi_config_str,
        "chi_blow_eff": chi_blow_eff,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean,
        "Q_pr_blow": qpr_blow_final,
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "kappa_surf_initial": kappa_surf_initial,
        "kappa_eff_initial": kappa_eff0,
        "Sigma_tau1_initial": sigma_tau1_cap_init,
        "sigma_surf_initial": sigma_surf_init_raw,
        "T_M_used": T_use,
        "T_M_used[K]": T_use,
        "T_M_source": T_M_source,
        "T_M_initial": temperature_track[0] if temperature_track else temp_runtime.initial_value,
        "T_M_final": temperature_track[-1] if temperature_track else temp_runtime.initial_value,
        "T_M_min": T_min,
        "T_M_median": T_median,
        "T_M_max": T_max,
        "early_stop_reason": early_stop_reason,
        "early_stop_time_s": early_stop_time_s,
        "stop_reason": "tau_exceeded" if early_stop_reason == "tau_exceeded" else None,
        "stop_tau_los": tau_stop_los_value if early_stop_reason == "tau_exceeded" else None,
        "analysis_window_years_actual": total_time_elapsed / SECONDS_PER_YEAR if total_time_elapsed is not None else None,
        "beta_at_smin_min": beta_min,
        "beta_at_smin_median": beta_median,
        "beta_at_smin_max": beta_max,
        "a_blow_min": ablow_min,
        "a_blow_median": ablow_median,
        "a_blow_max": ablow_max,
        "streaming_merge_completed": streaming_merge_completed
        if streaming_state.enabled and streaming_state.merge_at_end
        else None,
        "blowout_gate_factor_min": gate_min,
        "blowout_gate_factor_median": gate_median,
        "blowout_gate_factor_max": gate_max,
        "t_solid_min": tsolid_min,
        "t_solid_median": tsolid_median,
        "t_solid_max": tsolid_max,
        "temperature_driver": temp_runtime.provenance,
        "r_m_used": r,
        "r_RM_used": r_RM,
        "r_source": r_source,
        "phi_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
        "shielding_mode": shielding_mode,
        "shielding_fixed_tau1_mode": sigma_tau1_mode_label,
        "shielding_auto_max_active": shielding_auto_max_active,
        "shielding_auto_max_margin": auto_max_margin,
        "mass_budget_max_error_percent": mass_budget_max_error,
        "dt_over_t_blow_median": dt_over_t_blow_median,
        "config_source_path": str(config_source_path) if config_source_path is not None else None,
        "s_min_effective": s_min_effective,
        "s_min_effective[m]": s_min_effective,
        "s_min_config": s_min_config,
        "s_min_effective_gt_config": s_min_effective > s_min_config,
        "s_min_components": s_min_components,
        "supply_feedback_enabled": supply_feedback_enabled,
        "supply_feedback_target_tau": supply_feedback_target,
        "supply_feedback_gain": supply_feedback_gain,
        "supply_feedback_response_time_years": supply_feedback_response_yr,
        "supply_feedback_scale_min": supply_feedback_min,
        "supply_feedback_scale_median": supply_feedback_median,
        "supply_feedback_scale_max": supply_feedback_max,
        "supply_reservoir_enabled": supply_reservoir_enabled,
        "supply_reservoir_mass_total_Mmars": supply_reservoir_mass_total,
        "supply_reservoir_remaining_Mmars": reservoir_remaining_final,
        "supply_reservoir_mass_used_Mmars": reservoir_mass_used,
        "supply_reservoir_fraction_final": reservoir_fraction_final,
        "supply_reservoir_remaining_stats_Mmars": {
            "min": supply_reservoir_min,
            "median": supply_reservoir_median,
            "max": supply_reservoir_max,
        },
        "supply_reservoir_mode": supply_reservoir_mode,
        "supply_reservoir_taper_fraction": supply_reservoir_taper_fraction,
        "supply_reservoir_smooth_fraction": supply_reservoir_taper_fraction,
        "supply_reservoir_depletion_time_s": supply_reservoir_depleted_time,
        "supply_temperature_enabled": supply_temperature_enabled,
        "supply_temperature_mode": supply_temperature_mode,
        "supply_temperature_scale_min": supply_temp_scale_min,
        "supply_temperature_scale_median": supply_temp_scale_median,
        "supply_temperature_scale_max": supply_temp_scale_max,
        "supply_temperature_value_kind": supply_temperature_value_kind,
        "supply_temperature_table_path": str(supply_temperature_table_path) if supply_temperature_table_path is not None else None,
        "supply_mu_orbit10pct": supply_mu_orbit_cfg,
        "supply_mu_reference_tau": mu_reference_tau,
        "sigma_surf_mu_reference": sigma_surf_mu_ref,
        "supply_orbit_fraction_at_mu1": supply_orbit_fraction,
        "Sigma_surf0": sigma_surf0_target,
        "supply_rate_nominal_kg_m2_s": supply_rate_nominal_inferred,
        "supply_rate_scaled_initial_kg_m2_s": supply_rate_scaled_initial_final,
        "effective_prod_rate_kg_m2_s": supply_effective_rate,
        "supply_transport_mode": supply_transport_mode,
        "supply_transport_t_mix_orbits": supply_deep_tmix_orbits,
        "supply_transport_headroom_gate": supply_transport_headroom_gate,
        "supply_headroom_policy": supply_headroom_policy,
        "supply_visibility_min": supply_visibility_min,
        "supply_visibility_median": supply_visibility_median,
        "supply_visibility_max": supply_visibility_max,
        "supply_blocked_fraction": supply_blocked_fraction,
        "supply_mixing_fraction": supply_mixing_fraction,
        "supply_velocity_mode": supply_velocity_mode,
        "supply_velocity_blend_mode": supply_velocity_blend_mode,
        "supply_velocity_weight_mode": supply_velocity_weight_mode,
        "supply_velocity_e_inj": supply_velocity_e_inj,
        "supply_velocity_i_inj": supply_velocity_i_inj,
        "supply_velocity_vrel_factor": supply_velocity_vrel_factor,
        "supply_clip_time_fraction": supply_clip_time_fraction,
        "supply_clipping": {
            "headroom_min": supply_headroom_min,
            "headroom_median": supply_headroom_median,
            "headroom_max": supply_headroom_max,
            "clip_factor_min": supply_clip_factor_min,
            "clip_factor_median": supply_clip_factor_median,
            "clip_factor_max": supply_clip_factor_max,
            "clip_time_fraction": supply_clip_time_fraction,
            "visibility_min": supply_visibility_min,
            "visibility_median": supply_visibility_median,
            "visibility_max": supply_visibility_max,
            "blocked_fraction": supply_blocked_fraction,
            "mixing_fraction": supply_mixing_fraction,
        },
        "supply_spill": {
            "rate_min": supply_spill_rate_min,
            "rate_median": supply_spill_rate_median,
            "rate_max": supply_spill_rate_max,
            "active_fraction": supply_spill_active_fraction,
            "M_loss_cum": M_spill_cum,
        },
        "enforce_mass_budget": enforce_mass_budget,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "collision_solver": collision_solver_mode,
        "primary_scenario": primary_scenario,
        "process_overview": process_overview,
        "time_grid": {
            "basis": time_grid_info.get("t_end_basis"),
            "t_end_input": time_grid_info.get("t_end_input"),
            "t_end_s": time_grid_info.get("t_end_seconds"),
            "t_end_actual_s": total_time_elapsed,
            "dt_mode": time_grid_info.get("dt_mode"),
            "dt_input": time_grid_info.get("dt_input"),
            "dt_nominal_s": time_grid_info.get("dt_nominal"),
            "dt_step_s": dt,
            "n_steps": time_grid_info.get("n_steps"),
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
            "terminated_early": early_stop_reason is not None,
            "early_stop_reason": early_stop_reason,
            "early_stop_step": early_stop_step,
            "early_stop_time_s": early_stop_time_s,
        },
        "streaming": {
            "enabled": streaming_state.enabled,
            "enabled_config": streaming_enabled_cfg,
            "forced_off_env": force_streaming_off,
            "forced_on_env": force_streaming_on,
            "memory_limit_gb": streaming_memory_limit_gb if streaming_state.enabled else None,
            "step_flush_interval": streaming_step_interval if streaming_state.enabled else None,
            "compression": streaming_compression if streaming_state.enabled else None,
            "merge_at_end": streaming_merge_at_end if streaming_state.enabled else False,
            "cleanup_chunks": streaming_cleanup_chunks if streaming_state.enabled else None,
            "merge_outdir": str(streaming_state.merge_outdir) if streaming_state.enabled else None,
            "run_chunks": [str(p) for p in streaming_state.run_chunks],
            "psd_chunks": [str(p) for p in streaming_state.psd_chunks],
            "diagnostics_chunks": [str(p) for p in streaming_state.diag_chunks],
            "mass_budget_path": str(streaming_state.mass_budget_path if streaming_state.enabled else outdir / "checks" / "mass_budget.csv"),
            "energy_streaming_enabled": energy_streaming_enabled,
            "energy_streaming_config": bool(energy_streaming_cfg),
            "energy_series_path": str(energy_series_path),
            "energy_parquet_path": str(energy_parquet_path),
        },
        "archive": {
            "enabled": archive_enabled,
            "enabled_config": archive_enabled_cfg,
            "forced_off_env": archive_forced_off,
            "forced_on_env": archive_forced_on,
            "dir": str(archive_dir) if archive_dir is not None else None,
            "dir_resolved": str(archive_root_resolved) if archive_root_resolved is not None else None,
            "trigger": archive_trigger,
            "merge_target": archive_merge_target,
            "verify": archive_verify,
            "verify_level": archive_verify_level,
            "mode": archive_mode,
            "keep_local": archive_keep_local,
            "record_volume_info": archive_record_volume_info,
            "warn_slow_mb_s": archive_warn_slow_mb_s,
            "warn_slow_min_gb": archive_warn_slow_min_gb,
            "min_free_gb": archive_min_free_gb,
        },
    }
    summary["scope_limitations"] = scope_limitations_summary
    if extended_diag_enabled:
        summary.update(
            {
                "M_loss_blowout_total": M_loss_cum,
                "M_loss_sink_total": M_sink_cum,
                "M_loss_total": M_loss_cum + M_sink_cum,
                "max_mloss_rate": extended_max_rate,
                "max_mloss_rate_time": extended_max_rate_time,
                "median_ts_ratio": extended_median_ts_ratio,
                "median_gate_factor": gate_median,
                "tau_gate_blocked_time_fraction": tau_gate_block_fraction,
                "extended_diagnostics_version": extended_diag_version,
            }
        )
    summary["inner_disk_scope"] = inner_scope_flag
    summary["analysis_window_years"] = analysis_window_years
    summary["radiation_field"] = radiation_field
    summary["primary_process"] = primary_process
    summary["primary_scenario"] = primary_scenario
    summary["collisions_active"] = collisions_active
    summary["sinks_active"] = sinks_active
    summary["sublimation_active"] = sublimation_active_flag
    summary["sublimation_location"] = sublimation_location
    summary["blowout_active"] = blowout_enabled
    summary["state_tagging_enabled"] = state_tagging_enabled
    summary["state_phase_tag"] = state_phase_tag
    summary["physics"] = {
        "mode": physics_mode,
        "source": physics_mode_source,
    }
    summary["phase_branching"] = {
        "enabled": phase_controller.enabled,
        "source": phase_controller.source,
        "entrypoint": phase_controller.entrypoint,
        "temperature_input": phase_temperature_input_mode,
        "q_abs_mean": phase_q_abs_mean,
        "phase_temperature_formula": phase_temperature_formula,
        "phase_usage_time_s": {k: float(v) for k, v in phase_usage.items()},
        "phase_method_usage_time_s": {k: float(v) for k, v in phase_method_usage.items()},
        "sink_branch_usage_time_s": {k: float(v) for k, v in sink_branch_usage.items()},
    }
    if energy_count > 0:
        last = energy_last_row if energy_last_row is not None else {}
        summary["energy_bookkeeping"] = {
            "enabled": True,
            "E_rel_total": float(energy_sum_rel),
            "E_dissipated_total": float(energy_sum_diss),
            "E_retained_total": float(energy_sum_ret),
            "frac_fragmentation_last": float(last.get("frac_fragmentation", 0.0)),
            "frac_cratering_last": float(last.get("frac_cratering", 0.0)),
            "f_ke_mean_last": float(last.get("f_ke_mean", 0.0)),
            "f_ke_energy_last": float(last.get("f_ke_energy", 0.0)),
        }
    summary["radiation_tau_gate"] = {
        "enabled": tau_gate_enabled,
        "tau_max": tau_gate_threshold if tau_gate_enabled else None,
    }
    summary["solar_radiation"] = {
        "enabled": False,
        "requested": solar_rp_requested,
        "note": (
            "Solar radiation disabled (Mars-only scope)"
            if radiation_field == "mars"
            else "Radiation disabled via radiation.source='off'"
        ),
    }
    if orbits_completed > 0:
        summary["M_out_mean_per_orbit"] = M_loss_cum / orbits_completed
        summary["M_sink_mean_per_orbit"] = M_sink_cum / orbits_completed
        summary["M_loss_mean_per_orbit"] = (M_loss_cum + M_sink_cum) / orbits_completed
    if history.mass_budget_violation is not None:
        summary["mass_budget_violation"] = history.mass_budget_violation
    summary_path = outdir / "summary.json"
    writer.write_summary(summary, summary_path)
    mass_budget_path = (
        streaming_state.mass_budget_path if streaming_state.enabled else outdir / "checks" / "mass_budget.csv"
    )
    if streaming_state.enabled:
        if mass_budget:
            writer.append_csv(mass_budget, mass_budget_path, header=not mass_budget_path.exists())
            mass_budget.clear()
        if not mass_budget_path.exists():
            if last_mass_budget_entry:
                pd.DataFrame(columns=list(last_mass_budget_entry.keys())).to_csv(
                    mass_budget_path, index=False
                )
            else:
                writer.write_mass_budget(mass_budget, mass_budget_path)
    else:
        writer.write_mass_budget(mass_budget, mass_budget_path)
    if orbit_rollup_enabled and streaming_state.enabled:
        writer.write_orbit_rollup(history.orbit_rollup_rows, outdir / "orbit_rollup.csv")

    # Energy bookkeeping outputs (independent of bulk streaming)
    if energy_streaming_enabled:
        if energy_series_path.exists():
            try:
                df_energy = pd.read_csv(energy_series_path)
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Failed to read streamed energy CSV at %s: %s", energy_series_path, exc)
                df_energy = None
            if df_energy is not None and not df_energy.empty:
                writer.write_parquet(df_energy, energy_parquet_path)
        # Streaming path already wrote energy_budget incrementally.
    else:
        if energy_series:
            writer.write_parquet(pd.DataFrame(energy_series), energy_parquet_path)
            energy_series.clear()
        if energy_budget:
            writer.write_mass_budget(energy_budget, energy_budget_path)

    # Lightweight run_card with energy bookkeeping rollup
    run_card_path = outdir / "run_card.md"
    try:
        eb = summary.get("energy_bookkeeping", {})
        try:
            current_git_sha = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path.cwd())
                .decode()
                .strip()
            )
        except Exception:
            current_git_sha = "unknown"
        command_invoked = " ".join(sys.argv)
        rng_seed_resolved = getattr(cfg.initial, "rng_seed", None)
        numpy_version = np.__version__
        pandas_version = pd.__version__
        auto_tune_info = getattr(cfg, "_auto_tune_info", None)
        lines = [
            "# MarsDisk run card",
            "",
            "## Artifacts",
            f"- summary: {summary_path.name}",
            f"- series: series/run.parquet",
            f"- energy_series: series/energy.parquet",
            f"- mass_budget: checks/mass_budget.csv",
            f"- energy_budget: checks/energy_budget.csv",
            "",
            "## Configuration",
            f"- physics_mode: {physics_mode}",
            f"- collisions_active: {collisions_active}",
            f"- sinks_active: {sinks_active}",
            f"- energy_bookkeeping: {'enabled' if eb else 'disabled'}",
            "",
            "## Energy bookkeeping (totals)",
            f"- E_rel_total [J/m^2]: {eb.get('E_rel_total', 0.0):.6e}",
            f"- E_dissipated_total [J/m^2]: {eb.get('E_dissipated_total', 0.0):.6e}",
            f"- E_retained_total [J/m^2]: {eb.get('E_retained_total', 0.0):.6e}",
            f"- frac_fragmentation_last: {eb.get('frac_fragmentation_last', 0.0):.4f}",
            f"- frac_cratering_last: {eb.get('frac_cratering_last', 0.0):.4f}",
            f"- f_ke_mean_last: {eb.get('f_ke_mean_last', 0.0):.4f}",
            f"- f_ke_energy_last: {eb.get('f_ke_energy_last', 0.0):.4f}",
            "",
            "## Environment",
            f"- python: {sys.version.split()[0]}",
            f"- platform: {sys.platform}",
            f"- git_commit: {current_git_sha}",
            f"- run_command: {command_invoked}",
            f"- seed: {rng_seed_resolved}",
            f"- numpy: {numpy_version}",
            f"- pandas: {pandas_version}",
        ]
        if auto_tune_info is not None:
            decision = auto_tune_info.get("decision", {})
            lines.extend(
                [
                    "",
                    "## Auto-tune",
                    f"- enabled: true",
                    f"- profile: {decision.get('profile_resolved', 'unknown')}",
                    f"- numba_threads: {decision.get('numba_threads', 'unknown')}",
                    f"- numba_thread_source: {decision.get('numba_thread_source', 'unknown')}",
                    f"- suggested_sweep_jobs: {decision.get('suggested_sweep_jobs', 'unknown')}",
                ]
            )
        run_card_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to write run_card.md: %s", exc)

    # Quiet でも完了ステータスを一行で把握できるよう、進捗バーの完了後に短いメッセージを出す。
    if progress_enabled and merge_status_message is not None:
        progress._print(f"[info] {merge_status_message}")
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
            "T_M_initial": temperature_track[0] if temperature_track else temp_runtime.initial_value,
            "T_M_final": temperature_track[-1] if temperature_track else temp_runtime.initial_value,
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
            "physics_mode": physics_mode,
            "physics_mode_source": physics_mode_source,
            "phase_temperature_input": phase_temperature_input_mode,
            "phase_q_abs_mean": phase_q_abs_mean,
            "phase_temperature_formula": phase_temperature_formula,
        },
        "init_tau1": {
            "enabled": init_tau1_enabled,
            "sigma_tau1_target": sigma_tau1_unity,
            "sigma_surf_init_override_applied": sigma_override_applied,
            "sigma_surf_init_raw": sigma_surf_init_raw,
            "sigma_surf_init_applied": sigma_surf_reference,
            "sigma_tau1_cap_init": sigma_tau1_cap_init,
            "sigma_tau1_mode": sigma_tau1_mode_label,
            "initial_sigma_clipped": initial_sigma_clipped,
            "mass_total_original_Mmars": mass_total_original,
            "mass_total_applied_Mmars": mass_total_applied,
        },
        "optical_depth": {
            "enabled": optical_depth_enabled,
            "tau0_target": optical_tau0_target,
            "tau_stop": optical_tau_stop,
            "tau_stop_tol": optical_tau_stop_tol,
            "tau_field": optical_tau_field,
            "sigma_surf0": sigma_surf0_target,
            "kappa_eff0": kappa_eff0,
        },
        "supply_mu_orbit10pct": supply_mu_orbit_cfg,
        "supply_mu_reference_tau": mu_reference_tau,
        "sigma_surf_mu_reference": sigma_surf_mu_ref,
        "supply_orbit_fraction_at_mu1": supply_orbit_fraction,
        "init_ei": {
            "e_mode": cfg.dynamics.e_mode,
            "dr_min_m": cfg.dynamics.dr_min_m,
            "dr_max_m": cfg.dynamics.dr_max_m,
            "dr_dist": cfg.dynamics.dr_dist,
            "delta_r_sample_m": delta_r_sample,
            "e0_applied": e0_effective,
            "e_profile_mode": e_profile_meta.get("mode") if isinstance(e_profile_meta, dict) else None,
            "e_profile_r_kind": e_profile_meta.get("r_kind") if isinstance(e_profile_meta, dict) else None,
            "e_profile_table_path": e_profile_meta.get("table_path") if isinstance(e_profile_meta, dict) else None,
            "e_profile_formula": e_profile_meta.get("formula") if isinstance(e_profile_meta, dict) else None,
            "e_profile_applied": bool(e_profile_meta.get("applied")) if isinstance(e_profile_meta, dict) else False,
            "i_mode": cfg.dynamics.i_mode,
            "obs_tilt_deg": cfg.dynamics.obs_tilt_deg,
            "i_spread_deg": cfg.dynamics.i_spread_deg,
            "i0_applied_rad": i0_effective,
            "seed_used": int(seed),
            "e_formula_SI": "e = 1 - (R_MARS + Δr)/a; [Δr, a, R_MARS]: meters",
            "a_m_source": r_source,
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
            "max_steps": _get_max_steps(),
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "t_blow_nominal_s": time_grid_info.get("t_blow_nominal"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
            "scheme": "fixed-step implicit-Euler (S1)",
        },
        "physics_controls": {
            "blowout_enabled": blowout_enabled,
            "rp_blowout_enabled": rp_blowout_enabled,
            "blowout_target_phase": blowout_target_phase,
            "blowout_layer": blowout_layer_mode,
            "blowout_gate_mode": blowout_gate_mode,
            "freeze_kappa": freeze_kappa,
            "freeze_sigma": freeze_sigma,
            "shielding_mode": shielding_mode,
            "shielding_tau_fixed": tau_fixed_cfg,
            "shielding_sigma_tau1_fixed": sigma_tau1_fixed_target,
            "shielding_fixed_tau1_mode": sigma_tau1_mode_label,
            "shielding_auto_max_active": shielding_auto_max_active,
            "shielding_auto_max_margin": auto_max_margin,
            "shielding_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
            "psd_floor_mode": psd_floor_mode,
            "phase_enabled": phase_controller.enabled,
            "phase_source": phase_controller.source,
            "phase_entrypoint": phase_controller.entrypoint,
            "phase_temperature_input": phase_temperature_input_mode,
            "phase_q_abs_mean": phase_q_abs_mean,
            "phase_temperature_formula": phase_temperature_formula,
            "tau_gate_enabled": tau_gate_enabled,
            "tau_gate_tau_max": tau_gate_threshold if tau_gate_enabled else None,
            "hydro_escape_strength": getattr(hydro_cfg, "strength", None),
            "hydro_escape_temp_power": getattr(hydro_cfg, "temp_power", None),
            "radiation_use_mars_rp": mars_rp_enabled_cfg,
            "radiation_use_solar_rp": solar_rp_requested,
        },
    }
    auto_tune_info = getattr(cfg, "_auto_tune_info", None)
    if auto_tune_info is not None:
        run_config["auto_tune"] = auto_tune_info
    run_config["phase_temperature"] = {
        "mode": phase_temperature_input_mode,
        "q_abs_mean": phase_q_abs_mean,
        "formula": phase_temperature_formula,
        "r_m_used": r,
        "r_RM_used": r_RM,
    }
    qstar_coeff_table = {
        f"{float(v):.1f}": {
            "Qs": float(coeffs[0]),
            "a_s": float(coeffs[1]),
            "B": float(coeffs[2]),
            "b_g": float(coeffs[3]),
        }
        for v, coeffs in sorted(qstar.get_coefficient_table().items(), key=lambda item: item[0])
    }
    run_config["qstar"] = {
        "config": qstar_cfg.model_dump() if qstar_cfg is not None else None,
        "coeff_units_used": qstar_coeff_units_used,
        "coeff_units_source": qstar_coeff_units_source,
        "coeff_override": qstar_coeff_override,
        "coeff_scale": qstar_coeff_scale if qstar_coeff_override else None,
        "coeff_scale_applied": qstar_coeff_scale_applied,
        "coeff_table_source": qstar_coeff_table_source,
        "gravity_velocity_mu_used": qstar_mu_gravity_used,
        "gravity_velocity_mu_source": qstar_mu_gravity_source,
        "gravity_velocity_exponent_used": -3.0 * qstar_mu_gravity_used + 2.0,
        "reference_velocities_kms_active": [float(v) for v in sorted(qstar.get_coefficient_table().keys())],
        "coeff_table_active": qstar_coeff_table,
        "velocity_clamp_counts": qstar.get_velocity_clamp_stats(),
    }
    run_config["scope_limitations"] = scope_limitations_config
    run_config["physics_mode"] = physics_mode
    run_config["physics_mode_source"] = physics_mode_source
    run_config["scope_controls"] = {
        "region": scope_region,
        "analysis_window_years": analysis_window_years,
        "inner_disk_scope": inner_scope_flag,
    }
    run_config["process_controls"] = {
        "primary_process": primary_process,
        "primary_process_cfg": primary_process_cfg,
        "primary_scenario": primary_scenario,
        "primary_field_explicit": primary_field_explicit,
        "state_tagging_enabled": state_tagging_enabled,
        "state_phase_tag": state_phase_tag,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "collision_solver": collision_solver_mode,
        "collisions_active": collisions_active,
        "sinks_mode": sinks_mode_value,
        "sinks_enabled_cfg": sinks_enabled_cfg,
        "sinks_active": sinks_active,
        "sublimation_active": sublimation_active_flag,
        "sublimation_location": sublimation_location,
        "sink_timescale_active": sink_timescale_active,
        "blowout_active": blowout_enabled,
        "rp_blowout_enabled": rp_blowout_enabled,
    }
    run_config["supply"] = {
        "enabled": supply_enabled_cfg,
        "mode": supply_mode_value,
        "headroom_policy": supply_headroom_policy,
        "epsilon_mix": supply_epsilon_mix,
        "mu_orbit10pct": supply_mu_orbit_cfg,
        "orbit_fraction_at_mu1": supply_orbit_fraction,
        "const_prod_area_rate_kg_m2_s": supply_const_rate,
        "table_path": str(supply_table_path) if supply_table_path is not None else None,
        "effective_prod_rate_kg_m2_s": supply_effective_rate,
        "supply_rate_nominal_kg_m2_s": supply_rate_nominal_inferred,
        "supply_rate_scaled_initial_kg_m2_s": supply_rate_scaled_initial_final,
        "transport_mode": supply_transport_mode,
        "transport_t_mix_orbits": supply_deep_tmix_orbits,
        "transport_headroom_gate": supply_transport_headroom_gate,
        "injection_velocity": {
            "mode": supply_velocity_mode,
            "e_inj": supply_velocity_e_inj,
            "i_inj": supply_velocity_i_inj,
            "vrel_factor": supply_velocity_vrel_factor,
            "blend_mode": supply_velocity_blend_mode,
            "weight_mode": supply_velocity_weight_mode,
        },
        "supply_clip_time_fraction": supply_clip_time_fraction,
        "clipping": {
            "headroom_min": supply_headroom_min,
            "headroom_median": supply_headroom_median,
            "headroom_max": supply_headroom_max,
            "clip_factor_min": supply_clip_factor_min,
            "clip_factor_median": supply_clip_factor_median,
            "clip_factor_max": supply_clip_factor_max,
            "clip_time_fraction": supply_clip_time_fraction,
            "visibility_min": supply_visibility_min,
            "visibility_median": supply_visibility_median,
            "visibility_max": supply_visibility_max,
            "blocked_fraction": supply_blocked_fraction,
            "mixing_fraction": supply_mixing_fraction,
        },
        "spill": {
            "rate_min": supply_spill_rate_min,
            "rate_median": supply_spill_rate_median,
            "rate_max": supply_spill_rate_max,
            "active_fraction": supply_spill_active_fraction,
            "M_loss_cum": M_spill_cum,
        },
        "reservoir_enabled": supply_reservoir_enabled,
        "reservoir_mass_total_Mmars": supply_reservoir_mass_total,
        "reservoir_mode": supply_reservoir_mode,
        "reservoir_taper_fraction": supply_reservoir_taper_fraction,
        "reservoir_smooth_fraction": supply_reservoir_taper_fraction,
        "reservoir_depletion_time_s": supply_reservoir_depleted_time,
        "reservoir_remaining_Mmars_final": reservoir_remaining_final,
        "reservoir_fraction_final": reservoir_fraction_final,
        "reservoir_mass_used_Mmars": reservoir_mass_used,
        "feedback_enabled": supply_feedback_enabled,
        "feedback_target_tau": supply_feedback_target,
        "feedback_gain": supply_feedback_gain,
        "feedback_response_time_years": supply_feedback_response_yr,
        "feedback_min_scale": getattr(supply_feedback_cfg, "min_scale", None) if supply_feedback_cfg else None,
        "feedback_max_scale": getattr(supply_feedback_cfg, "max_scale", None) if supply_feedback_cfg else None,
        "feedback_tau_field": supply_feedback_tau_field if supply_feedback_cfg else None,
        "feedback_initial_scale": getattr(supply_feedback_cfg, "initial_scale", None) if supply_feedback_cfg else None,
        "temperature_enabled": supply_temperature_enabled,
        "temperature_mode": supply_temperature_mode,
        "temperature_reference_K": getattr(supply_temperature_cfg, "reference_K", None)
        if supply_temperature_cfg
        else None,
        "temperature_exponent": getattr(supply_temperature_cfg, "exponent", None) if supply_temperature_cfg else None,
        "temperature_scale_at_reference": getattr(supply_temperature_cfg, "scale_at_reference", None)
        if supply_temperature_cfg
        else None,
        "temperature_floor": getattr(supply_temperature_cfg, "floor", None) if supply_temperature_cfg else None,
        "temperature_cap": getattr(supply_temperature_cfg, "cap", None) if supply_temperature_cfg else None,
        "temperature_table_path": str(supply_temperature_table_path) if supply_temperature_table_path is not None else None,
        "temperature_table_value_kind": supply_temperature_value_kind,
    }
    run_config["physics_mode_resolution"] = {
        "resolved_mode": physics_mode,
        "source": physics_mode_source,
        "inputs": {
            "cli": physics_mode_override,
            "physics_mode_cfg": physics_mode_cfg,
        },
    }
    run_config["process_overview"] = process_overview
    run_config["solar_radiation"] = {
        "enabled": False,
        "requested": solar_rp_requested,
        "note": (
            "Solar radiation disabled (Mars-only scope)"
            if radiation_field == "mars"
            else "Radiation disabled via radiation.source='off'"
        ),
    }
    temp_prov = dict(temp_runtime.provenance)
    temp_prov.setdefault("mode", temp_runtime.mode)
    temp_prov.setdefault("enabled", temp_runtime.enabled)
    temp_prov.setdefault("source", temp_runtime.source)
    run_config["temperature_driver"] = temp_prov
    run_config["io"] = {
        "outdir": str(outdir),
        "streaming": {
            "enabled": streaming_state.enabled,
            "merge_at_end": streaming_merge_at_end if streaming_state.enabled else False,
            "cleanup_chunks": streaming_cleanup_chunks if streaming_state.enabled else None,
            "merge_outdir": str(streaming_state.merge_outdir) if streaming_state.enabled else None,
        },
        "archive": {
            "enabled": archive_enabled,
            "enabled_config": archive_enabled_cfg,
            "forced_off_env": archive_forced_off,
            "forced_on_env": archive_forced_on,
            "dir": str(archive_dir) if archive_dir is not None else None,
            "dir_resolved": str(archive_root_resolved) if archive_root_resolved is not None else None,
            "trigger": archive_trigger,
            "merge_target": archive_merge_target,
            "verify": archive_verify,
            "verify_level": archive_verify_level,
            "mode": archive_mode,
            "keep_local": archive_keep_local,
            "record_volume_info": archive_record_volume_info,
            "warn_slow_mb_s": archive_warn_slow_mb_s,
            "warn_slow_min_gb": archive_warn_slow_min_gb,
            "min_free_gb": archive_min_free_gb,
        },
    }
    if temp_autogen_info is not None:
        run_config["temperature_autogen"] = {
            "path": str(temp_autogen_info.get("path")),
            "generated": bool(temp_autogen_info.get("generated", False)),
            "coverage_years": temp_autogen_info.get("coverage_years"),
            "target_years": temp_autogen_info.get("target_years"),
            "time_unit": temp_autogen_info.get("time_unit"),
            "column_time": temp_autogen_info.get("column_time"),
            "column_temperature": temp_autogen_info.get("column_temperature"),
        }
    run_config["T_M_used"] = float(T_use)
    run_config["rho_used"] = float(rho_used)
    run_config["Q_pr_used"] = float(qpr_mean)
    if qpr_override is not None:
        qpr_source = "override"
    elif qpr_table_path_resolved is not None:
        qpr_source = "table"
    else:
        qpr_source = "fallback"
    run_config["radiation_provenance"] = {
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "Q_pr_override": qpr_override,
        "Q_pr_source": qpr_source,
        "Q_pr_blow": qpr_blow_final,
        "T_M_source": T_M_source,
        "radiation_field": radiation_field,
        "temperature_source": temp_runtime.source,
        "use_mars_rp": mars_rp_enabled_cfg,
        "use_solar_rp": solar_rp_requested,
    }
    run_config["blowout_provenance"] = {
        "s_blow_raw_m": float(a_blow),
        "s_blow_effective_m": float(a_blow_effective),
        "s_min_config_m": float(s_min_config),
        "psd_floor_mode": str(psd_floor_mode),
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
    valid_liquid_config = (
        list(sub_params.valid_liquid_K) if sub_params.valid_liquid_K is not None else None
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
        "A_liq": sub_params.A_liq,
        "B_liq": sub_params.B_liq,
        "P_gas": sub_params.P_gas,
        "valid_K_config": valid_config,
        "valid_liquid_K_config": valid_liquid_config,
        "valid_K_active": valid_active,
        "psat_table_path": psat_table_path,
        "psat_table_range_K": psat_table_range,
        "psat_table_monotonic": psat_selection.get("monotonic"),
        "psat_table_buffer_K": sub_params.psat_table_buffer_K,
        "local_fit_window_K": sub_params.local_fit_window_K,
        "min_points_local_fit": sub_params.min_points_local_fit,
        "psat_validity_status": psat_selection.get("psat_validity_status"),
        "psat_validity_direction": psat_selection.get("psat_validity_direction"),
        "psat_validity_delta_K": psat_selection.get("psat_validity_delta_K"),
        "psat_branch": psat_selection.get("psat_branch"),
        "T_req": psat_selection.get("T_req"),
        "P_sat_Pa": psat_selection.get("P_sat_Pa"),
        "log10P": psat_selection.get("log10P"),
        "log10P_tabulated": psat_selection.get("log10P_tabulated"),
        "eta_instant": sub_params.eta_instant,
        "runtime_radius_m": r,
        "runtime_t_orb_s": t_orb,
        "enable_liquid_branch": bool(getattr(sub_params, "enable_liquid_branch", False)),
        "psat_liquid_switch_K": getattr(sub_params, "psat_liquid_switch_K", None),
        "valid_liquid_K_active": (
            list(psat_selection["valid_K_active"])
            if isinstance(psat_selection.get("valid_K_active"), (tuple, list))
            else psat_selection.get("valid_K_active")
        ),
        "allow_liquid_hkl": allow_liquid_hkl,
    }
    writer.write_run_config(run_config, outdir / "run_config.json")

    if archive_enabled and archive_trigger == "post_merge":
        if archive_root_resolved is None and archive_dir is None:
            logger.warning("Archive enabled but io.archive.dir is not set; skipping archive.")
        else:
            archive_settings = archive_mod.ArchiveSettings(
                enabled=archive_enabled,
                dir=archive_dir,
                mode=archive_mode,
                trigger=archive_trigger,
                merge_target=archive_merge_target,
                verify=archive_verify,
                verify_level=archive_verify_level,
                keep_local=archive_keep_local,
                record_volume_info=archive_record_volume_info,
                warn_slow_mb_s=archive_warn_slow_mb_s,
                warn_slow_min_gb=archive_warn_slow_min_gb,
                min_free_gb=archive_min_free_gb,
            )
            archive_root = archive_root_resolved or archive_dir
            if archive_root is not None:
                result = archive_mod.archive_run(
                    outdir,
                    archive_root=archive_root,
                    settings=archive_settings,
                )
                if not result.success:
                    logger.warning("Archive failed for %s: %s", outdir, "; ".join(result.errors))

    if history.violation_triggered:
        raise MassBudgetViolationError(
            "Mass budget tolerance exceeded; see summary.json for details"
        )


def main(argv: Optional[List[str]] = None) -> None:
    """Command line entry point."""

    parser = argparse.ArgumentParser(description="Run a simple Mars disk model")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML configuration")
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show a console progress bar with ETA for the main integration loop.",
    )
    parser.add_argument(
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Suppress INFO logs and Python warnings for a cleaner CLI "
            "(defaults to enabled when not set in config; use --no-quiet to show logs)."
        ),
    )
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
        "--physics-mode",
        choices=["default", "sublimation_only", "collisions_only"],
        help="Override physics_mode from the CLI",
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
    parser.add_argument(
        "--overrides-file",
        action="append",
        type=Path,
        help="Load overrides from a file (one PATH=VALUE per line).",
    )
    parser.add_argument(
        "--auto-tune",
        action="store_true",
        help="Enable runtime auto-tuning of thread settings (default: off).",
    )
    parser.add_argument(
        "--auto-tune-profile",
        choices=["auto", "light", "balanced", "throughput"],
        default="auto",
        help="Select auto-tune profile when --auto-tune is enabled.",
    )
    args = parser.parse_args(argv)

    override_list: List[str] = []
    if args.overrides_file:
        for override_path in args.overrides_file:
            override_list.extend(config_utils.read_overrides_file(override_path))
    if args.override:
        for group in args.override:
            override_list.extend(group)
    auto_tune_info = None
    if args.auto_tune:
        from .runtime import autotune as autotune_mod

        auto_tune_info = autotune_mod.apply_auto_tune(profile=args.auto_tune_profile)
    cfg = load_config(args.config, overrides=override_list)
    if auto_tune_info is not None:
        try:
            setattr(cfg, "_auto_tune_info", auto_tune_info)
        except Exception:
            pass
    quiet_fields_set = set(getattr(cfg.io, "model_fields_set", ()))
    if args.quiet is not None:
        try:
            cfg.io.quiet = bool(args.quiet)
        except Exception:
            pass
    elif "quiet" not in quiet_fields_set:
        try:
            cfg.io.quiet = True
        except Exception:
            pass
    if args.progress:
        try:
            cfg.io.progress.enable = True
        except Exception:
            pass
    quiet_effective = bool(getattr(cfg.io, "quiet", False))
    _configure_logging(
        logging.WARNING if quiet_effective else logging.INFO,
        suppress_warnings=quiet_effective,
    )
    if args.sinks is not None:
        cfg.sinks.mode = args.sinks
    if args.physics_mode is not None:
        cfg.physics_mode = args.physics_mode
    geometry_mode = getattr(getattr(cfg, "geometry", None), "mode", "0D")
    if geometry_mode == "1D":
        from .run_one_d import run_one_d

        run_one_d(
            cfg,
            enforce_mass_budget=args.enforce_mass_budget,
            physics_mode_override=args.physics_mode,
            physics_mode_source_override="cli" if args.physics_mode is not None else None,
        )
        return
    run_zero_d(
        cfg,
        enforce_mass_budget=args.enforce_mass_budget,
        physics_mode_override=args.physics_mode,
        physics_mode_source_override="cli" if args.physics_mode is not None else None,
    )

__all__ = [
    "SECONDS_PER_YEAR",
    "MAX_STEPS",
    "TAU_MIN",
    "KAPPA_MIN",
    "MASS_BUDGET_TOLERANCE_PERCENT",
    "FAST_BLOWOUT_RATIO_THRESHOLD",
    "FAST_BLOWOUT_RATIO_STRICT",
    "_compute_gate_factor",
    "_surface_energy_floor",
    "_fast_blowout_correction_factor",
    "_log_stage",
    "compute_phase_tau_fields",
    "StreamingState",
    "ZeroDHistory",
    "ProgressReporter",
    "RunConfig",
    "RunState",
    "step",
    "run_n_steps",
    "load_config",
    "run_zero_d",
    "main",
    "MassBudgetViolationError",
    "radiation",
    "sizes",
]

if __name__ == "__main__":  # pragma: no cover - standard CLI entrypoint
    import logging

    logging.basicConfig(level=logging.INFO)
    main()
