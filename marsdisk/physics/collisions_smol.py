from __future__ import annotations

"""Smoluchowski collision+fragmentation step specialised for the 0D loop."""

import math
import os
import warnings
from dataclasses import dataclass
from typing import MutableMapping, TYPE_CHECKING

import numpy as np
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
    from ..schema import Dynamics


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


def supply_mass_rate_to_number_source(
    prod_subblow_mass_rate: float,
    s_bin_center: np.ndarray,
    m_bin: np.ndarray,
    s_min_eff: float,
) -> np.ndarray:
    """Convert a mass flux to a per-bin number source ``F_k`` (1/s).

    The mapping injects all supplied mass into the smallest bin with
    ``s >= s_min_eff`` (falling back to the last bin) so that
    ``sum(m_k * F_k) == prod_subblow_mass_rate`` holds by construction.
    Negative mass fluxes are treated as zero.
    """

    prod_rate = max(float(prod_subblow_mass_rate), 0.0)
    s_arr = np.asarray(s_bin_center, dtype=float)
    m_arr = np.asarray(m_bin, dtype=float)
    if s_arr.shape != m_arr.shape:
        raise MarsDiskError("s_bin_center and m_bin must share the same shape")
    if prod_rate <= 0.0 or s_arr.size == 0:
        return np.zeros_like(m_arr)

    candidates = np.nonzero(s_arr >= s_min_eff)[0]
    k_inj = int(candidates[0]) if candidates.size else int(len(s_arr) - 1)

    F = np.zeros_like(m_arr, dtype=float)
    if m_arr[k_inj] > 0.0:
        F[k_inj] = prod_rate / m_arr[k_inj]
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

    tau_eff = max(float(tau_eff), 0.0)
    e_kernel = float(dynamics_cfg.e0)
    i_kernel = float(dynamics_cfg.i0)
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
        e_kernel = max(c_eq / v_k_safe, 1.0e-8)
        i_kernel = 0.5 * e_kernel

    if dynamics_cfg.kernel_H_mode == "ia":
        H_base = dynamics_cfg.H_factor * i_kernel * a_orbit_m
    elif dynamics_cfg.kernel_H_mode == "fixed":
        if dynamics_cfg.H_fixed_over_a is None:
            raise MarsDiskError("kernel_H_mode='fixed' requires H_fixed_over_a")
        H_base = dynamics_cfg.H_fixed_over_a * a_orbit_m
    else:
        raise MarsDiskError(f"Unknown kernel_H_mode={dynamics_cfg.kernel_H_mode}")

    H_base = max(H_base, 1.0e-12)
    H_k = np.full_like(np.asarray(sizes, dtype=float), H_base, dtype=float)
    return e_kernel, i_kernel, H_k


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
) -> Smol0DStepResult:
    """Advance collisions+fragmentation in 0D using the Smol solver."""

    sigma_before_step = float(sigma_surf)
    sigma_clip_loss = 0.0
    sigma_for_step = sigma_before_step
    prod_subblow_area_rate = max(float(prod_subblow_area_rate), 0.0)
    if sigma_tau1 is not None and math.isfinite(sigma_tau1):
        sigma_for_step = float(min(sigma_for_step, sigma_tau1))
        headroom = max(sigma_tau1 - sigma_for_step, 0.0)
        if dt > 0.0 and headroom >= 0.0:
            prod_cap = headroom / dt
            if prod_subblow_area_rate > prod_cap:
                sigma_clip_loss = (prod_subblow_area_rate - prod_cap) * dt
                prod_subblow_area_rate = prod_cap

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
        if dynamics_cfg is not None:
            e_kernel, i_kernel, H_arr = compute_kernel_e_i_H(
                dynamics_cfg,
                tau_eff if tau_eff is not None else 0.0,
                a_orbit_m=r,
                v_k=r * Omega,
                sizes=sizes_arr,
            )
        else:
            e_kernel = e_value
            i_kernel = i_value
            H_arr = np.full_like(N_k, max(r * max(i_value, 1.0e-6), 1.0e-6))
        v_rel_scalar = dynamics.v_ij(e_kernel, i_kernel, v_k=r * Omega)
        C_kernel = collide.compute_collision_kernel_C1(N_k, sizes_arr, H_arr, v_rel_scalar)
        t_coll_kernel = kernel_minimum_tcoll(C_kernel)
        Y_tensor = _fragment_tensor(sizes_arr, m_k, v_rel_scalar, rho)
    else:
        C_kernel = np.zeros((N_k.size, N_k.size))
        Y_tensor = np.zeros((N_k.size, N_k.size, N_k.size))
        t_coll_kernel = float("inf")

    S_blow = _blowout_sink_vector(sizes_arr, a_blow, Omega, enable_blowout)
    mass_loss_rate_blow = float(np.sum(m_k * S_blow * N_k))

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
        S_sub_k, mass_loss_rate_sub = sublimation_sink_from_dsdt(
            sizes_arr,
            N_k,
            ds_dt_k,
            m_k,
        )

    extra_mass_loss_rate = mass_loss_rate_blow + mass_loss_rate_sink + mass_loss_rate_sub

    prod_mass_rate_eff = prod_subblow_area_rate if dt > 0.0 else 0.0
    source_k = supply_mass_rate_to_number_source(
        prod_mass_rate_eff,
        sizes_arr,
        m_k,
        s_min_eff=s_min_effective if s_min_effective is not None else 0.0,
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
    )
