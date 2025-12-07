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
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .schema import Config
from . import constants

logger = logging.getLogger(__name__)

# ===========================================================================
# Constants
# ===========================================================================
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
MAX_STEPS = 50_000_000
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0
PHASE7_SCHEMA_VERSION = "phase7-minimal-v1"


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
) -> TimeGridInfo:
    """Resolve time grid parameters from configuration.
    
    Determines the total simulation duration, time step, and number of steps
    based on the numerics configuration section.
    
    Parameters
    ----------
    numerics : Numerics
        The numerics configuration object.
    Omega : float
        Keplerian angular frequency [rad s⁻¹].
    t_orb : float
        Orbital period [s].
        
    Returns
    -------
    TimeGridInfo
        Resolved time grid parameters.
        
    Raises
    ------
    ValueError
        If neither t_end_years nor t_end_orbits is specified.
    """
    # Determine t_end
    if numerics.t_end_orbits is not None:
        t_end = float(numerics.t_end_orbits) * t_orb
        t_end_basis = "t_end_orbits"
        t_end_input = float(numerics.t_end_orbits)
    elif numerics.t_end_years is not None:
        t_end = float(numerics.t_end_years) * SECONDS_PER_YEAR
        t_end_basis = "t_end_years"
        t_end_input = float(numerics.t_end_years)
    else:
        raise ValueError("numerics must provide t_end_years or t_end_orbits")
    
    if not math.isfinite(t_end) or t_end <= 0.0:
        raise ValueError("Resolved integration duration must be positive and finite")
    
    # Determine dt
    dt_input = numerics.dt_init
    dt_mode = "auto" if isinstance(dt_input, str) and dt_input.lower() == "auto" else "explicit"
    dt_sources: Dict[str, float] = {}
    t_blow_nominal = 1.0 / Omega if Omega > 0.0 and math.isfinite(Omega) else float("inf")
    
    if dt_mode == "auto":
        candidates: List[float] = []
        
        # Candidate 1: 5% of blowout time
        if math.isfinite(t_blow_nominal) and t_blow_nominal > 0.0:
            value = 0.05 * t_blow_nominal
            dt_sources["0.05*t_blow"] = value
            if value > 0.0 and math.isfinite(value):
                candidates.append(value)
        
        # Candidate 2: t_end / 200
        value = t_end / 200.0
        dt_sources["t_end/200"] = value
        if value > 0.0 and math.isfinite(value):
            candidates.append(value)
        
        dt_nominal = min(candidates) if candidates else t_end
        dt_nominal = max(min(dt_nominal, t_end), 1.0e-9)
    else:
        dt_nominal = float(dt_input)
        if not math.isfinite(dt_nominal) or dt_nominal <= 0.0:
            raise ValueError("dt_init must be positive and finite")
        dt_sources["explicit"] = dt_nominal
    
    # Calculate number of steps
    n_steps = max(1, int(math.ceil(t_end / max(dt_nominal, 1.0e-9))))
    dt_step = t_end / n_steps
    
    dt_capped = False
    if n_steps > MAX_STEPS:
        n_steps = MAX_STEPS
        dt_step = t_end / n_steps
        dt_capped = True
    
    return TimeGridInfo(
        t_end_s=t_end,
        dt_nominal_s=dt_nominal,
        dt_step_s=dt_step,
        n_steps=n_steps,
        t_end_basis=t_end_basis,
        t_end_input=t_end_input,
        dt_mode=dt_mode,
        dt_sources=dt_sources,
        t_blow_nominal_s=t_blow_nominal if math.isfinite(t_blow_nominal) else None,
        dt_capped_by_max_steps=dt_capped,
    )


# ===========================================================================
# Configuration Resolution Helpers
# ===========================================================================

def resolve_orbital_radius(cfg: Config) -> tuple[float, str]:
    """Resolve orbital radius from configuration.
    
    Checks multiple configuration paths in priority order:
    1. geometry.r (direct specification in meters)
    2. geometry.runtime_orbital_radius_rm (Mars radii, deprecated)
    3. disk.geometry (r_in_RM, r_out_RM average)
    4. geometry.r_in (fallback)
    
    Parameters
    ----------
    cfg : Config
        The configuration object.
        
    Returns
    -------
    tuple[float, str]
        (radius_m, source_description)
        
    Raises
    ------
    ValueError
        If no radius can be determined.
    """
    r_source = "geometry.r"
    
    if cfg.geometry.r is not None:
        r = cfg.geometry.r
        r_source = "geometry.r"
    elif getattr(cfg.geometry, "runtime_orbital_radius_rm", None) is not None:
        r = float(cfg.geometry.runtime_orbital_radius_rm) * constants.R_MARS
        r_source = "geometry.runtime_orbital_radius_rm"
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
    
    return r, r_source


def resolve_physics_flags(cfg: Config, single_process_mode: str) -> PhysicsFlags:
    """Resolve physics control flags from configuration.
    
    Parameters
    ----------
    cfg : Config
        The configuration object.
    single_process_mode : str
        The resolved single-process mode ("off", "sublimation_only", "collisions_only").
        
    Returns
    -------
    PhysicsFlags
        Resolved physics flags.
    """
    enforce_sublimation_only = single_process_mode == "sublimation_only"
    enforce_collisions_only = single_process_mode == "collisions_only"
    
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
