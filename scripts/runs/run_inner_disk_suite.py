#!/usr/bin/env python3
"""Temperature and shielding sweep for the inner Roche-limit disk (0D model).

This helper automates the suite requested in the agent task:

* Sweep Mars-facing temperatures from 1000 K to 6000 K in 50 K increments.
* Toggle three constant self-shielding factors Φ(1) = {0.20, 0.37, 0.60}.
* Hold the inner-disk mass at 1×10⁻⁵ M_Mars and evolve the PSD for one year.
* Capture the PSD histogram at every step, render PNG frames and generate GIFs.
* Produce per-orbit mass-loss summaries for title annotations.

The script relies on ``python -m marsdisk.run`` and stores outputs under
``runs/inner_disk_suite/phi_<value>/TM_<value>`` by default.  It is safe to
re-run the helper thanks to the ``--skip-existing`` guard.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import imageio.v2 as imageio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk import constants

SEC_PER_DAY = 86400.0
GIF_FPS = 6
REQUIRED_OUTPUTS = [
    Path("series/run.parquet"),
    Path("series/psd_hist.parquet"),
    Path("summary.json"),
    Path("run_config.json"),
    Path("checks/mass_budget.csv"),
    Path("orbit_rollup.csv"),
]


def _resolve_table_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        parquet_path = path.with_suffix(".parquet")
        if parquet_path.exists():
            if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
                return parquet_path
    elif suffix in {".parquet", ".pq"} and not path.exists():
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
    return path


@dataclass(frozen=True)
class CaseSpec:
    """Description of a single (Φ, T_M) run."""

    phi: float
    temperature_k: float
    r_rm: float
    r_m: float
    t_orb: float
    outdir: Path
    phi_table_path: Path


def format_phi_tag(value: float) -> str:
    """Return a compact identifier for Φ."""

    return f"{value:.2f}".replace(".", "p")


def compute_orbit(r_rm: float) -> Tuple[float, float]:
    """Return (r_m, orbital period) for a given radius in Mars radii."""

    r_m = r_rm * constants.R_MARS
    Omega = math.sqrt(constants.G * constants.M_MARS / (r_m**3))
    t_orb = 2.0 * math.pi / Omega
    return r_m, t_orb


def build_overrides(spec: CaseSpec) -> List[str]:
    """Assemble CLI ``--override`` strings for a single case."""

    base = [
        f"disk.geometry.r_in_RM={spec.r_rm:.6f}",
        f"disk.geometry.r_out_RM={spec.r_rm:.6f}",
        f"numerics.dt_init={spec.t_orb:.6e}",
        "numerics.t_end_years=1.0",
        "numerics.orbit_rollup=true",
        f"radiation.TM_K={spec.temperature_k:.1f}",
        "shielding.mode=table",
        f"shielding.table_path={spec.phi_table_path.as_posix()}",
        "inner_disk_mass.use_Mmars_ratio=true",
        "inner_disk_mass.M_over_Mmars=1.0e-5",
        "sizes.s_min=1.0e-7",
        "sizes.s_max=1.0",
        "sizes.n_bins=80",
        f"io.outdir={spec.outdir.as_posix()}",
        "sinks.mode=none",
    ]
    return base


def ensure_required_outputs(case: CaseSpec) -> None:
    """Verify that all required files exist."""

    missing: List[Path] = []
    for rel in REQUIRED_OUTPUTS:
        path = _resolve_table_path(case.outdir / rel)
        if not path.exists():
            missing.append(path)
    if missing:
        missing_str = ", ".join(str(p) for p in missing)
        raise RuntimeError(f"Missing outputs for {case.outdir}: {missing_str}")


def load_series_tables(case: CaseSpec) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (run.parquet, psd_hist.parquet) frames."""

    run_df = pd.read_parquet(case.outdir / "series" / "run.parquet")
    hist_df = pd.read_parquet(case.outdir / "series" / "psd_hist.parquet")
    return run_df, hist_df


def render_psd_frames(
    case: CaseSpec,
    run_df: pd.DataFrame,
    hist_df: pd.DataFrame,
) -> List[Path]:
    """Render PSD snapshots for each recorded step and return frame paths."""

    frames_dir = case.outdir / "figs"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: List[Path] = []
    grouped = hist_df.groupby("time", sort=True)
    mass_series = run_df.set_index("time")["mass_lost_by_blowout"]
    sigma_series = run_df.set_index("time")["Sigma_surf"] if "Sigma_surf" in run_df.columns else None
    for idx, (time_s, sub) in enumerate(grouped):
        s_vals = sub["s_bin_center"].to_numpy(dtype=float)
        n_vals = sub["N_bin"].to_numpy(dtype=float)
        if s_vals.size == 0:
            continue
        fig, ax = plt.subplots(figsize=(6.0, 4.0))
        ax.plot(s_vals, n_vals, marker="o", linestyle="-", color="#0052a5", markersize=3.0)
        ax.set_xscale("log")
        ax.set_xlabel("粒径 s [m]")
        ax.set_ylabel("個数密度 (任意単位)")
        time_days = time_s / SEC_PER_DAY
        mass_lost = mass_series.get(time_s, float("nan"))
        subtitle = f"t = {time_days:.2f} 日, M_out = {mass_lost:.3e} M_Mars"
        if sigma_series is not None:
            sigma_val = sigma_series.get(time_s, float("nan"))
            subtitle += f", Σ_surf = {sigma_val:.3e} kg m⁻²"
        ax.set_title(
            f"Φ(1) = {case.phi:.2f}, T_M = {case.temperature_k:.0f} K\n{subtitle}",
            fontsize=11,
        )
        fig.text(
            0.02,
            0.02,
            "惑星放射起因のブローアウト",
            fontsize=9,
            color="#444444",
        )
        ax.grid(True, which="both", alpha=0.2)
        frame_path = frames_dir / f"frame_{idx:04d}.png"
        fig.tight_layout()
        fig.savefig(frame_path, dpi=150)
        plt.close(fig)
        frame_paths.append(frame_path)
    return frame_paths


def make_gif(frame_paths: Sequence[Path], gif_path: Path) -> None:
    """Bundle rendered PNGs into a GIF."""

    if not frame_paths:
        return
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    images = [imageio.imread(path) for path in frame_paths]
    imageio.mimsave(gif_path, images, fps=GIF_FPS)


def export_orbit_summary(case: CaseSpec) -> Path:
    """Create a compact CSV with orbit-level blow-out losses."""

    source = _resolve_table_path(case.outdir / "orbit_rollup.csv")
    if not source.exists():
        raise RuntimeError(f"orbit_rollup.csv not found for {case.outdir}")
    if source.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(source)
    else:
        df = pd.read_csv(source)
    keep_cols = [
        "orbit_index",
        "time_s",
        "M_out_orbit",
        "M_sink_orbit",
        "M_loss_orbit",
    ]
    subset = df[keep_cols].copy()
    subset.rename(
        columns={
            "time_s": "time_s_end",
            "M_out_orbit": "mass_blowout_Mmars",
            "M_sink_orbit": "mass_sinks_Mmars",
            "M_loss_orbit": "mass_total_Mmars",
        },
        inplace=True,
    )
    path = case.outdir / "orbit_rollup_summary.csv"
    subset.to_csv(path, index=False)
    return path


def write_command_metadata(case: CaseSpec, command: Sequence[str], result: subprocess.CompletedProcess[str]) -> None:
    """Persist the command line and execution log for provenance."""

    meta_dir = case.outdir / "logs"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "command.txt").write_text(" ".join(command) + "\n", encoding="utf-8")
    payload = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    (meta_dir / "command.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_cases(
    *,
    phi_values: Iterable[float],
    r_rm: float,
    temperature_min: float,
    temperature_max: float,
    temperature_step: float,
    out_root: Path,
    phi_table_root: Path,
) -> List[CaseSpec]:
    """Materialise the full list of case specifications."""

    cases: List[CaseSpec] = []
    temperature_values = np.arange(temperature_min, temperature_max + 0.5 * temperature_step, temperature_step)
    r_m, t_orb = compute_orbit(r_rm)
    for phi in phi_values:
        phi_tag = format_phi_tag(phi)
        phi_table = _resolve_table_path(phi_table_root / f"phi_const_{phi_tag}.csv")
        if not phi_table.exists():
            raise FileNotFoundError(f"Φ table not found: {phi_table}")
        for temperature in temperature_values:
            outdir = out_root / f"phi_{phi_tag}" / f"TM_{int(round(temperature)):04d}"
            cases.append(
                CaseSpec(
                    phi=float(phi),
                    temperature_k=float(temperature),
                    r_rm=float(r_rm),
                    r_m=r_m,
                    t_orb=t_orb,
                    outdir=outdir,
                    phi_table_path=phi_table,
                )
            )
    return cases


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Inner disk sweep with PSD GIF generation")
    parser.add_argument("--config", type=Path, default=Path("configs/base.yml"), help="Base YAML configuration")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python interpreter to invoke")
    parser.add_argument("--r-rm", type=float, default=2.5, help="Representative radius in Mars radii")
    parser.add_argument("--temperature-min", type=float, default=1000.0, help="Minimum Mars-facing temperature [K]")
    parser.add_argument("--temperature-max", type=float, default=6000.0, help="Maximum Mars-facing temperature [K]")
    parser.add_argument("--temperature-step", type=float, default=50.0, help="Temperature increment [K]")
    parser.add_argument(
        "--phi",
        type=float,
        nargs="+",
        default=[0.20, 0.37, 0.60],
        help="Constant Φ(1) values to sweep",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("runs/inner_disk_suite"),
        help="Root directory for run outputs",
    )
    parser.add_argument(
        "--phi-table-root",
        type=Path,
        default=Path("tables"),
        help="Directory containing Φ(τ) lookup CSV files",
    )
    parser.add_argument(
        "--gif-phi",
        type=float,
        default=0.37,
        help="Φ value used for the three highlighted GIF exports",
    )
    parser.add_argument(
        "--gif-temperatures",
        type=float,
        nargs="+",
        default=[2000.0, 4000.0, 6000.0],
        help="Temperature subset for the highlighted GIF exports",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip runs whose summary.json is already present",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands without executing marsdisk.run",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    cases = build_cases(
        phi_values=args.phi,
        r_rm=args.r_rm,
        temperature_min=args.temperature_min,
        temperature_max=args.temperature_max,
        temperature_step=args.temperature_step,
        out_root=args.out_root,
        phi_table_root=args.phi_table_root,
    )

    highlighted_phi = args.gif_phi
    highlighted_temperatures = {float(t) for t in args.gif_temperatures}
    highlighted_root = args.out_root / "animations"
    highlighted_root.mkdir(parents=True, exist_ok=True)

    for idx, case in enumerate(cases, start=1):
        summary_path = case.outdir / "summary.json"
        if args.skip_existing and summary_path.exists():
            print(f"[SKIP] {case.outdir} (summary.json already exists)")
            continue

        case.outdir.mkdir(parents=True, exist_ok=True)
        overrides = build_overrides(case)
        command: List[str] = [str(args.python), "-m", "marsdisk.run", "--config", str(args.config)]
        for item in overrides:
            command.extend(["--override", item])

        print(f"[{idx:03d}/{len(cases):03d}] Φ={case.phi:.2f}, T_M={case.temperature_k:.0f} K → {case.outdir}")
        if args.dry_run:
            print("  command:", " ".join(command))
            continue

        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
        write_command_metadata(case, command, result)
        if result.returncode != 0:
            raise RuntimeError(
                f"marsdisk.run failed for Φ={case.phi:.2f}, T_M={case.temperature_k:.0f} K "
                f"with return code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        ensure_required_outputs(case)
        run_df, hist_df = load_series_tables(case)
        frame_paths = render_psd_frames(case, run_df, hist_df)
        gif_path = case.outdir / "animations" / "psd_evolution.gif"
        make_gif(frame_paths, gif_path)
        orbit_summary_path = export_orbit_summary(case)
        print(f"  frames: {len(frame_paths)}, gif: {gif_path}, orbit summary: {orbit_summary_path}")

        if math.isclose(case.phi, highlighted_phi, rel_tol=0.0, abs_tol=5e-4):
            temp_int = int(round(case.temperature_k))
            if (
                abs(case.temperature_k - float(temp_int)) <= 1.0e-6
                and float(temp_int) in highlighted_temperatures
                and gif_path.exists()
            ):
                target = highlighted_root / f"Phi{format_phi_tag(case.phi)}_TM{temp_int:04d}.gif"
                shutil.copyfile(gif_path, target)
                print(f"  highlighted GIF copied to {target}")


if __name__ == "__main__":
    main()
