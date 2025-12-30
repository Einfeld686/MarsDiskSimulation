from __future__ import annotations

"""Smoluchowski collision+fragmentation step specialised for the 0D loop."""

import math
import os
import threading
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from typing import MutableMapping, TYPE_CHECKING

import numpy as np
import logging
from ..errors import MarsDiskError
from ..warnings import NumericalWarning, PhysicsWarning
from . import collide, dynamics, qstar, smol
from .fragments import largest_remnant_fraction_array, q_r_array
from .sublimation import sublimation_sink_from_dsdt

# Numba-accelerated kernels (optional)
try:
    from ._numba_kernels import (
        NUMBA_AVAILABLE,
        compute_weights_table_numba,
        fill_fragment_tensor_numba,
        fragment_tensor_fallback_numba,
        blowout_sink_vector_numba,
        supply_mass_rate_powerlaw_numba,
        kernel_minimum_tcoll_numba,
        compute_kernel_e_i_H_numba,
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
# Honour opt-out for collision caches to ease A/B comparisons.
_CACHE_DISABLED_ENV = os.environ.get("MARSDISK_DISABLE_COLLISION_CACHE", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_CACHE_ENABLED = not _CACHE_DISABLED_ENV
# Set to True after a runtime failure to avoid repeatedly calling broken JIT kernels.
_NUMBA_FAILED = False
_THREAD_LOCAL = threading.local()
_F_KE_MISMATCH_WARNED = False
_F_KE_MISMATCH_WARN_THRESHOLD = 0.1
H_OVER_A_WARN_THRESHOLD = 1.0e-8

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
    gain_mass_rate: float | None = None
    loss_mass_rate: float | None = None
    sink_mass_rate: float | None = None
    source_mass_rate: float | None = None
    sigma_spill: float = 0.0
    dSigma_dt_spill: float = 0.0
    mass_loss_rate_spill: float = 0.0
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
    energy_stats: np.ndarray | None = None
    f_ke_eps_mismatch: float | None = None
    e_next: float | None = None
    i_next: float | None = None
    e_eq_target: float | None = None
    t_damp_used: float | None = None


@dataclass
class KernelEIState:
    """Baseline and effective eccentricity/inclination for the collision kernel."""

    e_base: float
    i_base: float
    e_used: float
    i_used: float
    H_k: np.ndarray


@dataclass
class TimeOrbitParams:
    """Group A: 時間・軌道パラメータ."""

    dt: float
    Omega: float
    r: float
    t_blow: float | None = None


@dataclass
class FragmentWorkspace:
    """Cached size-dependent arrays for fragment tensor construction."""

    sizes_key: tuple
    rho: float
    m1: np.ndarray
    m2: np.ndarray
    m_tot: np.ndarray
    valid_pair: np.ndarray
    size_ref: np.ndarray


def _array_fingerprint(arr: np.ndarray) -> tuple[int, float, float, float, float]:
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return (0, 0.0, 0.0, 0.0, 0.0)
    return (
        int(arr.size),
        float(arr[0]),
        float(arr[-1]),
        float(np.sum(arr)),
        float(np.sum(arr * arr)),
    )


def _versioned_key(version: int | None, arr: np.ndarray, *, tag: str) -> tuple:
    if version is not None:
        return (tag, int(version))
    return (tag,) + _array_fingerprint(arr)


def _get_thread_cache(name: str) -> "OrderedDict[tuple, object]":
    cache = getattr(_THREAD_LOCAL, name, None)
    if cache is None:
        cache = OrderedDict()
        setattr(_THREAD_LOCAL, name, cache)
    return cache


@dataclass
class MaterialParams:
    """Group B: 物質パラメータ."""

    rho: float
    a_blow: float
    s_min_effective: float | None


@dataclass
class DynamicsParams:
    """Group C: 力学パラメータ."""

    e_value: float
    i_value: float
    dynamics_cfg: "Dynamics | None"
    tau_eff: float | None


@dataclass
class SupplyParams:
    """Group D: 供給パラメータ."""

    prod_subblow_area_rate: float
    supply_injection_mode: str
    supply_s_inj_min: float | None
    supply_s_inj_max: float | None
    supply_q: float
    supply_mass_weights: np.ndarray | None
    supply_velocity_cfg: "SupplyInjectionVelocity | None"


@dataclass
class CollisionControlFlags:
    """Group E: 制御フラグ."""

    enable_blowout: bool
    collisions_enabled: bool
    mass_conserving_sublimation: bool
    headroom_policy: str
    sigma_tau1: float | None
    t_sink: float | None
    ds_dt_val: float | None
    energy_bookkeeping_enabled: bool = False
    eps_restitution: float = 0.5
    f_ke_cratering: float = 0.1
    f_ke_fragmentation: float | None = None


@dataclass
class CollisionStepContext:
    """衝突ステップの統合コンテキスト."""

    time_orbit: TimeOrbitParams
    material: MaterialParams
    dynamics: DynamicsParams
    supply: SupplyParams
    control: CollisionControlFlags
    sigma_surf: float
    enable_e_damping: bool = False
    t_coll_for_damp: float | None = None


def supply_mass_rate_to_number_source(
    prod_subblow_mass_rate: float,
    s_bin_center: np.ndarray,
    m_bin: np.ndarray,
    s_min_eff: float,
    *,
    widths: np.ndarray | None = None,
    mass_weights: np.ndarray | None = None,
    mode: str = "min_bin",
    s_inj_min: float | None = None,
    s_inj_max: float | None = None,
    q: float = 3.5,
    sizes_version: int | None = None,
    edges_version: int | None = None,
) -> np.ndarray:
    """Convert a mass flux to a per-bin number source ``F_k`` (1/s).

    The default mapping injects all supplied mass into the smallest bin with
    ``s >= s_min_eff`` (falling back to the last bin) so that
    ``sum(m_k * F_k) == prod_subblow_mass_rate`` holds by construction.
    When ``mode='powerlaw_bins'`` the mass is distributed over bins in the
    range ``[s_inj_min, s_inj_max]`` with ``dN/ds ∝ s^{-q}``, scaled to
    preserve the total supplied mass. When ``mode='initial_psd'`` the supplied
    mass follows the provided per-bin mass weights. Negative mass fluxes are
    treated as zero.
    """

    global _NUMBA_FAILED
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
    if mode_normalised == "initial_psd":
        if mass_weights is None:
            raise MarsDiskError("initial_psd mode requires mass_weights")
        weights_arr = np.asarray(mass_weights, dtype=float)
        if weights_arr.shape != s_arr.shape:
            raise MarsDiskError("mass_weights must match the shape of s_bin_center")
        weights_arr = np.where(np.isfinite(weights_arr) & (weights_arr > 0.0), weights_arr, 0.0)
        weights_sum = float(np.sum(weights_arr))
        if weights_sum <= 0.0:
            raise MarsDiskError("initial_psd mass_weights must sum to a positive value")
        weights_arr = weights_arr / weights_sum
        F_weights = np.zeros_like(m_arr, dtype=float)
        positive = (weights_arr > 0.0) & (m_arr > 0.0)
        if np.any(positive):
            F_weights[positive] = prod_rate * weights_arr[positive] / m_arr[positive]
        return F_weights

    inj_floor = float(max(s_min_eff, 0.0))
    if s_inj_min is not None and math.isfinite(s_inj_min):
        inj_floor = max(inj_floor, float(s_inj_min))

    def _inject_min_bin(effective_floor: float) -> np.ndarray:
        k_inj = int(np.searchsorted(s_arr, effective_floor, side="left"))
        if k_inj >= len(s_arr):
            k_inj = int(len(s_arr) - 1)
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

    if not _CACHE_ENABLED:
        if _USE_NUMBA and not _NUMBA_FAILED:
            try:
                return supply_mass_rate_powerlaw_numba(
                    s_arr.astype(np.float64),
                    m_arr.astype(np.float64),
                    widths_arr.astype(np.float64),
                    float(prod_rate),
                    float(inj_floor),
                    float(inj_ceiling),
                    float(q),
                )
            except Exception as exc:  # pragma: no cover - fallback
                _NUMBA_FAILED = True
                warnings.warn(
                    f"supply_mass_rate_to_number_source: numba powerlaw kernel failed ({exc!r}); falling back to NumPy.",
                    NumericalWarning,
                )

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
        mass_sum = float(np.sum(weights * m_arr))
        if mass_sum <= 0.0:
            return _inject_min_bin(inj_floor)
        F = np.zeros_like(m_arr, dtype=float)
        positive = (weights > 0.0) & (m_arr > 0.0)
        if np.any(positive):
            F[positive] = weights[positive] * prod_rate / mass_sum
        return F

    sizes_key = _versioned_key(sizes_version, s_arr, tag="sizes")
    edges_key = _versioned_key(edges_version, widths_arr, tag="edges")
    m_key = _array_fingerprint(m_arr)
    cache_key = ("powerlaw", sizes_key, edges_key, m_key, float(inj_floor), float(inj_ceiling), float(q))

    cache = _get_thread_cache("supply_cache")
    cached = cache.get(cache_key)
    if cached is not None:
        cache.move_to_end(cache_key)
        weights, mass_sum = cached
    else:
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
        mass_sum = float(np.sum(weights * m_arr))
        weights.setflags(write=False)
        cache[cache_key] = (weights, mass_sum)
        cache.move_to_end(cache_key)
        if len(cache) > _SUPPLY_CACHE_MAX:
            cache.popitem(last=False)

    if mass_sum <= 0.0:
        return _inject_min_bin(inj_floor)

    F = np.zeros_like(m_arr, dtype=float)
    positive = (weights > 0.0) & (m_arr > 0.0)
    if np.any(positive):
        F[positive] = weights[positive] * prod_rate / mass_sum
    return F


_FRAG_CACHE: dict[tuple, np.ndarray] = {}
_FRAG_CACHE_MAX = 32
_FRAG_CACHE_LOCK = threading.Lock()
_WEIGHTS_CACHE_MAX = 16
_QSTAR_CACHE_MAX = 8
_SUPPLY_CACHE_MAX = 16

# Cache keys cover size/edge versions (or fingerprints), rho, scalar v_rel, alpha_frag,
# and the Q_D* signature to prevent cross-cell contamination in 1D runs.


def reset_collision_caches() -> None:
    """Clear run-local collision caches (fragment/weights/qstar/supply)."""

    with _FRAG_CACHE_LOCK:
        _FRAG_CACHE.clear()
    for name in ("weights_cache", "qstar_cache", "supply_cache"):
        cache = getattr(_THREAD_LOCAL, name, None)
        if cache is not None:
            cache.clear()
    if hasattr(_THREAD_LOCAL, "frag_ws"):
        _THREAD_LOCAL.frag_ws = None


def _get_fragment_workspace(
    sizes_arr: np.ndarray,
    masses_arr: np.ndarray,
    rho: float,
    sizes_key: tuple,
) -> FragmentWorkspace:
    if not _CACHE_ENABLED:
        m1 = masses_arr[:, None]
        m2 = masses_arr[None, :]
        m_tot = m1 + m2
        valid_pair = (m1 > 0.0) & (m2 > 0.0) & (m_tot > 0.0)
        size_ref = np.maximum.outer(sizes_arr, sizes_arr)
        return FragmentWorkspace(
            sizes_key=sizes_key,
            rho=float(rho),
            m1=m1,
            m2=m2,
            m_tot=m_tot,
            valid_pair=valid_pair,
            size_ref=size_ref,
        )
    workspace = getattr(_THREAD_LOCAL, "frag_ws", None)
    if workspace is not None:
        if workspace.sizes_key == sizes_key and workspace.rho == float(rho):
            expected_shape = (sizes_arr.size, sizes_arr.size)
            if (
                workspace.m1.shape == expected_shape
                and workspace.m2.shape == expected_shape
                and workspace.m_tot.shape == expected_shape
                and workspace.valid_pair.shape == expected_shape
                and workspace.size_ref.shape == expected_shape
            ):
                return workspace
    m1 = masses_arr[:, None]
    m2 = masses_arr[None, :]
    m_tot = m1 + m2
    valid_pair = (m1 > 0.0) & (m2 > 0.0) & (m_tot > 0.0)
    size_ref = np.maximum.outer(sizes_arr, sizes_arr)
    workspace = FragmentWorkspace(
        sizes_key=sizes_key,
        rho=float(rho),
        m1=m1,
        m2=m2,
        m_tot=m_tot,
        valid_pair=valid_pair,
        size_ref=size_ref,
    )
    _THREAD_LOCAL.frag_ws = workspace
    return workspace


def _get_weights_table(
    edges_arr: np.ndarray,
    alpha_frag: float,
    edges_key: tuple,
    *,
    prefer_numba: bool,
) -> np.ndarray:
    global _NUMBA_FAILED
    cache = None
    cache_key = None
    if _CACHE_ENABLED:
        cache = _get_thread_cache("weights_cache")
        cache_key = (edges_key, float(alpha_frag))
        cached = cache.get(cache_key)
        if cached is not None:
            cache.move_to_end(cache_key)
            return cached

    weights_table = None
    if prefer_numba and _NUMBA_AVAILABLE and not _NUMBA_FAILED:
        try:
            weights_table = compute_weights_table_numba(edges_arr, float(alpha_frag))
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"_fragment_tensor: numba weights_table failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
            weights_table = None

    if weights_table is None:
        n = edges_arr.size - 1
        left_edges = np.maximum(edges_arr[:-1], 1.0e-30)
        right_edges = np.maximum(edges_arr[1:], left_edges)
        power = 1.0 - float(alpha_frag)
        if abs(power) < 1.0e-12:
            bin_integrals = np.log(right_edges / left_edges)
        else:
            bin_integrals = (right_edges**power - left_edges**power) / power
        bin_integrals = np.where(
            np.isfinite(bin_integrals) & (bin_integrals > 0.0), bin_integrals, 0.0
        )
        weights_table = np.zeros((n, n), dtype=np.float64)
        for k_lr in range(n):
            weights = bin_integrals[: k_lr + 1]
            weights_sum = float(np.sum(weights))
            if weights_sum > 0.0:
                weights_table[k_lr, : k_lr + 1] = weights / weights_sum

    if not np.isfinite(weights_table).all():
        return weights_table
    if _CACHE_ENABLED and cache is not None and cache_key is not None:
        weights_table.setflags(write=False)
        cache[cache_key] = weights_table
        cache.move_to_end(cache_key)
        if len(cache) > _WEIGHTS_CACHE_MAX:
            cache.popitem(last=False)
    return weights_table


def _get_qstar_matrix(
    size_ref: np.ndarray,
    rho: float,
    v_matrix: np.ndarray,
    v_rel_scalar: float | None,
    sizes_key: tuple,
) -> np.ndarray:
    if v_rel_scalar is None:
        return qstar.compute_q_d_star_array(size_ref, rho, v_matrix / 1.0e3)
    v_rel_use = max(float(v_rel_scalar), 1.0e-12)  # m/s; converted to km/s below
    if not _CACHE_ENABLED:
        return qstar.compute_q_d_star_array(size_ref, rho, v_rel_use / 1.0e3)
    cache = _get_thread_cache("qstar_cache")
    qstar_sig = qstar.get_qdstar_signature()
    cache_key = (sizes_key, float(rho), float(v_rel_use), qstar_sig)
    cached = cache.get(cache_key)
    if cached is not None:
        cache.move_to_end(cache_key)
        return cached
    q_star_matrix = qstar.compute_q_d_star_array(size_ref, rho, v_rel_use / 1.0e3)
    q_star_matrix = np.asarray(q_star_matrix, dtype=float)
    if np.isfinite(q_star_matrix).all():
        q_star_matrix.setflags(write=False)
        cache[cache_key] = q_star_matrix
        cache.move_to_end(cache_key)
        if len(cache) > _QSTAR_CACHE_MAX:
            cache.popitem(last=False)
    return q_star_matrix


def _fragment_tensor(
    sizes: np.ndarray,
    masses: np.ndarray,
    edges: np.ndarray,
    v_rel: float | np.ndarray,
    rho: float,
    alpha_frag: float = 3.5,
    sizes_version: int | None = None,
    edges_version: int | None = None,
    *,
    use_numba: bool | None = None,
) -> np.ndarray:
    """Return a mass-conserving fragment distribution ``Y[k, i, j]``.

    When Numba is available, the inner loops are JIT-compiled and parallelised
    for significant speedup on multi-core systems.
    The fragment weights are computed by integrating a mass distribution
    ``dM/ds ∝ s^{-alpha_frag}`` over the bin edges.
    """
    global _NUMBA_FAILED

    sizes_arr = np.asarray(sizes, dtype=np.float64)
    masses_arr = np.asarray(masses, dtype=np.float64)
    edges_arr = np.asarray(edges, dtype=np.float64)
    if sizes_arr.shape != masses_arr.shape:
        raise MarsDiskError("sizes and masses must share the same shape")

    n = sizes_arr.size
    if n == 0:
        return np.zeros((0, 0, 0), dtype=np.float64)
    if edges_arr.shape != (n + 1,):
        raise MarsDiskError("edges must have length n_bins + 1")
    if rho <= 0.0:
        raise MarsDiskError("rho must be positive")

    sizes_key = _versioned_key(sizes_version, sizes_arr, tag="sizes")
    edges_key = _versioned_key(edges_version, edges_arr, tag="edges")

    is_scalar_v = np.isscalar(v_rel)
    v_rel_scalar = float(v_rel) if is_scalar_v else None
    use_cache = is_scalar_v and _CACHE_ENABLED
    cache_key: tuple | None = None
    if use_cache:
        cache_key = (
            "scalar",
            float(v_rel),
            float(rho),
            sizes_key,
            edges_key,
            float(alpha_frag),
        )
        with _FRAG_CACHE_LOCK:
            cached = _FRAG_CACHE.get(cache_key)
        if cached is not None:
            return cached

    if v_rel_scalar is not None:
        v_matrix = np.full((n, n), float(v_rel_scalar), dtype=np.float64)
    else:
        v_matrix = np.asarray(v_rel, dtype=np.float64)
        if v_matrix.shape != (n, n):
            raise MarsDiskError("v_rel must be scalar or (n, n)")
    v_matrix = np.maximum(v_matrix, 1.0e-12)

    # Precompute matrices needed for fragment distribution
    workspace = _get_fragment_workspace(sizes_arr, masses_arr, rho, sizes_key)
    m1 = workspace.m1
    m2 = workspace.m2
    m_tot = workspace.m_tot
    valid_pair = workspace.valid_pair
    size_ref = workspace.size_ref
    q_star_matrix = _get_qstar_matrix(size_ref, rho, v_matrix, v_rel_scalar, sizes_key)
    q_r_matrix = q_r_array(m1, m2, v_matrix)
    f_lr_matrix = np.clip(
        largest_remnant_fraction_array(q_r_matrix, q_star_matrix), 0.0, 1.0
    ).astype(np.float64)
    m_lr_matrix = f_lr_matrix * m_tot
    with np.errstate(invalid="ignore"):
        s_lr_matrix = np.where(
            valid_pair,
            (3.0 * m_lr_matrix / (4.0 * np.pi * float(rho))) ** (1.0 / 3.0),
            0.0,
        )
    k_lr_matrix = np.searchsorted(edges_arr, s_lr_matrix, side="right") - 1
    k_lr_matrix = np.clip(k_lr_matrix, 0, n - 1).astype(np.int64)

    # Output tensor
    Y = np.zeros((n, n, n), dtype=np.float64)

    # Decide whether to attempt JIT, with per-call override.
    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    if use_jit and not _NUMBA_AVAILABLE:
        use_jit = False

    # Branch: Numba-accelerated or pure Python fallback
    if use_jit:
        try:
            weights_table = _get_weights_table(
                edges_arr,
                alpha_frag,
                edges_key,
                prefer_numba=True,
            )
            fill_fragment_tensor_numba(
                Y, n, valid_pair, f_lr_matrix, k_lr_matrix, weights_table
            )
        except Exception as exc:  # pragma: no cover - exercised via fallback test
            # Reset and fall back to the pure-Python implementation.
            Y.fill(0.0)
            use_jit = False
            warnings.warn(
                f"_fragment_tensor: numba kernel failed ({exc!r}); falling back to pure Python.",
                NumericalWarning,
            )
            _NUMBA_FAILED = True

    used_fallback = False
    if (not use_jit) and _USE_NUMBA and not _NUMBA_FAILED and use_numba is not False:
        try:
            Y_num = fragment_tensor_fallback_numba(
                edges_arr, valid_pair, f_lr_matrix, k_lr_matrix, float(alpha_frag)
            )
            Y[:] = Y_num
            used_fallback = True
        except Exception as exc:  # pragma: no cover - exercised via fallback test
            _NUMBA_FAILED = True
            warnings.warn(
                f"_fragment_tensor: numba fallback failed ({exc!r}); falling back to pure Python.",
                NumericalWarning,
            )

    if not use_jit and not used_fallback:
        # Pure Python fallback (original implementation)
        weights_table = _get_weights_table(
            edges_arr,
            alpha_frag,
            edges_key,
            prefer_numba=False,
        )
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
        if not np.isfinite(Y).all():
            return Y
        with _FRAG_CACHE_LOCK:
            if len(_FRAG_CACHE) >= _FRAG_CACHE_MAX:
                _FRAG_CACHE.pop(next(iter(_FRAG_CACHE)))
            Y.setflags(write=False)
            _FRAG_CACHE[cache_key] = Y
    return Y


def _blowout_sink_vector(
    sizes: np.ndarray,
    a_blow: float,
    t_blow: float,
    enable_blowout: bool,
) -> np.ndarray:
    """Return per-bin blow-out sink rates (1/s)."""

    global _NUMBA_FAILED
    if not enable_blowout or not np.isfinite(t_blow) or t_blow <= 0.0:
        return np.zeros_like(sizes)
    rate = 1.0 / float(t_blow)
    threshold = float(a_blow) * (1.0 + 1.0e-12)
    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            return blowout_sink_vector_numba(
                np.asarray(sizes, dtype=np.float64),
                float(threshold),
                float(rate),
                bool(enable_blowout),
            )
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"_blowout_sink_vector: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
    return np.where(np.asarray(sizes, dtype=float) <= threshold, rate, 0.0)


def kernel_minimum_tcoll(C_kernel: np.ndarray, N: np.ndarray | None = None) -> float:
    """Return the minimum collisional time-scale implied by ``C``.

    When ``N`` is provided, the summed collision rate is converted to a
    per-particle loss coefficient via ``sum_j C_ij / N_i``.
    """

    global _NUMBA_FAILED
    if C_kernel.size == 0:
        return math.inf
    if _USE_NUMBA and not _NUMBA_FAILED and N is None:
        try:
            return float(kernel_minimum_tcoll_numba(np.asarray(C_kernel, dtype=np.float64)))
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"kernel_minimum_tcoll: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
    rates = np.sum(C_kernel, axis=1)
    if C_kernel.size:
        rates = rates + np.diagonal(C_kernel)
    if N is not None:
        N_arr = np.asarray(N, dtype=float)
        if N_arr.shape != rates.shape:
            raise MarsDiskError("N must have the same shape as the kernel diagonal")
        with np.errstate(divide="ignore", invalid="ignore"):
            rates = np.where(N_arr > 0.0, rates / N_arr, 0.0)
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
            c_eq *= v_k_safe
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


def _compute_ei_damping(
    e_curr: float,
    i_curr: float,
    *,
    dt: float,
    tau_eff: float | None,
    a_orbit_m: float,
    v_k: float,
    dynamics_cfg: "Dynamics | None",
    t_coll_ref: float | None,
    eps_restitution: float,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Return (e_next, i_next, t_damp, e_eq_target) for post-collision damping."""

    if dynamics_cfg is None:
        return None, None, None, None
    if t_coll_ref is None or not np.isfinite(t_coll_ref) or t_coll_ref <= 0.0 or dt <= 0.0:
        return None, None, None, None

    e_target = float(e_curr)
    try:
        def _eps_model(_v: float) -> float:
            return float(eps_restitution)

        tau_val = float(tau_eff) if tau_eff is not None and np.isfinite(tau_eff) else 0.0
        c_eq = dynamics.solve_c_eq(
            max(tau_val, 0.0),
            max(e_curr, 1.0e-8),
            _eps_model,
            f_wake=float(getattr(dynamics_cfg, "f_wake", 1.0)),
        )
        c_eq *= max(v_k, 1.0e-12)
        e_target = max(c_eq / max(v_k, 1.0e-12), 0.0)
    except Exception:
        e_target = float(e_curr)

    eps_sq = max(float(eps_restitution) * float(eps_restitution), 1.0e-12)
    t_damp = float(t_coll_ref) / eps_sq
    if not np.isfinite(t_damp) or t_damp <= 0.0:
        return None, None, None, None

    ratio_i = 0.5
    if e_curr > 0.0:
        ratio_i = max(i_curr, 0.0) / max(e_curr, 1.0e-12)
    i_target = ratio_i * e_target

    e_next = dynamics.update_e(float(e_curr), e_target, t_damp, dt)
    i_next = dynamics.update_e(float(i_curr), i_target, t_damp, dt)
    e_next = float(np.clip(e_next, 0.0, 0.999999))
    i_next = float(max(i_next, 0.0))
    return e_next, i_next, t_damp, e_target


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

    global _NUMBA_FAILED

    sizes_arr = np.asarray(sizes, dtype=float)
    mode_ei = getattr(dynamics_cfg, "kernel_ei_mode", "config")
    mode_H = getattr(dynamics_cfg, "kernel_H_mode", "ia")
    if mode_ei not in {"config", "wyatt_eq"}:
        raise MarsDiskError(f"Unknown kernel_ei_mode={mode_ei}")
    if mode_H not in {"ia", "fixed"}:
        raise MarsDiskError(f"Unknown kernel_H_mode={mode_H}")

    if mode_H == "fixed" and getattr(dynamics_cfg, "H_fixed_over_a", None) is None:
        raise MarsDiskError("kernel_H_mode='fixed' requires H_fixed_over_a")

    tau_val = float(tau_eff)
    a_val = float(a_orbit_m)
    v_k_val = float(v_k)
    e0_val = float(dynamics_cfg.e0)
    i0_val = float(dynamics_cfg.i0)
    H_factor_val = float(dynamics_cfg.H_factor)
    H_fixed_val = float(getattr(dynamics_cfg, "H_fixed_over_a", 0.0) or 0.0)
    f_wake_val = float(getattr(dynamics_cfg, "f_wake", 1.0))

    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            e_kernel, i_kernel, H_k = compute_kernel_e_i_H_numba(
                sizes_arr.astype(np.float64),
                tau_val,
                a_val,
                v_k_val,
                e0_val,
                i0_val,
                H_factor_val,
                H_fixed_val,
                1 if mode_ei == "wyatt_eq" else 0,
                1 if mode_H == "fixed" else 0,
                f_wake_val,
            )
            if a_val > 0.0 and H_k.size:
                ratio = float(np.min(H_k)) / a_val
                if np.isfinite(ratio) and ratio < H_OVER_A_WARN_THRESHOLD:
                    warnings.warn(
                        f"Kernel scale height H/a={ratio:.3e} below threshold; dt may collapse.",
                        NumericalWarning,
                    )
            return e_kernel, i_kernel, H_k
        except Exception as exc:  # pragma: no cover - fallback path
            _NUMBA_FAILED = True
            warnings.warn(
                f"compute_kernel_e_i_H: numba kernel failed ({exc!r}); falling back to Python.",
                NumericalWarning,
            )

    state = compute_kernel_ei_state(dynamics_cfg, tau_eff, a_orbit_m, v_k, sizes_arr)
    if a_orbit_m > 0.0 and state.H_k.size:
        ratio = float(np.min(state.H_k)) / float(a_orbit_m)
        if np.isfinite(ratio) and ratio < H_OVER_A_WARN_THRESHOLD:
            warnings.warn(
                f"Kernel scale height H/a={ratio:.3e} below threshold; dt may collapse.",
                NumericalWarning,
            )
    return state.e_used, state.i_used, state.H_k


def step_collisions(
    ctx: CollisionStepContext,
    psd_state: MutableMapping[str, np.ndarray | float],
) -> Smol0DStepResult:
    """Structured wrapper for the Smol 0D collision step."""

    return step_collisions_smol_0d(
        psd_state,
        ctx.sigma_surf,
        dt=ctx.time_orbit.dt,
        prod_subblow_area_rate=ctx.supply.prod_subblow_area_rate,
        r=ctx.time_orbit.r,
        Omega=ctx.time_orbit.Omega,
        t_blow=ctx.time_orbit.t_blow,
        a_blow=ctx.material.a_blow,
        rho=ctx.material.rho,
        e_value=ctx.dynamics.e_value,
        i_value=ctx.dynamics.i_value,
        sigma_tau1=ctx.control.sigma_tau1,
        enable_blowout=ctx.control.enable_blowout,
        t_sink=ctx.control.t_sink,
        ds_dt_val=ctx.control.ds_dt_val,
        s_min_effective=ctx.material.s_min_effective,
        dynamics_cfg=ctx.dynamics.dynamics_cfg,
        tau_eff=ctx.dynamics.tau_eff,
        collisions_enabled=ctx.control.collisions_enabled,
        mass_conserving_sublimation=ctx.control.mass_conserving_sublimation,
        supply_injection_mode=ctx.supply.supply_injection_mode,
        supply_s_inj_min=ctx.supply.supply_s_inj_min,
        supply_s_inj_max=ctx.supply.supply_s_inj_max,
        supply_q=ctx.supply.supply_q,
        supply_mass_weights=ctx.supply.supply_mass_weights,
        supply_velocity_cfg=ctx.supply.supply_velocity_cfg,
        headroom_policy=ctx.control.headroom_policy,
        energy_bookkeeping_enabled=ctx.control.energy_bookkeeping_enabled,
        f_ke_fragmentation=ctx.control.f_ke_fragmentation,
        f_ke_cratering=ctx.control.f_ke_cratering,
        eps_restitution=ctx.control.eps_restitution,
    )


def step_collisions_smol_0d(
    psd_state: MutableMapping[str, np.ndarray | float],
    sigma_surf: float,
    *,
    dt: float,
    prod_subblow_area_rate: float,
    r: float,
    Omega: float,
    t_blow: float | None = None,
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
    supply_mass_weights: np.ndarray | None = None,
    supply_velocity_cfg: "SupplyInjectionVelocity | None" = None,
    headroom_policy: str = "clip",
    energy_bookkeeping_enabled: bool = False,
    f_ke_fragmentation: float | None = None,
    f_ke_cratering: float = 0.1,
    eps_restitution: float = 0.5,
    enable_e_damping: bool = False,
    t_coll_for_damp: float | None = None,
) -> Smol0DStepResult:
    """Advance collisions+fragmentation in 0D using the Smol solver."""

    global _F_KE_MISMATCH_WARNED

    sigma_before_step = float(sigma_surf)
    sigma_clip_loss = 0.0
    sigma_for_step = sigma_before_step
    prod_subblow_area_rate = max(float(prod_subblow_area_rate), 0.0)

    sizes_arr, widths_arr, m_k, N_k, scale_to_sigma = smol.psd_state_to_number_density(
        psd_state,
        sigma_for_step,
        rho_fallback=rho,
    )
    sizes_version = psd_state.get("sizes_version")
    edges_version = psd_state.get("edges_version")
    energy_stats = None
    f_ke_eps_mismatch = None
    e_next_state = None
    i_next_state = None
    e_eq_target_state = None
    t_damp_used = None
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
            gain_mass_rate=0.0,
            loss_mass_rate=0.0,
            sink_mass_rate=0.0,
            source_mass_rate=0.0,
            energy_stats=None,
            f_ke_eps_mismatch=None,
            e_next=None,
            i_next=None,
            e_eq_target=None,
            t_damp_used=None,
        )

    kernel_workspace = None
    kernel_workspace_sizes_id = getattr(_THREAD_LOCAL, "kernel_ws_sizes_id", None)
    kernel_workspace_cached = getattr(_THREAD_LOCAL, "kernel_ws", None)
    sizes_ref = psd_state.get("sizes", None)
    sizes_ref_id = id(sizes_ref) if sizes_ref is not None else None
    if sizes_ref_id is not None and sizes_ref_id == kernel_workspace_sizes_id:
        kernel_workspace = kernel_workspace_cached
        if kernel_workspace is not None:
            expected_shape = (sizes_arr.size, sizes_arr.size)
            if (
                kernel_workspace.s_sum_sq.shape != expected_shape
                or kernel_workspace.delta.shape != expected_shape
            ):
                kernel_workspace = None
    if kernel_workspace is None:
        try:
            kernel_workspace = collide.prepare_collision_kernel_workspace(sizes_arr)
            _THREAD_LOCAL.kernel_ws = kernel_workspace
            _THREAD_LOCAL.kernel_ws_sizes_id = sizes_ref_id
        except Exception:
            kernel_workspace = None
            _THREAD_LOCAL.kernel_ws = None
            _THREAD_LOCAL.kernel_ws_sizes_id = None

    imex_workspace = getattr(_THREAD_LOCAL, "imex_ws", None)
    imex_workspace_key = getattr(_THREAD_LOCAL, "imex_ws_key", None)
    if imex_workspace is None or imex_workspace_key != N_k.shape:
        imex_workspace = smol.ImexWorkspace(
            gain=np.zeros_like(N_k, dtype=float),
            loss=np.zeros_like(N_k, dtype=float),
        )
        _THREAD_LOCAL.imex_ws = imex_workspace
        _THREAD_LOCAL.imex_ws_key = N_k.shape

    if collisions_enabled:
        supply_weight = 0.0
        if dynamics_cfg is not None:
            kernel_state = compute_kernel_ei_state(
                dynamics_cfg,
                tau_eff if tau_eff is not None else 0.0,
                a_orbit_m=r,
                v_k=r * Omega,
                sizes=sizes_arr,
                e_override=e_value,
                i_override=i_value,
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
                PhysicsWarning,
            )
        if v_rel_mode == "pericenter":
            v_rel_scalar = dynamics.v_rel_pericenter(e_kernel, v_k=r * Omega)
        else:
            v_rel_scalar = dynamics.v_ij(e_kernel, i_kernel, v_k=r * Omega)

        if enable_e_damping and t_coll_for_damp is not None and t_coll_for_damp > 0.0:
            eps_sq = max(eps_restitution * eps_restitution, 1.0e-12)
            t_damp = t_coll_for_damp / eps_sq
            decay = math.exp(-dt / max(t_damp, 1.0e-30))
            e_kernel = e_value + (e_kernel - e_value) * decay
            i_kernel = i_value + (i_kernel - i_value) * decay

        energy_enabled = bool(energy_bookkeeping_enabled)
        f_ke_eps_mismatch = None
        energy_stats = None

        if energy_enabled:
            # Fragment/energy matrices
            if np.isscalar(v_rel_scalar):
                v_matrix = np.full((N_k.size, N_k.size), float(v_rel_scalar), dtype=float)
            else:
                v_matrix = np.asarray(v_rel_scalar, dtype=float)
            size_ref = np.maximum.outer(sizes_arr, sizes_arr)
            q_star_matrix = qstar.compute_q_d_star_array(size_ref, rho, v_matrix / 1.0e3)
            q_r_matrix = q_r_array(m_k[:, None], m_k[None, :], v_matrix)
            F_lf_matrix = np.clip(largest_remnant_fraction_array(q_r_matrix, q_star_matrix), 0.0, 1.0)

            f_ke_frag = f_ke_fragmentation
            eps_val = max(float(eps_restitution), 1.0e-12)
            eps_sq = eps_val * eps_val
            f_ke_frag_used = f_ke_frag if f_ke_frag is not None else eps_sq
            f_ke_eps_mismatch = abs(f_ke_frag - eps_sq) if f_ke_frag is not None else 0.0
            if (
                f_ke_frag is not None
                and f_ke_eps_mismatch > _F_KE_MISMATCH_WARN_THRESHOLD
                and not _F_KE_MISMATCH_WARNED
            ):
                logger.warning(
                    "f_ke_fragmentation (%.3f) differs from eps_restitution^2 (%.3f) by %.3f; "
                    "consider aligning or rely on eps^2 by omitting f_ke_fragmentation.",
                    f_ke_frag,
                    eps_sq,
                    f_ke_eps_mismatch,
                )
                _F_KE_MISMATCH_WARNED = True
            f_ke_matrix = np.where(F_lf_matrix > 0.5, float(f_ke_cratering), float(f_ke_frag_used))
            C_kernel, energy_stats = collide.compute_collision_kernel_bookkeeping(
                N_k,
                sizes_arr,
                H_arr,
                m_k,
                v_rel_scalar,
                f_ke_matrix,
                F_lf_matrix,
            )
        else:
            C_kernel = collide.compute_collision_kernel_C1(
                N_k, sizes_arr, H_arr, v_rel_scalar, workspace=kernel_workspace
            )

        t_coll_kernel = kernel_minimum_tcoll(C_kernel, N_k)
        edges_state = psd_state.get("edges")
        edges_arr = np.asarray(edges_state, dtype=float) if edges_state is not None else None
        if edges_arr is None or edges_arr.shape != (sizes_arr.size + 1,):
            left_edges = np.maximum(sizes_arr - 0.5 * widths_arr, 0.0)
            edges_arr = np.empty(sizes_arr.size + 1, dtype=float)
            edges_arr[:-1] = left_edges
            edges_arr[-1] = sizes_arr[-1] + 0.5 * widths_arr[-1]
        Y_tensor = _fragment_tensor(
            sizes_arr,
            m_k,
            edges_arr,
            v_rel_scalar,
            rho,
            sizes_version=sizes_version if isinstance(sizes_version, int) else None,
            edges_version=edges_version if isinstance(edges_version, int) else None,
        )
        if logger.isEnabledFor(logging.DEBUG):
            e_log = float(e_kernel) if e_kernel is not None else float("nan")
            i_log = float(i_kernel) if i_kernel is not None else float("nan")
            y_max = float(np.max(Y_tensor)) if Y_tensor.size else 0.0
            logger.debug("collision kernel: t_coll=%.3e, e=%.4f, i=%.4f", t_coll_kernel, e_log, i_log)
            logger.debug("fragment tensor: shape=%s, Y_max=%.3e", Y_tensor.shape, y_max)
            logger.debug(
                "supply velocity blend: weight=%.3f, e_supply=%.4f, i_supply=%.4f, e_eff=%.4f, i_eff=%.4f",
                supply_weight,
                float(e_supply) if e_supply is not None else float("nan"),
                float(i_supply) if i_supply is not None else float("nan"),
                float(e_kernel) if e_kernel is not None else float("nan"),
                float(i_kernel) if i_kernel is not None else float("nan"),
            )
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

    if collisions_enabled and enable_e_damping:
        t_coll_reference = (
            t_coll_for_damp if t_coll_for_damp is not None and np.isfinite(t_coll_for_damp) else t_coll_kernel
        )
        e_next_state, i_next_state, t_damp_used, e_eq_target_state = _compute_ei_damping(
            e_value,
            i_value,
            dt=dt,
            tau_eff=tau_eff,
            a_orbit_m=r,
            v_k=r * Omega,
            dynamics_cfg=dynamics_cfg,
            t_coll_ref=t_coll_reference,
            eps_restitution=eps_restitution,
        )

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

    t_blow_use = (
        float(t_blow)
        if t_blow is not None and np.isfinite(t_blow)
        else (1.0 / Omega if Omega > 0.0 else float("inf"))
    )
    size_for_blow = sizes_arr
    edges_arr = psd_state.get("edges")
    if edges_arr is not None:
        edges_np = np.asarray(edges_arr, dtype=float)
        if edges_np.size == sizes_arr.size + 1:
            # Use bin lower edges so the threshold is applied even when s_min == a_blow.
            size_for_blow = edges_np[:-1]
    S_blow = _blowout_sink_vector(size_for_blow, a_blow, t_blow_use, enable_blowout)

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

    sigma_spill = 0.0
    prod_mass_rate_eff = prod_subblow_area_rate if dt > 0.0 else 0.0
    source_k = supply_mass_rate_to_number_source(
        prod_mass_rate_eff,
        sizes_arr,
        m_k,
        s_min_eff=s_min_effective if s_min_effective is not None else 0.0,
        widths=widths_arr,
        mass_weights=supply_mass_weights,
        mode=supply_injection_mode,
        s_inj_min=supply_s_inj_min,
        s_inj_max=supply_s_inj_max,
        q=supply_q,
        sizes_version=sizes_version if isinstance(sizes_version, int) else None,
        edges_version=edges_version if isinstance(edges_version, int) else None,
    )

    smol_diag: dict[str, float] = {}
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
        diag_out=smol_diag,
        workspace=imex_workspace,
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
    dSigma_dt_spill = sigma_spill / dt if dt > 0.0 else 0.0
    mass_loss_rate_spill = dSigma_dt_spill
    dSigma_dt_sinks = mass_loss_rate_sink + dSigma_dt_sublimation + mass_loss_rate_spill

    return Smol0DStepResult(
        psd_state=psd_state,
        sigma_before=sigma_before_step,
        sigma_after=sigma_after,
        sigma_loss=sigma_loss,
        sigma_for_step=sigma_for_step,
        sigma_clip_loss=sigma_clip_loss,
        dt_eff=dt_eff,
        mass_error=mass_err,
        prod_mass_rate_effective=prod_mass_rate_eff,
        dSigma_dt_blowout=dSigma_dt_blowout,
        dSigma_dt_sinks=dSigma_dt_sinks,
        dSigma_dt_sublimation=dSigma_dt_sublimation,
        mass_loss_rate_blowout=mass_loss_rate_blow,
        mass_loss_rate_sinks=mass_loss_rate_sink,
        mass_loss_rate_sublimation=mass_loss_rate_sub,
        gain_mass_rate=smol_diag.get("gain_mass_rate"),
        loss_mass_rate=smol_diag.get("loss_mass_rate"),
        sink_mass_rate=smol_diag.get("sink_mass_rate"),
        source_mass_rate=smol_diag.get("source_mass_rate"),
        sigma_spill=sigma_spill,
        dSigma_dt_spill=dSigma_dt_spill,
        mass_loss_rate_spill=mass_loss_rate_spill,
        t_coll_kernel=t_coll_kernel,
        e_kernel_used=e_kernel,
        i_kernel_used=i_kernel,
        e_kernel_base=e_kernel_base_val,
        i_kernel_base=i_kernel_base_val,
        e_kernel_supply=e_kernel_supply_val,
        i_kernel_supply=i_kernel_supply_val,
        e_kernel_effective=e_kernel_effective_val,
        i_kernel_effective=i_kernel_effective_val,
        supply_velocity_weight=supply_weight_val,
        energy_stats=energy_stats,
        f_ke_eps_mismatch=f_ke_eps_mismatch,
        e_next=e_next_state,
        i_next=i_next_state,
        e_eq_target=e_eq_target_state,
        t_damp_used=t_damp_used,
    )
