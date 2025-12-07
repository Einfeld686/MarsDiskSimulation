"""Helper utilities for normalising configuration inputs."""
from __future__ import annotations

from typing import Tuple
import math

from . import constants
from .schema import Config, Disk, DiskGeometry


def resolve_reference_radius(cfg: Config) -> Tuple[float, float, str]:
    """Return (r_m, r_RM, source_label) for the representative orbital radius."""

    disk = getattr(cfg, "disk", None)
    if disk is not None and getattr(disk, "geometry", None) is not None:
        r_in_rm = float(disk.geometry.r_in_RM)
        r_out_rm = float(disk.geometry.r_out_RM)
        if r_in_rm <= 0.0 or r_out_rm <= 0.0 or not (math.isfinite(r_in_rm) and math.isfinite(r_out_rm)):
            raise ValueError("disk.geometry radii must be finite and positive")
        r_rm = 0.5 * (r_in_rm + r_out_rm)
        r_m = r_rm * constants.R_MARS
        return r_m, r_rm, "disk.geometry"

    geom = getattr(cfg, "geometry", None)
    if geom is not None and getattr(geom, "r_in", None) is not None and getattr(geom, "r_out", None) is not None:
        r_in_m = float(geom.r_in)
        r_out_m = float(geom.r_out)
        if r_in_m <= 0.0 or r_out_m <= 0.0 or not (math.isfinite(r_in_m) and math.isfinite(r_out_m)):
            raise ValueError("geometry.r_in/r_out must be finite and positive")
        r_m = 0.5 * (r_in_m + r_out_m)
        r_rm = r_m / constants.R_MARS
        return r_m, r_rm, "geometry.r_in_out"

    raise ValueError("disk.geometry.r_in_RM / r_out_RM must be provided for 0D runs")


def ensure_disk_geometry(cfg: Config, r_rm: float) -> None:
    """Populate ``cfg.disk.geometry`` with a single-radius annulus centred on ``r_rm``."""

    r_rm_val = float(r_rm)
    if not math.isfinite(r_rm_val) or r_rm_val <= 0.0:
        raise ValueError("Reference radius must be finite and positive (in Mars radii)")
    geom = getattr(cfg, "disk", None)
    if geom is None or getattr(geom, "geometry", None) is None:
        cfg.disk = Disk(geometry=DiskGeometry(r_in_RM=r_rm_val, r_out_RM=r_rm_val))
        return
    cfg.disk.geometry.r_in_RM = r_rm_val
    cfg.disk.geometry.r_out_RM = r_rm_val


def resolve_temperature_field(cfg: Config) -> Tuple[float, str]:
    """Return (T_M, source_label) from the radiation block."""

    rad = getattr(cfg, "radiation", None)
    if rad is not None and getattr(rad, "TM_K", None) is not None:
        return float(rad.TM_K), "radiation.TM_K"
    driver = getattr(rad, "mars_temperature_driver", None) if rad is not None else None
    if driver is not None and getattr(driver, "constant", None) is not None and getattr(driver, "enabled", False):
        return float(driver.constant.value_K), "mars_temperature_driver.constant"
    raise ValueError("Mars temperature is not specified: set radiation.TM_K or enable mars_temperature_driver.constant")
