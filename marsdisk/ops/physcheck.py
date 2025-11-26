from __future__ import annotations

"""Quick physical consistency checks for the Mars disk model."""

import argparse
import datetime as dt
import json
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import numpy as np

from ..run import load_config
from ..physics import radiation, surface, smol

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "physcheck"
UNKNOWN_JSONL_PATH = REPO_ROOT / "analysis" / "UNKNOWN_REF_REQUESTS.jsonl"
MASS_BUDGET_LOG = REPO_ROOT / "out" / "checks" / "mass_budget.csv"


@dataclass
class CheckResult:
    """Container holding the outcome of a single check."""

    name: str
    status: str  # PASS / WARN / FAIL
    detail: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _dimension_check(config_path: Path) -> CheckResult:
    cfg = load_config(config_path)
    rho = cfg.material.rho if getattr(cfg, "material", None) else 3000.0
    beta_val = radiation.beta(
        s=1e-6,
        T_M=cfg.temps.T_M,
        rho=rho,
        Q_pr=1.0,
    )
    blow = radiation.blowout_radius(rho=rho, T_M=cfg.temps.T_M, Q_pr=1.0)
    if not (0.0 < beta_val < 10.0):
        return CheckResult(
            "dimension:beta",
            "FAIL",
            f"beta returned {beta_val} outside expected dimensionless bounds",
        )
    if blow <= 0.0:
        return CheckResult(
            "dimension:blowout_radius",
            "FAIL",
            f"blowout radius is non-positive ({blow})",
        )
    return CheckResult(
        "dimension:beta",
        "PASS",
        f"beta={beta_val:.3e}, a_blow={blow:.3e} m",
    )


def _limit_check() -> CheckResult:
    sigma = 10.0
    prod = 0.0
    dt_val = 1e-6
    Omega = 1.0
    result = surface.step_surface_density_S1(
        sigma,
        prod,
        dt_val,
        Omega,
        t_coll=None,
        t_sink=None,
        sigma_tau1=None,
    )
    deviation = abs(result.sigma_surf - sigma)
    if deviation > 1e-8:
        return CheckResult(
            "limit:dt->0",
            "WARN",
            f"IMEX limit deviates by {deviation:.3e} when dt->0",
        )
    return CheckResult(
        "limit:dt->0",
        "PASS",
        "Surface density remains stable as dt->0",
    )


def _mass_budget_check() -> CheckResult:
    masses_old = np.array([1.0, 2.0, 3.0])
    growth = np.zeros_like(masses_old)
    masses_new = masses_old + growth
    m_bin = np.array([1.0, 1.0, 1.0])
    err = smol.compute_mass_budget_error_C4(masses_old, masses_new, m_bin, 0.0, 1.0)
    detail = f"synthetic mass budget error={err:.3e}"
    if abs(err) > 1e-12:
        return CheckResult("mass_budget:C4", "FAIL", detail)
    if MASS_BUDGET_LOG.exists():
        try:
            import pandas as pd

            df = pd.read_csv(MASS_BUDGET_LOG)
            max_err = df["mass_budget_error_percent"].abs().max()
            if max_err > 0.5:
                return CheckResult(
                    "mass_budget:log",
                    "FAIL",
                    f"mass_budget.csv exceeds tolerance: {max_err:.3f}%",
                )
        except Exception as exc:  # pragma: no cover - diagnostic guard
            return CheckResult("mass_budget:log", "WARN", f"failed to read mass budget log: {exc}")
    else:
        return CheckResult(
            "mass_budget:log",
            "WARN",
            "out/checks/mass_budget.csv not found; run marsdisk.run to generate it.",
        )
    return CheckResult(
        "mass_budget:log",
        "PASS",
        "Mass budget log exists and meets the <0.5% tolerance.",
    )


def _unknown_reference_check() -> CheckResult:
    if not UNKNOWN_JSONL_PATH.exists():
        return CheckResult(
            "provenance:unknown_refs",
            "WARN",
            "analysis/UNKNOWN_REF_REQUESTS.jsonl missing; update provenance packets.",
        )
    requests: List[Dict[str, object]] = []
    for line in UNKNOWN_JSONL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            requests.append(json.loads(line))
        except json.JSONDecodeError:
            return CheckResult(
                "provenance:unknown_refs",
                "WARN",
                "UNKNOWN_REF_REQUESTS.jsonl contains malformed JSON.",
            )
    if requests:
        return CheckResult(
            "provenance:unknown_refs",
            "WARN",
            f"{len(requests)} provenance gaps remain; see UNKNOWN_REF_REQUESTS.md",
        )
    return CheckResult(
        "provenance:unknown_refs",
        "PASS",
        "All provenance requests resolved.",
    )


def _tl2003_info() -> CheckResult:
    detail = (
        "TL2003 surface ODE remains opt-in for gas-rich tests; default config keeps "
        "ALLOW_TL2003=false."
    )
    logger.info("TL2003 is disabled by default (gas-poor); set ALLOW_TL2003=true to opt-in.")
    return CheckResult("surface:tl2003_scope", "INFO", detail)


def run_checks(config_path: Path) -> List[CheckResult]:
    results = [
        _dimension_check(config_path),
        _limit_check(),
        _mass_budget_check(),
        _unknown_reference_check(),
        _tl2003_info(),
    ]
    return results


def _write_reports(results: Sequence[CheckResult]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"{timestamp}_physcheck.json"
    md_path = REPORT_DIR / f"{timestamp}_physcheck.md"
    payload = {"generated_at": timestamp, "checks": [res.to_dict() for res in results]}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["# PhysCheck レポート", f"- 生成時刻 (UTC): {timestamp}"]
    for res in results:
        lines.append(f"- [{res.status}] {res.name}: {res.detail}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "base.yml",
        help="YAML configuration used to seed the checks.",
    )
    args = parser.parse_args(argv)
    results = run_checks(args.config)
    _write_reports(results)
    has_fail = any(res.status == "FAIL" for res in results)
    return 1 if has_fail else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
