"""Configuration schema for Mars disk simulations.

This module defines Pydantic models that mirror the structure of the YAML
configuration files used by :mod:`marsdisk.run`.  Only a subset of the
parameters from the full research code is required for the unit tests.  The
models nevertheless follow the layout described in AGENTS.md so that the
configuration files remain forward compatible.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator, root_validator, validator

from . import constants
from .errors import ConfigurationError

DEFAULT_PHASE_ENTRYPOINT = "siO2_disk_cooling.siO2_cooling_map:lookup_phase_state"


class Geometry(BaseModel):
    """Geometric configuration of the simulation domain."""

    mode: Literal["0D", "1D"] = Field("0D", description="Spatial dimension: '0D' (radially uniform) or '1D'")
    r_in: Optional[float] = Field(None, description="Inner radius for 1D runs [m]")
    r_out: Optional[float] = Field(None, description="Outer radius for 1D runs [m]")
    Nr: Optional[int] = Field(None, description="Number of radial zones for 1D runs")

    @model_validator(mode="before")
    def _forbid_deprecated_radius(cls, data: Any) -> Any:
        """Disallow legacy radius keys that have been fully removed."""

        if not isinstance(data, dict):
            return data
        if "r" in data and data.get("r") is not None:
            raise ConfigurationError("geometry.r is no longer supported; use disk.geometry.r_in_RM/r_out_RM instead.")
        if "runtime_orbital_radius_rm" in data and data.get("runtime_orbital_radius_rm") is not None:
            raise ConfigurationError(
                "geometry.runtime_orbital_radius_rm is no longer supported; use disk.geometry.r_in_RM/r_out_RM instead."
            )
        return data


class DiskGeometry(BaseModel):
    """Geometry of the inner disk in units of Mars radii.

    This is the preferred way to specify orbital geometry.
    All radii are expressed in Mars radii (R_Mars ≈ 3389.5 km).

    Example:
        disk:
          geometry:
            r_in_RM: 2.2   # Inner edge at 2.2 Mars radii
            r_out_RM: 2.7  # Outer edge at 2.7 Mars radii
    """

    r_in_RM: float = Field(..., gt=0, description="Inner radius [Mars radii]")
    r_out_RM: float = Field(..., gt=0, description="Outer radius [Mars radii]")
    r_profile: Literal["uniform", "powerlaw"] = Field(
        "uniform",
        description="Radial surface density profile: 'uniform' or 'powerlaw' (Σ ∝ r^-p)",
    )
    p_index: float = Field(0.0, description="Power-law index for surface density (Σ ∝ r^-p)")

    @model_validator(mode="after")
    def _check_radius_order(cls, model: "DiskGeometry") -> "DiskGeometry":
        r_in = model.r_in_RM
        r_out = model.r_out_RM
        if r_in is not None and r_out is not None and r_in > r_out:
            raise ConfigurationError(f"disk.geometry.r_in_RM ({r_in}) must be less than or equal to r_out_RM ({r_out})")
        return model


class Disk(BaseModel):
    """Container for inner disk properties.

    This is the preferred location for specifying disk geometry.
    """

    geometry: DiskGeometry


class Scope(BaseModel):
    """Scope settings that restrict the analysis window and region."""

    region: Literal["inner"] = Field(
        "inner",
        description="Spatial scope selector. Phase 0 restricts runs to the inner disk.",
    )
    analysis_years: float = Field(
        2.0,
        gt=0.0,
        description="Total analysis window expressed in years.",
    )


class InnerDiskMass(BaseModel):
    """Scaling for the total mass of the inner disk."""

    use_Mmars_ratio: bool = True
    M_in_ratio: float = 3.0e-5
    map_to_sigma: Literal["analytic"] = "analytic"
    M_over_Mmars: Optional[float] = Field(
        None,
        description="Legacy alias for M_in_ratio retained for agent tasks.",
    )

    @model_validator(mode="before")
    def _alias_m_over_mmars(cls, data: Any) -> Any:
        """Normalise M_over_Mmars to M_in_ratio."""

        if not isinstance(data, dict):
            return data
        if "M_over_Mmars" in data and "M_in_ratio" not in data:
            data["M_in_ratio"] = data["M_over_Mmars"]
        return data


class SupplyConst(BaseModel):
    prod_area_rate_kg_m2_s: float = 0.0
    auto_from_tau1_tfill_years: Optional[float] = Field(
        None,
        gt=0.0,
        description=(
            "Optional fill time (years) to derive prod_area_rate_kg_m2_s from Σ_{τ=1}: "
            "prod_rate = (Sigma_tau1 / t_fill) / epsilon_mix when provided."
        ),
    )


class SupplyPowerLaw(BaseModel):
    A_kg_m2_s: Optional[float] = None
    t0_s: float = 0.0
    index: float = -1.0


class SupplyTable(BaseModel):
    path: Path = Path("data/supply_rate.csv")
    interp: Literal["linear"] = "linear"


class SupplyMixing(BaseModel):
    epsilon_mix: float = 0.05
    mu: Optional[float] = Field(
        None,
        description="Alias for epsilon_mix; if provided, overrides epsilon_mix.",
    )

    @model_validator(mode="before")
    def _alias_mu(cls, data: Any) -> Any:
        """Allow 'mu' as an alias for 'epsilon_mix'."""

        if not isinstance(data, dict):
            return data
        if "mu" in data and "epsilon_mix" not in data:
            data["epsilon_mix"] = data["mu"]
        return data

    @field_validator("epsilon_mix")
    def _validate_epsilon_mix(cls, value: float) -> float:
        """Restrict mixing efficiency to the physical interval [0, 1]."""

        if value < 0.0 or value > 1.0:
            raise ConfigurationError("supply.mixing.epsilon_mix must lie within [0, 1]")
        return value


class SupplyReservoir(BaseModel):
    enabled: bool = Field(
        False,
        description="Enable finite reservoir accounting; false keeps the legacy infinite reservoir behaviour.",
    )
    mass_total_Mmars: Optional[float] = Field(
        None,
        ge=0.0,
        description="Optional finite reservoir in Mars masses; None keeps the legacy infinite reservoir.",
    )
    depletion_mode: Literal["hard_stop", "taper"] = Field(
        "hard_stop",
        description="When 'taper', linearly ramp the rate down once the remaining mass falls below taper_fraction of the total.",
    )
    taper_fraction: float = Field(
        0.05,
        ge=0.0,
        le=1.0,
        description="Fraction of the reservoir at which the smooth ramp begins when depletion_mode='taper'.",
    )

    @model_validator(mode="before")
    def _normalise_aliases(cls, data: Any) -> Any:
        """Backwards-compatible aliases for reservoir controls."""

        if not isinstance(data, dict):
            return data
        if "smooth_fraction" in data and "taper_fraction" not in data:
            data["taper_fraction"] = data["smooth_fraction"]
        mode = data.get("depletion_mode")
        if mode == "smooth":
            data["depletion_mode"] = "taper"
        if data.get("enabled") is None and data.get("mass_total_Mmars") is not None:
            data["enabled"] = True
        return data

    @model_validator(mode="after")
    def _require_mass_when_enabled(cls, model: "SupplyReservoir") -> "SupplyReservoir":
        """Ensure a finite mass is provided when the reservoir is enabled."""

        if model.enabled and model.mass_total_Mmars is None:
            raise ConfigurationError("supply.reservoir.mass_total_Mmars must be set when reservoir.enabled=true")
        return model


class SupplyFeedback(BaseModel):
    enabled: bool = False
    target_tau: float = Field(
        1.0,
        ge=0.0,
        description="Target optical depth for proportional control.",
    )
    gain: float = Field(
        1.0,
        ge=0.0,
        description="Dimensionless proportional gain applied to the normalised tau error.",
    )
    response_time_years: float = Field(
        0.5,
        gt=0.0,
        description="Response time controlling how quickly the feedback scale reacts (years).",
    )
    min_scale: float = Field(
        1.0e-6,
        ge=0.0,
        description="Lower bound on the feedback multiplier (kept slightly above 0 to avoid locking the scale).",
    )
    max_scale: float = Field(
        10.0,
        gt=0.0,
        description="Upper bound on the feedback multiplier.",
    )
    tau_field: Literal["tau_vertical", "tau_los"] = Field(
        "tau_los",
        description="Optical-depth field to monitor for feedback control.",
    )
    initial_scale: float = Field(
        1.0,
        ge=0.0,
        description="Initial multiplier applied before any feedback updates.",
    )

    @field_validator("max_scale")
    def _validate_scale_bounds(cls, value: float, info: ValidationInfo) -> float:
        min_scale = info.data.get("min_scale", 0.0)
        if value <= 0.0:
            raise ConfigurationError("feedback.max_scale must be positive")
        if value < min_scale:
            raise ConfigurationError("feedback.max_scale must be greater than or equal to min_scale")
        return value


class SupplyTemperatureTable(BaseModel):
    path: Path = Path("data/supply_temperature_map.csv")
    value_kind: Literal["scale", "rate"] = Field(
        "scale",
        description="Whether the table values represent a dimensionless scale or an absolute rate.",
    )
    column_temperature: str = "T_K"
    column_value: str = "value"


class SupplyTemperature(BaseModel):
    enabled: bool = False
    mode: Literal["scale", "table"] = Field(
        "scale",
        description="Temperature coupling mode: analytic scale or table-driven lookup.",
    )
    reference_K: float = Field(
        1800.0,
        gt=0.0,
        description="Reference temperature for the analytic scaling mode.",
    )
    exponent: float = 1.0
    scale_at_reference: float = Field(
        1.0,
        ge=0.0,
        description="Multiplier applied at the reference temperature.",
    )
    floor: float = Field(
        0.0,
        ge=0.0,
        description="Minimum temperature multiplier (scale mode) or applied after table lookup when value_kind='scale'.",
    )
    cap: float = Field(
        10.0,
        gt=0.0,
        description="Maximum temperature multiplier (scale mode) or applied after table lookup when value_kind='scale'.",
    )
    table: SupplyTemperatureTable = Field(
        default_factory=SupplyTemperatureTable,
        description="Table configuration when mode='table'.",
    )


class SupplyTransport(BaseModel):
    """Routing of external supply between deep and surface reservoirs."""

    mode: Literal["direct", "deep_mixing"] = Field(
        "direct",
        description="direct: legacy headroom-gated surface injection. deep_mixing: send supply into deep then mix up.",
    )
    t_mix_orbits: Optional[float] = Field(
        None,
        ge=0.0,
        description="Mixing time from deep reservoir to surface (orbits). Required when mode='deep_mixing'.",
    )
    headroom_gate: Literal["hard", "soft"] = Field(
        "hard",
        description="Headroom limiter applied to deep→surface flux; 'soft' is reserved for future smoothing.",
    )

    @model_validator(mode="after")
    def _require_tmix_for_mixing(cls, model: "SupplyTransport") -> "SupplyTransport":
        mode = model.mode
        t_mix = model.t_mix_orbits
        if mode == "deep_mixing":
            if t_mix is None or t_mix <= 0.0 or not isinstance(t_mix, (int, float)):
                raise ConfigurationError("supply.transport.t_mix_orbits must be positive when mode='deep_mixing'")
        return model


class SupplyInjectionVelocity(BaseModel):
    """Velocity/eccentricity controls dedicated to the incoming supply."""

    mode: Literal["inherit", "fixed_ei", "factor"] = Field(
        "inherit",
        description="inherit: use kernel baseline. fixed_ei: override with e_inj/i_inj. factor: scale baseline v_rel.",
    )
    e_inj: Optional[float] = Field(
        None,
        ge=0.0,
        description="Injection eccentricity when mode='fixed_ei'.",
    )
    i_inj: Optional[float] = Field(
        None,
        ge=0.0,
        description="Injection inclination [rad] when mode='fixed_ei'.",
    )
    vrel_factor: Optional[float] = Field(
        None,
        ge=0.0,
        description="Relative-velocity multiplier when mode='factor'; applied as a scale on e/i.",
    )
    blend_mode: Literal["rms", "linear"] = Field(
        "rms",
        description="Blend effective e/i via RMS or linear mixing.",
    )
    weight_mode: Literal["delta_sigma", "sigma_ratio"] = Field(
        "delta_sigma",
        description="delta_sigma: ΔΣ/(Σ+ΔΣ). sigma_ratio: ΔΣ/max(Σ,eps).",
    )

    @model_validator(mode="after")
    def _validate_velocity_params(cls, model: "SupplyInjectionVelocity") -> "SupplyInjectionVelocity":
        mode = model.mode
        if mode == "fixed_ei":
            if model.e_inj is None or model.i_inj is None:
                raise ConfigurationError("supply.injection.velocity.mode='fixed_ei' requires e_inj and i_inj")
        if mode == "factor":
            if model.vrel_factor is None:
                raise ConfigurationError("supply.injection.velocity.mode='factor' requires vrel_factor")
        return model


class SupplyInjection(BaseModel):
    """Controls how external supply is injected into the PSD and surface layer."""

    mode: Literal["min_bin", "powerlaw_bins"] = Field(
        "min_bin",
        description="Injection mapping: 'min_bin' targets the smallest valid bin; 'powerlaw_bins' spreads mass across a size range.",
    )
    s_inj_min: Optional[float] = Field(
        None,
        ge=0.0,
        description="Lower bound of the injection size range [m]; defaults to the smallest available bin.",
    )
    s_inj_max: Optional[float] = Field(
        None,
        ge=0.0,
        description="Upper bound of the injection size range [m]; defaults to the largest available bin.",
    )
    q: float = Field(
        3.5,
        gt=0.0,
        description="Power-law exponent for dN/ds ∝ s^{-q} when mode='powerlaw_bins'.",
    )
    deep_reservoir_tmix_orbits: Optional[float] = Field(
        None,
        ge=0.0,
        description="Optional mixing time from the deep reservoir to the surface in orbital periods; None/0 disables the deep buffer.",
    )
    velocity: SupplyInjectionVelocity = Field(
        default_factory=SupplyInjectionVelocity,
        description="Effective eccentricity/inclination settings applied to the injected supply.",
    )

    @model_validator(mode="after")
    def _check_range(cls, model: "SupplyInjection") -> "SupplyInjection":
        s_min = model.s_inj_min
        s_max = model.s_inj_max
        if s_min is not None and s_max is not None and s_max <= s_min:
            raise ConfigurationError("supply.injection.s_inj_max must exceed s_inj_min when both are set")
        return model


class SupplyPiece(BaseModel):
    t_start_s: float
    t_end_s: float
    mode: Literal["const", "powerlaw", "table"] = "const"
    const: SupplyConst = SupplyConst()
    powerlaw: SupplyPowerLaw = SupplyPowerLaw()
    table: SupplyTable = SupplyTable()


class Supply(BaseModel):
    """Parameterisation of external surface supply.

    Simplified Usage:
        Only specify the parameters for the mode you're using.
        Other mode parameters can be omitted and will use defaults.

        Example (const mode - minimal):
            supply:
              mode: "const"
              const:
                prod_area_rate_kg_m2_s: 1.0e-10

        Example (table mode - minimal):
            supply:
              mode: "table"
              table:
                path: "data/my_supply.csv"
    """

    enabled: bool = Field(
        True,
        description="Master switch for external supply; false forces zero production.",
    )
    mode: Literal["const", "table", "powerlaw", "piecewise"] = Field(
        "const",
        description="Supply mode: 'const' (default), 'table', 'powerlaw', or 'piecewise'",
    )
    const: SupplyConst = Field(
        default_factory=SupplyConst,
        description="Parameters for const mode (only needed if mode='const')",
    )
    powerlaw: SupplyPowerLaw = Field(
        default_factory=SupplyPowerLaw,
        description="Parameters for powerlaw mode (only needed if mode='powerlaw')",
    )
    table: SupplyTable = Field(
        default_factory=SupplyTable,
        description="Parameters for table mode (only needed if mode='table')",
    )
    mixing: SupplyMixing = Field(
        default_factory=SupplyMixing,
        description="Mixing parameters (optional, applies to all modes)",
    )
    headroom_policy: Literal["clip", "spill"] = Field(
        "clip",
        description="clip: limit applied supply by Σ_tau1 headroom. spill: always apply supply then remove any τ>1 overflow.",
    )
    reservoir: SupplyReservoir = Field(
        default_factory=SupplyReservoir,
        description="Optional finite reservoir and depletion handling.",
    )
    feedback: SupplyFeedback = Field(
        default_factory=SupplyFeedback,
        description="Optional τ-based proportional feedback controller.",
    )
    temperature: SupplyTemperature = Field(
        default_factory=SupplyTemperature,
        description="Optional temperature-driven scaling of the supply rate.",
    )
    transport: SupplyTransport = Field(
        default_factory=SupplyTransport,
        description="Transport mode for routing supply to the surface or deep reservoir.",
    )
    injection: SupplyInjection = Field(
        default_factory=SupplyInjection,
        description="Mapping from external supply to PSD bins and optional deep-reservoir mixing.",
    )
    piecewise: list[SupplyPiece] = Field(
        default_factory=list,
        description="Piecewise segments (only needed if mode='piecewise')",
    )

    @model_validator(mode="before")
    def _align_transport_aliases(cls, data: Any) -> Any:
        """Normalise deep-buffer controls between injection and transport blocks."""

        if not isinstance(data, dict):
            return data
        injection_cfg = data.get("injection") or {}
        transport_cfg = data.get("transport") or {}
        # Allow deep_reservoir_tmix_orbits (legacy) to populate transport.t_mix_orbits when unset.
        deep_tmix_alias = None
        if isinstance(injection_cfg, dict):
            deep_tmix_alias = injection_cfg.get("deep_reservoir_tmix_orbits")
        if transport_cfg is None:
            transport_cfg = {}
        if isinstance(transport_cfg, dict):
            if transport_cfg.get("t_mix_orbits") is None and deep_tmix_alias is not None:
                transport_cfg["t_mix_orbits"] = deep_tmix_alias
            elif (
                deep_tmix_alias is not None
                and transport_cfg.get("t_mix_orbits") is not None
                and transport_cfg.get("t_mix_orbits") != deep_tmix_alias
            ):
                raise ConfigurationError("supply.transport.t_mix_orbits and injection.deep_reservoir_tmix_orbits conflict; set only one")
            data["transport"] = transport_cfg
        return data


class Material(BaseModel):
    """Material properties of the solids."""

    rho: float = Field(3000.0, gt=0.0, description="Bulk density [kg/m^3]")

    @field_validator("rho")
    def _check_rho_range(cls, value: float) -> float:
        low, high = constants.RHO_RANGE
        if not (low <= value <= high):
            raise ConfigurationError(
                f"Material density rho must lie within [{low}, {high}] kg/m^3"
            )
        return value


class Temps(BaseModel):
    """Thermal parameters.

    .. deprecated::
        `temps.T_M` is deprecated and will be removed in a future version.
        Use `radiation.TM_K` instead for specifying the Mars infrared temperature.
        During the transition period, if both are specified, `radiation.TM_K` takes
        precedence. If only `temps.T_M` is specified, a DeprecationWarning is issued
        and the value is automatically used as a fallback for `radiation.TM_K`.
    """

    T_M: float = Field(2000.0, description="Surface temperature of Mars [K] (DEPRECATED: use radiation.TM_K)")

    @field_validator("T_M")
    def _check_temperature_range(cls, value: float) -> float:
        Tmin, Tmax = 1000.0, 6500.0
        if not (Tmin <= value <= Tmax):
            raise ConfigurationError(f"Mars temperature T_M must lie within [{Tmin}, {Tmax}] K")
        step = 50.0
        # allow small numerical noise by rounding
        if abs((value - Tmin) % step) > 1e-6 and abs((value - Tmax) % step) > 1e-6:
            # values outside the 50 K cadence are allowed but logged via warning
            # during validation in the physics module; here we only ensure range.
            pass
        return value


class Sizes(BaseModel):
    """Particle size grid specification."""

    s_min: float = Field(..., description="Minimum grain size [m]")
    s_max: float = Field(..., description="Maximum grain size [m]")
    n_bins: int = Field(40, ge=1, description="Number of logarithmic size bins")
    evolve_min_size: bool = Field(
        False,
        description="Enable dynamic evolution of the minimum grain size.",
    )
    dsdt_model: Optional[str] = Field(
        None,
        description="Identifier for the minimum-size evolution prescription.",
    )
    dsdt_params: Dict[str, float] = Field(
        default_factory=dict,
        description="Model parameters for the minimum-size evolution prescription.",
    )
    apply_evolved_min_size: bool = Field(
        False,
        description="If true, the evolved minimum size participates in s_min_effective.",
    )


class Initial(BaseModel):
    """Initial mass and PSD mode."""

    mass_total: float = Field(..., description="Total initial mass in Mars masses")
    s0_mode: Literal[
        "mono",
        "upper",
        "melt_lognormal_mixture",
        "melt_truncated_powerlaw",
    ] = Field(
        "upper",
        description=(
            "Initial PSD mode. 'upper' keeps the default cascade, 'mono' forces a mono-disperse bin, "
            "and melt_* variants initialise solids with melt-derived grains while removing condensation dust."
        ),
    )
    class MeltPSD(BaseModel):
        mode: Literal["lognormal_mixture", "truncated_powerlaw"] = Field(
            "lognormal_mixture",
            description="Shape applied when s0_mode starts with melt_.",
        )
        f_fine: float = Field(
            0.3,
            ge=0.0,
            le=1.0,
            description="Mass fraction assigned to the ~100 µm component in the melt mixture.",
        )
        s_fine: float = Field(
            1.0e-4,
            gt=0.0,
            description="Characteristic size of the fine (~100 µm) melt fragment [m].",
        )
        s_meter: float = Field(
            1.5,
            gt=0.0,
            description="Characteristic size of the meter-scale melt droplets [m].",
        )
        width_dex: float = Field(
            0.3,
            gt=0.0,
            description="Log10 width (dex) shared by both components in the melt mixture.",
        )
        s_cut_condensation: float = Field(
            1.0e-6,
            gt=0.0,
            description="Sizes below this cut are treated as condensation dust and zeroed in the initial PSD [m].",
        )
        s_min_solid: float = Field(
            1.0e-4,
            gt=0.0,
            description="Minimum size populated by the melt truncated power-law [m].",
        )
        s_max_solid: float = Field(
            3.0,
            gt=0.0,
            description="Maximum size populated by the melt truncated power-law [m].",
        )
        alpha_solid: float = Field(
            3.5,
            description="Power-law slope dN/ds ∝ s^-alpha_solid for melt solids (Jutzi et al. 2010 motivated).",
        )

        @field_validator("s_max_solid")
        def _check_s_range(cls, value: float, info: ValidationInfo) -> float:
            s_min = info.data.get("s_min_solid", None)
            if s_min is not None and value <= s_min:
                raise ConfigurationError("s_max_solid must exceed s_min_solid")
            return value

    melt_psd: MeltPSD = Field(
        default_factory=MeltPSD,
        description="Parameters controlling melt-solid initial PSD modes.",
    )


class Dynamics(BaseModel):
    """Parameters governing dynamical excitation."""

    e0: float
    i0: float
    t_damp_orbits: float
    f_wake: float = 1.0
    eps_restitution: float = Field(
        0.5,
        gt=0.0,
        le=1.0,
        description="Coefficient of restitution used for collision energy bookkeeping (0<eps<=1).",
    )
    f_ke_cratering: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="Non-dissipated energy fraction f_ke applied to cratering (F_lf>0.5) collisions.",
    )
    f_ke_fragmentation: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional f_ke for catastrophic fragmentation (F_lf<=0.5); None uses eps_restitution**2.",
    )
    enable_e_damping: bool = Field(
        False,
        description="Enable post-collision e/i damping (off by default; formula selected in run-time logic).",
    )
    kernel_ei_mode: Literal["config", "wyatt_eq"] = Field(
        "config",
        description="How to choose e/i for collision kernels: 'config' uses e0/i0, 'wyatt_eq' solves for c_eq",
    )
    v_rel_mode: Literal["ohtsuki", "pericenter"] = Field(
        "pericenter",
        description=(
            "Relative speed prescription for collision kernels. "
            "'pericenter' (default) uses v_rel=v_K/√(1-e) near periapsis and is recommended for high-e discs; "
            "'ohtsuki' (legacy, discouraged for e≳0.1) uses v_rel=v_K*sqrt(1.25 e^2+i^2)."
        ),
    )
    kernel_H_mode: Literal["ia", "fixed"] = Field(
        "ia",
        description="Scale height prescription for collision kernels",
    )
    H_factor: float = Field(
        1.0,
        description="Multiplier applied to H when kernel_H_mode='ia'",
    )
    H_fixed_over_a: Optional[float] = Field(
        None,
        description="Fixed H/a used when kernel_H_mode='fixed'",
    )
    e_mode: Literal["fixed", "mars_clearance"] = Field(
        "fixed",
        description="Initial eccentricity mode; 'mars_clearance' samples Δr in meters",
    )
    dr_min_m: Optional[float] = Field(
        None,
        description="Minimum Δr offset above R_Mars used for eccentricity sampling [m]",
    )
    dr_max_m: Optional[float] = Field(
        None,
        description="Maximum Δr offset above R_Mars used for eccentricity sampling [m]",
    )
    dr_dist: Literal["uniform", "loguniform"] = Field(
        "uniform",
        description="Distribution for Δr sampling; interpreted in meters",
    )
    i_mode: Literal["fixed", "obs_tilt_spread"] = Field(
        "fixed",
        description="Initial inclination mode; 'obs_tilt_spread' samples i0 in radians",
    )
    obs_tilt_deg: float = Field(
        30.0,
        description="Observer tilt centre for inclination sampling [deg]",
    )
    i_spread_deg: float = Field(
        0.0,
        description="Half-width of inclination sampling window around obs_tilt_deg [deg]",
    )
    rng_seed: Optional[int] = Field(
        None,
        description="Optional seed for eccentricity/inclination RNG sampling (dimensionless)",
    )

    @model_validator(mode="after")
    def _check_kernel_H_params(cls, model: "Dynamics") -> "Dynamics":
        if model.kernel_H_mode == "fixed" and model.H_fixed_over_a is None:
            raise ConfigurationError("kernel_H_mode='fixed' requires H_fixed_over_a to be set")
        return model

    @field_validator("f_ke_fragmentation")
    def _check_f_ke_fragmentation(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if value < 0.0 or value > 1.0:
            raise ConfigurationError("dynamics.f_ke_fragmentation must be within [0, 1] or None")
        return float(value)


class QStar(BaseModel):
    """Strength law parameters for catastrophic disruption."""

    Qs: float
    a_s: float
    B: float
    b_g: float
    v_ref_kms: List[float]
    coeff_units: Literal["ba99_cgs", "si"] = Field(
        "ba99_cgs",
        description="Unit system for Qs/B coefficients: 'ba99_cgs' treats sizes in cm, rho in g/cm^3 and converts erg/g→J/kg; 'si' uses inputs as-is.",
    )
    override_coeffs: bool = Field(
        False,
        description="Use Q_D* coefficient table from config instead of the built-in defaults.",
    )
    coeff_scale: float = Field(
        1.0,
        gt=0.0,
        description="Scale factor applied to Qs and B when override_coeffs=true.",
    )
    coeff_table: Optional[Dict[float, List[float]]] = Field(
        None,
        description="Optional coefficient table mapping v_ref_kms to [Qs, a_s, B, b_g].",
    )
    mu_grav: float = Field(
        0.45,
        gt=0.0,
        description="Gravity-regime velocity exponent mu used for v^{-3mu+2} scaling applied to the gravity term when extrapolating Q_D^* beyond the tabulated velocities (LS09/Jutzi-style).",
    )

    @field_validator("coeff_table")
    def _check_coeff_table(cls, value: Optional[Dict[float, List[float]]]) -> Optional[Dict[float, List[float]]]:
        if value is None:
            return None
        if not value:
            raise ConfigurationError("qstar.coeff_table must not be empty when provided")
        for v_ref, coeffs in value.items():
            try:
                v_val = float(v_ref)
            except (TypeError, ValueError) as exc:
                raise ConfigurationError(f"qstar.coeff_table key {v_ref!r} is not a valid float") from exc
            if v_val <= 0.0:
                raise ConfigurationError("qstar.coeff_table velocity keys must be positive")
            if not isinstance(coeffs, (list, tuple)) or len(coeffs) != 4:
                raise ConfigurationError(
                    "qstar.coeff_table values must be a 4-item list [Qs, a_s, B, b_g]"
                )
        return value


class PSD(BaseModel):
    """Particle size distribution parameters."""

    alpha: float
    wavy_strength: float = 0.0
    class Floor(BaseModel):
        mode: Literal["fixed", "evolve_smin", "none"] = "fixed"

    floor: Floor = Floor()


class SurfaceEnergy(BaseModel):
    """Energy-limited minimum size (Krijt & Kama 2014 inspired)."""

    enabled: bool = False
    gamma_J_m2: float = Field(1.0, gt=0.0, description="Surface energy [J/m^2].")
    eta: float = Field(0.1, gt=0.0, le=1.0, description="Conversion efficiency from KE to surface energy.")


class Surface(BaseModel):
    """Surface layer evolution parameters."""

    init_policy: Literal["clip_by_tau1", "none"] = "clip_by_tau1"
    sigma_surf_init_override: Optional[float] = None
    use_tcoll: bool = True
    freeze_sigma: bool = False
    collision_solver: Literal["surface_ode", "smol"] = Field(
        "smol",
        description=(
            "Collision/outflux update scheme. 'surface_ode' preserves the legacy "
            "Wyatt-style implicit step (suited to e<<0.1), while 'smol' routes collisions "
            "through the Smoluchowski operator. Default is 'smol' to avoid overestimating "
            "t_coll in high-eccentricity (e~0.1–0.5) regimes."
        ),
    )


class InitTau1(BaseModel):
    """Optional toggle to initialise the surface at τ≈1."""

    enabled: bool = Field(
        False,
        description="When true, set σ_surf (and derived mass_total) to the Σ_τ=1 value at start-up.",
    )
    scale_to_tau1: bool = Field(
        False,
        description="If true, clamp the initial surface density to the chosen Σ_τ=1 cap to avoid headroom=0.",
    )
    tau_field: Literal["vertical", "los"] = Field(
        "los",
        description="Which optical-depth field to target when setting Σ_τ=1. Use 'los' to target Mars line-of-sight τ.",
    )
    target_tau: float = Field(
        1.0,
        description="Target optical depth for initialisation (usually 1.0). Applies to the selected tau_field.",
    )


class SublimationParamsModel(BaseModel):
    """Nested parameters for sublimation models.

    Simplified Usage:
        Only specify parameters relevant to your chosen mode.
        Irrelevant parameters can be omitted and will use defaults.

        Example (logistic mode - minimal):
            sub_params:
              mode: "logistic"
              dT: 50.0

        Example (hkl mode - minimal):
            sub_params:
              mode: "hkl"
              alpha_evap: 0.007
              mu: 0.044

    Mode-Specific Parameters:
        - logistic: dT, eta_instant
        - hkl/hkl_timescale: alpha_evap, mu, A, B, valid_K, psat_model, psat_table_*
    """

    mode: Literal["logistic", "hkl", "hkl_timescale"] = Field(
        "logistic",
        description="Sublimation model: 'logistic' (simple), 'hkl' (Hertz-Knudsen-Langmuir), 'hkl_timescale'",
    )
    # --- Common parameters ---
    P_gas: float = Field(0.0, ge=0.0, description="Ambient gas pressure [Pa]")

    # --- Logistic mode parameters ---
    dT: float = Field(50.0, gt=0.0, description="Transition width for logistic mode [K]")
    eta_instant: float = Field(0.1, ge=0.0, le=1.0, description="Instantaneous loss fraction for logistic mode")

    # --- HKL mode parameters ---
    alpha_evap: float = Field(0.007, ge=0.0, le=1.0, description="Evaporation coefficient for HKL modes")
    mu: float = Field(0.0440849, gt=0.0, description="Molecular weight [kg/mol] for HKL modes")
    A: Optional[float] = Field(13.613, description="Clausius-Clapeyron A coefficient (log10 scale)")
    B: Optional[float] = Field(17850.0, description="Clausius-Clapeyron B coefficient [K]")
    valid_K: Optional[Tuple[float, float]] = Field(
        (1270.0, 1600.0),
        description="Valid temperature range for Clausius-Clapeyron fit [K]"
    )
    enable_liquid_branch: bool = Field(
        True,
        description="Enable HKL Clausius liquid branch when temperatures exceed psat_liquid_switch_K",
    )
    psat_liquid_switch_K: Optional[float] = Field(
        1900.0,
        description="Switch temperature [K] for activating the liquid Clausius branch (None keeps solid-only)",
    )
    A_liq: Optional[float] = Field(
        13.203,
        description="Clausius-Clapeyron A coefficient (log10 scale) for the liquid branch",
    )
    B_liq: Optional[float] = Field(
        25898.9,
        description="Clausius-Clapeyron B coefficient [K] for the liquid branch",
    )
    valid_liquid_K: Optional[Tuple[float, float]] = Field(
        (1900.0, 3500.0),
        description="Valid temperature range for the liquid Clausius branch [K]",
    )

    # --- Tabulated psat parameters (advanced) ---
    psat_model: Literal["auto", "clausius", "tabulated"] = Field(
        "auto",
        description="Saturation pressure model: 'auto' (default), 'clausius', or 'tabulated'",
    )
    psat_table_path: Optional[Path] = Field(
        None,
        description="Path to tabulated psat data (only for psat_model='tabulated')",
    )
    psat_table_buffer_K: float = Field(75.0, gt=0.0, description="Buffer for psat table interpolation [K]")
    local_fit_window_K: float = Field(300.0, gt=0.0, description="Local fit window for psat [K]")
    min_points_local_fit: int = Field(3, ge=2, description="Minimum points for local psat fit")
    psat_cache_tol_K: float = Field(
        0.0,
        ge=0.0,
        description=(
            "Tolerance for reusing the last P_sat evaluation; ΔT within this window skips re-selection (0 disables)."
        ),
    )
    mass_conserving: bool = Field(
        False,
        description=(
            "If true, ds/dt-driven shrinkage does not remove mass except when grains cross the blow-out size "
            "within a step; crossing mass is treated as blow-out instead of a sublimation sink."
        ),
    )


class RPBlowoutConfig(BaseModel):
    """Toggle for radiation-pressure blow-out sinks."""

    enable: bool = True


class HydroEscapeConfig(BaseModel):
    """Configuration for vapour-driven hydrodynamic escape sinks.

    ``strength`` is interpreted as the base escape rate (s⁻¹) at
    ``T_ref_K`` for a unit vapour fraction; tune it to match the expected
    one-orbit loss fraction (e.g. Hyodo-style 10–40%) at the chosen radius.
    """

    enable: bool = False
    strength: float = Field(
        0.0,
        ge=0.0,
        description="Base rate coefficient for the hydrodynamic escape sink [s^-1].",
    )
    temp_power: float = Field(1.0, description="Temperature scaling index for the escape rate.")
    T_ref_K: float = Field(2000.0, gt=0.0, description="Reference temperature for the scaling law [K].")
    f_vap_floor: float = Field(
        1.0e-3,
        ge=0.0,
        description="Minimum vapour fraction used when estimating the escape rate.",
    )


class Sinks(BaseModel):
    """Configuration of additional sink processes."""

    mode: Literal["none", "sublimation"] = "sublimation"
    enable_sublimation: bool = True
    sublimation_location: Literal["surface", "smol", "both"] = Field(
        "surface",
        description="Select whether sublimation acts via the surface ODE, the Smol solver, or both.",
    )
    T_sub: float = 1300.0
    sub_params: SublimationParamsModel = SublimationParamsModel()
    enable_gas_drag: bool = Field(
        False,
        description=(
            "Enable gas drag on surface grains. Disabled by default as gas-poor "
            "disks are dominated by radiation and collisions (Takeuchi & Lin 2003; "
            "Strubbe & Chiang 2006)."
        ),
    )
    rho_g: float = 0.0
    rp_blowout: RPBlowoutConfig = RPBlowoutConfig()
    hydro_escape: HydroEscapeConfig = HydroEscapeConfig()


class ProcessStateTagging(BaseModel):
    """Placeholder toggle for future solid/gas tagging."""

    enabled: bool = Field(
        False,
        description="Enable the preliminary state-tagging hook (Phase 0 returns 'solid').",
    )


class Process(BaseModel):
    """Companion switches for phase tagging."""

    state_tagging: ProcessStateTagging = ProcessStateTagging()

    @model_validator(mode="before")
    def _forbid_primary(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "primary" in data:
            raise ConfigurationError("process.primary has been removed; use physics_mode instead.")
        return data


class PhaseThresholds(BaseModel):
    """Fallback thresholds used when no external phase map is available.

    The thresholds approximate a solid↔vapour split with a linear ramp between
    ``T_condense_K`` and ``T_vaporize_K`` and optional damping by ambient
    pressure (``P_ref_bar``) and line-of-sight optical depth (``tau_ref``).
    They provide a gas-poor inner-disk heuristic when a detailed Ronnet/Hyodo-
    style map is not present; tune the numbers when exploring more opaque or
    vapour-rich scenarios.
    """

    T_condense_K: float = Field(1700.0, gt=0.0)
    T_vaporize_K: float = Field(2000.0, gt=0.0)
    P_ref_bar: float = Field(1.0, ge=0.0)
    tau_ref: float = Field(1.0, gt=0.0)

    @field_validator("T_vaporize_K")
    def _check_temperature_hierarchy(cls, value: float, info: ValidationInfo) -> float:
        condense = info.data.get("T_condense_K", 0.0)
        if value <= condense:
            raise ConfigurationError("phase.thresholds.T_vaporize_K must exceed T_condense_K")
        return float(value)


class PhaseConfig(BaseModel):
    """Solid/vapour branching controls.

    Simplified Usage:
        Use `phase.entrypoint` directly to specify the map function.

        Example (threshold mode - recommended):
            phase:
              enabled: true
              source: "threshold"
              thresholds:
                T_condense_K: 1700.0
                T_vaporize_K: 2000.0

        Example (map mode - recommended):
            phase:
              enabled: true
              source: "map"
              entrypoint: "mymodule:my_phase_lookup"
    """

    enabled: bool = Field(False, description="Enable phase state branching")
    source: Literal["map", "threshold"] = Field(
        "threshold",
        description="Phase source: 'threshold' (simple T-based) or 'map' (external lookup)",
    )
    entrypoint: str = Field(
        DEFAULT_PHASE_ENTRYPOINT,
        description="Python entrypoint 'module:function' for phase lookup (used when source='map')",
    )
    extra_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keyword arguments forwarded to the phase map entrypoint.",
    )
    thresholds: PhaseThresholds = Field(
        default_factory=PhaseThresholds,
        description="Temperature thresholds (used when source='threshold')",
    )
    allow_liquid_hkl: bool = Field(
        False,
        description="Allow HKL sublimation when the bulk phase is liquid-dominated",
    )
    temperature_input: Literal["mars_surface", "particle"] = Field(
        "mars_surface",
        description=(
            "Select temperature passed into the phase map: 'mars_surface' keeps the Mars driver, "
            "'particle' uses the grain equilibrium temperature."
        ),
    )
    tau_field: Literal["vertical", "los"] = Field(
        "los",
        description=(
            "Optical-depth field forwarded to phase evaluation. "
            "'vertical' uses κΣ, 'los' multiplies by the line-of-sight factor."
        ),
    )
    q_abs_mean: float = Field(
        0.4,
        description="Mean absorption efficiency ⟨Q_abs⟩ used for the particle-temperature phase input.",
    )

    @field_validator("entrypoint")
    def _check_entrypoint_format(cls, value: str) -> str:
        text = str(value)
        module, sep, func = text.partition(":")
        if not module or sep == "" or not func:
            raise ConfigurationError("phase.entrypoint must be of the form 'module.submodule:function'")
        return text

    @field_validator("q_abs_mean")
    def _check_q_abs_mean(cls, value: float) -> float:
        val = float(value)
        if not math.isfinite(val) or val <= 0.0:
            raise ConfigurationError("phase.q_abs_mean must be positive and finite")
        if val > 1.0:
            logging.getLogger(__name__).warning(
                "phase.q_abs_mean=%.3g exceeds unity; ensure this is intentional for the scenario", val
            )
        return val


class MarsTemperatureDriverConstant(BaseModel):
    """Explicit constant value for the Mars temperature driver."""

    value_K: float = Field(..., description="Constant Mars-facing temperature [K].")

    @field_validator("value_K")
    def _check_value(cls, value: float) -> float:
        Tmin, Tmax = 1000.0, 6500.0
        if not (Tmin <= float(value) <= Tmax):
            raise ConfigurationError(f"mars_temperature_driver.constant.value_K must lie within [{Tmin}, {Tmax}] K")
        return float(value)


class MarsTemperatureDriverTable(BaseModel):
    """Tabulated Mars temperature driver."""

    path: Path = Field(..., description="Path to the time-series table file.")
    time_unit: Literal["s", "day", "yr", "orbit"] = Field(
        "s",
        description="Unit of the time column; 'orbit' scales with the representative orbital period.",
    )
    column_time: str = Field("time", description="Name of the time column.")
    column_temperature: str = Field("T_M", description="Name of the temperature column (Kelvin).")


class MarsTemperatureDriverHyodo(BaseModel):
    """Hyodo linear cooling approximation options."""

    d_layer_m: float = Field(1.0e5, gt=0.0, description="Effective slab thickness [m].")
    rho: float = Field(3000.0, gt=0.0, description="Bulk density [kg/m^3].")
    cp: float = Field(1000.0, gt=0.0, description="Heat capacity [J/kg/K].")


class MarsTemperatureAutogen(BaseModel):
    """Options for auto-generating Mars temperature tables."""

    enabled: bool = Field(False, description="Toggle automatic generation of Mars temperature tables.")
    output_dir: Path = Field(Path("data"), description="Directory to write generated temperature tables.")
    dt_hours: float = Field(1.0, gt=0.0, description="Time step of the generated table [hours].")
    min_years: float = Field(
        2.0, gt=0.0, description="Minimum coverage of the generated table [years]."
    )
    time_margin_years: float = Field(
        0.0,
        ge=0.0,
        description="Extra padding beyond the simulation horizon when generating tables [years].",
    )
    known_T0s: List[float] = Field(
        default_factory=lambda: [2000.0, 4000.0, 6000.0],
        description="Commonly pre-generated initial temperatures [K].",
    )
    time_unit: Literal["s", "day", "yr", "orbit"] = Field(
        "day", description="Unit of the generated time column."
    )
    column_time: str = Field("time_day", description="Name of the generated time column.")
    column_temperature: str = Field("T_K", description="Name of the generated temperature column.")
    model: Literal["slab", "hyodo"] = Field(
        "slab", description="Cooling model used for auto-generated temperature tables."
    )
    filename_template: str = Field(
        "mars_temperature_T{tag}K.csv",
        description="Filename template for generated tables. Uses `{tag}` placeholder for temperature.",
    )


class MarsTemperatureDriverConfig(BaseModel):
    """Configuration container for the Mars temperature driver."""

    enabled: bool = Field(False, description="Toggle the Mars temperature driver.")
    mode: Literal["constant", "table", "hyodo"] = Field(
        "constant",
        description="Driver mode: constant value, external table interpolation, or Hyodo linear cooling.",
    )
    constant: Optional[MarsTemperatureDriverConstant] = Field(
        None,
        description="Constant driver parameters.",
    )
    table: Optional[MarsTemperatureDriverTable] = Field(
        None,
        description="Tabulated driver parameters.",
    )
    hyodo: Optional[MarsTemperatureDriverHyodo] = Field(
        None,
        description="Hyodo cooling driver parameters (used when mode='hyodo').",
    )
    extrapolation: Literal["hold", "error"] = Field(
        "hold",
        description="Out-of-sample behaviour for the table driver.",
    )
    autogenerate: Optional[MarsTemperatureAutogen] = Field(
        None, description="Automatically generate a table from the SiO2 cooling model when needed."
    )

    @model_validator(mode="after")
    def _validate_mode_requirements(cls, model: "MarsTemperatureDriverConfig") -> "MarsTemperatureDriverConfig":
        if model.mode == "constant" and model.enabled and model.constant is None:
            raise ConfigurationError("radiation.mars_temperature_driver.constant must be provided when mode='constant'")
        if model.mode == "table" and model.enabled and model.table is None:
            raise ConfigurationError("radiation.mars_temperature_driver.table must be provided when mode='table'")
        if model.mode == "hyodo" and model.enabled and model.hyodo is None:
            model.hyodo = MarsTemperatureDriverHyodo()
        return model


class RadiationTauGate(BaseModel):
    """Optical-depth gating options for radiation-pressure blow-out."""

    enable: bool = False
    tau_max: float = Field(1.0, gt=0.0, description="τ threshold above which blow-out is suppressed.")


class QPrCache(BaseModel):
    """Cache controls for ⟨Q_pr⟩ lookups."""

    enabled: bool = True
    maxsize: int = Field(
        256,
        ge=0,
        description="Maximum memoised entries for ⟨Q_pr⟩ lookups (0 disables caching).",
    )
    round_tol: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional rounding tolerance applied to s and T before caching to reduce key churn.",
    )


class Radiation(BaseModel):
    """Radiation pressure options and table paths."""

    source: Literal["mars", "off", "none"] = Field(
        "mars",
        description="Origin of the radiation field driving blow-out (restricted to Mars or off).",
    )
    use_mars_rp: bool = Field(
        True,
        description="Enable Mars radiation-pressure forcing. Disabled automatically when source='off'.",
    )
    use_solar_rp: bool = Field(
        False,
        description="Legacy solar radiation toggle retained for logging (always forced off in gas-poor mode).",
    )
    TM_K: Optional[float] = Field(
        None,
        description="Optional override for the Mars-facing temperature [K].",
    )
    freeze_kappa: bool = False
    qpr_table_path: Optional[Path] = Field(
        None,
        description="Path to the Planck-averaged ⟨Q_pr⟩ lookup table. When omitted the analytic fallback is used.",
    )
    Q_pr: Optional[float] = Field(None, description="Grey-body radiation pressure efficiency")
    qpr_cache: QPrCache = QPrCache()
    mars_temperature_driver: Optional[MarsTemperatureDriverConfig] = Field(
        None,
        description="Time-dependent Mars temperature driver configuration.",
    )
    tau_gate: RadiationTauGate = RadiationTauGate()

    @field_validator("Q_pr")
    def _validate_qpr(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ConfigurationError("Q_pr must be positive if specified")
        if not (0.5 <= value <= 1.5):
            raise ConfigurationError("Q_pr must lie within the sensitivity range 0.5–1.5")
        return value

    @field_validator("source")
    def _validate_source(cls, value: str) -> str:
        """Enforce that only Mars-sourced radiation is allowed."""

        value_lower = value.lower()
        if value_lower in {"none", "off"}:
            return "off"
        if value_lower != "mars":
            raise ConfigurationError("radiation.source must be either 'mars' or 'off'")
        return "mars"

    @property
    def qpr_table_resolved(self) -> Optional[Path]:
        """Return the preferred ⟨Q_pr⟩ table path."""

        return self.qpr_table_path


class Shielding(BaseModel):
    """Self-shielding table configuration."""

    class LOSGeometry(BaseModel):
        """Line-of-sight geometry parameters for Mars-directed radiation."""

        mode: Literal["aspect_ratio_factor", "none"] = Field(
            "aspect_ratio_factor",
            description="How to scale τ from vertical to Mars line-of-sight; 'aspect_ratio_factor' multiplies by path_multiplier/h_over_r.",
        )
        h_over_r: float = Field(
            1.0,
            gt=0.0,
            description="Disk aspect ratio H/r used to convert vertical τ to LOS τ.",
        )
        path_multiplier: float = Field(
            1.0,
            gt=0.0,
            description="Geometric multiplier for the Mars-directed path length relative to r.",
        )

    table_path: Optional[Path] = Field(
        None,
        description="Primary path to the Φ(τ) lookup table.",
    )
    mode: Literal["off", "psitau", "fixed_tau1", "table"] = "psitau"
    fixed_tau1_tau: Optional[float] = Field(
        None,
        description="When shielding.mode='fixed_tau1', enforce an optical depth τ independent of radius.",
    )
    fixed_tau1_sigma: Optional[Union[float, Literal["auto", "auto_max"]]] = Field(
        None,
        description=(
            "Direct specification of Σ_{τ=1} when shielding.mode='fixed_tau1'. "
            "Use 'auto' to set Σ_{τ=1}=1/κ_eff at t=0; 'auto_max' takes max(1/κ_eff, Σ_init)×(1+margin)."
        ),
    )
    auto_max_margin: float = Field(
        0.05,
        ge=0.0,
        le=1.0,
        description="Margin applied when shielding.fixed_tau1_sigma='auto_max' or init_tau1.scale_to_tau1 clamps the initial surface density.",
    )
    los_geometry: LOSGeometry = LOSGeometry()

    @property
    def table_path_resolved(self) -> Optional[Path]:
        """Return the preferred Φ(τ) table path."""

        return self.table_path

    @property
    def mode_resolved(self) -> str:
        """Return the shielding mode with legacy aliases normalised."""

        mode_lower = str(self.mode).lower()
        if mode_lower == "table":
            return "psitau"
        return mode_lower


class Blowout(BaseModel):
    """Radiation blow-out control."""

    enabled: bool = True
    target_phase: Literal["solid_only", "any"] = Field(
        "solid_only",
        description="Select which phase states participate in the surface blow-out calculation.",
    )
    layer: Literal["surface_tau_le_1", "full_surface"] = Field(
        "surface_tau_le_1",
        description="Select the surface reservoir feeding blow-out (default: Σ_{τ≤1} skin).",
    )
    gate_mode: Literal["none", "sublimation_competition", "collision_competition"] = Field(
        "none",
        description="Optional surface gate to suppress blow-out when other solid-loss processes are faster.",
    )


class Checkpoint(BaseModel):
    """Checkpointing and restart controls."""

    enabled: bool = Field(
        False,
        description="Enable periodic checkpoints of the 0D state.",
    )
    interval_years: float = Field(
        1.0,
        gt=0.0,
        description="Checkpoint interval in years.",
    )
    path: Optional[Path] = Field(
        None,
        description="Directory to store checkpoints (default: <outdir>/checkpoints).",
    )
    format: Literal["pickle", "json"] = Field(
        "pickle",
        description="Checkpoint serialisation format.",
    )
    keep_last_n: int = Field(
        3,
        ge=0,
        description="Keep at most N recent checkpoints (0 disables pruning).",
    )


class Resume(BaseModel):
    """Resume-from-checkpoint configuration."""

    enabled: bool = Field(
        False,
        description="Resume a run from an existing checkpoint.",
    )
    from_path: Optional[Path] = Field(
        None,
        description="Explicit checkpoint file to resume from; if omitted, the latest in checkpoint.path is used.",
    )


class Numerics(BaseModel):
    """Integrator control parameters."""

    t_end_years: Optional[float] = Field(
        None,
        gt=0.0,
        description="Simulation duration expressed in years; mutually exclusive with t_end_orbits.",
    )
    t_end_orbits: Optional[float] = Field(
        None,
        gt=0.0,
        description="Simulation duration expressed in local orbital periods.",
    )
    t_end_until_temperature_K: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional stop condition: first time Mars temperature falls to this threshold [K].",
    )
    t_end_temperature_margin_years: float = Field(
        0.0,
        ge=0.0,
        description="Padding added after reaching t_end_until_temperature_K [years].",
    )
    stop_on_blowout_below_smin: bool = Field(
        False,
        description="Stop the run early if the blow-out grain size falls below the configured minimum size.",
    )
    t_end_temperature_search_years: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional cap on the search horizon for the temperature stop condition [years].",
    )
    dt_init: Union[float, Literal["auto"]] = Field(
        60000.0,
        description="Initial time-step size in seconds or 'auto' for heuristic selection.",
    )
    safety: float = 0.1
    atol: float = 1e-10
    rtol: float = 1e-6
    eval_per_step: bool = Field(
        True,
        description="Recompute blow-out size, sinks and ds/dt on every step.",
    )
    orbit_rollup: bool = Field(
        True,
        description="Enable per-orbit aggregation of mass loss diagnostics.",
    )
    dt_over_t_blow_max: Optional[float] = Field(
        None,
        gt=0.0,
        description="Optional warning threshold for dt/t_blow; disabled when null.",
    )
    checkpoint: Checkpoint = Checkpoint()
    resume: Resume = Resume()

    @field_validator("dt_init")
    def _check_dt_init(cls, value: Union[float, str]) -> Union[float, str]:
        if isinstance(value, str):
            if value.lower() != "auto":
                raise ConfigurationError("dt_init must be positive or the string 'auto'")
            return "auto"
        if value <= 0.0:
            raise ConfigurationError("dt_init must be positive")
        return float(value)

    @field_validator("t_end_orbits")
    def _check_t_end_orbits(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ConfigurationError("t_end_orbits must be positive when specified")
        return float(value)

    @field_validator("t_end_years")
    def _check_t_end_years(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ConfigurationError("t_end_years must be positive when specified")
        return float(value)

    @field_validator("safety")
    def _check_safety(cls, value: float) -> float:
        if value <= 0.0:
            raise ConfigurationError("numerics.safety must be positive")
        return value

    @field_validator("atol", "rtol")
    def _check_tol(cls, value: float) -> float:
        if value <= 0.0:
            raise ConfigurationError("numerics tolerances must be positive")
        return value

    @field_validator("dt_over_t_blow_max")
    def _check_dt_over_t_blow(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ConfigurationError("dt_over_t_blow_max must be positive when specified")
        return float(value)

    @field_validator("orbit_rollup")
    def _check_orbit_rollup(cls, value: bool) -> bool:
        return bool(value)

    @field_validator("eval_per_step")
    def _check_eval_per_step(cls, value: bool) -> bool:
        return bool(value)



class StepDiagnostics(BaseModel):
    """Per-step loss channel diagnostics output control."""

    enable: bool = Field(
        False,
        description="Write per-step loss diagnostics to disk (CSV or JSONL).",
    )
    format: Literal["csv", "jsonl"] = Field(
        "csv",
        description="Serialisation format for the per-step diagnostics table.",
    )
    path: Optional[Path] = Field(
        None,
        description="Optional path (absolute or relative to outdir) for the diagnostics file.",
    )


class Progress(BaseModel):
    """Console progress display controls."""

    enable: bool = Field(
        False,
        description="Enable a lightweight progress bar with ETA on the CLI.",
    )
    refresh_seconds: float = Field(
        1.0,
        gt=0.0,
        description="Wall-clock interval in seconds between progress updates.",
    )


class Streaming(BaseModel):
    """Streaming write controls for large zero-D runs."""

    enable: bool = Field(
        True,
        description="Enable chunked streaming writes when memory usage exceeds thresholds (default: on).",
    )
    opt_out: bool = Field(
        False,
        description="Force-disable streaming even if enable=true (safety valve).",
    )
    memory_limit_gb: float = Field(
        10.0,
        gt=0.0,
        description="Approximate in-memory buffer limit in gigabytes that triggers a flush.",
    )
    step_flush_interval: int = Field(
        10000,
        ge=0,
        description="Optional step interval trigger for flushing buffers (0 to disable).",
    )
    compression: Literal["snappy", "zstd", "brotli", "gzip", "none"] = Field(
        "snappy",
        description="Compression codec for Parquet chunk outputs.",
    )
    merge_at_end: bool = Field(
        True,
        description="Merge Parquet chunks into single files at the end of the run.",
    )

    @field_validator("memory_limit_gb")
    def _check_memory_limit(cls, value: float) -> float:
        if value <= 0.0:
            raise ConfigurationError("io.streaming.memory_limit_gb must be positive")
        return float(value)

    @field_validator("step_flush_interval")
    def _check_step_interval(cls, value: int) -> int:
        if value < 0:
            raise ConfigurationError("io.streaming.step_flush_interval must be non-negative")
        return int(value)


class IO(BaseModel):
    """Output directories."""

    outdir: Path = Path("out")
    step_diagnostics: StepDiagnostics = StepDiagnostics()
    progress: Progress = Progress()
    streaming: Streaming = Field(default_factory=Streaming)
    quiet: bool = Field(
        False,
        description="Suppress INFO logging and Python warnings for cleaner CLI output.",
    )
    debug_sinks: bool = Field(
        False,
        description="Enable verbose sink logging to out/<run>/debug/sinks_trace.jsonl",
    )
    correct_fast_blowout: bool = Field(
        False,
        description=
        "Apply a correction factor when dt greatly exceeds the blow-out timescale.",
    )
    substep_fast_blowout: bool = Field(
        False,
        description="Subdivide steps when dt/t_blow exceeds substep_max_ratio.",
    )
    substep_max_ratio: float = Field(
        1.0,
        gt=0.0,
        description="Upper limit for dt/t_blow before a step is subdivided (1.0 is effectively disabled; typical 0.3-0.5).",
    )


class ExtendedDiagnostics(BaseModel):
    """Optional extended diagnostics controls."""

    enable: bool = Field(
        False,
        description="Enable extended diagnostics (additional series columns and rollup keys).",
    )
    schema_version: str = Field(
        "extended-minimal-v1",
        description="Schema identifier for the extended diagnostics payload.",
    )


class EnergyBookkeeping(BaseModel):
    """Controls for collision energy bookkeeping outputs."""

    enabled: bool = Field(
        False,
        description="Enable collision energy bookkeeping (E_rel/E_diss/f_ke/F_lf statistics).",
    )
    stream: bool = Field(
        True,
        description="Allow streaming writes for energy_budget outputs (FORCE_STREAMING_OFF overrides).",
    )


class Diagnostics(BaseModel):
    """Diagnostics toggles grouped by feature phase."""

    extended_diagnostics: ExtendedDiagnostics = ExtendedDiagnostics()
    energy_bookkeeping: EnergyBookkeeping = EnergyBookkeeping()


class Config(BaseModel):
    """Top-level configuration object.

    Physics Mode Values:
        - "default": Run both collisions and sublimation/sinks (combined mode)
        - "sublimation_only": Run only sublimation, disable collisions and blow-out
        - "collisions_only": Run only collisions, disable sublimation sinks
    """

    geometry: Geometry
    scope: Scope = Scope()
    physics_mode: Literal["default", "full", "sublimation_only", "collisions_only"] = Field(
        "default",
        description=(
            "Primary physics mode selector. "
            "'default'/'full' runs combined collisions+sinks; "
            "'sublimation_only' disables collisions/blow-out; "
            "'collisions_only' disables sublimation sinks."
        ),
    )
    process: Process = Process()
    chi_blow: Union[float, Literal["auto"]] = Field(
        1.0,
        description="Blow-out timescale multiplier (float) or 'auto' to estimate from β and Q_pr.",
    )
    material: Material
    sizes: Sizes
    initial: Initial
    dynamics: Dynamics
    psd: PSD
    surface_energy: SurfaceEnergy = SurfaceEnergy()
    qstar: QStar
    disk: Optional[Disk] = None
    inner_disk_mass: Optional[InnerDiskMass] = None
    phase: PhaseConfig = PhaseConfig()
    surface: Surface = Surface()
    init_tau1: InitTau1 = InitTau1()
    supply: Supply = Field(default_factory=lambda: Supply())
    sinks: Sinks = Sinks()
    radiation: Optional[Radiation] = None
    shielding: Optional[Shielding] = None
    blowout: Blowout = Blowout()
    numerics: Numerics
    tables: Optional[dict] = None  # backward compatibility placeholder
    diagnostics: Diagnostics = Diagnostics()
    io: IO

    @model_validator(mode="before")
    def _forbid_deprecated_paths(cls, data: Any) -> Any:
        """Reject legacy configuration keys that have been removed."""

        if not isinstance(data, dict):
            return data

        forbidden: Dict[tuple[str, ...], str] = {
            ("geometry", "r"): "disk.geometry.r_in_RM / r_out_RM",
            ("geometry", "runtime_orbital_radius_rm"): "disk.geometry.r_in_RM / r_out_RM",
            ("temps",): "radiation.TM_K or mars_temperature_driver.constant",
            ("single_process_mode",): "physics_mode",
            ("modes", "single_process"): "physics_mode",
            ("process", "primary"): "physics_mode",
            ("phase", "map", "entrypoint"): "phase.entrypoint",
            ("phase", "map"): "phase.entrypoint",
            ("radiation", "qpr_table"): "radiation.qpr_table_path",
            ("shielding", "phi_table"): "shielding.table_path",
        }

        def _walk(node: Any, path: tuple[str, ...]) -> None:
            if not isinstance(node, dict):
                return
            for key, val in node.items():
                new_path = path + (str(key),)
                if new_path in forbidden:
                    raise ConfigurationError(
                        f"Configuration key '{'.'.join(new_path)}' is no longer supported; "
                        f"use {forbidden[new_path]} instead."
                    )
                _walk(val, new_path)

        _walk(data, tuple())
        return data

    @field_validator("physics_mode")
    def _normalise_physics_mode(cls, value: str) -> str:
        text = str(value).strip().lower() if value is not None else "default"
        if text in {"", "default", "off", "none", "full", "both"}:
            return "default"
        if text in {"sublimation_only", "sublimation"}:
            return "sublimation_only"
        if text in {"collisions_only", "collisional_only", "collision_only"}:
            return "collisions_only"
        raise ConfigurationError("physics_mode must be default, sublimation_only or collisions_only")

    @field_validator("chi_blow")
    def _validate_chi_blow(cls, value: Union[float, str]) -> Union[float, str]:  # type: ignore[override]
        if isinstance(value, str):
            if value.lower() != "auto":
                raise ConfigurationError("chi_blow string value must be 'auto'")
            return "auto"
        if value <= 0.0:
            raise ConfigurationError("chi_blow must be positive")
        return float(value)

    def get_effective_TM_K(self) -> float:
        """Return the effective Mars temperature from the radiation block."""

        if self.radiation is not None and getattr(self.radiation, "TM_K", None) is not None:
            return float(self.radiation.TM_K)  # type: ignore[return-value]
        driver = getattr(self.radiation, "mars_temperature_driver", None) if self.radiation else None
        if driver is not None and getattr(driver, "constant", None) is not None and getattr(driver, "enabled", False):
            return float(driver.constant.value_K)
        raise ConfigurationError("radiation.TM_K is required when no temperature driver constant is provided")


__all__ = [
    "Geometry",
    "DiskGeometry",
    "Disk",
    "Scope",
    "Material",
    "Temps",
    "Sizes",
    "Initial",
    "Dynamics",
    "QStar",
    "PSD",
    "Surface",
    "InitTau1",
    "InnerDiskMass",
    "Supply",
    "PhaseConfig",
    "PhaseThresholds",
    "Sinks",
    "Diagnostics",
    "ExtendedDiagnostics",
    "EnergyBookkeeping",
    "ProcessStateTagging",
    "Process",
    "MarsTemperatureDriverConfig",
    "RadiationTauGate",
    "Radiation",
    "Shielding",
    "Blowout",
    "Numerics",
    "IO",
    "RPBlowoutConfig",
    "HydroEscapeConfig",
    "Config",
]
