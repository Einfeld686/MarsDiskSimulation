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


class Geometry(BaseModel):
    """Geometric configuration of the simulation domain."""

    mode: Literal["0D", "1D"] = "0D"
    r: Optional[float] = Field(None, description="Orbital radius for 0D runs [m]")
    r_in: Optional[float] = Field(None, description="Inner radius for 1D runs [m]")
    r_out: Optional[float] = Field(None, description="Outer radius for 1D runs [m]")
    Nr: Optional[int] = Field(None, description="Number of radial zones for 1D runs")


class Material(BaseModel):
    """Material properties of the solids."""

    rho: float = Field(..., gt=0.0, description="Bulk density [kg/m^3]")


class Temps(BaseModel):
    """Thermal parameters."""

    T_M: float = Field(..., description="Surface temperature of Mars [K]")


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

    eps_mix: float
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
    enable_gas_drag: bool = False
    rho_g: float = 0.0


class Radiation(BaseModel):
    """Radiation pressure options and table paths."""

    use_tables: bool = True
    qpr_table: Optional[Path] = None


class Shielding(BaseModel):
    """Self-shielding table configuration."""

    phi_table: Optional[Path] = None


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
    surface: Surface
    sinks: Sinks
    radiation: Optional[Radiation] = None
    shielding: Optional[Shielding] = None
    numerics: Numerics
    tables: Optional[dict] = None  # backward compatibility placeholder
    io: IO


__all__ = [
    "Geometry",
    "Material",
    "Temps",
    "Sizes",
    "Initial",
    "Dynamics",
    "QStar",
    "PSD",
    "Surface",
    "Sinks",
    "Radiation",
    "Shielding",
    "Numerics",
    "IO",
    "Config",
]
