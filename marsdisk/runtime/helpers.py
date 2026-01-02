"""Shared helper functions for runtime geometry and gating."""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence, Tuple

import numpy as np


def compute_phase_tau_fields(
    kappa_surf: float,
    sigma_for_tau: float,
    los_factor: float,
    phase_tau_field: str,
) -> Tuple[float, float]:
    """Return (τ_used, τ_los) for phase evaluation (LOS-only)."""

    tau_los = float(kappa_surf * sigma_for_tau * los_factor)
    tau_los = float(tau_los) if math.isfinite(tau_los) else 0.0
    tau_used = tau_los
    return tau_used, tau_los


def resolve_feedback_tau_field(tau_field: Optional[str]) -> str:
    """Normalise feedback.tau_field and reject unknown values."""

    if tau_field is None:
        return "tau_los"
    text = str(tau_field).strip().lower()
    if text in {"tau_los", "los"}:
        return "tau_los"
    raise ValueError(
        f"Unknown supply.feedback.tau_field={tau_field!r}; expected 'tau_los'"
    )


def resolve_los_factor(los_geom: Optional[object]) -> float:
    """Return the multiplicative factor f_los scaling tau_vert to tau_los."""

    if los_geom is None:
        return 1.0
    mode = getattr(los_geom, "mode", "aspect_ratio_factor")
    if mode == "none":
        return 1.0
    h_over_r = float(getattr(los_geom, "h_over_r", 1.0) or 1.0)
    path_multiplier = float(getattr(los_geom, "path_multiplier", 1.0) or 1.0)
    if h_over_r <= 0.0 or path_multiplier <= 0.0:
        return 1.0
    factor = path_multiplier / h_over_r
    return float(factor if factor > 1.0 else 1.0)


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


def fast_blowout_correction_factor(ratio: float) -> float:
    """Return the effective loss fraction ``f_fast = 1 - exp(-dt/t_blow)``."""

    if ratio <= 0.0 or math.isinf(ratio):
        return 0.0 if ratio <= 0.0 else 1.0
    value = -math.expm1(-ratio)
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def auto_chi_blow(beta: float, qpr: float) -> float:
    """Return an automatic chi_blow scaling based on beta and Q_pr."""

    if not math.isfinite(beta) or beta <= 0.0:
        beta = 0.5
    if not math.isfinite(qpr) or qpr <= 0.0:
        qpr = 1.0
    beta_ratio = beta / 0.5
    chi_beta = 1.0 / (1.0 + 0.5 * (beta_ratio - 1.0))
    chi_beta = max(0.1, chi_beta)
    chi_qpr = min(max(qpr, 0.5), 1.5)
    chi = chi_beta * chi_qpr
    return float(min(max(chi, 0.5), 2.0))


def series_stats(values: Sequence[float]) -> tuple[float, float, float]:
    """Return min/median/max for finite values (or NaNs if empty)."""

    if not values:
        nan = float("nan")
        return nan, nan, nan
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        nan = float("nan")
        return nan, nan, nan
    return float(np.min(arr)), float(np.median(arr)), float(np.max(arr))


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
    "resolve_los_factor",
    "compute_gate_factor",
    "fast_blowout_correction_factor",
    "auto_chi_blow",
    "series_stats",
    "ensure_finite_kappa",
    "safe_float",
    "float_or_nan",
    "format_exception_short",
    "log_stage",
]
