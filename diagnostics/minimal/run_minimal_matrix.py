#!/usr/bin/env python3
"""Temperature sweep diagnostic to expose radiation.TM_K overrides.

The script compares two series:
* Series A fixes ``radiation.TM_K`` while varying ``temps.T_M``.
* Series B omits the override and relies on ``temps.T_M``.

For each series we sweep three temperatures (1800/2000/2200 K) and two
orbital radii.  Outputs include a CSV table, a simple line plot, and
assertions that capture the expected trends.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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

T_VALUES = [1800.0, 2000.0, 2200.0]
R_VALUES_RM = [2.4, 3.6]
TM_OVERRIDE = 2000.0
SUPPLY_RATE_BASE = 5.0e-8
SUPPLY_EXPONENT = 3.0
LOSS_CONST_R_TOL = 0.01
LOSS_MONO_TOL = 0.05
INNER_MARGIN = 0.05

YAML_DUMPER = YAML()
YAML_DUMPER.default_flow_style = False


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    label: str
    override_tm: bool


SERIES: list[SeriesSpec] = [
    SeriesSpec(key="override", label="A: radiation.TM_K fixed", override_tm=True),
    SeriesSpec(key="temps", label="B: temps.T_M direct", override_tm=False),
]

BASE_CONFIG: dict = {
    "geometry": {"mode": "0D", "r": None},
    "material": {"rho": 3000.0},
    "temps": {"T_M": None},
    "radiation": {},
    "sizes": {"s_min": 1.0e-7, "s_max": 1.0e-2, "n_bins": 40},
    "initial": {"mass_total": 1.0e-6, "s0_mode": "upper"},
    "dynamics": {
        "e0": 0.1,
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
        "T_sub": 1300.0,
        "sub_params": {
            "mode": "logistic",
            "alpha_evap": 1.0,
            "mu": 0.1,
            "A": None,
            "B": None,
            "dT": 50.0,
            "eta_instant": 0.1,
            "P_gas": 0.0,
        },
        "enable_gas_drag": False,
        "rho_g": 0.0,
    },
    "surface": {
        "init_policy": "clip_by_tau1",
        "sigma_surf_init_override": None,
        "use_tcoll": True,
    },
    "numerics": {
        "t_end_years": 0.05,
        "dt_init": 5.0e3,
        "safety": 0.1,
        "atol": 1e-10,
        "rtol": 1e-6,
    },
    "io": {"outdir": None},
}


def ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def build_config(series: SeriesSpec, T: float, r_rm: float, outdir: Path) -> tuple[dict, float]:
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["geometry"]["r"] = float(r_rm * constants.R_MARS)
    cfg["temps"]["T_M"] = float(T)
    cfg["io"]["outdir"] = str(outdir)

    scale = (min(R_VALUES_RM) / r_rm) ** SUPPLY_EXPONENT
    supply_rate = SUPPLY_RATE_BASE * scale
    cfg["supply"]["const"]["prod_area_rate_kg_m2_s"] = supply_rate

    if series.override_tm:
        cfg["radiation"] = {"TM_K": TM_OVERRIDE}
    else:
        cfg.pop("radiation", None)

    return cfg, supply_rate


def write_yaml(config: dict, path: Path) -> None:
    ensure_dirs([path.parent])
    with path.open("w", encoding="utf-8") as handle:
        YAML_DUMPER.dump(config, handle)


def run_case(config_path: Path) -> None:
    cmd = [sys.executable, "-m", "marsdisk.run", "--config", str(config_path)]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def evaluate_series_a(df: pd.DataFrame) -> dict[str, bool]:
    cond_loss = True
    cond_s_blow = True
    for _, group in df.groupby("r_RM"):
        ref_loss = group["M_loss"].iloc[0]
        ref_s_blow = group["s_blow_m"].iloc[0]
        if not np.allclose(group["M_loss"], ref_loss, rtol=LOSS_CONST_R_TOL, atol=0.0):
            cond_loss = False
        if not np.allclose(group["s_blow_m"], ref_s_blow, rtol=LOSS_CONST_R_TOL, atol=0.0):
            cond_s_blow = False
    return {"A_constant_M_loss": cond_loss, "A_constant_s_blow": cond_s_blow}


def evaluate_series_b(df: pd.DataFrame) -> dict[str, bool]:
    cond_monotonic = True
    cond_inner = True

    for _, group in df.groupby("r_RM"):
        ordered = group.sort_values("T_input")
        values = ordered["M_loss"].to_numpy()
        if values.size >= 2:
            diffs = np.diff(values)
            prev = values[:-1]
            if np.any(diffs < -LOSS_MONO_TOL * prev):
                cond_monotonic = False

    radii = np.sort(df["r_RM"].unique())
    if radii.size >= 2:
        inner = df[df["r_RM"] == radii[0]].set_index("T_input")
        outer = df[df["r_RM"] == radii[-1]].set_index("T_input")
        for T in T_VALUES:
            if T not in inner.index or T not in outer.index:
                continue
            inner_loss = float(inner.loc[T, "M_loss"])
            outer_loss = float(outer.loc[T, "M_loss"])
            if inner_loss < (1.0 + INNER_MARGIN) * outer_loss:
                cond_inner = False
                break
    else:
        cond_inner = False

    return {
        "B_monotonic_M_loss": cond_monotonic,
        "B_inner_radius_dominant": cond_inner,
    }


def make_plot(df: pd.DataFrame, path: Path) -> None:
    ensure_dirs([path.parent])
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 4.0), sharey=True)
    for ax, series in zip(axes, SERIES):
        subset = df[df["series"] == series.key]
        for r_rm in R_VALUES_RM:
            sub = subset[subset["r_RM"] == r_rm].sort_values("T_input")
            if sub.empty:
                continue
            ax.plot(
                sub["T_input"],
                sub["M_loss"],
                marker="o",
                label=f"r = {r_rm:.1f} R_M",
            )
        ax.set_title(series.label, fontsize=10)
        ax.set_xlabel("temps.T_M input [K]")
        ax.grid(True, linestyle="--", alpha=0.3)
    axes[0].set_ylabel("M_loss [M_Mars]")
    axes[1].legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    ensure_dirs([CONFIG_DIR, RUNS_DIR, RESULTS_DIR, PLOTS_DIR])

    records: list[dict] = []
    for series in SERIES:
        for r_rm in R_VALUES_RM:
            for T in T_VALUES:
                case_id = f"{series.key}_T{int(T):04d}_R{int(round(r_rm * 10)):03d}"
                run_dir = RUNS_DIR / series.key / case_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)

                config, supply_rate = build_config(series, T, r_rm, run_dir)
                config_path = CONFIG_DIR / series.key / f"{case_id}.yml"
                write_yaml(config, config_path)
                run_case(config_path)

                summary_path = run_dir / "summary.json"
                if not summary_path.exists():
                    raise FileNotFoundError(f"Missing summary.json for {case_id}")
                with summary_path.open("r", encoding="utf-8") as handle:
                    summary = json.load(handle)

                records.append(
                    {
                        "case_id": case_id,
                        "series": series.key,
                        "series_label": series.label,
                        "T_input": T,
                        "T_M_used": summary["T_M_used"],
                        "T_M_source": summary["T_M_source"],
                        "r_RM": r_rm,
                        "r_m": config["geometry"]["r"],
                        "supply_rate": supply_rate,
                        "M_loss": summary["M_loss"],
                        "s_blow_m": summary["s_blow_m"],
                        "outdir": str(run_dir),
                    }
                )

    df = pd.DataFrame.from_records(records)
    df.sort_values(["series", "r_RM", "T_input"], inplace=True)

    results_csv = RESULTS_DIR / "temperature_override.csv"
    df.to_csv(results_csv, index=False)

    series_a = df[df["series"] == "override"]
    if series_a.empty:
        raise AssertionError("Series A produced no records")
    series_b = df[df["series"] == "temps"]
    if series_b.empty:
        raise AssertionError("Series B produced no records")

    conds_a = evaluate_series_a(series_a)
    conds_b = evaluate_series_b(series_b)

    if not conds_a["A_constant_M_loss"]:
        raise AssertionError("Series A mass loss depends on temps.T_M despite override")
    if not conds_a["A_constant_s_blow"]:
        raise AssertionError("Series A blow-out size varies across T inputs")
    if not conds_b["B_monotonic_M_loss"]:
        raise AssertionError("Series B mass loss is not monotonic with temperature")
    if not conds_b["B_inner_radius_dominant"]:
        raise AssertionError("Series B inner radius does not lose more mass than outer radius")

    conditions = {**conds_a, **conds_b}
    with (RESULTS_DIR / "temperature_override_conditions.json").open("w", encoding="utf-8") as handle:
        json.dump(conditions, handle, indent=2, sort_keys=True)

    make_plot(df, PLOTS_DIR / "temperature_override.png")

    print(f"Wrote {len(df)} records to {results_csv}")
    print("Condition checks:", json.dumps(conditions, indent=2))


if __name__ == "__main__":
    main()
