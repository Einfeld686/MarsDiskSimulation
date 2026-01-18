r"""Particle size distribution (P1) with optional wavy correction.

This module provides a minimal three-slope particle size distribution (PSD)
that can mimic the short-term, non-steady behaviour of a collisional cascade.
An optional sinusoidal modulation adds the qualitative "wavy" pattern expected
when grains just above the blow-out limit are removed efficiently.

Core helpers are exposed:

``update_psd_state``
    Construct a PSD state dictionary for a given size range.
``compute_kappa``
    Compute the mass opacity ``\kappa`` from a PSD state.
``mass_weights_lognormal_mixture`` / ``mass_weights_truncated_powerlaw``
    Build melt-solid initial mass weights with condensation cuts.
``apply_mass_weights``
    Map mass weights onto the PSD number array while preserving total mass.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional

import logging
import warnings

import numpy as np

from ..errors import MarsDiskError
from ..runtime.numba_config import numba_disabled_env
from ..warnings import NumericalWarning
from . import sizes as size_models
from .sublimation import SublimationParams
try:
    from ._numba_kernels import NUMBA_AVAILABLE, size_drift_rebin_numba

    _NUMBA_AVAILABLE = NUMBA_AVAILABLE()
except ImportError:  # pragma: no cover - optional dependency
    _NUMBA_AVAILABLE = False

_NUMBA_DISABLED_ENV = numba_disabled_env()
_USE_NUMBA = _NUMBA_AVAILABLE and not _NUMBA_DISABLED_ENV
_NUMBA_FAILED = False

logger = logging.getLogger(__name__)

__all__ = [
    "update_psd_state",
    "compute_kappa",
    "mass_weights_lognormal_mixture",
    "mass_weights_truncated_powerlaw",
    "apply_mass_weights",
    "apply_uniform_size_drift",
    "sanitize_and_normalize_number",
]


def _set_psd_edges(
    psd_state: Dict[str, np.ndarray | float],
    edges: np.ndarray,
    *,
    bump_version: bool = True,
) -> None:
    """Update PSD edges and bump edges_version only when the content changes."""

    edges_arr = np.asarray(edges, dtype=float)
    old_edges = psd_state.get("edges")
    if isinstance(old_edges, np.ndarray):
        if old_edges.shape == edges_arr.shape and np.array_equal(old_edges, edges_arr):
            psd_state["edges"] = edges_arr
            return
    psd_state["edges"] = edges_arr
    if bump_version:
        psd_state["edges_version"] = int(psd_state.get("edges_version", 0)) + 1
    else:
        psd_state.setdefault("edges_version", 0)


def update_psd_state(
    *,
    s_min: float,
    s_max: float,
    alpha: float,
    wavy_strength: float,
    n_bins: int = 40,
    rho: float = 3000.0,
    wavy_decay: float = 0.0,   # wavy の減衰係数（任意, 既定0）
    alpha_mode: str = "size",
) -> Dict[str, np.ndarray | float]:
    """Return a particle size distribution state.

    Parameters
    ----------
    s_min:
        Minimum grain radius in metres.
    s_max:
        Maximum grain radius in metres; must exceed ``s_min``.
    alpha:
        Base power-law slope for the smallest grains.
    wavy_strength:
        Amplitude of the sinusoidal "wavy" modulation.  Set to zero to
        suppress the effect.
    n_bins:
        Number of logarithmic size bins.
    rho:
        Material density of the grains in kg/m^3.

    Returns
    -------
    dict
        Dictionary containing ``sizes`` (bin centres), ``widths`` (bin widths),
        ``number`` (relative number density) and ``rho``.

    Raises
    ------
    MarsDiskError
        If ``s_min`` is not smaller than ``s_max`` or if ``n_bins`` is not
        positive.
    """
    if s_min >= s_max:
        raise MarsDiskError("s_min must be smaller than s_max")
    if n_bins <= 0:
        raise MarsDiskError("n_bins must be positive")

    # logarithmic bin edges and centres
    edges = np.logspace(np.log10(s_min), np.log10(s_max), n_bins + 1)
    centres = np.sqrt(edges[:-1] * edges[1:])
    widths = np.diff(edges)

    # three-slope power-law approximation
    s_break1 = s_min * 10.0
    s_break2 = s_max / 10.0
    if alpha_mode == "mass":
        q0 = 3.0 * alpha - 2.0  # dN/ds ∝ s^{-q},  m ∝ s^3 より
    elif alpha_mode == "size":
        q0 = alpha
    else:
        raise MarsDiskError("alpha_mode must be 'size' or 'mass'")
    slopes = np.empty_like(centres)
    slopes.fill(q0 + 1.5)            # 大粒子側でより急になる例
    slopes[centres < s_break2] = q0 + 1.0
    slopes[centres < s_break1] = q0

    number = (centres / s_min) ** (-slopes)

    if wavy_strength != 0.0:
        period = np.log(s_max / s_min)
        phase = np.log(centres / s_min)
        envelope = np.exp(-wavy_decay * phase) if wavy_decay > 0.0 else 1.0
        number *= 1.0 + wavy_strength * envelope * np.sin(2.0 * np.pi * phase / period)

    logger.info("PSD updated: s_min=%g m, s_max=%g m", s_min, s_max)
    psd_state = {
        "sizes": centres,
        "widths": widths,
        "number": number,
        "rho": rho,
        "s_min": s_min,
        "s_max": s_max,
        "sizes_version": 0,
        "edges_version": 0,
        "wavy_decay": wavy_decay,
        "alpha": alpha,
        "alpha_mode": alpha_mode,
        # ---- alias 追加（後段の関数が参照しやすい共通キー）
        "s": centres,
        "n": number,
    }
    _set_psd_edges(psd_state, edges, bump_version=False)
    sanitize_and_normalize_number(psd_state)
    return psd_state


def sanitize_and_normalize_number(
    psd_state: Dict[str, np.ndarray | float],
    clip_max: float = 1e200,
    *,
    normalize: bool = True,
) -> Dict[str, np.ndarray | float]:
    """Clamp non-finite/negative/huge number entries and optionally mass-normalize.

    - 非有限/負の number は 0 へクリップ
    - clip_max より大きい値は clip_max へクリップ（浮動小数点オーバーフロー防止）
    - normalize=True の場合、質量重み ``sum(number * s^3 * width)`` が有限かつ正なら 1 で正規化
      （面積/質量比を計算する際のスケール暴走を抑止）。0/非有限なら一様分布にリセットして正規化。
    """

    sizes = np.asarray(psd_state.get("sizes"), dtype=float)
    widths = np.asarray(psd_state.get("widths"), dtype=float)
    number = np.asarray(psd_state.get("number"), dtype=float)
    if sizes.size == 0 or widths.size != sizes.size or number.size != sizes.size:
        return psd_state

    number = np.where(np.isfinite(number) & (number > 0.0), number, 0.0)
    if clip_max is not None and clip_max > 0.0:
        number = np.clip(number, 0.0, clip_max)

    if normalize:
        mass_weight = float(np.sum(number * (sizes**3) * widths))
        reset_applied = False
        if not np.isfinite(mass_weight) or mass_weight <= 0.0:
            number = np.ones_like(number, dtype=float)
            mass_weight = float(np.sum(number * (sizes**3) * widths))
            reset_applied = True
            if mass_weight <= 0.0 or not np.isfinite(mass_weight):
                mass_weight = 1.0
                reset_applied = True
        if reset_applied:
            psd_state["sanitize_reset_count"] = int(psd_state.get("sanitize_reset_count", 0)) + 1
            warnings.warn(
                "PSD normalization reset due to invalid mass weight; check PSD inputs.",
                NumericalWarning,
            )
        number /= mass_weight
    psd_state["number"] = number
    psd_state["n"] = number
    return psd_state


def ensure_psd_state_contract(
    psd_state: Dict[str, np.ndarray | float],
) -> Dict[str, np.ndarray | float]:
    """Ensure alias keys and version markers remain in sync."""

    sizes = psd_state.get("sizes")
    if sizes is not None:
        psd_state["s"] = sizes
    number = psd_state.get("number")
    if number is not None:
        psd_state["n"] = number
    psd_state.setdefault("sizes_version", 0)
    if "edges" in psd_state:
        psd_state.setdefault("edges_version", 0)
    return psd_state


def compute_kappa(psd_state: Dict[str, np.ndarray | float]) -> float:
    r"""Compute the mass opacity ``\kappa`` from a PSD state (P1).

    The opacity is defined as

    ``\kappa = \int \pi s^2 n(s) ds / \int (4/3) \pi \rho s^3 n(s) ds``.

    Parameters
    ----------
    psd_state:
        Dictionary produced by :func:`update_psd_state`.

    Returns
    -------
    float
        Mass opacity in m^2/kg.
    """
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
    rho = float(psd_state["rho"])

    if sizes.size == 0 or widths.size != sizes.size or number.size != sizes.size:
        return 0.0

    number = np.where(np.isfinite(number) & (number > 0.0), number, 0.0)
    max_val = float(np.max(number)) if number.size else 0.0
    if max_val > 0.0 and np.isfinite(max_val):
        number = number / max_val
    area = np.sum(np.pi * sizes**2 * number * widths)
    mass = np.sum((4.0 / 3.0) * np.pi * rho * sizes**3 * number * widths)
    if not np.isfinite(area) or not np.isfinite(mass) or mass <= 0.0:
        return 0.0
    return float(area / mass)


def mass_weights_lognormal_mixture(
    sizes: np.ndarray,
    widths: np.ndarray,
    *,
    f_fine: float,
    s_fine: float,
    s_meter: float,
    width_dex: float,
    s_cut: float | None = None,
) -> np.ndarray:
    """Return per-bin mass weights for a two-component melt mixture.

    Hyodo et al. (2017) report that post-impact solids are dominated by
    metre-scale melt droplets with a collisionally produced tail toward
    ~100 µm.  Condensation dust is sub-dominant (<5%), so bins below
    ``s_cut`` are zeroed to enforce the melt-only initial condition.
    """

    sizes_arr = np.asarray(sizes, dtype=float)
    widths_arr = np.asarray(widths, dtype=float)
    weights = np.zeros_like(sizes_arr, dtype=float)
    if sizes_arr.size == 0 or widths_arr.size != sizes_arr.size:
        return weights
    sigma_ln = max(float(width_dex), 0.0) * np.log(10.0)
    if sigma_ln <= 0.0:
        return weights

    def _lognormal(center: float) -> np.ndarray:
        if center <= 0.0 or not np.isfinite(center):
            return np.zeros_like(sizes_arr)
        log_ratio = np.log(sizes_arr / center)
        return np.exp(-0.5 * (log_ratio / sigma_ln) ** 2)

    f_fine_clipped = min(max(float(f_fine), 0.0), 1.0)
    weights_fine = _lognormal(float(s_fine)) * widths_arr
    weights_meter = _lognormal(float(s_meter)) * widths_arr
    if s_cut is not None and np.isfinite(s_cut):
        mask = sizes_arr >= float(s_cut)
        weights_fine = np.where(mask, weights_fine, 0.0)
        weights_meter = np.where(mask, weights_meter, 0.0)
    weights_fine_sum = float(np.sum(weights_fine))
    if weights_fine_sum > 0.0:
        weights_fine /= weights_fine_sum
    else:
        weights_fine = np.zeros_like(weights_fine, dtype=float)
    weights_meter_sum = float(np.sum(weights_meter))
    if weights_meter_sum > 0.0:
        weights_meter /= weights_meter_sum
    else:
        weights_meter = np.zeros_like(weights_meter, dtype=float)
    weights = (1.0 - f_fine_clipped) * weights_meter + f_fine_clipped * weights_fine
    return weights


def mass_weights_truncated_powerlaw(
    sizes: np.ndarray,
    widths: np.ndarray,
    *,
    alpha_solid: float,
    s_min_solid: float,
    s_max_solid: float,
    s_cut: float | None = None,
) -> np.ndarray:
    """Return per-bin mass weights for a truncated power-law melt PSD.

    Jutzi et al. (2010) report cumulative slopes N(>D)∝D^a with a≈-2.2…-2.7,
    implying dN/ds∝s^-alpha with alpha≈3.2–3.7.  The default alpha_solid=3.5
    captures this range while zeroing any condensation-sized bins below
    ``s_cut``.
    """

    sizes_arr = np.asarray(sizes, dtype=float)
    widths_arr = np.asarray(widths, dtype=float)
    weights = np.zeros_like(sizes_arr, dtype=float)
    if sizes_arr.size == 0 or widths_arr.size != sizes_arr.size:
        return weights

    floor = max(float(s_min_solid), float(s_cut) if s_cut is not None else 0.0)
    ceil = float(s_max_solid)
    if ceil <= floor:
        return weights
    mask = (sizes_arr >= floor) & (sizes_arr <= ceil)
    if not np.any(mask):
        return weights
    weights[mask] = np.power(sizes_arr[mask], 3.0 - float(alpha_solid)) * widths_arr[mask]
    return weights


def apply_mass_weights(
    psd_state: Dict[str, np.ndarray | float],
    mass_weights: np.ndarray,
    *,
    rho: float | None = None,
) -> Dict[str, np.ndarray | float]:
    """Map mass weights to the PSD's number array while preserving total mass."""

    sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
    widths_arr = np.asarray(psd_state.get("widths"), dtype=float)
    weights_arr = np.asarray(mass_weights, dtype=float)
    if (
        sizes_arr.size == 0
        or widths_arr.size != sizes_arr.size
        or weights_arr.size != sizes_arr.size
    ):
        return psd_state

    rho_use = rho if rho is not None else psd_state.get("rho", None)
    rho_use = float(rho_use) if rho_use is not None else 0.0
    if rho_use <= 0.0:
        return psd_state

    weights_arr = np.where(np.isfinite(weights_arr) & (weights_arr > 0.0), weights_arr, 0.0)
    weights_sum = float(np.sum(weights_arr))
    if weights_sum <= 0.0:
        logger.warning("apply_mass_weights: mass weights sum to zero; keeping existing PSD shape")
        return psd_state
    weights_arr /= weights_sum

    m_bin = (4.0 / 3.0) * np.pi * rho_use * sizes_arr**3
    denom = m_bin * widths_arr
    mask = denom > 0.0
    number_new = np.zeros_like(sizes_arr, dtype=float)
    number_new[mask] = weights_arr[mask] / denom[mask]
    if not np.any(number_new):
        logger.warning("apply_mass_weights: derived zero number density; keeping existing PSD shape")
        return psd_state

    psd_state["number"] = number_new
    psd_state["n"] = number_new
    sanitize_and_normalize_number(psd_state)
    return psd_state


def _size_drift_rebin_numpy(
    sizes: np.ndarray,
    number: np.ndarray,
    edges: np.ndarray,
    ds_step: float,
    floor_val: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised rebinning helper for :func:`apply_uniform_size_drift`."""

    s_new = sizes + ds_step
    s_new = np.where(np.isfinite(s_new), s_new, np.nan)
    s_new = np.where(s_new < floor_val, floor_val, s_new)
    valid = (number > 0.0) & np.isfinite(number) & np.isfinite(s_new)
    if not np.any(valid):
        return np.zeros_like(number), np.zeros_like(number)

    targets = np.searchsorted(edges, s_new[valid], side="right") - 1
    targets = np.clip(targets, 0, number.size - 1)
    new_number = np.zeros_like(number)
    accum_sizes = np.zeros_like(number)
    np.add.at(new_number, targets, number[valid])
    np.add.at(accum_sizes, targets, number[valid] * s_new[valid])
    return new_number, accum_sizes


def apply_uniform_size_drift(
    psd_state: Dict[str, np.ndarray | float],
    *,
    ds_dt: float,
    dt: float,
    floor: float,
    sigma_surf: float,
) -> tuple[float, float, Dict[str, float]]:
    """Erode all PSD bins by a uniform ``ds/dt`` and update ``Sigma_surf``.

    Parameters
    ----------
    psd_state:
        Mutable PSD state dictionary.
    ds_dt:
        Size-change rate ``ds/dt`` (m/s).  Negative values correspond to
        sublimation-driven erosion.  Positive values expand the grains.
    dt:
        Integration step (s).
    floor:
        Minimum grain size enforced after the drift (m).  Values below
        ``floor`` are clipped before rebinned.
    sigma_surf:
        Current surface mass density (kg/m^2).  Used to convert the change in
        the PSD to an areal mass deficit.

    Returns
    -------
    sigma_surf_new:
        Updated surface mass density after the uniform size drift.
    delta_sigma_loss:
        Positive-definite mass density removed from the solids during the
        drift (kg/m^2).  This should be tallied as a sublimation sink by the
        caller.
    diagnostics:
        Dictionary containing auxiliary information such as the cumulative
        shift ``ds_step`` and the mass ratio.
    """

    global _NUMBA_FAILED

    if dt <= 0.0 or not np.isfinite(dt):
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}
    if not np.isfinite(ds_dt) or ds_dt == 0.0:
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}

    sanitize_and_normalize_number(psd_state, normalize=False)

    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
    number_orig = number.copy()
    counts = number * widths
    if sizes.size == 0:
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}

    if "edges" in psd_state:
        edges = np.asarray(psd_state["edges"], dtype=float)
    else:  # pragma: no cover - legacy safeguard
        edges = np.empty(sizes.size + 1, dtype=float)
        edges[:-1] = sizes - 0.5 * widths
        edges[-1] = sizes[-1] + 0.5 * widths[-1]
    floor_val = float(floor)
    ds_step = float(ds_dt * dt)
    use_jit = _USE_NUMBA and not _NUMBA_FAILED
    if use_jit:
        try:
            new_counts, accum_sizes = size_drift_rebin_numba(
                sizes.astype(np.float64),
                counts.astype(np.float64),
                edges.astype(np.float64),
                float(ds_step),
                float(floor_val),
            )
        except Exception as exc:  # pragma: no cover - fallback
            use_jit = False
            _NUMBA_FAILED = True
            warnings.warn(
                f"size_drift_rebin_numba failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
    if not use_jit:
        new_counts, accum_sizes = _size_drift_rebin_numpy(sizes, counts, edges, ds_step, floor_val)

    # fallback: if nothing moved due to numerical issues keep original arrays
    if np.allclose(new_counts, 0.0):
        warnings.warn(
            "apply_uniform_size_drift: rebin produced all-zero distribution; keeping previous PSD.",
            NumericalWarning,
        )
        return sigma_surf, 0.0, {"ds_step": ds_step, "mass_ratio": 1.0, "rebin_zeroed": True}

    new_sizes = sizes.copy()
    mask = new_counts > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_counts[mask]
    new_sizes = np.maximum(new_sizes, floor_val)
    new_number = np.zeros_like(number)
    width_mask = mask & (widths > 0.0)
    new_number[width_mask] = new_counts[width_mask] / widths[width_mask]
    # clip-only sanitize before mass_ratio計算（規模暴走を防ぎつつスケールは保持）
    tmp_state = {"sizes": new_sizes, "widths": widths, "number": new_number}
    sanitize_and_normalize_number(tmp_state, normalize=False)
    new_number = np.asarray(tmp_state["number"], dtype=float)
    # 完全にゼロ化・非有限化した場合は前ステップへロールバックし、質量正規化して止血
    if not np.isfinite(new_number).all() or np.sum(new_number) == 0.0:
        logger.warning("apply_uniform_size_drift: number became zero/non-finite; rolling back to previous PSD shape")
        psd_state["number"] = number_orig
        psd_state["n"] = number_orig
        sanitize_and_normalize_number(psd_state, normalize=True)
        return sigma_surf, 0.0, {"ds_step": ds_step, "mass_ratio": 1.0, "sigma_before": sigma_surf, "sigma_after": sigma_surf}

    # update aliases for downstream consumers
    psd_state["number"] = new_number
    psd_state["n"] = new_number
    psd_state["sizes"] = new_sizes
    psd_state["s"] = new_sizes
    psd_state["sizes_version"] = int(psd_state.get("sizes_version", 0)) + 1
    psd_state["s_min"] = float(np.min(new_sizes))
    _set_psd_edges(psd_state, edges)
    sanitize_and_normalize_number(psd_state)

    # determine the relative change in solid mass represented by the PSD
    old_mass_weight = float(np.sum(number * (sizes**3) * widths))
    new_mass_weight = float(np.sum(new_number * (new_sizes**3) * widths))
    if old_mass_weight <= 0.0 or sigma_surf <= 0.0:
        mass_ratio = 1.0
        sigma_new = sigma_surf
        delta_sigma = 0.0
    else:
        mass_ratio = new_mass_weight / old_mass_weight if old_mass_weight else 1.0
        if not np.isfinite(mass_ratio) or mass_ratio < 0.0:
            mass_ratio = 0.0
        sigma_new = sigma_surf * mass_ratio
        delta_sigma = max(sigma_surf - sigma_new, 0.0)

    diagnostics = {
        "ds_step": ds_step,
        "mass_ratio": mass_ratio,
        "sigma_before": sigma_surf,
        "sigma_after": sigma_new,
    }
    return sigma_new, delta_sigma, diagnostics


def evolve_min_size(
    s_min_prev: float,
    *,
    dt: float,
    model: Optional[str] = None,
    params: Optional[Mapping[str, float]] = None,
    T: Optional[float] = None,
    rho: Optional[float] = None,
    s_floor: Optional[float] = None,
    sublimation_params: Optional[SublimationParams] = None,
) -> float:
    """Return the evolved minimum grain size after a time step ``dt``.

    Parameters
    ----------
    s_min_prev:
        Previous minimum grain size [m].
    dt:
        Time-step [s].
    model:
        Identifier of the evolution prescription.  ``None`` or ``"noop"``
        leaves the input unchanged.
    params:
        Optional mapping of model parameters.
    T:
        Diagnostic temperature (K).  Not used by the reference model but
        available for future extensions.
    rho:
        Diagnostic density (kg m⁻³).  Not used by the reference model but
        available for future extensions.
    s_floor:
        Optional lower bound enforced during the update.  The caller typically
        supplies ``max(s_min_cfg, a_blow)`` so the diagnostic value never drops
        below the operative PSD floor.
    sublimation_params:
        Optional sublimation settings for models that require them.

    Notes
    -----
    The returned value is a *diagnostic* candidate that reflects grain-size
    erosion models (e.g. sublimation ``ds/dt``).  The effective minimum used by
    :func:`marsdisk.run.run_zero_d` remains ``max(s_min_cfg, s_blow)``; callers
    must opt-in explicitly if they wish to apply the evolved value as a new
    floor.
    """

    if dt <= 0.0:
        return s_min_prev
    if model is None or model.lower() in {"noop", "identity", "none"}:
        return s_min_prev

    params = dict(params or {})
    floor = float(params.get("floor", 0.0))
    if s_floor is not None:
        floor = max(floor, float(s_floor))

    if model == "linear_decay":
        k0 = float(params.get("k0", 0.0))
        k_T = float(params.get("k_T", 0.0))
        T_ref = float(params.get("T_ref", 1.0))
        k = k0
        if k_T != 0.0 and T is not None:
            k += k_T * max(T, 0.0) / max(T_ref, 1e-6)
        ds = -k * dt
        s_new = max(s_min_prev + ds, floor)
        return s_new

    if model == "constant_decay":
        k0 = float(params.get("k0", 0.0))
        ds = -k0 * dt
        return max(s_min_prev + ds, floor)

    if model == "sublimation_min":
        if sublimation_params is None:
            logger.warning("sublimation_min requested without SublimationParams; skipping evolution")
            return max(s_min_prev, floor)
        if rho is None or rho <= 0.0:
            logger.warning("sublimation_min requires positive material density; skipping evolution")
            return max(s_min_prev, floor)
        if T is None or not np.isfinite(T) or T <= 0.0:
            logger.warning("sublimation_min requires positive temperature; skipping evolution")
            return max(s_min_prev, floor)
        ds_dt = size_models.eval_ds_dt_sublimation(float(T), rho, sublimation_params)
        ds = ds_dt * dt
        s_next = max(s_min_prev + ds, floor)
        if s_next < s_min_prev:
            # enforce monotonic increase of the lower bound
            s_next = s_min_prev
        return s_next

    # Unknown model: fall back to identity but log for debugging.
    logger.warning("Unknown ds/dt model '%s'; leaving s_min unchanged", model)
    return s_min_prev


__all__ = [
    "update_psd_state",
    "compute_kappa",
    "evolve_min_size",
    "apply_uniform_size_drift",
]
