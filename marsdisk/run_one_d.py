"""1D radial runner for the Mars disk simulation."""
from __future__ import annotations

import copy
import logging
import math
import os
import random
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import config_utils, constants, grid
from .errors import ConfigurationError, NumericalError, PhysicsError
from .io import tables, writer, archive as archive_mod
from .io.streaming import StreamingState
from .orchestrator import (
    resolve_time_grid as _resolve_time_grid,
    resolve_seed as _resolve_seed,
    human_bytes as _human_bytes,
    memory_estimate as _memory_estimate,
)
from .runtime import ProgressReporter, ZeroDHistory
from .runtime.helpers import (
    compute_phase_tau_fields,
    compute_gate_factor,
    ensure_finite_kappa,
    safe_float as _safe_float,
    float_or_nan as _float_or_nan,
)
from .output_schema import ensure_series_keys as _ensure_series_keys
from .output_schema import ensure_diagnostic_keys as _ensure_diagnostic_keys
from .schema import Config
from .physics import (
    psd,
    radiation,
    shielding,
    surface,
    supply,
    initfields,
    sizes,
    sinks,
    tempdriver,
    phase as phase_mod,
    qstar,
    collisions_smol,
    eccentricity,
)
from .physics.sublimation import SublimationParams, grain_temperature_graybody

logger = logging.getLogger(__name__)

SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
MAX_STEPS = 50_000_000
TAU_MIN = 1.0e-12
KAPPA_MIN = 1.0e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1.0e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0


class MassBudgetViolationError(NumericalError):
    """Raised when the mass budget tolerance is exceeded."""


def _resolve_los_factor(los_geom: Optional[object]) -> float:
    """Return the multiplicative factor f_los scaling τ_vert to τ_los."""

    if los_geom is None:
        return 1.0
    mode = getattr(los_geom, "mode", "aspect_ratio_factor")
    if mode == "none":
        return 1.0
    h_over_r = float(getattr(los_geom, "h_over_r", 1.0) or 1.0)
    path_multiplier = float(getattr(los_geom, "path_multiplier", 1.0) or 1.0)
    if h_over_r <= 0.0 or path_multiplier <= 0.0:
        return 1.0
    factor = path_multiplier / h_over_r
    return float(factor if factor > 1.0 else 1.0)


def _clamp_sigma_surf(value: float, *, label: str = "sigma_surf") -> float:
    """Return a non-negative finite surface density (clamped to 0 on invalid)."""

    try:
        sigma_val = float(value)
    except Exception:
        logger.warning("%s is not a valid float; clamping to 0", label)
        return 0.0
    if not math.isfinite(sigma_val) or sigma_val < 0.0:
        logger.warning("%s is non-finite or negative; clamping to 0", label)
        return 0.0
    return sigma_val


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
    """Return the effective loss fraction ``f_fast = 1 - exp(-Δt/t_blow)``."""

    if ratio <= 0.0 or math.isinf(ratio):
        return 0.0 if ratio <= 0.0 else 1.0
    value = -math.expm1(-ratio)
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


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


def _env_int(name: str) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _resolve_cell_parallel_config(
    *,
    os_name: str,
    n_cells: int,
    cell_parallel_requested: bool,
    cell_jobs_requested: int,
    cell_min_cells: int,
    cell_chunk_size_raw: int,
    cell_coupling_enabled: bool,
) -> Dict[str, object]:
    cell_parallel_reason = "enabled"
    if not cell_parallel_requested:
        cell_parallel_reason = "not_requested"
    elif os_name != "nt":
        cell_parallel_reason = "non_windows"
    elif n_cells < cell_min_cells:
        cell_parallel_reason = "too_few_cells"
    elif cell_coupling_enabled:
        cell_parallel_reason = "cell_coupling_enabled"
    elif cell_jobs_requested <= 1:
        cell_parallel_reason = "single_job"

    cell_parallel_enabled = cell_parallel_reason == "enabled"
    cell_jobs_effective = cell_jobs_requested
    if cell_parallel_enabled:
        cell_jobs_effective = max(1, min(cell_jobs_effective, n_cells))
        if cell_jobs_effective <= 1:
            cell_parallel_enabled = False
            cell_parallel_reason = "single_job"
            cell_jobs_effective = 1
    else:
        cell_jobs_effective = 1

    cell_chunk_mode = "auto"
    if cell_chunk_size_raw > 0:
        cell_chunk_mode = "fixed"
        cell_chunk_size_effective = cell_chunk_size_raw
    else:
        cell_chunk_size_effective = (
            int(math.ceil(n_cells / cell_jobs_effective)) if cell_jobs_effective > 0 else n_cells
        )
    if cell_chunk_size_effective < 1:
        cell_chunk_size_effective = 1
    if cell_chunk_size_effective > n_cells:
        cell_chunk_size_effective = n_cells

    return {
        "enabled": cell_parallel_enabled,
        "reason": cell_parallel_reason,
        "jobs_effective": int(cell_jobs_effective),
        "chunk_size": int(cell_chunk_size_effective),
        "chunk_mode": cell_chunk_mode,
    }


def run_one_d(
    cfg: Config,
    *,
    enforce_mass_budget: bool = False,
    physics_mode_override: Optional[str] = None,
    physics_mode_source_override: Optional[str] = None,
) -> None:
    """Execute the 1D radial Mars disk simulation."""

    config_source_path_raw = getattr(cfg, "_source_path", None)
    config_source_path: Optional[Path] = None
    if config_source_path_raw:
        try:
            config_source_path = Path(config_source_path_raw).resolve()
        except Exception:
            config_source_path = None
    outdir = Path(cfg.io.outdir)

    geometry_cfg = getattr(cfg, "geometry", None)
    if geometry_cfg is None or getattr(geometry_cfg, "mode", "0D") != "1D":
        raise ConfigurationError("run_one_d requires geometry.mode='1D'")
    n_cells = int(getattr(geometry_cfg, "Nr", 0) or 0)
    if n_cells <= 0:
        raise ConfigurationError("geometry.Nr must be positive for 1D runs")

    disk_geom = getattr(cfg, "disk", None)
    if disk_geom is not None and getattr(disk_geom, "geometry", None) is not None:
        r_in_rm = float(disk_geom.geometry.r_in_RM)
        r_out_rm = float(disk_geom.geometry.r_out_RM)
        r_in_m = r_in_rm * constants.R_MARS
        r_out_m = r_out_rm * constants.R_MARS
        geometry_source = "disk.geometry"
    else:
        r_in_raw = getattr(geometry_cfg, "r_in", None)
        r_out_raw = getattr(geometry_cfg, "r_out", None)
        if r_in_raw is None or r_out_raw is None:
            raise ConfigurationError("disk.geometry is required for 1D runs")
        r_in_m = float(r_in_raw)
        r_out_m = float(r_out_raw)
        geometry_source = "geometry.r_in_out"
    if r_in_m <= 0.0 or r_out_m <= 0.0 or not (math.isfinite(r_in_m) and math.isfinite(r_out_m)):
        raise ConfigurationError("geometry.r_in/r_out must be positive and finite")
    if r_in_m >= r_out_m:
        raise ConfigurationError("geometry.r_in must be less than r_out")

    radial_grid = grid.RadialGrid.linear(r_in_m, r_out_m, n_cells)
    r_vals = np.asarray(radial_grid.r, dtype=float)
    r_rm_vals = r_vals / constants.R_MARS
    area_vals = np.asarray(radial_grid.areas, dtype=float)
    total_area = float(np.sum(area_vals))
    Omega_vals = np.array([grid.omega_kepler(r) for r in r_vals], dtype=float)
    t_orb_vals = np.where(Omega_vals > 0.0, 2.0 * math.pi / Omega_vals, float("inf"))

    r_mid = float(0.5 * (r_in_m + r_out_m))
    r_rm_mid = r_mid / constants.R_MARS
    Omega_ref = grid.omega_kepler(r_mid)
    t_orb_ref = 2.0 * math.pi / Omega_ref if Omega_ref > 0.0 else float("inf")

    e_profile_values, e_profile_meta = eccentricity.evaluate_e_profile(
        getattr(cfg.dynamics, "e_profile", None),
        r_m=r_vals,
        r_RM=r_rm_vals,
        log=logger,
    )
    if e_profile_values is None:
        e_cells = np.full_like(r_vals, float(cfg.dynamics.e0))
        dynamics_cfg_cells = None
    else:
        e_cells = np.asarray(e_profile_values, dtype=float)
        if e_cells.shape != r_vals.shape:
            raise ConfigurationError("e_profile evaluation returned unexpected shape for 1D grid")
        dynamics_cfg_cells = [
            cfg.dynamics.model_copy(update={"e0": float(e_val)}) for e_val in e_cells
        ]
    init_ei_snapshot = {
        "e_mode": cfg.dynamics.e_mode,
        "e0_config": float(cfg.dynamics.e0),
        "i0_config_rad": float(cfg.dynamics.i0),
        "e_profile_mode": e_profile_meta.get("mode") if isinstance(e_profile_meta, dict) else None,
        "e_profile_r_kind": e_profile_meta.get("r_kind") if isinstance(e_profile_meta, dict) else None,
        "e_profile_table_path": e_profile_meta.get("table_path") if isinstance(e_profile_meta, dict) else None,
        "e_profile_formula": e_profile_meta.get("formula") if isinstance(e_profile_meta, dict) else None,
        "e_profile_applied": bool(e_profile_meta.get("applied")) if isinstance(e_profile_meta, dict) else False,
    }

    cell_parallel_requested = _env_flag("MARSDISK_CELL_PARALLEL") is True
    cell_jobs_env = _env_int("MARSDISK_CELL_JOBS")
    cell_min_cells_env = _env_int("MARSDISK_CELL_MIN_CELLS")
    cell_chunk_size_env = _env_int("MARSDISK_CELL_CHUNK_SIZE")

    cell_jobs_requested = cell_jobs_env if cell_jobs_env is not None else 1
    if cell_jobs_requested < 1:
        cell_jobs_requested = 1
    cell_min_cells = cell_min_cells_env if cell_min_cells_env is not None else 4
    if cell_min_cells < 1:
        cell_min_cells = 1
    cell_chunk_size_raw = cell_chunk_size_env if cell_chunk_size_env is not None else 0

    cell_coupling_enabled = bool(
        getattr(cfg.numerics, "enable_viscosity", False)
        or getattr(cfg.numerics, "enable_radial_transport", False)
    )
    cell_parallel_config = _resolve_cell_parallel_config(
        os_name=os.name,
        n_cells=n_cells,
        cell_parallel_requested=cell_parallel_requested,
        cell_jobs_requested=cell_jobs_requested,
        cell_min_cells=cell_min_cells,
        cell_chunk_size_raw=cell_chunk_size_raw,
        cell_coupling_enabled=cell_coupling_enabled,
    )
    cell_parallel_enabled = bool(cell_parallel_config["enabled"])
    cell_parallel_reason = str(cell_parallel_config["reason"])
    cell_jobs_effective = int(cell_parallel_config["jobs_effective"])
    cell_chunk_size_effective = int(cell_parallel_config["chunk_size"])
    cell_chunk_mode = str(cell_parallel_config["chunk_mode"])

    numba_threads_env = os.environ.get("NUMBA_NUM_THREADS")
    if numba_threads_env is not None and not numba_threads_env.strip():
        numba_threads_env = None
    numba_threads_auto = None
    numba_threads_effective = None
    if cell_parallel_enabled and cell_jobs_effective > 1 and numba_threads_env is None:
        cores = os.cpu_count() or 1
        numba_threads_auto = max(1, cores // cell_jobs_effective)
        os.environ["NUMBA_NUM_THREADS"] = str(numba_threads_auto)
        try:
            import numba  # type: ignore

            numba.set_num_threads(numba_threads_auto)
            numba_threads_effective = int(numba.get_num_threads())
        except Exception:
            numba_threads_effective = None

    cell_parallel_info = {
        "requested": cell_parallel_requested,
        "enabled": cell_parallel_enabled,
        "disabled_reason": None if cell_parallel_enabled else cell_parallel_reason,
        "jobs_requested": int(cell_jobs_requested),
        "jobs_effective": int(cell_jobs_effective),
        "min_cells": int(cell_min_cells),
        "chunk_size": int(cell_chunk_size_effective),
        "chunk_mode": cell_chunk_mode,
        "os": os.name,
        "numba_threads_env": numba_threads_env,
        "numba_threads_auto": numba_threads_auto,
        "numba_threads_effective": numba_threads_effective,
        "cell_coupling_enabled": cell_coupling_enabled,
    }

    if cell_parallel_requested:
        logger.info(
            "cell-parallel: enabled=%s jobs=%s chunk=%s reason=%s",
            cell_parallel_enabled,
            cell_jobs_effective,
            cell_chunk_size_effective,
            cell_parallel_reason,
        )

    cell_chunks = None
    cell_executor = None
    if cell_parallel_enabled:
        cell_chunks = [
            range(start, min(start + cell_chunk_size_effective, n_cells))
            for start in range(0, n_cells, cell_chunk_size_effective)
        ]
        cell_executor = ThreadPoolExecutor(max_workers=cell_jobs_effective)

    scope_cfg = getattr(cfg, "scope", None)
    analysis_window_years = float(getattr(scope_cfg, "analysis_years", 2.0)) if scope_cfg else 2.0
    if cfg.numerics.t_end_years is None and cfg.numerics.t_end_orbits is None:
        cfg.numerics.t_end_years = analysis_window_years

    physics_mode_cfg = getattr(cfg, "physics_mode", None)
    physics_mode = config_utils.normalise_physics_mode(physics_mode_override or physics_mode_cfg)
    physics_mode_source = "cli" if physics_mode_override is not None else "config"
    if physics_mode_source_override:
        physics_mode_source = physics_mode_source_override

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
    if qstar_cfg is not None and qstar_coeff_override:
        coeff_table_cfg = getattr(qstar_cfg, "coeff_table", None)
        if coeff_table_cfg:
            qstar.set_coefficient_table(coeff_table_cfg)
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
    else:
        qstar.reset_coefficient_table()

    seed_val, seed_expr, seed_basis = _resolve_seed(cfg)
    np.random.seed(seed_val)
    random.seed(seed_val)

    radiation_cfg = getattr(cfg, "radiation", None)
    radiation_field = str(getattr(radiation_cfg, "source", "mars")) if radiation_cfg else "mars"
    solar_rp_requested = bool(getattr(radiation_cfg, "use_solar_rp", False)) if radiation_cfg else False
    mars_rp_enabled_cfg = bool(getattr(radiation_cfg, "use_mars_rp", True)) if radiation_cfg else True
    radiation.configure_qpr_fallback(
        strict=bool(getattr(radiation_cfg, "qpr_strict", False)) if radiation_cfg else False,
    )
    qpr_override = None
    qpr_table_path_resolved: Optional[Path] = None
    qpr_strict = bool(getattr(radiation_cfg, "qpr_strict", False)) if radiation_cfg else False
    if radiation_cfg is not None:
        qpr_table_path_resolved = getattr(radiation_cfg, "qpr_table_resolved", None)
        if qpr_table_path_resolved is not None:
            radiation.load_qpr_table(qpr_table_path_resolved)
        else:
            qpr_override = getattr(radiation_cfg, "Q_pr", None)
    active_qpr_table = tables.get_qpr_table_path()
    if qpr_table_path_resolved is None and active_qpr_table is not None:
        qpr_table_path_resolved = active_qpr_table
    if qpr_override is None and qpr_table_path_resolved is None:
        if qpr_strict:
            raise ConfigurationError(
                "⟨Q_pr⟩ lookup table not initialised and radiation.qpr_strict=true. "
                "Provide radiation.qpr_table_path or radiation.Q_pr."
            )
        logger.warning("⟨Q_pr⟩ lookup table not initialised; using DEFAULT_Q_PR=1.")

    temp_runtime = tempdriver.resolve_temperature_driver(
        radiation_cfg,
        t_orb=t_orb_ref,
        prefer_driver=True,
    )
    T_M_source = temp_runtime.source
    tau_gate_cfg = getattr(cfg.radiation, "tau_gate", None) if cfg.radiation else None
    tau_gate_enabled = bool(getattr(tau_gate_cfg, "enable", False)) if tau_gate_cfg else False
    tau_gate_threshold = (
        float(getattr(tau_gate_cfg, "tau_max", 1.0)) if tau_gate_enabled else float("inf")
    )
    blowout_cfg = getattr(cfg, "blowout", None)
    blowout_enabled = bool(getattr(blowout_cfg, "enabled", True))
    blowout_target_phase = str(getattr(blowout_cfg, "target_phase", "solid_only"))
    blowout_layer_mode = str(getattr(blowout_cfg, "layer", "surface_tau_le_1"))
    blowout_gate_mode = (
        str(getattr(blowout_cfg, "gate_mode", "none")).lower() if blowout_cfg else "none"
    )
    if blowout_gate_mode not in {"none", "sublimation_competition", "collision_competition"}:
        raise ConfigurationError(f"Unknown blowout.gate_mode={blowout_gate_mode!r}")
    gate_enabled = blowout_gate_mode != "none"
    if blowout_gate_mode == "collision_competition" and not bool(
        getattr(cfg.surface, "use_tcoll", True)
    ):
        raise ConfigurationError(
            "blowout.gate_mode='collision_competition' requires surface.use_tcoll=true"
        )

    shielding_cfg = getattr(cfg, "shielding", None)
    shielding_mode = "off"
    phi_tau_fn = None
    los_factor = 1.0
    if shielding_cfg is not None:
        shielding_mode = shielding_cfg.mode_resolved
        los_factor = _resolve_los_factor(getattr(shielding_cfg, "los_geometry", None))
        table_path = getattr(shielding_cfg, "table_path_resolved", None)
        if shielding_mode in {"psitau", "table"} and table_path is not None:
            phi_tau_fn = shielding.load_phi_table(table_path)

    sizes_cfg = cfg.sizes
    s_min_config = float(getattr(sizes_cfg, "s_min", 1.0e-7))
    s_max_config = float(getattr(sizes_cfg, "s_max", 3.0))
    n_bins = int(getattr(sizes_cfg, "n_bins", 40))
    alpha = float(getattr(cfg.psd, "alpha", 1.83))
    wavy_strength = float(getattr(cfg.psd, "wavy_strength", 0.0))
    alpha_mode = str(getattr(cfg.psd, "alpha_mode", "size"))
    psd_floor_mode = str(getattr(getattr(cfg.psd, "floor", None), "mode", "fixed"))
    rho_used = float(getattr(cfg.material, "rho", 3000.0))

    T_init = float(temp_runtime.initial_value)

    def _lookup_qpr(size: float, T_use: float) -> float:
        size_eff = max(float(size), 1.0e-12)
        if qpr_override is not None:
            return float(qpr_override)
        return float(radiation.qpr_lookup(size_eff, T_use))

    def _resolve_blowout(size_floor: float, T_use: float) -> tuple[float, float, float]:
        if qpr_override is not None:
            qpr_val = float(qpr_override)
            s_blow_val = radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val)
            s_blow_raw = float(max(s_blow_val, 1.0e-12))
            return qpr_val, s_blow_raw, float(max(size_floor, s_blow_raw))
        s_eval = float(max(size_floor, 1.0e-12))
        for _ in range(6):
            qpr_val = float(radiation.qpr_lookup(s_eval, T_use))
            s_blow_val = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val))
            s_eval = float(max(s_blow_val, 1.0e-12))
        qpr_final = float(radiation.qpr_lookup(s_eval, T_use))
        s_blow_final = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_final))
        s_blow_raw = float(max(s_blow_final, 1.0e-12))
        return qpr_final, s_blow_raw, float(max(size_floor, s_blow_raw))

    def _psd_mass_peak(psd_state: Dict[str, np.ndarray | float]) -> float:
        try:
            sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
            number_arr = np.asarray(psd_state.get("number"), dtype=float)
        except Exception:
            return float("nan")
        if sizes_arr.size == 0 or number_arr.size != sizes_arr.size:
            return float("nan")
        mass_proxy = sizes_arr**3 * number_arr
        if mass_proxy.size == 0:
            return float("nan")
        idx = int(np.argmax(mass_proxy))
        if idx < 0 or idx >= sizes_arr.size:
            return float("nan")
        return float(sizes_arr[idx])

    qpr_blow_init, a_blow_init, a_blow_effective_init = _resolve_blowout(s_min_config, T_init)
    s_min_effective = float(max(s_min_config, a_blow_effective_init))
    psd_state_template = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=s_max_config,
        alpha=alpha,
        wavy_strength=wavy_strength,
        n_bins=n_bins,
        rho=rho_used,
        alpha_mode=alpha_mode,
    )
    s0_mode_value = str(getattr(cfg.initial, "s0_mode", "upper"))
    if s0_mode_value.startswith("melt_"):
        melt_cfg = getattr(cfg.initial, "melt_psd", None)
        if melt_cfg is None:
            raise ConfigurationError("initial.s0_mode requested melt PSD but initial.melt_psd is missing")
        if s0_mode_value == "melt_lognormal_mixture":
            mass_weights = psd.mass_weights_lognormal_mixture(
                psd_state_template["sizes"],
                psd_state_template["widths"],
                f_fine=getattr(melt_cfg, "f_fine", 0.0),
                s_fine=getattr(melt_cfg, "s_fine", 1.0e-4),
                s_meter=getattr(melt_cfg, "s_meter", 1.5),
                width_dex=getattr(melt_cfg, "width_dex", 0.3),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
        elif s0_mode_value == "melt_truncated_powerlaw":
            mass_weights = psd.mass_weights_truncated_powerlaw(
                psd_state_template["sizes"],
                psd_state_template["widths"],
                alpha_solid=getattr(melt_cfg, "alpha_solid", 3.5),
                s_min_solid=getattr(melt_cfg, "s_min_solid", s_min_effective),
                s_max_solid=getattr(melt_cfg, "s_max_solid", s_max_config),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
        else:
            raise ConfigurationError(f"Unknown initial.s0_mode={s0_mode_value!r}")
        psd_state_template = psd.apply_mass_weights(
            psd_state_template,
            mass_weights,
            rho=rho_used,
        )
        psd_state_template["s_min"] = s_min_effective
    psd.sanitize_and_normalize_number(psd_state_template, normalize=False)

    kappa_surf_initial = ensure_finite_kappa(psd.compute_kappa(psd_state_template), label="kappa_surf_initial")
    kappa_eff0 = kappa_surf_initial
    optical_depth_cfg = getattr(cfg, "optical_depth", None)
    optical_depth_enabled = optical_depth_cfg is not None
    optical_tau0_target = None
    optical_tau_stop = None
    optical_tau_stop_tol = None
    sigma_surf0_target = None
    if optical_depth_enabled:
        optical_tau0_target = float(getattr(optical_depth_cfg, "tau0_target", 1.0))
        optical_tau_stop = float(getattr(optical_depth_cfg, "tau_stop", 1.0))
        optical_tau_stop_tol = float(getattr(optical_depth_cfg, "tau_stop_tol", 1.0e-6))
        if optical_tau0_target <= 0.0 or not math.isfinite(optical_tau0_target):
            raise ConfigurationError("optical_depth.tau0_target must be positive and finite")
        if optical_tau_stop <= 0.0 or not math.isfinite(optical_tau_stop):
            raise ConfigurationError("optical_depth.tau_stop must be positive and finite")
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

    if sigma_surf0_target is None:
        raise ConfigurationError("1D runs require optical_depth to set Sigma_surf0")

    sigma_surf0 = np.full_like(r_vals, sigma_surf0_target, dtype=float)
    sigma_surf = sigma_surf0.copy()
    sigma_deep = np.zeros_like(r_vals, dtype=float)
    sigma_surf0_avg = float(np.sum(sigma_surf0 * area_vals) / max(np.sum(area_vals), 1.0))

    sigma_midplane = np.full_like(r_vals, float("nan"), dtype=float)
    sigma_midplane_avg = float("nan")
    if cfg.disk is not None and cfg.inner_disk_mass is not None:
        if cfg.inner_disk_mass.use_Mmars_ratio:
            M_in = cfg.inner_disk_mass.M_in_ratio * constants.M_MARS
        else:
            M_in = cfg.inner_disk_mass.M_in_ratio
        sigma_func = initfields.sigma_from_Minner(
            M_in,
            r_in_m,
            r_out_m,
            cfg.disk.geometry.p_index,
        )
        sigma_midplane = np.array([sigma_func(r) for r in r_vals], dtype=float)
        sigma_midplane_avg = float(np.sum(sigma_midplane * area_vals) / max(np.sum(area_vals), 1.0))

    psd_state_base = dict(psd_state_template)
    number_template = np.asarray(psd_state_template.get("number"), dtype=float)
    psd_states: List[Dict[str, np.ndarray | float]] = []
    for _ in range(n_cells):
        psd_state = dict(psd_state_base)
        number_copy = number_template.copy()
        psd_state["number"] = number_copy
        psd_state["n"] = number_copy
        psd_states.append(psd_state)
    kappa_surf_cells = np.full(n_cells, kappa_surf_initial, dtype=float)
    kappa_eff_cells = np.full(n_cells, kappa_eff0, dtype=float)
    tau_los_cells = np.full(n_cells, kappa_surf_initial * sigma_surf0_target * los_factor, dtype=float)
    sigma_tau1_cells = np.full(
        n_cells,
        shielding.sigma_tau1(kappa_eff0) if kappa_eff0 > 0.0 else float("inf"),
        dtype=float,
    )

    mass_initial_cell = sigma_surf0 * area_vals / constants.M_MARS
    mass_initial_total = float(np.sum(mass_initial_cell))
    M_loss_cum = np.zeros(n_cells, dtype=float)
    M_sink_cum = np.zeros(n_cells, dtype=float)
    M_spill_cum = np.zeros(n_cells, dtype=float)
    cell_active = np.ones(n_cells, dtype=bool)
    cell_solid_state = np.zeros(n_cells, dtype=bool)
    cell_stop_reason: List[Optional[str]] = [None] * n_cells
    cell_stop_time = np.full(n_cells, float("nan"), dtype=float)
    cell_stop_tau = np.full(n_cells, np.nan)
    frozen_records: List[Optional[Dict[str, Any]]] = [None] * n_cells
    temperature_track: List[float] = []
    beta_track: List[float] = []
    ablow_track: List[float] = []
    blowout_effective_warned = False
    supply_rate_nominal_track: List[float] = []
    supply_rate_scaled_track: List[float] = []
    supply_rate_applied_track: List[float] = []
    supply_headroom_track: List[float] = []
    supply_clip_factor_track: List[float] = []
    supply_visibility_track: List[float] = []
    supply_blocked_track: List[float] = []
    supply_mixing_track: List[float] = []
    supply_spill_rate_track: List[float] = []
    supply_feedback_track: List[float] = []
    supply_temperature_track: List[float] = []
    supply_reservoir_remaining_track: List[float] = []
    dt_over_t_blow_track: List[float] = []
    supply_rate_scaled_initial: Optional[float] = None
    supply_rate_nominal_time_sum = 0.0
    supply_rate_scaled_time_sum = 0.0
    supply_rate_applied_time_sum = 0.0
    supply_headroom_time_sum = 0.0
    supply_clip_factor_time_sum = 0.0
    supply_visibility_time_sum = 0.0
    supply_spill_rate_time_sum = 0.0
    supply_spill_active_time_sum = 0.0
    supply_blocked_time_sum = 0.0
    supply_mixing_time_sum = 0.0
    total_time_weight_sum = 0.0
    M_sublimation_cum = 0.0
    orbit_rollup_enabled = bool(getattr(cfg.numerics, "orbit_rollup", True))
    orbit_rollup_rows: List[Dict[str, Any]] = []
    orbit_time_accum = 0.0
    orbit_loss_blow = 0.0
    orbit_loss_sink = 0.0
    orbits_completed = 0

    qpr_at_smin_config = _lookup_qpr(s_min_config, T_init)
    qpr_mean_init = _lookup_qpr(s_min_effective, T_init)
    beta_at_smin_config = radiation.beta(s_min_config, rho_used, T_init, Q_pr=qpr_at_smin_config)
    beta_at_smin_effective = radiation.beta(s_min_effective, rho_used, T_init, Q_pr=qpr_mean_init)
    beta_threshold = radiation.BLOWOUT_BETA_THRESHOLD
    case_status = "blowout" if beta_at_smin_config >= beta_threshold else "ok"
    if not blowout_enabled:
        case_status = "no_blowout"
    T_use_last = T_init
    qpr_mean_last = qpr_mean_init
    a_blow_last = a_blow_init
    s_min_effective_last = s_min_effective

    chi_config_raw = getattr(cfg, "chi_blow", 1.0)
    if isinstance(chi_config_raw, str):
        if chi_config_raw.lower() != "auto":
            raise ConfigurationError("chi_blow string value must be 'auto'")
        chi_blow_eff = _auto_chi_blow(beta_at_smin_effective, qpr_mean_init)
    else:
        chi_blow_eff = float(chi_config_raw)
        if chi_blow_eff <= 0.0:
            raise ConfigurationError("chi_blow must be positive")
    chi_blow_eff = float(min(max(chi_blow_eff, 0.5), 2.0))
    t_blow_vals = np.where(Omega_vals > 0.0, chi_blow_eff / Omega_vals, float("inf"))

    sub_params_base = SublimationParams(**cfg.sinks.sub_params.model_dump())
    sub_params_cells: List[SublimationParams] = []
    for r_val, t_orb_val, Omega_val in zip(r_vals, t_orb_vals, Omega_vals):
        sub_params = copy.deepcopy(sub_params_base)
        setattr(sub_params, "runtime_orbital_radius_m", float(r_val))
        setattr(sub_params, "runtime_t_orb_s", float(t_orb_val))
        setattr(sub_params, "runtime_Omega", float(Omega_val))
        sub_params_cells.append(sub_params)

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
    sublimation_enabled_cfg = bool(getattr(cfg.sinks, "enable_sublimation", False)) if sinks_enabled_cfg else False
    gas_drag_enabled_cfg = bool(getattr(cfg.sinks, "enable_gas_drag", False)) if sinks_enabled_cfg else False
    sink_opts = sinks.SinkOptions(
        enable_sublimation=sublimation_enabled_cfg,
        sub_params=sub_params_base,
        enable_gas_drag=gas_drag_enabled_cfg,
        rho_g=cfg.sinks.rho_g if gas_drag_enabled_cfg else 0.0,
    )

    collisions_active = physics_mode != "sublimation_only"
    sinks_active = sinks_enabled_cfg and physics_mode != "collisions_only"

    supply_spec_base = cfg.supply
    supply_enabled_cfg = bool(getattr(supply_spec_base, "enabled", True))
    supply_mode_value = getattr(supply_spec_base, "mode", "const")
    supply_epsilon_mix = getattr(getattr(supply_spec_base, "mixing", None), "epsilon_mix", None)
    supply_mu_orbit_cfg = getattr(getattr(supply_spec_base, "const", None), "mu_orbit10pct", None)
    supply_orbit_fraction = getattr(getattr(supply_spec_base, "const", None), "orbit_fraction_at_mu1", None)
    supply_injection_cfg = getattr(supply_spec_base, "injection", None)
    supply_injection_mode = getattr(supply_injection_cfg, "mode", "min_bin") if supply_injection_cfg else "min_bin"
    supply_injection_s_min = getattr(supply_injection_cfg, "s_inj_min", None) if supply_injection_cfg else None
    supply_injection_s_max = getattr(supply_injection_cfg, "s_inj_max", None) if supply_injection_cfg else None
    supply_injection_q = float(getattr(supply_injection_cfg, "q", 3.5)) if supply_injection_cfg else 3.5
    supply_velocity_cfg = getattr(supply_injection_cfg, "velocity", None) if supply_injection_cfg else None
    supply_injection_weights = None
    if supply_injection_mode == "initial_psd":
        sizes_arr = np.asarray(psd_state_template.get("sizes"), dtype=float)
        widths_arr = np.asarray(psd_state_template.get("widths"), dtype=float)
        number_raw = psd_state_template.get("number")
        if number_raw is None:
            number_raw = psd_state_template.get("n")
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

    supply_headroom_policy = str(getattr(supply_spec_base, "headroom_policy", "clip") or "clip").lower()
    supply_headroom_enabled = supply_headroom_policy not in {"none", "off", "disabled"}
    if optical_depth_enabled and supply_headroom_enabled:
        supply_headroom_policy = "none"
        supply_headroom_enabled = False

    supply_transport_cfg = getattr(supply_spec_base, "transport", None)
    supply_transport_mode = getattr(supply_transport_cfg, "mode", "direct") if supply_transport_cfg else "direct"
    supply_transport_headroom_gate = (
        getattr(supply_transport_cfg, "headroom_gate", "hard") if supply_transport_cfg else "hard"
    )
    supply_deep_tmix_orbits = (
        getattr(supply_transport_cfg, "t_mix_orbits", None) if supply_transport_cfg else None
    )
    if supply_deep_tmix_orbits is None and supply_injection_cfg is not None:
        supply_deep_tmix_orbits = getattr(supply_injection_cfg, "deep_reservoir_tmix_orbits", None)
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
    supply_visibility_eps = 1.0e-30
    supply_headroom_eps = 1.0e-18

    supply_specs: List[Any] = []
    supply_states: List[Any] = []
    for idx in range(n_cells):
        spec = copy.deepcopy(supply_spec_base)
        if supply_enabled_cfg and supply_mode_value == "const" and supply_mu_orbit_cfg is not None:
            if supply_epsilon_mix is None or supply_epsilon_mix <= 0.0:
                raise ConfigurationError("supply.mixing.epsilon_mix must be positive when using mu_orbit10pct")
            orbit_fraction = 0.10 if supply_orbit_fraction is None else float(supply_orbit_fraction)
            if orbit_fraction <= 0.0 or not math.isfinite(orbit_fraction):
                raise ConfigurationError("supply.const.orbit_fraction_at_mu1 must be positive and finite")
            if sigma_surf_mu_ref is None or not math.isfinite(sigma_surf_mu_ref):
                raise ConfigurationError("mu_orbit10pct requires a finite Sigma_ref from mu_reference_tau")
            dotSigma_target = float(supply_mu_orbit_cfg) * orbit_fraction * sigma_surf_mu_ref / float(t_orb_vals[idx])
            supply_const_rate = dotSigma_target / float(supply_epsilon_mix)
            if hasattr(spec, "const"):
                setattr(spec.const, "prod_area_rate_kg_m2_s", float(supply_const_rate))
        supply_specs.append(spec)
        supply_states.append(supply.init_runtime_state(spec, area_vals[idx], seconds_per_year=SECONDS_PER_YEAR))

    phase_cfg = getattr(cfg, "phase", None)
    phase_controller = phase_mod.PhaseEvaluator.from_config(phase_cfg, logger=logger)
    phase_temperature_input_mode = str(getattr(phase_cfg, "temperature_input", "mars_surface") if phase_cfg else "mars_surface")
    phase_q_abs_mean = float(getattr(phase_cfg, "q_abs_mean", 0.4) if phase_cfg else 0.4)
    phase_tau_field = str(getattr(phase_cfg, "tau_field", "los") if phase_cfg else "los").strip().lower()
    if phase_temperature_input_mode:
        phase_temperature_input_mode = phase_temperature_input_mode.strip().lower()
    if phase_temperature_input_mode not in {"mars_surface", "particle"}:
        phase_temperature_input_mode = "mars_surface"
    if phase_tau_field != "los":
        phase_tau_field = "los"
    allow_liquid_hkl = bool(getattr(phase_cfg, "allow_liquid_hkl", True)) if phase_cfg else True
    dt_min_tcoll_ratio = getattr(cfg.numerics, "dt_min_tcoll_ratio", 0.5)
    if dt_min_tcoll_ratio is not None:
        dt_min_tcoll_ratio = float(dt_min_tcoll_ratio)

    t_end, dt_nominal, dt_initial_step, n_steps, time_grid_info = _resolve_time_grid(
        cfg.numerics,
        Omega_ref,
        t_orb_ref,
        temp_runtime=temp_runtime,
    )
    dt = float(dt_initial_step)
    max_steps = MAX_STEPS
    if n_steps > max_steps:
        n_steps = max_steps
        dt = t_end / n_steps
        time_grid_info["n_steps"] = n_steps
        time_grid_info["dt_step"] = dt
        time_grid_info["dt_capped_by_max_steps"] = True

    run_config_path = outdir / "run_config.json"
    run_config_snapshot = {
        "status": "pre_run",
        "outdir": str(outdir),
        "config_source_path": str(config_source_path) if config_source_path else None,
        "geometry_source": geometry_source,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "config": cfg.model_dump(mode="json"),
        "init_ei": init_ei_snapshot,
    }
    run_config_snapshot["cell_parallel"] = cell_parallel_info
    auto_tune_info = getattr(cfg, "_auto_tune_info", None)
    if auto_tune_info is not None:
        run_config_snapshot["auto_tune"] = auto_tune_info
    writer.write_run_config(run_config_snapshot, run_config_path)

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

    history = ZeroDHistory()
    streaming_state = StreamingState(
        enabled=streaming_enabled,
        outdir=Path(cfg.io.outdir),
        merge_outdir=streaming_merge_outdir,
        compression=streaming_compression,
        memory_limit_gb=streaming_memory_limit_gb,
        step_flush_interval=streaming_step_interval,
        merge_at_end=streaming_merge_at_end,
        cleanup_chunks=streaming_cleanup_chunks,
    )
    steps_since_flush = 0

    run_rows_est = n_steps * n_cells
    mem_short, mem_long = _memory_estimate(run_rows_est, n_bins)
    progress_enabled = bool(getattr(cfg.io.progress, "enable", False))
    progress = ProgressReporter(
        n_steps,
        t_end,
        refresh_seconds=float(getattr(cfg.io.progress, "refresh_seconds", 1.0) or 1.0),
        enabled=progress_enabled,
        memory_hint=mem_short,
        memory_header=mem_long,
    )
    progress.emit_header()

    time = 0.0
    step_no = 0
    mass_budget_max_error = 0.0
    early_stop_reason = None
    loop_exit_reason: Optional[str] = None

    try:
        while time < t_end and step_no < max_steps:
            if dt <= 0.0 or not math.isfinite(dt):
                loop_exit_reason = "dt_invalid"
                break
            dt = min(dt, t_end - time)
            if dt <= 0.0:
                loop_exit_reason = "t_end_reached"
                break

            T_use = float(temp_runtime.evaluate(time))
            rad_flux_step = constants.SIGMA_SB * (T_use ** 4)
            qpr_blow_step, a_blow_step, a_blow_effective_step = _resolve_blowout(s_min_config, T_use)
            if (
                not blowout_effective_warned
                and a_blow_effective_step > a_blow_step * (1.0 + 1.0e-12)
            ):
                warnings.warn(
                    "s_blow_m now records the raw blow-out radius; use s_blow_m_effective for the "
                    "size-floor-clipped value.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                blowout_effective_warned = True
            s_min_effective = float(max(s_min_config, a_blow_effective_step))
            qpr_mean_step = _lookup_qpr(s_min_effective, T_use)
            beta_at_smin_effective = radiation.beta(
                s_min_effective, rho_used, T_use, Q_pr=qpr_mean_step
            )
            beta_gate_active = beta_at_smin_effective >= beta_threshold
            temperature_track.append(T_use)
            beta_track.append(beta_at_smin_effective)
            ablow_track.append(a_blow_step)
            T_use_last = T_use
            qpr_mean_last = qpr_mean_step
            a_blow_last = a_blow_step
            s_min_effective_last = s_min_effective
            step_end_time = time + dt
            if bool(getattr(cfg.numerics, "stop_on_blowout_below_smin", False)) and a_blow_step <= s_min_config:
                early_stop_reason = "a_blow_below_s_min_config"
                break

            t_coll_min = float("inf")
            step_records = []
            step_diagnostics = []
            step_out_mass = 0.0
            step_sink_mass = 0.0
            step_sublimation_mass = 0.0
            step_area_sum = 0.0
            step_supply_rate_nominal_sum = 0.0
            step_supply_rate_scaled_sum = 0.0
            step_supply_rate_applied_sum = 0.0
            step_supply_headroom_sum = 0.0
            step_supply_clip_factor_sum = 0.0
            step_supply_visibility_sum = 0.0
            step_supply_spill_rate_sum = 0.0
            step_supply_feedback_sum = 0.0
            step_supply_temperature_sum = 0.0
            step_supply_reservoir_remaining_sum = 0.0
            step_dt_over_t_blow_sum = 0.0
            step_supply_blocked_area_sum = 0.0
            step_supply_mixing_area_sum = 0.0

            def _run_cell_indices(indices):
                local_step_records = []
                local_step_diagnostics = []
                local_step_out_mass = 0.0
                local_step_sink_mass = 0.0
                local_step_sublimation_mass = 0.0
                local_step_area_sum = 0.0
                local_step_supply_rate_nominal_sum = 0.0
                local_step_supply_rate_scaled_sum = 0.0
                local_step_supply_rate_applied_sum = 0.0
                local_step_supply_headroom_sum = 0.0
                local_step_supply_clip_factor_sum = 0.0
                local_step_supply_visibility_sum = 0.0
                local_step_supply_spill_rate_sum = 0.0
                local_step_supply_feedback_sum = 0.0
                local_step_supply_temperature_sum = 0.0
                local_step_supply_reservoir_remaining_sum = 0.0
                local_step_dt_over_t_blow_sum = 0.0
                local_step_supply_blocked_area_sum = 0.0
                local_step_supply_mixing_area_sum = 0.0
                local_psd_hist_records = []
                local_mass_budget_cells = []
                local_supply_rate_scaled_initial = None
                local_t_coll_min = float('inf')
                for idx in indices:
                    r_val = float(r_vals[idx])
                    r_rm = float(r_rm_vals[idx])
                    Omega_val = float(Omega_vals[idx])
                    t_orb_val = float(t_orb_vals[idx])
                    area_val = float(area_vals[idx])

                    psd_state = psd_states[idx]
                    sigma_val = float(sigma_surf[idx])
                    sigma_mid = float(sigma_midplane[idx]) if math.isfinite(sigma_midplane[idx]) else None
                    sigma_deep_val = float(sigma_deep[idx])
                    t_mix_seconds = None
                    if supply_deep_enabled and supply_deep_tmix_orbits is not None:
                        try:
                            t_mix_seconds = float(supply_deep_tmix_orbits) * t_orb_val
                        except Exception:
                            t_mix_seconds = None
                    supply_diag = None
                    prod_rate_raw_current = 0.0
                    supply_rate_nominal_current = 0.0
                    supply_rate_scaled_current = 0.0
                    supply_rate_applied_current = 0.0
                    prod_rate_diverted_current = 0.0
                    prod_rate_into_deep_current = 0.0
                    deep_to_surf_flux_attempt_current = 0.0
                    deep_to_surf_flux_current = 0.0
                    headroom_current = None
                    clip_factor_current = None
                    visibility_factor_current = None
                    supply_blocked_by_headroom_flag = False
                    supply_mixing_limited_flag = False
                    spill_rate_current = 0.0
                    mass_loss_spill_step = 0.0
                    t_coll_step = None
                    ts_ratio_value = None
                    t_solid_step = None
                    gate_factor = 1.0
                    tau_gate_block_step = False
                    phase_allows_step = True
                    sink_selected = "none"
                    ds_dt_raw = None
                    ds_dt_val = 0.0
                    t_sink_total_value = None
                    t_sink_surface_only = None
                    t_sink_sublimation_value = None
                    t_sink_gas_drag_value = None
                    T_p_effective = None
                    temperature_for_phase = T_use
                    tau_phase_used = None
                    tau_phase_los = None
                    phase_state = None
                    phase_method = None
                    phase_reason = None
                    phase_payload = {}
                    phase_f_vap = None
                    phase_bulk_state = None
                    phase_bulk_f_liquid = None
                    phase_bulk_f_solid = None
                    phase_bulk_f_vapor = None
                    sublimation_blocked_by_phase = False
                    e_kernel_used = None
                    i_kernel_used = None
                    e_kernel_base = None
                    i_kernel_base = None
                    e_kernel_supply = None
                    i_kernel_supply = None
                    e_kernel_effective = None
                    i_kernel_effective = None
                    e_state_next = None
                    i_state_next = None
                    e_eq_target = None
                    t_damp_used = None
                    supply_velocity_weight = None

                    if not cell_active[idx]:
                        frozen_record = frozen_records[idx]
                        if frozen_record is not None:
                            record = dict(frozen_record)
                            record["time"] = time + dt
                            record["dt"] = dt
                            record["cell_active"] = False
                            record["active_mask"] = False
                        else:
                            tau_los_inactive = (
                                float(tau_los_cells[idx]) if math.isfinite(tau_los_cells[idx]) else 0.0
                            )
                            record = {
                                "time": time + dt,
                                "dt": dt,
                                "cell_index": idx,
                                "cell_active": False,
                                "active_mask": False,
                                "r_m": r_val,
                                "r_RM": r_rm,
                                "r_orbit_RM": r_rm,
                                "r_source": geometry_source,
                                "Omega_s": Omega_val,
                                "t_orb_s": t_orb_val,
                                "t_blow_s": float(t_blow_vals[idx]),
                                "t_blow": float(t_blow_vals[idx]),
                                "T_M_used": T_use,
                                "T_M_source": T_M_source,
                                "T_p_effective": None,
                                "phase_temperature_input": phase_temperature_input_mode,
                                "rad_flux_Mars": rad_flux_step,
                                "tau": tau_los_inactive,
                                "tau_los_mars": tau_los_inactive,
                                "a_blow": a_blow_step,
                                "a_blow_step": a_blow_step,
                                "a_blow_at_smin": a_blow_step,
                                "s_min": s_min_effective,
                                "kappa": float(kappa_eff_cells[idx]),
                                "kappa_eff": float(kappa_eff_cells[idx]),
                                "kappa_surf": float(kappa_surf_cells[idx]),
                                "Qpr_mean": qpr_mean_step,
                                "Q_pr_at_smin": qpr_mean_step,
                                "beta_at_smin_config": beta_at_smin_config,
                                "beta_at_smin_effective": beta_at_smin_effective,
                                "beta_at_smin": beta_at_smin_effective,
                                "beta_threshold": beta_threshold,
                                "Sigma_surf": sigma_val,
                                "sigma_surf": sigma_val,
                                "Sigma_tau1": float(sigma_tau1_cells[idx]) if math.isfinite(sigma_tau1_cells[idx]) else None,
                                "Sigma_tau1_active": float(sigma_tau1_cells[idx])
                                if math.isfinite(sigma_tau1_cells[idx])
                                else None,
                                "sigma_tau1": float(sigma_tau1_cells[idx]) if math.isfinite(sigma_tau1_cells[idx]) else None,
                                "Sigma_tau1_last_finite": float(sigma_tau1_cells[idx])
                                if math.isfinite(sigma_tau1_cells[idx])
                                else None,
                                "Sigma_midplane": sigma_mid,
                                "sigma_deep": sigma_deep_val,
                                "headroom": None,
                                "outflux_surface": 0.0,
                                "sink_flux_surface": 0.0,
                                "prod_subblow_area_rate": 0.0,
                                "M_out_dot": 0.0,
                                "M_sink_dot": 0.0,
                                "dM_dt_surface_total": 0.0,
                                "dSigma_dt_blowout": 0.0,
                                "dSigma_dt_sinks": 0.0,
                                "dSigma_dt_total": 0.0,
                                "dSigma_dt_sublimation": 0.0,
                                "M_loss_cum": float(M_loss_cum[idx] + M_sink_cum[idx]),
                                "mass_total_bins": float(sigma_val * area_val / constants.M_MARS),
                                "mass_lost_by_blowout": float(M_loss_cum[idx]),
                                "mass_lost_by_sinks": float(M_sink_cum[idx]),
                                "M_sink_cum": float(M_sink_cum[idx]),
                                "dt_over_t_blow": 0.0,
                                "fast_blowout_factor": 0.0,
                                "fast_blowout_flag_gt3": False,
                                "fast_blowout_flag_gt10": False,
                                "fast_blowout_corrected": False,
                                "dSigma_dt_sublimation": 0.0,
                                "mass_lost_sinks_step": 0.0,
                                "mass_lost_sublimation_step": 0.0,
                                "mass_lost_tau_clip_spill_step": 0.0,
                                "cum_mass_lost_tau_clip_spill": float(M_spill_cum[idx]),
                                "mass_lost_surface_solid_marsRP_step": 0.0,
                                "M_loss_rp_mars": float(M_loss_cum[idx]),
                                "M_loss_surface_solid_marsRP": float(M_loss_cum[idx]),
                                "M_loss_hydro": 0.0,
                                "fast_blowout_ratio": 0.0,
                                "n_substeps": 1,
                                "substep_active": False,
                                "chi_blow_eff": chi_blow_eff,
                                "case_status": case_status,
                                "s_blow_m": a_blow_step,
                                "s_blow_m_effective": a_blow_effective_step,
                                "rho_used": rho_used,
                                "Q_pr_used": qpr_mean_step,
                                "Q_pr_blow": qpr_blow_step,
                                "s_min_effective": s_min_effective,
                                "s_min_config": s_min_config,
                                "s_min_effective_gt_config": s_min_effective > s_min_config,
                                "T_source": T_M_source,
                                "ds_dt_sublimation": 0.0,
                                "ds_dt_sublimation_raw": 0.0,
                                "phi_effective": None,
                                "phi_used": None,
                                "phase_tau_field": phase_tau_field,
                                "phase_state": None,
                                "phase_f_vap": None,
                                "phase_method": None,
                                "phase_reason": None,
                                "phase_bulk_state": None,
                                "phase_bulk_f_liquid": None,
                                "phase_bulk_f_solid": None,
                                "phase_bulk_f_vapor": None,
                                "tau_mars_line_of_sight": tau_los_inactive,
                                "tau_gate_blocked": False,
                                "blowout_beta_gate": beta_gate_active,
                                "blowout_phase_allowed": True,
                                "blowout_layer_mode": blowout_layer_mode,
                                "blowout_target_phase": blowout_target_phase,
                                "sink_selected": "none",
                                "sublimation_blocked_by_phase": False,
                                "Sigma_surf0": float(sigma_surf0[idx]),
                                "cell_stop_reason": cell_stop_reason[idx],
                                "cell_stop_time": float(cell_stop_time[idx]) if math.isfinite(cell_stop_time[idx]) else None,
                                "cell_stop_tau": float(cell_stop_tau[idx]) if math.isfinite(cell_stop_tau[idx]) else None,
                            }
                        _ensure_series_keys(record)
                        local_step_records.append(record)
                        tau_los_inactive = record.get("tau_los_mars")
                        diag_entry = {
                            "time": record["time"],
                            "dt": record["dt"],
                            "cell_index": idx,
                            "r_m_used": r_val,
                            "r_RM_used": r_rm,
                            "T_M_used": T_use,
                            "rad_flux_Mars": rad_flux_step,
                            "Omega_s": Omega_val,
                            "t_orb_s": t_orb_val,
                            "t_blow_s": float(t_blow_vals[idx]),
                            "sigma_surf": sigma_val,
                            "sigma_deep": sigma_deep_val,
                            "sigma_tau1": record.get("sigma_tau1"),
                            "sigma_tau1_active": record.get("Sigma_tau1_active"),
                            "Sigma_tau1_last_finite": record.get("Sigma_tau1_last_finite"),
                            "tau_los_mars": record.get("tau_los_mars"),
                            "tau_phase_los": None,
                            "tau_phase_used": None,
                            "phase_tau_field": phase_tau_field,
                            "kappa_eff": record.get("kappa_eff"),
                            "kappa_surf": record.get("kappa_surf"),
                            "phi_effective": None,
                            "psi_shield": None,
                            "kappa_Planck": record.get("kappa_surf"),
                            "tau_eff": None,
                            "s_min": s_min_effective,
                            "a_blow_at_smin": a_blow_step,
                            "beta_at_smin_effective": beta_at_smin_effective,
                            "beta_at_smin": beta_at_smin_effective,
                            "Q_pr_at_smin": qpr_mean_step,
                            "s_peak": _psd_mass_peak(psd_state),
                            "area_m2": area_val,
                            "prod_subblow_area_rate": 0.0,
                            "prod_subblow_area_rate_raw": 0.0,
                            "supply_rate_nominal": 0.0,
                            "supply_rate_scaled": 0.0,
                            "supply_rate_applied": 0.0,
                            "supply_tau_clip_spill_rate": 0.0,
                            "supply_headroom": None,
                            "supply_clip_factor": None,
                            "headroom": None,
                            "prod_rate_raw": 0.0,
                            "prod_rate_applied_to_surf": 0.0,
                            "prod_rate_diverted_to_deep": 0.0,
                            "prod_rate_into_deep": 0.0,
                            "deep_to_surf_flux_attempt": 0.0,
                            "deep_to_surf_flux": 0.0,
                            "deep_to_surf_flux_applied": 0.0,
                            "supply_visibility_factor": None,
                            "supply_blocked_by_headroom": False,
                            "supply_mixing_limited": False,
                            "supply_transport_mode": supply_transport_mode,
                            "supply_temperature_scale": None,
                            "supply_temperature_value": None,
                            "supply_temperature_value_kind": None,
                            "supply_feedback_scale": None,
                            "supply_feedback_error": None,
                            "supply_reservoir_remaining_Mmars": None,
                            "supply_reservoir_fraction": None,
                            "supply_reservoir_clipped": False,
                            "s_min_effective": s_min_effective,
                            "qpr_mean": qpr_mean_step,
                            "chi_blow_eff": chi_blow_eff,
                            "ds_step_uniform": None,
                            "mass_ratio_uniform": None,
                            "M_out_cum": float(M_loss_cum[idx]),
                            "M_sink_cum": float(M_sink_cum[idx]),
                            "M_loss_cum": float(M_loss_cum[idx] + M_sink_cum[idx]),
                            "cum_mass_lost_tau_clip_spill": float(M_spill_cum[idx]),
                            "M_loss_surface_solid_marsRP": float(M_loss_cum[idx]),
                            "M_hydro_cum": 0.0,
                            "phase_state": None,
                            "phase_method": None,
                            "phase_reason": None,
                            "phase_f_vap": None,
                            "phase_bulk_state": None,
                            "phase_bulk_f_liquid": None,
                            "phase_bulk_f_solid": None,
                            "phase_bulk_f_vapor": None,
                            "phase_payload": {},
                            "ds_dt_sublimation": 0.0,
                            "ds_dt_sublimation_raw": 0.0,
                            "sublimation_blocked_by_phase": False,
                            "tau_mars_line_of_sight": tau_los_inactive,
                            "tau_gate_blocked": False,
                            "blowout_beta_gate": beta_gate_active,
                            "blowout_phase_allowed": True,
                            "blowout_layer_mode": blowout_layer_mode,
                            "blowout_target_phase": blowout_target_phase,
                            "sink_selected": "none",
                            "hydro_timescale_s": None,
                            "mass_loss_surface_solid_step": 0.0,
                            "blowout_gate_factor": 1.0,
                        }
                        _ensure_diagnostic_keys(diag_entry)
                        local_step_diagnostics.append(diag_entry)
                        local_step_area_sum += area_val
                        local_step_dt_over_t_blow_sum += 0.0
                        continue

                    if not math.isfinite(sigma_val):
                        sigma_val = 0.0

                    psd_state["s_min"] = s_min_effective
                    if getattr(cfg.radiation, "freeze_kappa", False):
                        kappa_surf = kappa_surf_initial
                    else:
                        kappa_surf = ensure_finite_kappa(psd.compute_kappa(psd_state), label="kappa_surf_step")

                    tau_phase_used, tau_phase_los = compute_phase_tau_fields(
                        kappa_surf,
                        sigma_val,
                        los_factor,
                        phase_tau_field,
                    )

                    if phase_temperature_input_mode == "particle":
                        T_p_effective = phase_mod.particle_temperature_equilibrium(
                            T_use,
                            r_val,
                            phase_q_abs_mean,
                        )
                        temperature_for_phase = T_p_effective
                    else:
                        temperature_for_phase = T_use

                    phase_decision, phase_bulk = phase_controller.evaluate_with_bulk(
                        temperature_for_phase,
                        tau=tau_phase_used,
                        radius_m=r_val,
                        time_s=time,
                        T0_K=temp_runtime.initial_value,
                    )
                    phase_state = phase_decision.state
                    phase_method = phase_decision.method
                    phase_reason = phase_decision.reason
                    phase_payload = dict(phase_decision.payload)
                    phase_f_vap = phase_decision.f_vap
                    phase_bulk_state = phase_bulk.state
                    phase_bulk_f_liquid = phase_bulk.f_liquid
                    phase_bulk_f_solid = phase_bulk.f_solid
                    phase_bulk_f_vapor = phase_bulk.f_vapor
                    liquid_block_collisions = phase_bulk_state == "liquid_dominated"
                    collisions_active_step = collisions_active and not liquid_block_collisions
                    allow_supply_step = step_no > 0 and phase_state == "solid" and not liquid_block_collisions
                    cell_is_solid = phase_state == "solid"
                    cell_solid_state[idx] = bool(cell_is_solid)
                    tau_gate_block_step = bool(
                        tau_gate_enabled
                        and tau_phase_los is not None
                        and math.isfinite(tau_phase_los)
                        and tau_phase_los >= tau_gate_threshold
                    )
                    phase_allows_step = not (
                        blowout_target_phase == "solid_only" and phase_state != "solid"
                    )
                    enable_blowout_step = bool(
                        collisions_active_step
                        and blowout_enabled
                        and beta_gate_active
                        and phase_allows_step
                        and not tau_gate_block_step
                    )
                    sink_selected = "rp_blowout" if enable_blowout_step else "none"

                    ds_dt_val = 0.0
                    ds_dt_raw = 0.0
                    if sinks_active and sublimation_enabled_cfg:
                        sub_params = sub_params_cells[idx]
                        T_grain = grain_temperature_graybody(T_use, r_val)
                        try:
                            ds_dt_raw = sizes.eval_ds_dt_sublimation(T_grain, rho_used, sub_params)
                        except ValueError:
                            ds_dt_raw = 0.0
                        if phase_bulk_state == "liquid_dominated" and not allow_liquid_hkl and ds_dt_raw < 0.0:
                            ds_dt_val = 0.0
                            sublimation_blocked_by_phase = True
                        else:
                            ds_dt_val = ds_dt_raw

                    t_sink_step = None
                    sink_result = None
                    if sinks_active and (sublimation_enabled_cfg or gas_drag_enabled_cfg):
                        sub_params = sub_params_cells[idx]
                        sink_opts_cell = sinks.SinkOptions(
                            enable_sublimation=sublimation_enabled_cfg,
                            sub_params=sub_params,
                            enable_gas_drag=gas_drag_enabled_cfg,
                            rho_g=cfg.sinks.rho_g if gas_drag_enabled_cfg else 0.0,
                        )
                        sink_result = sinks.total_sink_timescale(
                            T_use,
                            rho_used,
                            Omega_val,
                            sink_opts_cell,
                            s_ref=SINK_REF_SIZE,
                        )
                        t_sink_total_value = sink_result.t_sink
                        if sink_result.components:
                            t_sink_sublimation_value = sink_result.components.get("sublimation")
                            t_sink_gas_drag_value = sink_result.components.get("gas_drag")
                            non_sub_times: List[float] = []
                            for name, value in sink_result.components.items():
                                if name == "sublimation":
                                    continue
                                val = _safe_float(value, default=float("nan"))
                                if math.isfinite(val) and val > 0.0:
                                    non_sub_times.append(val)
                            t_sink_surface_only = min(non_sub_times) if non_sub_times else None
                        t_sink_step = t_sink_total_value
                        if sublimation_to_smol:
                            t_sink_step = sink_result.components.get("gas_drag")

                    kappa_eff = kappa_surf
                    tau_los = tau_phase_los
                    if shielding_mode == "off":
                        kappa_eff = kappa_surf
                    elif shielding_mode in {"psitau", "table"} and phi_tau_fn is not None:
                        kappa_eff = shielding.effective_kappa(kappa_surf, tau_los, phi_tau_fn)
                    if kappa_eff <= 0.0 or not math.isfinite(kappa_eff):
                        kappa_eff = kappa_surf
                    sigma_tau1_limit = shielding.sigma_tau1(kappa_eff) if kappa_eff > 0.0 else None

                    prod_rate = 0.0
                    if supply_enabled_cfg:
                        spec = supply_specs[idx]
                        supply_state = supply_states[idx]
                        supply_diag = supply.evaluate_supply(
                            time,
                            r_val,
                            dt,
                            spec,
                            area=area_val,
                            state=supply_state,
                            tau_for_feedback=tau_los,
                            temperature_K=T_use,
                            apply_reservoir=allow_supply_step,
                        )
                        prod_rate_raw_current = supply_diag.rate if allow_supply_step else 0.0
                        supply_rate_nominal_current = supply_diag.mixed_rate if allow_supply_step else 0.0
                        supply_rate_scaled_current = supply_diag.rate if allow_supply_step else 0.0
                        if local_supply_rate_scaled_initial is None and math.isfinite(supply_diag.rate):
                            local_supply_rate_scaled_initial = float(supply_diag.rate)
                        split_res = supply.split_supply_with_deep_buffer(
                            prod_rate_raw_current,
                            dt,
                            sigma_val,
                            sigma_tau1_limit,
                            sigma_deep_val,
                            t_mix=t_mix_seconds,
                            deep_enabled=supply_deep_enabled,
                            transport_mode=supply_transport_mode,
                            headroom_gate=supply_transport_headroom_gate,
                            headroom_policy=supply_headroom_policy,
                            t_blow=float(t_blow_vals[idx]),
                        )
                        prod_rate = split_res.prod_rate_applied
                        supply_rate_applied_current = prod_rate
                        prod_rate_diverted_current = split_res.prod_rate_diverted
                        prod_rate_into_deep_current = split_res.prod_rate_into_deep
                        deep_to_surf_flux_attempt_current = split_res.deep_to_surf_flux_attempt
                        deep_to_surf_flux_current = split_res.deep_to_surf_rate
                        headroom_current = split_res.headroom
                        sigma_deep_val = split_res.sigma_deep
                        sigma_deep[idx] = sigma_deep_val
                    if (
                        supply_rate_scaled_current is not None
                        and math.isfinite(supply_rate_scaled_current)
                        and supply_rate_scaled_current > 0.0
                    ):
                        clip_factor_current = float(
                            max(supply_rate_applied_current, 0.0)
                            / max(supply_rate_scaled_current, 1.0e-30)
                        )
                    if prod_rate_raw_current is not None:
                        visibility_factor_current = float(
                            max(supply_rate_applied_current, 0.0)
                            / max(prod_rate_raw_current, supply_visibility_eps)
                        )
                    supply_blocked_by_headroom_flag = bool(
                        supply_headroom_enabled
                        and prod_rate_raw_current is not None
                        and prod_rate_raw_current > 0.0
                        and headroom_current is not None
                        and headroom_current <= supply_headroom_eps
                        and supply_rate_applied_current <= supply_visibility_eps
                    )
                    supply_mixing_limited_flag = bool(
                        supply_transport_mode == "deep_mixing"
                        and prod_rate_raw_current is not None
                        and prod_rate_raw_current > 0.0
                        and not supply_blocked_by_headroom_flag
                        and supply_rate_applied_current <= supply_visibility_eps
                    )

                    if collisions_active_step and getattr(cfg.surface, "collision_solver", "smol") != "smol":
                        raise ConfigurationError("1D runner supports collision_solver='smol' only")

                    outflux_surface = 0.0
                    sink_flux_surface = 0.0
                    mass_loss_sublimation_step = 0.0
                    smol_res = None
                    if collisions_active_step:
                        collision_ctx = collisions_smol.CollisionStepContext(
                            time_orbit=collisions_smol.TimeOrbitParams(
                                dt=dt,
                                Omega=Omega_val,
                                r=r_val,
                                t_blow=float(t_blow_vals[idx]),
                            ),
                            material=collisions_smol.MaterialParams(
                                rho=rho_used,
                                a_blow=a_blow_step,
                                s_min_effective=s_min_effective,
                            ),
                            dynamics=collisions_smol.DynamicsParams(
                                e_value=float(e_cells[idx]),
                                i_value=float(getattr(cfg.dynamics, "i0", 0.05)),
                                dynamics_cfg=(
                                    dynamics_cfg_cells[idx] if dynamics_cfg_cells is not None else cfg.dynamics
                                ),
                                tau_eff=tau_los,
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
                                enable_blowout=enable_blowout_step,
                                collisions_enabled=collisions_active_step,
                                mass_conserving_sublimation=bool(getattr(cfg.sinks.sub_params, "mass_conserving", False)),
                                headroom_policy=supply_headroom_policy,
                                sigma_tau1=sigma_tau1_limit,
                                t_sink=t_sink_step,
                                ds_dt_val=ds_dt_val if sublimation_to_smol else None,
                                energy_bookkeeping_enabled=False,
                                eps_restitution=float(getattr(cfg.dynamics, "eps_restitution", 0.5)),
                                f_ke_cratering=float(getattr(cfg.dynamics, "f_ke_cratering", 0.1)),
                                f_ke_fragmentation=getattr(cfg.dynamics, "f_ke_fragmentation", None),
                            ),
                            sigma_surf=sigma_val,
                        )
                        smol_res = collisions_smol.step_collisions(collision_ctx, psd_state)
                        psd_state = smol_res.psd_state
                        sigma_val = smol_res.sigma_after
                        outflux_surface = smol_res.dSigma_dt_blowout
                        sink_flux_surface = smol_res.dSigma_dt_sinks
                        spill_rate_current = smol_res.mass_loss_rate_spill
                        if spill_rate_current > 0.0 and dt > 0.0:
                            mass_loss_spill_step = spill_rate_current * dt * area_val / constants.M_MARS
                            M_spill_cum[idx] += mass_loss_spill_step
                        if smol_res.mass_loss_rate_sublimation is not None:
                            mass_loss_sublimation_step = smol_res.mass_loss_rate_sublimation * dt * area_val / constants.M_MARS
                        e_kernel_used = smol_res.e_kernel_used
                        i_kernel_used = smol_res.i_kernel_used
                        e_kernel_base = smol_res.e_kernel_base
                        i_kernel_base = smol_res.i_kernel_base
                        e_kernel_supply = smol_res.e_kernel_supply
                        i_kernel_supply = smol_res.i_kernel_supply
                        e_kernel_effective = smol_res.e_kernel_effective
                        i_kernel_effective = smol_res.i_kernel_effective
                        supply_velocity_weight = smol_res.supply_velocity_weight
                        e_state_next = smol_res.e_next
                        i_state_next = smol_res.i_next
                        e_eq_target = smol_res.e_eq_target
                        t_damp_used = smol_res.t_damp_used
                        if smol_res.t_coll_kernel is not None and math.isfinite(smol_res.t_coll_kernel):
                            local_t_coll_min = min(local_t_coll_min, float(smol_res.t_coll_kernel))
                    else:
                        surface_step = surface.step_surface_sink_only(
                            sigma_val,
                            prod_rate,
                            dt,
                            t_sink=t_sink_step,
                        )
                        sigma_val = surface_step.sigma_surf
                        outflux_surface = surface_step.outflux
                        sink_flux_surface = surface_step.sink_flux

                    if getattr(cfg.surface, "freeze_sigma", False):
                        sigma_val = float(sigma_surf0[idx])

                    sigma_val = _clamp_sigma_surf(sigma_val)

                    if getattr(cfg.radiation, "freeze_kappa", False):
                        kappa_surf = kappa_surf_initial
                    else:
                        kappa_surf = ensure_finite_kappa(psd.compute_kappa(psd_state), label="kappa_surf_update")
                    tau_los = kappa_surf * sigma_val * los_factor
                    if shielding_mode in {"psitau", "table"} and phi_tau_fn is not None:
                        kappa_eff = shielding.effective_kappa(kappa_surf, tau_los, phi_tau_fn)
                    else:
                        kappa_eff = kappa_surf
                    if not math.isfinite(kappa_eff) or kappa_eff <= 0.0:
                        kappa_eff = kappa_surf
                    sigma_tau1_limit = shielding.sigma_tau1(kappa_eff) if kappa_eff > 0.0 else None
                    kappa_surf_cells[idx] = float(kappa_surf)
                    kappa_eff_cells[idx] = float(kappa_eff)
                    tau_los_cells[idx] = float(tau_los) if math.isfinite(tau_los) else 0.0
                    sigma_tau1_cells[idx] = float(sigma_tau1_limit) if sigma_tau1_limit is not None else float("inf")
                    phi_effective = None
                    if kappa_surf > 0.0 and math.isfinite(kappa_surf):
                        phi_effective = kappa_eff / kappa_surf

                    t_blow = float(t_blow_vals[idx])
                    if blowout_gate_mode == "sublimation_competition":
                        if ds_dt_val < 0.0 and math.isfinite(ds_dt_val) and math.isfinite(s_min_effective):
                            candidate = s_min_effective / abs(ds_dt_val)
                            if candidate > 0.0 and math.isfinite(candidate):
                                t_solid_step = candidate
                    elif blowout_gate_mode == "collision_competition":
                        if tau_los > TAU_MIN and Omega_val > 0.0:
                            tau_vert = float(tau_los) / max(los_factor, 1.0)
                            if tau_vert > TAU_MIN:
                                candidate = 1.0 / (Omega_val * tau_vert)
                                if candidate > 0.0 and math.isfinite(candidate):
                                    t_solid_step = candidate
                        t_coll_candidate = None
                        if collisions_active_step and tau_los > TAU_MIN and Omega_val > 0.0:
                            if smol_res is not None:
                                t_coll_candidate = smol_res.t_coll_kernel
                        if t_coll_candidate is None:
                            try:
                                tau_vert = float(tau_los) / max(los_factor, 1.0)
                                if tau_vert > TAU_MIN:
                                    t_coll_candidate = surface.wyatt_tcoll_S1(tau_vert, Omega_val)
                                else:
                                    t_coll_candidate = None
                            except Exception:
                                t_coll_candidate = None
                            if (
                                t_coll_candidate is not None
                                and math.isfinite(t_coll_candidate)
                                and t_coll_candidate > 0.0
                            ):
                                t_coll_step = float(t_coll_candidate)
                        if (
                            t_coll_step is not None
                            and t_coll_step > 0.0
                            and t_blow > 0.0
                            and math.isfinite(t_blow)
                        ):
                            ts_ratio_value = float(t_blow / t_coll_step)
                        if t_coll_step is not None and math.isfinite(t_coll_step):
                            local_t_coll_min = min(local_t_coll_min, float(t_coll_step))

                    if gate_enabled and enable_blowout_step:
                        gate_factor = compute_gate_factor(t_blow, t_solid_step)
                        outflux_surface *= gate_factor

                    if optical_depth_enabled and optical_tau_stop is not None and cell_is_solid:
                        kappa_for_stop = kappa_eff if math.isfinite(kappa_eff) else kappa_surf
                        tau_stop_los_current = float(kappa_for_stop * sigma_val * los_factor)
                        if (
                            math.isfinite(tau_stop_los_current)
                            and tau_stop_los_current
                            > optical_tau_stop * (1.0 + float(optical_tau_stop_tol or 0.0))
                        ):
                            cell_active[idx] = False
                            cell_stop_tau[idx] = tau_stop_los_current
                            cell_stop_time[idx] = time + dt
                            cell_stop_reason[idx] = "tau_exceeded"

                    sigma_surf[idx] = sigma_val
                    psd_states[idx] = psd_state

                    dt_over_t_blow = dt / t_blow if t_blow > 0.0 and math.isfinite(t_blow) else 0.0
                    if not blowout_enabled:
                        dt_over_t_blow = 0.0

                    fast_blowout_factor_calc = (
                        _fast_blowout_correction_factor(dt_over_t_blow) if dt_over_t_blow > 0.0 else 0.0
                    )
                    fast_blowout_flag_gt3 = bool(dt_over_t_blow > FAST_BLOWOUT_RATIO_THRESHOLD)
                    fast_blowout_flag_gt10 = bool(dt_over_t_blow > FAST_BLOWOUT_RATIO_STRICT)
                    fast_blowout_factor_record = (
                        fast_blowout_factor_calc if case_status == "blowout" else 0.0
                    )
                    fast_blowout_ratio_alias = dt_over_t_blow if case_status == "blowout" else 0.0
                    if not blowout_enabled:
                        fast_blowout_factor_record = 0.0
                        fast_blowout_ratio_alias = 0.0
                        outflux_surface = 0.0

                    M_out_dot = outflux_surface * area_val / constants.M_MARS
                    M_sink_dot = sink_flux_surface * area_val / constants.M_MARS
                    dM_dt_surface_total = M_out_dot + M_sink_dot
                    dSigma_dt_blowout = outflux_surface
                    dSigma_dt_sinks = sink_flux_surface
                    dSigma_dt_sublimation = smol_res.dSigma_dt_sublimation if smol_res is not None else 0.0
                    dSigma_dt_total = dSigma_dt_blowout + dSigma_dt_sinks
                    M_loss_cum[idx] += M_out_dot * dt
                    M_sink_cum[idx] += M_sink_dot * dt
                    local_step_out_mass += M_out_dot * dt
                    local_step_sink_mass += M_sink_dot * dt
                    local_step_sublimation_mass += mass_loss_sublimation_step

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
                    if smol_res is not None:
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

                    record = {
                        "time": time + dt,
                        "dt": dt,
                        "cell_index": idx,
                        "cell_active": bool(cell_active[idx]),
                        "active_mask": bool(cell_active[idx]),
                        "r_m": r_val,
                        "r_RM": r_rm,
                        "r_orbit_RM": r_rm,
                        "r_source": geometry_source,
                        "Omega_s": Omega_val,
                        "t_orb_s": t_orb_val,
                        "t_blow_s": t_blow,
                        "t_coll": t_coll_step,
                        "ts_ratio": ts_ratio_value,
                        "T_M_used": T_use,
                        "T_M_source": T_M_source,
                        "T_p_effective": T_p_effective,
                        "phase_temperature_input": phase_temperature_input_mode,
                        "rad_flux_Mars": rad_flux_step,
                        "dt_over_t_blow": dt_over_t_blow,
                        "tau": tau_los,
                        "tau_los_mars": tau_los,
                        "a_blow": a_blow_step,
                        "a_blow_step": a_blow_step,
                        "a_blow_at_smin": a_blow_step,
                        "s_min": s_min_effective,
                        "kappa": kappa_eff,
                        "kappa_eff": kappa_eff,
                        "kappa_surf": kappa_surf,
                        "Qpr_mean": qpr_mean_step,
                        "Q_pr_at_smin": qpr_mean_step,
                        "beta_at_smin_config": beta_at_smin_config,
                        "beta_at_smin_effective": beta_at_smin_effective,
                        "beta_at_smin": beta_at_smin_effective,
                        "beta_threshold": beta_threshold,
                        "Sigma_surf": sigma_val,
                        "sigma_surf": sigma_val,
                        "Sigma_surf0": float(sigma_surf0[idx]),
                        "Sigma_tau1": sigma_tau1_limit,
                        "Sigma_tau1_active": sigma_tau1_limit,
                        "sigma_tau1": sigma_tau1_limit,
                        "Sigma_tau1_last_finite": float(sigma_tau1_cells[idx])
                        if math.isfinite(sigma_tau1_cells[idx])
                        else None,
                        "tau_phase_los": tau_phase_los,
                        "tau_phase_used": tau_phase_used,
                        "phase_tau_field": phase_tau_field,
                        "Sigma_midplane": sigma_mid,
                        "sigma_deep": sigma_deep_val,
                        "headroom": headroom_current,
                        "outflux_surface": outflux_surface,
                        "t_solid_s": t_solid_step,
                        "blowout_gate_factor": gate_factor,
                        "sink_flux_surface": sink_flux_surface,
                        "t_blow": t_blow,
                        "prod_subblow_area_rate": prod_rate,
                        "prod_subblow_area_rate_raw": supply_diag.raw_rate if supply_diag else None,
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
                        "e_value": float(e_cells[idx]),
                        "e_kernel_used": _safe_float(e_kernel_used),
                        "i_kernel_used": _safe_float(i_kernel_used),
                        "e_kernel_base": _safe_float(e_kernel_base),
                        "i_kernel_base": _safe_float(i_kernel_base),
                        "e_kernel_supply": _safe_float(e_kernel_supply),
                        "i_kernel_supply": _safe_float(i_kernel_supply),
                        "e_kernel_effective": _safe_float(e_kernel_effective),
                        "i_kernel_effective": _safe_float(i_kernel_effective),
                        "e_state_next": _safe_float(e_state_next),
                        "i_state_next": _safe_float(i_state_next),
                        "t_damp_collisions": _safe_float(t_damp_used),
                        "e_eq_target": _safe_float(e_eq_target),
                        "supply_velocity_weight_w": _safe_float(supply_velocity_weight),
                        "supply_temperature_scale": supply_diag.temperature_scale if supply_diag else None,
                        "supply_temperature_value": supply_diag.temperature_value if supply_diag else None,
                        "supply_temperature_value_kind": supply_diag.temperature_value_kind if supply_diag else None,
                        "supply_feedback_scale": supply_diag.feedback_scale if supply_diag else None,
                        "supply_feedback_error": supply_diag.feedback_error if supply_diag else None,
                        "supply_reservoir_remaining_Mmars": supply_diag.reservoir_remaining_Mmars if supply_diag else None,
                        "supply_reservoir_fraction": supply_diag.reservoir_fraction if supply_diag else None,
                        "supply_reservoir_clipped": bool(supply_diag.clipped_by_reservoir) if supply_diag else False,
                        "M_out_dot": M_out_dot,
                        "M_sink_dot": M_sink_dot,
                        "dM_dt_surface_total": dM_dt_surface_total,
                        "M_out_dot_avg": M_out_dot,
                        "M_sink_dot_avg": M_sink_dot,
                        "dM_dt_surface_total_avg": dM_dt_surface_total,
                        "fast_blowout_factor_avg": fast_blowout_factor_record,
                        "dSigma_dt_blowout": dSigma_dt_blowout,
                        "dSigma_dt_sinks": dSigma_dt_sinks,
                        "dSigma_dt_total": dSigma_dt_total,
                        "dSigma_dt_sublimation": dSigma_dt_sublimation,
                        "M_loss_cum": float(M_loss_cum[idx] + M_sink_cum[idx]),
                        "mass_total_bins": float(sigma_val * area_val / constants.M_MARS),
                        "mass_lost_by_blowout": float(M_loss_cum[idx]),
                        "mass_lost_by_sinks": float(M_sink_cum[idx]),
                        "M_sink_cum": float(M_sink_cum[idx]),
                        "mass_lost_sinks_step": M_sink_dot * dt,
                        "mass_lost_sublimation_step": mass_loss_sublimation_step,
                        "mass_lost_hydro_step": 0.0,
                        "mass_lost_tau_clip_spill_step": mass_loss_spill_step,
                        "cum_mass_lost_tau_clip_spill": float(M_spill_cum[idx]),
                        "mass_lost_surface_solid_marsRP_step": M_out_dot * dt,
                        "M_loss_rp_mars": float(M_loss_cum[idx]),
                        "M_loss_surface_solid_marsRP": float(M_loss_cum[idx]),
                        "M_loss_hydro": 0.0,
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
                        "fast_blowout_factor": fast_blowout_factor_record,
                        "fast_blowout_corrected": False,
                        "fast_blowout_flag_gt3": fast_blowout_flag_gt3,
                        "fast_blowout_flag_gt10": fast_blowout_flag_gt10,
                        "fast_blowout_ratio": fast_blowout_ratio_alias,
                        "n_substeps": 1,
                        "substep_active": False,
                        "chi_blow_eff": chi_blow_eff,
                        "case_status": case_status,
                        "s_blow_m": a_blow_step,
                        "s_blow_m_effective": a_blow_effective_step,
                        "rho_used": rho_used,
                        "Q_pr_used": qpr_mean_step,
                        "Q_pr_blow": qpr_blow_step,
                        "s_min_effective": s_min_effective,
                        "s_min_config": s_min_config,
                        "s_min_effective_gt_config": s_min_effective > s_min_config,
                        "T_source": T_M_source,
                        "ds_dt_sublimation": ds_dt_val,
                        "ds_dt_sublimation_raw": ds_dt_raw,
                        "phi_effective": phi_effective,
                        "phi_used": phi_effective,
                        "phase_state": phase_state,
                        "phase_f_vap": phase_f_vap,
                        "phase_method": phase_method,
                        "phase_reason": phase_reason,
                        "phase_bulk_state": phase_bulk_state,
                        "phase_bulk_f_liquid": phase_bulk_f_liquid,
                        "phase_bulk_f_solid": phase_bulk_f_solid,
                        "phase_bulk_f_vapor": phase_bulk_f_vapor,
                        "tau_mars_line_of_sight": tau_los,
                        "tau_gate_blocked": tau_gate_block_step,
                        "blowout_beta_gate": beta_gate_active,
                        "blowout_phase_allowed": phase_allows_step,
                        "blowout_layer_mode": blowout_layer_mode,
                        "blowout_target_phase": blowout_target_phase,
                        "sink_selected": sink_selected,
                        "sublimation_blocked_by_phase": sublimation_blocked_by_phase,
                        "cell_stop_reason": cell_stop_reason[idx],
                        "cell_stop_time": float(cell_stop_time[idx]) if math.isfinite(cell_stop_time[idx]) else None,
                        "cell_stop_tau": float(cell_stop_tau[idx]) if math.isfinite(cell_stop_tau[idx]) else None,
                    }
                    _ensure_series_keys(record)
                    local_step_records.append(record)
                    F_abs_geom = rad_flux_step * (constants.R_MARS / r_val) ** 2
                    F_abs_geom_qpr = F_abs_geom * qpr_mean_step
                    tau_eff = kappa_eff * sigma_val if math.isfinite(kappa_eff) else None
                    s_peak_value = _psd_mass_peak(psd_state)
                    diag_entry = {
                        "time": time + dt,
                        "dt": dt,
                        "cell_index": idx,
                        "dt_over_t_blow": dt_over_t_blow,
                        "r_m_used": r_val,
                        "r_RM_used": r_rm,
                        "T_M_used": T_use,
                        "T_p_effective": T_p_effective,
                        "phase_temperature_input": phase_temperature_input_mode,
                        "phase_temperature_used_K": temperature_for_phase,
                        "rad_flux_Mars": rad_flux_step,
                        "F_abs_geom": F_abs_geom,
                        "F_abs_geom_qpr": F_abs_geom_qpr,
                        "F_abs": F_abs_geom_qpr,
                        "Omega_s": Omega_val,
                        "t_orb_s": t_orb_val,
                        "t_blow_s": t_blow,
                        "t_solid_s": t_solid_step,
                        "t_sink_total_s": t_sink_total_value,
                        "t_sink_surface_s": t_sink_surface_only,
                        "t_sink_sublimation_s": t_sink_sublimation_value,
                        "t_sink_gas_drag_s": t_sink_gas_drag_value,
                        "mass_loss_sinks_step": M_sink_dot * dt,
                        "mass_lost_by_sinks": float(M_sink_cum[idx]),
                        "mass_loss_sublimation_step": mass_loss_sublimation_step,
                        "sigma_tau1": sigma_tau1_limit,
                        "sigma_tau1_active": sigma_tau1_limit,
                        "Sigma_tau1_last_finite": float(sigma_tau1_cells[idx])
                        if math.isfinite(sigma_tau1_cells[idx])
                        else None,
                        "tau_los_mars": tau_los,
                        "tau_phase_los": tau_phase_los,
                        "tau_phase_used": tau_phase_used,
                        "phase_tau_field": phase_tau_field,
                        "kappa_eff": kappa_eff,
                        "kappa_surf": kappa_surf,
                        "phi_effective": phi_effective,
                        "psi_shield": phi_effective,
                        "sigma_surf": sigma_val,
                        "sigma_deep": sigma_deep_val,
                        "kappa_Planck": kappa_surf,
                        "tau_eff": tau_eff,
                        "s_min": s_min_effective,
                        "a_blow_at_smin": a_blow_step,
                        "beta_at_smin_effective": beta_at_smin_effective,
                        "beta_at_smin": beta_at_smin_effective,
                        "Q_pr_at_smin": qpr_mean_step,
                        "s_peak": s_peak_value,
                        "area_m2": area_val,
                        "prod_subblow_area_rate": prod_rate,
                        "prod_subblow_area_rate_raw": supply_diag.raw_rate if supply_diag else None,
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
                        "supply_temperature_scale": supply_diag.temperature_scale if supply_diag else None,
                        "supply_temperature_value": supply_diag.temperature_value if supply_diag else None,
                        "supply_temperature_value_kind": supply_diag.temperature_value_kind if supply_diag else None,
                        "supply_feedback_scale": supply_diag.feedback_scale if supply_diag else None,
                        "supply_feedback_error": supply_diag.feedback_error if supply_diag else None,
                        "supply_reservoir_remaining_Mmars": supply_diag.reservoir_remaining_Mmars if supply_diag else None,
                        "supply_reservoir_fraction": supply_diag.reservoir_fraction if supply_diag else None,
                        "supply_reservoir_clipped": bool(supply_diag.clipped_by_reservoir) if supply_diag else False,
                        "s_min_effective": s_min_effective,
                        "qpr_mean": qpr_mean_step,
                        "chi_blow_eff": chi_blow_eff,
                        "ds_step_uniform": None,
                        "mass_ratio_uniform": None,
                        "M_out_cum": float(M_loss_cum[idx]),
                        "M_sink_cum": float(M_sink_cum[idx]),
                        "M_loss_cum": float(M_loss_cum[idx] + M_sink_cum[idx]),
                        "cum_mass_lost_tau_clip_spill": float(M_spill_cum[idx]),
                        "M_loss_surface_solid_marsRP": float(M_loss_cum[idx]),
                        "M_hydro_cum": 0.0,
                        "phase_state": phase_state,
                        "phase_method": phase_method,
                        "phase_reason": phase_reason,
                        "phase_f_vap": phase_f_vap,
                        "phase_bulk_state": phase_bulk_state,
                        "phase_bulk_f_liquid": phase_bulk_f_liquid,
                        "phase_bulk_f_solid": phase_bulk_f_solid,
                        "phase_bulk_f_vapor": phase_bulk_f_vapor,
                        "phase_payload": phase_payload,
                        "ds_dt_sublimation": ds_dt_val,
                        "ds_dt_sublimation_raw": ds_dt_raw,
                        "sublimation_blocked_by_phase": sublimation_blocked_by_phase,
                        "tau_mars_line_of_sight": tau_los,
                        "tau_gate_blocked": tau_gate_block_step,
                        "blowout_beta_gate": beta_gate_active,
                        "blowout_phase_allowed": phase_allows_step,
                        "blowout_layer_mode": blowout_layer_mode,
                        "blowout_target_phase": blowout_target_phase,
                        "sink_selected": sink_selected,
                        "hydro_timescale_s": None,
                        "mass_loss_surface_solid_step": M_out_dot * dt,
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
                    _ensure_diagnostic_keys(diag_entry)
                    local_step_diagnostics.append(diag_entry)
                    local_step_area_sum += area_val
                    local_step_supply_rate_nominal_sum += _safe_float(supply_rate_nominal_current) * area_val
                    local_step_supply_rate_scaled_sum += _safe_float(supply_rate_scaled_current) * area_val
                    local_step_supply_rate_applied_sum += _safe_float(supply_rate_applied_current) * area_val
                    local_step_supply_headroom_sum += _safe_float(headroom_current) * area_val
                    local_step_supply_clip_factor_sum += _safe_float(clip_factor_current) * area_val
                    local_step_supply_visibility_sum += _safe_float(visibility_factor_current) * area_val
                    local_step_supply_spill_rate_sum += _safe_float(spill_rate_current) * area_val
                    local_step_supply_feedback_sum += _safe_float(
                        supply_diag.feedback_scale if supply_diag else None
                    ) * area_val
                    local_step_supply_temperature_sum += _safe_float(
                        supply_diag.temperature_scale if supply_diag else None
                    ) * area_val
                    local_step_supply_reservoir_remaining_sum += _safe_float(
                        supply_diag.reservoir_remaining_Mmars if supply_diag else None
                    ) * area_val
                    local_step_dt_over_t_blow_sum += _safe_float(dt_over_t_blow) * area_val
                    if supply_blocked_by_headroom_flag:
                        local_step_supply_blocked_area_sum += area_val
                    if supply_mixing_limited_flag:
                        local_step_supply_mixing_area_sum += area_val
                    if not cell_active[idx] and frozen_records[idx] is None:
                        frozen_records[idx] = dict(record)

                    if psd_history_enabled and (psd_history_stride <= 1 or step_no % psd_history_stride == 0):
                        sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
                        widths_arr = np.asarray(psd_state.get("widths"), dtype=float)
                        number_arr = np.asarray(psd_state.get("number"), dtype=float)
                        if sizes_arr.size and number_arr.size == sizes_arr.size and widths_arr.size == sizes_arr.size:
                            mass_weight_bins = number_arr * (sizes_arr ** 3) * widths_arr
                            mass_weight_total = float(np.sum(mass_weight_bins))
                            if not math.isfinite(mass_weight_total) or mass_weight_total <= 0.0:
                                mass_frac = np.zeros_like(mass_weight_bins)
                            else:
                                mass_frac = mass_weight_bins / mass_weight_total
                            for b_idx, (size_val, number_val, f_mass_val) in enumerate(zip(sizes_arr, number_arr, mass_frac)):
                                local_psd_hist_records.append(
                                    {
                                        "time": time + dt,
                                        "cell_index": idx,
                                        "r_m": r_val,
                                        "r_RM": r_rm,
                                        "bin_index": int(b_idx),
                                        "s_bin_center": float(size_val),
                                        "N_bin": float(number_val),
                                        "Sigma_bin": float(f_mass_val * sigma_val),
                                        "f_mass": float(f_mass_val),
                                        "Sigma_surf": sigma_val,
                                    }
                                )

                    mass_lost_cell = M_loss_cum[idx] + M_sink_cum[idx]
                    mass_remaining_cell = mass_initial_cell[idx] - mass_lost_cell
                    mass_diff_cell = mass_initial_cell[idx] - mass_remaining_cell - mass_lost_cell
                    error_percent_cell = 0.0
                    if mass_initial_cell[idx] > 0.0:
                        error_percent_cell = abs(mass_diff_cell / mass_initial_cell[idx]) * 100.0
                    local_mass_budget_cells.append(
                        {
                            "time": time + dt,
                            "cell_index": idx,
                            "r_RM": r_rm,
                            "mass_initial": float(mass_initial_cell[idx]),
                            "mass_remaining": float(mass_remaining_cell),
                            "mass_lost": float(mass_lost_cell),
                            "mass_diff": float(mass_diff_cell),
                            "error_percent": float(error_percent_cell),
                            "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
                            "cell_active": bool(cell_active[idx]),
                        }
                    )

                return {
                    'records': local_step_records,
                    'diagnostics': local_step_diagnostics,
                    'out_mass': local_step_out_mass,
                    'sink_mass': local_step_sink_mass,
                    'sublimation_mass': local_step_sublimation_mass,
                    'area_sum': local_step_area_sum,
                    'supply_rate_nominal_sum': local_step_supply_rate_nominal_sum,
                    'supply_rate_scaled_sum': local_step_supply_rate_scaled_sum,
                    'supply_rate_applied_sum': local_step_supply_rate_applied_sum,
                    'supply_headroom_sum': local_step_supply_headroom_sum,
                    'supply_clip_factor_sum': local_step_supply_clip_factor_sum,
                    'supply_visibility_sum': local_step_supply_visibility_sum,
                    'supply_spill_rate_sum': local_step_supply_spill_rate_sum,
                    'supply_feedback_sum': local_step_supply_feedback_sum,
                    'supply_temperature_sum': local_step_supply_temperature_sum,
                    'supply_reservoir_remaining_sum': local_step_supply_reservoir_remaining_sum,
                    'dt_over_t_blow_sum': local_step_dt_over_t_blow_sum,
                    'supply_blocked_area_sum': local_step_supply_blocked_area_sum,
                    'supply_mixing_area_sum': local_step_supply_mixing_area_sum,
                    'psd_hist_records': local_psd_hist_records,
                    'mass_budget_cells': local_mass_budget_cells,
                    't_coll_min': local_t_coll_min,
                    'supply_rate_scaled_initial': local_supply_rate_scaled_initial,
                }

            step_payload_iter = None
            if cell_parallel_enabled and cell_executor is not None and cell_chunks is not None:
                step_payload_iter = cell_executor.map(_run_cell_indices, cell_chunks)
            else:
                step_payload_iter = (_run_cell_indices(range(n_cells)),)
            for payload in step_payload_iter:
                step_records.extend(payload['records'])
                step_diagnostics.extend(payload['diagnostics'])
                step_out_mass += payload['out_mass']
                step_sink_mass += payload['sink_mass']
                step_sublimation_mass += payload['sublimation_mass']
                step_area_sum += payload['area_sum']
                step_supply_rate_nominal_sum += payload['supply_rate_nominal_sum']
                step_supply_rate_scaled_sum += payload['supply_rate_scaled_sum']
                step_supply_rate_applied_sum += payload['supply_rate_applied_sum']
                step_supply_headroom_sum += payload['supply_headroom_sum']
                step_supply_clip_factor_sum += payload['supply_clip_factor_sum']
                step_supply_visibility_sum += payload['supply_visibility_sum']
                step_supply_spill_rate_sum += payload['supply_spill_rate_sum']
                step_supply_feedback_sum += payload['supply_feedback_sum']
                step_supply_temperature_sum += payload['supply_temperature_sum']
                step_supply_reservoir_remaining_sum += payload['supply_reservoir_remaining_sum']
                step_dt_over_t_blow_sum += payload['dt_over_t_blow_sum']
                step_supply_blocked_area_sum += payload['supply_blocked_area_sum']
                step_supply_mixing_area_sum += payload['supply_mixing_area_sum']
                if payload['psd_hist_records']:
                    history.psd_hist_records.extend(payload['psd_hist_records'])
                if payload['mass_budget_cells']:
                    history.mass_budget_cells.extend(payload['mass_budget_cells'])
                if supply_rate_scaled_initial is None and payload['supply_rate_scaled_initial'] is not None:
                    supply_rate_scaled_initial = payload['supply_rate_scaled_initial']
                if payload['t_coll_min'] is not None and math.isfinite(payload['t_coll_min']):
                    t_coll_min = min(t_coll_min, payload['t_coll_min'])
            area_denom = step_area_sum if step_area_sum > 0.0 else total_area
            if area_denom <= 0.0 or not math.isfinite(area_denom):
                area_denom = 1.0
            supply_rate_nominal_avg = step_supply_rate_nominal_sum / area_denom
            supply_rate_scaled_avg = step_supply_rate_scaled_sum / area_denom
            supply_rate_applied_avg = step_supply_rate_applied_sum / area_denom
            supply_headroom_avg = step_supply_headroom_sum / area_denom
            supply_clip_factor_avg = step_supply_clip_factor_sum / area_denom
            supply_visibility_avg = step_supply_visibility_sum / area_denom
            supply_spill_rate_avg = step_supply_spill_rate_sum / area_denom
            supply_feedback_avg = step_supply_feedback_sum / area_denom
            supply_temperature_avg = step_supply_temperature_sum / area_denom
            supply_reservoir_remaining_avg = step_supply_reservoir_remaining_sum / area_denom
            dt_over_t_blow_avg = step_dt_over_t_blow_sum / area_denom
            supply_blocked_fraction = step_supply_blocked_area_sum / area_denom
            supply_mixing_fraction = step_supply_mixing_area_sum / area_denom

            supply_rate_nominal_track.append(supply_rate_nominal_avg)
            supply_rate_scaled_track.append(supply_rate_scaled_avg)
            supply_rate_applied_track.append(supply_rate_applied_avg)
            supply_headroom_track.append(supply_headroom_avg)
            supply_clip_factor_track.append(supply_clip_factor_avg)
            supply_visibility_track.append(supply_visibility_avg)
            supply_spill_rate_track.append(supply_spill_rate_avg)
            supply_feedback_track.append(supply_feedback_avg)
            supply_temperature_track.append(supply_temperature_avg)
            supply_reservoir_remaining_track.append(supply_reservoir_remaining_avg)
            dt_over_t_blow_track.append(dt_over_t_blow_avg)
            supply_blocked_track.append(supply_blocked_fraction)
            supply_mixing_track.append(supply_mixing_fraction)

            if dt > 0.0 and math.isfinite(dt):
                supply_rate_nominal_time_sum += supply_rate_nominal_avg * dt
                supply_rate_scaled_time_sum += supply_rate_scaled_avg * dt
                supply_rate_applied_time_sum += supply_rate_applied_avg * dt
                supply_headroom_time_sum += supply_headroom_avg * dt
                supply_clip_factor_time_sum += supply_clip_factor_avg * dt
                supply_visibility_time_sum += supply_visibility_avg * dt
                supply_spill_rate_time_sum += supply_spill_rate_avg * dt
                if supply_spill_rate_avg > 0.0:
                    supply_spill_active_time_sum += dt
                supply_blocked_time_sum += supply_blocked_fraction * dt
                supply_mixing_time_sum += supply_mixing_fraction * dt
                total_time_weight_sum += dt

            t_coll_min_output = float(t_coll_min) if math.isfinite(t_coll_min) else None
            if step_records:
                for record in step_records:
                    record["t_coll_kernel_min"] = t_coll_min_output
                history.records.extend(step_records)
            if step_diagnostics:
                history.diagnostics.extend(step_diagnostics)

            M_sublimation_cum += step_sublimation_mass
            if orbit_rollup_enabled and t_orb_ref > 0.0:
                orbit_time_accum += dt
                orbit_loss_blow += step_out_mass
                orbit_loss_sink += step_sink_mass
                while orbit_time_accum >= t_orb_ref and orbit_time_accum > 0.0:
                    orbit_time_accum_before = orbit_time_accum
                    fraction = t_orb_ref / orbit_time_accum_before
                    M_orbit_blow = orbit_loss_blow * fraction
                    M_orbit_sink = orbit_loss_sink * fraction
                    orbits_completed += 1
                    mass_loss_frac = float("nan")
                    if mass_initial_total > 0.0:
                        mass_loss_frac = (M_orbit_blow + M_orbit_sink) / mass_initial_total
                    time_s_end = step_end_time - max(orbit_time_accum_before - t_orb_ref, 0.0)
                    orbit_rollup_rows.append(
                        {
                            "orbit_index": orbits_completed,
                            "time_s": step_end_time,
                            "time_s_end": time_s_end,
                            "t_orb_s": t_orb_ref,
                            "M_out_orbit": M_orbit_blow,
                            "M_sink_orbit": M_orbit_sink,
                            "M_loss_orbit": M_orbit_blow + M_orbit_sink,
                            "M_out_per_orbit": M_orbit_blow / t_orb_ref,
                            "M_sink_per_orbit": M_orbit_sink / t_orb_ref,
                            "M_loss_per_orbit": (M_orbit_blow + M_orbit_sink) / t_orb_ref,
                            "mass_loss_frac_per_orbit": mass_loss_frac,
                            "M_out_cum": float(np.sum(M_loss_cum)),
                            "M_sink_cum": float(np.sum(M_sink_cum)),
                            "M_loss_cum": float(np.sum(M_loss_cum + M_sink_cum)),
                            "r_RM": r_rm_mid,
                            "T_M": T_use,
                            "slope_dlnM_dlnr": None,
                        }
                    )
                    orbit_time_accum -= t_orb_ref
                    orbit_loss_blow = max(orbit_loss_blow - M_orbit_blow, 0.0)
                    orbit_loss_sink = max(orbit_loss_sink - M_orbit_sink, 0.0)

            mass_lost_total = float(np.sum(M_loss_cum + M_sink_cum))
            mass_remaining_total = mass_initial_total - mass_lost_total
            mass_diff_total = mass_initial_total - mass_remaining_total - mass_lost_total
            error_percent_total = 0.0
            if mass_initial_total > 0.0:
                error_percent_total = abs(mass_diff_total / mass_initial_total) * 100.0
            mass_budget_max_error = max(mass_budget_max_error, error_percent_total)
            history.mass_budget.append(
                {
                    "time": time + dt,
                    "mass_initial": mass_initial_total,
                    "mass_remaining": mass_remaining_total,
                    "mass_lost": mass_lost_total,
                    "mass_diff": mass_diff_total,
                    "error_percent": error_percent_total,
                    "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
                }
            )

            time += dt
            step_no += 1
            steps_since_flush += 1
            progress.update(step_no, time)

            if streaming_state.should_flush(history, steps_since_flush):
                streaming_state.flush(history, step_no)
                steps_since_flush = 0

            all_cells_solid_state = bool(np.all(cell_solid_state))

            if np.all(~cell_active) and all_cells_solid_state:
                early_stop_reason = "tau_exceeded_all_cells"
                break

            if dt_min_tcoll_ratio is not None and math.isfinite(t_coll_min):
                dt_floor = dt_min_tcoll_ratio * t_coll_min
                if math.isfinite(dt_floor) and dt_floor > 0.0:
                    dt = max(dt_nominal, dt_floor)
                else:
                    dt = dt_nominal
            else:
                dt = dt_nominal
    finally:
        if cell_executor is not None:
            cell_executor.shutdown(wait=True)
    progress.finish(step_no, time)

    if streaming_state.enabled:
        streaming_state.flush(history, step_no)
        streaming_state.merge_chunks()
    else:
        if history.records:
            writer.write_parquet(pd.DataFrame(history.records), outdir / "series" / "run.parquet")
        if history.diagnostics:
            writer.write_parquet(
                pd.DataFrame(history.diagnostics), outdir / "series" / "diagnostics.parquet"
            )
        if history.psd_hist_records:
            writer.write_parquet(
                pd.DataFrame(history.psd_hist_records), outdir / "series" / "psd_hist.parquet"
            )
    mass_budget_path = (
        streaming_state.mass_budget_path if streaming_state.enabled else outdir / "checks" / "mass_budget.csv"
    )
    if history.mass_budget:
        writer.append_csv(history.mass_budget, mass_budget_path, header=not mass_budget_path.exists())
        history.mass_budget.clear()
    if not mass_budget_path.exists():
        pd.DataFrame(columns=["time", "mass_initial", "mass_remaining", "mass_lost", "error_percent", "tolerance_percent"]).to_csv(
            mass_budget_path,
            index=False,
        )

    mass_budget_cells_path = (
        streaming_state.mass_budget_cells_path if streaming_state.enabled else outdir / "checks" / "mass_budget_cells.csv"
    )
    if history.mass_budget_cells:
        writer.append_csv(history.mass_budget_cells, mass_budget_cells_path, header=not mass_budget_cells_path.exists())
        history.mass_budget_cells.clear()
    if not mass_budget_cells_path.exists():
        pd.DataFrame(
            columns=[
                "time",
                "cell_index",
                "r_RM",
                "mass_initial",
                "mass_remaining",
                "mass_lost",
                "error_percent",
                "tolerance_percent",
                "cell_active",
            ]
        ).to_csv(mass_budget_cells_path, index=False)

    M_out_cum = float(np.sum(M_loss_cum))
    M_sink_cum = float(np.sum(M_sink_cum))
    sigma_midplane_avg_value = (
        float(sigma_midplane_avg) if math.isfinite(sigma_midplane_avg) else None
    )
    if orbit_rollup_enabled and not orbit_rollup_rows:
        mass_loss_frac = float("nan")
        if mass_initial_total > 0.0:
            mass_loss_frac = (orbit_loss_blow + orbit_loss_sink) / mass_initial_total
        denom = t_orb_ref if t_orb_ref > 0.0 else float("nan")
        orbit_rollup_rows.append(
            {
                "orbit_index": 1,
                "time_s": time,
                "time_s_end": time,
                "t_orb_s": t_orb_ref,
                "M_out_orbit": orbit_loss_blow,
                "M_sink_orbit": orbit_loss_sink,
                "M_loss_orbit": orbit_loss_blow + orbit_loss_sink,
                "M_out_per_orbit": orbit_loss_blow / denom if math.isfinite(denom) else float("nan"),
                "M_sink_per_orbit": orbit_loss_sink / denom if math.isfinite(denom) else float("nan"),
                "M_loss_per_orbit": (orbit_loss_blow + orbit_loss_sink) / denom if math.isfinite(denom) else float("nan"),
                "mass_loss_frac_per_orbit": mass_loss_frac,
                "M_out_cum": M_out_cum,
                "M_sink_cum": M_sink_cum,
                "M_loss_cum": M_out_cum + M_sink_cum,
                "r_RM": r_rm_mid,
                "T_M": T_use_last,
                "slope_dlnM_dlnr": None,
            }
        )
        orbits_completed = max(orbits_completed, 1)
    if orbit_rollup_enabled:
        writer.write_orbit_rollup(orbit_rollup_rows, outdir / "orbit_rollup.csv")

    def _series_stats(values: List[float]) -> tuple[float, float, float]:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            nan = float("nan")
            return nan, nan, nan
        return float(np.min(arr)), float(np.median(arr)), float(np.max(arr))

    T_min, T_median, T_max = _series_stats(temperature_track)
    beta_min, beta_median, beta_max = _series_stats(beta_track)
    ablow_min, ablow_median, ablow_max = _series_stats(ablow_track)
    supply_nominal_min, supply_nominal_median, supply_nominal_max = _series_stats(
        supply_rate_nominal_track
    )
    supply_scaled_min, supply_scaled_median, supply_scaled_max = _series_stats(
        supply_rate_scaled_track
    )
    supply_applied_min, supply_applied_median, supply_applied_max = _series_stats(
        supply_rate_applied_track
    )
    supply_headroom_min, supply_headroom_median, supply_headroom_max = _series_stats(
        supply_headroom_track
    )
    supply_clip_factor_min, supply_clip_factor_median, supply_clip_factor_max = _series_stats(
        supply_clip_factor_track
    )
    supply_visibility_min, supply_visibility_median, supply_visibility_max = _series_stats(
        supply_visibility_track
    )
    supply_spill_rate_min, supply_spill_rate_median, supply_spill_rate_max = _series_stats(
        supply_spill_rate_track
    )
    supply_feedback_min, supply_feedback_median, supply_feedback_max = _series_stats(
        supply_feedback_track
    )
    supply_temp_scale_min, supply_temp_scale_median, supply_temp_scale_max = _series_stats(
        supply_temperature_track
    )
    supply_reservoir_min, supply_reservoir_median, supply_reservoir_max = _series_stats(
        supply_reservoir_remaining_track
    )
    dt_over_t_blow_min, dt_over_t_blow_median, dt_over_t_blow_max = _series_stats(
        dt_over_t_blow_track
    )
    supply_blocked_min, supply_blocked_median, supply_blocked_max = _series_stats(supply_blocked_track)
    supply_mixing_min, supply_mixing_median, supply_mixing_max = _series_stats(supply_mixing_track)
    supply_rate_nominal_inferred = (
        supply_rate_nominal_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_rate_scaled_inferred = (
        supply_rate_scaled_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_rate_applied_inferred = (
        supply_rate_applied_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_headroom_inferred = (
        supply_headroom_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_clip_factor_inferred = (
        supply_clip_factor_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_visibility_inferred = (
        supply_visibility_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_spill_rate_inferred = (
        supply_spill_rate_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_blocked_fraction = (
        supply_blocked_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_mixing_fraction = (
        supply_mixing_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    supply_spill_active_fraction = (
        supply_spill_active_time_sum / total_time_weight_sum
        if total_time_weight_sum > 0.0
        else None
    )
    temp_prov = dict(temp_runtime.provenance)
    temp_prov.setdefault("mode", temp_runtime.mode)
    temp_prov.setdefault("enabled", temp_runtime.enabled)
    temp_prov.setdefault("source", temp_runtime.source)
    solar_radiation = {
        "enabled": False,
        "requested": solar_rp_requested,
        "note": (
            "Solar radiation disabled (Mars-only scope)"
            if radiation_field == "mars"
            else "Radiation disabled via radiation.source='off'"
        ),
    }
    a_blow_effective_last = max(s_min_config, a_blow_last)
    s_min_components = {
        "config": float(s_min_config),
        "blowout": float(a_blow_last),
        "blowout_raw": float(a_blow_last),
        "blowout_effective": float(a_blow_effective_last),
        "effective": float(s_min_effective_last),
    }
    stop_reason = early_stop_reason
    if stop_reason is None:
        if loop_exit_reason is not None:
            stop_reason = loop_exit_reason
        elif step_no >= max_steps:
            stop_reason = "max_steps"
        else:
            stop_reason = "t_end_reached"

    summary = {
        "status": "complete",
        "geometry_mode": "1D",
        "geometry_source": geometry_source,
        "geometry": {
            "r_in_m": float(r_in_m),
            "r_out_m": float(r_out_m),
            "Nr": int(n_cells),
        },
        "sigma_surf0_avg": sigma_surf0_avg,
        "sigma_surf0_target": sigma_surf0_target,
        "sigma_midplane_avg": sigma_midplane_avg_value,
        "M_out_cum": M_out_cum,
        "M_sink_cum": M_sink_cum,
        "M_loss": M_out_cum + M_sink_cum,
        "M_loss_from_sinks": M_sink_cum,
        "M_loss_from_sublimation": float(M_sublimation_cum),
        "mass_budget_max_error_percent": mass_budget_max_error,
        "dt_over_t_blow_median": dt_over_t_blow_median,
        "early_stop_reason": early_stop_reason,
        "stop_reason": stop_reason,
        "cells_stopped": int(np.sum(~cell_active)),
        "cells_total": int(n_cells),
        "time_end_s": time,
        "time_grid": {
            "dt_nominal_s": dt_nominal,
            "t_end_s": t_end,
            "dt_min_tcoll_ratio": dt_min_tcoll_ratio,
            **time_grid_info,
        },
        "case_status": case_status,
        "beta_at_smin_config": beta_at_smin_config,
        "beta_at_smin_effective": beta_at_smin_effective,
        "beta_at_smin_min": beta_min,
        "beta_at_smin_median": beta_median,
        "beta_at_smin_max": beta_max,
        "beta_threshold": beta_threshold,
        "s_blow_m": float(a_blow_last),
        "s_blow_m_effective": float(a_blow_effective_last),
        "a_blow_final": float(a_blow_last),
        "a_blow_min": ablow_min,
        "a_blow_median": ablow_median,
        "a_blow_max": ablow_max,
        "Q_pr_used": qpr_mean_last,
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "rho_used": rho_used,
        "T_M_used": T_use_last,
        "T_M_initial": temperature_track[0] if temperature_track else T_init,
        "T_M_final": temperature_track[-1] if temperature_track else T_init,
        "T_M_min": T_min,
        "T_M_median": T_median,
        "T_M_max": T_max,
        "temperature_driver": temp_prov,
        "solar_radiation": solar_radiation,
        "chi_blow_eff": chi_blow_eff,
        "s_min_effective": float(s_min_effective_last),
        "s_min_components": s_min_components,
        "supply_rate_nominal_kg_m2_s": supply_rate_nominal_inferred,
        "supply_rate_scaled_initial_kg_m2_s": supply_rate_scaled_initial,
        "effective_prod_rate_kg_m2_s": supply_rate_applied_inferred,
        "supply_transport_mode": supply_transport_mode,
        "supply_transport_t_mix_orbits": supply_deep_tmix_orbits,
        "supply_transport_headroom_gate": supply_transport_headroom_gate,
        "supply_headroom_policy": supply_headroom_policy,
        "supply_visibility_min": supply_visibility_min,
        "supply_visibility_median": supply_visibility_median,
        "supply_visibility_max": supply_visibility_max,
        "supply_blocked_fraction": supply_blocked_fraction,
        "supply_mixing_fraction": supply_mixing_fraction,
        "supply_feedback_scale_min": supply_feedback_min,
        "supply_feedback_scale_median": supply_feedback_median,
        "supply_feedback_scale_max": supply_feedback_max,
        "supply_temperature_scale_min": supply_temp_scale_min,
        "supply_temperature_scale_median": supply_temp_scale_median,
        "supply_temperature_scale_max": supply_temp_scale_max,
        "supply_reservoir_remaining_stats_Mmars": {
            "min": supply_reservoir_min,
            "median": supply_reservoir_median,
            "max": supply_reservoir_max,
        },
        "supply_clipping": {
            "headroom_min": supply_headroom_min,
            "headroom_median": supply_headroom_median,
            "headroom_max": supply_headroom_max,
            "clip_factor_min": supply_clip_factor_min,
            "clip_factor_median": supply_clip_factor_median,
            "clip_factor_max": supply_clip_factor_max,
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
            "M_loss_cum": float(np.sum(M_spill_cum)),
        },
        "orbits_completed": orbits_completed,
        "seed": seed_val,
        "seed_expr": seed_expr,
        "seed_basis": seed_basis,
    }
    if orbits_completed > 0:
        summary["M_out_mean_per_orbit"] = M_out_cum / orbits_completed
        summary["M_sink_mean_per_orbit"] = M_sink_cum / orbits_completed
        summary["M_loss_mean_per_orbit"] = (M_out_cum + M_sink_cum) / orbits_completed
    else:
        summary["M_out_mean_per_orbit"] = None
        summary["M_sink_mean_per_orbit"] = None
        summary["M_loss_mean_per_orbit"] = None
    writer.write_summary(summary, outdir / "summary.json")

    sublimation_provenance = {
        "sublimation_formula": "HKL",
        "mode": sub_params_base.mode,
        "psat_model": sub_params_base.psat_model,
        "alpha_evap": sub_params_base.alpha_evap,
        "mu": sub_params_base.mu,
        "A": sub_params_base.A,
        "B": sub_params_base.B,
        "P_gas": sub_params_base.P_gas,
        "valid_K": list(sub_params_base.valid_K) if sub_params_base.valid_K is not None else None,
        "valid_liquid_K": list(sub_params_base.valid_liquid_K)
        if sub_params_base.valid_liquid_K is not None
        else None,
    }
    run_config_snapshot = {
        "status": "complete",
        "outdir": str(outdir),
        "config_source_path": str(config_source_path) if config_source_path else None,
        "geometry_source": geometry_source,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "config": cfg.model_dump(mode="json"),
        "init_ei": init_ei_snapshot,
        "sigma_surf0_target": sigma_surf0_target,
        "sigma_surf0_avg": sigma_surf0_avg,
        "sigma_midplane_avg": sigma_midplane_avg_value,
        "supply_mu_orbit10pct": supply_mu_orbit_cfg,
        "supply_mu_reference_tau": mu_reference_tau,
        "sigma_surf_mu_reference": sigma_surf_mu_ref,
        "supply_orbit_fraction_at_mu1": supply_orbit_fraction,
        "epsilon_mix": supply_epsilon_mix,
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "beta_formula": "beta = 3 SIGMA_SB T_M^4 R_M^2 Q_pr / (4 G M_M c rho s)",
        "T_M_used": T_use_last,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean_last,
        "blowout_provenance": {
            "s_blow_raw_m": float(a_blow_last),
            "s_blow_effective_m": float(a_blow_effective_last),
            "s_min_config_m": float(s_min_config),
            "psd_floor_mode": str(psd_floor_mode),
        },
        "temperature_driver": temp_prov,
        "solar_radiation": solar_radiation,
        "sublimation_provenance": sublimation_provenance,
    }
    run_config_snapshot["io"] = {
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
    run_config_snapshot["cell_parallel"] = cell_parallel_info
    if auto_tune_info is not None:
        run_config_snapshot["auto_tune"] = auto_tune_info
    writer.write_run_config(run_config_snapshot, run_config_path)

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

    if mass_budget_max_error > MASS_BUDGET_TOLERANCE_PERCENT and enforce_mass_budget:
        raise MassBudgetViolationError(
            "Mass budget tolerance exceeded; see summary.json for details"
        )


__all__ = ["run_one_d", "MassBudgetViolationError"]
