#!/usr/bin/env bash
# Run temp supply parameter sweep:
#   T_M = {2000, 4000, 6000} K
#   epsilon_mix = {0.1, 0.5, 1.0}
#   shielding.table_path = {phi_const_0p20, phi_const_0p37, phi_const_0p60}
# 出力は out/temp_supply_sweep/<ts>__<sha>__seed<batch>/T{T}_eps{eps}_phi{phi}/ に配置。
# 供給は supply.* による外部源（温度・τフィードバック・有限リザーバ対応）。

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
SUPPLY_RATE="${SUPPLY_RATE:-3.0e-3}"  # kg m^-2 s^-1 before mixing
SHIELDING_MODE="${SHIELDING_MODE:-fixed_tau1}"
SHIELDING_SIGMA="${SHIELDING_SIGMA:-auto}"
SHIELDING_AUTO_MAX_MARGIN="${SHIELDING_AUTO_MAX_MARGIN:-0.05}"
INIT_SCALE_TO_TAU1="${INIT_SCALE_TO_TAU1:-true}"

# Supply reservoir / feedback / temperature coupling (off by default)
SUPPLY_RESERVOIR_M="${SUPPLY_RESERVOIR_M:-}"             # Mars masses; empty=disabled
SUPPLY_RESERVOIR_MODE="${SUPPLY_RESERVOIR_MODE:-hard_stop}"  # hard_stop|smooth
SUPPLY_RESERVOIR_SMOOTH="${SUPPLY_RESERVOIR_SMOOTH:-0.1}"    # used when smooth

SUPPLY_FEEDBACK_ENABLED="${SUPPLY_FEEDBACK_ENABLED:-1}"
SUPPLY_FEEDBACK_TARGET="${SUPPLY_FEEDBACK_TARGET:-1.0}"
SUPPLY_FEEDBACK_GAIN="${SUPPLY_FEEDBACK_GAIN:-1.0}"
SUPPLY_FEEDBACK_RESPONSE_YR="${SUPPLY_FEEDBACK_RESPONSE_YR:-0.5}"
SUPPLY_FEEDBACK_MIN_SCALE="${SUPPLY_FEEDBACK_MIN_SCALE:-0.0}"
SUPPLY_FEEDBACK_MAX_SCALE="${SUPPLY_FEEDBACK_MAX_SCALE:-10.0}"
SUPPLY_FEEDBACK_TAU_FIELD="${SUPPLY_FEEDBACK_TAU_FIELD:-tau_vertical}" # tau_vertical|tau_los
SUPPLY_FEEDBACK_INITIAL="${SUPPLY_FEEDBACK_INITIAL:-1.0}"

SUPPLY_TEMP_ENABLED="${SUPPLY_TEMP_ENABLED:-1}"
SUPPLY_TEMP_MODE="${SUPPLY_TEMP_MODE:-scale}"            # scale|table
SUPPLY_TEMP_REF_K="${SUPPLY_TEMP_REF_K:-1800.0}"
SUPPLY_TEMP_EXP="${SUPPLY_TEMP_EXP:-1.0}"
SUPPLY_TEMP_SCALE_REF="${SUPPLY_TEMP_SCALE_REF:-1.0}"
SUPPLY_TEMP_FLOOR="${SUPPLY_TEMP_FLOOR:-0.0}"
SUPPLY_TEMP_CAP="${SUPPLY_TEMP_CAP:-10.0}"
SUPPLY_TEMP_TABLE_PATH="${SUPPLY_TEMP_TABLE_PATH:-}"
SUPPLY_TEMP_TABLE_VALUE_KIND="${SUPPLY_TEMP_TABLE_VALUE_KIND:-scale}" # scale|rate
SUPPLY_TEMP_TABLE_COL_T="${SUPPLY_TEMP_TABLE_COL_T:-T_K}"
SUPPLY_TEMP_TABLE_COL_VAL="${SUPPLY_TEMP_TABLE_COL_VAL:-value}"

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

SUPPLY_OVERRIDES=()
if [[ -n "${SUPPLY_RESERVOIR_M}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.mass_total_Mmars=${SUPPLY_RESERVOIR_M}")
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.depletion_mode=${SUPPLY_RESERVOIR_MODE}")
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.smooth_fraction=${SUPPLY_RESERVOIR_SMOOTH}")
  echo "[info] supply reservoir: M=${SUPPLY_RESERVOIR_M} M_Mars mode=${SUPPLY_RESERVOIR_MODE} smooth=${SUPPLY_RESERVOIR_SMOOTH}"
fi
if [[ "${SUPPLY_FEEDBACK_ENABLED}" != "0" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.feedback.enabled=true")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.target_tau=${SUPPLY_FEEDBACK_TARGET}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.gain=${SUPPLY_FEEDBACK_GAIN}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.response_time_years=${SUPPLY_FEEDBACK_RESPONSE_YR}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.min_scale=${SUPPLY_FEEDBACK_MIN_SCALE}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.max_scale=${SUPPLY_FEEDBACK_MAX_SCALE}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.tau_field=${SUPPLY_FEEDBACK_TAU_FIELD}")
  SUPPLY_OVERRIDES+=(--override "supply.feedback.initial_scale=${SUPPLY_FEEDBACK_INITIAL}")
  echo "[info] supply feedback enabled: target_tau=${SUPPLY_FEEDBACK_TARGET}, gain=${SUPPLY_FEEDBACK_GAIN}, tau_field=${SUPPLY_FEEDBACK_TAU_FIELD}"
fi
if [[ "${SUPPLY_TEMP_ENABLED}" != "0" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.temperature.enabled=true")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.mode=${SUPPLY_TEMP_MODE}")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.reference_K=${SUPPLY_TEMP_REF_K}")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.exponent=${SUPPLY_TEMP_EXP}")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.scale_at_reference=${SUPPLY_TEMP_SCALE_REF}")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.floor=${SUPPLY_TEMP_FLOOR}")
  SUPPLY_OVERRIDES+=(--override "supply.temperature.cap=${SUPPLY_TEMP_CAP}")
  if [[ -n "${SUPPLY_TEMP_TABLE_PATH}" ]]; then
    SUPPLY_OVERRIDES+=(--override "supply.temperature.table.path=${SUPPLY_TEMP_TABLE_PATH}")
    SUPPLY_OVERRIDES+=(--override "supply.temperature.table.value_kind=${SUPPLY_TEMP_TABLE_VALUE_KIND}")
    SUPPLY_OVERRIDES+=(--override "supply.temperature.table.column_temperature=${SUPPLY_TEMP_TABLE_COL_T}")
    SUPPLY_OVERRIDES+=(--override "supply.temperature.table.column_value=${SUPPLY_TEMP_TABLE_COL_VAL}")
  fi
  echo "[info] supply temperature coupling enabled: mode=${SUPPLY_TEMP_MODE}"
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
        --override "init_tau1.scale_to_tau1=${INIT_SCALE_TO_TAU1}"
      )
      if ((${#SUPPLY_OVERRIDES[@]})); then
        cmd+=("${SUPPLY_OVERRIDES[@]}")
      fi
      if ((${#STREAMING_OVERRIDES[@]})); then
        cmd+=("${STREAMING_OVERRIDES[@]}")
      fi
      cmd+=(--override "shielding.table_path=tables/phi_const_0p${PHI}.csv")
      cmd+=(--override "shielding.mode=${SHIELDING_MODE}")
      if [[ "${SHIELDING_MODE}" == "fixed_tau1" ]]; then
        cmd+=(--override "shielding.fixed_tau1_sigma=${SHIELDING_SIGMA}")
        cmd+=(--override "shielding.auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN}")
      fi
      set +e
      "${cmd[@]}"
      rc=$?
      set -e
      if [[ ${rc} -ne 0 ]]; then
        echo "[warn] run command exited with status ${rc}; attempting plots anyway"
      fi

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
    "supply_feedback_scale",
    "supply_temperature_scale",
    "supply_reservoir_remaining_Mmars",
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
effective_prod = summary.get("effective_prod_rate_kg_m2_s")
if effective_prod is not None:
    title_lines.append(f"prod_eff={effective_prod:.2e}")
title_lines.append(f"prod_mean={prod_mean:.3e}")
fig.suptitle(" | ".join(title_lines))
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(plots_dir / "overview.png", dpi=180)
plt.close(fig)

fig2, ax2 = plt.subplots(4, 1, figsize=(10, 14), sharex=True)
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

ax2[3].plot(df["time_days"], df["supply_feedback_scale"], label="feedback scale", color="tab:cyan")
ax2[3].plot(df["time_days"], df["supply_temperature_scale"], label="temperature scale", color="tab:gray")
ax2[3].plot(df["time_days"], df["supply_reservoir_remaining_Mmars"], label="reservoir M_Mars", color="tab:pink")
ax2[3].set_ylabel("scale / M_Mars")
ax2[3].legend(loc="upper right")
ax2[3].set_title("Supply diagnostics")

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
