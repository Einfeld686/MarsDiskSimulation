"""Phase (solid/vapour) inference and hydrodynamic sink helpers."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
import math
from typing import Any, Callable, Dict, Literal, Optional

from ..schema import HydroEscapeConfig, PhaseConfig, PhaseMapConfig, PhaseThresholds

logger = logging.getLogger(__name__)

DEFAULT_ENTRYPOINT = "siO2_disk_cooling.siO2_cooling_map:lookup_phase_state"


@dataclass
class PhaseDecision:
    """Return value describing the resolved phase state for one step."""

    state: Literal["solid", "vapor"]
    f_vap: float
    method: str
    reason: str
    used_map: bool
    payload: Dict[str, Any]


class PhaseEvaluator:
    """Resolve the effective phase state using maps or threshold fallbacks."""

    def __init__(self, cfg: Optional[PhaseConfig]) -> None:
        self._cfg = cfg
        self.enabled = bool(cfg and cfg.enabled)
        self.source = (cfg.source if cfg is not None else "threshold") if self.enabled else "disabled"
        self.thresholds = cfg.thresholds if cfg is not None else PhaseThresholds()
        self.entrypoint = self._resolve_entrypoint(cfg.map if cfg else None)
        self._map_callable: Optional[Callable[..., Any]] = None
        self._map_error_logged = False
        if self.enabled and self.source == "map":
            self._map_callable = self._load_map_callable(self.entrypoint)

    @staticmethod
    def _resolve_entrypoint(map_cfg: Optional[PhaseMapConfig]) -> str:
        if map_cfg is None or not map_cfg.entrypoint:
            return DEFAULT_ENTRYPOINT
        return str(map_cfg.entrypoint)

    def _load_map_callable(self, entrypoint: str | None) -> Optional[Callable[..., Any]]:
        if entrypoint is None:
            return None
        module_name, sep, func_name = entrypoint.partition(":")
        if not module_name:
            logger.warning("phase: invalid map entrypoint '%s'", entrypoint)
            return None
        target_attr = func_name or "lookup_phase_state"
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            logger.warning("phase: unable to import map module '%s': %s", module_name, exc)
            return None
        try:
            func = getattr(module, target_attr)
        except AttributeError:
            logger.warning(
                "phase: entrypoint '%s' missing attribute '%s'", module_name, target_attr
            )
            return None
        if not callable(func):
            logger.warning(
                "phase: entrypoint '%s:%s' is not callable", module_name, target_attr
            )
            return None
        logger.info("phase: using map entrypoint %s:%s", module_name, target_attr)
        return func

    def evaluate(
        self,
        temperature_K: float,
        *,
        pressure_Pa: Optional[float] = None,
        tau: Optional[float] = None,
    ) -> PhaseDecision:
        pressure_clean: Optional[float] = None
        if pressure_Pa is not None and math.isfinite(pressure_Pa):
            pressure_clean = float(max(pressure_Pa, 0.0))
        tau_clean: Optional[float] = None
        if tau is not None and math.isfinite(tau):
            tau_clean = float(max(tau, 0.0))
        diagnostics: Dict[str, Any] = {
            "temperature_K": float(temperature_K),
            "pressure_Pa": pressure_clean,
            "pressure_bar": (pressure_clean / 1.0e5) if pressure_clean is not None else None,
            "tau_clamped": tau_clean,
        }
        if not self.enabled:
            return PhaseDecision(
                state="solid",
                f_vap=0.0,
                method="disabled",
                reason="phase.disabled",
                used_map=False,
                payload=diagnostics,
            )

        if self.source == "map" and self._map_callable is not None:
            try:
                raw = self._call_map(self._map_callable, temperature_K, pressure_clean, tau_clean)
                decision = self._parse_map_result(raw, diagnostics)
                if decision is not None:
                    return decision
            except Exception as exc:  # pragma: no cover - defensive logging
                if not self._map_error_logged:
                    logger.warning("phase: map evaluation failed (%s); falling back to thresholds", exc)
                    self._map_error_logged = True
        elif self.source == "map" and not self._map_error_logged:
            logger.info("phase: map source requested but entrypoint unavailable; using thresholds")
            self._map_error_logged = True

        return self._threshold_decision(temperature_K, pressure_clean, tau_clean, diagnostics)

    def _call_map(
        self,
        func: Callable[..., Any],
        temperature_K: float,
        pressure_Pa: Optional[float],
        tau: Optional[float],
    ) -> Any:
        try:
            return func(temperature_K, pressure_Pa, tau)
        except TypeError:
            pass
        try:
            return func(temperature_K, pressure_Pa)
        except TypeError:
            pass
        return func(temperature_K)

    def _parse_map_result(
        self,
        payload: Any,
        diagnostics: Dict[str, Any],
    ) -> Optional[PhaseDecision]:
        state: Optional[str] = None
        f_vap: Optional[float] = None
        reason = "phase.map"
        used_map = True

        if isinstance(payload, dict):
            diagnostics.update({k: v for k, v in payload.items() if k not in diagnostics})
            state = payload.get("state") or payload.get("phase_state")
            f_vap = payload.get("f_vap") or payload.get("fraction")
        elif isinstance(payload, (list, tuple)) and payload:
            state = payload[0]
            if len(payload) > 1:
                try:
                    f_vap = float(payload[1])
                except (TypeError, ValueError):
                    f_vap = None
        elif isinstance(payload, str):
            state = payload

        if state is None:
            return None
        state_norm = str(state).strip().lower()
        if state_norm not in {"solid", "vapor"}:
            return None
        f_vap_val = 1.0 if state_norm == "vapor" else 0.0
        if f_vap is not None:
            try:
                f_vap_val = float(f_vap)
            except (TypeError, ValueError):
                f_vap_val = 0.0
        f_vap_val = float(min(max(f_vap_val, 0.0), 1.0))
        state_final: Literal["solid", "vapor"] = "vapor" if f_vap_val >= 0.5 else "solid"
        return PhaseDecision(
            state=state_final,
            f_vap=f_vap_val,
            method="map",
            reason=reason,
            used_map=used_map,
            payload=diagnostics,
        )

    def _threshold_decision(
        self,
        temperature_K: float,
        pressure_Pa: Optional[float],
        tau: Optional[float],
        diagnostics: Dict[str, Any],
    ) -> PhaseDecision:
        T = float(temperature_K)
        if not math.isfinite(T) or T <= 0.0:
            raise ValueError("temperature_K must be positive and finite for phase evaluation")
        thresh = self.thresholds
        T_cond = float(thresh.T_condense_K)
        T_vap = float(max(thresh.T_vaporize_K, T_cond + 1.0))
        pressure_bar = None
        if pressure_Pa is not None and math.isfinite(pressure_Pa):
            pressure_bar = float(pressure_Pa / 1.0e5)
        tau_val = None
        if tau is not None and math.isfinite(tau):
            tau_val = float(max(tau, 0.0))

        if T <= T_cond:
            frac = 0.0
        elif T >= T_vap:
            frac = 1.0
        else:
            span = T_vap - T_cond
            frac = (T - T_cond) / span
            if pressure_bar is not None and thresh.P_ref_bar > 0.0:
                frac /= 1.0 + pressure_bar / float(thresh.P_ref_bar)
            if tau_val is not None and thresh.tau_ref > 0.0:
                frac /= 1.0 + max(tau_val, 0.0) / float(thresh.tau_ref)
        frac = float(min(max(frac, 0.0), 1.0))
        state: Literal["solid", "vapor"] = "vapor" if frac >= 0.5 else "solid"
        diagnostics.update(
            {
                "phase_thresholds": {
                    "T_condense_K": T_cond,
                    "T_vaporize_K": T_vap,
                    "P_ref_bar": thresh.P_ref_bar,
                    "tau_ref": thresh.tau_ref,
                }
            }
        )
        return PhaseDecision(
            state=state,
            f_vap=frac,
            method="threshold",
            reason="phase.thresholds",
            used_map=False,
            payload=diagnostics,
        )


def hydro_escape_timescale(
    cfg: Optional[HydroEscapeConfig],
    temperature_K: float,
    f_vap: float,
) -> Optional[float]:
    """Return ``t_escape`` implied by the hydrodynamic escape scaling."""

    if cfg is None or not cfg.enable:
        return None
    strength = float(max(cfg.strength, 0.0))
    if strength <= 0.0 or f_vap <= 0.0:
        return None
    T_ref = float(max(cfg.T_ref_K, 1.0))
    temp_ratio = float(max(temperature_K, 1.0)) / T_ref
    try:
        temp_factor = temp_ratio ** float(cfg.temp_power)
    except (OverflowError, ValueError):  # pragma: no cover - guard degenerate input
        temp_factor = 1.0
    vapour_factor = max(float(f_vap), float(cfg.f_vap_floor))
    rate = strength * temp_factor * vapour_factor
    if rate <= 0.0:
        return None
    return 1.0 / rate


__all__ = ["PhaseEvaluator", "PhaseDecision", "hydro_escape_timescale"]
