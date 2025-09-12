from __future__ import annotations

"""External surface supply parameterisations.

This module evaluates the production rate of sub--blow-out material per unit
area according to a :class:`~marsdisk.schema.Supply` specification.  The public
entry point :func:`get_prod_area_rate` returns the rate already multiplied by
the configured mixing efficiency ``epsilon_mix`` and clipped to be
non-negative.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..schema import Supply, SupplyPiece

_EPS = 1.0e-12


@dataclass
class _TableData:
    """Holder for time/radius grids and associated rates."""

    t: np.ndarray
    r: np.ndarray
    rate: np.ndarray

    @classmethod
    def load(cls, path: Path) -> "_TableData":
        df = pd.read_csv(path)
        if {"t", "r", "rate"}.issubset(df.columns):
            t_vals = np.unique(df["t"].to_numpy(dtype=float))
            r_vals = np.unique(df["r"].to_numpy(dtype=float))
            grid = (
                df.pivot_table(index="t", columns="r", values="rate")
                .reindex(index=t_vals, columns=r_vals)
                .to_numpy(dtype=float)
            )
            return cls(t_vals, r_vals, grid)
        t = df.iloc[:, 0].to_numpy(dtype=float)
        rate = df.iloc[:, -1].to_numpy(dtype=float)
        return cls(t, np.array([]), rate[:, None])

    def interp(self, t: float, r: float) -> float:
        if self.r.size == 0:
            return float(
                np.interp(t, self.t, self.rate[:, 0], left=self.rate[0, 0], right=self.rate[-1, 0])
            )
        t_idx = np.clip(np.searchsorted(self.t, t) - 1, 0, len(self.t) - 2)
        r_idx = np.clip(np.searchsorted(self.r, r) - 1, 0, len(self.r) - 2)
        t0, t1 = self.t[t_idx], self.t[t_idx + 1]
        r0, r1 = self.r[r_idx], self.r[r_idx + 1]
        f00 = self.rate[t_idx, r_idx]
        f01 = self.rate[t_idx, r_idx + 1]
        f10 = self.rate[t_idx + 1, r_idx]
        f11 = self.rate[t_idx + 1, r_idx + 1]
        wt = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        wr = 0.0 if r1 == r0 else (r - r0) / (r1 - r0)
        return float((1 - wt) * (1 - wr) * f00 + (1 - wt) * wr * f01 + wt * (1 - wr) * f10 + wt * wr * f11)


_TABLE_CACHE: Dict[Path, _TableData] = {}


def _rate_basic(t: float, r: float, spec: Supply | SupplyPiece) -> float:
    mode = spec.mode
    if mode == "const":
        return spec.const.prod_area_rate_kg_m2_s
    if mode == "powerlaw":
        A = spec.powerlaw.A_kg_m2_s
        if A is None:
            return 0.0
        t0 = spec.powerlaw.t0_s if spec.powerlaw.t0_s > 0.0 else 0.0
        return A * ((t - t0) + _EPS) ** spec.powerlaw.index
    if mode == "table":
        data = _TABLE_CACHE.get(spec.table.path)
        if data is None:
            data = _TableData.load(spec.table.path)
            _TABLE_CACHE[spec.table.path] = data
        return data.interp(t, r)
    if mode == "piecewise":  # type: ignore[comparison-overlap]
        for piece in spec.piecewise:
            if piece.t_start_s <= t < piece.t_end_s:
                return _rate_basic(t, r, piece)
        return 0.0
    return 0.0


def get_prod_area_rate(t: float, r: float, spec: Supply) -> float:
    """Return the mixed surface production rate in kg m⁻² s⁻¹."""

    raw = _rate_basic(t, r, spec)
    rate = raw * spec.mixing.epsilon_mix
    return max(rate, 0.0)


__all__ = ["get_prod_area_rate"]
