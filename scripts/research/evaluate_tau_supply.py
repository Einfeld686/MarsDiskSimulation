#!/usr/bin/env python
"""Evaluate tau≈1 と供給維持の成否を run 出力から判定する簡易スクリプト。

デフォルトでは run.parquet の後半 50% を評価区間とし、以下をチェックする（本番用閾値）:
- tau_vertical（なければ tau）の中央値が 0.5–2
- prod_subblow_area_rate が設定供給（dotSigma_prod 目安）の 90%以上を連続して維持する期間が
  min_duration（既定 0.1 日）以上存在

例:
    python scripts/research/evaluate_tau_supply.py --run-dir out/debug_supply_test
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


def _load_target_rate(run_dir: Path, override: float | None) -> float | None:
    if override is not None:
        return override
    rc_path = run_dir / "run_config.json"
    if not rc_path.exists():
        return None
    try:
        data = json.loads(rc_path.read_text())
    except Exception:
        return None
    supply_cfg = data.get("supply", {}) or {}
    rate = supply_cfg.get("supply_rate_nominal_kg_m2_s")
    if rate is None:
        rate = supply_cfg.get("effective_prod_rate_kg_m2_s")
    if rate is None:
        rate = supply_cfg.get("supply_rate_scaled_initial_kg_m2_s")
    if rate is None:
        const_rate = supply_cfg.get("const_prod_area_rate_kg_m2_s")
        eps = supply_cfg.get("epsilon_mix")
        if const_rate is not None and eps is not None:
            try:
                rate = float(const_rate) * float(eps)
            except Exception:
                rate = None
    return rate


def _safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").to_numpy()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(np.median(values))


def evaluate_run(
    run_dir: Path,
    *,
    window_spans: Sequence[tuple[float, float]] = ((0.5, 1.0),),
    min_duration_days: float = 0.1,
    target_rate: float | None = None,
    threshold_factor: float = 0.9,
) -> dict[str, object]:
    run_path = run_dir / "series" / "run.parquet"
    if not run_path.exists():
        raise FileNotFoundError(f"run.parquet not found under {run_dir}")
    df = pd.read_parquet(
        run_path,
        columns=[
            "time",
            "prod_subblow_area_rate",
            "tau",
            "tau_vertical",
            "Sigma_surf0",
            "t_orb_s",
        ],
    )
    target = _load_target_rate(run_dir, target_rate)
    if target is None:
        rc_path = run_dir / "run_config.json"
        try:
            data = json.loads(rc_path.read_text())
        except Exception:
            data = {}
        supply_cfg = data.get("supply", {}) or {}
        mu_orbit = supply_cfg.get("mu_orbit10pct")
        orbit_fraction = supply_cfg.get("orbit_fraction_at_mu1", 0.10)
        if mu_orbit is not None and "Sigma_surf0" in df.columns and "t_orb_s" in df.columns:
            sigma0 = float(df["Sigma_surf0"].iloc[0])
            t_orb = float(df["t_orb_s"].iloc[0])
            if np.isfinite(sigma0) and sigma0 > 0.0 and np.isfinite(t_orb) and t_orb > 0.0:
                target = float(mu_orbit) * float(orbit_fraction) * sigma0 / t_orb
    t_max = float(df["time"].max())
    tau_col = "tau_vertical" if "tau_vertical" in df.columns else "tau"
    per_span = []
    any_success = False
    for span in window_spans:
        start_frac, end_frac = span
        start_t = t_max * float(max(min(start_frac, end_frac), 0.0))
        end_t = t_max * float(max(start_frac, end_frac))
        window = df[(df["time"] >= start_t) & (df["time"] <= end_t)].copy()
        if window.empty:
            per_span.append(
                {
                    "span": [start_frac, end_frac],
                    "tau_median": float("nan"),
                    "tau_condition": False,
                    "target_rate": target,
                    "threshold_rate": None,
                    "longest_supply_duration_s": 0.0,
                    "supply_condition": False,
                    "success": False,
                    "reason": "empty_window",
                }
            )
            continue
        tau_median = _safe_median(window[tau_col])
        prod = window["prod_subblow_area_rate"]
        dt_med = _safe_median(window["time"].diff())
        if not np.isfinite(dt_med) or dt_med <= 0.0:
            dt_med = _safe_median(df["time"].diff())
        if not np.isfinite(dt_med) or dt_med <= 0.0:
            dt_med = 1.0
        threshold = target * threshold_factor if target is not None else None
        longest_true = 0
        if threshold is not None:
            mask = prod >= threshold
            current = 0
            for ok in mask.values:
                if ok:
                    current += 1
                    longest_true = max(longest_true, current)
                else:
                    current = 0
        longest_duration = longest_true * dt_med
        min_duration_s = min_duration_days * 86400.0
        cond_tau = 0.5 <= tau_median <= 2.0
        cond_supply = threshold is None or longest_duration >= min_duration_s
        span_success = cond_tau and cond_supply
        any_success = any_success or span_success
        per_span.append(
            {
                "span": [start_frac, end_frac],
                "tau_median": tau_median,
                "tau_condition": cond_tau,
                "target_rate": target,
                "threshold_rate": threshold,
                "longest_supply_duration_s": longest_duration,
                "supply_condition": cond_supply,
                "success": span_success,
            }
        )
    return {
        "run_dir": str(run_dir),
        "window_spans": [list(s) for s in window_spans],
        "min_duration_days": min_duration_days,
        "threshold_factor": threshold_factor,
        "per_span": per_span,
        "success_any": any_success,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True, help="run ディレクトリ（series/run.parquet を含む）")
    ap.add_argument(
        "--window-spans",
        type=str,
        default="0.5-1.0",
        help="評価する時間割合の区間（例: '0.0-0.2,0.2-0.6,0.6-1.0'）。開始-終了のカンマ区切り。",
    )
    ap.add_argument("--min-duration-days", type=float, default=0.1, help="供給が閾値を維持すべき連続時間（日）")
    ap.add_argument("--target-rate", type=float, default=None, help="供給の目標レート [kg m^-2 s^-1]（未指定なら run_config を参照）")
    ap.add_argument("--threshold-factor", type=float, default=0.9, help="目標供給に対する許容割合（0–1）")
    args = ap.parse_args()
    spans: list[tuple[float, float]] = []
    for part in args.window_spans.split(","):
        if "-" not in part:
            continue
        try:
            a, b = part.split("-", 1)
            spans.append((float(a), float(b)))
        except Exception:
            continue
    if not spans:
        spans = [(0.5, 1.0)]
    result = evaluate_run(
        args.run_dir,
        window_spans=tuple(spans),
        min_duration_days=args.min_duration_days,
        target_rate=args.target_rate,
        threshold_factor=args.threshold_factor,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
