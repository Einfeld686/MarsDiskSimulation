"""Custom exceptions for the :mod:`marsdisk` package."""
from __future__ import annotations


class MarsDiskError(Exception):
    """Base exception for Mars disk simulation errors."""


__all__ = ["MarsDiskError"]
