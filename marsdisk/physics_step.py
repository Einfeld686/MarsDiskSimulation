"""Per-step physics calculations for Mars disk simulations.

This module provides functions that perform the physics calculations
for a single time step. It encapsulates the computation logic that was
previously embedded in the main loop of run.py.

The step functions follow the coupling order specified in AGENTS.md:

    ⟨Q_pr⟩ → β → a_blow → sublimation ds/dt → τ & Φ → surface sink fluxes

Each function is designed to be stateless with respect to the simulation
history, receiving all necessary inputs as parameters and returning
outputs as structured data.

See Also
--------
- `analysis/physics_flow.md`: Visual diagrams of computation flow
- `analysis/equations.md`: Mathematical definitions
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Callable

import numpy as np

from . import constants, grid
from .physics import radiation, shielding, psd, surface, sinks, sizes
from .physics.sublimation import grain_temperature_graybody
from .runtime.helpers import compute_gate_factor, fast_blowout_correction_factor

logger = logging.getLogger(__name__)

# Constants
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12


@dataclass
class RadiationResult:
    """Results from radiation pressure calculations (R1-R3).
    
    Attributes
    ----------
    qpr_mean : float
        Planck-mean radiation pressure efficiency ⟨Q_pr⟩.
    beta : float
        Radiation pressure ratio β at s_min.
    a_blow : float
        Blowout radius [m].
    T_M : float
        Mars surface temperature used [K].
    """
    qpr_mean: float
    beta: float
    a_blow: float
    T_M: float


@dataclass
class ShieldingResult:
    """Results from optical depth and shielding calculations (S0).
    
    Attributes
    ----------
    tau : float
        Vertical optical depth τ.
    kappa_eff : float
        Effective opacity after shielding [m² kg⁻¹].
    sigma_tau1 : float or None
        Surface density at τ=1 [kg m⁻²].
    phi : float or None
        Shielding coefficient Φ(τ).
    """
    tau: float
    kappa_eff: float
    sigma_tau1: Optional[float]
    phi: Optional[float]


@dataclass
class SublimationResult:
    """Results from sublimation calculations.
    
    Attributes
    ----------
    ds_dt : float
        Size erosion rate [m s⁻¹].
    ds_dt_raw : float
        Uncorrected erosion rate [m s⁻¹].
    T_grain : float or None
        Grain temperature [K].
    blocked_by_phase : bool
        Whether sublimation was blocked by phase state.
    """
    ds_dt: float
    ds_dt_raw: float
    T_grain: Optional[float]
    blocked_by_phase: bool


@dataclass
class SurfaceStepResult:
    """Results from surface layer evolution (S1).
    
    Attributes
    ----------
    sigma_surf : float
        Updated surface density [kg m⁻²].
    outflux : float
        Blowout outflux [kg m⁻² s⁻¹].
    sink_flux : float
        Sink flux [kg m⁻² s⁻¹].
    t_coll : float or None
        Collision timescale [s].
    t_blow : float
        Blowout timescale [s].
    """
    sigma_surf: float
    outflux: float
    sink_flux: float
    t_coll: Optional[float]
    t_blow: float


@dataclass
class PhysicsStepResult:
    """Aggregated results from a full physics step.
    
    This dataclass bundles all sub-results from the computation chain:
    radiation → sublimation → shielding → surface evolution.
    """
    radiation: RadiationResult
    shielding: ShieldingResult
    sublimation: SublimationResult
    surface: SurfaceStepResult
    
    # Mass tracking
    mass_loss_blowout: float = 0.0
    mass_loss_sinks: float = 0.0
    mass_loss_sublimation: float = 0.0
    
    # Derived rates
    M_out_dot: float = 0.0  # [M_Mars s⁻¹]
    M_sink_dot: float = 0.0  # [M_Mars s⁻¹]
    
    # Diagnostics
    dt_over_t_blow: float = 0.0
    fast_blowout_factor: float = 0.0


# ===========================================================================
# Radiation Pressure Functions (R1-R3)
# ===========================================================================

def compute_radiation_parameters(
    s_min: float,
    rho: float,
    T_M: float,
    *,
    qpr_override: Optional[float] = None,
    qpr_lookup_fn: Optional[Callable[[float, float], float]] = None,
    initial: Optional[float] = None,
    a_blow_override: Optional[float] = None,
    iterations: int = 6,
) -> RadiationResult:
    """Compute radiation pressure parameters for the current step.

    This implements the R1-R3 equations from the specification:
    - R1: ⟨Q_pr⟩ at ``s_min`` from table or override
    - R2: β = f(s_min, ρ, T_M, Q_pr)
    - R3: a_blow from iterative self-consistency (optional override supported)

    Parameters
    ----------
    s_min : float
        Minimum grain size [m].
    rho : float
        Grain density [kg m⁻³].
    T_M : float
        Mars surface temperature [K].
    qpr_override : float, optional
        Override value for Q_pr instead of table lookup.
    qpr_lookup_fn : callable, optional
        Optional lookup function ``qpr_lookup_fn(size, T_M)`` for caching.
    initial : float, optional
        Initial size guess for the blowout iteration.
    a_blow_override : float, optional
        Precomputed blowout radius to skip the iteration.
    iterations : int
        Iteration count for self-consistent blowout sizing.

    Returns
    -------
    RadiationResult
        Computed radiation parameters.

    See Also
    --------
    analysis/equations.md : (E.004), (E.013), (E.014)
    """
    lookup = qpr_lookup_fn or radiation.qpr_lookup
    qpr_mean = float(qpr_override) if qpr_override is not None else float(lookup(s_min, T_M))

    if a_blow_override is not None:
        a_blow_val = float(a_blow_override)
    elif qpr_override is not None:
        a_blow_val = float(radiation.blowout_radius(rho, T_M, Q_pr=qpr_mean))
    else:
        s_eval = max(float(initial if initial is not None else s_min), 1.0e-12)
        for _ in range(max(int(iterations), 1)):
            qpr_blow = float(lookup(s_eval, T_M))
            a_blow_val = float(radiation.blowout_radius(rho, T_M, Q_pr=qpr_blow))
            s_eval = max(float(a_blow_val), 1.0e-12)
        qpr_blow = float(lookup(s_eval, T_M))
        a_blow_val = float(radiation.blowout_radius(rho, T_M, Q_pr=qpr_blow))

    beta_val = radiation.beta(s_min, rho, T_M, Q_pr=qpr_mean)

    return RadiationResult(
        qpr_mean=qpr_mean,
        beta=beta_val,
        a_blow=a_blow_val,
        T_M=T_M,
    )


# ===========================================================================
# Shielding Functions (S0)
# ===========================================================================

def compute_shielding(
    kappa_surf: float,
    sigma_surf: float,
    *,
    mode: str = "psitau",
    phi_tau_fn: Any = None,
    tau_fixed: Optional[float] = None,
    sigma_tau1_fixed: Optional[float] = None,
    los_factor: float = 1.0,
) -> ShieldingResult:
    """Compute optical depth and shielding correction.
    
    This implements the S0 equation: Φ(τ, ω₀, g) applied to κ_eff.
    
    Parameters
    ----------
    kappa_surf : float
        Surface opacity [m² kg⁻¹].
    sigma_surf : float
        Surface density [kg m⁻²].
    mode : str
        Shielding mode: "psitau", "fixed_tau1", or "off".
    phi_tau_fn : callable, optional
        Function Φ(τ) for shielding interpolation.
    tau_fixed : float, optional
        Fixed τ value for "fixed_tau1" mode.
    sigma_tau1_fixed : float, optional
        Fixed Σ_{τ=1} value.
    los_factor : float, optional
        Multiplicative factor converting vertical τ to Mars line-of-sight τ.
        
    Returns
    -------
    ShieldingResult
        Computed shielding parameters.
        
    See Also
    --------
    analysis/equations.md : (E.020)–(E.022)
    """
    los_factor_val = los_factor if los_factor > 0.0 else 1.0
    tau_vert = kappa_surf * sigma_surf
    tau = tau_vert * los_factor_val
    
    if mode == "off":
        sigma_tau1 = shielding.sigma_tau1(kappa_surf)
        phi = kappa_surf / kappa_surf if kappa_surf > 0.0 else None
        return ShieldingResult(
            tau=tau,
            kappa_eff=kappa_surf,
            sigma_tau1=sigma_tau1,
            phi=phi,
        )
    
    if mode == "fixed_tau1":
        tau_target = tau_fixed if tau_fixed is not None and math.isfinite(tau_fixed) else tau
        
        if sigma_tau1_fixed is not None:
            sigma_tau1 = float(sigma_tau1_fixed)
            if kappa_surf > 0.0 and not math.isfinite(tau_target):
                tau_target = kappa_surf * sigma_tau1 * los_factor_val
        else:
            sigma_tau1 = None
        
        if phi_tau_fn is not None:
            kappa_eff = shielding.effective_kappa(kappa_surf, tau_target, phi_tau_fn)
        else:
            kappa_eff = kappa_surf
        
        if sigma_tau1 is None:
            if kappa_eff <= 0.0:
                sigma_tau1 = float("inf")
            else:
                sigma_tau1 = float(tau_target / max(kappa_eff, 1.0e-30))
        
        phi = kappa_eff / kappa_surf if kappa_surf > 0.0 else None
        
        return ShieldingResult(
            tau=tau_target,
            kappa_eff=kappa_eff,
            sigma_tau1=sigma_tau1,
            phi=phi,
        )
    
    # Default: psitau mode
    if phi_tau_fn is not None:
        kappa_eff = shielding.effective_kappa(kappa_surf, tau, phi_tau_fn)
        sigma_tau1 = shielding.sigma_tau1(kappa_eff)
    else:
        kappa_eff, sigma_tau1 = shielding.apply_shielding(kappa_surf, tau, 0.0, 0.0)
    
    phi = kappa_eff / kappa_surf if kappa_surf > 0.0 else None
    
    return ShieldingResult(
        tau=tau,
        kappa_eff=kappa_eff,
        sigma_tau1=sigma_tau1,
        phi=phi,
    )


# ===========================================================================
# Sublimation Functions
# ===========================================================================

def compute_sublimation(
    T_M: float,
    r: float,
    rho: float,
    sub_params: Any,
    *,
    phase_state: str = "solid",
    enabled: bool = True,
) -> SublimationResult:
    """Compute sublimation erosion rate.
    
    Parameters
    ----------
    T_M : float
        Mars surface temperature [K].
    r : float
        Orbital radius [m].
    rho : float
        Grain density [kg m⁻³].
    sub_params : SublimationParams
        Sublimation model parameters.
    phase_state : str
        Current phase state ("solid", "liquid", "vapor").
    enabled : bool
        Whether sublimation is active.
        
    Returns
    -------
    SublimationResult
        Computed sublimation parameters.
    """
    if not enabled:
        return SublimationResult(
            ds_dt=0.0,
            ds_dt_raw=0.0,
            T_grain=None,
            blocked_by_phase=False,
        )
    
    T_grain = grain_temperature_graybody(T_M, r)
    
    try:
        ds_dt_raw = sizes.eval_ds_dt_sublimation(T_grain, rho, sub_params)
    except ValueError:
        ds_dt_raw = 0.0
    
    blocked = phase_state == "liquid_dominated" and ds_dt_raw < 0.0
    ds_dt = 0.0 if blocked else ds_dt_raw
    
    return SublimationResult(
        ds_dt=ds_dt,
        ds_dt_raw=ds_dt_raw,
        T_grain=T_grain,
        blocked_by_phase=blocked,
    )


# ===========================================================================
# Surface Evolution (S1)
# ===========================================================================

def step_surface_layer(
    sigma_surf: float,
    prod_rate: float,
    dt: float,
    Omega: float,
    *,
    tau: Optional[float] = None,
    t_sink: Optional[float] = None,
    sigma_tau1: Optional[float] = None,
    enable_blowout: bool = True,
    chi_blow: float = 1.0,
) -> SurfaceStepResult:
    """Advance the surface layer by one time step.
    
    This implements the S1 equation using implicit Euler:
    
        Σ^{n+1} = (Σ^n + Δt·prod) / (1 + Δt·λ)
        
    where λ = 1/t_blow + I_coll/t_coll + I_sink/t_sink.
    
    Parameters
    ----------
    sigma_surf : float
        Current surface density [kg m⁻²].
    prod_rate : float
        Production rate [kg m⁻² s⁻¹].
    dt : float
        Time step [s].
    Omega : float
        Keplerian angular frequency [rad s⁻¹].
    tau : float, optional
        Optical depth for collision timescale.
    t_sink : float, optional
        Sink timescale [s].
    sigma_tau1 : float, optional
        Surface density limit at τ=1 [kg m⁻²].
    enable_blowout : bool
        Whether blowout is active.
    chi_blow : float
        Blowout correction factor.
        
    Returns
    -------
    SurfaceStepResult
        Updated surface state and fluxes.
        
    See Also
    --------
    analysis/equations.md : (E.007)
    """
    t_blow = chi_blow / Omega if Omega > 0.0 else float("inf")
    
    # Compute collision timescale if tau is provided
    t_coll = None
    if tau is not None and tau > TAU_MIN and Omega > 0.0:
        t_coll = 1.0 / (Omega * tau)
    
    # Call the physics module
    result = surface.step_surface(
        sigma_surf,
        prod_rate,
        dt,
        Omega,
        tau=tau,
        t_blow=t_blow,
        t_sink=t_sink,
        sigma_tau1=sigma_tau1,
        enable_blowout=enable_blowout,
    )
    
    return SurfaceStepResult(
        sigma_surf=result.sigma_surf,
        outflux=result.outflux,
        sink_flux=result.sink_flux,
        t_coll=t_coll,
        t_blow=t_blow,
    )

