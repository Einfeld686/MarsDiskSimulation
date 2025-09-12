from __future__ import annotations

"""External surface supply parameterisations.

This module provides a thin wrapper around the ``Supply`` configuration model
and exposes a :class:`SupplyModel` which evaluates the production rate of
sub--blow-out material per unit area for a given time ``t``.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..schema import Supply


@dataclass
class _TableData:
    t: np.ndarray
    rate: np.ndarray

    @classmethod
    def load(cls, path: Path) -> "_TableData":
        df = pd.read_csv(path)
        t = df.iloc[:, 0].to_numpy(dtype=float)
        rate = df.iloc[:, -1].to_numpy(dtype=float)
        return cls(t=t, rate=rate)

    def interp(self, t: float) -> float:
        return float(np.interp(t, self.t, self.rate, left=self.rate[0], right=self.rate[-1]))


class SupplyModel:
    """Evaluator for the configured supply mode."""

    def __init__(self, cfg: Supply) -> None:
        self.cfg = cfg
        self._table: Optional[_TableData] = None

    def rate(self, t: float) -> float:
        mode = self.cfg.mode
        if mode == "const":
            return self.cfg.const.prod_area_rate_kg_m2_s
        if mode == "powerlaw":
            A = self.cfg.powerlaw.A_kg_m2_s
            if A is None:
                return 0.0
            t0 = self.cfg.powerlaw.t0_s
            if t0 <= 0.0:
                return 0.0
            return A * (t / t0) ** self.cfg.powerlaw.index
        if mode == "table":
            if self._table is None:
                self._table = _TableData.load(self.cfg.table.path)
            return self._table.interp(t)
        return 0.0


def supply_rate(cfg: Supply, t: float) -> float:
    """Convenience wrapper returning ``cfg``'s production rate at ``t``."""

    return SupplyModel(cfg).rate(t)
