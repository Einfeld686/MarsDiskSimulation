"""Shared helper functions for runtime geometry and gating."""
from __future__ import annotations

import math
from typing import Any, Optional, Tuple


def compute_phase_tau_fields(
    kappa_surf: float,
    sigma_for_tau: float,
    los_factor: float,
    phase_tau_field: str,
) -> Tuple[float, float, float]:
    """Return (τ_used, τ_vertical, τ_los) for phase evaluation."""

    tau_vertical = float(kappa_surf * sigma_for_tau)
    tau_los = tau_vertical * los_factor
    tau_los = float(tau_los) if math.isfinite(tau_los) else 0.0
    tau_field_norm = "los" if phase_tau_field == "los" else "vertical"
    tau_used = tau_los if tau_field_norm == "los" else tau_vertical
    return tau_used, tau_vertical, tau_los


def resolve_feedback_tau_field(tau_field: Optional[str]) -> str:
    """Normalise feedback.tau_field and reject unknown values."""

    if tau_field is None:
        return "tau_vertical"
    text = str(tau_field).strip().lower()
    if text in {"tau_vertical", "vertical"}:
        return "tau_vertical"
    if text in {"tau_los", "los"}:
        return "tau_los"
    raise ValueError(
        f"Unknown supply.feedback.tau_field={tau_field!r}; expected 'tau_vertical' or 'tau_los'"
    )


def compute_gate_factor(t_blow: Optional[float], t_solid: Optional[float]) -> float:
    """Return gate coefficient f_gate=t_solid/(t_solid+t_blow) clipped to [0,1]."""

    if t_blow is None or t_solid is None:
        return 1.0
    try:
        t_blow_val = float(t_blow)
        t_solid_val = float(t_solid)
    except (TypeError, ValueError):
        return 1.0
    if not (math.isfinite(t_blow_val) and math.isfinite(t_solid_val)):
        return 1.0
    if t_blow_val <= 0.0 or t_solid_val <= 0.0:
        return 1.0
    factor = t_solid_val / (t_solid_val + t_blow_val)
    if factor < 0.0:
        return 0.0
    if factor > 1.0:
        return 1.0
    return factor


def ensure_finite_kappa(kappa: Any, *, label: str | None = None) -> float:
    """Return finite, non-negative kappa; replace NaN/inf/negative with 0."""

    name = label or "kappa"
    try:
        val = float(kappa)
    except Exception:
        return 0.0
    if not math.isfinite(val) or val < 0.0:
        return 0.0
    return val


def safe_float(value: Any, default: float = 0.0) -> float:
    """Return float(value) or default if conversion fails or is non-finite."""

    try:
        val = float(value)
    except Exception:
        return default
    if not math.isfinite(val):
        return default
    return val


def float_or_nan(value: Any) -> float:
    """Return float(value) or NaN if conversion fails or is non-finite."""

    try:
        val = float(value)
    except Exception:
        return math.nan
    return val if math.isfinite(val) else math.nan


def format_exception_short(exc: BaseException) -> str:
    """Return a concise exception string."""

    name = exc.__class__.__name__
    return f"{name}: {exc}"


def log_stage(logger_obj, label: str, *, extra: dict | None = None) -> None:
    """Lightweight stage logger wrapper."""

    if logger_obj is None:
        return
    if extra:
        logger_obj.info("stage=%s %s", label, extra)
    else:
        logger_obj.info("stage=%s", label)


__all__ = [
    "compute_phase_tau_fields",
    "resolve_feedback_tau_field",
    "compute_gate_factor",
    "ensure_finite_kappa",
    "safe_float",
    "float_or_nan",
    "format_exception_short",
    "log_stage",
]
