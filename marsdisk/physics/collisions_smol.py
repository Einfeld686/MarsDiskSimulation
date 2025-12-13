from __future__ import annotations

"""Smoluchowski collision+fragmentation step specialised for the 0D loop."""

import math
import os
import warnings
from dataclasses import dataclass
from typing import MutableMapping, TYPE_CHECKING

import numpy as np
import logging
from ..errors import MarsDiskError
from . import collide, dynamics, qstar, smol
from .fragments import largest_remnant_fraction_array, q_r_array
from .sublimation import sublimation_sink_from_dsdt

# Numba-accelerated kernels (optional)
try:
    from ._numba_kernels import (
        NUMBA_AVAILABLE,
        compute_weights_table_numba,
        fill_fragment_tensor_numba,
    )
    _NUMBA_AVAILABLE = NUMBA_AVAILABLE()
except ImportError:
    _NUMBA_AVAILABLE = False

# Honour opt-out via environment variable to aid debugging or CI sandboxes.
_NUMBA_DISABLED_ENV = os.environ.get("MARSDISK_DISABLE_NUMBA", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_USE_NUMBA = _NUMBA_AVAILABLE and not _NUMBA_DISABLED_ENV
# Set to True after a runtime failure to avoid repeatedly calling broken JIT kernels.
_NUMBA_FAILED = False

if TYPE_CHECKING:
    from ..schema import Dynamics, SupplyInjectionVelocity

logger = logging.getLogger(__name__)
_SUPPLY_EPS = 1.0e-30


@dataclass
class Smol0DStepResult:
    """Container for Smol collision updates and diagnostics."""

    psd_state: MutableMapping[str, np.ndarray | float]
    sigma_before: float
    sigma_after: float
    sigma_loss: float
    sigma_for_step: float
    sigma_clip_loss: float
    dt_eff: float
    mass_error: float
    prod_mass_rate_effective: float
    dSigma_dt_blowout: float
    dSigma_dt_sinks: float
    dSigma_dt_sublimation: float
    mass_loss_rate_blowout: float
    mass_loss_rate_sinks: float
    mass_loss_rate_sublimation: float
    t_coll_kernel: float | None = None
    e_kernel_used: float | None = None
    i_kernel_used: float | None = None
    e_kernel_base: float | None = None
    i_kernel_base: float | None = None
    e_kernel_supply: float | None = None
    i_kernel_supply: float | None = None
    e_kernel_effective: float | None = None
    i_kernel_effective: float | None = None
    supply_velocity_weight: float | None = None


@dataclass
class KernelEIState:
    """Baseline and effective eccentricity/inclination for the collision kernel."""

    e_base: float
    i_base: float
    e_used: float
    i_used: float
    H_k: np.ndarray


def supply_mass_rate_to_number_source(
    prod_subblow_mass_rate: float,
    s_bin_center: np.ndarray,
    m_bin: np.ndarray,
    s_min_eff: float,
    *,
    widths: np.ndarray | None = None,
    mode: str = "min_bin",
    s_inj_min: float | None = None,
    s_inj_max: float | None = None,
    q: float = 3.5,
) -> np.ndarray:
    """Convert a mass flux to a per-bin number source ``F_k`` (1/s).

    The default mapping injects all supplied mass into the smallest bin with
    ``s >= s_min_eff`` (falling back to the last bin) so that
    ``sum(m_k * F_k) == prod_subblow_mass_rate`` holds by construction.
    When ``mode='powerlaw_bins'`` the mass is distributed over bins in the
    range ``[s_inj_min, s_inj_max]`` with ``dN/ds ∝ s^{-q}``, scaled to
    preserve the total supplied mass.  Negative mass fluxes are treated as
    zero.
    """

    prod_rate = max(float(prod_subblow_mass_rate), 0.0)
    s_arr = np.asarray(s_bin_center, dtype=float)
    m_arr = np.asarray(m_bin, dtype=float)
    widths_arr = np.asarray(widths, dtype=float) if widths is not None else None
    if s_arr.shape != m_arr.shape:
        raise MarsDiskError("s_bin_center and m_bin must share the same shape")
    if widths_arr is not None and widths_arr.shape != s_arr.shape:
        raise MarsDiskError("widths must match the shape of s_bin_center")
    if prod_rate <= 0.0 or s_arr.size == 0:
        return np.zeros_like(m_arr)

    mode_normalised = str(mode or "min_bin")
    inj_floor = float(max(s_min_eff, 0.0))
    if s_inj_min is not None and math.isfinite(s_inj_min):
        inj_floor = max(inj_floor, float(s_inj_min))

    def _inject_min_bin(effective_floor: float) -> np.ndarray:
        candidates = np.nonzero(s_arr >= effective_floor)[0]
        k_inj = int(candidates[0]) if candidates.size else int(len(s_arr) - 1)
        F_min = np.zeros_like(m_arr, dtype=float)
        if m_arr[k_inj] > 0.0:
            F_min[k_inj] = prod_rate / m_arr[k_inj]
        return F_min

    if mode_normalised != "powerlaw_bins":
        return _inject_min_bin(inj_floor)

    if widths_arr is None:
        raise MarsDiskError("powerlaw_bins mode requires bin widths")

    inj_ceiling = float(np.max(s_arr))
    if s_inj_max is not None and math.isfinite(s_inj_max):
        inj_ceiling = float(s_inj_max)
    inj_ceiling = max(min(inj_ceiling, float(np.max(s_arr))), inj_floor)

    left_edges = np.maximum(s_arr - 0.5 * widths_arr, 0.0)
    right_edges = left_edges + widths_arr
    overlap_left = np.maximum(left_edges, inj_floor)
    overlap_right = np.minimum(right_edges, inj_ceiling)
    mask = overlap_right > overlap_left
    weights = np.zeros_like(s_arr, dtype=float)
    if np.any(mask):
        if math.isclose(q, 1.0):
            weights[mask] = np.log(overlap_right[mask] / overlap_left[mask])
        else:
            power = 1.0 - float(q)
            weights[mask] = (overlap_right[mask] ** power - overlap_left[mask] ** power) / power
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
    weights_sum = float(np.sum(weights))
    if weights_sum <= 0.0:
        return _inject_min_bin(inj_floor)

    mass_alloc = (weights / weights_sum) * prod_rate
    F = np.zeros_like(m_arr, dtype=float)
    positive = (mass_alloc > 0.0) & (m_arr > 0.0)
    F[positive] = mass_alloc[positive] / m_arr[positive]
    return F


_FRAG_CACHE: dict[tuple, np.ndarray] = {}
_FRAG_CACHE_MAX = 8


def _fragment_tensor(
    sizes: np.ndarray,
    masses: np.ndarray,
    v_rel: float | np.ndarray,
    rho: float,
    alpha_frag: float = 3.5,
    *,
    use_numba: bool | None = None,
) -> np.ndarray:
    """Return a mass-conserving fragment distribution ``Y[k, i, j]``.

    When Numba is available, the inner loops are JIT-compiled and parallelised
    for significant speedup on multi-core systems.
    """
    global _NUMBA_FAILED

    sizes_arr = np.asarray(sizes, dtype=np.float64)
    masses_arr = np.asarray(masses, dtype=np.float64)
    if sizes_arr.shape != masses_arr.shape:
        raise MarsDiskError("sizes and masses must share the same shape")

    n = sizes_arr.size
    if n == 0:
        return np.zeros((0, 0, 0), dtype=np.float64)
    if rho <= 0.0:
        raise MarsDiskError("rho must be positive")

    use_cache = np.isscalar(v_rel)
    cache_key: tuple | None = None
    if use_cache:
        cache_key = (
            "scalar",
            float(v_rel),
            float(rho),
            tuple(sizes_arr.tolist()),
            tuple(masses_arr.tolist()),
            float(alpha_frag),
        )
        cached = _FRAG_CACHE.get(cache_key)
        if cached is not None:
            return cached

    if np.isscalar(v_rel):
        v_matrix = np.full((n, n), float(v_rel), dtype=np.float64)
    else:
        v_matrix = np.asarray(v_rel, dtype=np.float64)
        if v_matrix.shape != (n, n):
            raise MarsDiskError("v_rel must be scalar or (n, n)")
    v_matrix = np.maximum(v_matrix, 1.0e-12)

    # Precompute matrices needed for fragment distribution
    m1 = masses_arr[:, None]
    m2 = masses_arr[None, :]
    m_tot = m1 + m2
    valid_pair = (m1 > 0.0) & (m2 > 0.0) & (m_tot > 0.0)

    size_ref = np.maximum.outer(sizes_arr, sizes_arr)
    q_star_matrix = qstar.compute_q_d_star_array(size_ref, rho, v_matrix / 1.0e3)
    q_r_matrix = q_r_array(m1, m2, v_matrix)
    f_lr_matrix = np.clip(
        largest_remnant_fraction_array(q_r_matrix, q_star_matrix), 0.0, 1.0
    ).astype(np.float64)
    k_lr_matrix = np.maximum.outer(
        np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int64)
    )

    # Output tensor
    Y = np.zeros((n, n, n), dtype=np.float64)

    # Decide whether to attempt JIT, with per-call override.
    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    if use_jit and not _NUMBA_AVAILABLE:
        use_jit = False

    # Branch: Numba-accelerated or pure Python fallback
    if use_jit:
        try:
            weights_table = compute_weights_table_numba(sizes_arr, float(alpha_frag))
            fill_fragment_tensor_numba(
                Y, n, valid_pair, f_lr_matrix, k_lr_matrix, weights_table
            )
        except Exception as exc:  # pragma: no cover - exercised via fallback test
            # Reset and fall back to the pure-Python implementation.
            Y.fill(0.0)
            use_jit = False
            warnings.warn(
                f"_fragment_tensor: numba kernel failed ({exc!r}); falling back to pure Python.",
                RuntimeWarning,
            )
            _NUMBA_FAILED = True

    if not use_jit:
        # Pure Python fallback (original implementation)
        weights_table = np.zeros((n, n), dtype=np.float64)
        for k_lr in range(n):
            weights = np.power(sizes_arr[: k_lr + 1], -alpha_frag)
            weights_sum = float(np.sum(weights))
            if weights_sum > 0.0:
                weights_table[k_lr, : k_lr + 1] = weights / weights_sum

        for i in range(n):
            for j in range(n):
                if not valid_pair[i, j]:
                    continue
                k_lr = int(k_lr_matrix[i, j])
                f_lr = float(f_lr_matrix[i, j])
                Y[k_lr, i, j] += f_lr

                remainder_frac = 1.0 - f_lr
                if remainder_frac <= 0.0:
                    continue
                weights = weights_table[k_lr, : k_lr + 1]
                if weights.size == 0 or weights.sum() <= 0.0:
                    continue
                Y[: k_lr + 1, i, j] += remainder_frac * weights

    if use_cache and cache_key is not None:
        if len(_FRAG_CACHE) >= _FRAG_CACHE_MAX:
            _FRAG_CACHE.pop(next(iter(_FRAG_CACHE)))
        _FRAG_CACHE[cache_key] = Y
    return Y


def _blowout_sink_vector(
    sizes: np.ndarray,
    a_blow: float,
    Omega: float,
    enable_blowout: bool,
) -> np.ndarray:
    """Return per-bin blow-out sink rates (1/s)."""

    if not enable_blowout or Omega <= 0.0:
        return np.zeros_like(sizes)
    mask = sizes <= a_blow
    sink = np.zeros_like(sizes, dtype=float)
    sink[mask] = Omega
    return sink


def kernel_minimum_tcoll(C_kernel: np.ndarray) -> float:
    """Return the minimum collisional time-scale implied by ``C``."""

    if C_kernel.size == 0:
        return math.inf
    rates = np.sum(C_kernel, axis=1)
    rate_max = float(np.max(rates))
    if rate_max <= 0.0:
        return math.inf
    return 1.0 / rate_max


def _supply_velocity_weight(delta_sigma: float, sigma_prev: float, mode: str = "delta_sigma") -> float:
    """Blend weight for supply velocities."""

    delta_pos = max(float(delta_sigma), 0.0)
    sigma_pos = max(float(sigma_prev), 0.0)
    mode_norm = str(mode or "delta_sigma")
    if mode_norm == "sigma_ratio":
        return float(delta_pos / max(sigma_pos, _SUPPLY_EPS))
    return float(delta_pos / (sigma_pos + delta_pos + _SUPPLY_EPS))


def _resolve_supply_velocity(cfg: "SupplyInjectionVelocity | None", e_base: float, i_base: float) -> tuple[float, float]:
    """Return (e_supply, i_supply) given the injection velocity settings."""

    if cfg is None:
        return e_base, i_base
    mode = getattr(cfg, "mode", "inherit")
    if mode == "fixed_ei":
        e_sup = getattr(cfg, "e_inj", e_base)
        i_sup = getattr(cfg, "i_inj", i_base)
        return float(e_sup if e_sup is not None else e_base), float(i_sup if i_sup is not None else i_base)
    if mode == "factor":
        factor = getattr(cfg, "vrel_factor", 1.0) or 1.0
        factor = float(factor) if math.isfinite(factor) else 1.0
        return float(e_base * factor), float(i_base * factor)
    return e_base, i_base


def _blend_supply_velocity(
    e_base: float,
    i_base: float,
    e_supply: float,
    i_supply: float,
    *,
    weight: float,
    mode: str = "rms",
) -> tuple[float, float]:
    """Blend baseline and supply e/i."""

    w = float(np.clip(weight, 0.0, 1.0))
    mode_norm = str(mode or "rms")
    if mode_norm == "linear":
        e_eff = (1.0 - w) * e_base + w * e_supply
        i_eff = (1.0 - w) * i_base + w * i_supply
        return e_eff, i_eff
    e_eff = math.sqrt(max((1.0 - w) * e_base**2 + w * e_supply**2, 0.0))
    i_eff = math.sqrt(max((1.0 - w) * i_base**2 + w * i_supply**2, 0.0))
    return e_eff, i_eff


def compute_kernel_ei_state(
    dynamics_cfg: "Dynamics",
    tau_eff: float,
    a_orbit_m: float,
    v_k: float,
    sizes: np.ndarray,
    *,
    e_override: float | None = None,
    i_override: float | None = None,
) -> KernelEIState:
    """Return baseline and effective e/i along with the scale height array."""

    tau_eff = max(float(tau_eff), 0.0)
    e_base = float(dynamics_cfg.e0)
    i_base = float(dynamics_cfg.i0)
    v_k_safe = max(float(v_k), 1.0e-12)

    if dynamics_cfg.kernel_ei_mode == "wyatt_eq":
        def _eps_model(_v: float) -> float:
            return 0.5

        try:
            c_eq = dynamics.solve_c_eq(
                tau_eff,
                max(dynamics_cfg.e0, 1.0e-6),
                _eps_model,
                f_wake=float(dynamics_cfg.f_wake),
            )
        except Exception:
            c_eq = max(dynamics_cfg.e0 * v_k_safe, 0.0)
        e_base = max(c_eq / v_k_safe, 1.0e-8)
        i_base = 0.5 * e_base

    e_used = e_override if e_override is not None else e_base
    i_used = i_override if i_override is not None else i_base

    if dynamics_cfg.kernel_H_mode == "ia":
        H_base = dynamics_cfg.H_factor * i_used * a_orbit_m
    elif dynamics_cfg.kernel_H_mode == "fixed":
        if dynamics_cfg.H_fixed_over_a is None:
            raise MarsDiskError("kernel_H_mode='fixed' requires H_fixed_over_a")
        H_base = dynamics_cfg.H_fixed_over_a * a_orbit_m
    else:
        raise MarsDiskError(f"Unknown kernel_H_mode={dynamics_cfg.kernel_H_mode}")

    H_base = max(H_base, 1.0e-12)
    H_k = np.full_like(np.asarray(sizes, dtype=float), H_base, dtype=float)
    return KernelEIState(e_base=e_base, i_base=i_base, e_used=float(e_used), i_used=float(i_used), H_k=H_k)


def compute_kernel_e_i_H(
    dynamics_cfg: "Dynamics",
    tau_eff: float,
    a_orbit_m: float,
    v_k: float,
    sizes: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    """Return ``(e_kernel, i_kernel, H_k)`` for the Smol collision kernel.

    - ``kernel_ei_mode='config'`` uses ``e0``/``i0`` directly.
    - ``kernel_ei_mode='wyatt_eq'`` solves for ``c_eq`` (using a constant
      restitution coefficient) and maps to ``e_kernel=c_eq/v_k`` with
      ``i_kernel=0.5 e_kernel``.
    - ``kernel_H_mode='ia'`` sets ``H_k = H_factor * i_kernel * a`` (all bins).
      ``'fixed'`` uses ``H_fixed_over_a * a`` if provided.
    """

    state = compute_kernel_ei_state(dynamics_cfg, tau_eff, a_orbit_m, v_k, sizes)
    return state.e_used, state.i_used, state.H_k


def step_collisions_smol_0d(
    psd_state: MutableMapping[str, np.ndarray | float],
    sigma_surf: float,
    *,
    dt: float,
    prod_subblow_area_rate: float,
    r: float,
    Omega: float,
    a_blow: float,
    rho: float,
    e_value: float,
    i_value: float,
    sigma_tau1: float | None,
    enable_blowout: bool,
    t_sink: float | None,
    ds_dt_val: float | None = None,
    s_min_effective: float | None = None,
    dynamics_cfg: "Dynamics | None" = None,
    tau_eff: float | None = None,
    collisions_enabled: bool = True,
    mass_conserving_sublimation: bool = False,
    supply_injection_mode: str = "min_bin",
    supply_s_inj_min: float | None = None,
    supply_s_inj_max: float | None = None,
    supply_q: float = 3.5,
    supply_velocity_cfg: "SupplyInjectionVelocity | None" = None,
) -> Smol0DStepResult:
    """Advance collisions+fragmentation in 0D using the Smol solver."""

    sigma_before_step = float(sigma_surf)
    sigma_clip_loss = 0.0
    sigma_for_step = sigma_before_step
    prod_requested = float(prod_subblow_area_rate)
    prod_subblow_area_rate = max(float(prod_subblow_area_rate), 0.0)
    if sigma_tau1 is not None and math.isfinite(sigma_tau1):
        sigma_for_step = float(min(sigma_for_step, sigma_tau1))
        headroom = max(sigma_tau1 - sigma_for_step, 0.0)
        if dt > 0.0 and headroom >= 0.0:
            prod_cap = headroom / dt
            if prod_subblow_area_rate > prod_cap:
                sigma_clip_loss = (prod_subblow_area_rate - prod_cap) * dt
                prod_subblow_area_rate = prod_cap
            # Guard against missing module logger in edge import contexts
            _logger = logger if "logger" in globals() else logging.getLogger(__name__)
            if prod_requested > 0.0 and prod_cap <= 0.0 and _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    "collisions_smol: supply headroom exhausted (sigma_tau1=%.3e, sigma=%.3e); prod clipped to zero",
                    sigma_tau1,
                    sigma_for_step,
                )

    sizes_arr, widths_arr, m_k, N_k, scale_to_sigma = smol.psd_state_to_number_density(
        psd_state,
        sigma_for_step,
        rho_fallback=rho,
    )
    if N_k.size == 0 or not np.isfinite(sigma_for_step):
        return Smol0DStepResult(
            psd_state,
            sigma_before_step,
            sigma_for_step,
            sigma_before_step - sigma_for_step,
            sigma_for_step,
            sigma_clip_loss,
            dt,
            0.0,
            prod_subblow_area_rate,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    if collisions_enabled:
        supply_weight = 0.0
        if dynamics_cfg is not None:
            kernel_state = compute_kernel_ei_state(
                dynamics_cfg,
                tau_eff if tau_eff is not None else 0.0,
                a_orbit_m=r,
                v_k=r * Omega,
                sizes=sizes_arr,
            )
        else:
            H_arr_default = np.full_like(N_k, max(r * max(i_value, 1.0e-6), 1.0e-6))
            kernel_state = KernelEIState(
                e_base=float(e_value),
                i_base=float(i_value),
                e_used=float(e_value),
                i_used=float(i_value),
                H_k=H_arr_default,
            )
        e_supply = kernel_state.e_base
        i_supply = kernel_state.i_base
        if supply_velocity_cfg is not None:
            delta_sigma_supply = max(prod_subblow_area_rate, 0.0) * dt
            supply_weight = _supply_velocity_weight(
                delta_sigma_supply,
                sigma_before_step,
                getattr(supply_velocity_cfg, "weight_mode", "delta_sigma"),
            )
            e_supply, i_supply = _resolve_supply_velocity(supply_velocity_cfg, kernel_state.e_base, kernel_state.i_base)
            e_eff, i_eff = _blend_supply_velocity(
                kernel_state.e_base,
                kernel_state.i_base,
                e_supply,
                i_supply,
                weight=supply_weight,
                mode=getattr(supply_velocity_cfg, "blend_mode", "rms"),
            )
            if dynamics_cfg is not None:
                kernel_state = compute_kernel_ei_state(
                    dynamics_cfg,
                    tau_eff if tau_eff is not None else 0.0,
                    a_orbit_m=r,
                    v_k=r * Omega,
                    sizes=sizes_arr,
                    e_override=e_eff,
                    i_override=i_eff,
                )
            else:
                H_arr_default = np.full_like(N_k, max(r * max(i_eff, 1.0e-6), 1.0e-6))
                kernel_state = KernelEIState(
                    e_base=kernel_state.e_base,
                    i_base=kernel_state.i_base,
                    e_used=float(e_eff),
                    i_used=float(i_eff),
                    H_k=H_arr_default,
                )
        e_kernel = kernel_state.e_used
        i_kernel = kernel_state.i_used
        H_arr = kernel_state.H_k
        v_rel_mode = getattr(dynamics_cfg, "v_rel_mode", "pericenter") if dynamics_cfg is not None else "pericenter"
        if v_rel_mode == "ohtsuki":
            warnings.warn(
                "v_rel_mode='ohtsuki' is deprecated for high-e discs; prefer 'pericenter'.",
                RuntimeWarning,
            )
        if v_rel_mode == "pericenter":
            v_rel_scalar = dynamics.v_rel_pericenter(e_kernel, v_k=r * Omega)
        else:
            v_rel_scalar = dynamics.v_ij(e_kernel, i_kernel, v_k=r * Omega)
        C_kernel = collide.compute_collision_kernel_C1(N_k, sizes_arr, H_arr, v_rel_scalar)
        t_coll_kernel = kernel_minimum_tcoll(C_kernel)
        Y_tensor = _fragment_tensor(sizes_arr, m_k, v_rel_scalar, rho)
    else:
        C_kernel = np.zeros((N_k.size, N_k.size))
        Y_tensor = np.zeros((N_k.size, N_k.size, N_k.size))
        t_coll_kernel = float("inf")
        e_kernel = None
        i_kernel = None
        e_supply = None
        i_supply = None
        supply_weight = 0.0
        H_arr = np.full_like(N_k, max(r * max(i_value, 1.0e-6), 1.0e-6))

    if collisions_enabled:
        e_kernel_base_val = kernel_state.e_base
        i_kernel_base_val = kernel_state.i_base
        e_kernel_supply_val = e_supply if e_supply is not None else kernel_state.e_base
        i_kernel_supply_val = i_supply if i_supply is not None else kernel_state.i_base
    else:
        e_kernel_base_val = float(e_value)
        i_kernel_base_val = float(i_value)
        e_kernel_supply_val = float(e_value)
        i_kernel_supply_val = float(i_value)
    e_kernel_effective_val = e_kernel
    i_kernel_effective_val = i_kernel
    supply_weight_val = supply_weight

    S_blow = _blowout_sink_vector(sizes_arr, a_blow, Omega, enable_blowout)

    S_sink = None
    mass_loss_rate_sink = 0.0
    if t_sink is not None and t_sink > 0.0:
        sink_rate = 1.0 / t_sink
        S_sink = np.full_like(N_k, sink_rate)
        mass_loss_rate_sink = float(np.sum(m_k * sink_rate * N_k))

    S_sub_k = None
    mass_loss_rate_sub = 0.0
    if ds_dt_val is not None:
        ds_dt_k = np.full_like(sizes_arr, float(ds_dt_val), dtype=float)
        if mass_conserving_sublimation and a_blow > 0.0 and dt > 0.0:
            mask = (ds_dt_k < 0.0) & np.isfinite(ds_dt_k) & (sizes_arr > a_blow)
            if np.any(mask):
                t_cross = (sizes_arr[mask] - a_blow) / np.abs(ds_dt_k[mask])
                t_cross = np.where(t_cross <= 0.0, np.inf, t_cross)
                mask_cross = t_cross <= dt
                if np.any(mask_cross):
                    t_cross_use = np.maximum(t_cross[mask_cross], 1.0e-30)
                    rates = 1.0 / t_cross_use
                    S_extra = np.zeros_like(sizes_arr, dtype=float)
                    S_extra_indices = np.nonzero(mask)[0][mask_cross]
                    S_extra[S_extra_indices] = rates
                    S_blow = S_blow + S_extra
        else:
            S_sub_k, mass_loss_rate_sub = sublimation_sink_from_dsdt(
                sizes_arr,
                N_k,
                ds_dt_k,
                m_k,
            )

    mass_loss_rate_blow = float(np.sum(m_k * S_blow * N_k))

    extra_mass_loss_rate = mass_loss_rate_blow + mass_loss_rate_sink + mass_loss_rate_sub

    prod_mass_rate_eff = prod_subblow_area_rate if dt > 0.0 else 0.0
    source_k = supply_mass_rate_to_number_source(
        prod_mass_rate_eff,
        sizes_arr,
        m_k,
        s_min_eff=s_min_effective if s_min_effective is not None else 0.0,
        widths=widths_arr,
        mode=supply_injection_mode,
        s_inj_min=supply_s_inj_min,
        s_inj_max=supply_s_inj_max,
        q=supply_q,
    )

    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        N_k,
        C_kernel,
        Y_tensor,
        S_blow,
        m_k,
        prod_subblow_mass_rate=prod_mass_rate_eff,
        dt=dt,
        source_k=source_k,
        S_external_k=S_sink,
        S_sublimation_k=S_sub_k,
        extra_mass_loss_rate=extra_mass_loss_rate,
    )

    psd_state, sigma_after, sigma_loss = smol.number_density_to_psd_state(
        N_new,
        psd_state,
        sigma_for_step,
        widths=widths_arr,
        m=m_k,
        scale_to_sigma=scale_to_sigma,
    )

    dSigma_dt_blowout = mass_loss_rate_blow
    dSigma_dt_sublimation = mass_loss_rate_sub
    dSigma_dt_sinks = mass_loss_rate_sink + dSigma_dt_sublimation

    return Smol0DStepResult(
        psd_state,
        sigma_before_step,
        sigma_after,
        sigma_loss,
        sigma_for_step,
        sigma_clip_loss,
        dt_eff,
        mass_err,
        prod_mass_rate_eff,
        dSigma_dt_blowout,
        dSigma_dt_sinks,
        dSigma_dt_sublimation,
        mass_loss_rate_blow,
        mass_loss_rate_sink,
        mass_loss_rate_sub,
        t_coll_kernel,
        e_kernel,
        i_kernel,
        e_kernel_base=e_kernel_base_val,
        i_kernel_base=i_kernel_base_val,
        e_kernel_supply=e_kernel_supply_val,
        i_kernel_supply=i_kernel_supply_val,
        e_kernel_effective=e_kernel_effective_val,
        i_kernel_effective=i_kernel_effective_val,
        supply_velocity_weight=supply_weight_val,
    )
