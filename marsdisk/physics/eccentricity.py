"""Radial eccentricity profile evaluation utilities."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Tuple

import numpy as np

from .. import constants
from ..errors import ConfigurationError
from ..io import tables

logger = logging.getLogger(__name__)

_DEPRECATED_E_PROFILE_MODES = {"off", "table"}


def _warn_deprecated(mode: str, log: logging.Logger | None) -> None:
    if log is None:
        return
    if mode in _DEPRECATED_E_PROFILE_MODES:
        log.warning(
            "dynamics.e_profile.mode='%s' is deprecated; default is 'mars_pericenter'.",
            mode,
        )


def evaluate_e_profile(
    profile_cfg: Any,
    *,
    r_m: float | np.ndarray,
    r_RM: float | np.ndarray,
    log: logging.Logger | None = None,
) -> Tuple[float | np.ndarray | None, dict]:
    """Evaluate the eccentricity profile at radius ``r``.

    Returns the evaluated eccentricity (or None when profile is off) and a
    metadata dictionary for run_config provenance.
    """

    if profile_cfg is None:
        return None, {"applied": False}

    mode = str(getattr(profile_cfg, "mode", "off")).lower()
    meta = {
        "applied": mode != "off",
        "mode": mode,
        "r_kind": None,
        "table_path": None,
        "formula": None,
    }

    if mode == "off":
        _warn_deprecated(mode, log)
        return None, meta

    _warn_deprecated(mode, log)

    r_m_arr = np.asarray(r_m, dtype=float)
    r_rm_arr = np.asarray(r_RM, dtype=float)
    if not np.all(np.isfinite(r_m_arr)) or not np.all(np.isfinite(r_rm_arr)):
        raise ConfigurationError("e_profile evaluation requires finite r values")
    if np.any(r_m_arr <= 0.0):
        raise ConfigurationError("e_profile evaluation requires r>0")

    if mode == "mars_pericenter":
        if np.any(r_m_arr <= constants.R_MARS):
            if log is not None:
                count = int(np.sum(r_m_arr <= constants.R_MARS))
                log.warning(
                    "e_profile mars_pericenter: %d radius values <= R_MARS; clamping e to 0.",
                    count,
                )
        e_raw = 1.0 - constants.R_MARS / r_m_arr
        e_raw = np.where(r_m_arr <= constants.R_MARS, 0.0, e_raw)
        meta["formula"] = "e = 1 - R_MARS / r"
    elif mode == "table":
        r_kind = str(getattr(profile_cfg, "r_kind", "r_RM"))
        meta["r_kind"] = r_kind
        table_path = getattr(profile_cfg, "table_path", None)
        if table_path is None:
            raise ConfigurationError("e_profile.mode='table' requires table_path")
        table_path = Path(table_path)
        meta["table_path"] = str(table_path)
        table = tables.load_e_profile_table(table_path, r_column=r_kind)
        r_query = r_rm_arr if r_kind == "r_RM" else r_m_arr
        e_raw = table.interp_array(r_query)
    else:
        raise ConfigurationError(f"Unknown dynamics.e_profile.mode={mode!r}")

    clip_min = float(getattr(profile_cfg, "clip_min", 0.0))
    clip_max = float(getattr(profile_cfg, "clip_max", 0.999999))
    e_clipped = np.clip(e_raw, clip_min, clip_max)

    if np.isscalar(r_m) and np.isscalar(r_RM):
        return float(np.asarray(e_clipped).item()), meta
    return np.asarray(e_clipped, dtype=float), meta


__all__ = ["evaluate_e_profile"]
