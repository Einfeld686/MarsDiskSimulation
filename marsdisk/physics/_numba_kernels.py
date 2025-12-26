"""Numba-accelerated kernels for performance-critical physics computations.

This module provides JIT-compiled implementations of computationally intensive
routines used in the Smoluchowski collision/fragmentation solver.  The functions
are designed as drop-in replacements for pure-Python/NumPy loops and are
activated automatically when :mod:`numba` is available.

The main acceleration targets are:

1. **Fragment tensor construction** (`_fragment_tensor`): The O(n²) loop that
   fills `Y[k, i, j]` is replaced with a parallelised Numba kernel using
   `prange` over the outer index.

2. **Weights table precomputation**: Power-law fragment weights are computed
   once and reused across all (i, j) pairs.

Usage
-----
These functions are not meant to be called directly.  Instead, the parent
module :mod:`marsdisk.physics.collisions_smol` checks for the availability
of the Numba implementations and uses them transparently when possible.

Notes
-----
* All kernels use ``cache=True`` to persist compiled bytecode across runs.
* ``parallel=True`` enables automatic threading via ``prange``; the number
  of threads respects ``NUMBA_NUM_THREADS`` (default: all cores).
* Fallback to pure NumPy is automatic if Numba is unavailable or compilation
  fails at import time.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit, prange
    _NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMBA_AVAILABLE = False

    # Provide dummy decorators so the module can still be imported
    def njit(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])

    def prange(*args, **kwargs):  # type: ignore[misc]
        return range(*args)

__all__ = [
    "NUMBA_AVAILABLE",
    "compute_weights_table_numba",
    "fill_fragment_tensor_numba",
    "gain_from_kernel_tensor_numba",
    "collision_kernel_numba",
    "collision_kernel_bookkeeping_numba",
    "compute_prod_subblow_area_rate_C2_numba",
    "loss_sum_numba",
    "mass_budget_error_numba",
    "gain_tensor_fallback_numba",
    "fragment_tensor_fallback_numba",
    "supply_mass_rate_powerlaw_numba",
    "blowout_sink_vector_numba",
    "compute_kernel_e_i_H_numba",
    "kernel_minimum_tcoll_numba",
    "size_drift_rebin_numba",
]


def NUMBA_AVAILABLE() -> bool:
    """Return True if Numba JIT compilation is available."""
    return _NUMBA_AVAILABLE


# ---------------------------------------------------------------------------
# Weights table for power-law fragment distribution
# ---------------------------------------------------------------------------


@njit(cache=True)
def compute_weights_table_numba(
    edges: np.ndarray,
    alpha_frag: float,
) -> np.ndarray:
    """Precompute normalised power-law weights for fragment distribution.

    For each largest-remnant bin index ``k_lr``, the weights are based on
    integrating ``dM/ds ∝ s^{-alpha_frag}`` over each bin.
    """
    n = edges.shape[0] - 1
    table = np.zeros((n, n), dtype=np.float64)
    bin_integrals = np.zeros(n, dtype=np.float64)
    power = 1.0 - alpha_frag

    for k in range(n):
        left = edges[k]
        right = edges[k + 1]
        if left <= 0.0:
            left = 1.0e-30
        if right < left:
            right = left
        if abs(power) < 1.0e-12:
            bin_integrals[k] = np.log(right / left)
        else:
            bin_integrals[k] = (right ** power - left ** power) / power
        if not np.isfinite(bin_integrals[k]) or bin_integrals[k] < 0.0:
            bin_integrals[k] = 0.0

    for k_lr in range(n):
        total = 0.0
        for k in range(k_lr + 1):
            total += bin_integrals[k]
        if total > 0.0:
            inv_total = 1.0 / total
            for k in range(k_lr + 1):
                table[k_lr, k] = bin_integrals[k] * inv_total
    return table


# ---------------------------------------------------------------------------
# Fragment tensor Y[k, i, j] construction
# ---------------------------------------------------------------------------


@njit(cache=True, parallel=True)
def fill_fragment_tensor_numba(
    Y: np.ndarray,
    n: int,
    valid_pair: np.ndarray,
    f_lr_matrix: np.ndarray,
    k_lr_matrix: np.ndarray,
    weights_table: np.ndarray,
) -> None:
    """Fill the fragment distribution tensor in-place using parallel loops.

    This kernel replaces the pure-Python double loop in ``_fragment_tensor``.
    The outer loop over ``i`` is parallelised with ``prange``.

    Parameters
    ----------
    Y : ndarray
        Output tensor of shape ``(n, n, n)`` to fill in-place.  Should be
        initialised to zeros before calling.
    n : int
        Number of size bins.
    valid_pair : ndarray
        Boolean mask of shape ``(n, n)`` indicating valid (i, j) pairs.
    f_lr_matrix : ndarray
        Largest-remnant mass fraction for each (i, j) pair, shape ``(n, n)``.
    k_lr_matrix : ndarray
        Bin index of the largest remnant for each (i, j) pair, shape ``(n, n)``.
        Values are integers cast to ``np.int64``.
    weights_table : ndarray
        Precomputed weights from :func:`compute_weights_table_numba`.
    """
    for i in prange(n):
        for j in range(n):
            if not valid_pair[i, j]:
                continue

            k_lr = k_lr_matrix[i, j]
            f_lr = f_lr_matrix[i, j]

            # Assign largest remnant fraction
            Y[k_lr, i, j] += f_lr

            # Distribute remainder according to power-law weights
            remainder = 1.0 - f_lr
            if remainder > 0.0:
                for k in range(k_lr + 1):
                    w = weights_table[k_lr, k]
                    if w > 0.0:
                        Y[k, i, j] += remainder * w


# ---------------------------------------------------------------------------
# Gain term and collision kernel helpers
# ---------------------------------------------------------------------------


@njit(cache=True, parallel=True)
def gain_from_kernel_tensor_numba(C: np.ndarray, Y: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Return gain vector using a parallelised triple loop over C and Y.

    The gain maps mass fractions in Y to number-source terms via (m_i+m_j)/m_k
    and sums only the upper-triangular collision pairs to avoid double counting.
    """

    n = C.shape[0]
    out = np.zeros(n, dtype=np.float64)
    for k in prange(n):
        acc = 0.0
        for i in range(n):
            m_i = m[i]
            for j in range(i, n):
                acc += C[i, j] * Y[k, i, j] * (m_i + m[j])
        if m[k] > 0.0:
            out[k] = acc / m[k]
        else:
            out[k] = 0.0
    return out


@njit(cache=True, parallel=True)
def collision_kernel_numba(
    N: np.ndarray,
    s: np.ndarray,
    H: np.ndarray,
    v_rel_scalar: float,
    v_rel_matrix: np.ndarray,
    use_matrix_velocity: bool,
) -> np.ndarray:
    """Compute the collision kernel with optional pair-specific velocities."""

    n = N.shape[0]
    kernel = np.zeros((n, n), dtype=np.float64)
    coeff = np.pi / np.sqrt(2.0 * np.pi)

    for i in prange(n):
        Ni = N[i]
        s_i = s[i]
        H_i = H[i]
        for j in range(n):
            Nj = N[j]
            v = v_rel_matrix[i, j] if use_matrix_velocity else v_rel_scalar
            s_sum = s_i + s[j]
            denom = np.sqrt(H_i * H_i + H[j] * H[j])
            base = Ni * Nj * (s_sum * s_sum) * v
            val = base * coeff / max(denom, 1.0e-30)
            if i == j:
                val *= 0.5
            kernel[i, j] = val

    return kernel


@njit(cache=True, parallel=True)
def collision_kernel_bookkeeping_numba(
    N: np.ndarray,
    s: np.ndarray,
    H: np.ndarray,
    m: np.ndarray,
    v_rel_scalar: float,
    v_rel_matrix: np.ndarray,
    use_matrix_velocity: bool,
    f_ke_matrix: np.ndarray,
    F_lf_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute ``C`` together with energy bookkeeping statistics.

    Returns
    -------
    (kernel, stats)
        ``kernel`` is the collision matrix (same形状 as ``N``).
        ``stats`` is a vector:
        [E_rel_step, E_dissipated_step, E_retained_step,
         f_ke_mean_C, f_ke_energy, F_lf_mean,
         n_cratering_rate, n_fragmentation_rate,
         frac_cratering, frac_fragmentation]
    """

    n = N.shape[0]
    kernel = np.zeros((n, n), dtype=np.float64)
    coeff = np.pi / np.sqrt(2.0 * np.pi)

    # Accumulators
    sum_C = 0.0
    sum_E_rel = 0.0
    sum_E_ret = 0.0
    sum_f_ke_C = 0.0
    sum_F_lf_C = 0.0
    sum_C_crat = 0.0
    sum_C_frag = 0.0

    for i in prange(n):
        Ni = N[i]
        s_i = s[i]
        H_i = H[i]
        m_i = m[i]
        for j in range(n):
            Nj = N[j]
            v = v_rel_matrix[i, j] if use_matrix_velocity else v_rel_scalar
            s_sum = s_i + s[j]
            denom = np.sqrt(H_i * H_i + H[j] * H[j])
            base = Ni * Nj * (s_sum * s_sum) * v
            val = base * coeff / max(denom, 1.0e-30)
            if i == j:
                val *= 0.5
            kernel[i, j] = val

            # Only accumulate upper triangle
            if j < i:
                continue

            Cij = val
            sum_C += Cij
            # reduced mass
            m_j = m[j]
            m_tot = m_i + m_j
            mu = (m_i * m_j / m_tot) if m_tot > 0.0 else 0.0
            E_rel = 0.5 * mu * v * v

            f_ke = f_ke_matrix[i, j]
            F_lf = F_lf_matrix[i, j]
            E_ret = f_ke * E_rel
            E_diss = E_rel - E_ret

            sum_E_rel += Cij * E_rel
            sum_E_ret += Cij * E_ret
            sum_f_ke_C += Cij * f_ke
            sum_F_lf_C += Cij * F_lf

            if F_lf > 0.5:
                sum_C_crat += Cij
            else:
                sum_C_frag += Cij

    denom_C = sum_C if sum_C > 0.0 else 1.0
    E_rel_step = sum_E_rel
    E_ret_step = sum_E_ret
    E_diss_step = sum_E_rel - sum_E_ret
    f_ke_mean_C = sum_f_ke_C / denom_C
    f_ke_energy = (E_ret_step / E_rel_step) if E_rel_step > 0.0 else 0.0
    F_lf_mean = sum_F_lf_C / denom_C

    denom_frac = sum_C_crat + sum_C_frag
    frac_crat = (sum_C_crat / denom_frac) if denom_frac > 0.0 else 0.0
    frac_frag = (sum_C_frag / denom_frac) if denom_frac > 0.0 else 0.0

    stats = np.array(
        [
            E_rel_step,
            E_diss_step,
            E_ret_step,
            f_ke_mean_C,
            f_ke_energy,
            F_lf_mean,
            sum_C_crat,
            sum_C_frag,
            frac_crat,
            frac_frag,
        ],
        dtype=np.float64,
    )
    return kernel, stats


# ---------------------------------------------------------------------------
# Additional helpers (NumPy fallbacks lifted into Numba)
# ---------------------------------------------------------------------------


@njit(cache=True)
def compute_prod_subblow_area_rate_C2_numba(C: np.ndarray, m_subblow: np.ndarray) -> float:
    """Upper-triangular inner product for sub-blowout production (C2)."""

    n = C.shape[0]
    acc = 0.0
    for i in range(n):
        for j in range(i, n):
            acc += C[i, j] * m_subblow[i, j]
    return acc


@njit(cache=True)
def loss_sum_numba(C: np.ndarray) -> np.ndarray:
    """Row-wise sum of the collision kernel."""

    n = C.shape[0]
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        acc = 0.0
        for j in range(n):
            acc += C[i, j]
        out[i] = acc
    return out


@njit(cache=True)
def mass_budget_error_numba(
    N_old: np.ndarray,
    N_new: np.ndarray,
    m: np.ndarray,
    prod_subblow_mass_rate: float,
    dt: float,
    extra_mass_loss_rate: float,
) -> float:
    """Mass budget error mirroring compute_mass_budget_error_C4."""

    M_before = 0.0
    M_after = 0.0
    n = N_old.shape[0]
    for k in range(n):
        M_before += m[k] * N_old[k]
        M_after += m[k] * N_new[k]
    prod_term = dt * prod_subblow_mass_rate
    extra_term = dt * extra_mass_loss_rate
    diff = M_after + extra_term - (M_before + prod_term)
    baseline = M_before if M_before > 0.0 else (M_before + prod_term if (M_before + prod_term) > 0.0 else 1.0e-30)
    if baseline == 0.0:
        baseline = 1.0e-30
    err = diff if diff >= 0.0 else -diff
    err /= baseline
    return err


@njit(cache=True, parallel=True)
def gain_tensor_fallback_numba(C: np.ndarray, Y: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Triple-loop gain term used when the main Numba kernel is unavailable."""

    n = C.shape[0]
    out = np.zeros(n, dtype=np.float64)
    for k in prange(n):
        acc = 0.0
        for i in range(n):
            m_i = m[i]
            for j in range(i, n):
                acc += C[i, j] * Y[k, i, j] * (m_i + m[j])
        if m[k] > 0.0:
            out[k] = acc / m[k]
        else:
            out[k] = 0.0
    return out


@njit(cache=True)
def fragment_tensor_fallback_numba(
    edges: np.ndarray,
    valid_pair: np.ndarray,
    f_lr_matrix: np.ndarray,
    k_lr_matrix: np.ndarray,
    alpha_frag: float,
) -> np.ndarray:
    """Pure-Python fallback ported to Numba (weights + triple loop)."""

    n = edges.shape[0] - 1
    Y = np.zeros((n, n, n), dtype=np.float64)
    bin_integrals = np.zeros(n, dtype=np.float64)
    power = 1.0 - alpha_frag

    for k in range(n):
        left = edges[k]
        right = edges[k + 1]
        if left <= 0.0:
            left = 1.0e-30
        if right < left:
            right = left
        if abs(power) < 1.0e-12:
            bin_integrals[k] = np.log(right / left)
        else:
            bin_integrals[k] = (right ** power - left ** power) / power
        if not np.isfinite(bin_integrals[k]) or bin_integrals[k] < 0.0:
            bin_integrals[k] = 0.0

    weights_table = np.zeros((n, n), dtype=np.float64)
    for k_lr in range(n):
        total = 0.0
        for k in range(k_lr + 1):
            total += bin_integrals[k]
        if total > 0.0:
            inv_total = 1.0 / total
            for k in range(k_lr + 1):
                weights_table[k_lr, k] = bin_integrals[k] * inv_total

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
            for k in range(k_lr + 1):
                w = weights_table[k_lr, k]
                if w > 0.0:
                    Y[k, i, j] += remainder_frac * w
    return Y


@njit(cache=True)
def supply_mass_rate_powerlaw_numba(
    s_arr: np.ndarray,
    m_arr: np.ndarray,
    widths_arr: np.ndarray,
    prod_rate: float,
    inj_floor: float,
    inj_ceiling: float,
    q: float,
) -> np.ndarray:
    """Distribute supply over bins with dN/ds ∝ s^{-q} using bin overlaps."""

    n = s_arr.shape[0]
    out = np.zeros_like(m_arr)
    if prod_rate <= 0.0 or n == 0:
        return out

    weights = np.zeros_like(s_arr)
    for k in range(n):
        width = widths_arr[k]
        if width <= 0.0:
            continue
        left = s_arr[k] - 0.5 * width
        if left < 0.0:
            left = 0.0
        right = left + width
        overlap_left = left if left > inj_floor else inj_floor
        overlap_right = right if right < inj_ceiling else inj_ceiling
        if overlap_right <= overlap_left:
            continue
        if abs(q - 1.0) < 1.0e-8:
            val = np.log(overlap_right / overlap_left)
        else:
            power = 1.0 - q
            val = (overlap_right ** power - overlap_left ** power) / power
        if np.isfinite(val) and val > 0.0:
            weights[k] = val

    mass_sum = 0.0
    for k in range(n):
        mass_sum += weights[k] * m_arr[k]
    if mass_sum <= 0.0:
        return out

    for k in range(n):
        if weights[k] <= 0.0 or m_arr[k] <= 0.0:
            continue
        out[k] = weights[k] * prod_rate / mass_sum
    return out


@njit(cache=True)
def blowout_sink_vector_numba(
    sizes: np.ndarray,
    a_blow: float,
    rate: float,
    enable_blowout: bool,
) -> np.ndarray:
    """Per-bin blow-out sink rates."""

    n = sizes.shape[0]
    out = np.zeros(n, dtype=np.float64)
    if (not enable_blowout) or rate <= 0.0:
        return out
    for k in range(n):
        out[k] = rate if sizes[k] <= a_blow else 0.0
    return out


@njit(cache=True)
def _solve_c_eq_constant_eps_numba(
    tau: float,
    e_guess: float,
    f_wake: float,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    """Fixed-point iteration with constant restitution (ε=0.5)."""

    if tau < 0.0 or f_wake < 1.0:
        return -1.0
    c = e_guess if e_guess > 1.0e-6 else 1.0e-6
    for _ in range(max_iter):
        eps = 0.5
        denom = 1.0 - eps * eps
        if denom <= 0.0:
            denom = 1.0e-12
        c_new = (f_wake * tau / denom) ** 0.5
        if abs(c_new - c) <= tol * max(c_new, 1.0):
            return c_new
        c = 0.5 * (c + c_new)
    return -1.0


@njit(cache=True)
def compute_kernel_e_i_H_numba(
    sizes: np.ndarray,
    tau_eff: float,
    a_orbit_m: float,
    v_k: float,
    e0: float,
    i0: float,
    H_factor: float,
    H_fixed_over_a: float,
    kernel_ei_mode_flag: int,
    kernel_H_mode_flag: int,
    f_wake: float,
) -> tuple[float, float, np.ndarray]:
    """Numba helper mirroring compute_kernel_e_i_H for simple configs."""

    v_k_safe = v_k if v_k > 1.0e-12 else 1.0e-12
    e_base = e0
    i_base = i0
    if kernel_ei_mode_flag == 1:
        c_eq = _solve_c_eq_constant_eps_numba(
            tau_eff if tau_eff > 0.0 else 0.0,
            e0 if e0 > 1.0e-6 else 1.0e-6,
            f_wake if f_wake > 1.0 else 1.0,
        )
        if c_eq > 0.0:
            e_base = c_eq / v_k_safe
            if e_base < 1.0e-8:
                e_base = 1.0e-8
            i_base = 0.5 * e_base
        else:
            e_base = e0 * v_k_safe
            i_base = 0.5 * e_base

    e_used = e_base
    i_used = i_base

    if kernel_H_mode_flag == 1:
        H_base = H_fixed_over_a * a_orbit_m
    else:
        H_base = H_factor * i_used * a_orbit_m
    if (not np.isfinite(H_base)) or H_base <= 0.0:
        H_base = 1.0e-12

    H_k = np.full_like(sizes, H_base, dtype=np.float64)
    return float(e_used), float(i_used), H_k


@njit(cache=True)
def kernel_minimum_tcoll_numba(C_kernel: np.ndarray) -> float:
    """Minimum collisional timescale from kernel row sums."""

    n = C_kernel.shape[0]
    if n == 0:
        return np.inf
    rate_max = 0.0
    for i in range(n):
        acc = 0.0
        for j in range(n):
            acc += C_kernel[i, j]
        if acc > rate_max:
            rate_max = acc
    if rate_max <= 0.0:
        return np.inf
    return 1.0 / rate_max


@njit(cache=True)
def size_drift_rebin_numba(
    sizes: np.ndarray,
    number: np.ndarray,
    edges: np.ndarray,
    ds_step: float,
    floor_val: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Rebin number densities after a uniform size drift."""

    n = sizes.shape[0]
    new_number = np.zeros(n, dtype=np.float64)
    accum_sizes = np.zeros(n, dtype=np.float64)
    for idx in range(n):
        n_val = number[idx]
        if n_val <= 0.0 or not np.isfinite(n_val):
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor_val:
            s_new = floor_val
        target = np.searchsorted(edges, s_new, side="right") - 1
        if target < 0:
            target = 0
        elif target >= n:
            target = n - 1
        new_number[target] += n_val
        accum_sizes[target] += n_val * s_new
    return new_number, accum_sizes
