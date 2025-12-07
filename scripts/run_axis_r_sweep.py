#!/usr/bin/env python3
"""Generate Mars disk sweep configurations and execute runs.

This helper automates the multi-parameter sweep described in the agent task:

1. Create per-case YAML configuration files under
   ``analysis/agent_runs/AXIS_r_sweep/configs``.
2. Run ``python -m marsdisk.run`` for each case with the generated config.
3. Verify required outputs exist and collect summary metrics (step 5).

The script is idempotent and will overwrite existing configuration files.
Outputs from ``marsdisk.run`` are placed in dedicated subdirectories under
``analysis/agent_runs/AXIS_r_sweep`` as required by the task instructions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


R_MARS = 3.3895e6  # [m]
OUTPUT_ROOT = Path("analysis/agent_runs/AXIS_r_sweep")
CONFIG_DIR = OUTPUT_ROOT / "configs"
REQUIRED_FILES = [
    Path("series/run.parquet"),
    Path("summary.json"),
    Path("run_config.json"),
]


R_GRID_RM = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6]
T_GRID_K = [
    1800.0,
    2000.0,
    2200.0,
    2400.0,
    2600.0,
    2800.0,
    3000.0,
    3200.0,
    3400.0,
    3600.0,
    3800.0,
    4000.0,
    4200.0,
    4400.0,
    4600.0,
    4800.0,
    5000.0,
    5200.0,
    5400.0,
    5600.0,
    5800.0,
    6000.0,
]
M_GRID_MM = [3.0e-5, 2.0e-5, 1.0e-5]


@dataclass
class CaseResult:
    """Container for per-case run diagnostics."""

    name: str
    r_rm: float
    r_m: float
    temperature_k: float
    mass_mmars: float
    config_path: Path
    outdir: Path
    seed: int
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    missing_outputs: List[Path] = field(default_factory=list)
    summary: Optional[dict] = None
    run_config: Optional[dict] = None

    @property
    def status_label(self) -> str:
        if self.missing_outputs:
            return "missing-output"
        if not self.summary:
            return "summary-missing"
        if self.returncode not in (None, 0):
            return "run-error"
        return "ok"


def format_r_rm(value: float) -> str:
    """Return radius in units of R_M with two decimals."""
    return f"{value:.2f}"


def format_mass_tag(value: float) -> str:
    """Produce compact scientific notation for directory names."""
    if value == 0.0:
        return "0"
    mantissa, exponent = f"{value:.0e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    if not mantissa:
        mantissa = "1"
    sign = exponent[0]
    digits = exponent[1:].lstrip("0") or "0"
    return f"{mantissa}e{sign}{digits}"


def format_float(value: float) -> str:
    """Format floats for YAML fields using up to six significant digits."""
    if value == 0.0:
        return "0.0"
    magnitude = abs(value)
    if magnitude >= 1e5 or magnitude < 1e-3:
        mantissa, exponent = f"{value:.6e}".split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        exponent = exponent.replace("+", "")
        return f"{mantissa}e{exponent}"
    if float(magnitude).is_integer():
        integer = int(round(magnitude))
        return f"{integer:d}" if value >= 0 else f"-{integer:d}"
    return f"{value:.6g}"


def compute_seed(r_m: float, temperature_k: float, mass_mmars: float) -> int:
    """Derive a deterministic RNG seed from the parameter triple."""
    payload = f"{r_m:.6f}|{temperature_k:.1f}|{mass_mmars:.6e}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest, 16) % (2**31)


def render_config_yaml(
    *,
    r_m: float,
    r_rm: float,
    temperature_k: float,
    mass_mmars: float,
    outdir: Path,
    seed: int,
) -> str:
    """Materialise the YAML template with units annotated via inline comments."""

    outdir_str = outdir.as_posix()
    r_rm_str = format_float(r_rm)
    temp_str = format_float(temperature_k)
    return (
        "geometry:\n"
        '  mode: "0D"\n'
        "material:\n"
        "  rho: 2500.0  # [kg/m^3]\n"
        "sizes:\n"
        "  s_min: 1.0e-7  # [m]\n"
        "  s_max: 1.0  # [m]\n"
        "  n_bins: 40\n"
        "initial:\n"
        f"  mass_total: {format_float(mass_mmars)}  # [M_Mars]\n"
        '  s0_mode: "upper"\n'
        "dynamics:\n"
        "  e0: 0.1  # fallback, overridden by e_mode\n"
        "  i0: 0.05  # fallback, overridden by i_mode\n"
        "  t_damp_orbits: 1000.0  # [orbit]\n"
        '  e_mode: "mars_clearance"\n'
        "  dr_min_m: 10.0  # [m]\n"
        "  dr_max_m: 1.0e4  # [m]\n"
        '  dr_dist: "loguniform"\n'
        '  i_mode: "obs_tilt_spread"\n'
        "  obs_tilt_deg: 30.0  # [deg]\n"
        "  i_spread_deg: 5.0  # [deg]\n"
        f"  rng_seed: {seed}\n"
        "psd:\n"
        "  alpha: 3.5\n"
        "  wavy_strength: 0.0\n"
        "qstar:\n"
        "  Qs: 5.0e7\n"
        "  a_s: 0.37\n"
        "  B: 0.3\n"
        "  b_g: 1.36\n"
        "  v_ref_kms: [3.0]\n"
        "disk:\n"
        "  geometry:\n"
        f"    r_in_RM: {r_rm_str}\n"
        f"    r_out_RM: {r_rm_str}\n"
        '    r_profile: "uniform"\n'
        "    p_index: 0.0\n"
        "inner_disk_mass:\n"
        "  use_Mmars_ratio: true\n"
        '  map_to_sigma: "analytic"\n'
        "surface:\n"
        '  init_policy: "clip_by_tau1"\n'
        "  use_tcoll: true\n"
        "sinks:\n"
        "  enable_sublimation: true\n"
        '  mode: "none"\n'
        "  rho_g: 0.0\n"
        "radiation:\n"
        f"  TM_K: {temp_str}\n"
        '  qpr_table_path: "data/qpr_table.csv"\n'
        "  Q_pr: null\n"
        "  use_mars_rp: true\n"
        "  use_solar_rp: false\n"
        "shielding:\n"
        '  mode: "psitau"\n'
        "  table_path: null\n"
        "numerics:\n"
        "  t_end_years: 2.0\n"
        "  dt_init: 10.0\n"
        "  safety: 0.1\n"
        "  atol: 1.0e-10\n"
        "  rtol: 1.0e-6\n"
        "io:\n"
        f'  outdir: "{outdir_str}"\n'
    )


def ensure_directories() -> None:
    """Create output directories if they do not already exist."""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def build_cases(root: Path) -> List[CaseResult]:
    """Construct CaseResult objects for all sweep combinations."""

    cases: List[CaseResult] = []
    ensure_directories()
    for r_rm, temp_k, mass_mm in itertools.product(R_GRID_RM, T_GRID_K, M_GRID_MM):
        r_m = r_rm * R_MARS
        seed = compute_seed(r_m, temp_k, mass_mm)
        r_tag = format_r_rm(r_rm)
        t_tag = f"{int(temp_k):04d}"
        m_tag = format_mass_tag(mass_mm)
        case_name = f"rRM_{r_tag}__TM_{t_tag}__M_{m_tag}"
        config_path = CONFIG_DIR / f"{case_name}.yml"
        outdir = OUTPUT_ROOT / case_name
        cases.append(
            CaseResult(
                name=case_name,
                r_rm=r_rm,
                r_m=r_m,
                temperature_k=temp_k,
                mass_mmars=mass_mm,
                config_path=config_path,
                outdir=outdir,
                seed=seed,
            )
        )
    return cases


def write_configs(cases: Iterable[CaseResult], root: Path) -> None:
    """Write configuration YAML files for each case."""

    for case in cases:
        yaml_content = render_config_yaml(
            r_m=case.r_m,
            r_rm=case.r_rm,
            temperature_k=case.temperature_k,
            mass_mmars=case.mass_mmars,
            outdir=case.outdir,
            seed=case.seed,
        )
        case.config_path.parent.mkdir(parents=True, exist_ok=True)
        case.config_path.write_text(yaml_content, encoding="utf-8")


def run_case(case: CaseResult, root: Path) -> None:
    """Execute marsdisk.run for the provided case."""

    config_rel = case.config_path.as_posix()
    cmd = ["python", "-m", "marsdisk.run", "--config", config_rel]
    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    case.returncode = result.returncode
    case.stdout = result.stdout
    case.stderr = result.stderr

    collect_outputs(case)


def collect_outputs(case: CaseResult) -> None:
    """Populate summary and run_config information for an executed case."""

    missing = []
    for rel_path in REQUIRED_FILES:
        path = case.outdir / rel_path
        if not path.exists():
            missing.append(rel_path)
    case.missing_outputs = missing

    summary_path = case.outdir / "summary.json"
    if summary_path.exists():
        case.summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        case.summary = None

    run_config_path = case.outdir / "run_config.json"
    if run_config_path.exists():
        case.run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    else:
        case.run_config = None


def write_summary_csv(cases: Iterable[CaseResult], output_path: Path) -> None:
    """Aggregate summary metrics into a CSV file as specified in step 5."""

    import csv

    fieldnames = [
        "case_name",
        "r_m",
        "r_RM",
        "T_M[K]",
        "M_init[M_Mars]",
        "M_loss[M_Mars]",
        "case_status",
        "beta_at_smin",
        "s_blow_m",
        "s_min_effective[m]",
        "e_formula_SI",
        "a_m_source",
        "rng_seed",
        "run_returncode",
        "status_label",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for case in cases:
            summary = case.summary or {}
            run_cfg = case.run_config or {}
            init_ei = run_cfg.get("init_ei", {})
            writer.writerow(
                {
                    "case_name": case.name,
                    "r_m": case.r_m,
                    "r_RM": case.r_rm,
                    "T_M[K]": case.temperature_k,
                    "M_init[M_Mars]": case.mass_mmars,
                    "M_loss[M_Mars]": summary.get("M_loss"),
                    "case_status": summary.get("case_status"),
                    "beta_at_smin": summary.get("beta_at_smin_effective"),
                    "s_blow_m": summary.get("s_blow_m"),
                    "s_min_effective[m]": summary.get("s_min_effective"),
                    "e_formula_SI": init_ei.get("e_formula_SI"),
                    "a_m_source": init_ei.get("a_m_source"),
                    "rng_seed": init_ei.get("seed_used", case.seed),
                    "run_returncode": (
                        case.returncode if case.returncode is not None else (0 if case.status_label == "ok" else None)
                    ),
                    "status_label": case.status_label,
                }
            )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AXIS r sweep or regenerate summaries.")
    parser.add_argument(
        "--skip-runs",
        action="store_true",
        help="Skip executing marsdisk.run and only (re-)generate configs and summary CSV.",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    cases = build_cases(root)
    write_configs(cases, root)
    total = len(cases)
    width = max(2, len(str(total)))
    if args.skip_runs:
        for idx, case in enumerate(cases, start=1):
            print(f"[{idx:0{width}d}/{total:0{width}d}] Skipping run for {case.name} (collecting outputs) ...", flush=True)
            collect_outputs(case)
            if case.status_label != "ok":
                print(
                    f"  -> status={case.status_label} missing={[p.as_posix() for p in case.missing_outputs]}",
                    file=sys.stderr,
                )
    else:
        for idx, case in enumerate(cases, start=1):
            print(f"[{idx:0{width}d}/{total:0{width}d}] Running {case.name} ...", flush=True)
            run_case(case, root)
            if case.status_label != "ok":
                print(
                    f"  -> status={case.status_label} returncode={case.returncode} "
                    f"missing={[p.as_posix() for p in case.missing_outputs]}",
                    file=sys.stderr,
                )

    summary_csv = OUTPUT_ROOT / "summary.csv"
    write_summary_csv(cases, summary_csv)
    failures = [case for case in cases if case.status_label != "ok"]
    print(
        f"\nCompleted sweep: {len(cases) - len(failures)} ok / "
        f"{len(failures)} failures. Summary CSV: {summary_csv}",
        flush=True,
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
