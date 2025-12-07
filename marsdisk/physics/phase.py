"""Phase (solid/vapour) inference and hydrodynamic sink helpers."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import importlib
import logging
import math
from typing import Any, Callable, Dict, Literal, Optional, Tuple

from ..schema import (
    DEFAULT_PHASE_ENTRYPOINT,
    HydroEscapeConfig,
    PhaseConfig,
    PhaseThresholds,
)

logger = logging.getLogger(__name__)

DEFAULT_ENTRYPOINT = DEFAULT_PHASE_ENTRYPOINT


@dataclass
class PhaseDecision:
    """Return value describing the resolved phase state for one step."""

    state: Literal["solid", "vapor"]
    f_vap: float
    method: str
    reason: str
    used_map: bool
    payload: Dict[str, Any]


@dataclass
class BulkPhaseState:
    """Bulk (solid/liquid) phase descriptor used for sublimation gating."""

    state: Literal["solid_dominated", "liquid_dominated", "mixed"]
    f_liquid: float
    f_solid: float
    f_vapor: float
    method: str
    reason: str
    used_map: bool
    payload: Dict[str, Any]
    temperature_K: Optional[float] = None
    pressure_Pa: Optional[float] = None
    tau: Optional[float] = None


class PhaseEvaluator:
    """Resolve the effective phase state using maps or threshold fallbacks."""

    def __init__(self, cfg: Optional[PhaseConfig] = None, *, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._cfg = cfg
        self.enabled = bool(cfg and cfg.enabled)
        self.source = (cfg.source if cfg is not None else "threshold") if self.enabled else "disabled"
        self.thresholds = cfg.thresholds if cfg is not None else PhaseThresholds()
        self.entrypoint = self._resolve_entrypoint(cfg)
        self.extra_kwargs: Dict[str, Any] = dict(getattr(cfg, "extra_kwargs", {}) or {})
        self._lookup_func: Optional[Callable[..., Any]] = None
        self._map_error_logged = False
        if self.enabled and self.source == "map":
            try:
                self._lookup_func = self._load_entrypoint(self.entrypoint)
            except Exception as exc:
                self._map_error_logged = True
                self.logger.warning(
                    "phase: source='map' but entrypoint '%s' failed to load (%s); falling back to thresholds",
                    self.entrypoint,
                    exc,
                )
                # Degrade gracefully to threshold heuristics rather than aborting the run.
                self.source = "threshold"
                self._lookup_func = None

    @classmethod
    def from_config(
        cls,
        cfg: Optional[PhaseConfig],
        *,
        logger: Optional[logging.Logger] = None,
    ) -> "PhaseEvaluator":
        """Construct a phase evaluator from a configuration object."""

        return cls(cfg, logger=logger)

    @staticmethod
    def _resolve_entrypoint(cfg: Optional[PhaseConfig]) -> str:
        if cfg is None:
            return DEFAULT_ENTRYPOINT
        if getattr(cfg, "entrypoint", None):
            return str(cfg.entrypoint)
        map_cfg = getattr(cfg, "map", None)
        if map_cfg is not None and getattr(map_cfg, "entrypoint", None):
            return str(map_cfg.entrypoint)
        return DEFAULT_ENTRYPOINT

    @staticmethod
    def _load_entrypoint(entrypoint: Optional[str]) -> Optional[Callable[..., Any]]:
        if entrypoint is None:
            return None
        module_name, sep, func_name = str(entrypoint).partition(":")
        if not module_name or not func_name:
            raise RuntimeError(f"Invalid phase map entrypoint '{entrypoint}' (expected 'module:function')")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(f"Unable to import map module '{module_name}': {exc}") from exc
        try:
            func = getattr(module, func_name)
        except AttributeError as exc:
            raise RuntimeError(f"phase entrypoint '{entrypoint}' missing attribute '{func_name}'") from exc
        if not callable(func):
            raise RuntimeError(f"phase entrypoint '{entrypoint}' is not callable")
        return func

    def evaluate(
        self,
        temperature_K: float,
        *,
        pressure_Pa: Optional[float] = None,
        tau: Optional[float] = None,
        radius_m: Optional[float] = None,
        time_s: Optional[float] = None,
        T0_K: Optional[float] = None,
    ) -> PhaseDecision:
        decision, _ = self.evaluate_with_bulk(
            temperature_K,
            pressure_Pa=pressure_Pa,
            tau=tau,
            radius_m=radius_m,
            time_s=time_s,
            T0_K=T0_K,
        )
        return decision

    def evaluate_with_bulk(
        self,
        temperature_K: float,
        *,
        pressure_Pa: Optional[float] = None,
        tau: Optional[float] = None,
        radius_m: Optional[float] = None,
        time_s: Optional[float] = None,
        T0_K: Optional[float] = None,
    ) -> Tuple[PhaseDecision, BulkPhaseState]:
        """Return (solid/vapour decision, bulk solid/liquid state)."""

        diagnostics = self._build_diagnostics(temperature_K, pressure_Pa, tau, radius_m, time_s, T0_K)
        diagnostics_bulk = dict(diagnostics)
        pressure_clean = diagnostics["pressure_Pa"]
        tau_clean = diagnostics["tau_clamped"]

        if not self.enabled:
            decision = PhaseDecision(
                state="solid",
                f_vap=0.0,
                method="disabled",
                reason="phase.disabled",
                used_map=False,
                payload=diagnostics,
            )
            bulk = self._bulk_state_from_fraction(
                f_liquid=0.0,
                f_vapor=0.0,
                diagnostics=diagnostics_bulk,
                method="disabled",
                reason="phase.disabled",
                used_map=False,
            )
            return decision, bulk

        if self.source == "map" and self._lookup_func is not None:
            try:
                raw = self._call_map(
                    self._lookup_func,
                    temperature_K,
                    pressure_clean,
                    tau_clean,
                    radius_m=radius_m,
                    time_s=time_s,
                    T0_K=T0_K,
                )
                decision = self._parse_map_result(raw, dict(diagnostics))
                bulk = self._parse_bulk_map_result(raw, diagnostics_bulk)
                if decision is not None or bulk is not None:
                    decision_final = decision
                    if decision_final is None and bulk is not None:
                        decision_final = PhaseDecision(
                            state="vapor" if bulk.state == "liquid_dominated" else "solid",
                            f_vap=float(self._clamp_fraction(bulk.f_vapor, default=bulk.f_liquid)),
                            method="map",
                            reason="phase.map.bulk_only",
                            used_map=True,
                            payload=dict(bulk.payload),
                        )
                    if bulk is None and decision_final is not None:
                        bulk = self._bulk_state_from_fraction(
                            f_liquid=decision_final.f_vap,
                            diagnostics=diagnostics_bulk,
                            method="map",
                            reason=decision_final.reason,
                            used_map=True,
                        )
                    if decision_final is not None and bulk is not None:
                        return decision_final, bulk
            except Exception as exc:  # pragma: no cover - defensive logging
                if not self._map_error_logged:
                    self.logger.warning(
                        "phase: map evaluation failed (%s); falling back to thresholds", exc
                    )
                    self._map_error_logged = True
        elif self.source == "map" and not self._map_error_logged:
            self.logger.info("phase: map source requested but entrypoint unavailable; using thresholds")
            self._map_error_logged = True

        decision = self._threshold_decision(temperature_K, pressure_clean, tau_clean, diagnostics)
        bulk = self._bulk_state_from_fraction(
            f_liquid=decision.f_vap,
            diagnostics=diagnostics_bulk,
            method=decision.method,
            reason=decision.reason,
            used_map=False,
        )
        return decision, bulk

    def _call_map(
        self,
        func: Callable[..., Any],
        temperature_K: float,
        pressure_Pa: Optional[float],
        tau: Optional[float],
        *,
        radius_m: Optional[float] = None,
        time_s: Optional[float] = None,
        T0_K: Optional[float] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "temperature_K": temperature_K,
            "pressure_Pa": pressure_Pa,
            "tau": tau,
            "radius_m": radius_m,
            "time_s": time_s,
            "T0_K": T0_K,
        }
        kwargs.update(self.extra_kwargs)
        return self._invoke_with_signature(func, kwargs)

    @staticmethod
    def _invoke_with_signature(func: Callable[..., Any], kwargs: Dict[str, Any]) -> Any:
        signature = inspect.signature(func)
        params = signature.parameters
        accepts_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        call_kwargs: Dict[str, Any] = {}
        for name in params.keys():
            if name in kwargs:
                call_kwargs[name] = kwargs[name]
        if accepts_var_kwargs:
            for name, value in kwargs.items():
                if name not in call_kwargs:
                    call_kwargs[name] = value
        if call_kwargs:
            return func(**call_kwargs)
        if "temperature_K" in kwargs:
            return func(kwargs["temperature_K"])
        return func()

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
            f_vap = payload.get("f_vap") or payload.get("f_vapor") or payload.get("fraction")
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
            f_vap_val = self._clamp_fraction(f_vap, default=f_vap_val)
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
        """Fallback solid/vapour decision using the configured thresholds.

        The ramp between ``T_condense_K`` and ``T_vaporize_K`` is a gas-poor,
        optically-thin heuristic; pressure and optical-depth terms soften the
        transition when the disk deviates from that limit.
        """
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

    @staticmethod
    def _build_diagnostics(
        temperature_K: float,
        pressure_Pa: Optional[float],
        tau: Optional[float],
        radius_m: Optional[float],
        time_s: Optional[float],
        T0_K: Optional[float],
    ) -> Dict[str, Any]:
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
        if radius_m is not None and math.isfinite(radius_m):
            diagnostics["radius_m"] = float(radius_m)
        if time_s is not None and math.isfinite(time_s):
            diagnostics["time_s"] = float(time_s)
        if T0_K is not None and math.isfinite(T0_K):
            diagnostics["temperature_initial_K"] = float(T0_K)
        return diagnostics

    @staticmethod
    def _clamp_fraction(value: Optional[float], default: float = 0.0) -> float:
        if value is None:
            return float(default)
        try:
            val = float(value)
        except (TypeError, ValueError):
            return float(default)
        if not math.isfinite(val):
            return float(default)
        return float(min(max(val, 0.0), 1.0))

    def _bulk_state_from_fraction(
        self,
        f_liquid: float,
        *,
        diagnostics: Dict[str, Any],
        method: str,
        reason: str,
        used_map: bool,
        f_solid: Optional[float] = None,
        f_vapor: Optional[float] = None,
    ) -> BulkPhaseState:
        f_liquid_clean = self._clamp_fraction(f_liquid)
        f_solid_clean = None if f_solid is None else self._clamp_fraction(f_solid)
        f_vapor_clean = None if f_vapor is None else self._clamp_fraction(f_vapor)
        if f_solid_clean is None and f_vapor_clean is not None:
            f_solid_clean = max(0.0, 1.0 - f_liquid_clean - f_vapor_clean)
        if f_solid_clean is None:
            f_solid_clean = max(0.0, 1.0 - f_liquid_clean)
        if f_vapor_clean is None:
            f_vapor_clean = max(0.0, 1.0 - f_liquid_clean - f_solid_clean)
        total = f_liquid_clean + f_solid_clean + f_vapor_clean
        if total > 0.0 and not math.isclose(total, 1.0):
            scale = 1.0 / total
            f_liquid_clean *= scale
            f_solid_clean *= scale
            f_vapor_clean *= scale
        if total <= 0.0:
            f_liquid_clean = 0.0
            f_solid_clean = 1.0
            f_vapor_clean = 0.0
        if f_liquid_clean >= 0.95:
            state: Literal["solid_dominated", "liquid_dominated", "mixed"] = "liquid_dominated"
        elif f_liquid_clean <= 0.05:
            state = "solid_dominated"
        else:
            state = "mixed"
        return BulkPhaseState(
            state=state,
            f_liquid=f_liquid_clean,
            f_solid=f_solid_clean,
            f_vapor=f_vapor_clean,
            method=method,
            reason=reason,
            used_map=used_map,
            payload=diagnostics,
            temperature_K=diagnostics.get("temperature_K"),
            pressure_Pa=diagnostics.get("pressure_Pa"),
            tau=diagnostics.get("tau_clamped"),
        )

    def _parse_bulk_map_result(
        self,
        payload: Any,
        diagnostics: Dict[str, Any],
    ) -> Optional[BulkPhaseState]:
        state_raw: Optional[str] = None
        f_liquid_raw: Optional[float] = None
        f_solid_raw: Optional[float] = None
        f_vapor_raw: Optional[float] = None
        reason = "phase.map"

        if isinstance(payload, dict):
            diagnostics.update({k: v for k, v in payload.items() if k not in diagnostics})
            state_raw = payload.get("state") or payload.get("phase_state")
            f_liquid_raw = payload.get("f_liquid")
            f_solid_raw = payload.get("f_solid")
            f_vapor_raw = payload.get("f_vapor")
            frac_raw = payload.get("f_vap") or payload.get("fraction")
            if f_liquid_raw is None and frac_raw is not None:
                f_liquid_raw = frac_raw
            if f_vapor_raw is None and frac_raw is not None:
                f_vapor_raw = frac_raw
        elif isinstance(payload, (list, tuple)) and payload:
            state_raw = payload[0]
            if len(payload) > 1:
                try:
                    f_liquid_raw = float(payload[1])
                except (TypeError, ValueError):
                    f_liquid_raw = None
        elif isinstance(payload, str):
            state_raw = payload

        def _maybe_float(value: Optional[float]) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        f_liquid_val: Optional[float] = _maybe_float(f_liquid_raw)
        f_solid_val: Optional[float] = _maybe_float(f_solid_raw)
        f_vapor_val: Optional[float] = _maybe_float(f_vapor_raw)

        state_norm = state_raw.lower().strip() if isinstance(state_raw, str) else None
        liquids = {"liquid", "vapor", "vapour", "molten", "liquidus", "liquid_dominated"}
        solids = {"solid", "glass", "solidus", "solid_dominated"}
        mixed = {"mixed", "blend", "partial", "partially_molten"}

        if f_liquid_val is None and f_solid_val is None and f_vapor_val is None:
            if state_norm in liquids:
                f_liquid_val, f_solid_val = 1.0, 0.0
            elif state_norm in solids:
                f_liquid_val, f_solid_val = 0.0, 1.0
            elif state_norm in mixed:
                f_liquid_val, f_solid_val = 0.5, 0.5

        if f_vapor_val is not None:
            f_vapor_val = self._clamp_fraction(f_vapor_val)
        if f_liquid_val is not None:
            f_liquid_val = self._clamp_fraction(f_liquid_val)
        if f_solid_val is not None:
            f_solid_val = self._clamp_fraction(f_solid_val)

        if f_liquid_val is None and f_vapor_val is not None:
            condensed = max(0.0, 1.0 - f_vapor_val)
            if state_norm in liquids:
                f_liquid_val, f_solid_val = condensed, f_solid_val or 0.0
            elif state_norm in solids:
                f_liquid_val, f_solid_val = 0.0, condensed
            elif state_norm in mixed:
                f_liquid_val = 0.5 * condensed
                f_solid_val = 0.5 * condensed

        if f_liquid_val is None and f_solid_val is not None:
            f_liquid_val = 1.0 - f_solid_val
        if f_solid_val is None and f_liquid_val is not None and f_vapor_val is not None:
            f_solid_val = max(0.0, 1.0 - f_liquid_val - f_vapor_val)
        if f_solid_val is None and f_liquid_val is not None:
            f_solid_val = 1.0 - f_liquid_val

        if state_norm in liquids and f_liquid_val is None:
            f_liquid_val, f_solid_val = 1.0, 0.0
        elif state_norm in solids and f_liquid_val is None:
            f_liquid_val, f_solid_val = 0.0, 1.0
        elif state_norm in mixed and f_liquid_val is None:
            f_liquid_val, f_solid_val = 0.5, 0.5

        if f_liquid_val is None:
            return None

        return self._bulk_state_from_fraction(
            f_liquid=float(f_liquid_val),
            f_solid=f_solid_val,
            f_vapor=f_vapor_val,
            diagnostics=diagnostics,
            method="map",
            reason=reason,
            used_map=True,
        )


def hydro_escape_timescale(
    cfg: Optional[HydroEscapeConfig],
    temperature_K: float,
    f_vap: float,
) -> Optional[float]:
    """Return ``t_escape`` implied by the hydrodynamic escape scaling.

    ``strength`` acts as the reference escape rate at ``T_ref_K`` for
    ``f_vap≈1``, so it can be calibrated to match a target orbital-loss
    fraction or scale-height assumption before toggling the sink on.  The
    scaling is deliberately 0D; callers choose the representative radius/
    layer when setting ``strength``.
    """

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


__all__ = ["PhaseEvaluator", "PhaseDecision", "BulkPhaseState", "hydro_escape_timescale"]
