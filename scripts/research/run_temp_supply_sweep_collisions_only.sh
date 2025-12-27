#!/usr/bin/env bash
# Run temp supply sweep (collisions only)
# T_M = {2000, 4000, 6000}
# epsilon_mix = {0.1, 0.5, 1.0}
# mu_orbit10pct = 1.0 (1 orbit supplies 10% of Sigma_ref(tau=1); scaled by orbit_fraction_at_mu1)
# tau0_target = {1.0, 0.5, 0.1}
# Outputs under: out/temp_supply_sweep/<ts>__<sha>__seed<BATCH>/T{T}_eps{eps}_tau{tau}_mode-collisions_only/

set -euo pipefail

VENV_DIR=".venv"
REQ_FILE="requirements.txt"
RUN_TS="$(date +%Y%m%d-%H%M%S)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
BATCH_SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
BATCH_DIR="out/temp_supply_sweep/${RUN_TS}__${GIT_SHA}__seed${BATCH_SEED}"
mkdir -p "${BATCH_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[setup] Creating virtual environment in ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

if [[ -f "${REQ_FILE}" ]]; then
  echo "[setup] Installing/upgrading dependencies from ${REQ_FILE} ..."
  python -m pip install --upgrade pip
  pip install -r "${REQ_FILE}"
else
  echo "[warn] ${REQ_FILE} not found; skipping dependency install."
fi

BASE_CONFIG="configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"
T_LIST=("2000" "4000" "6000")
EPS_LIST=("0.1" "0.5" "1.0")
TAU_LIST=("1.0" "0.5" "0.1")
MODE="collisions_only"
SUPPLY_MU_ORBIT10PCT="${SUPPLY_MU_ORBIT10PCT:-1.0}"
SUPPLY_ORBIT_FRACTION="${SUPPLY_ORBIT_FRACTION:-0.10}"

PROGRESS_FLAG=()
if [[ -t 1 ]]; then
  if [[ "${ENABLE_PROGRESS:-1}" != "0" ]]; then
    PROGRESS_FLAG=(--progress)
  fi
else
  if [[ "${ENABLE_PROGRESS:-0}" == "1" ]]; then
    echo "[warn] stdout is not a TTY; progress bar disabled to avoid newline spam"
  fi
  PROGRESS_FLAG=()
fi

for T in "${T_LIST[@]}"; do
  T_TABLE="data/mars_temperature_T${T}p0K.csv"
  for EPS in "${EPS_LIST[@]}"; do
    EPS_TITLE="${EPS/0./0p}"
    EPS_TITLE="${EPS_TITLE/./p}"
    for TAU in "${TAU_LIST[@]}"; do
      TAU_TITLE="${TAU/0./0p}"
      TAU_TITLE="${TAU_TITLE/./p}"
      SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
      TITLE="T${T}_eps${EPS_TITLE}_tau${TAU_TITLE}_mode-${MODE}"
      OUTDIR="${BATCH_DIR}/${TITLE}"
      echo "[run] mode=${MODE} T=${T} eps=${EPS} tau=${TAU} -> ${OUTDIR} (batch=${BATCH_SEED}, seed=${SEED})"
      python -m marsdisk.run \
        --config "${BASE_CONFIG}" \
        --quiet \
        "${PROGRESS_FLAG[@]}" \
        --override numerics.dt_init=20 \
        --override "io.outdir=${OUTDIR}" \
        --override "dynamics.rng_seed=${SEED}" \
        --override "radiation.TM_K=${T}" \
        --override "radiation.mars_temperature_driver.table.path=${T_TABLE}" \
        --override "supply.mixing.epsilon_mix=${EPS}" \
        --override "supply.const.mu_orbit10pct=${SUPPLY_MU_ORBIT10PCT}" \
        --override "supply.const.orbit_fraction_at_mu1=${SUPPLY_ORBIT_FRACTION}" \
        --override "optical_depth.tau0_target=${TAU}" \
        --override "shielding.mode=off" \
        --override "physics_mode=${MODE}"

      RUN_DIR="${OUTDIR}" python - <<'PY'
import os
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import pyarrow.parquet as pq
import pandas as pd
import matplotlib.pyplot as plt

run_dir = Path(os.environ["RUN_DIR"])
series_dir = run_dir / "series"
series_path = series_dir / "run.parquet"
summary_path = run_dir / "summary.json"

def _is_one_d(series_dir: Path, series_path: Path) -> bool:
    if series_path.exists():
        try:
            return "cell_index" in set(pq.read_schema(series_path).names)
        except Exception:
            return False
    chunk_files = sorted(series_dir.glob("run_chunk_*.parquet"))
    if not chunk_files:
        return False
    try:
        return "cell_index" in set(pq.read_schema(chunk_files[0]).names)
    except Exception:
        return False

plots_dir = run_dir / ("figures" if _is_one_d(series_dir, series_path) else "plots")
plots_dir.mkdir(parents=True, exist_ok=True)

if not series_path.exists():
    print(f"[warn] series not found: {series_path}, skip plotting")
    raise SystemExit(0)

series_cols = [
    "time",
    "M_out_dot",
    "M_sink_dot",
    "M_loss_cum",
    "mass_lost_by_blowout",
    "mass_lost_by_sinks",
    "s_min",
    "a_blow",
    "prod_subblow_area_rate",
    "Sigma_surf",
    "outflux_surface",
]

summary = {}
if summary_path.exists():
    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        summary = {}

df = pd.read_parquet(series_path, columns=series_cols)
n = len(df)
step = max(n // 4000, 1)
df = df.iloc[::step].copy()
df["time_days"] = df["time"] / 86400.0

fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
axes[0].plot(df["time_days"], df["M_out_dot"], label="M_out_dot (blowout)", lw=1.2)
axes[0].plot(df["time_days"], df["M_sink_dot"], label="M_sink_dot (sinks)", lw=1.0, alpha=0.7)
axes[0].set_ylabel("M_Mars / s")
axes[0].legend(loc="upper right")
axes[0].set_title("Mass loss rates")

axes[1].plot(df["time_days"], df["M_loss_cum"], label="M_loss_cum (total)", lw=1.2)
axes[1].plot(df["time_days"], df["mass_lost_by_blowout"], label="mass_lost_by_blowout", lw=1.0)
axes[1].plot(df["time_days"], df["mass_lost_by_sinks"], label="mass_lost_by_sinks", lw=1.0)
axes[1].set_ylabel("M_Mars")
axes[1].legend(loc="upper left")
axes[1].set_title("Cumulative losses")

axes[2].plot(df["time_days"], df["s_min"], label="s_min", lw=1.0)
axes[2].plot(df["time_days"], df["a_blow"], label="a_blow", lw=1.0, alpha=0.8)
axes[2].set_ylabel("m")
axes[2].set_xlabel("days")
axes[2].set_yscale("log")
axes[2].legend(loc="upper right")
axes[2].set_title("Minimum size vs blowout")

mloss = summary.get("M_loss")
mass_err = summary.get("mass_budget_max_error_percent")
title_lines = [run_dir.name]
if mloss is not None:
    title_lines.append(f"M_loss={mloss:.3e} M_Mars")
if mass_err is not None:
    title_lines.append(f"mass budget err={mass_err:.3f}%")
fig.suptitle(" | ".join(title_lines))
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(plots_dir / "overview.png", dpi=180)
plt.close(fig)

fig2, ax2 = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
ax2[0].plot(df["time_days"], df["prod_subblow_area_rate"], label="prod_subblow_area_rate", color="tab:blue")
ax2[0].set_ylabel("kg m^-2 s^-1")
ax2[0].set_title("Sub-blow supply rate")

ax2[1].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
ax2[1].plot(df["time_days"], df["outflux_surface"], label="outflux_surface (surface blowout)", color="tab:red", alpha=0.8)
ax2[1].set_ylabel("kg m^-2 / M_Mars s^-1")
ax2[1].set_xlabel("days")
ax2[1].legend(loc="upper right")
ax2[1].set_title("Surface mass and outflux")

fig2.suptitle(run_dir.name)
fig2.tight_layout(rect=(0, 0, 1, 0.95))
fig2.savefig(plots_dir / "supply_surface.png", dpi=180)
plt.close(fig2)
print(f"[plot] saved plots to {plots_dir}")
PY
    done
  done
done

echo "[done] Sweep (collisions_only) completed (batch=${BATCH_SEED}, dir=${BATCH_DIR})."
