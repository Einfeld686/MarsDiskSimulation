"""Time-dependent Mars temperature drivers for the radiation subsystem."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import logging

import numpy as np
import pandas as pd

from siO2_disk_cooling.model import CoolingParams, YEAR_SECONDS, mars_temperature

from .. import constants
from ..schema import (
    MarsTemperatureAutogen,
    MarsTemperatureDriverConfig,
    MarsTemperatureDriverTable,
    Radiation,
)

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400.0
SECONDS_PER_YEAR = 365.25 * SECONDS_PER_DAY

T_MIN, T_MAX = 1000.0, 6500.0


def _validate_temperature(value: float, *, context: str) -> float:
    if not np.isfinite(value):
        raise ValueError(f"{context} produced a non-finite Mars temperature ({value})")
    if not (T_MIN <= value <= T_MAX):
        raise ValueError(
            f"{context} produced an out-of-range Mars temperature {value:.3f} K "
            f"(expected within [{T_MIN}, {T_MAX}] K)"
        )
    return float(value)


def _time_unit_scale(unit: str, t_orb: Optional[float]) -> float:
    if unit == "s":
        return 1.0
    if unit == "day":
        return SECONDS_PER_DAY
    if unit == "yr":
        return SECONDS_PER_YEAR
    if unit == "orbit":
        if t_orb is None or t_orb <= 0.0:
            raise ValueError("time_unit='orbit' requires a positive orbital period")
        return float(t_orb)
    raise ValueError(f"Unsupported time unit '{unit}' for mars_temperature_driver")


def _load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Mars temperature driver table '{path}' not found")
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    elif suffix in {".json"}:
        df = pd.read_json(path)
    else:
        df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Mars temperature driver table '{path}' is empty")
    return df


def _prepare_table_driver(
    table_cfg: MarsTemperatureDriverConfig,
    *,
    t_orb: float,
) -> tuple[Callable[[float], float], Dict[str, Any]]:
    if table_cfg.table is None:
        raise ValueError("mars_temperature_driver.table must be provided for mode='table'")
    table = table_cfg.table
    df = _load_table(table.path)
    if table.column_time not in df.columns:
        raise ValueError(
            f"Column '{table.column_time}' missing in Mars temperature table '{table.path}'"
        )
    if table.column_temperature not in df.columns:
        raise ValueError(
            f"Column '{table.column_temperature}' missing in Mars temperature table '{table.path}'"
        )
    time_vals = pd.to_numeric(df[table.column_time], errors="coerce").to_numpy(dtype=float)
    temp_vals = pd.to_numeric(df[table.column_temperature], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(time_vals)):
        raise ValueError(f"Mars temperature driver table '{table.path}' contains non-finite time values")
    if not np.all(np.isfinite(temp_vals)):
        raise ValueError(f"Mars temperature driver table '{table.path}' contains non-finite temperature values")
    order = np.argsort(time_vals)
    time_sorted = np.asarray(time_vals[order], dtype=float)
    temp_sorted = np.asarray(temp_vals[order], dtype=float)
    mask = np.diff(time_sorted, prepend=time_sorted[0] - 1.0) > 0.0
    if not np.all(mask):
        time_sorted = time_sorted[mask]
        temp_sorted = temp_sorted[mask]
    if time_sorted.size < 2:
        raise ValueError("Mars temperature table must contain at least two distinct time samples")
    scale = _time_unit_scale(table.time_unit, t_orb)
    time_seconds = np.asarray(time_sorted * scale, dtype=float)
    temp_sorted = np.asarray(temp_sorted, dtype=float)
    extrapolation = table_cfg.extrapolation
    t_min = float(time_seconds[0])
    t_max = float(time_seconds[-1])

    def _interp(time_s: float) -> float:
        t_val = float(time_s)
        if t_val < t_min:
            if extrapolation == "error":
                raise ValueError(
                    f"T(t) requested at t={t_val:.3e} s < table minimum {t_min:.3e} s (extrapolation=error)"
                )
            return float(temp_sorted[0])
        if t_val > t_max:
            if extrapolation == "error":
                raise ValueError(
                    f"T(t) requested at t={t_val:.3e} s > table maximum {t_max:.3e} s (extrapolation=error)"
                )
            return float(temp_sorted[-1])
        return float(np.interp(t_val, time_seconds, temp_sorted))

    provenance = {
        "table_path": str(table.path),
        "time_unit": table.time_unit,
        "column_time": table.column_time,
        "column_temperature": table.column_temperature,
        "t_range_s": [t_min, t_max],
        "n_rows": int(time_seconds.size),
        "extrapolation": extrapolation,
    }
    return _interp, provenance


def _format_temperature_tag(T0: float) -> str:
    """Return a filesystem-friendly tag for the initial temperature."""

    tag = f"{float(T0):.1f}"
    safe = tag.replace("-", "m").replace(".", "p")
    return safe


def _target_years(t_end_years: float, autogen_cfg: MarsTemperatureAutogen) -> float:
    """Return the coverage horizon with padding applied."""

    horizon = max(float(t_end_years), float(autogen_cfg.min_years))
    return horizon + float(autogen_cfg.time_margin_years)


def _read_existing_max_time_s(
    path: Path, autogen_cfg: MarsTemperatureAutogen, *, t_orb: float
) -> Optional[float]:
    """Return max time in seconds from an existing table, or None if unusable."""

    if not path.exists():
        return None
    try:
        df = _load_table(path)
    except Exception:
        return None
    if autogen_cfg.column_time not in df.columns:
        return None
    scale = _time_unit_scale(autogen_cfg.time_unit, t_orb)
    times = pd.to_numeric(df[autogen_cfg.column_time], errors="coerce").to_numpy(dtype=float)
    if times.size == 0:
        return None
    max_time = float(np.nanmax(times))
    if not np.isfinite(max_time):
        return None
    return max_time * scale


def _write_temperature_table(
    path: Path,
    autogen_cfg: MarsTemperatureAutogen,
    *,
    T0: float,
    t_end_years: float,
    t_orb: float,
) -> float:
    """Generate and write T(t) using the SiO2 cooling analytic solution."""

    path.parent.mkdir(parents=True, exist_ok=True)
    dt_s = float(autogen_cfg.dt_hours) * 3600.0
    if dt_s <= 0.0:
        raise ValueError("autogen.dt_hours must be positive")
    scale = _time_unit_scale(autogen_cfg.time_unit, t_orb)
    t_end_s = float(t_end_years) * YEAR_SECONDS
    time_s = np.arange(0.0, t_end_s + 0.5 * dt_s, dt_s, dtype=float)
    temps = mars_temperature(time_s, float(T0), CoolingParams())
    df = pd.DataFrame(
        {
            autogen_cfg.column_time: time_s / scale,
            autogen_cfg.column_temperature: temps,
        }
    )
    df.to_csv(path, index=False)
    return float(time_s[-1]) if time_s.size else 0.0


def ensure_temperature_table(
    autogen_cfg: MarsTemperatureAutogen,
    *,
    T0: float,
    t_end_years: float,
    t_orb: float,
) -> Dict[str, Any]:
    """Ensure a Mars temperature table exists and covers the requested horizon."""

    T_val = _validate_temperature(float(T0), context="temperature autogen")
    target_years = _target_years(t_end_years, autogen_cfg)
    tag = _format_temperature_tag(T_val)
    filename = autogen_cfg.filename_template.format(tag=tag)
    path = Path(autogen_cfg.output_dir) / filename
    required_s = target_years * YEAR_SECONDS
    existing_max_s = _read_existing_max_time_s(path, autogen_cfg, t_orb=t_orb)
    generated = False
    last_time_s = existing_max_s if existing_max_s is not None else 0.0
    if existing_max_s is None or existing_max_s + 1.0 < required_s:
        last_time_s = _write_temperature_table(
            path,
            autogen_cfg,
            T0=T_val,
            t_end_years=target_years,
            t_orb=t_orb,
        )
        generated = True
        logger.info(
            "Generated Mars temperature table at %s (T0=%.1f K, span=%.3f yr, dt=%.2f h)",
            path,
            T_val,
            last_time_s / YEAR_SECONDS if last_time_s else target_years,
            autogen_cfg.dt_hours,
        )
    else:
        logger.info(
            "Reusing existing Mars temperature table at %s (coverage=%.3f yr required=%.3f yr)",
            path,
            last_time_s / YEAR_SECONDS,
            target_years,
        )

    return {
        "path": path,
        "generated": generated,
        "coverage_years": last_time_s / YEAR_SECONDS if last_time_s else target_years,
        "target_years": target_years,
        "time_unit": autogen_cfg.time_unit,
        "column_time": autogen_cfg.column_time,
        "column_temperature": autogen_cfg.column_temperature,
    }


@dataclass
class TemperatureDriverRuntime:
    """Runtime helper that evaluates the Mars temperature at arbitrary times."""

    source: str
    mode: str
    enabled: bool
    initial_value: float
    provenance: Dict[str, Any]
    _driver_fn: Callable[[float], float]

    def evaluate(self, time_s: float) -> float:
        """Return T_M(t) with validation."""

        value = float(self._driver_fn(time_s))
        return _validate_temperature(value, context=f"Mars temperature driver ({self.mode})")


def resolve_temperature_driver(
    radiation_cfg: Optional[Radiation],
    *,
    t_orb: float,
    prefer_driver: bool = False,
) -> TemperatureDriverRuntime:
    """Return the driver controlling the Mars-facing temperature."""

    driver_cfg = getattr(radiation_cfg, "mars_temperature_driver", None) if radiation_cfg is not None else None
    tm_override = getattr(radiation_cfg, "TM_K", None) if radiation_cfg is not None else None

    if driver_cfg is not None and driver_cfg.enabled and prefer_driver:
        tm_override = None

    if driver_cfg is not None and driver_cfg.enabled:
        if driver_cfg.mode == "constant":
            if driver_cfg.constant is None:
                raise ValueError("mars_temperature_driver.constant must be provided for mode='constant'")
            value = _validate_temperature(
                float(driver_cfg.constant.value_K), context="mars_temperature_driver.constant"
            )
            provenance = {
                "source": "mars_temperature_driver.constant",
                "mode": "constant",
                "enabled": True,
                "value_K": value,
            }
            return TemperatureDriverRuntime(
                source="mars_temperature_driver.constant",
                mode="constant",
                enabled=True,
                initial_value=value,
                provenance=provenance,
                _driver_fn=lambda _time: value,
            )
        if driver_cfg.mode == "table":
            interp_fn, table_meta = _prepare_table_driver(driver_cfg, t_orb=t_orb)
            value = _validate_temperature(interp_fn(0.0), context="mars_temperature_driver.table")
            provenance = {
                "source": "mars_temperature_driver.table",
                "mode": "table",
                "enabled": True,
                **table_meta,
            }
            return TemperatureDriverRuntime(
                source="mars_temperature_driver.table",
                mode="table",
                enabled=True,
                initial_value=value,
                provenance=provenance,
                _driver_fn=interp_fn,
            )
        raise ValueError(f"Unsupported mars_temperature_driver.mode='{driver_cfg.mode}'")

    if tm_override is not None:
        value = _validate_temperature(float(tm_override), context="radiation.TM_K override")
        provenance = {"source": "radiation.TM_K", "enabled": False, "mode": "constant"}
        return TemperatureDriverRuntime(
            source="radiation.TM_K",
            mode="constant",
            enabled=False,
            initial_value=value,
            provenance=provenance,
            _driver_fn=lambda _time: value,
        )

    raise ValueError("Mars temperature is not specified: set radiation.TM_K or enable mars_temperature_driver")


def autogenerate_temperature_table_if_needed(
    rad_cfg: Any,
    *,
    t_end_years: float,
    t_orb: float,
) -> Optional[Dict[str, Any]]:
    """Generate a Mars temperature table when autogen is enabled on the driver."""

    if rad_cfg is None or getattr(rad_cfg, "source", "mars") == "off":
        return None

    driver_cfg: Optional[MarsTemperatureDriverConfig] = getattr(rad_cfg, "mars_temperature_driver", None)
    # If a table driver with a path is already provided, assume cooling is handled.
    if (
        driver_cfg is not None
        and getattr(driver_cfg, "enabled", False)
        and getattr(driver_cfg, "mode", "table") == "table"
        and getattr(driver_cfg, "table", None) is not None
        and getattr(driver_cfg.table, "path", None) is not None
        and Path(driver_cfg.table.path).exists()
    ):
        return None

    autogen_cfg: Optional[MarsTemperatureAutogen] = getattr(driver_cfg, "autogenerate", None) if driver_cfg else None
    if autogen_cfg is None:
        autogen_cfg = MarsTemperatureAutogen(enabled=True)
    else:
        autogen_cfg.enabled = True

    if rad_cfg.TM_K is not None:
        T0 = float(rad_cfg.TM_K)
    elif driver_cfg is not None and driver_cfg.mode == "constant" and driver_cfg.constant is not None:
        T0 = float(driver_cfg.constant.value_K)
    else:
        raise ValueError("Temperature autogeneration enabled but no initial temperature specified")

    table_info = ensure_temperature_table(
        autogen_cfg,
        T0=T0,
        t_end_years=t_end_years,
        t_orb=t_orb,
    )

    table_cfg = (
        driver_cfg.table
        if driver_cfg is not None and driver_cfg.table is not None
        else MarsTemperatureDriverTable(
            path=table_info["path"],
            time_unit=autogen_cfg.time_unit,
            column_time=autogen_cfg.column_time,
            column_temperature=autogen_cfg.column_temperature,
        )
    )
    table_cfg.path = Path(table_info["path"])
    table_cfg.time_unit = autogen_cfg.time_unit
    table_cfg.column_time = autogen_cfg.column_time
    table_cfg.column_temperature = autogen_cfg.column_temperature

    if driver_cfg is None:
        driver_cfg = MarsTemperatureDriverConfig(
            enabled=True,
            mode="table",
            table=table_cfg,
            extrapolation="hold",
            autogenerate=autogen_cfg,
        )
        rad_cfg.mars_temperature_driver = driver_cfg
    else:
        driver_cfg.enabled = True
        driver_cfg.mode = "table"
        driver_cfg.table = table_cfg
        driver_cfg.autogenerate = autogen_cfg

    rad_cfg.TM_K = rad_cfg.TM_K if rad_cfg.TM_K is not None else T0
    logger.info(
        "Mars temperature autogen selected table %s (generated=%s)",
        table_info["path"],
        table_info["generated"],
    )
    return table_info
