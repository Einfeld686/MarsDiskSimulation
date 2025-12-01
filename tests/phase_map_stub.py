"""Stub map callable used by phase branching unit tests."""
from __future__ import annotations

from typing import Optional


def lookup_phase_state(temperature_K: float, pressure_Pa: Optional[float] = None, tau: Optional[float] = None) -> dict[str, float | str | None]:  # noqa: D401
    """Return a deterministic solid/vapor state for testing.

    Temperatures above 1800 K are treated as vapour-dominated; everything else
    remains solid regardless of pressure or optical depth.  The payload mimics
    the structure returned by ``siO2_cooling_map.lookup_phase_state`` so that
    the production code can exercise the same parsing path inside the tests.
    """

    state = "vapor" if temperature_K >= 1800.0 else "solid"
    f_vap = 1.0 if state == "vapor" else 0.0
    return {
        "state": state,
        "f_vap": f_vap,
        "temperature_K": float(temperature_K),
        "pressure_bar": float(pressure_Pa or 0.0) / 1.0e5,
        "tau": tau,
    }


def lookup_unphysical_fraction(temperature_K: float, *_args, **_kwargs) -> dict[str, float | str]:
    """Return an over-unity vapour fraction to exercise clamping logic."""

    state = "vapor" if temperature_K >= 1500.0 else "solid"
    return {"state": state, "f_vap": 2.5}


def lookup_phase_liquid(*_args, **_kwargs) -> dict[str, float | str]:
    """Return a liquid-dominated bulk state for testing."""

    return {"state": "liquid_dominated", "f_liquid": 1.0, "f_solid": 0.0}


def lookup_phase_solid(*_args, **_kwargs) -> dict[str, float | str]:
    """Return a solid-dominated bulk state for testing."""

    return {"state": "solid_dominated", "f_liquid": 0.0, "f_solid": 1.0}
