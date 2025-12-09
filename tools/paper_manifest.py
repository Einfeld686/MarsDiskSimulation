#!/usr/bin/env python3
"""
paper_manifest.py

論文マニフェスト（configs/paper_*.yml）を検証し、runs/figures の入力を解決する。
- run の outdir を glob から選び、summary/mass_budget を読み込んで簡易チェックを付与
- figure の run 参照の整合性を確認
- paper_checks.json と resolved_manifest.json を outdir に出力
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field, root_validator

try:
    from pydantic import model_validator
except ImportError:  # pydantic v1
    model_validator = None
from ruamel.yaml import YAML


class PaperCheckSettings(BaseModel):
    mass_budget_tolerance_percent: float = 0.5
    imex_dt_ratio_max: float = 0.1
    allow_missing_runs: bool = False


class PaperSettings(BaseModel):
    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    template_set: Optional[str] = None
    output_root: str = "out/paper_inputs"
    checks: PaperCheckSettings = Field(default_factory=PaperCheckSettings)
    manual_blocks: Dict[str, str] = Field(default_factory=dict)


class RunEntry(BaseModel):
    run_id: str
    label: Optional[str] = None
    outdir: Optional[str] = None
    outdir_glob: Optional[str] = None
    run_card: str = "run_card.md"
    summary: str = "summary.json"
    series: Dict[str, str] = Field(
        default_factory=lambda: {"main": "series/run.parquet", "diagnostics": "series/diagnostics.parquet"}
    )
    checks: Dict[str, str] = Field(default_factory=lambda: {"mass_budget": "checks/mass_budget.csv"})
    tags: List[str] = Field(default_factory=list)

    if model_validator:

        @model_validator(mode="after")
        def ensure_location(cls, values: "RunEntry") -> "RunEntry":
            if not values.outdir and not values.outdir_glob:
                raise ValueError("run entry requires outdir or outdir_glob")
            return values

    else:

        @root_validator(skip_on_failure=True)
        def ensure_location(cls, values: Dict[str, Any]) -> Dict[str, Any]:
            if not values.get("outdir") and not values.get("outdir_glob"):
                raise ValueError("run entry requires outdir or outdir_glob")
            return values


class FigureEntry(BaseModel):
    fig_id: str
    script: str
    runs: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)


class PaperManifest(BaseModel):
    paper: PaperSettings
    runs: List[RunEntry]
    figures: List[FigureEntry] = Field(default_factory=list)


def _load_manifest(path: Path) -> PaperManifest:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text())
    return PaperManifest(**data)


def _model_dump(model: BaseModel) -> Dict[str, Any]:
    """Compatibility wrapper for pydantic v1/v2."""
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        return dump()
    return model.dict()


def _resolve_outdir(run: RunEntry, base_dir: Path) -> Tuple[Optional[Path], List[Path]]:
    """Return chosen outdir and all matches considered."""
    candidates: List[Path] = []
    if run.outdir:
        candidates.append((base_dir / run.outdir).resolve())
    if run.outdir_glob:
        candidates.extend(sorted(base_dir.glob(run.outdir_glob)))
    candidates = [c for c in candidates if c.exists()]
    if not candidates:
        return None, []
    # prefer newest mtime to pick latest run
    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0], candidates


def _read_summary(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _evaluate_mass_budget(csv_path: Path, tolerance_percent: float) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not csv_path.exists():
        return None, None
    df = pd.read_csv(csv_path)
    if df.empty or "error_percent" not in df.columns:
        return None, None
    df["abs_error"] = df["error_percent"].abs()
    idx = int(df["abs_error"].idxmax())
    row = df.loc[idx].to_dict()
    result = {
        "max_error_percent": float(df["abs_error"].max()),
        "max_error_row": row,
        "within_tolerance": float(df["abs_error"].max()) <= tolerance_percent,
        "tolerance_percent": tolerance_percent,
    }
    check = None
    if not result["within_tolerance"]:
        check = {
            "level": "error",
            "code": "mass_budget_exceeds_tolerance",
            "message": f"mass_budget error {result['max_error_percent']:.3f}% exceeds tolerance {tolerance_percent}%",
        }
    return result, check


def _evaluate_dt_ratio(summary: Dict[str, Any], max_ratio: float) -> Optional[Dict[str, Any]]:
    if not summary:
        return None
    ratio = summary.get("dt_over_t_blow_median")
    if ratio is None:
        return None
    return {
        "value": ratio,
        "within_limit": ratio <= max_ratio,
        "limit": max_ratio,
    }


def _collect_run(run: RunEntry, base_dir: Path, checks_cfg: PaperCheckSettings, strict: bool) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    resolved: Dict[str, Any] = {"run_id": run.run_id, "label": run.label, "tags": run.tags}
    messages: List[Dict[str, Any]] = []

    outdir, candidates = _resolve_outdir(run, base_dir)
    resolved["outdir"] = str(outdir) if outdir else None
    resolved["outdir_candidates"] = [str(c) for c in candidates]

    if not outdir:
        level = "error" if strict or not checks_cfg.allow_missing_runs else "warning"
        messages.append(
            {
                "level": level,
                "code": "missing_outdir",
                "run_id": run.run_id,
                "message": f"outdir not found (glob={run.outdir_glob}, explicit={run.outdir})",
            }
        )
        return resolved, messages

    def abs_path(rel: str) -> Path:
        return (outdir / rel).resolve()

    resolved_paths: Dict[str, Optional[str]] = {}
    run_card_path = abs_path(run.run_card)
    summary_path = abs_path(run.summary)
    resolved_paths["run_card"] = str(run_card_path) if run_card_path.exists() else None
    resolved_paths["summary"] = str(summary_path) if summary_path.exists() else None
    for key, rel in run.series.items():
        path = abs_path(rel)
        resolved_paths[f"series_{key}"] = str(path) if path.exists() else None
    for key, rel in run.checks.items():
        path = abs_path(rel)
        resolved_paths[f"check_{key}"] = str(path) if path.exists() else None
    resolved["paths"] = resolved_paths

    if not resolved_paths["summary"]:
        messages.append(
            {
                "level": "warning",
                "code": "missing_summary",
                "run_id": run.run_id,
                "message": f"summary not found at {summary_path}",
            }
        )
    summary_data = _read_summary(summary_path) if resolved_paths["summary"] else {}
    resolved["summary"] = summary_data or None

    mass_budget_path = abs_path(run.checks.get("mass_budget", "")) if "mass_budget" in run.checks else None
    if mass_budget_path and not mass_budget_path.exists():
        messages.append(
            {
                "level": "warning",
                "code": "missing_mass_budget",
                "run_id": run.run_id,
                "message": f"mass_budget file not found at {mass_budget_path}",
            }
        )

    mass_budget_info, mb_check = _evaluate_mass_budget(mass_budget_path, checks_cfg.mass_budget_tolerance_percent) if mass_budget_path else (None, None)
    resolved["mass_budget"] = mass_budget_info
    if mb_check:
        mb_check["run_id"] = run.run_id
        messages.append(mb_check)

    dt_info = _evaluate_dt_ratio(summary_data, checks_cfg.imex_dt_ratio_max)
    resolved["dt_over_t_blow"] = dt_info
    if dt_info and not dt_info["within_limit"]:
        messages.append(
            {
                "level": "warning",
                "code": "dt_ratio_high",
                "run_id": run.run_id,
                "message": f"dt_over_t_blow_median={dt_info['value']} exceeds limit {dt_info['limit']}",
            }
        )

    return resolved, messages


def _collect_figures(figs: List[FigureEntry], known_run_ids: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    tasks: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []
    run_set = set(known_run_ids)
    for fig in figs:
        missing = [rid for rid in fig.runs if rid not in run_set]
        if missing:
            messages.append(
                {
                    "level": "warning",
                    "code": "figure_missing_run",
                    "fig_id": fig.fig_id,
                    "message": f"runs not in manifest: {', '.join(missing)}",
                }
            )
        tasks.append(
            {
                "fig_id": fig.fig_id,
                "script": fig.script,
                "runs": fig.runs,
                "params": fig.params,
            }
        )
    return tasks, messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve paper manifest and emit checks")
    parser.add_argument("--manifest", required=True, type=Path, help="path to paper YAML (configs/paper_*.yml)")
    parser.add_argument("--outdir", type=Path, help="output directory for resolved manifest and checks")
    parser.add_argument("--base-dir", type=Path, default=Path("."), help="base directory to resolve relative paths (default: repo root)")
    parser.add_argument("--strict", action="store_true", help="treat missing runs as errors even if manifest allows missing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    manifest = _load_manifest(args.manifest)
    outdir = args.outdir or (Path(manifest.paper.output_root) / manifest.paper.id)
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    run_results: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []

    for run in manifest.runs:
        info, messages = _collect_run(run, base_dir, manifest.paper.checks, args.strict)
        run_results.append(info)
        checks.extend(messages)

    figure_tasks, fig_messages = _collect_figures(manifest.figures, [r.run_id for r in manifest.runs])
    checks.extend(fig_messages)

    # summarize levels
    level_counts = {"error": 0, "warning": 0, "info": 0}
    for m in checks:
        level_counts[m["level"]] = level_counts.get(m["level"], 0) + 1

    resolved_manifest = {
        "paper": _model_dump(manifest.paper),
        "runs": run_results,
        "figures": figure_tasks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_dir": str(base_dir),
    }

    checks_payload = {
        "paper_id": manifest.paper.id,
        "generated_at": resolved_manifest["generated_at"],
        "level_counts": level_counts,
        "checks": checks,
    }

    resolved_path = outdir / "resolved_manifest.json"
    checks_path = outdir / "paper_checks.json"
    resolved_path.write_text(json.dumps(resolved_manifest, indent=2, ensure_ascii=False))
    checks_path.write_text(json.dumps(checks_payload, indent=2, ensure_ascii=False))

    print(f"[paper_manifest] wrote {resolved_path}")
    print(f"[paper_manifest] wrote {checks_path}")
    if level_counts["error"] > 0:
        print("[paper_manifest] errors present", file=sys.stderr)


if __name__ == "__main__":
    main()
