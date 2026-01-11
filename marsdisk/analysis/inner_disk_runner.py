"""2年内側円盤の質量損失を集計するランナーとスイープ用ユーティリティ."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from marsdisk import config_utils, constants
from marsdisk.run import load_config, run_zero_d
from marsdisk.schema import Config

DEFAULT_T_END_YEARS = 2.0

__all__ = [
    "run_inner_disk_case",
    "run_inner_disk_sweep",
    "save_massloss_table",
    "main",
]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_mass_budget(outdir: Path) -> Optional[pd.DataFrame]:
    path = outdir / "checks" / "mass_budget.csv"
    parquet_path = path.with_suffix(".parquet")
    if parquet_path.exists():
        if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
            path = parquet_path
    if not path.exists():
        return None
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if df.empty:
        return None
    return df


def _read_step_diagnostics(outdir: Path, format_hint: Optional[str]) -> Optional[pd.DataFrame]:
    candidates: List[Path] = []
    if format_hint:
        ext = "jsonl" if str(format_hint).lower() == "jsonl" else "csv"
        candidates.append(outdir / "series" / f"step_diagnostics.{ext}")
    candidates.extend(
        [
            outdir / "series" / "step_diagnostics.parquet",
            outdir / "series" / "step_diagnostics.csv",
            outdir / "series" / "step_diagnostics.jsonl",
        ]
    )
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            continue
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_json(path, lines=True)
        if not df.empty:
            return df
    return None


def _infer_initial_mass(cfg: Config, budget: Optional[pd.DataFrame], step_df: Optional[pd.DataFrame]) -> float:
    if budget is not None and "mass_initial" in budget.columns:
        first = budget.iloc[0]["mass_initial"]
        if math.isfinite(first):
            return float(first)
    if step_df is not None and {"mass_total_bins", "mass_lost_by_blowout", "mass_lost_by_sinks"}.issubset(
        set(step_df.columns)
    ):
        row0 = step_df.iloc[0]
        total = (
            _safe_float(row0.get("mass_total_bins"))
            + _safe_float(row0.get("mass_lost_by_blowout"))
            + _safe_float(row0.get("mass_lost_by_sinks"))
        )
        if math.isfinite(total):
            return float(total)
    return float(cfg.initial.mass_total)


def _infer_remaining_mass(
    m_init: float,
    m_loss_total: float,
    budget: Optional[pd.DataFrame],
    step_df: Optional[pd.DataFrame],
) -> float:
    if budget is not None and "mass_remaining" in budget.columns and not budget.empty:
        last = budget.iloc[-1]["mass_remaining"]
        if math.isfinite(last):
            return float(last)
    if step_df is not None and "mass_total_bins" in step_df.columns and not step_df.empty:
        last = step_df.iloc[-1]["mass_total_bins"]
        if math.isfinite(last):
            return float(last)
    if math.isfinite(m_init) and math.isfinite(m_loss_total):
        remain = m_init - m_loss_total
        return max(remain, 0.0)
    return float("nan")


def _max_budget_error(summary: Mapping[str, Any], budget: Optional[pd.DataFrame]) -> float:
    summary_val = _safe_float(summary.get("mass_budget_max_error_percent"))
    if math.isfinite(summary_val):
        return summary_val
    if budget is None or "error_percent" not in budget.columns or budget.empty:
        return float("nan")
    errors = np.abs(budget["error_percent"].to_numpy(dtype=float))
    if errors.size == 0:
        return float("nan")
    return float(np.nanmax(errors))


def _sanitize_label(label: Optional[str], config_path: Path) -> str:
    if label in (None, ""):
        label = config_path.stem
    label = str(label)
    return re.sub(r"[^0-9A-Za-z._-]+", "-", label).strip("-")


def _extract_inputs(cfg: Config, summary: Mapping[str, Any]) -> Dict[str, Any]:
    r_m_summary = _safe_float(summary.get("r_m_used"))
    r_rm_summary = _safe_float(summary.get("r_RM_used"))
    if not math.isfinite(r_m_summary) or not math.isfinite(r_rm_summary):
        try:
            r_m_calc, r_rm_calc, _ = config_utils.resolve_reference_radius(cfg)
            if not math.isfinite(r_m_summary):
                r_m_summary = r_m_calc
            if not math.isfinite(r_rm_summary):
                r_rm_summary = r_rm_calc
        except Exception:
            pass

    T_M = _safe_float(summary.get("T_M_used"))
    if not math.isfinite(T_M):
        try:
            T_M, _ = config_utils.resolve_temperature_field(cfg)
        except Exception:
            T_M = float("nan")

    s_min_effective = _safe_float(summary.get("s_min_effective"))
    if not math.isfinite(s_min_effective):
        s_min_effective = _safe_float(getattr(cfg.sizes, "s_min", None))

    supply_mode = getattr(cfg.supply, "mode", None)
    supply_const_rate = None
    if getattr(cfg.supply, "const", None) is not None:
        supply_const_rate = _safe_float(cfg.supply.const.prod_area_rate_kg_m2_s)

    return {
        "r_m": r_m_summary,
        "r_RM": r_rm_summary,
        "T_M": T_M,
        "s_min": s_min_effective,
        "sinks_mode": getattr(cfg.sinks, "mode", None),
        "enable_sublimation": bool(getattr(cfg.sinks, "enable_sublimation", False)),
        "enable_gas_drag": bool(getattr(cfg.sinks, "enable_gas_drag", False)),
        "supply_mode": supply_mode,
        "supply_const_prod_area_rate_kg_m2_s": supply_const_rate,
        "case_status": summary.get("case_status"),
    }


def _build_record(
    *,
    label: str,
    config_path: Path,
    cfg: Config,
    outdir: Path,
    summary: Mapping[str, Any],
    budget: Optional[pd.DataFrame],
    step_df: Optional[pd.DataFrame],
    t_end_years: float,
) -> Dict[str, Any]:
    m_blow = _safe_float(summary.get("M_loss_rp_mars"))
    if not math.isfinite(m_blow):
        m_blow = _safe_float(summary.get("M_out_cum"))
    if not math.isfinite(m_blow) and step_df is not None and "mass_lost_by_blowout" in step_df.columns:
        m_blow = _safe_float(step_df.iloc[-1].get("mass_lost_by_blowout"))

    m_sink = _safe_float(summary.get("M_loss_from_sinks"))
    if not math.isfinite(m_sink):
        m_sink = _safe_float(summary.get("M_sink_cum"))
    if not math.isfinite(m_sink) and step_df is not None and "mass_lost_by_sinks" in step_df.columns:
        m_sink = _safe_float(step_df.iloc[-1].get("mass_lost_by_sinks"))

    m_subl = _safe_float(summary.get("M_loss_from_sublimation"))
    m_loss_total = float(m_blow + m_sink)

    m_init = _infer_initial_mass(cfg, budget, step_df)
    m_remain = _infer_remaining_mass(m_init, m_loss_total, budget, step_df)
    f_loss = m_loss_total / m_init if m_init > 0.0 else 0.0

    if m_sink > 0.0:
        f_subl = m_subl / m_sink
    elif m_loss_total > 0.0:
        f_subl = m_subl / m_loss_total
    else:
        f_subl = 0.0

    closure_error_percent = float("nan")
    if m_init > 0.0 and math.isfinite(m_remain):
        closure_error_percent = abs((m_init - (m_remain + m_loss_total)) / m_init) * 100.0

    inputs = _extract_inputs(cfg, summary)

    record: Dict[str, Any] = {
        "label": label,
        "config_path": str(config_path),
        "outdir": str(outdir),
        "t_end_years_run": float(t_end_years),
        "M_init": m_init,
        "M_loss_total": m_loss_total,
        "M_loss_blowout": m_blow,
        "M_loss_sinks": m_sink,
        "M_loss_subl": m_subl,
        "M_remain": m_remain,
        "f_loss": f_loss,
        "f_subl": f_subl,
        "mass_closure_error_percent": closure_error_percent,
        "mass_budget_max_error_percent": _max_budget_error(summary, budget),
        "dt_over_t_blow_median": _safe_float(summary.get("dt_over_t_blow_median")),
        "dt_over_t_blow_p90": _safe_float(summary.get("dt_over_t_blow_p90")),
    }
    record.update(inputs)
    return record


def run_inner_disk_case(
    config_path: Path | str,
    *,
    label: Optional[str] = None,
    overrides: Optional[Sequence[str]] = None,
    t_end_years: float = DEFAULT_T_END_YEARS,
    enable_step_diagnostics: bool = False,
    append_label_to_outdir: bool = True,
) -> Dict[str, Any]:
    """単一設定を2年（既定）まで回して質量損失指標を返す."""

    path = Path(config_path)
    cfg = load_config(path, overrides=overrides)
    case_cfg = cfg.model_copy(deep=True)
    case_cfg.numerics.t_end_years = float(t_end_years)
    case_cfg.numerics.t_end_orbits = None

    label_resolved = _sanitize_label(label, path)
    outdir = Path(case_cfg.io.outdir)
    if append_label_to_outdir and label_resolved:
        outdir = outdir / label_resolved
    case_cfg.io.outdir = outdir

    if enable_step_diagnostics:
        case_cfg.io.step_diagnostics.enable = True

    run_zero_d(case_cfg)

    summary_path = outdir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found under {outdir}")
    summary = _read_json(summary_path)
    budget = _read_mass_budget(outdir)
    step_df = _read_step_diagnostics(outdir, getattr(case_cfg.io.step_diagnostics, "format", None))

    return _build_record(
        label=label_resolved,
        config_path=path,
        cfg=case_cfg,
        outdir=outdir,
        summary=summary,
        budget=budget,
        step_df=step_df,
        t_end_years=t_end_years,
    )


def run_inner_disk_sweep(
    config_paths: Iterable[str | Path],
    *,
    overrides: Optional[Sequence[str]] = None,
    labels: Optional[Sequence[str]] = None,
    t_end_years: float = DEFAULT_T_END_YEARS,
    enable_step_diagnostics: bool = False,
    append_label_to_outdir: bool = True,
) -> pd.DataFrame:
    """複数設定をまとめて実行し、1行ずつのDataFrameを返す."""

    records: List[Dict[str, Any]] = []
    label_list: List[str] = list(labels or [])
    for idx, cfg_path in enumerate(config_paths):
        label = label_list[idx] if idx < len(label_list) else None
        record = run_inner_disk_case(
            cfg_path,
            label=label,
            overrides=overrides,
            t_end_years=t_end_years,
            enable_step_diagnostics=enable_step_diagnostics,
            append_label_to_outdir=append_label_to_outdir,
        )
        records.append(record)
    return pd.DataFrame(records)


def save_massloss_table(df: pd.DataFrame, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run inner-disk 0D simulations for 2-year mass-loss accounting.")
    parser.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="YAML設定ファイルのリスト。",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="集計結果を書き出すCSVパス。未指定なら標準出力のみ。",
    )
    parser.add_argument(
        "--label",
        dest="labels",
        nargs="+",
        help="各ケースのラベル（configsと同じ順）。1件だけ指定した場合は単一ケースに適用。",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="path=value 形式の上書き（複数指定可）。",
    )
    parser.add_argument(
        "--t-end-years",
        type=float,
        default=DEFAULT_T_END_YEARS,
        help="実行終了年数（既定: 2年）。",
    )
    parser.add_argument(
        "--step-diagnostics",
        action="store_true",
        help="io.step_diagnostics.enable を自動で true にする。",
    )
    parser.add_argument(
        "--no-append-label-outdir",
        action="store_true",
        help="outdir へのラベル付与を無効化し、YAML指定をそのまま使う。",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    cfg_paths = [Path(p) for p in args.configs]
    if args.labels and len(args.labels) not in (1, len(cfg_paths)):
        raise ValueError("--label は1件または --configs と同数を指定してください")
    df = run_inner_disk_sweep(
        cfg_paths,
        overrides=args.override or None,
        labels=args.labels,
        t_end_years=float(args.t_end_years),
        enable_step_diagnostics=bool(args.step_diagnostics),
        append_label_to_outdir=not bool(args.no_append_label_outdir),
    )
    if args.out:
        save_massloss_table(df, args.out)
    pd.set_option("display.max_columns", None)
    print(df.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
