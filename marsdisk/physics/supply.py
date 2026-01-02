from __future__ import annotations

"""External surface supply parameterisations.

This module evaluates the production rate of sub--blow-out material per unit
area according to a :class:`~marsdisk.schema.Supply` specification.  The public
entry point :func:`get_prod_area_rate` returns the rate already multiplied by
the configured mixing efficiency ``epsilon_mix`` and clipped to be
non-negative.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .. import constants
from ..errors import MarsDiskError
from ..schema import Supply, SupplyPiece

_EPS = 1.0e-12
SECONDS_PER_YEAR = constants.SECONDS_PER_YEAR


@dataclass
class _TableData:
    """Holder for time/radius grids and associated rates."""

    t: np.ndarray
    r: np.ndarray
    rate: np.ndarray

    @classmethod
    def load(cls, path: Path) -> "_TableData":
        df = pd.read_csv(path)
        if {"t", "r", "rate"}.issubset(df.columns):
            t_vals = np.unique(df["t"].to_numpy(dtype=float))
            r_vals = np.unique(df["r"].to_numpy(dtype=float))
            grid = (
                df.pivot_table(index="t", columns="r", values="rate")
                .reindex(index=t_vals, columns=r_vals)
                .to_numpy(dtype=float)
            )
            if t_vals.size < 2 or r_vals.size < 2:
                raise ValueError("supply table requires at least two unique t and r values")
            if not np.all(np.isfinite(t_vals)) or not np.all(np.isfinite(r_vals)):
                raise ValueError("supply table contains non-finite t or r values")
            if grid.size == 0:
                raise ValueError("supply table must contain at least one data point")
            if not np.all(np.isfinite(grid)):
                raise ValueError("supply table contains missing or non-finite grid values")
            return cls(t_vals, r_vals, grid)
        t = df.iloc[:, 0].to_numpy(dtype=float)
        rate = df.iloc[:, -1].to_numpy(dtype=float)
        return cls(t, np.array([]), rate[:, None])

    def interp(self, t: float, r: float) -> float:
        if self.r.size == 0:
            return float(
                np.interp(t, self.t, self.rate[:, 0], left=self.rate[0, 0], right=self.rate[-1, 0])
            )
        t_idx = np.clip(np.searchsorted(self.t, t) - 1, 0, len(self.t) - 2)
        r_idx = np.clip(np.searchsorted(self.r, r) - 1, 0, len(self.r) - 2)
        t0, t1 = self.t[t_idx], self.t[t_idx + 1]
        r0, r1 = self.r[r_idx], self.r[r_idx + 1]
        f00 = self.rate[t_idx, r_idx]
        f01 = self.rate[t_idx, r_idx + 1]
        f10 = self.rate[t_idx + 1, r_idx]
        f11 = self.rate[t_idx + 1, r_idx + 1]
        wt = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        wr = 0.0 if r1 == r0 else (r - r0) / (r1 - r0)
        return float((1 - wt) * (1 - wr) * f00 + (1 - wt) * wr * f01 + wt * (1 - wr) * f10 + wt * wr * f11)


@dataclass
class _TemperatureTable:
    """Holder for temperature→value lookup tables."""

    temperature: np.ndarray
    value: np.ndarray
    column_temperature: str
    column_value: str

    @classmethod
    def load(cls, path: Path, column_temperature: str, column_value: str) -> "_TemperatureTable":
        df = pd.read_csv(path)
        if column_temperature not in df.columns or column_value not in df.columns:
            raise KeyError(f"temperature table {path} must contain '{column_temperature}' and '{column_value}' columns")
        temp_sorted = df.sort_values(column_temperature)
        temperature = temp_sorted[column_temperature].to_numpy(dtype=float)
        value = temp_sorted[column_value].to_numpy(dtype=float)
        if temperature.size == 0 or value.size == 0:
            raise ValueError(f"temperature table {path} must contain at least one row")
        if not np.all(np.isfinite(temperature)):
            raise ValueError(f"temperature table {path} contains non-finite temperature values")
        if np.any(temperature <= 0.0):
            raise ValueError(f"temperature table {path} requires positive temperatures")
        if not np.all(np.isfinite(value)):
            raise ValueError(f"temperature table {path} contains non-finite values")
        return cls(temperature, value, column_temperature, column_value)

    def interp(self, temperature_K: float) -> float:
        return float(
            np.interp(
                temperature_K,
                self.temperature,
                self.value,
                left=self.value[0],
                right=self.value[-1],
            )
        )


@dataclass
class SupplyEvalResult:
    """Evaluation output for a single timestep."""

    rate: float
    raw_rate: float
    mixed_rate: float
    temperature_scale: float
    feedback_scale: float
    reservoir_scale: float
    reservoir_remaining_Mmars: Optional[float]
    reservoir_fraction: Optional[float]
    clipped_by_reservoir: bool
    feedback_error: Optional[float]
    temperature_value: Optional[float]
    temperature_value_kind: str


@dataclass
class SupplySplitResult:
    """Allocation of supply between surface and deep reservoir."""

    prod_rate_applied: float
    prod_rate_diverted: float
    deep_to_surf_rate: float
    sigma_deep: float
    headroom: Optional[float] = None
    prod_rate_into_deep: float = 0.0
    deep_to_surf_flux_attempt: float = 0.0
    deep_to_surf_flux_applied: float = 0.0
    transport_mode: str = "direct"


@dataclass
class SupplyRuntimeState:
    """Mutable state for reservoir accounting and feedback control."""

    reservoir_enabled: bool = False
    reservoir_mass_total_kg: Optional[float] = None
    reservoir_mass_remaining_kg: Optional[float] = None
    reservoir_mode: str = "none"
    reservoir_taper_fraction: float = 0.0
    feedback_enabled: bool = False
    feedback_scale: float = 1.0
    feedback_target_tau: float = 1.0
    feedback_gain: float = 1.0
    feedback_response_time_s: float = 0.0
    feedback_tau_field: str = "tau_los"
    feedback_min_scale: float = 1.0e-6
    feedback_max_scale: float = 10.0
    temperature_mode: str = "off"
    temperature_reference_K: float = 1.0
    temperature_exponent: float = 1.0
    temperature_scale_at_reference: float = 1.0
    temperature_floor: float = 0.0
    temperature_cap: float = float("inf")
    temperature_table: Optional[_TemperatureTable] = None
    temperature_value_kind: str = "scale"

    def reservoir_remaining_Mmars(self) -> Optional[float]:
        if self.reservoir_mass_remaining_kg is None:
            return None
        return float(self.reservoir_mass_remaining_kg / constants.M_MARS)

    def reservoir_fraction(self) -> Optional[float]:
        if self.reservoir_mass_remaining_kg is None or not self.reservoir_mass_total_kg:
            return None
        if self.reservoir_mass_total_kg <= 0.0:
            return None
        return float(self.reservoir_mass_remaining_kg / self.reservoir_mass_total_kg)


_TABLE_CACHE: Dict[tuple[Path, str], _TableData] = {}
_TEMP_TABLE_CACHE: Dict[Path, _TemperatureTable] = {}


def _table_time_scale(unit: str) -> float:
    unit_norm = str(unit or "s").lower()
    if unit_norm == "year":
        return SECONDS_PER_YEAR
    return 1.0


def _rate_basic(t: float, r: float, spec: Supply | SupplyPiece) -> float:
    mode = spec.mode
    if mode == "const":
        return spec.const.prod_area_rate_kg_m2_s
    if mode == "powerlaw":
        A = spec.powerlaw.A_kg_m2_s
        if A is None:
            return 0.0
        t0 = spec.powerlaw.t0_s if spec.powerlaw.t0_s > 0.0 else 0.0
        if t < t0:
            return 0.0
        return A * ((t - t0) + _EPS) ** spec.powerlaw.index
    if mode == "table":
        time_unit = getattr(spec.table, "time_unit", "s")
        cache_key = (spec.table.path, str(time_unit))
        data = _TABLE_CACHE.get(cache_key)
        if data is None:
            data = _TableData.load(spec.table.path)
            _TABLE_CACHE[cache_key] = data
        scale = _table_time_scale(time_unit)
        t_eval = float(t) / scale if scale > 0.0 else float(t)
        return data.interp(t_eval, r)
    if mode == "piecewise":  # type: ignore[comparison-overlap]
        for piece in spec.piecewise:
            if piece.t_start_s <= t < piece.t_end_s:
                return _rate_basic(t, r, piece)
        return 0.0
    return 0.0


def init_runtime_state(
    spec: Supply,
    area: float,
    *,
    seconds_per_year: float = SECONDS_PER_YEAR,
) -> SupplyRuntimeState:
    """Create a mutable state container for supply evaluation."""

    state = SupplyRuntimeState()
    reservoir_cfg = getattr(spec, "reservoir", None)
    if reservoir_cfg is not None:
        total_mass_mmars = getattr(reservoir_cfg, "mass_total_Mmars", None)
        reservoir_enabled = bool(getattr(reservoir_cfg, "enabled", False)) or total_mass_mmars is not None
        if reservoir_enabled:
            state.reservoir_enabled = True
            total_mass_kg = float(total_mass_mmars) * constants.M_MARS if total_mass_mmars is not None else 0.0
            state.reservoir_mass_total_kg = total_mass_kg
            state.reservoir_mass_remaining_kg = total_mass_kg
            mode = str(getattr(reservoir_cfg, "depletion_mode", "hard_stop"))
            if mode == "smooth":
                mode = "taper"
            state.reservoir_mode = mode
            taper_fraction = float(
                getattr(reservoir_cfg, "taper_fraction", getattr(reservoir_cfg, "smooth_fraction", 0.0))
            )
            state.reservoir_taper_fraction = taper_fraction

    feedback_cfg = getattr(spec, "feedback", None)
    if feedback_cfg is not None and getattr(feedback_cfg, "enabled", False):
        state.feedback_enabled = True
        state.feedback_scale = float(getattr(feedback_cfg, "initial_scale", 1.0))
        state.feedback_target_tau = float(getattr(feedback_cfg, "target_tau", 1.0))
        state.feedback_gain = float(getattr(feedback_cfg, "gain", 1.0))
        state.feedback_response_time_s = float(getattr(feedback_cfg, "response_time_years", 0.0)) * seconds_per_year
        state.feedback_tau_field = str(getattr(feedback_cfg, "tau_field", "tau_los"))
        state.feedback_min_scale = float(getattr(feedback_cfg, "min_scale", 0.0))
        state.feedback_max_scale = float(getattr(feedback_cfg, "max_scale", 10.0))

    temp_cfg = getattr(spec, "temperature", None)
    if temp_cfg is not None and getattr(temp_cfg, "enabled", False):
        state.temperature_mode = str(getattr(temp_cfg, "mode", "scale"))
        state.temperature_reference_K = float(getattr(temp_cfg, "reference_K", 1.0))
        state.temperature_exponent = float(getattr(temp_cfg, "exponent", 1.0))
        state.temperature_scale_at_reference = float(getattr(temp_cfg, "scale_at_reference", 1.0))
        state.temperature_floor = float(getattr(temp_cfg, "floor", 0.0))
        state.temperature_cap = float(getattr(temp_cfg, "cap", float("inf")))
        table_cfg = getattr(temp_cfg, "table", None)
        if state.temperature_mode == "table" and table_cfg is not None:
            temp_path = table_cfg.path
            table = _TEMP_TABLE_CACHE.get(temp_path)
            if table is None:
                table = _TemperatureTable.load(temp_path, table_cfg.column_temperature, table_cfg.column_value)
                _TEMP_TABLE_CACHE[temp_path] = table
            state.temperature_table = table
            state.temperature_value_kind = str(getattr(table_cfg, "value_kind", "scale"))
    return state


def _temperature_factor(
    temperature_K: Optional[float],
    state: Optional[SupplyRuntimeState],
) -> Tuple[float, Optional[float], str, Optional[float]]:
    """Return (scale, override_rate, value_kind, raw_value)."""

    if state is None or state.temperature_mode == "off":
        return 1.0, None, "scale", None
    if temperature_K is None:
        return 1.0, None, "scale", None
    if not math.isfinite(temperature_K) or temperature_K <= 0.0:
        raise MarsDiskError("temperature_K must be positive and finite for supply temperature scaling")

    override_rate = None
    raw_value = None
    if state.temperature_mode == "scale":
        ref = state.temperature_reference_K if state.temperature_reference_K > 0.0 else 1.0
        scale = state.temperature_scale_at_reference * (temperature_K / ref) ** state.temperature_exponent
        scale = float(np.clip(scale, state.temperature_floor, state.temperature_cap))
        return scale, None, "scale", scale

    if state.temperature_mode == "table" and state.temperature_table is not None:
        raw_value = state.temperature_table.interp(temperature_K)
        if state.temperature_value_kind == "rate":
            override_rate = float(raw_value)
            scale = 1.0
        else:
            scale = float(np.clip(raw_value, state.temperature_floor, state.temperature_cap))
        return scale, override_rate, state.temperature_value_kind, raw_value

    return 1.0, None, "scale", None


def evaluate_supply(
    t: float,
    r: float,
    dt: float,
    spec: Supply,
    *,
    area: float,
    state: Optional[SupplyRuntimeState] = None,
    tau_for_feedback: Optional[float] = None,
    temperature_K: Optional[float] = None,
    apply_reservoir: bool = True,
) -> SupplyEvalResult:
    """Evaluate the surface production rate with optional feedback and reservoir tracking."""

    if not getattr(spec, "enabled", True):
        return SupplyEvalResult(
            rate=0.0,
            raw_rate=0.0,
            mixed_rate=0.0,
            temperature_scale=1.0,
            feedback_scale=1.0,
            reservoir_scale=1.0,
            reservoir_remaining_Mmars=state.reservoir_remaining_Mmars() if state else None,
            reservoir_fraction=state.reservoir_fraction() if state else None,
            clipped_by_reservoir=False,
            feedback_error=None,
            temperature_value=None,
            temperature_value_kind="scale",
        )

    raw = _rate_basic(t, r, spec)
    mixed = raw * spec.mixing.epsilon_mix

    temp_scale, temp_override, temp_value_kind, temp_value = _temperature_factor(temperature_K, state)
    rate_pre_feedback = temp_override if temp_override is not None else mixed * temp_scale

    feedback_scale = 1.0
    feedback_error = None
    if state is not None and state.feedback_enabled:
        feedback_scale = state.feedback_scale
        if tau_for_feedback is not None and math.isfinite(tau_for_feedback):
            target_tau = max(state.feedback_target_tau, _EPS)
            feedback_error = (state.feedback_target_tau - tau_for_feedback) / target_tau
            step_gain = state.feedback_gain * (dt / max(state.feedback_response_time_s, _EPS))
            feedback_scale = float(state.feedback_scale * (1.0 + step_gain * feedback_error))
            feedback_scale = float(np.clip(feedback_scale, state.feedback_min_scale, state.feedback_max_scale))
            state.feedback_scale = feedback_scale

    rate = rate_pre_feedback * feedback_scale
    reservoir_scale = 1.0
    clipped = False
    if (
        apply_reservoir
        and state is not None
        and state.reservoir_enabled
        and state.reservoir_mass_remaining_kg is not None
        and dt > 0.0
        and area > 0.0
    ):
        remaining = state.reservoir_mass_remaining_kg
        total = state.reservoir_mass_total_kg if state.reservoir_mass_total_kg is not None else remaining
        fraction_remaining = None
        if total and total > 0.0:
            fraction_remaining = remaining / total
        if state.reservoir_mode in {"taper", "smooth"} and fraction_remaining is not None:
            taper_fraction = max(state.reservoir_taper_fraction, 0.0)
            if taper_fraction > 0.0 and fraction_remaining < taper_fraction:
                ramp = fraction_remaining / max(taper_fraction, _EPS)
                reservoir_scale = min(reservoir_scale, max(ramp, 0.0))
        max_rate = remaining / (area * dt)
        if max_rate < rate:
            clipped = True
            reservoir_scale = min(reservoir_scale, max_rate / max(rate, _EPS))
        rate *= reservoir_scale
        mass_draw = rate * area * dt
        state.reservoir_mass_remaining_kg = max(remaining - mass_draw, 0.0)

    reservoir_remaining = state.reservoir_remaining_Mmars() if state is not None else None
    reservoir_fraction = state.reservoir_fraction() if state is not None else None

    return SupplyEvalResult(
        rate=max(rate, 0.0),
        raw_rate=raw,
        mixed_rate=max(mixed, 0.0),
        temperature_scale=temp_scale,
        feedback_scale=feedback_scale,
        reservoir_scale=reservoir_scale,
        reservoir_remaining_Mmars=reservoir_remaining,
        reservoir_fraction=reservoir_fraction,
        clipped_by_reservoir=clipped,
        feedback_error=feedback_error,
        temperature_value=temp_value,
        temperature_value_kind=temp_value_kind,
    )


def split_supply_with_deep_buffer(
    prod_rate_raw: float,
    dt: float,
    sigma_surf: float,
    sigma_tau1: Optional[float],
    sigma_deep: float,
    *,
    t_mix: Optional[float],
    deep_enabled: bool,
    transport_mode: str = "direct",
    headroom_gate: str = "hard",
    headroom_policy: str = "clip",
    t_blow: Optional[float] = None,
) -> SupplySplitResult:
    """Route external supply between the surface and a deep reservoir."""

    prod_rate = max(float(prod_rate_raw), 0.0)
    if dt <= 0.0 or not math.isfinite(dt):
        return SupplySplitResult(
            prod_rate,
            0.0,
            0.0,
            float(sigma_deep),
            sigma_tau1,
            prod_rate_into_deep=0.0,
            deep_to_surf_flux_attempt=0.0,
            deep_to_surf_flux_applied=0.0,
            transport_mode=str(transport_mode or "direct"),
        )

    policy = str(headroom_policy or "clip").lower()
    headroom_disabled = policy in {"none", "off", "disabled"}
    spill_mode = policy == "spill"
    headroom = None
    if not headroom_disabled and sigma_tau1 is not None and math.isfinite(sigma_tau1):
        sigma_cap = max(min(float(sigma_surf), float(sigma_tau1)), 0.0)
        headroom = max(float(sigma_tau1) - sigma_cap, 0.0)

    mode = str(transport_mode or "direct").lower()
    gate_mode = str(headroom_gate or "hard").lower()
    dSigma_in = prod_rate * dt
    dSigma_to_surf_direct = dSigma_in
    dSigma_into_deep = 0.0
    sigma_deep_new = float(sigma_deep)
    deep_to_surf_attempt = 0.0
    deep_to_surf_applied = 0.0

    dotSigma_max = float("inf")
    if dt > 0.0:
        dot_headroom = float("inf") if headroom is None else max(headroom / dt, 0.0)
        dot_replenish = 0.0
        if (
            sigma_tau1 is not None
            and math.isfinite(sigma_tau1)
            and t_blow is not None
            and t_blow > 0.0
            and math.isfinite(t_blow)
        ):
            dot_replenish = max(float(sigma_tau1) / t_blow, 0.0)
        dotSigma_max = dot_headroom + dot_replenish

    limit_dSigma = dotSigma_max * dt if math.isfinite(dotSigma_max) else float("inf")

    if mode == "deep_mixing":
        dSigma_into_deep = dSigma_in
        sigma_deep_new += dSigma_into_deep
        available_headroom = float("inf") if spill_mode or headroom is None else max(headroom, 0.0)
        if deep_enabled and t_mix is not None and t_mix > 0.0:
            deep_to_surf_attempt = sigma_deep_new * (dt / t_mix)
            deep_to_surf_applied = deep_to_surf_attempt
            if (gate_mode == "hard" or gate_mode == "soft") and not spill_mode:
                deep_to_surf_applied = min(available_headroom, deep_to_surf_applied, sigma_deep_new)
            cap_remaining = max(limit_dSigma, 0.0)
            deep_to_surf_applied = min(deep_to_surf_applied, cap_remaining)
            sigma_deep_new = max(sigma_deep_new - deep_to_surf_applied, 0.0)
        dSigma_to_surf_direct = 0.0
    else:
        if headroom is not None and not spill_mode:
            dSigma_to_surf_direct = min(dSigma_in, headroom)
            dSigma_into_deep = dSigma_in - dSigma_to_surf_direct
        # Apply global surface cap including replenishment term
        dSigma_to_surf_direct = min(dSigma_to_surf_direct, limit_dSigma)
        if deep_enabled:
            sigma_deep_new += dSigma_into_deep
            available_headroom = float("inf") if spill_mode or headroom is None else max(headroom - dSigma_to_surf_direct, 0.0)
            cap_remaining = max(limit_dSigma - dSigma_to_surf_direct, 0.0)
            if t_mix is not None and t_mix > 0.0:
                deep_to_surf_attempt = sigma_deep_new * (dt / t_mix)
                if spill_mode:
                    deep_to_surf_applied = min(deep_to_surf_attempt, sigma_deep_new, cap_remaining)
                else:
                    deep_to_surf_applied = min(available_headroom, deep_to_surf_attempt, sigma_deep_new, cap_remaining)
                sigma_deep_new = max(sigma_deep_new - deep_to_surf_applied, 0.0)

    dSigma_to_surf = dSigma_to_surf_direct + deep_to_surf_applied
    prod_rate_applied = dSigma_to_surf / dt
    prod_rate_into_deep = dSigma_into_deep / dt if dSigma_into_deep > 0.0 else 0.0
    prod_rate_diverted = max(dSigma_into_deep - deep_to_surf_applied, 0.0) / dt
    deep_to_surf_rate = deep_to_surf_applied / dt if deep_to_surf_applied > 0.0 else 0.0
    deep_to_surf_attempt_rate = deep_to_surf_attempt / dt if deep_to_surf_attempt > 0.0 else 0.0

    return SupplySplitResult(
        prod_rate_applied=prod_rate_applied,
        prod_rate_diverted=prod_rate_diverted,
        deep_to_surf_rate=deep_to_surf_rate,
        sigma_deep=sigma_deep_new,
        headroom=headroom,
        prod_rate_into_deep=prod_rate_into_deep,
        deep_to_surf_flux_attempt=deep_to_surf_attempt_rate,
        deep_to_surf_flux_applied=deep_to_surf_rate,
        transport_mode=mode,
    )


def get_prod_area_rate(t: float, r: float, spec: Supply) -> float:
    """Return the mixed surface production rate in kg m⁻² s⁻¹."""

    result = evaluate_supply(t, r, dt=0.0, spec=spec, area=1.0, state=None, apply_reservoir=False)
    return result.rate


__all__ = [
    "SupplyEvalResult",
    "SupplyRuntimeState",
    "SupplySplitResult",
    "evaluate_supply",
    "split_supply_with_deep_buffer",
    "get_prod_area_rate",
    "init_runtime_state",
]
