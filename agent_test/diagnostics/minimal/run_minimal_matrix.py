#!/usr/bin/env python3
"""Step 18 — supply versus blow-out dM/dt benchmark.

This diagnostic sweeps a coarse grid in orbital radius and mid-plane
temperature and compares the surface-loss budget for three integration
strategies:

1. Baseline (fast blow-out correction disabled).
2. Fast blow-out correction enabled.
3. Fast blow-out sub-stepping enabled.

For each case we run the full two-year integration, collect the final
surface terms (Ω, t_blow, dt/t_blow, dΣ/dt_*), and export both a CSV
summary table and a simple heatmap that visualises the depletion ratio
dΣ̇_blowout / Ṡ_prod.  The baseline branch is cross-checked against the
precomputed ``analysis/radius_sweep/radius_sweep_metrics.csv`` reference
to ensure numerical consistency.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ruamel.yaml import YAML

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk import constants  # noqa: E402

CONFIG_DIR = CURRENT_FILE.parent / "configs"
RUNS_DIR = CURRENT_FILE.parent / "runs"
RESULTS_DIR = CURRENT_FILE.parent / "results"
PLOTS_DIR = CURRENT_FILE.parent / "plots"
FIGURES_DIR = REPO_ROOT / "figures"

T_VALUES = [2000.0, 2500.0, 3000.0]
R_VALUES_RM = [1.4, 1.6, 1.8, 2.0, 2.2]
REFERENCE_T = 2500.0
SUPPLY_RATE_BASE = 5.0e-8
SUPPLY_EXPONENT = 3.0
RELERR_TOL = 1.0e-2

YAML_DUMPER = YAML()
YAML_DUMPER.default_flow_style = False


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    label: str
    correct_fast_blowout: bool
    substep_fast_blowout: bool
    substep_max_ratio: float = 3.0


SERIES: Sequence[SeriesSpec] = [
    SeriesSpec(
        key="baseline",
        label="Baseline (no correction)",
        correct_fast_blowout=False,
        substep_fast_blowout=False,
    ),
    SeriesSpec(
        key="corrected",
        label="Fast blow-out correction",
        correct_fast_blowout=True,
        substep_fast_blowout=False,
    ),
    SeriesSpec(
        key="substepped",
        label="Fast blow-out sub-stepping",
        correct_fast_blowout=False,
        substep_fast_blowout=True,
    ),
]

BASE_CONFIG: dict = {
    "chi_blow": 1.0,
    "geometry": {"mode": "0D", "r": None},
    "material": {"rho": 3000.0},
    "temps": {"T_M": None},
    "radiation": {},
    "sizes": {"s_min": 1.0e-6, "s_max": 3.0, "n_bins": 40},
    "initial": {"mass_total": 1.0e-5, "s0_mode": "upper"},
    "dynamics": {
        "e0": 0.5,
        "i0": 0.05,
        "t_damp_orbits": 1000.0,
        "f_wake": 1.0,
        "rng_seed": 2025,
    },
    "psd": {"alpha": 3.5, "wavy_strength": 0.3},
    "qstar": {"Qs": 3.5e7, "a_s": 0.38, "B": 0.3, "b_g": 1.36, "v_ref_kms": [3.0, 5.0]},
    "supply": {
        "mode": "const",
        "const": {"prod_area_rate_kg_m2_s": SUPPLY_RATE_BASE},
        "mixing": {"epsilon_mix": 1.0},
    },
    "sinks": {
        "mode": "none",
        "enable_sublimation": False,
        "enable_gas_drag": False,
    },
    "surface": {
        "init_policy": "clip_by_tau1",
        "sigma_surf_init_override": None,
        "use_tcoll": True,
    },
    "numerics": {
        "t_end_years": 2.0,
        "dt_init": 6.0e4,
        "safety": 0.1,
        "atol": 1e-10,
        "rtol": 1e-6,
    },
    "io": {
        "outdir": None,
        "debug_sinks": False,
        "correct_fast_blowout": False,
        "substep_fast_blowout": False,
        "substep_max_ratio": 3.0,
    },
}


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def build_config(series: SeriesSpec, T: float, r_rm: float, outdir: Path) -> tuple[dict, float]:
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["geometry"]["r"] = float(r_rm * constants.R_MARS)
    cfg["temps"]["T_M"] = float(T)
    cfg["io"]["outdir"] = str(outdir)
    cfg["io"]["correct_fast_blowout"] = bool(series.correct_fast_blowout)
    cfg["io"]["substep_fast_blowout"] = bool(series.substep_fast_blowout)
    cfg["io"]["substep_max_ratio"] = float(series.substep_max_ratio)

    scale = (min(R_VALUES_RM) / r_rm) ** SUPPLY_EXPONENT
    supply_rate = SUPPLY_RATE_BASE * scale
    cfg["supply"]["const"]["prod_area_rate_kg_m2_s"] = supply_rate

    return cfg, supply_rate


def write_yaml(config: dict, path: Path) -> None:
    ensure_dirs([path.parent])
    with path.open("w", encoding="utf-8") as handle:
        YAML_DUMPER.dump(config, handle)


def run_case(config_path: Path) -> None:
    cmd = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path)]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _read_summary(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing summary.json at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_timeseries(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing time series parquet at {path}")
    return pd.read_parquet(path)


def _resolve_scalar(row: pd.Series, *keys: str, default: float | None = None) -> float:
    for key in keys:
        if key in row and pd.notna(row[key]):
            return float(row[key])
    if default is not None:
        return float(default)
    raise KeyError(f"None of the requested keys {keys} found in row")


def collect_metrics(run_dir: Path) -> dict:
    ts_path = run_dir / "series" / "run.parquet"
    df = _read_timeseries(ts_path)
    if df.empty:
        raise ValueError(f"No rows in time series at {ts_path}")
    final = df.iloc[-1]

    d_sigma_blow = _resolve_scalar(final, "dSigma_dt_blowout", "outflux_surface")
    d_sigma_sinks = _resolve_scalar(final, "dSigma_dt_sinks", "sink_flux_surface", default=0.0)
    d_sigma_total = _resolve_scalar(final, "dSigma_dt_total", default=d_sigma_blow + d_sigma_sinks)
    prod_rate = _resolve_scalar(final, "prod_subblow_area_rate")

    ratio = np.nan
    if abs(prod_rate) > 0.0:
        ratio = d_sigma_blow / prod_rate

    n_substeps = final.get("n_substeps", 1.0)
    if pd.isna(n_substeps):
        n_substeps = 1.0

    return {
        "time_final_s": _resolve_scalar(final, "time"),
        "dt_s": _resolve_scalar(final, "dt"),
        "Omega_s": _resolve_scalar(final, "Omega_s"),
        "t_blow_s": _resolve_scalar(final, "t_blow_s", "t_blow"),
        "dt_over_t_blow": _resolve_scalar(final, "dt_over_t_blow", "fast_blowout_ratio"),
        "prod_subblow_area_rate": prod_rate,
        "dSigma_dt_blowout": d_sigma_blow,
        "dSigma_dt_sinks": d_sigma_sinks,
        "dSigma_dt_total": d_sigma_total,
        "blowout_to_supply_ratio": ratio,
        "M_out_dot": _resolve_scalar(final, "M_out_dot", default=0.0),
        "M_sink_dot": _resolve_scalar(final, "M_sink_dot", default=0.0),
        "dM_dt_surface_total": _resolve_scalar(final, "dM_dt_surface_total", default=0.0),
        "fast_blowout_ratio": _resolve_scalar(final, "fast_blowout_ratio", "dt_over_t_blow"),
        "fast_blowout_factor": _resolve_scalar(final, "fast_blowout_factor", default=0.0),
        "fast_blowout_factor_avg": _resolve_scalar(final, "fast_blowout_factor_avg", "fast_blowout_factor", default=0.0),
        "fast_blowout_corrected": bool(final.get("fast_blowout_corrected", False)),
        "fast_blowout_flag_gt3": bool(final.get("fast_blowout_flag_gt3", False)),
        "fast_blowout_flag_gt10": bool(final.get("fast_blowout_flag_gt10", False)),
        "n_substeps": float(n_substeps),
        "chi_blow_eff": _resolve_scalar(final, "chi_blow_eff", default=1.0),
        "tau_final": _resolve_scalar(final, "tau", default=np.nan),
        "s_min_final": _resolve_scalar(final, "s_min", "s_min_effective", default=np.nan),
        "beta_at_smin_effective": _resolve_scalar(
            final,
            "beta_at_smin_effective",
            "beta_at_smin",
            default=np.nan,
        ),
        "case_status": str(final.get("case_status", "")),
    }


def compare_with_reference(df: pd.DataFrame) -> list[dict[str, float]]:
    """Cross-check baseline branch against the archived radius sweep."""
    ref_path = REPO_ROOT / "analysis" / "radius_sweep" / "radius_sweep_metrics.csv"
    if not ref_path.exists():
        return []

    ref_df = pd.read_csv(ref_path)
    baseline = df[
        (df["series"] == "baseline")
        & np.isclose(df["T_input"], REFERENCE_T, atol=1e-6)
    ]
    if baseline.empty:
        raise AssertionError(
            f"No baseline rows found at T={REFERENCE_T} K for reference comparison"
        )

    shared_radii = sorted(set(baseline["r_RM"]).intersection(ref_df["r_over_RM"]))
    if not shared_radii:
        raise AssertionError("No shared radii between new results and reference table")

    metrics = ["Omega_s", "t_blow_s", "dt_over_t_blow", "dSigma_dt_blowout", "M_out_dot"]
    records: list[dict[str, float]] = []
    for r_rm in shared_radii:
        new_row = baseline[np.isclose(baseline["r_RM"], r_rm, atol=1e-6)].iloc[0]
        ref_row = ref_df[np.isclose(ref_df["r_over_RM"], r_rm, atol=1e-6)].iloc[0]
        for key in metrics:
            new_val = float(new_row[key])
            ref_val = float(ref_row[key])
            if pd.isna(ref_val):
                continue
            if ref_val == 0.0:
                rel_err = abs(new_val - ref_val)
            else:
                rel_err = abs(new_val - ref_val) / abs(ref_val)
            records.append(
                {
                    "series": "baseline",
                    "T_input": REFERENCE_T,
                    "r_RM": r_rm,
                    "metric": key,
                    "reference": ref_val,
                    "computed": new_val,
                    "rel_error": rel_err,
                    "within_tol": bool(rel_err <= RELERR_TOL),
                }
            )

    worst = max(records, key=lambda rec: rec["rel_error"])
    if not worst["within_tol"]:
        raise AssertionError(
            f"Reference mismatch for {worst['metric']} at r={worst['r_RM']:.2f} R_M: "
            f"computed={worst['computed']}, ref={worst['reference']}, "
            f"rel_err={worst['rel_error']:.3e} (tol={RELERR_TOL:.3e})"
        )

    return records


def make_heatmap(df: pd.DataFrame, path: Path) -> None:
    ensure_dirs([path.parent])

    radii = sorted(df["r_RM"].unique())
    temps = sorted(df["T_input"].unique())
    r_index = {value: idx for idx, value in enumerate(radii)}
    t_index = {value: idx for idx, value in enumerate(temps)}

    fig, axes = plt.subplots(1, len(SERIES), figsize=(4.5 * len(SERIES), 4.2), sharex=True, sharey=True)
    cmap = plt.get_cmap("viridis")
    vmin, vmax = 0.0, 2.5

    for ax, series in zip(np.atleast_1d(axes), SERIES):
        grid = np.full((len(radii), len(temps)), np.nan)
        subset = df[df["series"] == series.key]
        for _, row in subset.iterrows():
            i = r_index[row["r_RM"]]
            j = t_index[row["T_input"]]
            grid[i, j] = row["blowout_to_supply_ratio"]

        im = ax.imshow(
            grid,
            origin="lower",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            aspect="auto",
        )
        ax.set_title(series.label, fontsize=11)
        ax.set_xticks(range(len(temps)))
        ax.set_xticklabels([f"{t:.0f}" for t in temps])
        ax.set_xlabel("temps.T_M [K]")
        ax.set_yticks(range(len(radii)))
        ax.set_yticklabels([f"{r:.1f}" for r in radii])
        ax.set_ylabel("r / R_M")
        for i, r_val in enumerate(radii):
            for j, t_val in enumerate(temps):
                value = grid[i, j]
                if np.isnan(value):
                    continue
                ax.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    color="white" if value > (vmax + vmin) / 2 else "black",
                    fontsize=8,
                )

    axes_list = np.atleast_1d(axes).ravel().tolist()
    cbar = fig.colorbar(im, ax=axes_list, shrink=0.85)
    cbar.set_label("dΣ̇_blowout / Ṡ_prod")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    ensure_dirs([CONFIG_DIR, RUNS_DIR, RESULTS_DIR, PLOTS_DIR, FIGURES_DIR])

    records: list[dict] = []
    for series in SERIES:
        for r_rm in R_VALUES_RM:
            for T in T_VALUES:
                case_id = f"{series.key}_T{int(round(T)):04d}_R{int(round(r_rm * 100)):03d}"
                run_dir = RUNS_DIR / series.key / case_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)

                config, supply_rate = build_config(series, T, r_rm, run_dir)
                config_path = CONFIG_DIR / series.key / f"{case_id}.yml"
                write_yaml(config, config_path)
                run_case(config_path)

                summary = _read_summary(run_dir / "summary.json")
                metrics = collect_metrics(run_dir)

                record = {
                    "case_id": case_id,
                    "series": series.key,
                    "series_label": series.label,
                    "T_input": float(T),
                    "T_M_used": summary.get("T_M_used"),
                    "r_RM": float(r_rm),
                    "r_m": config["geometry"]["r"],
                    "supply_rate_config": supply_rate,
                    "M_loss": summary.get("M_loss"),
                    "M_loss_from_sinks": summary.get("M_loss_from_sinks", 0.0),
                    "M_loss_from_sublimation": summary.get("M_loss_from_sublimation", 0.0),
                    "s_blow_m": summary.get("s_blow_m"),
                    "beta_at_smin_effective_summary": summary.get("beta_at_smin_effective"),
                }
                record.update(metrics)
                records.append(record)

    df = pd.DataFrame.from_records(records)
    df.sort_values(
        ["series", "r_RM", "T_input"],
        inplace=True,
        kind="mergesort",
    )

    results_csv = RESULTS_DIR / "supply_vs_blowout.csv"
    df.to_csv(results_csv, index=False)

    comparison_records = compare_with_reference(df)
    if comparison_records:
        comparison_path = RESULTS_DIR / "supply_vs_blowout_reference_check.json"
        with comparison_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "tolerance": RELERR_TOL,
                    "records": comparison_records,
                },
                handle,
                indent=2,
                sort_keys=True,
            )

    local_plot = PLOTS_DIR / "supply_vs_blowout.png"
    make_heatmap(df, local_plot)
    global_plot = FIGURES_DIR / "supply_vs_blowout.png"
    shutil.copy2(local_plot, global_plot)

    print(f"Wrote {len(df)} records to {results_csv}")
    if comparison_records:
        print(
            "Reference cross-check passed; worst relative error "
            f"{max(rec['rel_error'] for rec in comparison_records):.3e}"
        )
    print(f"Heatmap stored at {local_plot} and {global_plot}")


if __name__ == "__main__":
    main()
