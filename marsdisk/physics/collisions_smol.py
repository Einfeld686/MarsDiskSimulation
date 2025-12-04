from __future__ import annotations

"""Smoluchowski collision+fragmentation step specialised for the 0D loop."""

import math
from dataclasses import dataclass
from typing import MutableMapping

import numpy as np
from ..errors import MarsDiskError
from . import collide, dynamics, qstar, smol
from .fragments import compute_largest_remnant_mass_fraction_F2
from .sublimation import sublimation_sink_from_dsdt


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


def _fragment_tensor(
    sizes: np.ndarray,
    masses: np.ndarray,
    v_rel: float | np.ndarray,
    rho: float,
    alpha_frag: float = 3.5,
) -> np.ndarray:
    """Return a mass-conserving fragment distribution ``Y[k, i, j]``."""

    n = sizes.size
    Y = np.zeros((n, n, n))
    if n == 0:
        return Y

    v_matrix = v_rel
    if np.isscalar(v_rel):
        v_matrix = np.full((n, n), float(v_rel), dtype=float)
    else:
        v_matrix = np.asarray(v_rel, dtype=float)
        if v_matrix.shape != (n, n):
            raise MarsDiskError("v_rel must be scalar or (n, n)")

    for i in range(n):
        for j in range(n):
            m1 = masses[i]
            m2 = masses[j]
            m_tot = m1 + m2
            if m1 <= 0.0 or m2 <= 0.0 or m_tot <= 0.0:
                continue
            v_pair = max(float(v_matrix[i, j]), 1.0e-12)
            v_kms = v_pair / 1.0e3
            size_ref = max(sizes[i], sizes[j])
            q_star = qstar.compute_q_d_star_F1(size_ref, rho, v_kms)
            f_lr = compute_largest_remnant_mass_fraction_F2(m1, m2, v_pair, q_star)
            m_lr = f_lr * m_tot
            k_lr = int(max(i, j))
            Y[k_lr, i, j] += m_lr / m_tot

            remainder = m_tot - m_lr
            if remainder <= 0.0:
                continue
            weights = sizes[: k_lr + 1] ** (-alpha_frag)
            weights_sum = float(np.sum(weights))
            if weights_sum <= 0.0:
                continue
            frac_vec = remainder / m_tot * (weights / weights_sum)
            Y[: k_lr + 1, i, j] += frac_vec

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
) -> Smol0DStepResult:
    """Advance collisions+fragmentation in 0D using the Smol solver."""

    sigma_before_step = float(sigma_surf)
    sigma_target = sigma_before_step + prod_subblow_area_rate * dt
    sigma_clip_loss = 0.0
    sigma_for_step = sigma_target
    if sigma_tau1 is not None and math.isfinite(sigma_tau1):
        if sigma_target > sigma_tau1:
            sigma_clip_loss = max(sigma_target - sigma_tau1, 0.0)
        sigma_for_step = float(min(sigma_target, sigma_tau1))

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

    H_arr = np.full_like(N_k, max(r * max(i_value, 1.0e-6), 1.0e-6))
    v_rel_scalar = dynamics.v_ij(e_value, i_value, v_k=r * Omega)
    C_kernel = collide.compute_collision_kernel_C1(N_k, sizes_arr, H_arr, v_rel_scalar)
    Y_tensor = _fragment_tensor(sizes_arr, m_k, v_rel_scalar, rho)

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
    if sigma_clip_loss > 0.0 and dt > 0.0:
        extra_mass_loss_rate += sigma_clip_loss / dt

    prod_mass_rate_eff = (sigma_for_step - sigma_before_step + sigma_clip_loss) / dt if dt > 0.0 else 0.0

    N_new, dt_eff, mass_err = smol.step_imex_bdf1_C3(
        N_k,
        C_kernel,
        Y_tensor,
        S_blow,
        m_k,
        prod_subblow_mass_rate=prod_mass_rate_eff,
        dt=dt,
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
    if sigma_clip_loss > 0.0 and dt > 0.0:
        dSigma_dt_sinks += sigma_clip_loss / dt

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
    )
