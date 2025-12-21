"""History containers used by the zero-D runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ZeroDHistory:
    """Per-step history bundle used by the full-feature zero-D driver."""

    records: List[Dict[str, Any]] = field(default_factory=list)
    psd_hist_records: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    mass_budget: List[Dict[str, float]] = field(default_factory=list)
    mass_budget_cells: List[Dict[str, float]] = field(default_factory=list)
    step_diag_records: List[Dict[str, Any]] = field(default_factory=list)
    debug_records: List[Dict[str, Any]] = field(default_factory=list)
    orbit_rollup_rows: List[Dict[str, float]] = field(default_factory=list)
    temperature_track: List[float] = field(default_factory=list)
    beta_track: List[float] = field(default_factory=list)
    ablow_track: List[float] = field(default_factory=list)
    gate_factor_track: List[float] = field(default_factory=list)
    t_solid_track: List[float] = field(default_factory=list)
    extended_total_rate_track: List[float] = field(default_factory=list)
    extended_total_rate_time_track: List[float] = field(default_factory=list)
    extended_ts_ratio_track: List[float] = field(default_factory=list)
    mass_budget_violation: Optional[Dict[str, float]] = None
    violation_triggered: bool = False
    tau_gate_block_time: float = 0.0
    total_time_elapsed: float = 0.0
