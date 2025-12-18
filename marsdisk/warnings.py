"""Structured warning classes for the :mod:`marsdisk` package."""
from __future__ import annotations

import warnings


class MarsDiskWarning(UserWarning):
    """Base warning class for marsdisk."""


class PhysicsWarning(MarsDiskWarning):
    """Physical parameter or regime warnings."""


class NumericalWarning(MarsDiskWarning):
    """Numerical stability or accuracy warnings."""


class TableWarning(MarsDiskWarning):
    """Table loading or fallback warnings."""


__all__ = [
    "MarsDiskWarning",
    "PhysicsWarning",
    "NumericalWarning",
    "TableWarning",
]
