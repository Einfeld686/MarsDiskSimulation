"""Configuration schema for Mars disk simulations.

This module defines Pydantic models that mirror the structure of the YAML
configuration files used by :mod:`marsdisk.run`.  Only a subset of the
parameters from the full research code is required for the unit tests.  The
models nevertheless follow the layout described in AGENTS.md so that the
configuration files remain forward compatible.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator

from . import constants


class Geometry(BaseModel):
    """Geometric configuration of the simulation domain."""

    mode: Literal["0D", "1D"] = "0D"
    r: Optional[float] = Field(None, description="Orbital radius for 0D runs [m]")
    r_in: Optional[float] = Field(None, description="Inner radius for 1D runs [m]")
    r_out: Optional[float] = Field(None, description="Outer radius for 1D runs [m]")
    Nr: Optional[int] = Field(None, description="Number of radial zones for 1D runs")


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
        Tmin, Tmax = 1000.0, 6000.0
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


class Surface(BaseModel):
    """Surface layer evolution parameters."""

    init_policy: Literal["clip_by_tau1", "none"] = "clip_by_tau1"
    sigma_surf_init_override: Optional[float] = None
    use_tcoll: bool = True


class SublimationParamsModel(BaseModel):
    """Nested parameters for sublimation models."""

    mode: Literal["logistic", "hkl", "hkl_timescale"] = "logistic"
    alpha_evap: float = 1.0
    mu: float = 0.1
    A: Optional[float] = None
    B: Optional[float] = None
    dT: float = 50.0
    eta_instant: float = 0.1
    P_gas: float = 0.0


class Sinks(BaseModel):
    """Configuration of additional sink processes."""

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

    TM_K: Optional[float] = None
    qpr_table: Optional[Path] = None
    Q_pr: Optional[float] = Field(None, description="Grey-body radiation pressure efficiency")

    @validator("Q_pr")
    def _validate_qpr(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value <= 0.0:
            raise ValueError("Q_pr must be positive if specified")
        if not (0.5 <= value <= 1.5):
            raise ValueError("Q_pr must lie within the sensitivity range 0.5–1.5")
        return value


class Shielding(BaseModel):
    """Self-shielding table configuration."""

    phi_table: Optional[str] = None


class Numerics(BaseModel):
    """Integrator control parameters."""

    t_end_years: float
    dt_init: float
    safety: float = 0.1
    atol: float = 1e-10
    rtol: float = 1e-6


class IO(BaseModel):
    """Output directories."""

    outdir: Path = Path("out")


class Config(BaseModel):
    """Top-level configuration object."""

    geometry: Geometry
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
    numerics: Numerics
    tables: Optional[dict] = None  # backward compatibility placeholder
    io: IO


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
    "Numerics",
    "IO",
    "Config",
]
