"""Orchestrator layer for Mars disk simulations.

This module provides the high-level orchestration functions that coordinate
the simulation workflow. It separates the control flow from the physics
calculations and I/O operations.

Architecture Overview
---------------------
The run.py module has been split into three logical layers:

1. **Orchestrator (this module)**
   - Configuration resolution and validation
   - Time grid setup
   - Main simulation loop control
   - Progress reporting

2. **Physics Steps (marsdisk.physics.*)**
   - Individual physics calculations
   - Module-specific state updates

3. **I/O (marsdisk.io.*)**
   - File writing (Parquet, JSON, CSV)
   - Table loading (Q_pr, Φ)
   - Diagnostic output

Module Dependencies
-------------------
```
orchestrator.py
├── run.py (main entry point)
├── physics_step.py (per-step physics)
├── io/writer.py (output)
└── io/tables.py (input tables)
```

See Also
--------
- `analysis/physics_flow.md`: Mermaid diagrams of computation flow
- `analysis/glossary.md`: Variable naming conventions
"""
from __future__ import annotations

import copy
import hashlib
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .errors import ConfigurationError
from .schema import Config
from . import config_utils, constants
from .physics import tempdriver
from .io.streaming import MEMORY_DIAG_ROW_BYTES, MEMORY_PSD_ROW_BYTES, MEMORY_RUN_ROW_BYTES

logger = logging.getLogger(__name__)

# ===========================================================================
# Constants
# ===========================================================================
SECONDS_PER_YEAR = constants.SECONDS_PER_YEAR
MAX_STEPS = constants.MAX_STEPS
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0
EXTENDED_DIAGNOSTICS_VERSION = "extended-minimal-v1"


# ===========================================================================
# Data Classes for State Management
# ===========================================================================

@dataclass
class TimeGridInfo:
    """Information about the simulation time grid.
    
    Attributes
    ----------
    t_end_s : float
        Total simulation duration [s].
    dt_nominal_s : float
        Nominal time step [s].
    dt_step_s : float
        Actual step size [s] (may differ from nominal).
    n_steps : int
        Total number of steps.
    t_end_basis : str
        Source of t_end ("t_end_years" or "t_end_orbits").
    dt_mode : str
        How dt was determined ("auto" or "explicit").
    """
    t_end_s: float
    dt_nominal_s: float
    dt_step_s: float
    n_steps: int
    t_end_basis: str
    t_end_input: float
    dt_mode: str
    dt_sources: Dict[str, float] = field(default_factory=dict)
    t_blow_nominal_s: Optional[float] = None
    dt_capped_by_max_steps: bool = False


@dataclass
class SimulationState:
    """Mutable state variables during simulation.
    
    This dataclass holds all quantities that evolve during the time integration.
    It separates the evolving state from the fixed configuration.
    
    Attributes
    ----------
    time_s : float
        Current simulation time [s].
    sigma_surf : float
        Surface mass density [kg m⁻²].
    psd_state : dict
        Particle size distribution state.
    M_loss_cum : float
        Cumulative mass loss from blowout [M_Mars].
    M_sink_cum : float
        Cumulative mass loss from sinks [M_Mars].
    M_sublimation_cum : float
        Cumulative sublimation mass loss [M_Mars].
    M_hydro_cum : float
        Cumulative hydrodynamic escape mass loss [M_Mars].
    """
    time_s: float = 0.0
    sigma_surf: float = 0.0
    psd_state: Dict[str, Any] = field(default_factory=dict)
    M_loss_cum: float = 0.0
    M_sink_cum: float = 0.0
    M_sublimation_cum: float = 0.0
    M_hydro_cum: float = 0.0
    
    # Per-step tracking
    kappa_surf: float = 0.0
    kappa_eff: float = 0.0
    tau: float = 0.0
    a_blow: float = 0.0
    s_min_effective: float = 0.0
    qpr_mean: float = 1.0
    beta_at_smin: float = 0.0
    
    # Orbit tracking
    orbit_time_accum: float = 0.0
    orbit_loss_blow: float = 0.0
    orbit_loss_sink: float = 0.0
    orbits_completed: int = 0


@dataclass
class PhysicsFlags:
    """Boolean flags controlling physics behavior.
    
    These flags determine which physical processes are active during simulation.
    They are resolved from configuration and remain constant during a run.
    """
    collisions_active: bool = True
    sublimation_active: bool = False
    blowout_enabled: bool = True
    sink_timescale_active: bool = False
    freeze_kappa: bool = False
    freeze_sigma: bool = False
    tau_gate_enabled: bool = False
    phase_enabled: bool = False


@dataclass 
class OrchestrationContext:
    """Context object holding all simulation parameters and state.
    
    This bundles configuration, physics flags, and runtime state into
    a single object that can be passed through the orchestration layer.
    """
    cfg: Config
    state: SimulationState
    flags: PhysicsFlags
    time_grid: TimeGridInfo
    
    # Derived quantities
    r_m: float = 0.0
    Omega: float = 0.0
    t_orb_s: float = 0.0
    area_m2: float = 0.0
    rho: float = 3000.0
    
    # Temperature driver (callable)
    temp_driver: Any = None
    
    # Tracking lists (for history)
    temperature_track: List[float] = field(default_factory=list)
    beta_track: List[float] = field(default_factory=list)
    ablow_track: List[float] = field(default_factory=list)


# ===========================================================================
# Time Grid Resolution
# ===========================================================================

def resolve_time_grid(
    numerics: Any,
    Omega: float,
    t_orb: float,
    *,
    temp_runtime: Optional[tempdriver.TemperatureDriverRuntime] = None,
) -> tuple[float, float, float, int, Dict[str, Any]]:
    """Resolve (t_end, dt_nominal, dt_step, n_steps, info) for the integrator."""

    t_end_basis = None
    t_end_input = None
    t_end = None
    t_end_seconds_from_temperature = None
    temp_stop = getattr(numerics, "t_end_until_temperature_K", None)
    temp_pad_years = float(getattr(numerics, "t_end_temperature_margin_years", 0.0) or 0.0)
    temp_search_years = getattr(numerics, "t_end_temperature_search_years", None)

    if temp_stop is not None:
        if temp_runtime is None:
            raise ConfigurationError("t_end_until_temperature_K requires a resolved Mars temperature driver")
        search_max_s = float(temp_search_years) * SECONDS_PER_YEAR if temp_search_years is not None else None
        t_stop_s = tempdriver.estimate_time_to_temperature(
            temp_runtime,
            float(temp_stop),
            search_max_s=search_max_s,
        )
        if t_stop_s is not None:
            t_end_seconds_from_temperature = t_stop_s + temp_pad_years * SECONDS_PER_YEAR
            t_end_basis = "t_end_until_temperature_K"
            t_end_input = float(temp_stop)

    if t_end_seconds_from_temperature is not None:
        t_end = t_end_seconds_from_temperature
    elif numerics.t_end_orbits is not None:
        t_end = float(numerics.t_end_orbits) * t_orb
        t_end_basis = "t_end_orbits"
        t_end_input = float(numerics.t_end_orbits)
    elif numerics.t_end_years is not None:
        t_end = float(numerics.t_end_years) * SECONDS_PER_YEAR
        t_end_basis = "t_end_years"
        t_end_input = float(numerics.t_end_years)
    else:
        raise ConfigurationError(
            "numerics must provide t_end_years, t_end_orbits, or t_end_until_temperature_K"
        )

    if not math.isfinite(t_end) or t_end <= 0.0:
        raise ConfigurationError("Resolved integration duration must be positive and finite")

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
            raise ConfigurationError("dt_init must be positive and finite")
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
        "temperature_stop_K": float(temp_stop) if temp_stop is not None else None,
        "t_end_seconds_from_temperature": t_end_seconds_from_temperature,
        "t_end_temperature_search_years": float(temp_search_years) if temp_search_years is not None else None,
    }
    return t_end, dt_nominal, dt_step, n_steps, info


# ===========================================================================
# Configuration Resolution Helpers
# ===========================================================================

def resolve_orbital_radius(cfg: Config) -> tuple[float, str]:
    """Resolve orbital radius from configuration."""

    r_m, _, source = config_utils.resolve_reference_radius(cfg)
    return r_m, source


def resolve_physics_flags(cfg: Config, physics_mode: str) -> PhysicsFlags:
    """Resolve physics control flags from configuration.
    
    Parameters
    ----------
    cfg : Config
        The configuration object.
    physics_mode : str
        The resolved physics mode ("default", "sublimation_only", "collisions_only").
        
    Returns
    -------
    PhysicsFlags
        Resolved physics flags.
    """
    enforce_sublimation_only = physics_mode == "sublimation_only"
    enforce_collisions_only = physics_mode == "collisions_only"
    
    collisions_active = not enforce_sublimation_only
    
    sinks_mode = getattr(cfg.sinks, "mode", "sublimation")
    sinks_enabled = sinks_mode != "none"
    
    sublimation_enabled = bool(
        sinks_enabled
        and (
            getattr(cfg.sinks, "enable_sublimation", False)
            or sinks_mode == "sublimation"
        )
    )
    
    if enforce_sublimation_only:
        sublimation_active = True
    elif enforce_collisions_only:
        sublimation_active = False
    else:
        sublimation_active = sublimation_enabled
    
    blowout_cfg = getattr(cfg, "blowout", None)
    blowout_enabled_cfg = bool(getattr(blowout_cfg, "enabled", True)) if blowout_cfg else True
    
    rp_blowout_cfg = getattr(cfg.sinks, "rp_blowout", None)
    rp_blowout_enabled = bool(getattr(rp_blowout_cfg, "enable", True)) if rp_blowout_cfg else True
    
    radiation_cfg = getattr(cfg, "radiation", None)
    mars_rp_enabled = True
    if radiation_cfg is not None:
        source_raw = getattr(radiation_cfg, "source", "mars")
        radiation_field = str(source_raw).lower()
        mars_rp_enabled = bool(getattr(radiation_cfg, "use_mars_rp", True))
        if radiation_field == "off":
            mars_rp_enabled = False
    
    blowout_enabled = (
        blowout_enabled_cfg
        and collisions_active
        and rp_blowout_enabled
        and mars_rp_enabled
    )
    
    tau_gate_cfg = getattr(radiation_cfg, "tau_gate", None) if radiation_cfg else None
    tau_gate_enabled = bool(getattr(tau_gate_cfg, "enable", False)) if tau_gate_cfg else False
    
    freeze_kappa = bool(getattr(radiation_cfg, "freeze_kappa", False)) if radiation_cfg else False
    freeze_sigma = bool(getattr(cfg.surface, "freeze_sigma", False))
    
    phase_cfg = getattr(cfg, "phase", None)
    phase_enabled = bool(getattr(phase_cfg, "enabled", False)) if phase_cfg else False
    
    gas_drag_enabled = bool(sinks_enabled and getattr(cfg.sinks, "enable_gas_drag", False))
    
    sink_timescale_active = bool(
        (sublimation_enabled or gas_drag_enabled)
        and not enforce_collisions_only
    )
    
    return PhysicsFlags(
        collisions_active=collisions_active,
        sublimation_active=sublimation_active,
        blowout_enabled=blowout_enabled,
        sink_timescale_active=sink_timescale_active,
        freeze_kappa=freeze_kappa,
        freeze_sigma=freeze_sigma,
        tau_gate_enabled=tau_gate_enabled,
        phase_enabled=phase_enabled,
    )


# ===========================================================================
# Utility Functions
# ===========================================================================

def derive_seed_components(cfg: Config) -> str:
    """Return a deterministic seed basis string from configuration inputs."""

    parts: list[str] = []
    try:
        r_m, r_rm, r_source = config_utils.resolve_reference_radius(cfg)
        parts.append(f"reference_radius_m={r_m!r}")
        parts.append(f"reference_radius_RM={r_rm!r}")
        parts.append(f"r_source={r_source}")
    except Exception:
        parts.append("reference_radius_m=None")
    if cfg.disk is not None:
        parts.append(
            f"disk.r_in_RM={cfg.disk.geometry.r_in_RM!r},r_out_RM={cfg.disk.geometry.r_out_RM!r}"
        )
    tm_seed = None
    radiation_cfg = getattr(cfg, "radiation", None)
    if radiation_cfg is not None and getattr(radiation_cfg, "TM_K", None) is not None:
        tm_seed = getattr(radiation_cfg, "TM_K", None)
    driver_cfg = getattr(radiation_cfg, "mars_temperature_driver", None) if radiation_cfg else None
    if tm_seed is None and driver_cfg is not None and getattr(driver_cfg, "constant", None) is not None:
        tm_seed = getattr(driver_cfg.constant, "value_K", None)
    parts.append(f"T_M_basis={tm_seed!r}")
    parts.append(f"initial.mass_total={cfg.initial.mass_total!r}")
    return "|".join(parts)


def resolve_seed(cfg: Config) -> tuple[int, str, str]:
    """Return the RNG seed, seed expression description, and basis."""

    if cfg.dynamics.rng_seed is not None:
        seed_val = int(cfg.dynamics.rng_seed)
        return seed_val, "cfg.dynamics.rng_seed", "user"

    basis = derive_seed_components(cfg)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    seed_val = int(digest[:8], 16) % (2**31)
    safe_basis = basis.replace("'", r"\'")
    expr = f"sha256('{safe_basis}') % 2**31"
    return seed_val, expr, basis


def human_bytes(value: float) -> str:
    """Return a human-readable byte string."""

    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024.0:
            return f"{amount:,.1f} {unit}"
        amount /= 1024.0
    return f"{amount:,.1f} EB"


def memory_estimate(
    n_steps: int,
    n_bins: int,
    run_row_bytes: float = MEMORY_RUN_ROW_BYTES,
    psd_row_bytes: float = MEMORY_PSD_ROW_BYTES,
    *,
    n_cells: int = 1,
    psd_history_enabled: bool = True,
    psd_history_stride: int = 1,
    diagnostics_enabled: bool = True,
    mass_budget_enabled: bool = True,
    mass_budget_cells_enabled: bool = False,
    step_diag_enabled: bool = False,
    diag_row_bytes: float = MEMORY_DIAG_ROW_BYTES,
    smol_value_bytes: float = 8.0,
) -> tuple[str, str]:
    """Return short and long memory hints estimated from expected row counts."""

    steps = max(int(n_steps), 0)
    bins = max(int(n_bins), 0)
    cells = max(int(n_cells), 1)
    stride = max(int(psd_history_stride), 1)

    run_rows = steps * cells
    diag_rows = run_rows if diagnostics_enabled else 0
    budget_rows = steps if mass_budget_enabled else 0
    budget_cells_rows = run_rows if mass_budget_cells_enabled else 0
    step_diag_rows = steps if step_diag_enabled else 0

    if psd_history_enabled and bins > 0 and steps > 0:
        psd_steps = (steps + stride - 1) // stride
        psd_rows = psd_steps * bins * cells
    else:
        psd_rows = 0

    run_mem = run_rows * float(run_row_bytes)
    diag_mem = diag_rows * float(diag_row_bytes)
    psd_mem = psd_rows * float(psd_row_bytes)
    budget_mem = (budget_rows + budget_cells_rows) * float(run_row_bytes)
    step_diag_mem = step_diag_rows * float(diag_row_bytes)
    smol_mem = smol_value_bytes * (bins**2 + bins**3) if bins > 0 else 0.0
    total_mem = run_mem + diag_mem + psd_mem + budget_mem + step_diag_mem + smol_mem
    short = f"{human_bytes(total_mem)} est"
    row_parts = [f"run_rows={run_rows:,}"]
    if diagnostics_enabled:
        row_parts.append(f"diag_rows={diag_rows:,}")
    if psd_history_enabled:
        row_parts.append(f"psd_rows={psd_rows:,}")
    if mass_budget_enabled:
        row_parts.append(f"budget_rows={budget_rows:,}")
    if mass_budget_cells_enabled:
        row_parts.append(f"budget_cells_rows={budget_cells_rows:,}")
    if step_diag_enabled:
        row_parts.append(f"step_diag_rows={step_diag_rows:,}")
    mem_parts = []
    for label, value in (
        ("run", run_mem),
        ("diag", diag_mem),
        ("psd", psd_mem),
        ("budget", budget_mem),
        ("step_diag", step_diag_mem),
        ("smol", smol_mem),
    ):
        if value > 0.0:
            mem_parts.append(f"{label}~{human_bytes(value)}")
    row_text = " ".join(row_parts)
    mem_text = " ".join(mem_parts)
    long = f"[mem est] {row_text} {mem_text} total~{human_bytes(total_mem)}"
    return short, long

def safe_float(value: Any) -> Optional[float]:
    """Return value cast to float when finite, otherwise None.
    
    Parameters
    ----------
    value : Any
        Value to convert.
        
    Returns
    -------
    float or None
        Converted value if finite, else None.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def human_bytes(value: float) -> str:
    """Return a human-readable byte string.
    
    Parameters
    ----------
    value : float
        Number of bytes.
        
    Returns
    -------
    str
        Human-readable string like "1.5 MB".
    """
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024.0:
            return f"{amount:,.1f} {unit}"
        amount /= 1024.0
    return f"{amount:,.1f} EB"


def series_stats(values: List[float]) -> tuple[float, float, float]:
    """Compute min, median, max of a list of values.
    
    Parameters
    ----------
    values : list of float
        Input values.
        
    Returns
    -------
    tuple[float, float, float]
        (min, median, max), or (nan, nan, nan) if empty.
    """
    if not values:
        nan = float("nan")
        return nan, nan, nan
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        nan = float("nan")
        return nan, nan, nan
    return float(np.min(arr)), float(np.median(arr)), float(np.max(arr))
