"""Pytest fixtures and hooks for the marsdisk test suite."""

from marsdisk.physics import radiation

# Ensure tests exercise the documented default ⟨Q_pr⟩=1 when no table is requested.
radiation._QPR_LOOKUP = None
