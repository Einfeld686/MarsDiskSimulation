"""Scan SiO saturation pressure and HKL flux for the psat auto-selector checks."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
from ruamel.yaml import YAML

from marsdisk import constants
from marsdisk.physics.sublimation import SublimationParams, p_sat


@dataclass(frozen=True)
class CaseConfig:
    name: str
    config_path: Path
    run_dir: Path
    scan_path: Path


def load_sub_params(config_path: Path) -> SublimationParams:
    yaml = YAML(typ="safe")
    data = yaml.load(config_path.read_text(encoding="utf-8"))
    sub_cfg: Dict[str, object] = data["sinks"]["sub_params"]
    # Convert tuples/lists to the dataclass-friendly structures.
    kwargs: Dict[str, object] = dict(sub_cfg)
    table_path = kwargs.get("psat_table_path")
    if table_path:
        kwargs["psat_table_path"] = Path(table_path)
    valid = kwargs.get("valid_K")
    if valid:
        kwargs["valid_K"] = tuple(valid)
    return SublimationParams(**kwargs)


def scan_case(
    case: CaseConfig,
    T_grid: Iterable[float],
) -> Tuple[List[Dict[str, float]], Dict[str, object]]:
    params = load_sub_params(case.config_path)
    mu = params.mu
    alpha = params.alpha_evap
    P_gas = params.P_gas
    rows: List[Dict[str, float]] = []
    J_values: List[float] = []
    for T in T_grid:
        P_sat = float(p_sat(T, params))
        log10P = math.log10(P_sat) if P_sat > 0.0 else float("-inf")
        root = math.sqrt(mu / (2.0 * math.pi * constants.R_GAS * T))
        J = alpha * max(P_sat - P_gas, 0.0) * root
        rows.append({"T_K": T, "log10P_Pa": log10P, "J_kg_m2_s": J})
        J_values.append(J)
    J_arr = np.array(J_values, dtype=float)
    monotonic = bool(np.all(np.diff(J_arr) >= -1e-12))
    finite = bool(np.isfinite(J_arr).all())
    nonnegative = bool((J_arr >= -1e-12).all())
    assertions = {
        "case": case.name,
        "monotonic": monotonic,
        "finite": finite,
        "nonnegative": nonnegative,
        "min_flux": float(J_arr.min()),
        "max_flux": float(J_arr.max()),
    }
    return rows, assertions


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    scans_dir = script_dir / "scans"
    scans_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        CaseConfig(
            name="case_A",
            config_path=script_dir / "inputs" / "case_A_tabulated.yml",
            run_dir=script_dir / "runs" / "case_A_tabulated",
            scan_path=scans_dir / "hkl_scan_case_A.csv",
        ),
        CaseConfig(
            name="case_B",
            config_path=script_dir / "inputs" / "case_B_localfit.yml",
            run_dir=script_dir / "runs" / "case_B_localfit",
            scan_path=scans_dir / "hkl_scan_case_B.csv",
        ),
        CaseConfig(
            name="case_C",
            config_path=script_dir / "inputs" / "case_C_clausius.yml",
            run_dir=script_dir / "runs" / "case_C_clausius",
            scan_path=scans_dir / "hkl_scan_case_C.csv",
        ),
    ]
    T_grid = [float(T) for T in range(1500, 6000 + 1, 50)]
    assertions_summary: Dict[str, Dict[str, object]] = {}
    provenance_summary: Dict[str, object] = {}
    for case in cases:
        run_config_path = case.run_dir / "run_config.json"
        run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
        provenance_raw = run_config.get("sublimation_provenance", {})
        rows, assertions = scan_case(case, T_grid)
        with case.scan_path.open("w", newline="", encoding="ascii") as f:
            writer = csv.DictWriter(f, fieldnames=["T_K", "log10P_Pa", "J_kg_m2_s"])
            writer.writeheader()
            writer.writerows(rows)
        assertions_summary[case.name] = assertions
        provenance_summary[case.name] = {
            "psat_model_resolved": provenance_raw.get("psat_model_resolved"),
            "selection_reason": provenance_raw.get("psat_selection_reason"),
            "A_active": provenance_raw.get("A"),
            "B_active": provenance_raw.get("B"),
            "valid_K_active": provenance_raw.get("valid_K_active"),
            "valid_K_config": provenance_raw.get("valid_K_config"),
            "psat_table_path": provenance_raw.get("psat_table_path"),
            "psat_table_range_K": provenance_raw.get("psat_table_range_K"),
            "T_req_K": provenance_raw.get("T_req"),
            "alpha_evap": provenance_raw.get("alpha_evap"),
            "mu": provenance_raw.get("mu"),
        }
        print(f"{case.name}: wrote {len(rows)} samples to {case.scan_path.relative_to(repo_root)}")
    (scans_dir / "hkl_assertions.json").write_text(
        json.dumps(assertions_summary, indent=2),
        encoding="utf-8",
    )
    (scans_dir / "psat_provenance.json").write_text(
        json.dumps(provenance_summary, indent=2),
        encoding="utf-8",
    )
    print("Assertions collected:", json.dumps(assertions_summary, indent=2))


if __name__ == "__main__":
    main()
