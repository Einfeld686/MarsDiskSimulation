"""Table I/O and interpolation utilities.

The production code expects pre-computed tables for the radiation pressure
coefficient :math:`\langle Q_{\rm pr}\rangle` and for the self-shielding
factor :math:`\Phi`.  During early development such tables may not yet be
available.  In that case this module falls back to simple analytic
approximations and emits a :class:`RuntimeWarning` to alert the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import warnings

import numpy as np
import pandas as pd

from .. import constants

DATA_DIR = Path(__file__).resolve().parent / "data"


def _approx_qpr(s: float, T: float) -> float:
    """Smooth transition between Rayleigh and geometric optics.

    The approximation uses the size parameter ``x = 2πs/λ`` with the
    wavelength estimated from Wien's displacement law.  ``Q`` transitions
    from ``x^4`` (Rayleigh) to unity.
    """
    # avoid divide-by-zero
    lam = 2.897771955e-3 / max(T, 1.0)
    x = 2.0 * np.pi * s / lam
    return float(x**4 / (1.0 + x**4))


def _approx_phi(tau: float, w0: float, g: float) -> float:
    raw = np.exp(-tau * max(0.0, 1.0 - w0)) * (1.0 - g)
    return float(np.clip(raw, 0.0, 1.0))


@dataclass
class QPrTable:
    s_vals: np.ndarray
    T_vals: np.ndarray
    q_vals: np.ndarray

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "QPrTable":
        pivot = df.pivot_table(index="T_M", columns="s", values="Q_pr")
        T_vals = pivot.index.to_numpy(dtype=float)
        s_vals = pivot.columns.to_numpy(dtype=float)
        q_vals = pivot.to_numpy(dtype=float)
        return cls(s_vals=s_vals, T_vals=T_vals, q_vals=q_vals)

    def interp(self, s: float, T: float) -> float:
        s_arr, T_arr = self.s_vals, self.T_vals
        q = self.q_vals
        i = np.clip(np.searchsorted(s_arr, s) - 1, 0, len(s_arr) - 2)
        j = np.clip(np.searchsorted(T_arr, T) - 1, 0, len(T_arr) - 2)
        s1, s2 = s_arr[i], s_arr[i + 1]
        T1, T2 = T_arr[j], T_arr[j + 1]
        q11 = q[j, i]
        q12 = q[j + 1, i]
        q21 = q[j, i + 1]
        q22 = q[j + 1, i + 1]
        ws = 0.0 if s2 == s1 else (s - s1) / (s2 - s1)
        wT = 0.0 if T2 == T1 else (T - T1) / (T2 - T1)
        q1 = q11 * (1 - ws) + q21 * ws
        q2 = q12 * (1 - ws) + q22 * ws
        return float(q1 * (1 - wT) + q2 * wT)


@dataclass
class PhiTable:
    tau_vals: np.ndarray
    w0_vals: np.ndarray
    g_vals: np.ndarray
    phi_vals: np.ndarray

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "PhiTable":
        # Expect a three-dimensional table; reshape using MultiIndex
        pivot = df.pivot_table(index=["tau", "w0"], columns="g", values="Phi")
        idx = pivot.index
        tau_vals = np.sort(idx.get_level_values("tau").unique().astype(float))
        w0_vals = np.sort(idx.get_level_values("w0").unique().astype(float))
        g_vals = pivot.columns.to_numpy(dtype=float)
        phi_vals = pivot.to_numpy(dtype=float).reshape(len(tau_vals), len(w0_vals), len(g_vals))
        return cls(tau_vals=tau_vals, w0_vals=w0_vals, g_vals=g_vals, phi_vals=phi_vals)

    def interp(self, tau: float, w0: float, g: float) -> float:
        t_arr, w_arr, g_arr = self.tau_vals, self.w0_vals, self.g_vals
        phi = self.phi_vals
        it = np.clip(np.searchsorted(t_arr, tau) - 1, 0, len(t_arr) - 2)
        iw = np.clip(np.searchsorted(w_arr, w0) - 1, 0, len(w_arr) - 2)
        ig = np.clip(np.searchsorted(g_arr, g) - 1, 0, len(g_arr) - 2)
        t1, t2 = t_arr[it], t_arr[it + 1]
        w1, w2 = w_arr[iw], w_arr[iw + 1]
        g1, g2 = g_arr[ig], g_arr[ig + 1]
        xd = 0.0 if t2 == t1 else (tau - t1) / (t2 - t1)
        yd = 0.0 if w2 == w1 else (w0 - w1) / (w2 - w1)
        zd = 0.0 if g2 == g1 else (g - g1) / (g2 - g1)
        # trilinear interpolation
        c000 = phi[it, iw, ig]
        c100 = phi[it + 1, iw, ig]
        c010 = phi[it, iw + 1, ig]
        c110 = phi[it + 1, iw + 1, ig]
        c001 = phi[it, iw, ig + 1]
        c101 = phi[it + 1, iw, ig + 1]
        c011 = phi[it, iw + 1, ig + 1]
        c111 = phi[it + 1, iw + 1, ig + 1]
        c00 = c000 * (1 - xd) + c100 * xd
        c01 = c001 * (1 - xd) + c101 * xd
        c10 = c010 * (1 - xd) + c110 * xd
        c11 = c011 * (1 - xd) + c111 * xd
        c0 = c00 * (1 - yd) + c10 * yd
        c1 = c01 * (1 - yd) + c11 * yd
        return float(c0 * (1 - zd) + c1 * zd)


# Attempt to load tables at import time
_QPR_TABLE: Optional[QPrTable]
_PHI_TABLE: Optional[PhiTable]

try:
    qpr_path = DATA_DIR / "qpr.csv"
    _QPR_TABLE = QPrTable.from_frame(pd.read_csv(qpr_path)) if qpr_path.exists() else None
    if _QPR_TABLE is None:
        warnings.warn("Q_pr table not found; using analytic approximation", RuntimeWarning)
except Exception as exc:  # pragma: no cover - defensive
    warnings.warn(f"Failed to load Q_pr table: {exc}; using approximation", RuntimeWarning)
    _QPR_TABLE = None

try:
    phi_path = DATA_DIR / "phi.csv"
    _PHI_TABLE = PhiTable.from_frame(pd.read_csv(phi_path)) if phi_path.exists() else None
    if _PHI_TABLE is None:
        warnings.warn("Phi table not found; using analytic approximation", RuntimeWarning)
except Exception as exc:  # pragma: no cover - defensive
    warnings.warn(f"Failed to load Phi table: {exc}; using approximation", RuntimeWarning)
    _PHI_TABLE = None


def interp_qpr(s: float, T_M: float) -> float:
    """Interpolate the mean radiation pressure efficiency.

    Falls back to :func:`_approx_qpr` when the lookup table is not available.
    """
    if _QPR_TABLE is None:
        return _approx_qpr(s, T_M)
    return _QPR_TABLE.interp(s, T_M)


def interp_phi(tau: float, w0: float, g: float) -> float:
    """Interpolate the self-shielding factor Φ.

    Falls back to :func:`_approx_phi` when the lookup table is not available.
    """
    if _PHI_TABLE is None:
        return _approx_phi(tau, w0, g)
    return _PHI_TABLE.interp(tau, w0, g)


def load_qpr_table(path: Path) -> None:
    """Load a Q_pr table from ``path`` overriding any existing table."""

    global _QPR_TABLE
    if path.suffix in {".h5", ".hdf", ".hdf5"}:
        df = pd.read_hdf(path)
    else:
        df = pd.read_csv(path)
    _QPR_TABLE = QPrTable.from_frame(df)
