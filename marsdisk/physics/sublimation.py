"""Sublimation utilities based on the Hertz–Knudsen–Langmuir law.

This module provides tools to estimate sublimation mass fluxes and the
corresponding instantaneous-sink size for dust grains.  When saturation
vapour pressure data are unavailable a logistic placeholder is used as a
smooth approximation, allowing the interface to remain stable until
proper tables are supplied.  Grain temperatures feeding the HKL flux
use :func:`radiation.grain_temperature_graybody`, i.e. the Hyodo et al.
(2018) Lambertian equilibrium (E.043). [@Hyodo2018_ApJ860_150]
"""
from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, NamedTuple, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

from .. import constants
from ..errors import PhysicsError, TableLoadError
from .radiation import grain_temperature_graybody

logger = logging.getLogger(__name__)

__all__ = [
    "SublimationParams",
    "p_sat_clausius",
    "p_sat_tabulated",
    "p_sat",
    "choose_psat_backend",
    "mass_flux_hkl",
    "s_sink_from_timescale",
    "grain_temperature_graybody",
    "sublimation_sink_from_dsdt",
]

PSAT_TABLE_BUFFER_DEFAULT_K = 75.0
PSAT_LOCAL_FIT_WINDOW_DEFAULT_K = 300.0
PSAT_LOCAL_FIT_MIN_POINTS = 3
PSAT_VALIDITY_WARNING_MARGIN_K = 200.0


class PsatSelection(NamedTuple):
    model: str
    evaluator: Callable[[float], float]
    metadata: Dict[str, Any]


@dataclass
class SublimationParams:
    r"""Parameters governing sublimation calculations.

    Parameters
    ----------
    mode:
        ``"hkl"`` to evaluate the full Hertz–Knudsen–Langmuir expression
        using saturation vapour pressure.  Any other value activates the
        logistic placeholder.
    psat_model:
        Saturation vapour pressure source.  ``"auto"`` prefers tabulated
        datasets when available, falling back to local Clausius fits or the
        baseline coefficients.  ``"clausius"`` enforces the analytic form,
        whereas ``"tabulated"`` strictly uses the table.
    alpha_evap:
        Evaporation coefficient :math:`\alpha` (0 < ``alpha_evap`` \le 1).
    mu:
        Molar mass in kg/mol.
    A, B:
        Clausius–Clapeyron coefficients such that
        ``log10(P_sat/Pa) = A - B/T``.
    valid_K:
        Temperature validity domain in Kelvin.  Temperatures outside this range
        trigger a :func:`logging.warning` but calculations proceed.
    psat_table_path:
        Optional path to a CSV/JSON table with columns ``T[K]`` and
        ``log10P[Pa]`` used when ``psat_model="tabulated"``.
    psat_table_buffer_K:
        Temperature padding around the tabulated domain that still triggers
        a local Clausius fit when ``psat_model="auto"``.
    local_fit_window_K:
        Half-width of the temperature window (Kelvin) used for local least
        squares Clausius fits.
    min_points_local_fit:
        Minimum number of table samples required for a local Clausius fit.
    T_sub:
        Nominal sublimation threshold for the logistic placeholder (K).
    s_ref:
        Reference size used to calibrate the placeholder (m).
    eta_instant:
        Fraction defining the "instantaneous" criterion.
    dT:
        Temperature width controlling the steepness of the logistic model.
    P_gas:
        Ambient vapour pressure (Pa); defaults to vacuum.
    """

    mode: str = "logistic"
    psat_model: str = "auto"
    alpha_evap: float = 0.007
    mu: float = 0.0440849
    A: Optional[float] = 13.613
    B: Optional[float] = 17850.0
    valid_K: Optional[Tuple[float, float]] = (1270.0, 1600.0)
    enable_liquid_branch: bool = True
    psat_liquid_switch_K: Optional[float] = 1900.0
    A_liq: Optional[float] = 13.203
    B_liq: Optional[float] = 25898.9
    valid_liquid_K: Optional[Tuple[float, float]] = (1900.0, 3500.0)
    psat_table_path: Optional[Path] = None
    psat_table_buffer_K: float = PSAT_TABLE_BUFFER_DEFAULT_K
    local_fit_window_K: float = PSAT_LOCAL_FIT_WINDOW_DEFAULT_K
    min_points_local_fit: int = PSAT_LOCAL_FIT_MIN_POINTS
    psat_cache_tol_K: float = 0.0
    T_sub: float = 1300.0
    s_ref: float = 1e-6
    eta_instant: float = 0.1
    dT: float = 50.0
    P_gas: float = 0.0
    mass_conserving: bool = False
    _psat_interp: Optional[Callable[[float], float]] = field(default=None, init=False, repr=False)
    _psat_table_T: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _psat_table_log10P: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _psat_table_monotonic: Optional[bool] = field(default=None, init=False, repr=False)
    psat_model_resolved: Optional[str] = field(default=None, init=False, repr=False)
    psat_selection_reason: Optional[str] = field(default=None, init=False, repr=False)
    _psat_last_selection: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _psat_last_T: Optional[float] = field(default=None, init=False, repr=False)
    _psat_last_log10P: Optional[float] = field(default=None, init=False, repr=False)
    _psat_last_P: Optional[float] = field(default=None, init=False, repr=False)


def _is_hkl_active(params: SublimationParams) -> bool:
    mode = params.mode.lower()
    if mode not in {"hkl", "hkl_timescale"}:
        return False
    psat_model = params.psat_model.lower()
    if psat_model == "clausius":
        has_solid = params.A is not None and params.B is not None
        has_liquid = (
            params.enable_liquid_branch
            and params.A_liq is not None
            and params.B_liq is not None
        )
        return has_solid or has_liquid
    if psat_model == "tabulated":
        return params.psat_table_path is not None or params._psat_interp is not None
    if psat_model == "auto":
        has_table = params.psat_table_path is not None or params._psat_interp is not None
        has_clausius = (params.A is not None and params.B is not None) or (
            params.enable_liquid_branch and params.A_liq is not None and params.B_liq is not None
        )
        return has_table or has_clausius
    return False


def _resolve_clausius_branch(
    T: float, params: SublimationParams
) -> Tuple[str, Optional[float], Optional[float], Optional[Tuple[float, float]]]:
    """Return the active Clausius branch (solid/liquid) and coefficients."""

    branch = "solid"
    A = params.A
    B = params.B
    valid = params.valid_K

    if (
        params.enable_liquid_branch
        and params.psat_liquid_switch_K is not None
        and T >= float(params.psat_liquid_switch_K)
        and params.A_liq is not None
        and params.B_liq is not None
    ):
        branch = "liquid"
        A = params.A_liq
        B = params.B_liq
        valid = params.valid_liquid_K or params.valid_K

    return branch, A, B, valid


def p_sat_clausius(
    T: float,
    params: SublimationParams,
    *,
    A_override: Optional[float] = None,
    B_override: Optional[float] = None,
) -> float:
    """Return the saturation vapour pressure ``P_sat`` in Pascals.

    The relation ``log10(P_sat / Pa) = A - B / T`` is used (Kubaschewski 1974),
    assuming ``T`` in Kelvin and returning ``P_sat`` in Pascal.  Missing
    coefficients raise :class:`ValueError`.
    """

    A = params.A if A_override is None else A_override
    B = params.B if B_override is None else B_override
    if not np.isfinite(T) or T <= 0.0:
        raise PhysicsError("temperature must be positive for Clausius P_sat")
    if A is None or B is None:
        raise PhysicsError("Clausius–Clapeyron coefficients A and B must be provided")
    return 10.0 ** (A - B / float(T))


def _load_psat_table(params: SublimationParams) -> Callable[[float], float]:
    """Return an interpolator for log10 P_sat based on a tabulated dataset."""

    if params.psat_table_path is None:
        raise PhysicsError("psat_table_path must be provided when psat_model='tabulated'")

    path = Path(params.psat_table_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"psat table {path} does not exist")
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        df = pd.read_csv(path)
    elif suffix in {".json"}:
        df = pd.read_json(path)
    else:
        raise TableLoadError(f"Unsupported psat table format: '{suffix}'")

    rename_map = {"T[K]": "T", "log10P[Pa]": "log10P"}
    df = df.rename(columns=rename_map)
    required = {"T", "log10P"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise TableLoadError(f"psat table missing required columns: {names}")

    work = df[["T", "log10P"]].copy()
    work["T"] = pd.to_numeric(work["T"], errors="coerce")
    work["log10P"] = pd.to_numeric(work["log10P"], errors="coerce")
    if work.isna().any().any():
        raise TableLoadError("psat table contains non-numeric entries")
    if (work["T"] <= 0.0).any():
        raise TableLoadError("psat table temperatures must be positive")

    work = work.drop_duplicates(subset="T").sort_values("T")
    if len(work) < 2:
        raise TableLoadError("psat table requires at least two unique temperature samples")

    T_vals = work["T"].to_numpy(dtype=float)
    log_vals = work["log10P"].to_numpy(dtype=float)
    if not np.all(np.isfinite(log_vals)):
        raise TableLoadError("psat table contains non-finite log10P values")
    if not np.all(np.diff(T_vals) > 0.0):
        raise TableLoadError("psat table temperatures must be strictly increasing")

    params._psat_interp = PchipInterpolator(T_vals, log_vals, extrapolate=False)
    params._psat_table_T = T_vals.copy()
    params._psat_table_log10P = log_vals.copy()
    if len(T_vals) > 1:
        slopes = np.diff(log_vals) / np.diff(T_vals)
        monotonic = bool(np.all(slopes > 0.0))
    else:
        monotonic = True
    params._psat_table_monotonic = monotonic
    if not monotonic:
        logger.warning(
            "psat table '%s' exhibits non-monotonic log10P(T); auto-selection may fall back to Clausius fits.",
            path,
        )
    if params.valid_K in {(1270.0, 1600.0), None}:
        params.valid_K = (float(T_vals[0]), float(T_vals[-1]))
    return params._psat_interp


def _get_table_info(
    params: SublimationParams, *, raise_on_error: bool
) -> Optional[Dict[str, Any]]:
    """Return cached table information, optionally raising on load failures."""

    if params._psat_interp is None or params._psat_table_T is None:
        if params.psat_table_path is None:
            if raise_on_error:
                raise PhysicsError("psat_table_path must be provided for tabulated model")
            return None
        if raise_on_error:
            interp = _load_psat_table(params)
        else:
            try:
                interp = _load_psat_table(params)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to load psat table '%s': %s; falling back to Clausius coefficients.",
                    params.psat_table_path,
                    exc,
                )
                return None
        if params._psat_interp is None:
            params._psat_interp = interp

    if params._psat_table_T is None or params._psat_table_log10P is None:
        return None

    path = str(params.psat_table_path) if params.psat_table_path else None
    return {
        "T_vals": params._psat_table_T,
        "log10P_vals": params._psat_table_log10P,
        "path": path,
        "monotonic": bool(params._psat_table_monotonic)
        if params._psat_table_monotonic is not None
        else True,
    }


def _local_clausius_fit_selection(
    T_req: float,
    params: SublimationParams,
    table_info: Dict[str, Any],
) -> Optional[PsatSelection]:
    """Return a local Clausius fit selection when sufficient table data exist."""

    T_vals = np.asarray(table_info["T_vals"], dtype=float)
    log_vals = np.asarray(table_info["log10P_vals"], dtype=float)
    if T_vals.size < 2:
        return None

    window = abs(float(params.local_fit_window_K)) or PSAT_LOCAL_FIT_WINDOW_DEFAULT_K
    min_points = max(int(params.min_points_local_fit), 2)
    Tmin = float(T_vals[0])
    Tmax = float(T_vals[-1])
    center = float(np.clip(T_req, Tmin, Tmax))

    mask = np.abs(T_vals - center) <= window
    idx = np.where(mask)[0]
    if idx.size < min_points:
        order = np.argsort(np.abs(T_vals - center))
        idx = np.unique(np.sort(order[: min(T_vals.size, max(min_points, 2))]))
    if idx.size < 2:
        return None

    T_sel = T_vals[idx]
    log_sel = log_vals[idx]
    x = 1.0 / T_sel

    design = np.vstack([np.ones_like(x), x]).T
    try:
        coeff, *_ = np.linalg.lstsq(design, log_sel, rcond=None)
    except np.linalg.LinAlgError:  # pragma: no cover - defensive
        return None

    A_fit = float(coeff[0])
    B_fit = float(-coeff[1])
    if not math.isfinite(A_fit) or not math.isfinite(B_fit):
        return None
    if B_fit <= 0.0:
        logger.warning(
            "psat auto: local Clausius fit produced non-positive B=%.3f; rejecting fit.",
            B_fit,
        )
        return None

    residuals = log_sel - (A_fit - B_fit / T_sel)
    rms = float(np.sqrt(np.mean(residuals**2))) if residuals.size else 0.0
    metadata: Dict[str, Any] = {
        "selection_reason": "local Clausius fit around requested temperature",
        "fit_window_K": float(window),
        "fit_T_center": float(center),
        "n_points": int(len(T_sel)),
        "A_active": A_fit,
        "B_active": B_fit,
        "rms_log10P": rms,
        "psat_table_path": table_info.get("path"),
        "psat_table_range_K": (float(Tmin), float(Tmax)),
        "valid_K_active": (float(T_sel.min()), float(T_sel.max())),
        "psat_branch": "clausius_local_fit",
    }

    def evaluator(T: float) -> float:
        return 10.0 ** (A_fit - B_fit / float(T))

    return PsatSelection("clausius(local-fit)", evaluator, metadata)


def _baseline_clausius_selection(
    params: SublimationParams,
    reason: str,
    *,
    model_name: str = "clausius(baseline)",
    A_override: Optional[float] = None,
    B_override: Optional[float] = None,
    valid_override: Optional[Tuple[float, float]] = None,
    branch: Optional[str] = None,
) -> PsatSelection:
    """Return a baseline Clausius selection using the configured coefficients."""

    A_active = params.A if A_override is None else A_override
    B_active = params.B if B_override is None else B_override
    valid_range = valid_override if valid_override is not None else params.valid_K

    if A_active is None or B_active is None:
        raise PhysicsError(
            "Clausius coefficients (A, B) must be provided for baseline sublimation calculations"
        )

    metadata: Dict[str, Any] = {
        "selection_reason": reason,
        "A_active": float(A_active),
        "B_active": float(B_active),
        "psat_table_path": str(params.psat_table_path) if params.psat_table_path else None,
        "psat_table_range_K": None,
        "valid_K_active": (tuple(float(x) for x in valid_range) if valid_range is not None else None),
        "psat_branch": branch or "solid",
    }

    def evaluator(T: float) -> float:
        return p_sat_clausius(T, params, A_override=A_active, B_override=B_active)

    return PsatSelection(model_name, evaluator, metadata)


def p_sat_tabulated(T: float, params: SublimationParams) -> float:
    r"""Return ``P_sat`` (Pa) from a tabulated :math:`\log_{10} P` dataset."""

    info = _get_table_info(params, raise_on_error=True)
    if info is None:
        raise PhysicsError("psat table is required but not available")

    interp = params._psat_interp
    if interp is None:
        raise PhysicsError("psat table interpolator not initialised")

    log10P = float(interp(T))
    if not np.isfinite(log10P):
        raise PhysicsError(f"P_sat interpolation failed at T={T} K")
    return 10.0 ** log10P


def choose_psat_backend(
    T_req: float,
    params: SublimationParams,
    table_meta: Optional[Dict[str, Any]] = None,
) -> PsatSelection:
    """Resolve the saturation pressure backend according to configuration and data."""

    model = params.psat_model.lower()

    if model == "auto":
        info = table_meta if table_meta is not None else _get_table_info(params, raise_on_error=False)
        if info is not None:
            Tmin = float(info["T_vals"][0])
            Tmax = float(info["T_vals"][-1])
            monotonic = bool(info.get("monotonic", True))
            buffer = abs(float(params.psat_table_buffer_K)) or PSAT_TABLE_BUFFER_DEFAULT_K
            # Prefer direct interpolation when within the tabulated range
            if Tmin <= T_req <= Tmax and params._psat_interp is not None:
                log10P = float(params._psat_interp(T_req))
                metadata: Dict[str, Any] = {
                    "selection_reason": "tabulated dataset covers requested temperature",
                    "psat_table_path": info.get("path"),
                    "psat_table_range_K": (Tmin, Tmax),
                    "valid_K_active": (
                        tuple(float(x) for x in params.valid_K)
                        if params.valid_K is not None
                        else (Tmin, Tmax)
                    ),
                    "monotonic": monotonic,
                    "A_active": None,
                    "B_active": None,
                    "psat_branch": "tabulated",
                    "log10P_tabulated": log10P,
                }
                if not monotonic:
                    logger.warning(
                        "psat table '%s' is non-monotonic; consider revising the dataset or supplying Clausius coefficients.",
                        info.get("path"),
                    )

                def evaluator(T: float) -> float:
                    return p_sat_tabulated(T, params)

                return PsatSelection("tabulated", evaluator, metadata)

            selection = _local_clausius_fit_selection(T_req, params, info)
            if selection is not None:
                selection.metadata.setdefault(
                    "selection_reason",
                    "temperature outside tabulated range; applied local Clausius fit",
                )
                fit_center = selection.metadata.get("fit_T_center", Tmin)
                delta = abs(float(T_req) - float(fit_center))
                selection.metadata["delta_extrapolation_K"] = float(delta)
                if delta > buffer:
                    selection.metadata["extrapolation_exceeds_buffer"] = True
                    logger.info(
                        "psat auto: requested temperature %.1f K is %.0f K away from tabulated support; using local Clausius fit.",
                        T_req,
                        delta,
                    )
                return selection
            logger.warning(
                "psat auto: insufficient samples around %.1f K for a local Clausius fit (table range %.1f–%.1f K).",
                T_req,
                Tmin,
                Tmax,
            )

        branch, A_active, B_active, valid_range = _resolve_clausius_branch(T_req, params)
        return _baseline_clausius_selection(
            params,
            "auto fallback to Clausius baseline",
            A_override=A_active,
            B_override=B_active,
            valid_override=valid_range,
            branch=branch,
        )

    if model == "tabulated":
        info = table_meta if table_meta is not None else _get_table_info(params, raise_on_error=True)
        if info is None or params._psat_interp is None:
            raise PhysicsError("psat model 'tabulated' requires a valid dataset")
        Tmin = float(info["T_vals"][0])
        Tmax = float(info["T_vals"][-1])
        monotonic = bool(info.get("monotonic", True))
        metadata: Dict[str, Any] = {
            "selection_reason": "explicit tabulated psat_model",
            "psat_table_path": info.get("path"),
            "psat_table_range_K": (Tmin, Tmax),
            "valid_K_active": (
                tuple(float(x) for x in params.valid_K)
                if params.valid_K is not None
                else (Tmin, Tmax)
            ),
            "monotonic": monotonic,
            "A_active": None,
            "B_active": None,
            "psat_branch": "tabulated",
        }
        if not monotonic:
            logger.warning(
                "psat table '%s' is non-monotonic; HKL fluxes may be unreliable.",
                info.get("path"),
            )

        def evaluator(T: float) -> float:
            return p_sat_tabulated(T, params)

        return PsatSelection("tabulated", evaluator, metadata)

    if model == "clausius":
        branch, A_active, B_active, valid_range = _resolve_clausius_branch(T_req, params)
        return _baseline_clausius_selection(
            params,
            "psat_model='clausius'",
            model_name="clausius",
            A_override=A_active,
            B_override=B_active,
            valid_override=valid_range,
            branch=branch,
        )

    raise PhysicsError(f"Unrecognised psat_model '{params.psat_model}'")


def _store_psat_selection(
    params: SublimationParams, selection: PsatSelection, T_req: float, P_value: float
) -> None:
    """Persist selection metadata on ``params`` for provenance."""

    log10P = float("-inf")
    if P_value > 0.0:
        try:
            log10P = math.log10(P_value)
        except ValueError:  # pragma: no cover - defensive
            log10P = float("-inf")

    metadata = dict(selection.metadata)
    metadata.update(
        {
            "psat_model_resolved": selection.model,
            "T_req": float(T_req),
            "P_sat_Pa": float(P_value),
            "log10P": log10P,
        }
    )
    metadata.setdefault("psat_branch", "solid")
    params.psat_model_resolved = selection.model
    params.psat_selection_reason = metadata.get("selection_reason")
    params._psat_last_selection = metadata
    params._psat_last_T = float(T_req)
    params._psat_last_log10P = log10P
    params._psat_last_P = float(P_value)


def p_sat(T: float, params: SublimationParams) -> float:
    """Return the saturation vapour pressure according to the selected model."""

    tol = max(float(getattr(params, "psat_cache_tol_K", 0.0) or 0.0), 0.0)
    last_T = getattr(params, "_psat_last_T", None)
    last_P = getattr(params, "_psat_last_P", None)
    if last_T is not None and last_P is not None:
        if (tol == 0.0 and float(T) == float(last_T)) or (
            tol > 0.0 and abs(float(T) - float(last_T)) <= tol
        ):
            return float(last_P)

    selection = choose_psat_backend(T, params)
    P_value = selection.evaluator(T)
    _store_psat_selection(params, selection, T, P_value)
    return P_value


def mass_flux_hkl(T: float, params: SublimationParams) -> float:
    """Return the sublimation mass flux ``J(T)`` in kg m^-2 s^-1. [@Pignatale2018_ApJ853_118]

    If ``params.mode`` is ``"hkl"`` *and* Clausius–Clapeyron coefficients
    are supplied, the Hertz–Knudsen–Langmuir expression is used:

    ``J = α (P_sat - P_gas) * sqrt( μ / (2π R T) )``.

    Otherwise a logistic placeholder ``J = exp((T - T_sub)/dT)`` is returned,
    providing a monotonic and differentiable approximation suitable for
    testing.
    """

    if not np.isfinite(T) or T <= 0.0:
        raise PhysicsError("temperature must be positive for sublimation flux")
    use_hkl = _is_hkl_active(params)
    branch, A_active, B_active, valid_range = _resolve_clausius_branch(T, params)
    validity_status: Optional[str] = None
    validity_direction: Optional[str] = None
    validity_delta: Optional[float] = None
    if use_hkl and valid_range is not None:
        T_valid_low, T_valid_high = valid_range
        validity_status = "within"
        if T < T_valid_low:
            validity_status = "below"
            validity_direction = "below"
            validity_delta = T_valid_low - T
        elif T > T_valid_high:
            validity_status = "above"
            validity_direction = "above"
            validity_delta = T - T_valid_high

    if use_hkl:
        P_sat = p_sat(T, params)
        P_ex = max(0.0, P_sat - params.P_gas)
        if P_ex <= 0.0:
            return 0.0
        if params.mu <= 0.0:
            raise PhysicsError("molar mass mu must be positive")
        # Hertz–Knudsen–Langmuir: P in Pa, T in K, μ in kg/mol, R_GAS in J mol^-1 K^-1.
        root = math.sqrt(params.mu / (2.0 * math.pi * constants.R_GAS * T))
        meta = getattr(params, "_psat_last_selection", None)
        if meta is not None:
            meta.setdefault(
                "valid_K_config",
                list(params.valid_K) if params.valid_K is not None else None,
            )
            meta["psat_validity_status"] = validity_status
            meta["psat_validity_direction"] = validity_direction
            meta["psat_validity_delta_K"] = float(validity_delta) if validity_delta is not None else None
            meta["psat_branch"] = meta.get("psat_branch", branch)
            meta["valid_K_active"] = (
                tuple(float(x) for x in valid_range) if valid_range is not None else None
            )
        return params.alpha_evap * P_ex * root

    # logistic placeholder: J0 * exp((T - T_sub)/dT)
    J0 = 1.0
    return J0 * math.exp((T - params.T_sub) / max(params.dT, 1.0))


def s_sink_from_timescale(
    T: float, rho: float, t_ref: float, params: SublimationParams
) -> float:
    r"""Return the instantaneous-sink size :math:`s_{\rm sink}`. [@Ronnet2016_ApJ828_109]

    The sublimation lifetime of a spherical grain of radius ``s`` is
    ``t_sub = ρ s / J(T)``.  Requiring ``t_sub \le η t_ref`` yields the
    expression ``s_sink = η t_ref J(T) / ρ`` implemented here.
    """

    if rho <= 0.0 or t_ref <= 0.0:
        raise PhysicsError("rho and t_ref must be positive")
    J = mass_flux_hkl(T, params)
    if J <= 0.0:
        return 0.0
    return params.eta_instant * t_ref * J / rho


def sublimation_sink_from_dsdt(
    s_grid_m: np.ndarray,
    N_k: np.ndarray,
    ds_dt_k: np.ndarray | float,
    m_k: np.ndarray,
) -> tuple[np.ndarray, float]:
    r"""Return per-bin sublimation sinks and the associated mass loss rate.

    The helper converts size-drift rates ``ds/dt`` into number-density sinks
    ``S_sub_k`` (1/s) for the Smoluchowski operator and the corresponding
    mass-loss rate per unit area.

    Notes
    -----
    Future extension: redistribute the eroded mass into smaller bins via a
    dedicated ``Y_sub`` matrix instead of removing it from the system.
    """

    s_arr = np.asarray(s_grid_m, dtype=float)
    N_arr = np.asarray(N_k, dtype=float)
    m_arr = np.asarray(m_k, dtype=float)
    if not (s_arr.shape == N_arr.shape == m_arr.shape):
        raise PhysicsError("s_grid_m, N_k and m_k must have identical shapes")
    if s_arr.ndim != 1:
        raise PhysicsError("inputs must be one-dimensional")

    S_sub = np.zeros_like(s_arr, dtype=float)
    if np.isscalar(ds_dt_k):
        ds_dt_val = float(ds_dt_k)
        if np.isfinite(ds_dt_val) and ds_dt_val < 0.0:
            mask = s_arr > 0.0
            if np.any(mask):
                with np.errstate(divide="ignore", invalid="ignore"):
                    t_sub = np.where(mask, s_arr / abs(ds_dt_val), np.inf)
                    valid = np.isfinite(t_sub) & (t_sub > 0.0)
                    S_sub = np.where(valid, 1.0 / t_sub, 0.0)
    else:
        ds_dt_arr = np.asarray(ds_dt_k, dtype=float)
        if ds_dt_arr.shape != s_arr.shape:
            raise PhysicsError("ds_dt_k must have the same shape as s_grid_m")
        mask = (ds_dt_arr < 0.0) & np.isfinite(ds_dt_arr) & (s_arr > 0.0)
        if np.any(mask):
            with np.errstate(divide="ignore", invalid="ignore"):
                t_sub = np.where(mask, s_arr / np.abs(ds_dt_arr), np.inf)
                valid = np.isfinite(t_sub) & (t_sub > 0.0)
                S_sub = np.where(valid, 1.0 / t_sub, 0.0)

    mass_loss_rate = float(np.sum(m_arr * S_sub * N_arr))
    return S_sub, mass_loss_rate
