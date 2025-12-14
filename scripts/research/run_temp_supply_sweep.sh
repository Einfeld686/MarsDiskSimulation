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

# Base config to override per run (melt-solid PSD w/ condensation cut)
BASE_CONFIG="${BASE_CONFIG:-configs/sweep_temp_supply/temp_supply_T4000_eps1.yml}"
# qstar unit system (ba99_cgs: cm/g/cm^3/erg/g → J/kg, si: legacy meter/kg)
QSTAR_UNITS="${QSTAR_UNITS:-ba99_cgs}"

# Parameter grids (run hotter cases first)
T_LIST=("5000" "4000" "3000")
MU_LIST=("1.0" "0.5" "0.1")
PHI_LIST=("20" "37" "60")  # maps to tables/phi_const_0pXX.csv

# Fast blow-out substeps (surface_ode path). 0=off, 1=on.
SUBSTEP_FAST_BLOWOUT="${SUBSTEP_FAST_BLOWOUT:-0}"
SUBSTEP_MAX_RATIO="${SUBSTEP_MAX_RATIO:-}"

# Cooling stop condition (dynamic horizon based on Mars cooling time)
COOL_TO_K="${COOL_TO_K:-1000}"                 # stop when Mars T_M reaches this [K]; empty to disable
COOL_MARGIN_YEARS="${COOL_MARGIN_YEARS:-0}"    # padding after reaching COOL_TO_K
COOL_SEARCH_YEARS="${COOL_SEARCH_YEARS:-}"     # optional search cap (years)
# Cooling driver mode: slab (T^-3 analytic slab) or hyodo (linear cooling)
COOL_MODE="${COOL_MODE:-slab}"

# Phase temperature input (Mars surface vs particle equilibrium)
PHASE_TEMP_INPUT="${PHASE_TEMP_INPUT:-particle}"  # mars_surface|particle
PHASE_QABS_MEAN="${PHASE_QABS_MEAN:-0.4}"

# Evaluation toggle (0=skip, 1=run evaluate_tau_supply)
EVAL="${EVAL:-1}"

# Supply/shielding defaults (overridable via env)
# Default is conservative clip + soft gate to avoid spill losses unless明示指定。
SUPPLY_HEADROOM_POLICY="${SUPPLY_HEADROOM_POLICY:-clip}"
SUPPLY_MODE="${SUPPLY_MODE:-const}"
# Raw const supply rate before mixing; μ=1 で 3.0e-5 kg m^-2 s^-1 に設定。
SUPPLY_RATE="${SUPPLY_RATE:-1.0e-4}"  # kg m^-2 s^-1 before mixing
SHIELDING_MODE="${SHIELDING_MODE:-psitau}"
SHIELDING_SIGMA="${SHIELDING_SIGMA:-auto}"
SHIELDING_AUTO_MAX_MARGIN="${SHIELDING_AUTO_MAX_MARGIN:-0.05}"
INIT_SCALE_TO_TAU1="${INIT_SCALE_TO_TAU1:-true}"

# Supply reservoir / feedback / temperature coupling (off by default)
SUPPLY_RESERVOIR_M="${SUPPLY_RESERVOIR_M:-}"                 # Mars masses; empty=disabled
SUPPLY_RESERVOIR_MODE="${SUPPLY_RESERVOIR_MODE:-hard_stop}"  # hard_stop|taper
SUPPLY_RESERVOIR_TAPER="${SUPPLY_RESERVOIR_TAPER:-0.05}"     # used when taper

SUPPLY_FEEDBACK_ENABLED="${SUPPLY_FEEDBACK_ENABLED:-0}"
SUPPLY_FEEDBACK_TARGET="${SUPPLY_FEEDBACK_TARGET:-1.0}"
SUPPLY_FEEDBACK_GAIN="${SUPPLY_FEEDBACK_GAIN:-1.0}"
SUPPLY_FEEDBACK_RESPONSE_YR="${SUPPLY_FEEDBACK_RESPONSE_YR:-0.5}"
SUPPLY_FEEDBACK_MIN_SCALE="${SUPPLY_FEEDBACK_MIN_SCALE:-0.0}"
SUPPLY_FEEDBACK_MAX_SCALE="${SUPPLY_FEEDBACK_MAX_SCALE:-10.0}"
SUPPLY_FEEDBACK_TAU_FIELD="${SUPPLY_FEEDBACK_TAU_FIELD:-tau_vertical}" # tau_vertical|tau_los
SUPPLY_FEEDBACK_INITIAL="${SUPPLY_FEEDBACK_INITIAL:-1.0}"

SUPPLY_TEMP_ENABLED="${SUPPLY_TEMP_ENABLED:-0}"
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

SUPPLY_INJECTION_MODE="${SUPPLY_INJECTION_MODE:-powerlaw_bins}" # min_bin|powerlaw_bins
SUPPLY_INJECTION_Q="${SUPPLY_INJECTION_Q:-3.5}"   # collisional cascade fragments
SUPPLY_INJECTION_SMIN="${SUPPLY_INJECTION_SMIN:-}"
SUPPLY_INJECTION_SMAX="${SUPPLY_INJECTION_SMAX:-}"
SUPPLY_DEEP_TMIX_ORBITS="${SUPPLY_DEEP_TMIX_ORBITS:-}"          # legacy alias for transport.t_mix_orbits
# Prefer buffering overflow in a deep reservoir with soft headroom gate.
SUPPLY_TRANSPORT_MODE="${SUPPLY_TRANSPORT_MODE:-deep_mixing}"   # direct|deep_mixing
SUPPLY_TRANSPORT_TMIX_ORBITS="${SUPPLY_TRANSPORT_TMIX_ORBITS:-50}" # preferred knob when deep_mixing
SUPPLY_TRANSPORT_HEADROOM="${SUPPLY_TRANSPORT_HEADROOM:-soft}"  # hard|soft
SUPPLY_VEL_MODE="${SUPPLY_VEL_MODE:-inherit}"                   # inherit|fixed_ei|factor
SUPPLY_VEL_E="${SUPPLY_VEL_E:-0.05}"
SUPPLY_VEL_I="${SUPPLY_VEL_I:-0.025}"
SUPPLY_VEL_FACTOR="${SUPPLY_VEL_FACTOR:-}"
SUPPLY_VEL_BLEND="${SUPPLY_VEL_BLEND:-rms}"                     # rms|linear
SUPPLY_VEL_WEIGHT="${SUPPLY_VEL_WEIGHT:-delta_sigma}"           # delta_sigma|sigma_ratio

echo "[config] supply multipliers: temp_enabled=${SUPPLY_TEMP_ENABLED} (mode=${SUPPLY_TEMP_MODE}) feedback_enabled=${SUPPLY_FEEDBACK_ENABLED} reservoir=${SUPPLY_RESERVOIR_M:-off}"
echo "[config] shielding: mode=${SHIELDING_MODE} fixed_tau1_sigma=${SHIELDING_SIGMA} auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN} init_scale_to_tau1=${INIT_SCALE_TO_TAU1}"
echo "[config] injection: mode=${SUPPLY_INJECTION_MODE} q=${SUPPLY_INJECTION_Q} s_inj_min=${SUPPLY_INJECTION_SMIN:-none} s_inj_max=${SUPPLY_INJECTION_SMAX:-none}"
echo "[config] transport: mode=${SUPPLY_TRANSPORT_MODE} t_mix=${SUPPLY_TRANSPORT_TMIX_ORBITS:-${SUPPLY_DEEP_TMIX_ORBITS:-disabled}} headroom_gate=${SUPPLY_TRANSPORT_HEADROOM} velocity=${SUPPLY_VEL_MODE}"
echo "[config] const supply before mixing: ${SUPPLY_RATE} kg m^-2 s^-1 (epsilon_mix swept per MU_LIST)"
echo "[config] fast blowout substep: enabled=${SUBSTEP_FAST_BLOWOUT} substep_max_ratio=${SUBSTEP_MAX_RATIO:-default}"
echo "[config] phase temperature input: ${PHASE_TEMP_INPUT} (q_abs_mean=${PHASE_QABS_MEAN})"
if [[ -n "${COOL_TO_K}" ]]; then
  echo "[config] dynamic horizon: stop when Mars T_M <= ${COOL_TO_K} K (margin ${COOL_MARGIN_YEARS} yr, search_cap=${COOL_SEARCH_YEARS:-none})"
else
  echo "[config] dynamic horizon disabled (using numerics.t_end_* from config)"
fi
echo "[config] cooling driver mode: ${COOL_MODE} (slab: T^-3, hyodo: linear flux)"

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
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.enabled=true")
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.mass_total_Mmars=${SUPPLY_RESERVOIR_M}")
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.depletion_mode=${SUPPLY_RESERVOIR_MODE}")
  SUPPLY_OVERRIDES+=(--override "supply.reservoir.taper_fraction=${SUPPLY_RESERVOIR_TAPER}")
  echo "[info] supply reservoir: M=${SUPPLY_RESERVOIR_M} M_Mars mode=${SUPPLY_RESERVOIR_MODE} taper_fraction=${SUPPLY_RESERVOIR_TAPER}"
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
SUPPLY_OVERRIDES+=(--override "supply.injection.mode=${SUPPLY_INJECTION_MODE}")
SUPPLY_OVERRIDES+=(--override "supply.injection.q=${SUPPLY_INJECTION_Q}")
if [[ -n "${SUPPLY_INJECTION_SMIN}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.injection.s_inj_min=${SUPPLY_INJECTION_SMIN}")
fi
if [[ -n "${SUPPLY_INJECTION_SMAX}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.injection.s_inj_max=${SUPPLY_INJECTION_SMAX}")
fi
if [[ -n "${SUPPLY_DEEP_TMIX_ORBITS}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.transport.t_mix_orbits=${SUPPLY_DEEP_TMIX_ORBITS}")
  SUPPLY_OVERRIDES+=(--override "supply.transport.mode=deep_mixing")
  echo "[info] deep reservoir enabled (legacy alias): t_mix=${SUPPLY_DEEP_TMIX_ORBITS} orbits"
fi
if [[ -n "${SUPPLY_TRANSPORT_TMIX_ORBITS}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.transport.t_mix_orbits=${SUPPLY_TRANSPORT_TMIX_ORBITS}")
fi
if [[ -n "${SUPPLY_TRANSPORT_MODE}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.transport.mode=${SUPPLY_TRANSPORT_MODE}")
fi
if [[ -n "${SUPPLY_TRANSPORT_HEADROOM}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.transport.headroom_gate=${SUPPLY_TRANSPORT_HEADROOM}")
fi
SUPPLY_OVERRIDES+=(--override "supply.headroom_policy=${SUPPLY_HEADROOM_POLICY}")
SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.mode=${SUPPLY_VEL_MODE}")
if [[ -n "${SUPPLY_VEL_E}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.e_inj=${SUPPLY_VEL_E}")
fi
if [[ -n "${SUPPLY_VEL_I}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.i_inj=${SUPPLY_VEL_I}")
fi
if [[ -n "${SUPPLY_VEL_FACTOR}" ]]; then
  SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.vrel_factor=${SUPPLY_VEL_FACTOR}")
fi
SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.blend_mode=${SUPPLY_VEL_BLEND}")
SUPPLY_OVERRIDES+=(--override "supply.injection.velocity.weight_mode=${SUPPLY_VEL_WEIGHT}")

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
      eff_rate=$(python - "${SUPPLY_RATE}" "${MU}" <<'PY'
import sys
rate = float(sys.argv[1])
mu = float(sys.argv[2])
print(f"{rate * mu:.3e}")
PY
)
      echo "[info] 実効スケール係数 epsilon_mix=${MU}; effective supply (const×epsilon_mix)=${eff_rate} kg m^-2 s^-1"
      echo "[info] shielding: mode=${SHIELDING_MODE} fixed_tau1_sigma=${SHIELDING_SIGMA} auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN}"
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
        --override numerics.stop_on_blowout_below_smin=true
        --override "io.outdir=${OUTDIR}"
        --override "dynamics.rng_seed=${SEED}"
        --override "phase.enabled=true"
        --override "phase.temperature_input=${PHASE_TEMP_INPUT}"
        --override "phase.q_abs_mean=${PHASE_QABS_MEAN}"
        --override "radiation.TM_K=${T}"
        --override "qstar.coeff_units=${QSTAR_UNITS}"
        --override "radiation.qpr_table_path=marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv"
        --override "radiation.mars_temperature_driver.enabled=true"
      )
      if [[ "${COOL_MODE}" == "hyodo" ]]; then
        cmd+=(--override "radiation.mars_temperature_driver.mode=hyodo")
        cmd+=(--override "radiation.mars_temperature_driver.hyodo.d_layer_m=1.0e5")
        cmd+=(--override "radiation.mars_temperature_driver.hyodo.rho=3000")
        cmd+=(--override "radiation.mars_temperature_driver.hyodo.cp=1000")
      else
        cmd+=(--override "radiation.mars_temperature_driver.mode=table")
        cmd+=(--override "radiation.mars_temperature_driver.table.path=${T_TABLE}")
        cmd+=(--override "radiation.mars_temperature_driver.table.time_unit=day")
        cmd+=(--override "radiation.mars_temperature_driver.table.column_time=time_day")
        cmd+=(--override "radiation.mars_temperature_driver.table.column_temperature=T_K")
        cmd+=(--override "radiation.mars_temperature_driver.extrapolation=hold")
      fi
      cmd+=(
        --override "supply.enabled=true"
        --override "supply.mixing.epsilon_mix=${MU}"
        --override "supply.mode=${SUPPLY_MODE}"
        --override "supply.const.prod_area_rate_kg_m2_s=${SUPPLY_RATE}"
        --override "init_tau1.scale_to_tau1=${INIT_SCALE_TO_TAU1}"
      )
      if [[ -n "${COOL_TO_K}" ]]; then
        cmd+=(--override "numerics.t_end_years=null")
        cmd+=(--override "numerics.t_end_orbits=null")
        cmd+=(--override "numerics.t_end_until_temperature_K=${COOL_TO_K}")
        cmd+=(--override "numerics.t_end_temperature_margin_years=${COOL_MARGIN_YEARS}")
        cmd+=(--override "numerics.t_end_temperature_search_years=${COOL_SEARCH_YEARS:-null}")
        cmd+=(--override "scope.analysis_years=10")
        if [[ -n "${COOL_SEARCH_YEARS}" ]]; then
          cmd+=(--override "numerics.t_end_temperature_search_years=${COOL_SEARCH_YEARS}")
        fi
      fi
      if [[ "${SUBSTEP_FAST_BLOWOUT}" != "0" ]]; then
        cmd+=(--override "io.substep_fast_blowout=true")
        if [[ -n "${SUBSTEP_MAX_RATIO}" ]]; then
          cmd+=(--override "io.substep_max_ratio=${SUBSTEP_MAX_RATIO}")
        fi
      fi
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
      if [[ "${SHIELDING_SIGMA}" == "auto_max" ]]; then
        echo "[warn] fixed_tau1_sigma=auto_max is debug-only; exclude from production figures"
      fi
      if [[ "${INIT_SCALE_TO_TAU1}" != "true" && "${INIT_SCALE_TO_TAU1}" != "True" ]]; then
        echo "[warn] init_tau1.scale_to_tau1 is not 'true'; supply may be clipped at Στ=1"
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
    "supply_rate_nominal",
    "supply_rate_scaled",
    "supply_rate_applied",
    "prod_rate_raw",
    "prod_rate_applied_to_surf",
    "prod_rate_diverted_to_deep",
    "deep_to_surf_flux",
    "supply_headroom",
    "supply_clip_factor",
    "headroom",
    "Sigma_surf",
    "sigma_surf",
    "sigma_deep",
    "Sigma_tau1",
    "sigma_tau1",
    "outflux_surface",
    "t_coll",
    "t_blow_s",
    "dt_over_t_blow",
    "tau",
    "tau_vertical",
    "tau_los_mars",
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

df_full = pd.read_parquet(series_path)
missing_cols = [c for c in series_cols if c not in df_full.columns]
if missing_cols:
    print(f"[warn] missing columns in run.parquet: {missing_cols}")
for col in series_cols:
    if col not in df_full.columns:
        df_full[col] = pd.NA
df = df_full[series_cols].copy()
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
clip_frac = summary.get("supply_clip_time_fraction")
if clip_frac is None:
    clip_frac = summary.get("supply_clipping", {}).get("clip_time_fraction")
if clip_frac is not None:
    title_lines.append(f"clip_zero_frac={float(clip_frac):.2%}")
title_lines.append(f"prod_mean={prod_mean:.3e}")
fig.suptitle(" | ".join(title_lines))
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(plots_dir / "overview.png", dpi=180)
plt.close(fig)

fig2, ax2 = plt.subplots(5, 1, figsize=(10, 16), sharex=True)
ax2[0].plot(df["time_days"], df["supply_rate_nominal"], label="nominal (raw×mix)", color="tab:gray", alpha=0.9)
ax2[0].plot(df["time_days"], df["supply_rate_scaled"], label="scaled (temp/feedback/reservoir)", color="tab:blue")
ax2[0].plot(df["time_days"], df["supply_rate_applied"], label="applied (after headroom)", color="tab:red", alpha=0.8)
ax2[0].plot(df["time_days"], df["prod_rate_applied_to_surf"], label="applied (deep-mixed)", color="tab:orange", alpha=0.8, linestyle="--")
ax2[0].plot(
    df["time_days"],
    df["prod_subblow_area_rate"],
    label="prod_subblow_area_rate (legacy)",
    color="tab:purple",
    linestyle="--",
    alpha=0.5,
)
ax2[0].set_ylabel("kg m^-2 s^-1")
ax2[0].legend(loc="upper right")
ax2[0].set_title("Supply rates (nominal → scaled → applied)")

ax2[1].plot(df["time_days"], df["prod_rate_diverted_to_deep"], label="diverted→deep", color="tab:brown", alpha=0.8)
ax2[1].plot(df["time_days"], df["deep_to_surf_flux"], label="deep→surf flux", color="tab:olive", alpha=0.9)
ax2[1].plot(df["time_days"], df["sigma_deep"], label="sigma_deep", color="tab:gray", alpha=0.7)
ax2[1].set_ylabel("kg m^-2 / s")
ax2[1].legend(loc="upper right")
ax2[1].set_title("Deep reservoir routing")

ax2[2].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
ax2[2].plot(df["time_days"], df["Sigma_tau1"], label="Sigma_tau1", color="tab:orange", alpha=0.8)
ax2[2].plot(df["time_days"], df["supply_headroom"], label="headroom (legacy)", color="tab:brown", alpha=0.7)
ax2[2].plot(df["time_days"], df["headroom"], label="headroom (applied)", color="tab:blue", alpha=0.7, linestyle="--")
ax2[2].set_ylabel("kg m^-2")
ax2[2].legend(loc="upper right")
ax2[2].set_title("Surface density vs tau=1 cap")

ax2[3].plot(df["time_days"], df["outflux_surface"], label="outflux_surface (M_Mars/s)", color="tab:red", alpha=0.9)
ax2[3].plot(df["time_days"], df["tau_vertical"], label="tau_vertical", color="tab:purple", alpha=0.7)
ax2[3].axhline(1.0, color="gray", linestyle=":", alpha=0.6, label="τ=1 reference")
ax2[3].set_yscale("symlog", linthresh=1e-20)
ax2[3].set_ylabel("outflux / tau")
ax2[3].set_xlabel("days")
ax2[3].legend(loc="upper right")
ax2[3].set_title("Surface outflux and optical depth")

ax2[4].plot(df["time_days"], df["supply_feedback_scale"], label="feedback scale", color="tab:cyan")
ax2[4].plot(df["time_days"], df["supply_temperature_scale"], label="temperature scale", color="tab:gray")
ax2[4].plot(df["time_days"], df["supply_reservoir_remaining_Mmars"], label="reservoir M_Mars", color="tab:pink")
ax2[4].plot(df["time_days"], df["supply_clip_factor"], label="clip factor", color="tab:olive", alpha=0.8)
# Add headroom ratio (Sigma_tau1 - Sigma_surf) / Sigma_tau1 for clip context
headroom_ratio = (df["Sigma_tau1"] - df["Sigma_surf"]).clip(lower=0) / df["Sigma_tau1"].clip(lower=1e-20)
ax2[4].plot(df["time_days"], headroom_ratio, label="headroom ratio", color="tab:red", alpha=0.5, linestyle="--")
ax2[4].axhline(0.0, color="gray", linestyle=":", alpha=0.4)
ax2[4].set_ylabel("scale / ratio")
ax2[4].legend(loc="upper right")
ax2[4].set_title("Supply diagnostics (scales + clip factor + headroom ratio)")

fig2.suptitle(run_dir.name)
fig2.tight_layout(rect=(0, 0, 1, 0.95))
fig2.savefig(plots_dir / "supply_surface.png", dpi=180)
plt.close(fig2)

# Optical depth quick-look (vertical, LOS, bulk tau)
def _plot_if_available(ax, x, y, label, **kwargs):
    if y.isna().all():
        return
    ax.plot(x, y, label=label, **kwargs)

fig3, ax3 = plt.subplots(1, 1, figsize=(10, 4))
_plot_if_available(ax3, df["time_days"], df["tau_vertical"], label="tau_vertical", color="tab:purple", alpha=0.9)
_plot_if_available(ax3, df["time_days"], df["tau"], label="tau (bulk)", color="tab:blue", alpha=0.8, linestyle="--")
if "tau_los_mars" in df.columns:
    _plot_if_available(ax3, df["time_days"], df["tau_los_mars"], label="tau_los_mars", color="tab:red", alpha=0.8)
headroom_ratio = (df["Sigma_tau1"] - df["Sigma_surf"]).clip(lower=0) / df["Sigma_tau1"].clip(lower=1e-20)
ax3.plot(df["time_days"], headroom_ratio, label="headroom ratio", color="tab:orange", alpha=0.6, linestyle=":")
ax3.axhline(1.0, color="gray", linestyle=":", alpha=0.5, label="τ=1 reference")
ax3.set_yscale("symlog", linthresh=1e-12)
ax3.set_ylabel("optical depth")
ax3.set_xlabel("days")
ax3.set_title("Optical depth evolution")
ax3.legend(loc="upper right")
fig3.tight_layout()
fig3.savefig(plots_dir / "optical_depth.png", dpi=180)
plt.close(fig3)
print(f"[plot] saved plots to {plots_dir}")
PY
      if [[ "${EVAL}" != "0" ]]; then
        eval_out="${final_dir}/checks/tau_supply_eval.json"
        mkdir -p "$(dirname "${eval_out}")"
        set +e
        python scripts/research/evaluate_tau_supply.py --run-dir "${final_dir}" --window-spans "0.5-1.0" --min-duration-days 0.1 --threshold-factor 0.9 > "${eval_out}"
        eval_rc=$?
        set -e
        if [[ ${eval_rc} -ne 0 ]]; then
          echo "[warn] evaluate_tau_supply failed (rc=${eval_rc}) for ${final_dir}"
        else
          echo "[info] evaluate_tau_supply -> ${eval_out}"
        fi
      fi
    done
  done
done

echo "[done] Sweep completed (batch=${BATCH_SEED}, dir=${BATCH_DIR})."
