#!/usr/bin/env bash
# Run temp supply parameter sweep:
#   T_M = {2000, 4000, 6000} K
#   epsilon_mix = {0.1, 0.5, 1.0}
#   shielding.table_path = {phi_const_0p20, phi_const_0p37, phi_const_0p60}
# 出力は out/temp_supply_sweep/<ts>__<sha>__seed<batch>/T{T}_eps{eps}_phi{phi}/ に配置。

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
BATCH_ROOT_FALLBACK="out"
BATCH_ROOT_DEFAULT_EXT="/Volumes/KIOXIA/marsdisk_out"
if [[ -n "${OUT_ROOT:-}" ]]; then
  BATCH_ROOT="${OUT_ROOT}"
elif [[ -d "/Volumes/KIOXIA" && -w "/Volumes/KIOXIA" ]]; then
  # Use external SSD by default when available.
  BATCH_ROOT="${BATCH_ROOT_DEFAULT_EXT}"
else
  BATCH_ROOT="${BATCH_ROOT_FALLBACK}"
fi
BATCH_DIR="${BATCH_ROOT}/temp_supply_sweep/${RUN_TS}__${GIT_SHA}__seed${BATCH_SEED}"
echo "[setup] Output root: ${BATCH_ROOT}"
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

# Base config to override per run
BASE_CONFIG="configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"

# Parameter grids (run hotter cases first)
T_LIST=("6000" "4000" "2000")
MU_LIST=("1.0" "0.5" "0.1")
PHI_LIST=("20" "37" "60")  # maps to tables/phi_const_0pXX.csv

# Supply/shielding defaults (overridable via env)
SUPPLY_MODE="${SUPPLY_MODE:-const}"
SUPPLY_RATE="${SUPPLY_RATE:-1.0e-10}"  # kg m^-2 s^-1 before mixing
SHIELDING_MODE="${SHIELDING_MODE:-fixed_tau1}"
SHIELDING_SIGMA="${SHIELDING_SIGMA:-1.0e-2}"

# Progress bar: default ON when stdout is a TTY; OFF otherwise to avoid CR->LF spam.
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

STREAM_MEM_GB="${STREAM_MEM_GB:-}"
STREAM_STEP_INTERVAL="${STREAM_STEP_INTERVAL:-}"
STREAMING_OVERRIDES=()
if [[ -n "${STREAM_MEM_GB}" ]]; then
  STREAMING_OVERRIDES+=(--override "io.streaming.memory_limit_gb=${STREAM_MEM_GB}")
  echo "[info] override io.streaming.memory_limit_gb=${STREAM_MEM_GB}"
fi
if [[ -n "${STREAM_STEP_INTERVAL}" ]]; then
  STREAMING_OVERRIDES+=(--override "io.streaming.step_flush_interval=${STREAM_STEP_INTERVAL}")
  echo "[info] override io.streaming.step_flush_interval=${STREAM_STEP_INTERVAL}"
fi

for T in "${T_LIST[@]}"; do
  T_TABLE="data/mars_temperature_T${T}p0K.csv"
  for MU in "${MU_LIST[@]}"; do
    MU_TITLE="${MU/0./0p}"
    MU_TITLE="${MU_TITLE/./p}"
    for PHI in "${PHI_LIST[@]}"; do
      SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
      TITLE="T${T}_mu${MU_TITLE}_phi${PHI}"
      OUTDIR="${BATCH_DIR}/${TITLE}"
      echo "[run] T=${T} mu=${MU} phi=${PHI} -> ${OUTDIR} (batch=${BATCH_SEED}, seed=${SEED})"
      if [[ "${MU}" == "0.1" ]]; then
        echo "[info] mu=0.1 is a low-supply extreme case; expect weak blowout/sinks"
      fi
      cmd=(
        python -m marsdisk.run
        --config "${BASE_CONFIG}"
        --quiet
      )
      if ((${#PROGRESS_FLAG[@]})); then
        cmd+=("${PROGRESS_FLAG[@]}")
      fi
      cmd+=(
        --override numerics.dt_init=20
        --override "io.outdir=${OUTDIR}"
        --override "dynamics.rng_seed=${SEED}"
        --override "radiation.TM_K=${T}"
        --override "radiation.mars_temperature_driver.table.path=${T_TABLE}"
        --override "supply.enabled=true"
        --override "supply.mixing.epsilon_mix=${MU}"
        --override "supply.mode=${SUPPLY_MODE}"
        --override "supply.const.prod_area_rate_kg_m2_s=${SUPPLY_RATE}"
      )
      if ((${#STREAMING_OVERRIDES[@]})); then
        cmd+=("${STREAMING_OVERRIDES[@]}")
      fi
      cmd+=(--override "shielding.table_path=tables/phi_const_0p${PHI}.csv")
      cmd+=(--override "shielding.mode=${SHIELDING_MODE}")
      if [[ "${SHIELDING_MODE}" == "fixed_tau1" ]]; then
        cmd+=(--override "shielding.fixed_tau1_sigma=${SHIELDING_SIGMA}")
      fi
      "${cmd[@]}"

      final_dir="${OUTDIR}"
      mkdir -p "${final_dir}/series" "${final_dir}/checks"

      # Generate quick-look plots into <final_dir>/plots
      RUN_DIR="${final_dir}" python - <<'PY'
import os
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import pandas as pd
import matplotlib.pyplot as plt

run_dir = Path(os.environ["RUN_DIR"])
series_path = run_dir / "series" / "run.parquet"
summary_path = run_dir / "summary.json"
plots_dir = run_dir / "plots"
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
    "Sigma_tau1",
    "outflux_surface",
    "t_coll",
    "t_blow_s",
    "dt_over_t_blow",
    "tau_vertical",
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
df["t_coll_years"] = (df["t_coll"].clip(lower=1e-6)) / 31557600.0
df["t_blow_hours"] = (df["t_blow_s"].clip(lower=1e-12)) / 3600.0
prod_mean = float(df["prod_subblow_area_rate"].mean()) if not df.empty else 0.0

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

axes[2].plot(df["time_days"], df["t_coll_years"], label="t_coll (yr)", lw=1.0)
axes[2].plot(df["time_days"], df["t_blow_hours"], label="t_blow (hr)", lw=1.0, alpha=0.8)
axes[2].plot(df["time_days"], df["dt_over_t_blow"], label="dt / t_blow", lw=0.9, alpha=0.7)
axes[2].set_yscale("log")
axes[2].set_ylabel("timescales (log)")
axes[2].set_xlabel("days")
axes[2].legend(loc="upper right")
axes[2].set_title("Timescales (collisional vs blowout)")

mloss = summary.get("M_loss")
mass_err = summary.get("mass_budget_max_error_percent")
title_lines = [run_dir.name]
if mloss is not None:
    title_lines.append(f"M_loss={mloss:.3e} M_Mars")
if mass_err is not None:
    title_lines.append(f"mass budget err={mass_err:.3f}%")
title_lines.append(f"prod_mean={prod_mean:.3e} kg m^-2 s^-1")
fig.suptitle(" | ".join(title_lines))
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(plots_dir / "overview.png", dpi=180)
plt.close(fig)

fig2, ax2 = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
ax2[0].plot(df["time_days"], df["prod_subblow_area_rate"], label="prod_subblow_area_rate", color="tab:blue")
ax2[0].set_ylabel("kg m^-2 s^-1")
ax2[0].set_title("Sub-blow supply rate")

ax2[1].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
ax2[1].plot(df["time_days"], df["Sigma_tau1"], label="Sigma_tau1", color="tab:orange", alpha=0.8)
ax2[1].set_ylabel("kg m^-2")
ax2[1].legend(loc="upper right")
ax2[1].set_title("Surface density vs tau=1 cap")

ax2[2].plot(df["time_days"], df["outflux_surface"], label="outflux_surface (M_Mars/s)", color="tab:red", alpha=0.9)
ax2[2].plot(df["time_days"], df["tau_vertical"], label="tau_vertical", color="tab:purple", alpha=0.7)
ax2[2].set_yscale("symlog", linthresh=1e-20)
ax2[2].set_ylabel("outflux / tau")
ax2[2].set_xlabel("days")
ax2[2].legend(loc="upper right")
ax2[2].set_title("Surface outflux and optical depth")

fig2.suptitle(run_dir.name)
fig2.tight_layout(rect=(0, 0, 1, 0.95))
fig2.savefig(plots_dir / "supply_surface.png", dpi=180)
plt.close(fig2)
print(f"[plot] saved plots to {plots_dir}")
PY
    done
  done
done

echo "[done] Sweep completed (batch=${BATCH_SEED}, dir=${BATCH_DIR})."
