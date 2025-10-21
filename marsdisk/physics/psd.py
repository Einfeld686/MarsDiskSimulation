"""Particle size distribution (P1) with optional wavy correction.

This module provides a minimal three-slope particle size distribution (PSD)
that can mimic the short-term, non-steady behaviour of a collisional cascade.
An optional sinusoidal modulation adds the qualitative "wavy" pattern expected
when grains just above the blow-out limit are removed efficiently.

Two helper functions are exposed:

``update_psd_state``
    Construct a PSD state dictionary for a given size range.
``compute_kappa``
    Compute the mass opacity ``\kappa`` from a PSD state.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional

import logging

import numpy as np

from ..errors import MarsDiskError
from . import sizes as size_models
from .sublimation import SublimationParams

logger = logging.getLogger(__name__)


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
        number *= 1.0 + wavy_strength * np.sin(2.0 * np.pi * phase / period)

    logger.info("PSD updated: s_min=%g m, s_max=%g m", s_min, s_max)
    return {
        "sizes": centres,
        "widths": widths,
        "number": number,
        "rho": rho,
        "s_min": s_min,
        "s_max": s_max,
        "wavy_decay": wavy_decay,
        "alpha": alpha,
        "alpha_mode": alpha_mode,
        # ---- alias 追加（後段の関数が参照しやすい共通キー）
        "s": centres,
        "n": number,
        "edges": edges,
    }


def compute_kappa(psd_state: Dict[str, np.ndarray | float]) -> float:
    """Compute the mass opacity ``\kappa`` from a PSD state (P1).

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

    area = np.sum(np.pi * sizes**2 * number * widths)
    mass = np.sum((4.0 / 3.0) * np.pi * rho * sizes**3 * number * widths)

    return float(area / mass)


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

    if dt <= 0.0 or not np.isfinite(dt):
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}
    if not np.isfinite(ds_dt) or ds_dt == 0.0:
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}

    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)
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

    new_number = np.zeros_like(number)
    accum_sizes = np.zeros_like(number)
    for idx, n_val in enumerate(number):
        if n_val <= 0.0:
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor_val:
            s_new = floor_val
        # locate the new bin
        target = int(np.searchsorted(edges, s_new, side="right") - 1)
        if target < 0:
            target = 0
        elif target >= new_number.size:
            target = new_number.size - 1
        new_number[target] += n_val
        accum_sizes[target] += n_val * s_new

    # fallback: if nothing moved due to numerical issues keep original arrays
    if np.allclose(new_number, 0.0):
        return sigma_surf, 0.0, {"ds_step": 0.0, "mass_ratio": 1.0}

    new_sizes = sizes.copy()
    mask = new_number > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_number[mask]
    new_sizes = np.maximum(new_sizes, floor_val)

    # update aliases for downstream consumers
    psd_state["number"] = new_number
    psd_state["n"] = new_number
    psd_state["sizes"] = new_sizes
    psd_state["s"] = new_sizes
    psd_state["s_min"] = float(np.min(new_sizes))
    psd_state["edges"] = edges

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
            return s_min_prev
        if rho is None or rho <= 0.0:
            logger.warning("sublimation_min requires positive material density; skipping evolution")
            return s_min_prev
        ds_dt = size_models.eval_ds_dt_sublimation(T or 0.0, rho, sublimation_params)
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
