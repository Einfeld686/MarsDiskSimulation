"""Legacy step helpers retained for tutorials and tests."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .. import constants
from ..physics import psd, shielding, surface
from ..io import writer

KAPPA_MIN = 1e-12

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration parameters for a zero-dimensional run."""

    r: float                # orbital radius [m]
    Omega: float            # Keplerian frequency [s^-1]
    prod_rate: float        # production rate of sub-blow-out grains
    area: float | None = None  # surface area factor
    los_factor: float = 1.0  # τ scaling from vertical to Mars line-of-sight

    def __post_init__(self) -> None:
        if self.area is None:
            self.area = math.pi * self.r ** 2
        if self.los_factor <= 0.0 or not math.isfinite(self.los_factor):
            self.los_factor = 1.0


@dataclass
class RunState:
    """State variables evolved during the run."""

    sigma_surf: float
    psd_state: Dict[str, Any]
    M_loss_cum: float = 0.0
    time: float = 0.0


def step(config: RunConfig, state: RunState, dt: float) -> Dict[str, float]:
    """Advance the coupled S0/S1 system by one time-step."""

    kappa_surf = psd.compute_kappa(state.psd_state)
    tau_vert = kappa_surf * state.sigma_surf
    los_factor = config.los_factor if config.los_factor > 0.0 else 1.0
    tau_los = tau_vert * los_factor
    kappa_eff, sigma_tau1 = shielding.apply_shielding(kappa_surf, tau_los, 0.0, 0.0)
    if kappa_eff <= KAPPA_MIN:
        sigma_tau1 = None
    res = surface.step_surface_density_S1(
        state.sigma_surf,
        config.prod_rate,
        dt,
        config.Omega,
        sigma_tau1=sigma_tau1,
    )
    state.sigma_surf = res.sigma_surf

    t_blow = 1.0 / config.Omega
    # kg/s -> M_Mars/s
    M_out_dot = (res.outflux * config.area) / constants.M_MARS
    state.M_loss_cum += M_out_dot * dt
    state.time += dt

    record = {
        "time": state.time,
        "dt": dt,
        "outflux_surface": res.outflux,
        "sink_flux_surface": res.sink_flux,
        "t_blow": t_blow,
        "tau_vertical": tau_vert,
        "tau_los_mars": tau_los,
        "M_out_dot": M_out_dot,  # M_Mars/s
        "M_loss_cum": state.M_loss_cum,  # M_Mars
    }
    logger.info(
        "run.step: t=%e t_blow=%e outflux=%e M_out_dot[M_Mars/s]=%e M_loss_cum[M_Mars]=%e",
        state.time,
        t_blow,
        res.outflux,
        M_out_dot,
        state.M_loss_cum,
    )
    return record


def run_n_steps(
    config: RunConfig,
    state: RunState,
    n: int,
    dt: float,
    out_dir: Path | None = None,
) -> pd.DataFrame:
    """Run ``n`` steps and optionally serialise results."""

    records: List[Dict[str, float]] = []
    for _ in range(n):
        records.append(step(config, state, dt))

    df = pd.DataFrame(records)
    if out_dir is not None:
        writer.write_parquet(df, Path(out_dir) / "series" / "run.parquet")
        summary = {"M_loss": state.M_loss_cum}  # M_Mars
        writer.write_summary(summary, Path(out_dir) / "summary.json")
    return df


__all__ = ["RunConfig", "RunState", "step", "run_n_steps"]
