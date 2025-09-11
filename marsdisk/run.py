"""Simple orchestration helpers for the Mars disk model.

This module provides a minimal driver used in the tests and documentation
examples.  It showcases the coupling between the optical-depth clipping
(S0) and the surface layer evolution (S1).  Only a very small subset of
the final project's functionality is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import logging
from typing import Dict, Any, List

import pandas as pd

from .physics import psd, surface
from .io import writer

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration parameters for a zero-dimensional run."""

    r: float                # orbital radius [m]
    Omega: float            # Keplerian frequency [s^-1]
    eps_mix: float          # mixing efficiency
    prod_rate: float        # production rate of sub-blow-out grains
    area: float | None = None  # surface area factor

    def __post_init__(self) -> None:
        if self.area is None:
            self.area = math.pi * self.r ** 2


@dataclass
class RunState:
    """State variables evolved during the run."""

    sigma_surf: float
    psd_state: Dict[str, Any]
    M_loss_cum: float = 0.0
    time: float = 0.0


def step(config: RunConfig, state: RunState, dt: float) -> Dict[str, float]:
    """Advance the coupled S0/S1 system by one time-step.

    The procedure computes the effective opacity from the PSD state to
    obtain ``sigma_tau1`` and then performs a surface step with
    :func:`surface.step_surface_density_S1`.
    """

    kappa_eff = psd.compute_kappa(state.psd_state)
    sigma_tau1 = 1.0 / kappa_eff if kappa_eff > 0.0 else None
    res = surface.step_surface_density_S1(
        state.sigma_surf,
        config.prod_rate,
        config.eps_mix,
        dt,
        config.Omega,
        sigma_tau1=sigma_tau1,
    )
    state.sigma_surf = res.sigma_surf

    t_blow = 1.0 / config.Omega
    M_out_dot = res.outflux * config.area
    state.M_loss_cum += M_out_dot * dt
    state.time += dt

    record = {
        "time": state.time,
        "dt": dt,
        "outflux_surface": res.outflux,
        "t_blow": t_blow,
        "M_out_dot": M_out_dot,
        "M_loss_cum": state.M_loss_cum,
    }
    logger.info(
        "run.step: t=%e t_blow=%e outflux=%e M_out_dot=%e M_loss_cum=%e",
        state.time,
        t_blow,
        res.outflux,
        M_out_dot,
        state.M_loss_cum,
    )
    return record


def run_n_steps(config: RunConfig, state: RunState, n: int, dt: float, out_dir: Path | None = None) -> pd.DataFrame:
    """Run ``n`` steps and optionally serialise results.

    Parameters
    ----------
    config, state:
        Run configuration and state dataclass instances.
    n:
        Number of steps to perform.
    dt:
        Time-step size.
    out_dir:
        Destination directory for output.  When ``None`` the results are not
        written to disk.
    """

    records: List[Dict[str, float]] = []
    for _ in range(n):
        records.append(step(config, state, dt))

    df = pd.DataFrame(records)
    if out_dir is not None:
        writer.write_parquet(df, Path(out_dir) / "series" / "run.parquet")
        summary = {"M_loss_cum": state.M_loss_cum}
        writer.write_summary(summary, Path(out_dir) / "summary.json")
    return df


__all__ = ["RunConfig", "RunState", "step", "run_n_steps"]
