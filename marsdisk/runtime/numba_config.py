"""Shared configuration helpers for Numba enable/disable switches."""
from __future__ import annotations

import os
from typing import Mapping, Optional

_TRUTHY = {"1", "true", "yes", "on", "enable", "enabled"}
_FALSY = {"0", "false", "no", "off", "disable", "disabled"}

_DISABLE_ENV_VARS = (
    "MARSDISK_NUMBA_DISABLE",
    "MARSDISK_DISABLE_NUMBA",
)


def _env_flag(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    text = value.strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def numba_disabled_env(env: Optional[Mapping[str, str]] = None) -> bool:
    """Return True when Numba is explicitly disabled via environment variables."""

    env_map = os.environ if env is None else env
    for key in _DISABLE_ENV_VARS:
        flag = _env_flag(env_map.get(key))
        if flag is not None:
            return flag
    return False


def numba_status(
    available: bool,
    disabled_env: bool,
    use_numba: bool,
    numba_failed: bool,
) -> dict[str, object]:
    """Standardise the Numba status payload used in run metadata."""

    return {
        "available": bool(available),
        "disabled_env": bool(disabled_env),
        "use_numba": bool(use_numba),
        "numba_failed": bool(numba_failed),
    }


__all__ = [
    "numba_disabled_env",
    "numba_status",
]
