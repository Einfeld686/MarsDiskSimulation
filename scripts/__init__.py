"""Compatibility shims for legacy imports."""

from .sweeps import sweep_heatmaps  # Backward-compatible re-export.

__all__ = ["sweep_heatmaps"]
