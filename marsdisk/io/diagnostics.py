"""Diagnostic helpers for zero-D runs."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..runtime import ZeroDHistory
from ..schema import Config
from . import writer


def safe_float(value: Any) -> Optional[float]:
    """Return value cast to float when finite, otherwise None."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def write_zero_d_history(
    cfg: Config,
    df: pd.DataFrame,
    history: ZeroDHistory,
    *,
    step_diag_enabled: bool,
    step_diag_format: str,
    step_diag_path_cfg: Optional[Path],
    step_diag_path: Optional[Path],
    orbit_rollup_enabled: bool,
    extended_diag_enabled: bool,
) -> None:
    """Persist time series, diagnostics, and rollups for a zero-D run."""

    outdir = Path(cfg.io.outdir)
    resolved_step_diag_path = step_diag_path
    if step_diag_enabled and resolved_step_diag_path is None:
        if step_diag_path_cfg is not None:
            resolved_step_diag_path = Path(step_diag_path_cfg)
            if not resolved_step_diag_path.is_absolute():
                resolved_step_diag_path = outdir / resolved_step_diag_path
        else:
            ext = "jsonl" if step_diag_format == "jsonl" else "csv"
            resolved_step_diag_path = outdir / "series" / f"step_diagnostics.{ext}"
    writer.write_parquet(df, outdir / "series" / "run.parquet")
    if history.psd_hist_records:
        psd_hist_df = pd.DataFrame(history.psd_hist_records)
        writer.write_parquet(psd_hist_df, outdir / "series" / "psd_hist.parquet")
    if history.diagnostics:
        diag_df = pd.DataFrame(history.diagnostics)
        writer.write_parquet(diag_df, outdir / "series" / "diagnostics.parquet")
    if step_diag_enabled and resolved_step_diag_path is not None:
        writer.write_step_diagnostics(
            history.step_diag_records, resolved_step_diag_path, fmt=step_diag_format
        )
    if orbit_rollup_enabled:
        rows_for_rollup = history.orbit_rollup_rows
        required_extended_cols = {
            "mloss_blowout_rate",
            "mloss_sink_rate",
            "mloss_total_rate",
            "ts_ratio",
            "dt",
            "time",
            "blowout_gate_factor",
        }
        if extended_diag_enabled and rows_for_rollup and not df.empty and required_extended_cols.issubset(set(df.columns)):
            df_end = df["time"].to_numpy()
            df_start = (df["time"] - df["dt"]).to_numpy()
            blow_rates = df["mloss_blowout_rate"].to_numpy()
            sink_rates = df["mloss_sink_rate"].to_numpy()
            total_rates = df["mloss_total_rate"].to_numpy()
            ts_ratio_series = df["ts_ratio"].to_numpy()
            gate_factor_series = df["blowout_gate_factor"].to_numpy()

            def _safe_peak(arr: np.ndarray, mask: np.ndarray) -> float:
                subset = arr[mask]
                subset = subset[np.isfinite(subset)]
                if subset.size == 0:
                    return float("nan")
                return float(np.max(subset))

            def _safe_median(arr: np.ndarray, mask: np.ndarray) -> float:
                subset = arr[mask]
                subset = subset[np.isfinite(subset)]
                if subset.size == 0:
                    return float("nan")
                return float(np.median(subset))

            gate_factor_median_all = _safe_median(
                gate_factor_series,
                np.ones_like(gate_factor_series, dtype=bool),
            )

            rows_for_rollup = []
            orbit_start_time = 0.0
            for row in history.orbit_rollup_rows:
                orbit_end_time = safe_float(row.get("time_s_end"))
                if orbit_end_time is None:
                    t_orb_row = safe_float(row.get("t_orb_s"))
                    orbit_end_time = orbit_start_time + (t_orb_row if t_orb_row is not None else 0.0)
                mask = (df_end > orbit_start_time) & (df_start <= orbit_end_time)
                blow_peak = _safe_peak(blow_rates, mask)
                sink_peak = _safe_peak(sink_rates, mask)
                total_peak = _safe_peak(total_rates, mask)
                ts_ratio_med = _safe_median(ts_ratio_series, mask)
                gate_factor_med = _safe_median(gate_factor_series, mask)
                if not math.isfinite(gate_factor_med):
                    gate_factor_med = gate_factor_median_all
                row_aug = dict(row)
                row_aug["mloss_blowout_rate_mean"] = row.get("M_out_per_orbit")
                row_aug["mloss_sink_rate_mean"] = row.get("M_sink_per_orbit")
                row_aug["mloss_total_rate_mean"] = row.get("M_loss_per_orbit")
                row_aug["mloss_blowout_rate_peak"] = blow_peak
                row_aug["mloss_sink_rate_peak"] = sink_peak
                row_aug["mloss_total_rate_peak"] = total_peak
                row_aug["ts_ratio_median"] = ts_ratio_med
                row_aug["gate_factor_median"] = gate_factor_med
                rows_for_rollup.append(row_aug)
                orbit_start_time = orbit_end_time
        writer.write_orbit_rollup(rows_for_rollup, outdir / "orbit_rollup.csv")


__all__ = ["write_zero_d_history", "safe_float"]
