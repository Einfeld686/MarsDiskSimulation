r"""Table I/O and interpolation utilities.

The production code expects pre-computed tables for the radiation pressure
coefficient :math:`\langle Q_{\rm pr}\rangle` and for the self-shielding
factor :math:`\Phi`.  The ⟨Q_pr⟩ table is mandatory—if it cannot be loaded
the caller must supply a valid file via ``radiation.qpr_table_path``.  An
analytic fallback is intentionally not provided so that all runs stay
anchored to the vetted Mie calculations shipped with the repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Callable, Sequence
import warnings

import numpy as np
import pandas as pd

from .. import constants
from ..warnings import TableWarning

PACKAGE_DATA_DIR = Path(__file__).resolve().parent / "data"
REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

DATA_DIR = PACKAGE_DATA_DIR  # retained for backwards compatibility paths


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
        """Q_prテーブルのDataFrameを格子配列へ変換する。Planck 平均⟨Q_pr⟩.
        T 行 × s 列でピボットする前提を共有する。Planck 平均⟨Q_pr⟩.
        """
        required = {"s", "T_M", "Q_pr"}
        missing = required.difference(df.columns)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Q_pr table is missing required columns: {names}")

        work = df.copy()
        work["s"] = pd.to_numeric(work["s"], errors="coerce")
        work["T_M"] = pd.to_numeric(work["T_M"], errors="coerce")
        work["Q_pr"] = pd.to_numeric(work["Q_pr"], errors="coerce")
        if work[["s", "T_M", "Q_pr"]].isna().any().any():
            raise ValueError("Q_pr table contains non-numeric or missing values")

        if (work["s"] <= 0).any() or (work["T_M"] <= 0).any():
            raise ValueError("Q_pr table requires positive s and T_M values")

        if work.duplicated(subset=["s", "T_M"]).any():
            raise ValueError("Q_pr table has duplicate (s, T_M) entries")

        pivot = work.pivot(index="T_M", columns="s", values="Q_pr")
        pivot = pivot.sort_index(axis=0).sort_index(axis=1)
        if pivot.isna().any().any():
            raise ValueError("Q_pr table grid has missing values")

        T_vals = pivot.index.to_numpy(dtype=float)
        s_vals = pivot.columns.to_numpy(dtype=float)
        if len(T_vals) < 2 or len(s_vals) < 2:
            raise ValueError("Q_pr table needs at least two unique s and T_M values")

        q_vals = pivot.to_numpy(dtype=float)
        if not np.all(np.isfinite(q_vals)):
            raise ValueError("Q_pr table contains non-finite Q_pr values")

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


def _read_qpr_frame_h5datasets(path: Path) -> pd.DataFrame:
    """HDF5 datasetsからQ_prテーブルを読み込む。Planck 平均⟨Q_pr⟩."""

    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ValueError("h5py is required to read HDF5 datasets 'qpr','log10s','T'") from exc

    try:
        with h5py.File(path, "r") as handle:
            missing = [name for name in ("qpr", "log10s", "T") if name not in handle]
            if missing:
                missing_str = ", ".join(sorted(missing))
                raise ValueError(f"Q_pr HDF5 file is missing datasets: {missing_str}")
            qpr = np.array(handle["qpr"], dtype=float)
            log10s = np.array(handle["log10s"], dtype=float)
            temperatures = np.array(handle["T"], dtype=float)
    except OSError as exc:  # pragma: no cover - file level issues
        raise ValueError(f"Failed to read Q_pr HDF5 datasets from {path}: {exc}") from exc

    if log10s.ndim != 1:
        raise ValueError("Dataset 'log10s' must be one-dimensional")
    if temperatures.ndim != 1:
        raise ValueError("Dataset 'T' must be one-dimensional")
    if qpr.ndim != 2:
        raise ValueError("Dataset 'qpr' must be two-dimensional")

    if not np.all(np.isfinite(log10s)):
        raise ValueError("Dataset 'log10s' must contain finite values")
    if not np.all(np.isfinite(temperatures)):
        raise ValueError("Dataset 'T' must contain finite values")
    if not np.all(np.isfinite(qpr)):
        raise ValueError("Dataset 'qpr' must contain finite values")

    s_vals = np.power(10.0, log10s)
    if np.any(s_vals <= 0.0):
        raise ValueError("Converted grain sizes must be positive")
    if np.any(temperatures <= 0.0):
        raise ValueError("Temperatures must be positive")

    expected_shape = (temperatures.size, s_vals.size)
    if qpr.shape != expected_shape:
        raise ValueError(
            f"Dataset 'qpr' has shape {qpr.shape}, expected {expected_shape}"
        )

    data = {
        "T_M": np.repeat(temperatures, s_vals.size),
        "s": np.tile(s_vals, temperatures.size),
        "Q_pr": qpr.reshape(-1),
    }
    return pd.DataFrame(data)


def _read_qpr_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise ValueError(f"Q_pr table file does not exist: {path}")

    try:
        if path.suffix in {".h5", ".hdf", ".hdf5"}:
            df = pd.read_hdf(path)
        else:
            df = pd.read_csv(path)
    except Exception:  # pragma: no cover - handled by fallback
        return _read_qpr_frame_h5datasets(path)

    if "log10_s" in df.columns and "s" not in df.columns:
        df = df.rename(columns={"log10_s": "s"})
        df["s"] = 10.0 ** df["s"].astype(float)
    return df


_EXPECTED_QPR_LOCATIONS: Sequence[Path] = (
    REPO_DATA_DIR / "qpr_table.csv",
    PACKAGE_DATA_DIR / "qpr_planck.h5",
    PACKAGE_DATA_DIR / "qpr_planck.csv",
)

# Attempt to load tables at import time
_QPR_TABLE: Optional[QPrTable]
_QPR_TABLE_PATH: Optional[Path]
_PHI_TABLE: Optional[PhiTable]

_QPR_TABLE = None
_QPR_TABLE_PATH = None
for candidate in _EXPECTED_QPR_LOCATIONS:
    try:
        if not candidate.exists():
            continue
        _QPR_TABLE = QPrTable.from_frame(_read_qpr_frame(candidate))
        _QPR_TABLE_PATH = candidate.resolve()
        break
    except Exception as exc:  # pragma: no cover - defensive logging
        warnings.warn(f"Failed to load default Q_pr table from {candidate}: {exc}", TableWarning)
        _QPR_TABLE = None
        _QPR_TABLE_PATH = None

if _QPR_TABLE is None:
    joined = ", ".join(str(path) for path in _EXPECTED_QPR_LOCATIONS)
    raise RuntimeError(
        f"⟨Q_pr⟩ lookup table not found. Provide a table via radiation.qpr_table_path "
        f"or place one at: {joined}"
    )

try:
    phi_path = DATA_DIR / "phi.csv"
    _PHI_TABLE = PhiTable.from_frame(pd.read_csv(phi_path)) if phi_path.exists() else None
    if _PHI_TABLE is None:
        warnings.warn("Phi table not found; using analytic approximation", TableWarning)
except Exception as exc:  # pragma: no cover - defensive
    warnings.warn(f"Failed to load Phi table: {exc}; using approximation", TableWarning)
    _PHI_TABLE = None


def interp_qpr(s: float, T_M: float) -> float:
    """Interpolate the mean radiation pressure efficiency.

    Raises :class:`RuntimeError` when the lookup table has not been initialised.
    """
    if _QPR_TABLE is None or _QPR_TABLE_PATH is None:
        joined = ", ".join(str(path) for path in _EXPECTED_QPR_LOCATIONS)
        raise RuntimeError(
            "Q_pr table has not been initialised. Call load_qpr_table(path) with a valid file. "
            f"Expected table at one of: {joined}"
        )
    return _QPR_TABLE.interp(s, T_M)


def interp_phi(tau: float, w0: float, g: float) -> float:
    """Interpolate the self-shielding factor Φ.

    Falls back to :func:`_approx_phi` when the lookup table is not available.
    """
    if _PHI_TABLE is None:
        return _approx_phi(tau, w0, g)
    return _PHI_TABLE.interp(tau, w0, g)


def load_qpr_table(path: str | Path) -> Callable[[float, float], float]:
    """Read a table file and build an interpolator. Planck averaged ⟨Q_pr⟩."""

    global _QPR_TABLE, _QPR_TABLE_PATH

    table_path = Path(path)
    if not table_path.exists():
        raise ValueError(f"Q_pr table file does not exist: {table_path}")

    df = _read_qpr_frame(table_path)
    _QPR_TABLE = QPrTable.from_frame(df)
    _QPR_TABLE_PATH = table_path.resolve()
    return _QPR_TABLE.interp


def load_phi_table(path: str | Path) -> Callable[[float], float]:
    """Create a clamped interpolator from a Φ(τ) CSV file. Self-shielding Φ."""

    table_path = Path(path)
    if not table_path.exists():
        raise ValueError(f"Phi table file does not exist: {table_path}")

    try:
        df = pd.read_csv(table_path)
    except Exception as exc:  # pragma: no cover - pandas already tested
        raise ValueError(f"Failed to read Phi table from {table_path}: {exc}") from exc

    required = {"tau", "phi"}
    missing = required.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Phi table is missing required columns: {names}")

    work = df.copy()
    work["tau"] = pd.to_numeric(work["tau"], errors="coerce")
    work["phi"] = pd.to_numeric(work["phi"], errors="coerce")
    if work[["tau", "phi"]].isna().any().any():
        raise ValueError("Phi table contains non-numeric or missing values")

    work = work.sort_values("tau")
    tau_vals = work["tau"].to_numpy(dtype=float)
    phi_vals = work["phi"].to_numpy(dtype=float)

    if tau_vals.size == 0:
        raise ValueError("Phi table must contain at least one row")
    if tau_vals.size >= 2 and np.any(np.diff(tau_vals) <= 0.0):
        raise ValueError("Phi table requires strictly increasing tau values")
    if not np.all(np.isfinite(phi_vals)):
        raise ValueError("Phi table contains non-finite phi values")

    if tau_vals.size == 1:
        phi_const = float(np.clip(phi_vals[0], 0.0, 1.0))

        def phi_fn(_: float) -> float:
            return phi_const

        return phi_fn

    def phi_fn(tau: float) -> float:
        value = float(
            np.interp(
                tau,
                tau_vals,
                phi_vals,
                left=phi_vals[0],
                right=phi_vals[-1],
            )
        )
        return float(np.clip(value, 0.0, 1.0))

    return phi_fn


def get_qpr_table_path() -> Optional[Path]:
    """Return the resolved path of the active ⟨Q_pr⟩ table, if any."""

    return _QPR_TABLE_PATH
