"""Configuration schema for Mars disk simulations.

This module defines Pydantic models that mirror the structure of the YAML
configuration files used by :mod:`marsdisk.run`.  Only a subset of the
parameters from the full research code is required for the unit tests.  The
models nevertheless follow the layout described in AGENTS.md so that the
configuration files remain forward compatible.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union
import warnings

from pydantic import BaseModel, Field, validator, root_validator

from . import constants


class Geometry(BaseModel):
    """Geometric configuration of the simulation domain."""

    mode: Literal["0D", "1D"] = "0D"
    r: Optional[float] = Field(None, description="Orbital radius for 0D runs [m]")
    r_in: Optional[float] = Field(None, description="Inner radius for 1D runs [m]")
    r_out: Optional[float] = Field(None, description="Outer radius for 1D runs [m]")
    Nr: Optional[int] = Field(None, description="Number of radial zones for 1D runs")
    runtime_orbital_radius_rm: Optional[float] = Field(
        None,
        description="Optional orbital radius expressed in Mars radii; takes effect when geometry.r is omitted.",
    )


class DiskGeometry(BaseModel):
    """Geometry of the inner disk in units of Mars radii."""

    r_in_RM: float
    r_out_RM: float
    r_profile: Literal["uniform", "powerlaw"] = "uniform"
    p_index: float = 0.0


class Disk(BaseModel):
    """Container for inner disk properties."""

    geometry: DiskGeometry


class InnerDiskMass(BaseModel):
    """Scaling for the total mass of the inner disk."""

    use_Mmars_ratio: bool = True
    M_in_ratio: float = 3.0e-5
    map_to_sigma: Literal["analytic"] = "analytic"
    M_over_Mmars: Optional[float] = Field(
        None,
        description="Legacy alias for M_in_ratio retained for agent tasks.",
    )

    @root_validator(pre=True)
    def _alias_m_over_mmars(cls, values: Dict[str, object]) -> Dict[str, object]:
        """Normalise M_over_Mmars to M_in_ratio."""

        if "M_over_Mmars" in values and "M_in_ratio" not in values:
            values["M_in_ratio"] = values["M_over_Mmars"]
        return values


class SupplyConst(BaseModel):
    prod_area_rate_kg_m2_s: float = 0.0


class SupplyPowerLaw(BaseModel):
    A_kg_m2_s: Optional[float] = None
    t0_s: float = 0.0
    index: float = -1.0


class SupplyTable(BaseModel):
    path: Path = Path("data/supply_rate.csv")
    interp: Literal["linear"] = "linear"


class SupplyMixing(BaseModel):
    epsilon_mix: float = 1.0


class SupplyPiece(BaseModel):
    t_start_s: float
    t_end_s: float
    mode: Literal["const", "powerlaw", "table"] = "const"
    const: SupplyConst = SupplyConst()
    powerlaw: SupplyPowerLaw = SupplyPowerLaw()
    table: SupplyTable = SupplyTable()


class Supply(BaseModel):
    """Parameterisation of external surface supply."""

    mode: Literal["const", "table", "powerlaw", "piecewise"] = "const"
    const: SupplyConst = SupplyConst()
    powerlaw: SupplyPowerLaw = SupplyPowerLaw()
    table: SupplyTable = SupplyTable()
    mixing: SupplyMixing = SupplyMixing()
    piecewise: list[SupplyPiece] = []


class Material(BaseModel):
    """Material properties of the solids."""

    rho: float = Field(3000.0, gt=0.0, description="Bulk density [kg/m^3]")

    @validator("rho")
    def _check_rho_range(cls, value: float) -> float:
        low, high = constants.RHO_RANGE
        if not (low <= value <= high):
            raise ValueError(
                f"Material density rho must lie within [{low}, {high}] kg/m^3"
            )
        return value


class Temps(BaseModel):
    """Thermal parameters."""

    T_M: float = Field(2000.0, description="Surface temperature of Mars [K]")

    @validator("T_M")
    def _check_temperature_range(cls, value: float) -> float:
        Tmin, Tmax = 1000.0, 6500.0
        if not (Tmin <= value <= Tmax):
            raise ValueError(f"Mars temperature T_M must lie within [{Tmin}, {Tmax}] K")
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
    s0_mode: Literal["mono", "upper"] = Field("upper", description="Initial PSD mode")


class Dynamics(BaseModel):
    """Parameters governing dynamical excitation."""

    e0: float
    i0: float
    t_damp_orbits: float
    f_wake: float = 1.0
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


class QStar(BaseModel):
    """Strength law parameters for catastrophic disruption."""

    Qs: float
    a_s: float
    B: float
    b_g: float
    v_ref_kms: List[float]


class PSD(BaseModel):
    """Particle size distribution parameters."""

    alpha: float
    wavy_strength: float = 0.0
    class Floor(BaseModel):
        mode: Literal["fixed", "evolve_smin", "none"] = "fixed"

    floor: Floor = Floor()


class Surface(BaseModel):
    """Surface layer evolution parameters."""

    init_policy: Literal["clip_by_tau1", "none"] = "clip_by_tau1"
    sigma_surf_init_override: Optional[float] = None
    use_tcoll: bool = True
    freeze_sigma: bool = False


class SublimationParamsModel(BaseModel):
    """Nested parameters for sublimation models."""

    mode: Literal["logistic", "hkl", "hkl_timescale"] = "logistic"
    psat_model: Literal["auto", "clausius", "tabulated"] = "auto"
    alpha_evap: float = 0.007
    mu: float = 0.0440849
    A: Optional[float] = 13.613
    B: Optional[float] = 17850.0
    valid_K: Optional[Tuple[float, float]] = (1270.0, 1600.0)
    psat_table_path: Optional[Path] = None
    psat_table_buffer_K: float = 75.0
    local_fit_window_K: float = 300.0
    min_points_local_fit: int = 3
    dT: float = 50.0
    eta_instant: float = 0.1
    P_gas: float = 0.0


class Sinks(BaseModel):
    """Configuration of additional sink processes."""

    mode: Literal["none", "sublimation"] = "sublimation"
    enable_sublimation: bool = True
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


class Radiation(BaseModel):
    """Radiation pressure options and table paths."""

    TM_K: Optional[float] = Field(
        None,
        description="Optional override for the Mars-facing temperature [K]; temps.T_M is used when omitted.",
    )
    freeze_kappa: bool = False
    qpr_table_path: Optional[Path] = Field(
        None,
        description="Path to the Planck-averaged ⟨Q_pr⟩ lookup table. When omitted the analytic fallback is used.",
    )
    qpr_table: Optional[Path] = Field(
        None,
        description="Legacy alias for qpr_table_path; kept for backward compatibility.",
    )
    Q_pr: Optional[float] = Field(None, description="Grey-body radiation pressure efficiency")

    @validator("qpr_table", always=True)
    def _check_qpr_table_alias(
        cls,
        value: Optional[Path],
        values: Dict[str, Optional[Path]],
    ) -> Optional[Path]:
        """Ensure that qpr_table/qpr_table_path do not conflict."""

        new_style = values.get("qpr_table_path")
        if value is not None and new_style is not None and Path(value) != Path(new_style):
            raise ValueError("Specify either radiation.qpr_table_path or radiation.qpr_table (legacy), not both.")
        if value is not None and new_style is None:
            warnings.warn(
                "radiation.qpr_table is deprecated; please migrate to radiation.qpr_table_path.",
                DeprecationWarning,
                stacklevel=2,
            )
        return value

    @validator("Q_pr")
    def _validate_qpr(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ValueError("Q_pr must be positive if specified")
        if not (0.5 <= value <= 1.5):
            raise ValueError("Q_pr must lie within the sensitivity range 0.5–1.5")
        return value

    @property
    def qpr_table_resolved(self) -> Optional[Path]:
        """Return the preferred ⟨Q_pr⟩ table path, respecting legacy keys."""

        return self.qpr_table_path or self.qpr_table


class Shielding(BaseModel):
    """Self-shielding table configuration."""

    table_path: Optional[Path] = Field(
        None,
        description="Primary path to the Φ(τ) lookup table.",
    )
    phi_table: Optional[Path] = Field(
        None,
        description="Legacy alias for table_path retained for backward compatibility.",
    )
    mode: Literal["off", "psitau", "fixed_tau1", "table"] = "psitau"
    fixed_tau1_tau: Optional[float] = Field(
        None,
        description="When shielding.mode='fixed_tau1', enforce an optical depth τ independent of radius.",
    )
    fixed_tau1_sigma: Optional[float] = Field(
        None,
        description="Optional direct specification of Σ_{τ=1} when shielding.mode='fixed_tau1'.",
    )

    @validator("phi_table", always=True)
    def _check_phi_table_alias(
        cls,
        value: Optional[Path],
        values: Dict[str, Optional[Path]],
    ) -> Optional[Path]:
        """Ensure that table_path/phi_table do not conflict."""

        primary = values.get("table_path")
        if value is not None and primary is not None and Path(value) != Path(primary):
            raise ValueError("Specify either shielding.table_path or shielding.phi_table (legacy), not both.")
        if value is not None and primary is None:
            warnings.warn(
                "shielding.phi_table is deprecated; please migrate to shielding.table_path.",
                DeprecationWarning,
                stacklevel=2,
            )
        return value

    @property
    def table_path_resolved(self) -> Optional[Path]:
        """Return the preferred Φ(τ) table path."""

        return self.table_path or self.phi_table

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

    @validator("dt_init")
    def _check_dt_init(cls, value: Union[float, str]) -> Union[float, str]:
        if isinstance(value, str):
            if value.lower() != "auto":
                raise ValueError("dt_init must be positive or the string 'auto'")
            return "auto"
        if value <= 0.0:
            raise ValueError("dt_init must be positive")
        return float(value)

    @validator("t_end_orbits")
    def _check_t_end_orbits(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ValueError("t_end_orbits must be positive when specified")
        return float(value)

    @validator("t_end_years")
    def _check_t_end_years(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ValueError("t_end_years must be positive when specified")
        return float(value)

    @validator("safety")
    def _check_safety(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("numerics.safety must be positive")
        return value

    @validator("atol", "rtol")
    def _check_tol(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("numerics tolerances must be positive")
        return value

    @validator("dt_over_t_blow_max")
    def _check_dt_over_t_blow(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ValueError("dt_over_t_blow_max must be positive when specified")
        return float(value)

    @validator("orbit_rollup")
    def _check_orbit_rollup(cls, value: bool) -> bool:
        return bool(value)

    @validator("eval_per_step")
    def _check_eval_per_step(cls, value: bool) -> bool:
        return bool(value)



class IO(BaseModel):
    """Output directories."""

    outdir: Path = Path("out")
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
        description="Upper limit for dt/t_blow before a step is subdivided.",
    )


class Config(BaseModel):
    """Top-level configuration object."""

    geometry: Geometry
    chi_blow: Union[float, Literal["auto"]] = Field(
        1.0,
        description="Blow-out timescale multiplier (float) or 'auto' to estimate from β and Q_pr.",
    )
    material: Material
    temps: Temps
    sizes: Sizes
    initial: Initial
    dynamics: Dynamics
    psd: PSD
    qstar: QStar
    disk: Optional[Disk] = None
    inner_disk_mass: Optional[InnerDiskMass] = None
    surface: Surface = Surface()
    supply: Supply = Field(default_factory=lambda: Supply())
    sinks: Sinks = Sinks()
    radiation: Optional[Radiation] = None
    shielding: Optional[Shielding] = None
    blowout: Blowout = Blowout()
    numerics: Numerics
    tables: Optional[dict] = None  # backward compatibility placeholder
    io: IO

    @validator("chi_blow")
    def _validate_chi_blow(cls, value: Union[float, str]) -> Union[float, str]:  # type: ignore[override]
        if isinstance(value, str):
            if value.lower() != "auto":
                raise ValueError("chi_blow string value must be 'auto'")
            return "auto"
        if value <= 0.0:
            raise ValueError("chi_blow must be positive")
        return float(value)


__all__ = [
    "Geometry",
    "DiskGeometry",
    "Disk",
    "Material",
    "Temps",
    "Sizes",
    "Initial",
    "Dynamics",
    "QStar",
    "PSD",
    "Surface",
    "InnerDiskMass",
    "Supply",
    "Sinks",
    "Radiation",
    "Shielding",
    "Blowout",
    "Numerics",
    "IO",
    "Config",
]
