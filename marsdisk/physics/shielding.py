"""Self-shielding utilities for the disk surface layer (S0).

The surface opacity ``κ_surf`` obtained from the particle size distribution is
modified by the self-shielding factor ``Φ`` to yield an effective opacity
``κ_eff = Φ κ``.  From this, the surface density corresponding to optical depth
unity is ``Σ_{τ=1} = 1 / κ_eff``.  Functions in this module facilitate this
calculation and provide a helper to clip the surface density accordingly.
"""
from __future__ import annotations

import csv
import logging
from numbers import Real
from pathlib import Path
from typing import Callable, Optional, Tuple
import numpy as np

from ..io import tables
from ..errors import PhysicsError

# type alias for Φ interpolation function
type_Phi = Callable[[float, float, float], float]

logger = logging.getLogger(__name__)


def _read_tau_range(table_path: Path) -> tuple[float, float] | None:
    """Extract τ range from a CSV file. Self-shielding Φ."""

    try:
        with table_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or "tau" not in reader.fieldnames:
                return None
            tau_vals: list[float] = []
            for row in reader:
                raw = row.get("tau")
                if raw is None or raw == "":
                    continue
                tau_vals.append(float(raw))
    except (OSError, ValueError, csv.Error):
        return None

    if not tau_vals:
        return None

    arr = np.asarray(tau_vals, dtype=float)
    if not np.all(np.isfinite(arr)):
        return None
    return float(np.min(arr)), float(np.max(arr))


def load_phi_table(path: Path | str) -> Callable[[float], float]:
    """Load a τ-only Φ lookup table with logging. Self-shielding Φ."""

    table_path = Path(path)
    phi_fn = tables.load_phi_table(table_path)
    tau_range = _read_tau_range(table_path)
    if tau_range is not None:
        logger.info(
            "Loaded Φ(τ) table from %s with τ∈[%e, %e]",
            table_path,
            tau_range[0],
            tau_range[1],
        )
    else:
        logger.info("Loaded Φ(τ) table from %s", table_path)
    return phi_fn


def _infer_phi_table(func: Callable[..., float]) -> Optional[object]:
    table_obj = getattr(func, "__self__", None)
    if table_obj is not None and hasattr(table_obj, "tau_vals"):
        return table_obj
    if func is tables.interp_phi:
        table_obj = getattr(tables, "_PHI_TABLE", None)
        if table_obj is not None and hasattr(table_obj, "tau_vals"):
            return table_obj
    return None


def effective_kappa(
    kappa: float,
    tau: float,
    phi_fn: Optional[Callable[[float], float]],
) -> float:
    """Compute the effective opacity from Φ. Self-shielding Φ."""

    if not isinstance(kappa, Real):
        raise TypeError("surface opacity 'kappa' must be a real number for Φ application")
    if not np.isfinite(kappa):
        raise PhysicsError("surface opacity 'kappa' must be finite for Φ application")
    if kappa < 0.0:
        raise PhysicsError("surface opacity 'kappa' must be greater or equal to 0 for Φ application")
    if not isinstance(tau, Real):
        raise TypeError("optical depth 'tau' must be a real number for Φ application")
    if not np.isfinite(tau):
        raise PhysicsError("optical depth 'tau' must be finite for Φ application")

    kappa_val = float(kappa)
    tau_val = float(tau)

    if phi_fn is None:
        return kappa_val
    if not callable(phi_fn):
        raise TypeError("Φ lookup function 'phi_fn' must be callable")

    phi_raw = float(phi_fn(tau_val))
    if not np.isfinite(phi_raw):
        raise PhysicsError(
            f"Φ lookup returned non-finite value for tau={tau_val:.6e}"
        )
    phi = float(np.clip(phi_raw, 0.0, 1.0))
    if phi != phi_raw:
        logger.info(
            "Clamped Φ value from %e to %e at tau=%e; valid range 0≤Φ≤1",
            phi_raw,
            phi,
            tau_val,
        )
    return float(phi * kappa_val)


def sigma_tau1(kappa_eff: float) -> float:
    """Return Σ_{τ=1} derived from κ_eff. Self-shielding Φ."""

    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for Σ_{τ=1}")
    if not np.isfinite(kappa_eff) or kappa_eff <= 0.0:
        return float(np.inf)
    return float(1.0 / float(kappa_eff))


def apply_shielding(
    kappa_surf: float,
    tau: float,
    w0: float,
    g: float,
    interp: type_Phi | None = None,
) -> Tuple[float, float]:
    """Return effective opacity and ``Σ_{τ=1}`` for given conditions. Self-shielding Φ."""

    if not isinstance(kappa_surf, Real):
        raise TypeError("surface opacity 'kappa_surf' must be a real number for Φ lookup")
    if not np.isfinite(kappa_surf):
        raise PhysicsError("surface opacity 'kappa_surf' must be finite for Φ lookup")
    if kappa_surf < 0.0:
        raise PhysicsError("surface opacity 'kappa_surf' must be greater or equal to 0 for Φ lookup")
    if not isinstance(tau, Real):
        raise TypeError("optical depth 'tau' must be a real number for Φ lookup")
    if not np.isfinite(tau):
        raise PhysicsError("optical depth 'tau' must be finite for Φ lookup")
    if not isinstance(w0, Real):
        raise TypeError("single-scattering albedo 'w0' must be a real number for Φ lookup")
    if not np.isfinite(w0):
        raise PhysicsError("single-scattering albedo 'w0' must be finite for Φ lookup")
    if not isinstance(g, Real):
        raise TypeError("asymmetry parameter 'g' must be a real number for Φ lookup")
    if not np.isfinite(g):
        raise PhysicsError("asymmetry parameter 'g' must be finite for Φ lookup")
    if interp is not None and not callable(interp):
        raise TypeError("Φ interpolator 'interp' must be callable")

    func = tables.interp_phi if interp is None else interp
    if not callable(func):
        raise TypeError("Φ interpolator must be callable")

    tau_val = float(tau)
    w0_val = float(w0)
    g_val = float(g)

    phi_table = _infer_phi_table(func)
    clamp_msgs: list[str] = []
    tau_min = tau_max = None
    if phi_table is not None:
        tau_vals = np.asarray(getattr(phi_table, "tau_vals"), dtype=float)
        w0_vals = np.asarray(getattr(phi_table, "w0_vals"), dtype=float)
        g_vals = np.asarray(getattr(phi_table, "g_vals"), dtype=float)
        if tau_vals.size:
            tau_min = float(np.min(tau_vals))
            tau_max = float(np.max(tau_vals))
            if tau_val < tau_min or tau_val > tau_max:
                clamped = float(np.clip(tau_val, tau_min, tau_max))
                clamp_msgs.append(
                    f"tau={tau_val:.6e}->{clamped:.6e} (range {tau_min:.6e}–{tau_max:.6e})"
                )
                tau_val = clamped
        if w0_vals.size:
            w0_min = float(np.min(w0_vals))
            w0_max = float(np.max(w0_vals))
            if w0_val < w0_min or w0_val > w0_max:
                clamped = float(np.clip(w0_val, w0_min, w0_max))
                clamp_msgs.append(
                    f"w0={w0_val:.6e}->{clamped:.6e} (range {w0_min:.6e}–{w0_max:.6e})"
                )
                w0_val = clamped
        if g_vals.size:
            g_min = float(np.min(g_vals))
            g_max = float(np.max(g_vals))
            if g_val < g_min or g_val > g_max:
                clamped = float(np.clip(g_val, g_min, g_max))
                clamp_msgs.append(
                    f"g={g_val:.6e}->{clamped:.6e} (range {g_min:.6e}–{g_max:.6e})"
                )
                g_val = clamped
    if clamp_msgs:
        logger.info("Φ lookup clamped: %s", ", ".join(clamp_msgs))

    def phi_wrapper(val_tau: float) -> float:
        tau_arg = float(val_tau)
        if phi_table is not None and tau_min is not None and tau_max is not None:
            tau_arg = float(np.clip(tau_arg, tau_min, tau_max))
        return float(func(tau_arg, w0_val, g_val))

    kappa_eff = effective_kappa(float(kappa_surf), tau_val, phi_wrapper)
    sigma_tau1_limit = sigma_tau1(kappa_eff)
    return kappa_eff, sigma_tau1_limit


def clip_to_tau1(sigma_surf: float, kappa_eff: float) -> float:
    """Clip ``Σ_surf`` so that it does not exceed ``Σ_{τ=1}``. Self-shielding Φ."""

    if not isinstance(sigma_surf, Real):
        raise TypeError("surface density 'sigma_surf' must be a real number for τ=1 clipping")
    if not np.isfinite(sigma_surf):
        raise PhysicsError("surface density 'sigma_surf' must be finite for τ=1 clipping")
    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for τ=1 clipping")
    if not np.isfinite(kappa_eff):
        raise PhysicsError("effective opacity 'kappa_eff' must be finite for τ=1 clipping")

    sigma_val = float(sigma_surf)
    kappa_val = float(kappa_eff)

    if kappa_val <= 0.0:
        if sigma_val < 0.0:
            logger.info(
                "Clamped Σ_surf from %e to 0 due to non-positive κ_eff=%e",
                sigma_val,
                kappa_val,
            )
        return max(0.0, sigma_val)

    if sigma_val < 0.0:
        logger.info(
            "Clamped Σ_surf from %e to 0 with κ_eff=%e",
            sigma_val,
            kappa_val,
        )
        return 0.0

    sigma_tau1_limit = sigma_tau1(kappa_val)
    if sigma_val > sigma_tau1_limit:
        logger.info(
            "Clamped Σ_surf from %e to τ=1 limit %e with κ_eff=%e",
            sigma_val,
            sigma_tau1_limit,
            kappa_val,
        )
        return float(sigma_tau1_limit)

    return sigma_val
