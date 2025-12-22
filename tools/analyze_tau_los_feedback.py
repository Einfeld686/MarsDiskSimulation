"""Tau line-of-sight feedback log analyzer.

Diagnostics Parquet を集約し、tau_los の追従度と supply.feedback の挙動を
簡易に評価するスクリプト。巨大ログ対策として必要列だけを読み込む。

Usage:
    python -m tools.analyze_tau_los_feedback \\
        --run-dir /path/to/run \\
        --out-dir out/feedback_demo \\
        --target-tau 0.8
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import warnings

import matplotlib

warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
    category=FutureWarning,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

SECONDS_PER_YEAR = 365.25 * 24 * 3600.0

def _coalesce(*values):
    for val in values:
        if val is not None:
            return val
    return None


DEFAULT_COLUMNS = [
    "time",
    "time_s",
    "time_years",
    "dt",
    "dt_over_t_blow",
    "t_blow",
    "t_blow_s",
    "tau_los",
    "tau_los_mars",
    "tau_mars_line_of_sight",
    "Sigma_surf",
    "sigma_surf",
    "Sigma_tau1",
    "sigma_tau1",
    "Sigma_tau1_last_finite",
    "headroom",
    "supply_headroom",
    "supply_rate_base",
    "supply_rate_nominal",
    "supply_rate_scaled",
    "supply_rate_applied",
    "supply_feedback_scale",
    "supply_feedback_error",
    "supply_blocked_by_headroom",
    "M_out_rate",
    "M_sink_rate",
    "M_loss_rate",
    "mass_loss_surface_solid_step",
    "mass_loss_sinks_step",
    "mass_loss_sublimation_step",
    "M_out_cum",
    "M_sink_cum",
    "M_loss_cum",
]


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with path.open() as fp:
        return json.load(fp)


def _resolve_diagnostics_paths(run_dir: Path, summary: Dict, max_chunks: Optional[int]) -> List[Path]:
    series_dir = run_dir / "series"
    merged = series_dir / "diagnostics.parquet"
    if merged.exists():
        paths = [merged]
    else:
        streaming = summary.get("streaming") or {}
        raw_paths: Sequence[str] = streaming.get("diagnostics_chunks") or streaming.get("diagnostics") or []
        paths = [Path(p) for p in raw_paths if Path(p).exists()]
        if not paths:
            paths = sorted(series_dir.glob("diagnostics_chunk_*.parquet"))
    if max_chunks is not None:
        paths = paths[: max_chunks or None]
    return paths


def _collect_columns(arg_columns: Sequence[str]) -> List[str]:
    extras: List[str] = []
    for item in arg_columns:
        if not item:
            continue
        for token in item.split(","):
            token = token.strip()
            if token:
                extras.append(token)
    return list(dict.fromkeys(DEFAULT_COLUMNS + extras))


def _load_diagnostics(paths: Sequence[Path], columns: Sequence[str]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for path in paths:
        pf = pq.ParquetFile(path)
        cols = [c for c in columns if c in pf.schema.names]
        if not cols:
            continue
        table = pf.read(columns=cols)
        frame = table.to_pandas()
        if frame.empty or frame.shape[1] == 0:
            continue
        frames.append(frame)
    frames = [f for f in frames if f.shape[0] > 0 and f.shape[1] > 0 and not f.isna().all().all()]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _choose_series(df: pd.DataFrame, candidates: Iterable[str]) -> Tuple[Optional[pd.Series], Optional[str]]:
    for name in candidates:
        if name in df.columns:
            return _to_numeric(df[name]), name
    return None, None


def _time_years(df: pd.DataFrame) -> pd.Series:
    if "time_years" in df.columns:
        return _to_numeric(df["time_years"])
    if "time" in df.columns:
        return _to_numeric(df["time"]) / SECONDS_PER_YEAR
    if "time_s" in df.columns:
        return _to_numeric(df["time_s"]) / SECONDS_PER_YEAR
    return pd.Series(np.arange(len(df), dtype=float) / SECONDS_PER_YEAR)


def _weights_dt(df: pd.DataFrame) -> pd.Series:
    if "dt" in df.columns:
        weights = _to_numeric(df["dt"])
        if weights.notna().any():
            fill = float(weights.median()) if math.isfinite(weights.median()) else 1.0
            return weights.fillna(fill)
    return pd.Series(np.ones(len(df), dtype=float))


def _weighted_fraction(mask: pd.Series, weights: pd.Series) -> Optional[float]:
    aligned_mask = mask.fillna(False).astype(bool)
    valid_weights = weights.where(aligned_mask, 0.0)
    total = float(weights.sum())
    if total <= 0.0:
        return None
    return float(valid_weights.sum() / total)


def _quantiles(series: pd.Series, qs: Sequence[float]) -> Dict[str, Optional[float]]:
    arr = _to_numeric(series).dropna()
    if arr.empty:
        return {f"p{int(q*100)}": None for q in qs}
    return {f"p{int(q*100)}": float(np.nanpercentile(arr, q * 100.0)) for q in qs}


def _nanmedian(series: pd.Series) -> Optional[float]:
    arr = _to_numeric(series).dropna()
    if arr.empty:
        return None
    return float(np.nanmedian(arr))


def _infer_headroom(df: pd.DataFrame) -> Optional[pd.Series]:
    direct, _ = _choose_series(df, ["headroom", "supply_headroom"])
    if direct is not None and direct.notna().any():
        return direct
    sigma_tau1, _ = _choose_series(df, ["Sigma_tau1", "sigma_tau1", "Sigma_tau1_last_finite"])
    sigma_surf, _ = _choose_series(df, ["Sigma_surf", "sigma_surf"])
    if sigma_tau1 is not None and sigma_surf is not None:
        diff = sigma_tau1 - sigma_surf
        if diff.notna().any():
            return diff
    return None


def _render_placeholder(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    ax.text(0.02, 0.5, message, va="center", ha="left")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def analyze(args: argparse.Namespace) -> Dict:
    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    summary = _load_json(run_dir / "summary.json")
    run_config = _load_json(run_dir / "run_config.json")
    diag_paths = _resolve_diagnostics_paths(run_dir, summary, args.max_chunks)
    columns = _collect_columns(args.columns or [])

    df = _load_diagnostics(diag_paths, columns)
    if df.empty:
        raise SystemExit("diagnostics data could not be loaded (no rows).")

    time_years = _time_years(df)
    weights = _weights_dt(df)
    tau_series, tau_field_used = _choose_series(
        df,
        ["tau_los", "tau_los_mars", "tau_mars_line_of_sight"],
    )
    if tau_series is None:
        raise SystemExit("tau_los/tau_mars_line_of_sight が見つかりませんでした。")
    tau_series = _to_numeric(tau_series)

    target_tau = _coalesce(args.target_tau, summary.get("supply_feedback_target_tau"), run_config.get("supply_feedback_target_tau"), 1.0)

    feedback_cfg = run_config.get("supply", {})
    initial_scale = _coalesce(args.initial_scale, feedback_cfg.get("feedback_initial_scale"), summary.get("supply_feedback_scale_median"), 1.0)
    min_scale = _coalesce(feedback_cfg.get("feedback_min_scale"), summary.get("supply_feedback_scale_min"))
    max_scale = _coalesce(feedback_cfg.get("feedback_max_scale"), summary.get("supply_feedback_scale_max"))

    raw_scale, _ = _choose_series(df, ["supply_feedback_scale"])
    raw_error, _ = _choose_series(df, ["supply_feedback_error"])
    scale_ffill = raw_scale.ffill() if raw_scale is not None else pd.Series([initial_scale] * len(df))
    if scale_ffill.empty:
        scale_ffill = pd.Series([initial_scale] * len(df))
    if not math.isfinite(scale_ffill.iloc[0]):
        scale_ffill.iloc[0] = initial_scale
    scale_ffill = scale_ffill.ffill().fillna(initial_scale)
    if raw_error is not None:
        error_ffill = raw_error.ffill()
    else:
        error_ffill = pd.Series([np.nan] * len(df))

    headroom_series = _infer_headroom(df)
    blocked_series, _ = _choose_series(df, ["supply_blocked_by_headroom"])

    # Tau metrics
    tau_stats = _quantiles(tau_series, [0.1, 0.5, 0.9])
    over_one = _weighted_fraction(tau_series > 1.0, weights)
    close_ratio = _weighted_fraction((tau_series - target_tau).abs() < args.tau_tolerance, weights)

    # Transient vs steady split
    total_time = float(time_years.max() - time_years.min()) if len(time_years) else 0.0
    steady_start_years = args.steady_start_years
    if steady_start_years is None and total_time > 0.0:
        steady_start_years = total_time * args.steady_start_frac
    transient_mask = time_years <= (steady_start_years or 0.0)
    steady_mask = ~transient_mask

    def _tau_block(mask: pd.Series) -> Dict[str, Optional[float]]:
        block_weights = weights.where(mask, 0.0)
        return {
            "median": _nanmedian(tau_series.where(mask)),
            "p10": _quantiles(tau_series.where(mask), [0.1]).get("p10"),
            "p90": _quantiles(tau_series.where(mask), [0.9]).get("p90"),
            "close_ratio": _weighted_fraction((tau_series - target_tau).abs() < args.tau_tolerance, block_weights),
            "over_one_ratio": _weighted_fraction(tau_series.where(mask) > 1.0, block_weights),
        }

    tau_split = {"transient": _tau_block(transient_mask), "steady": _tau_block(steady_mask)}

    # Feedback metrics
    scale_stats = _quantiles(scale_ffill, [0.1, 0.5, 0.9])
    scale_stats.update({"min": float(scale_ffill.min()), "max": float(scale_ffill.max())})
    near_min = None
    near_max = None
    if min_scale is not None:
        near_min = _weighted_fraction(scale_ffill <= float(min_scale) * 1.1, weights)
    if max_scale is not None:
        near_max = _weighted_fraction(scale_ffill >= float(max_scale) * 0.9, weights)
    error_events = int(_to_numeric(raw_error).dropna().shape[0]) if raw_error is not None else 0
    scale_change_events = 0
    if raw_scale is not None:
        scale_numeric = _to_numeric(raw_scale)
        if not scale_numeric.empty:
            scale_diff = scale_numeric.diff().abs()
            scale_change_events = int(scale_diff[scale_diff > args.scale_change_eps].count())
    error_stats = _quantiles(error_ffill, [0.1, 0.5, 0.9])

    # Headroom metrics
    headroom_stats = {}
    if headroom_series is not None:
        headroom_stats["p10"], headroom_stats["p50"], headroom_stats["p90"] = (
            _quantiles(headroom_series, [0.1, 0.5, 0.9]).get("p10"),
            _quantiles(headroom_series, [0.5]).get("p50"),
            _quantiles(headroom_series, [0.9]).get("p90"),
        )
        headroom_stats["tight_fraction"] = _weighted_fraction(headroom_series <= args.headroom_threshold, weights)
        if tau_series.notna().any() and headroom_series.notna().any():
            tau_clean = tau_series.copy()
            hdr_clean = headroom_series.copy()
            corr = tau_clean.corr(hdr_clean)
            headroom_stats["corr_tau"] = float(corr) if pd.notna(corr) else None
    if blocked_series is not None:
        headroom_stats["blocked_fraction"] = _weighted_fraction(blocked_series.astype(bool), weights)

    # dt/t_blow metrics
    dt_over_tb, _ = _choose_series(df, ["dt_over_t_blow"])
    dt_over_tb_stats = None
    if dt_over_tb is not None:
        dt_over_tb_stats = {
            "p50": _quantiles(dt_over_tb, [0.5]).get("p50"),
            "p90": _quantiles(dt_over_tb, [0.9]).get("p90"),
            "max": float(_to_numeric(dt_over_tb).max()),
        }
    nominal_dt = summary.get("time_grid", {}).get("dt_nominal_s") or run_config.get("time_grid", {}).get("dt_nominal_s")
    nominal_t_blow = None
    if "t_blow_nominal_s" in run_config:
        nominal_t_blow = run_config.get("t_blow_nominal_s")
    dt_over_nominal = float(nominal_dt / nominal_t_blow) if nominal_dt and nominal_t_blow else None

    # Plots
    stride = max(len(df) // 5000, 1)
    t_plot = time_years[::stride]
    tau_plot = tau_series[::stride]
    scale_plot = scale_ffill[::stride]

    if not tau_plot.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(t_plot, tau_plot, lw=0.8, label="tau_los")
        ax.axhline(target_tau, color="C1", ls="--", lw=1.0, label=f"target={target_tau}")
        ax.set_xlabel("time [yr]")
        ax.set_ylabel("tau_los")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(plots_dir / "tau_vs_time.png", dpi=180)
        plt.close(fig)
    else:
        _render_placeholder(plots_dir / "tau_vs_time.png", "tau vs time", "tau_los がありません")

    if not scale_plot.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(t_plot, scale_plot, lw=0.8, color="C2")
        ax.set_xlabel("time [yr]")
        ax.set_ylabel("feedback scale (ffill)")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(plots_dir / "scale_vs_time.png", dpi=180)
        plt.close(fig)
    else:
        _render_placeholder(plots_dir / "scale_vs_time.png", "scale vs time", "scale がありません")

    if not tau_plot.empty and not scale_plot.empty:
        fig, ax = plt.subplots(figsize=(4.5, 4))
        ax.scatter(scale_plot, tau_plot, s=4, alpha=0.3)
        ax.set_xlabel("feedback scale (ffill)")
        ax.set_ylabel("tau_los")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(plots_dir / "tau_vs_scale.png", dpi=180)
        plt.close(fig)
    else:
        _render_placeholder(plots_dir / "tau_vs_scale.png", "tau vs scale", "プロット用データ不足")

    base_rate = _coalesce(
        feedback_cfg.get("supply_rate_nominal_kg_m2_s"),
        feedback_cfg.get("const_prod_area_rate_kg_m2_s"),
        summary.get("supply_rate_nominal_kg_m2_s"),
    )
    scale_ref = _nanmedian(scale_ffill)
    base_rate_new = base_rate * scale_ref if base_rate is not None and scale_ref is not None else None

    result = {
        "run_dir": str(run_dir),
        "used_paths": [str(p) for p in diag_paths],
        "n_rows": len(df),
        "target_tau": target_tau,
        "tau_field_used": tau_field_used,
        "tau": {
            "stats": tau_stats,
            "over_one_ratio": over_one,
            "close_ratio": close_ratio,
            "split": tau_split,
        },
        "feedback": {
            "scale_stats": scale_stats,
            "error_stats": error_stats,
            "near_min_fraction": near_min,
            "near_max_fraction": near_max,
            "error_events": error_events,
            "scale_change_events": scale_change_events,
            "scale_reference": scale_ref,
            "initial_scale": initial_scale,
            "min_scale": min_scale,
            "max_scale": max_scale,
            "base_rate_current": base_rate,
            "base_rate_new": base_rate_new,
        },
        "headroom": headroom_stats,
        "dt_over_t_blow": {
            "summary_median": summary.get("dt_over_t_blow_median"),
            "diagnostics": dt_over_tb_stats,
            "nominal_dt_over_t_blow": dt_over_nominal,
        },
    }
    return result


def _rows_from_result(result: Dict) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    tau = result.get("tau", {})
    tau_stats = tau.get("stats", {})
    for key, val in tau_stats.items():
        rows.append({"category": "tau", "metric": key, "value": val})
    rows.append({"category": "tau", "metric": "over_one_ratio", "value": tau.get("over_one_ratio")})
    rows.append({"category": "tau", "metric": "close_ratio", "value": tau.get("close_ratio")})
    for phase, stats in (tau.get("split") or {}).items():
        for mkey, mval in stats.items():
            rows.append({"category": f"tau_{phase}", "metric": mkey, "value": mval})

    fb = result.get("feedback", {})
    for key, val in (fb.get("scale_stats") or {}).items():
        rows.append({"category": "feedback_scale", "metric": key, "value": val})
    rows.append({"category": "feedback_scale", "metric": "near_min_fraction", "value": fb.get("near_min_fraction")})
    rows.append({"category": "feedback_scale", "metric": "near_max_fraction", "value": fb.get("near_max_fraction")})
    rows.append({"category": "feedback_scale", "metric": "error_events", "value": fb.get("error_events")})
    rows.append({"category": "feedback_scale", "metric": "scale_change_events", "value": fb.get("scale_change_events")})
    rows.append({"category": "feedback_scale", "metric": "base_rate_new", "value": fb.get("base_rate_new")})
    for key, val in (fb.get("error_stats") or {}).items():
        rows.append({"category": "feedback_error", "metric": key, "value": val})

    headroom = result.get("headroom") or {}
    for key, val in headroom.items():
        rows.append({"category": "headroom", "metric": key, "value": val})

    dt_tb = result.get("dt_over_t_blow") or {}
    rows.append({"category": "dt_over_t_blow", "metric": "summary_median", "value": dt_tb.get("summary_median")})
    diag_stats = dt_tb.get("diagnostics") or {}
    for key, val in diag_stats.items():
        rows.append({"category": "dt_over_t_blow_diag", "metric": key, "value": val})
    rows.append({"category": "dt_over_t_blow", "metric": "nominal_dt_over_t_blow", "value": dt_tb.get("nominal_dt_over_t_blow")})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="tau_los feedback ログ解析ツール")
    parser.add_argument("--run-dir", required=True, help="解析対象の run ディレクトリ")
    parser.add_argument("--out-dir", required=True, help="解析結果を書き出すディレクトリ")
    parser.add_argument("--target-tau", type=float, default=None, help="目標 tau。未指定なら summary/run_config から取得")
    parser.add_argument("--tau-tolerance", type=float, default=0.1, help="|tau - target| 許容幅 (default: 0.1)")
    parser.add_argument("--headroom-threshold", type=float, default=1.0e-4, help="headroom が逼迫とみなす閾値")
    parser.add_argument("--max-chunks", type=int, default=None, help="diagnostics_chunk_* を最大で何個読むか")
    parser.add_argument("--columns", nargs="*", default=[], help="追加で読みたい列（カンマ区切り可）")
    parser.add_argument("--steady-start-years", type=float, default=None, help="この年数までは立ち上がり区間とみなす")
    parser.add_argument("--steady-start-frac", type=float, default=0.25, help="指定がない場合、総時間に対する定常区間の開始割合")
    parser.add_argument("--initial-scale", type=float, default=None, help="ffill 初期値を明示したいときに指定")
    parser.add_argument("--scale-change-eps", type=float, default=1e-9, help="scale 変化をカウントするしきい値")

    args = parser.parse_args()
    result = analyze(args)

    out_dir = Path(args.out_dir)
    rows = _rows_from_result(result)
    pd.DataFrame(rows).to_csv(out_dir / "feedback_summary.csv", index=False)
    with (out_dir / "feedback_summary.json").open("w") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
