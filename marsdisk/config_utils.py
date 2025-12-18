"""Helper utilities for normalising configuration inputs."""
from __future__ import annotations

import logging
import math
import subprocess
import warnings
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

from . import constants
from .errors import ConfigurationError
from .schema import Config, Disk, DiskGeometry

logger = logging.getLogger(__name__)


def resolve_reference_radius(cfg: Config) -> Tuple[float, float, str]:
    """Return (r_m, r_RM, source_label) for the representative orbital radius."""

    disk = getattr(cfg, "disk", None)
    if disk is not None and getattr(disk, "geometry", None) is not None:
        r_in_rm = float(disk.geometry.r_in_RM)
        r_out_rm = float(disk.geometry.r_out_RM)
        if r_in_rm <= 0.0 or r_out_rm <= 0.0 or not (math.isfinite(r_in_rm) and math.isfinite(r_out_rm)):
            raise ConfigurationError("disk.geometry radii must be finite and positive")
        r_rm = 0.5 * (r_in_rm + r_out_rm)
        r_m = r_rm * constants.R_MARS
        return r_m, r_rm, "disk.geometry"

    geom = getattr(cfg, "geometry", None)
    if geom is not None and getattr(geom, "r_in", None) is not None and getattr(geom, "r_out", None) is not None:
        r_in_m = float(geom.r_in)
        r_out_m = float(geom.r_out)
        if r_in_m <= 0.0 or r_out_m <= 0.0 or not (math.isfinite(r_in_m) and math.isfinite(r_out_m)):
            raise ConfigurationError("geometry.r_in/r_out must be finite and positive")
        r_m = 0.5 * (r_in_m + r_out_m)
        r_rm = r_m / constants.R_MARS
        return r_m, r_rm, "geometry.r_in_out"

    raise ConfigurationError("disk.geometry.r_in_RM / r_out_RM must be provided for 0D runs")


def ensure_disk_geometry(cfg: Config, r_rm: float) -> None:
    """Populate ``cfg.disk.geometry`` with a single-radius annulus centred on ``r_rm``."""

    r_rm_val = float(r_rm)
    if not math.isfinite(r_rm_val) or r_rm_val <= 0.0:
        raise ConfigurationError("Reference radius must be finite and positive (in Mars radii)")
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
    raise ConfigurationError("Mars temperature is not specified: set radiation.TM_K or enable mars_temperature_driver.constant")


def parse_override_value(raw: str) -> Any:
    """Parse a CLI override value into a Python object."""

    text = raw.strip()
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None
    if lower in {"nan"}:
        return float("nan")
    if lower in {"inf", "+inf", "+infinity", "infinity"}:
        return float("inf")
    if lower in {"-inf", "-infinity"}:
        return float("-inf")
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def apply_overrides_dict(payload: Dict[str, Any], overrides: Sequence[str]) -> Dict[str, Any]:
    """Apply dotted-path overrides to a configuration dictionary."""

    if not overrides:
        return payload
    for item in overrides:
        if not isinstance(item, str):  # pragma: no cover - defensive
            continue
        key, sep, value_str = item.partition("=")
        if not sep:
            raise ConfigurationError(f"Invalid override '{item}'; expected path=value")
        path = key.strip()
        if not path:
            raise ConfigurationError(f"Invalid override '{item}'; empty path")
        if path.startswith("physics."):
            path = path[len("physics.") :]
        parts = [segment for segment in path.split(".") if segment]
        if not parts:
            raise ConfigurationError(f"Invalid override '{item}'; empty path")
        target: Any = payload
        for segment in parts[:-1]:
            if isinstance(target, dict):
                if segment not in target or target[segment] is None:
                    target[segment] = {}
                target = target[segment]
            else:
                raise TypeError(
                    f"Cannot traverse into non-mapping for override '{item}' at '{segment}'"
                )
        final_key = parts[-1]
        value = parse_override_value(value_str)
        if isinstance(target, dict):
            target[final_key] = value
        else:
            raise TypeError(f"Cannot set override '{item}'; target is not a mapping")
    return payload


def merge_physics_section(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Inline an optional ``physics`` mapping into the root config tree."""

    if not isinstance(payload, dict):  # pragma: no cover - defensive guard
        return payload
    physics_block = payload.pop("physics", None)
    if isinstance(physics_block, dict):
        for key, value in physics_block.items():
            target_key = "physics_mode" if key == "mode" else key
            if target_key in payload:
                logger.debug(
                    "load_config: skipping physics.%s because top-level key exists",
                    target_key,
                )
                continue
            payload[target_key] = value
    return payload


def normalise_physics_mode(value: Any) -> str:
    """Return the canonical physics.mode string."""

    if value is None:
        return "default"
    text = str(value).strip().lower()
    if text in {"", "default", "off", "none", "full", "both"}:
        return "default"
    if text in {"sublimation_only", "sublimation"}:
        return "sublimation_only"
    if text in {"collisions_only", "collisional_only", "collision_only"}:
        return "collisions_only"
    logger.warning("Unknown physics_mode=%s; defaulting to 'default'", value)
    return "default"


def gather_git_info() -> Dict[str, Any]:
    """Return basic git metadata for provenance recording."""

    repo_root = Path(__file__).resolve().parents[1]
    info: Dict[str, Any] = {}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["commit"] = "unknown"
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["branch"] = "unknown"
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=repo_root, text=True
        )
        info["dirty"] = bool(status.strip())
    except Exception:
        info["dirty"] = None
    return info


def configure_logging(level: int, suppress_warnings: bool = False) -> None:
    """Configure root logging and optionally silence Python warnings."""

    logging.basicConfig(level=level)
    root = logging.getLogger()
    root.setLevel(level)
    if suppress_warnings:
        warnings.filterwarnings("ignore")
    logging.captureWarnings(True)
