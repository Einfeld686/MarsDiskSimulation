from __future__ import annotations

"""Smoluchowski coagulation/fragmentation solver (C3--C4)."""

import os
import logging
import warnings
from dataclasses import dataclass
from typing import Iterable, MutableMapping

import numpy as np

from ..errors import MarsDiskError
from ..warnings import NumericalWarning
from .collide import compute_collision_kernel_C1, compute_prod_subblow_area_rate_C2
try:
    from ._numba_kernels import (
        NUMBA_AVAILABLE,
        gain_from_kernel_tensor_numba,
        gain_tensor_fallback_numba,
        loss_sum_numba,
        mass_budget_error_numba,
    )

    _NUMBA_AVAILABLE = NUMBA_AVAILABLE()
except ImportError:  # pragma: no cover - optional dependency
    _NUMBA_AVAILABLE = False

_NUMBA_DISABLED_ENV = os.environ.get("MARSDISK_DISABLE_NUMBA", "").lower() in {"1", "true", "yes", "on"}
_USE_NUMBA = _NUMBA_AVAILABLE and not _NUMBA_DISABLED_ENV
_NUMBA_FAILED = False

__all__ = [
    "step_imex_bdf1_C3",
    "compute_mass_budget_error_C4",
    "compute_collision_kernel_C1",
    "compute_prod_subblow_area_rate_C2",
    "psd_state_to_number_density",
    "number_density_to_psd_state",
    "ImexWorkspace",
]


@dataclass
class ImexWorkspace:
    """Reusable buffers for :func:`step_imex_bdf1_C3`."""

    gain: np.ndarray
    loss: np.ndarray

logger = logging.getLogger(__name__)


def psd_state_to_number_density(
    psd_state: MutableMapping[str, np.ndarray | float],
    sigma_surf: float,
    *,
    rho_fallback: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Return Smoluchowski-ready arrays derived from a PSD state.

    The conversion preserves the existing scaling convention used in
    ``run_zero_d``: ``number * width`` gives the unscaled per-bin counts and
    the result is normalised so that ``sum(m_k * N_k) == sigma_surf``.

    Parameters
    ----------
    psd_state:
        PSD dictionary containing ``sizes``, ``widths``, ``number`` and ``rho``.
    sigma_surf:
        Surface mass density (kg/m^2) used to scale the counts.
    rho_fallback:
        Optional material density used when ``psd_state`` lacks ``rho``.

    Returns
    -------
    sizes_k, widths_k, m_k, N_k, scale_to_sigma:
        Bin centres, widths, per-particle masses, number densities (#/m^2) and
        the scaling factor applied to match ``sigma_surf``.
    """

    try:
        sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
        widths_arr = np.asarray(psd_state.get("widths"), dtype=float)
        number_arr = np.asarray(psd_state.get("number"), dtype=float)
    except Exception:
        return (
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            0.0,
        )
    if (
        sizes_arr.size == 0
        or widths_arr.size != sizes_arr.size
        or number_arr.size != sizes_arr.size
    ):
        return (
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            np.empty(0, dtype=float),
            0.0,
        )

    rho_psd = float(psd_state.get("rho", rho_fallback if rho_fallback is not None else 0.0))
    m_k = (4.0 / 3.0) * np.pi * rho_psd * sizes_arr**3

    if sigma_surf <= 0.0 or not np.isfinite(sigma_surf):
        return sizes_arr, widths_arr, m_k, np.zeros_like(sizes_arr), 0.0

    base_counts = number_arr * widths_arr
    mass_density_raw = float(np.sum(m_k * base_counts))
    scale_to_sigma = sigma_surf / mass_density_raw if mass_density_raw > 0.0 else 0.0
    N_k = base_counts * scale_to_sigma if scale_to_sigma > 0.0 else np.zeros_like(base_counts)
    return sizes_arr, widths_arr, m_k, N_k, scale_to_sigma


def number_density_to_psd_state(
    N_new: np.ndarray,
    psd_state: MutableMapping[str, np.ndarray | float],
    sigma_before: float,
    *,
    widths: np.ndarray,
    m: np.ndarray,
    scale_to_sigma: float,
) -> tuple[MutableMapping[str, np.ndarray | float], float, float]:
    """Update ``psd_state`` from Smol output while preserving the current scaling.

    The helper mirrors :func:`psd_state_to_number_density` by rescaling the
    updated ``N_new`` back into the PSD's ``number`` array using the same
    ``scale_to_sigma`` factor.  ``sigma_before`` is used to report the
    per-step mass loss for diagnostics.

    Parameters
    ----------
    N_new:
        Number density per bin after the Smol step (#/m^2).
    psd_state:
        Mutable PSD dictionary updated in-place.
    sigma_before:
        Surface mass density (kg/m^2) prior to the Smol step.
    widths:
        Bin widths used for the PSD representation.
    m:
        Particle masses associated with each bin.
    scale_to_sigma:
        Scaling factor returned by :func:`psd_state_to_number_density`.

    Returns
    -------
    psd_state, sigma_after, sigma_loss:
        Updated PSD state, new surface density and the mass density removed by
        the Smol step (all in kg/m^2).
    """

    widths_arr = np.asarray(widths, dtype=float)
    N_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    sigma_after = float(np.sum(m_arr * N_arr))
    sigma_after = max(sigma_after, 0.0)
    sigma_loss = max(sigma_before - sigma_after, 0.0)

    if scale_to_sigma > 0.0 and widths_arr.shape == N_arr.shape:
        number_new = N_arr / (scale_to_sigma * widths_arr)
    else:
        number_new = np.zeros_like(N_arr)

    psd_state["number"] = number_new
    psd_state["n"] = number_new
    return psd_state, sigma_after, sigma_loss


def _gain_tensor(C: np.ndarray, Y: np.ndarray, out: np.ndarray | None = None) -> np.ndarray:
    """Return gain term, preferring the Numba kernel when available."""

    global _NUMBA_FAILED
    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            gain_arr = gain_from_kernel_tensor_numba(
                np.asarray(C, dtype=np.float64), np.asarray(Y, dtype=np.float64)
            )
            if out is not None and out.shape == gain_arr.shape:
                out[:] = gain_arr
                return out
            return gain_arr
        except Exception as exc:  # pragma: no cover - exercised by fallback
            warnings.warn(
                f"gain_tensor numba kernel failed ({exc!r}); trying fallback kernel.",
                NumericalWarning,
            )
            try:
                gain_arr = gain_tensor_fallback_numba(
                    np.asarray(C, dtype=np.float64), np.asarray(Y, dtype=np.float64)
                )
                if out is not None and out.shape == gain_arr.shape:
                    out[:] = gain_arr
                    return out
                return gain_arr
            except Exception as exc2:  # pragma: no cover
                _NUMBA_FAILED = True
                warnings.warn(
                    f"gain_tensor numba fallback failed ({exc2!r}); falling back to einsum.",
                    NumericalWarning,
                )
    einsum_out = out if out is not None else None
    result = np.einsum("ij,kij->k", C, Y, out=einsum_out)
    if result is None and einsum_out is not None:
        result = einsum_out
    if out is None:
        return 0.5 * result
    out[:] = 0.5 * result
    return out


def step_imex_bdf1_C3(
    N: Iterable[float],
    C: np.ndarray,
    Y: np.ndarray,
    S: Iterable[float] | None,
    m: Iterable[float],
    prod_subblow_mass_rate: float | None,
    dt: float,
    *,
    source_k: Iterable[float] | None = None,
    S_external_k: Iterable[float] | None = None,
    S_sublimation_k: Iterable[float] | None = None,
    extra_mass_loss_rate: float = 0.0,
    mass_tol: float = 5e-3,
    safety: float = 0.1,
    workspace: ImexWorkspace | None = None,
) -> tuple[np.ndarray, float, float]:
    """Advance the Smoluchowski system by one time step.

    The integration employs an IMEX-BDF(1) scheme: loss terms are treated
    implicitly while the gain terms and sink ``S`` are explicit.  In the
    sublimation-only configuration used by :func:`marsdisk.run.run_zero_d`,
    this reduces to a pure sink update with ``C=0``, ``Y=0`` and non-zero
    ``S_sublimation_k``.

    Parameters
    ----------
    N:
        Array of number surface densities for each size bin.
    C:
        Collision kernel matrix ``C_{ij}``.
    Y:
        Fragment distribution where ``Y[k, i, j]`` is the fraction of mass
        from a collision ``(i, j)`` placed into bin ``k``.
    S:
        Explicit sink term ``S_k`` for each bin.  ``None`` disables the
        legacy sink input.
    S_external_k:
        Optional additional sink term combined with ``S`` (1/s).
    S_sublimation_k:
        Optional sublimation sink (1/s) summed with ``S``.  This is the
        preferred entrypoint for the pure-sink mode.
    m:
        Particle mass associated with each bin.
    prod_subblow_mass_rate:
        Nominal mass source rate (kg/m^2/s) associated with external supply.
        When ``source_k`` is provided the per-bin source is mapped back to a
        mass rate via ``sum(m_k * source_k)`` for the mass budget check.  A
        ``None`` value defers entirely to that computed rate.
    source_k:
        Optional explicit source vector ``F_k`` (1/s) that injects particles
        into the Smol system.  A zero vector preserves the legacy behaviour.
    extra_mass_loss_rate:
        Additional mass flux leaving the system (kg m^-2 s^-1) that should be
        included in the mass budget check (e.g. sublimation sinks handled
        outside the explicit ``S`` vector).  This feeds directly into
        :func:`compute_mass_budget_error_C4`.
    dt:
        Initial time step.
    mass_tol:
        Tolerance on the relative mass conservation error.
    safety:
        Safety factor controlling the maximum allowed step size relative to
        the minimum collision time.
    workspace:
        Optional reusable buffers for ``gain`` and ``loss`` vectors to reduce
        allocations when calling the solver repeatedly.

    Returns
    -------
    tuple of ``(N_new, dt_eff, mass_error)``
        Updated number densities, the actual time step used and the relative
        mass conservation error as defined in (C4).
    """

    global _NUMBA_FAILED
    N_arr = np.asarray(N, dtype=float)
    S_base = np.zeros_like(N_arr) if S is None else np.asarray(S, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if N_arr.ndim != 1 or S_base.ndim != 1 or m_arr.ndim != 1:
        raise MarsDiskError("N, S and m must be one-dimensional")
    if not (len(N_arr) == len(S_base) == len(m_arr)):
        raise MarsDiskError("array lengths must match")
    if C.shape != (N_arr.size, N_arr.size):
        raise MarsDiskError("C has incompatible shape")
    if Y.shape != (N_arr.size, N_arr.size, N_arr.size):
        raise MarsDiskError("Y has incompatible shape")
    if dt <= 0.0:
        raise MarsDiskError("dt must be positive")

    def _optional_sink(arr: Iterable[float] | None, name: str) -> np.ndarray:
        if arr is None:
            return np.zeros_like(N_arr)
        arr_np = np.asarray(arr, dtype=float)
        if arr_np.shape != N_arr.shape:
            raise MarsDiskError(f"{name} has incompatible shape")
        return arr_np

    source_arr = _optional_sink(source_k, "source_k")
    S_external_arr = _optional_sink(S_external_k, "S_external_k")
    S_sub_arr = _optional_sink(S_sublimation_k, "S_sublimation_k")
    S_arr = S_base + S_external_arr + S_sub_arr

    gain_out = None
    loss_out = None
    if workspace is not None:
        gain_buf = getattr(workspace, "gain", None)
        loss_buf = getattr(workspace, "loss", None)
        if isinstance(gain_buf, np.ndarray) and gain_buf.shape == N_arr.shape:
            gain_out = gain_buf
        if isinstance(loss_buf, np.ndarray) and loss_buf.shape == N_arr.shape:
            loss_out = loss_buf

    try_use_numba = _USE_NUMBA and not _NUMBA_FAILED
    if try_use_numba:
        try:
            loss = loss_sum_numba(np.asarray(C, dtype=np.float64))
        except Exception as exc:  # pragma: no cover - fallback
            try_use_numba = False
            _NUMBA_FAILED = True
            warnings.warn(f"loss_sum_numba failed ({exc!r}); falling back to NumPy.", NumericalWarning)
    if not try_use_numba:
        if loss_out is not None:
            np.sum(C, axis=1, out=loss_out)
            loss = loss_out
        else:
            loss = np.sum(C, axis=1)
    t_coll = 1.0 / np.maximum(loss, 1e-30)
    dt_max = safety * float(np.min(t_coll))
    dt_eff = min(float(dt), dt_max)

    source_mass_rate = float(np.sum(m_arr * source_arr))
    if prod_subblow_mass_rate is None:
        prod_mass_rate_budget = source_mass_rate
    else:
        prod_mass_rate_budget = float(prod_subblow_mass_rate)

    gain = _gain_tensor(C, Y, out=gain_out)

    while True:
        N_new = (N_arr + dt_eff * (gain + source_arr - S_arr * N_arr)) / (1.0 + dt_eff * loss)
        if np.any(N_new < 0.0):
            dt_eff *= 0.5
            continue
        mass_err = compute_mass_budget_error_C4(
            N_arr,
            N_new,
            m_arr,
            prod_mass_rate_budget,
            dt_eff,
            extra_mass_loss_rate=float(extra_mass_loss_rate),
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("step_imex_bdf1_C3: dt=%e mass_err=%e", dt_eff, mass_err)
        if mass_err <= mass_tol:
            break
        dt_eff *= 0.5

    return N_new, dt_eff, mass_err


def compute_mass_budget_error_C4(
    N_old: Iterable[float],
    N_new: Iterable[float],
    m: Iterable[float],
    prod_subblow_mass_rate: float,
    dt: float,
    *,
    extra_mass_loss_rate: float = 0.0,
) -> float:
    """Return the relative mass budget error according to (C4).

    The budget compares the initial mass to the combination of retained mass
    and explicit source/sink fluxes:

    ``M_old + dt * prod_subblow_mass_rate = M_new + dt * extra_mass_loss_rate``.
    """

    global _NUMBA_FAILED
    N_old_arr = np.asarray(N_old, dtype=float)
    N_new_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if not (N_old_arr.shape == N_new_arr.shape == m_arr.shape):
        raise MarsDiskError("array shapes must match")

    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            err = float(
                mass_budget_error_numba(
                    m_arr * 0.0 + N_old_arr,  # ensure contiguous copies
                    m_arr * 0.0 + N_new_arr,
                    m_arr,
                    float(prod_subblow_mass_rate),
                    float(dt),
                    float(extra_mass_loss_rate),
                )
            )
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"compute_mass_budget_error_C4: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
            err = None
    else:
        err = None

    if err is None:
        M_before = float(np.sum(m_arr * N_old_arr))
        M_after = float(np.sum(m_arr * N_new_arr))
        prod_term = dt * float(prod_subblow_mass_rate)
        extra_term = dt * float(extra_mass_loss_rate)
        diff = M_after + extra_term - (M_before + prod_term)
        baseline = M_before if M_before > 0.0 else max(M_before + prod_term, 1.0e-30)
        err = abs(diff) / baseline
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "compute_mass_budget_error_C4: M_before=%e M_after=%e prod=%e extra=%e diff=%e err=%e",
            M_before,
            M_after,
            prod_subblow_mass_rate,
            extra_mass_loss_rate,
            diff,
            err,
        )
    return err
