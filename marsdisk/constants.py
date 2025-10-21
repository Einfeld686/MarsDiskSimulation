"""Physical constants and default parameter ranges for the Mars disk models.

This module collects a minimal set of constants used throughout the code
base.  Numerical values are taken from CODATA 2018 where applicable.  The
values are provided in SI units.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

# Gravitational constant (m^3 kg^-1 s^-2)
G: float = 6.67430e-11

# Speed of light in vacuum (m s^-1)
C: float = 2.99792458e8

# Stefan-Boltzmann constant (W m^-2 K^-4)
SIGMA_SB: float = 5.670374419e-8

# Universal gas constant (J mol^-1 K^-1)
R_GAS: float = 8.314462618

# Mars physical parameters
M_MARS: float = 6.4171e23  # kg
R_MARS: float = 3.3895e6   # m

# Default material density range for solids (kg m^-3)
RHO_RANGE: Tuple[float, float] = (1000.0, 5000.0)

# Default melt temperature range of Mars materials (K)
T_M_RANGE: Tuple[float, float] = (1500.0, 2500.0)


@dataclass(frozen=True)
class MarsConstants:
    """Convenience container bundling frequently used constants.

    The dataclass is primarily syntactic sugar to ease passing groups of
    constants around the code.  Values are immutable to avoid accidental
    modification during simulations.
    """

    G: float = G
    C: float = C
    SIGMA_SB: float = SIGMA_SB
    R_GAS: float = R_GAS
    M_MARS: float = M_MARS
    R_MARS: float = R_MARS
    RHO_RANGE: Tuple[float, float] = RHO_RANGE
    T_M_RANGE: Tuple[float, float] = T_M_RANGE
