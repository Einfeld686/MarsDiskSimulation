"""Generate a validation report for a simulation run directory.

This helper compares the cumulative mass loss (M_loss) and mass budget error
across multiple runs and writes a machine-readable report to
``<base_run_dir>/checks/validation.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def _read_summary(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found: {summary_path}")
    with summary_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise TypeError(f"summary.json must be a JSON object: {summary_path}")
    return payload


def _require_float(summary: dict[str, Any], key: str, *, label: str) -> float:
    if key not in summary:
        raise KeyError(f"Missing '{key}' in {label}/summary.json")
    try:
        return float(summary[key])
    except Exception as exc:  # pragma: no cover - defensive
        raise TypeError(f"'{key}' must be numeric in {label}/summary.json") from exc


def _rel_diff(base: float, ref: float) -> float:
    if ref == 0.0:
        return 0.0 if base == 0.0 else math.inf
    return abs(base - ref) / abs(ref)


def _build_report(
    *,
    base_dir: Path,
    dt_half_dir: Path | None,
    psd2x_dir: Path | None,
    tol_mass_percent: float,
    tol_rel: float,
) -> dict[str, Any]:
    base_summary = _read_summary(base_dir)
    base_m_loss = _require_float(base_summary, "M_loss", label="base")
    base_mass_err = _require_float(
        base_summary, "mass_budget_max_error_percent", label="base"
    )

    dt_summary: dict[str, Any] | None = None
    dt_m_loss: float | None = None
    dt_rel: float | None = None
    dt_ok: bool | None = None
    if dt_half_dir is not None:
        dt_summary = _read_summary(dt_half_dir)
        dt_m_loss = _require_float(dt_summary, "M_loss", label="dt_half")
        dt_rel = _rel_diff(base_m_loss, dt_m_loss)
        dt_ok = bool(dt_rel <= tol_rel)

    psd_summary: dict[str, Any] | None = None
    psd_m_loss: float | None = None
    psd_rel: float | None = None
    psd_ok: bool | None = None
    if psd2x_dir is not None:
        psd_summary = _read_summary(psd2x_dir)
        psd_m_loss = _require_float(psd_summary, "M_loss", label="psd2x")
        psd_rel = _rel_diff(base_m_loss, psd_m_loss)
        psd_ok = bool(psd_rel <= tol_rel)

    mass_ok = bool(base_mass_err <= tol_mass_percent)
    passed = mass_ok
    if dt_ok is not None:
        passed = passed and dt_ok
    if psd_ok is not None:
        passed = passed and psd_ok

    return {
        "inputs": {
            "base_run_dir": str(base_dir),
            "dt_half_run_dir": str(dt_half_dir) if dt_half_dir is not None else None,
            "psd2x_run_dir": str(psd2x_dir) if psd2x_dir is not None else None,
            "tol_mass_percent": float(tol_mass_percent),
            "tol_rel": float(tol_rel),
        },
        "values": {
            "M_loss_base": base_m_loss,
            "mass_budget_max_error_percent_base": base_mass_err,
            "M_loss_dt_half": dt_m_loss,
            "M_loss_psd2x": psd_m_loss,
            "rel_diff_dt": dt_rel,
            "rel_diff_psd": psd_rel,
        },
        "checks": {
            "mass_ok": mass_ok,
            "dt_ok": dt_ok,
            "psd_ok": psd_ok,
        },
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run-dir", type=Path, required=True)
    parser.add_argument("--dt-half-run-dir", type=Path, default=None)
    parser.add_argument("--psd2x-run-dir", type=Path, default=None)
    parser.add_argument("--tol-mass-percent", type=float, default=0.5)
    parser.add_argument("--tol-rel", type=float, default=0.01)
    args = parser.parse_args(argv)

    base_dir = args.base_run_dir.expanduser().resolve()
    dt_half_dir = args.dt_half_run_dir.expanduser().resolve() if args.dt_half_run_dir else None
    psd2x_dir = args.psd2x_run_dir.expanduser().resolve() if args.psd2x_run_dir else None

    try:
        report = _build_report(
            base_dir=base_dir,
            dt_half_dir=dt_half_dir,
            psd2x_dir=psd2x_dir,
            tol_mass_percent=float(args.tol_mass_percent),
            tol_rel=float(args.tol_rel),
        )
    except Exception as exc:
        print(f"[validate_run] error: {exc}", file=sys.stderr)
        return 1

    checks_dir = base_dir / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    out_path = checks_dir / "validation.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

