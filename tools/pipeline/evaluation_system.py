"""Evaluate simulation outputs against analysis specifications."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

SERIES_COLUMNS_REF = "analysis/run-recipes.md:44"
SUMMARY_FIELDS_REF = "analysis/run-recipes.md:45-47"
S_MIN_REF = "analysis/run-recipes.md:47"
MASS_BUDGET_REF = "analysis/run-recipes.md:50"
ORBIT_ROLLUP_REF = "analysis/run-recipes.md:48"
RUN_CONFIG_REF = "analysis/run-recipes.md:51"

REQUIRED_SERIES_COLUMNS = [
    "time",
    "dt",
    "T_M_used",
    "rad_flux_Mars",
    "tau",
    "a_blow",
    "a_blow_at_smin",
    "s_min",
    "kappa",
    "Qpr_mean",
    "Q_pr_at_smin",
    "beta_at_smin_config",
    "beta_at_smin_effective",
    "beta_at_smin",
    "Sigma_surf",
    "Sigma_tau1",
    "outflux_surface",
    "t_blow",
    "prod_subblow_area_rate",
    "M_out_dot",
    "M_loss_cum",
    "mass_total_bins",
    "mass_lost_by_blowout",
    "mass_lost_by_sinks",
    "dt_over_t_blow",
    "fast_blowout_factor",
    "fast_blowout_flag_gt3",
    "fast_blowout_flag_gt10",
    "fast_blowout_corrected",
    "a_blow_step",
    "dSigma_dt_sublimation",
    "mass_lost_sinks_step",
    "mass_lost_sublimation_step",
    "ds_dt_sublimation",
]

REQUIRED_SUMMARY_FIELDS = [
    "case_status",
    "beta_at_smin_config",
    "beta_at_smin_effective",
    "beta_at_smin_min",
    "beta_at_smin_median",
    "beta_at_smin_max",
    "beta_threshold",
    "a_blow_min",
    "a_blow_median",
    "a_blow_max",
    "M_out_cum",
    "M_sink_cum",
    "M_out_mean_per_orbit",
    "M_sink_mean_per_orbit",
    "M_loss",
    "M_loss_from_sinks",
    "M_loss_from_sublimation",
    "orbits_completed",
    "chi_blow_eff",
    "s_min_components",
    "s_min_effective",
    "time_grid",
    "mass_budget_max_error_percent",
    "qpr_table_path",
    "rho_used",
    "T_M_used",
    "T_M_initial",
    "T_M_final",
    "T_M_min",
    "T_M_median",
    "T_M_max",
    "temperature_driver",
    "solar_radiation",
]

REQUIRED_RUN_CONFIG_FIELDS = [
    "sublimation_provenance",
    "beta_formula",
    "T_M_used",
    "rho_used",
    "Q_pr_used",
    "temperature_driver",
    "solar_radiation",
]

ORBIT_ROLLUP_COLUMNS = ["time_s_end", "M_out_orbit", "M_sink_orbit", "M_loss_per_orbit"]
MASS_BUDGET_COLUMNS = [
    "time",
    "mass_initial",
    "mass_remaining",
    "mass_lost",
    "error_percent",
    "tolerance_percent",
]


@dataclass
class CheckResult:
    """Encapsulate the outcome of a single evaluation step."""

    name: str
    passed: bool
    reference: str
    description: str
    details: str = ""


@dataclass
class EvaluationCheck:
    """Associate a name/reference pair with a callable check."""

    name: str
    description: str
    reference: str
    func: Callable[["EvaluationContext"], Tuple[bool, str]]


class EvaluationContext:
    """Lazy loaders for output artefacts required by the evaluation."""

    def __init__(self, outdir: Path) -> None:
        self.outdir = Path(outdir)
        self._series_df: Optional[pd.DataFrame] = None
        self._series_path: Optional[Path] = None
        self._summary: Optional[dict] = None
        self._mass_budget: Optional[pd.DataFrame] = None
        self._orbit_rollup: Optional[pd.DataFrame] = None
        self._run_config: Optional[dict] = None

    @property
    def summary_path(self) -> Path:
        return self.outdir / "summary.json"

    @property
    def mass_budget_path(self) -> Path:
        return self.outdir / "checks" / "mass_budget.csv"

    @property
    def orbit_rollup_path(self) -> Path:
        return self.outdir / "orbit_rollup.csv"

    @property
    def run_config_path(self) -> Path:
        return self.outdir / "run_config.json"

    @property
    def series_path(self) -> Path:
        if self._series_path is not None:
            return self._series_path
        series_dir = self.outdir / "series"
        preferred = series_dir / "run.parquet"
        if preferred.exists():
            self._series_path = preferred
            return preferred
        candidates = sorted(series_dir.glob("*.parquet"))
        if not candidates:
            raise FileNotFoundError(f"no Parquet files found in {series_dir}")
        latest = max(candidates, key=lambda path: path.stat().st_mtime)
        self._series_path = latest
        return latest

    @property
    def summary(self) -> dict:
        if self._summary is None:
            self._summary = json.loads(self.summary_path.read_text(encoding="utf-8"))
        return self._summary

    @property
    def series(self) -> pd.DataFrame:
        if self._series_df is None:
            self._series_df = pd.read_parquet(self.series_path)
        return self._series_df

    @property
    def mass_budget(self) -> pd.DataFrame:
        if self._mass_budget is None:
            self._mass_budget = pd.read_csv(self.mass_budget_path)
        return self._mass_budget

    @property
    def orbit_rollup(self) -> pd.DataFrame:
        if self._orbit_rollup is None:
            self._orbit_rollup = pd.read_csv(self.orbit_rollup_path)
        return self._orbit_rollup

    @property
    def run_config(self) -> dict:
        if self._run_config is None:
            self._run_config = json.loads(self.run_config_path.read_text(encoding="utf-8"))
        return self._run_config


def _check_required_outputs(ctx: EvaluationContext) -> Tuple[bool, str]:
    missing: List[str] = []
    paths = [
        ctx.series_path,
        ctx.summary_path,
        ctx.mass_budget_path,
        ctx.orbit_rollup_path,
        ctx.run_config_path,
    ]
    for path in paths:
        if not path.exists():
            missing.append(str(path))
    if missing:
        return False, f"missing required artefacts: {', '.join(missing)}"
    return True, "all baseline artefacts detected"


# Column aliases: at least one column from each group must be present
SERIES_COLUMN_ALIASES = [
    ("tau_los_mars", "tau_mars_line_of_sight"),  # Either of these is acceptable
]


def _check_series_columns(ctx: EvaluationContext) -> Tuple[bool, str]:
    df = ctx.series
    missing = [name for name in REQUIRED_SERIES_COLUMNS if name not in df.columns]
    if missing:
        return False, f"missing columns: {', '.join(missing)}"
    # Check aliased columns: at least one from each alias group must exist
    for alias_group in SERIES_COLUMN_ALIASES:
        if not any(col in df.columns for col in alias_group):
            return False, f"missing one of aliased columns: {alias_group}"
    return True, f"{len(REQUIRED_SERIES_COLUMNS)} required columns present"


def _check_summary_fields(ctx: EvaluationContext) -> Tuple[bool, str]:
    summary = ctx.summary
    missing = [name for name in REQUIRED_SUMMARY_FIELDS if name not in summary]
    if missing:
        return False, f"summary missing fields: {', '.join(missing)}"
    return True, "summary schema matches specification"


def _check_case_status(ctx: EvaluationContext) -> Tuple[bool, str]:
    summary = ctx.summary
    status = summary.get("case_status")
    beta_cfg = summary.get("beta_at_smin_config")
    beta_threshold = summary.get("beta_threshold")
    if status is None or beta_cfg is None or beta_threshold is None:
        return False, "case_status or beta fields missing"
    expected = "blowout" if beta_cfg >= beta_threshold else "ok"
    if status not in {"ok", "blowout"}:
        return False, f"unexpected case_status='{status}'"
    if status != expected:
        return False, f"case_status='{status}' disagrees with beta comparison (expected {expected})"
    return True, f"case_status '{status}' consistent with beta comparison"


def _check_s_min_components(ctx: EvaluationContext) -> Tuple[bool, str]:
    summary = ctx.summary
    components = summary.get("s_min_components")
    s_effective = summary.get("s_min_effective")
    if not isinstance(components, dict):
        return False, "s_min_components missing or not a mapping"
    missing = [key for key in ("config", "blowout", "effective") if key not in components]
    if missing:
        return False, f"s_min_components missing keys: {', '.join(missing)}"
    if s_effective is None:
        return False, "s_min_effective missing from summary"
    try:
        config_val = float(components["config"])
        blow_val = float(components["blowout"])
        effective = float(s_effective)
    except (TypeError, ValueError) as exc:
        return False, f"invalid numeric values in s_min components: {exc}"
    if not math.isclose(effective, float(components["effective"]), rel_tol=1e-6, abs_tol=1e-12):
        return False, "s_min_effective disagrees with s_min_components.effective"
    floor_mode = components.get("floor_mode")
    floor_dynamic = components.get("floor_dynamic")
    if floor_mode == "none":
        expected = config_val
        expected_label = "config (psd.floor.mode=none)"
    elif floor_mode == "evolve_smin":
        if floor_dynamic is None:
            expected = max(config_val, blow_val)
            expected_label = "max(config, blowout)"
        else:
            try:
                floor_dynamic_val = float(floor_dynamic)
            except (TypeError, ValueError) as exc:
                return False, f"invalid floor_dynamic in s_min components: {exc}"
            expected = max(config_val, blow_val, floor_dynamic_val)
            expected_label = "max(config, blowout, floor_dynamic)"
    else:
        expected = max(config_val, blow_val)
        expected_label = "max(config, blowout)"
    if not math.isclose(effective, expected, rel_tol=1e-6, abs_tol=1e-12):
        return False, f"s_min_effective={effective} differs from {expected_label}={expected}"
    return True, f"s_min components consistent with {expected_label}"


def _check_mass_budget(ctx: EvaluationContext) -> Tuple[bool, str]:
    df = ctx.mass_budget
    missing_cols = [name for name in MASS_BUDGET_COLUMNS if name not in df.columns]
    if missing_cols:
        return False, f"mass_budget missing columns: {', '.join(missing_cols)}"
    if df.empty:
        return False, "mass_budget.csv is empty"
    max_error = float(df["error_percent"].abs().max())
    if not math.isfinite(max_error):
        return False, "mass_budget contains non-finite error_percent"
    if max_error > 0.5 + 1e-9:
        return False, f"mass budget error exceeds tolerance (max {max_error:.3f}%)"
    return True, f"mass budget error max {max_error:.3e}%"


def _check_orbit_rollup(ctx: EvaluationContext) -> Tuple[bool, str]:
    df = ctx.orbit_rollup
    missing = [name for name in ORBIT_ROLLUP_COLUMNS if name not in df.columns]
    if missing:
        return False, f"orbit_rollup missing columns: {', '.join(missing)}"
    if df.empty:
        return False, "orbit_rollup.csv is empty"
    return True, f"{len(df)} orbit rollup rows available"


def _check_run_config(ctx: EvaluationContext) -> Tuple[bool, str]:
    config = ctx.run_config
    missing = [name for name in REQUIRED_RUN_CONFIG_FIELDS if name not in config]
    if missing:
        return False, f"run_config missing fields: {', '.join(missing)}"
    provenance = config.get("sublimation_provenance")
    if not isinstance(provenance, dict):
        return False, "sublimation_provenance missing or not a mapping"
    required_provenance_keys = ["psat_model", "alpha_evap", "mu", "P_gas"]
    missing_sub = [key for key in required_provenance_keys if key not in provenance]
    if missing_sub:
        return False, f"sublimation_provenance missing entries: {', '.join(missing_sub)}"
    return True, "run_config metadata present for sublimation provenance"


DEFAULT_CHECKS: Sequence[EvaluationCheck] = [
    EvaluationCheck(
        name="required_outputs",
        description="出力 artefacts (series/summary/checks/orbit_rollup/run_config) の存在確認",
        reference="analysis/run-recipes.md:37-41",
        func=_check_required_outputs,
    ),
    EvaluationCheck(
        name="series_columns",
        description="タイムシリーズの必須列チェック",
        reference=SERIES_COLUMNS_REF,
        func=_check_series_columns,
    ),
    EvaluationCheck(
        name="summary_fields",
        description="summary.json の基本フィールド検証",
        reference=SUMMARY_FIELDS_REF,
        func=_check_summary_fields,
    ),
    EvaluationCheck(
        name="case_status",
        description="β比較に基づく case_status 一貫性",
        reference="analysis/run-recipes.md:45",
        func=_check_case_status,
    ),
    EvaluationCheck(
        name="s_min_components",
        description="s_min_components のキーと floor_mode に応じた s_min_effective 整合",
        reference=S_MIN_REF,
        func=_check_s_min_components,
    ),
    EvaluationCheck(
        name="mass_budget",
        description="質量保存ログの閾値確認",
        reference=MASS_BUDGET_REF,
        func=_check_mass_budget,
    ),
    EvaluationCheck(
        name="orbit_rollup",
        description="公転集計ファイルと列の存在確認",
        reference=ORBIT_ROLLUP_REF,
        func=_check_orbit_rollup,
    ),
    EvaluationCheck(
        name="run_config_meta",
        description="run_config.json の昇華由来メタデータ検証",
        reference=RUN_CONFIG_REF,
        func=_check_run_config,
    ),
]


class EvaluationSystem:
    """Orchestrate evaluation checks for a given output directory."""

    def __init__(self, outdir: Path, checks: Sequence[EvaluationCheck] | None = None) -> None:
        self.outdir = Path(outdir)
        self.checks = list(checks) if checks is not None else list(DEFAULT_CHECKS)

    def run(self) -> List[CheckResult]:
        ctx = EvaluationContext(self.outdir)
        results: List[CheckResult] = []
        for check in self.checks:
            try:
                passed, details = check.func(ctx)
            except Exception as exc:  # pragma: no cover - defensive logging
                passed = False
                details = f"exception: {exc}"
            results.append(
                CheckResult(
                    name=check.name,
                    passed=passed,
                    reference=check.reference,
                    description=check.description,
                    details=details,
                )
            )
        return results


def _render_table(results: Iterable[CheckResult]) -> str:
    lines = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.name}: {result.details} ({result.reference})")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate 0D run outputs using analysis specifications.")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out"),
        help="Evaluation target directory (default: ./out).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    system = EvaluationSystem(args.outdir)
    results = system.run()
    payload = [
        {
            "name": result.name,
            "passed": result.passed,
            "reference": result.reference,
            "description": result.description,
            "details": result.details,
        }
        for result in results
    ]
    failures = [result for result in results if not result.passed]
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_render_table(results))
        print()
        if failures:
            print(f"{len(failures)} check(s) failed.")
        else:
            print("すべての評価チェックに合格しました。")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
