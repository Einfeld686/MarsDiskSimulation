#!/usr/bin/env bash
# Run temp supply parameter sweep:
#   T_M = {2000, 4000, 6000} K
#   epsilon_mix = {0.1, 0.5, 1.0}
#   mu_orbit10pct = 1.0 (1 orbit supplies 10% of Sigma_ref(tau=1); scaled by orbit_fraction_at_mu1)
#   optical_depth.tau0_target = {1.0, 0.5, 0.1}
# 出力は out/temp_supply_sweep/<ts>__<sha>__seed<batch>/T{T}_eps{eps}_tau{tau}/ に配置。
# 供給は supply.* による外部源（温度・τフィードバック・有限リザーバ対応）。

set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
SKIP_SETUP="${SKIP_SETUP:-0}"
RUN_ONE_MODE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --run-one)
      RUN_ONE_MODE=1
      shift
      ;;
    *)
      break
      ;;
  esac
done

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
SWEEP_TAG="${SWEEP_TAG:-temp_supply_sweep}"
if [[ -n "${OUT_ROOT:-}" ]]; then
  BATCH_ROOT="${OUT_ROOT}"
elif [[ -d "/Volumes/KIOXIA" && -w "/Volumes/KIOXIA" ]]; then
  # Use external SSD by default when available.
  BATCH_ROOT="${BATCH_ROOT_DEFAULT_EXT}"
else
  BATCH_ROOT="${BATCH_ROOT_FALLBACK}"
fi
echo "[setup] Output root: ${BATCH_ROOT}"

if [[ "${SKIP_SETUP}" == "1" || "${SKIP_SETUP}" == "true" ]]; then
  echo "[setup] SKIP_SETUP=1; skipping venv setup and dependency install."
else
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
fi

# Base config to override per run (melt-solid PSD w/ condensation cut)
BASE_CONFIG="${BASE_CONFIG:-configs/sweep_temp_supply/temp_supply_T4000_eps1.yml}"
# qstar unit system (ba99_cgs: cm/g/cm^3/erg/g → J/kg, si: legacy meter/kg)
QSTAR_UNITS="${QSTAR_UNITS:-ba99_cgs}"
GEOMETRY_MODE="${GEOMETRY_MODE:-0D}"
GEOMETRY_NR="${GEOMETRY_NR:-32}"
GEOMETRY_R_IN_M="${GEOMETRY_R_IN_M:-}"
GEOMETRY_R_OUT_M="${GEOMETRY_R_OUT_M:-}"

# Optional study file (YAML) to override sweep lists and tags.
if [[ -n "${STUDY_FILE:-}" ]]; then
  if [[ -f "${STUDY_FILE}" ]]; then
    set +e
    study_exports="$(
      python - <<'PY'
import os
import shlex
try:
    from ruamel.yaml import YAML
except Exception:
    YAML = None

path = os.environ.get("STUDY_FILE")
if not path:
    raise SystemExit(0)
if YAML is None:
    raise SystemExit(1)
yaml = YAML(typ="safe")
data = yaml.load(open(path, "r", encoding="utf-8")) or {}

def _join_list(value):
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)

def emit(key, value):
    if value is None:
        return
    print(f"{key}={shlex.quote(_join_list(value))}")

emit("T_LIST_RAW", data.get("T_LIST_RAW", data.get("T_LIST")))
emit("EPS_LIST_RAW", data.get("EPS_LIST_RAW", data.get("EPS_LIST")))
emit("TAU_LIST_RAW", data.get("TAU_LIST_RAW", data.get("TAU_LIST")))
emit("SWEEP_TAG", data.get("SWEEP_TAG"))
emit("COOL_TO_K", data.get("COOL_TO_K"))
emit("COOL_MARGIN_YEARS", data.get("COOL_MARGIN_YEARS"))
emit("COOL_SEARCH_YEARS", data.get("COOL_SEARCH_YEARS"))
emit("COOL_MODE", data.get("COOL_MODE"))
emit("T_END_YEARS", data.get("T_END_YEARS"))
emit("T_END_SHORT_YEARS", data.get("T_END_SHORT_YEARS"))
PY
    )"
    study_rc=$?
    set -e
    if [[ ${study_rc} -eq 0 && -n "${study_exports}" ]]; then
      eval "${study_exports}"
      echo "[info] loaded study overrides from ${STUDY_FILE}"
    else
      echo "[warn] failed to parse STUDY_FILE=${STUDY_FILE}"
    fi
  else
    echo "[warn] STUDY_FILE not found: ${STUDY_FILE}"
  fi
fi

# Parameter grids (run hotter cases first). Override via env:
#   T_LIST_RAW="4000 3000", EPS_LIST_RAW="1.0", TAU_LIST_RAW="1.0 0.5"
T_LIST_RAW="${T_LIST_RAW:-5000 4000 3000}"
EPS_LIST_RAW="${EPS_LIST_RAW:-1.0 0.5 0.1}"
TAU_LIST_RAW="${TAU_LIST_RAW:-1.0 0.5 0.1}"
SEED_OVERRIDE=""
if [[ "${RUN_ONE_MODE}" == "1" || -n "${RUN_ONE_T:-}" || -n "${RUN_ONE_EPS:-}" || -n "${RUN_ONE_TAU:-}" ]]; then
  if [[ -z "${RUN_ONE_T:-}" || -z "${RUN_ONE_EPS:-}" || -z "${RUN_ONE_TAU:-}" ]]; then
    echo "[error] RUN_ONE_T/RUN_ONE_EPS/RUN_ONE_TAU are required for run-one mode" >&2
    exit 1
  fi
  T_LIST_RAW="${RUN_ONE_T}"
  EPS_LIST_RAW="${RUN_ONE_EPS}"
  TAU_LIST_RAW="${RUN_ONE_TAU}"
  if [[ -z "${SWEEP_TAG:-}" ]]; then
    SWEEP_TAG="run_one"
  fi
  if [[ -n "${RUN_ONE_SEED:-}" ]]; then
    SEED_OVERRIDE="${RUN_ONE_SEED}"
  fi
  echo "[info] run-one mode: T=${RUN_ONE_T} eps=${RUN_ONE_EPS} tau=${RUN_ONE_TAU} seed=${RUN_ONE_SEED:-auto}"
fi
BATCH_DIR="${BATCH_ROOT}/${SWEEP_TAG}/${RUN_TS}__${GIT_SHA}__seed${BATCH_SEED}"
mkdir -p "${BATCH_DIR}"
read -r -a T_LIST <<<"${T_LIST_RAW}"
read -r -a EPS_LIST <<<"${EPS_LIST_RAW}"
read -r -a TAU_LIST <<<"${TAU_LIST_RAW}"
T_END_YEARS="${T_END_YEARS:-2.0}"              # fixed integration horizon when COOL_TO_K is unset [yr]
# 短縮テスト用に T_END_SHORT_YEARS=0.001 を指定すると強制上書き
if [[ -n "${T_END_SHORT_YEARS:-}" ]]; then
  T_END_YEARS="${T_END_SHORT_YEARS}"
  echo "[info] short-run override: T_END_YEARS=${T_END_YEARS} yr"
fi

# Fast blow-out substeps (surface_ode path). 0=off, 1=on.
SUBSTEP_FAST_BLOWOUT="${SUBSTEP_FAST_BLOWOUT:-0}"
SUBSTEP_MAX_RATIO="${SUBSTEP_MAX_RATIO:-}"

# Cooling stop condition (dynamic horizon based on Mars cooling time)
COOL_TO_K="${COOL_TO_K-2000}"                  # stop when Mars T_M reaches this [K]; default=2000 K (set empty/none to disable)
if [[ "${COOL_TO_K}" == "none" ]]; then
  COOL_TO_K=""
fi
T_END_YEARS="${T_END_YEARS:-2.0}"              # fixed integration horizon when COOL_TO_K is unset [yr]
COOL_MARGIN_YEARS="${COOL_MARGIN_YEARS:-0}"    # padding after reaching COOL_TO_K
COOL_SEARCH_YEARS="${COOL_SEARCH_YEARS:-}"     # optional search cap (years)
# Cooling driver mode: slab (T^-3 analytic slab) or hyodo (linear cooling)
COOL_MODE="${COOL_MODE:-slab}"

# Phase temperature input (Mars surface vs particle equilibrium)
PHASE_TEMP_INPUT="${PHASE_TEMP_INPUT:-particle}"  # mars_surface|particle
PHASE_QABS_MEAN="${PHASE_QABS_MEAN:-0.4}"
PHASE_TAU_FIELD="${PHASE_TAU_FIELD:-los}"         # vertical|los

# Evaluation toggle (0=skip, 1=run evaluate_tau_supply)
EVAL="${EVAL:-1}"
# Plot toggle (0=skip quick-look plots)
PLOT_ENABLE="${PLOT_ENABLE:-1}"
HOOKS_ENABLE="${HOOKS_ENABLE:-}"
HOOKS_STRICT="${HOOKS_STRICT:-0}"

OVERRIDE_BUILDER="scripts/runsets/common/build_overrides.py"
OVERRIDE_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/marsdisk_overrides_XXXXXX")"
trap 'rm -rf "${OVERRIDE_TMP_DIR}"' EXIT
BASE_OVERRIDES_FILE="${OVERRIDE_TMP_DIR}/base_overrides.txt"
CASE_OVERRIDES_FILE="${OVERRIDE_TMP_DIR}/case_overrides.txt"
MERGED_OVERRIDES_FILE="${OVERRIDE_TMP_DIR}/merged_overrides.txt"
EXTRA_OVERRIDE_FILE_ARGS=()
if [[ -n "${EXTRA_OVERRIDES_FILE:-}" ]]; then
  if [[ -f "${EXTRA_OVERRIDES_FILE}" ]]; then
    EXTRA_OVERRIDE_FILE_ARGS=(--file "${EXTRA_OVERRIDES_FILE}")
  else
    echo "[warn] EXTRA_OVERRIDES_FILE not found: ${EXTRA_OVERRIDES_FILE}"
  fi
fi

append_override() {
  local file="$1"
  local key="$2"
  local value="$3"
  printf '%s=%s\n' "${key}" "${value}" >> "${file}"
}

# Supply/shielding defaults (overridable via env).
# Default is optical_depth + mu_orbit10pct; legacy knobs are opt-in only.
SUPPLY_HEADROOM_POLICY="${SUPPLY_HEADROOM_POLICY:-}"
SUPPLY_MODE="${SUPPLY_MODE:-const}"
# External supply scaling (mu_orbit10pct=1.0 injects orbit_fraction_at_mu1 of Sigma_surf0 per orbit).
SUPPLY_MU_ORBIT10PCT="${SUPPLY_MU_ORBIT10PCT:-1.0}"
SUPPLY_MU_REFERENCE_TAU="${SUPPLY_MU_REFERENCE_TAU:-1.0}"
SUPPLY_ORBIT_FRACTION="${SUPPLY_ORBIT_FRACTION:-0.10}"
# optical_depth の Sigma_surf0 を使うため、初期質量は形状用の最小限に抑える。
INIT_MASS_TOTAL="${INIT_MASS_TOTAL:-1.0e-7}"
SHIELDING_MODE="${SHIELDING_MODE:-off}"
SHIELDING_SIGMA="${SHIELDING_SIGMA:-auto}"
SHIELDING_AUTO_MAX_MARGIN="${SHIELDING_AUTO_MAX_MARGIN:-0.05}"
OPTICAL_TAU0_TARGET="${OPTICAL_TAU0_TARGET:-1.0}"
OPTICAL_TAU_STOP="${OPTICAL_TAU_STOP:-2.302585092994046}"
OPTICAL_TAU_STOP_TOL="${OPTICAL_TAU_STOP_TOL:-1.0e-6}"
STOP_ON_BLOWOUT_BELOW_SMIN="${STOP_ON_BLOWOUT_BELOW_SMIN:-true}"

# Supply reservoir / feedback / temperature coupling (off by default)
SUPPLY_RESERVOIR_M="${SUPPLY_RESERVOIR_M:-}"                 # Mars masses; empty=disabled
SUPPLY_RESERVOIR_MODE="${SUPPLY_RESERVOIR_MODE:-hard_stop}"  # hard_stop|taper
SUPPLY_RESERVOIR_TAPER="${SUPPLY_RESERVOIR_TAPER:-0.05}"     # used when taper

SUPPLY_FEEDBACK_ENABLED="${SUPPLY_FEEDBACK_ENABLED:-0}"
SUPPLY_FEEDBACK_TARGET="${SUPPLY_FEEDBACK_TARGET:-0.9}"
SUPPLY_FEEDBACK_GAIN="${SUPPLY_FEEDBACK_GAIN:-1.2}"
SUPPLY_FEEDBACK_RESPONSE_YR="${SUPPLY_FEEDBACK_RESPONSE_YR:-0.4}"
SUPPLY_FEEDBACK_MIN_SCALE="${SUPPLY_FEEDBACK_MIN_SCALE:-1.0e-6}"
SUPPLY_FEEDBACK_MAX_SCALE="${SUPPLY_FEEDBACK_MAX_SCALE:-10.0}"
SUPPLY_FEEDBACK_TAU_FIELD="${SUPPLY_FEEDBACK_TAU_FIELD:-tau_los}" # tau_los only
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
# Optional deep_mixing buffer (non-default); enable via env.
SUPPLY_TRANSPORT_MODE="${SUPPLY_TRANSPORT_MODE:-direct}"        # direct|deep_mixing
SUPPLY_TRANSPORT_TMIX_ORBITS="${SUPPLY_TRANSPORT_TMIX_ORBITS:-}" # preferred knob when deep_mixing
SUPPLY_TRANSPORT_HEADROOM="${SUPPLY_TRANSPORT_HEADROOM:-hard}"  # hard|soft
SUPPLY_VEL_MODE="${SUPPLY_VEL_MODE:-inherit}"                   # inherit|fixed_ei|factor
SUPPLY_VEL_E="${SUPPLY_VEL_E:-0.05}"
SUPPLY_VEL_I="${SUPPLY_VEL_I:-0.025}"
SUPPLY_VEL_FACTOR="${SUPPLY_VEL_FACTOR:-}"
SUPPLY_VEL_BLEND="${SUPPLY_VEL_BLEND:-rms}"                     # rms|linear
SUPPLY_VEL_WEIGHT="${SUPPLY_VEL_WEIGHT:-delta_sigma}"           # delta_sigma|sigma_ratio

echo "[config] supply multipliers: temp_enabled=${SUPPLY_TEMP_ENABLED} (mode=${SUPPLY_TEMP_MODE}) feedback_enabled=${SUPPLY_FEEDBACK_ENABLED} reservoir=${SUPPLY_RESERVOIR_M:-off}"
echo "[config] shielding: mode=${SHIELDING_MODE} fixed_tau1_sigma=${SHIELDING_SIGMA} auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN}"
echo "[config] injection: mode=${SUPPLY_INJECTION_MODE} q=${SUPPLY_INJECTION_Q} s_inj_min=${SUPPLY_INJECTION_SMIN:-none} s_inj_max=${SUPPLY_INJECTION_SMAX:-none}"
echo "[config] transport: mode=${SUPPLY_TRANSPORT_MODE} t_mix=${SUPPLY_TRANSPORT_TMIX_ORBITS:-${SUPPLY_DEEP_TMIX_ORBITS:-disabled}} headroom_gate=${SUPPLY_TRANSPORT_HEADROOM} velocity=${SUPPLY_VEL_MODE}"
echo "[config] external supply: mu_orbit10pct=${SUPPLY_MU_ORBIT10PCT} mu_reference_tau=${SUPPLY_MU_REFERENCE_TAU} orbit_fraction_at_mu1=${SUPPLY_ORBIT_FRACTION} (epsilon_mix swept per EPS_LIST)"
echo "[config] optical_depth: tau0_target_list=${TAU_LIST_RAW} tau_stop=${OPTICAL_TAU_STOP} tau_stop_tol=${OPTICAL_TAU_STOP_TOL}"
echo "[config] fast blowout substep: enabled=${SUBSTEP_FAST_BLOWOUT} substep_max_ratio=${SUBSTEP_MAX_RATIO:-default}"
echo "[config] phase temperature input: ${PHASE_TEMP_INPUT} (q_abs_mean=${PHASE_QABS_MEAN}, tau_field=${PHASE_TAU_FIELD})"
echo "[config] geometry: mode=${GEOMETRY_MODE} Nr=${GEOMETRY_NR} r_in_m=${GEOMETRY_R_IN_M:-disk.geometry} r_out_m=${GEOMETRY_R_OUT_M:-disk.geometry}"
if [[ -n "${COOL_TO_K}" ]]; then
  echo "[config] dynamic horizon: stop when Mars T_M <= ${COOL_TO_K} K (margin ${COOL_MARGIN_YEARS} yr, search_cap=${COOL_SEARCH_YEARS:-none})"
else
  echo "[config] fixed horizon: t_end_years=${T_END_YEARS} (temperature stop disabled)"
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
# Enable streaming by default for sweep; keep memory modest to avoid stalls.
stream_enable="true"
stream_mem="${STREAM_MEM_GB:-10}"
stream_step="${STREAM_STEP_INTERVAL:-1000}"
stream_merge="true"
if ((${#EXTRA_OVERRIDE_FILE_ARGS[@]})); then
  echo "[info] streaming: enable=${stream_enable} mem_limit_gb=${stream_mem} step_flush_interval=${stream_step} merge_at_end=${stream_merge} (EXTRA_OVERRIDES_FILE may override)"
else
  echo "[info] streaming: enable=${stream_enable} mem_limit_gb=${stream_mem} step_flush_interval=${stream_step} merge_at_end=${stream_merge}"
fi

# Checkpoint (segmented run) defaults
CHECKPOINT_ENABLE="${CHECKPOINT_ENABLE:-1}"
CHECKPOINT_INTERVAL_YEARS="${CHECKPOINT_INTERVAL_YEARS:-0.083}" # ~30 days
CHECKPOINT_KEEP="${CHECKPOINT_KEEP:-3}"
CHECKPOINT_FORMAT="${CHECKPOINT_FORMAT:-pickle}"
if [[ "${CHECKPOINT_ENABLE}" != "0" ]]; then
  echo "[info] checkpoint enabled: interval_years=${CHECKPOINT_INTERVAL_YEARS} keep_last_n=${CHECKPOINT_KEEP} format=${CHECKPOINT_FORMAT}"
fi

: > "${BASE_OVERRIDES_FILE}"

# Core overrides shared by all cases.
append_override "${BASE_OVERRIDES_FILE}" "numerics.dt_init" "20"
append_override "${BASE_OVERRIDES_FILE}" "numerics.stop_on_blowout_below_smin" "${STOP_ON_BLOWOUT_BELOW_SMIN}"
append_override "${BASE_OVERRIDES_FILE}" "phase.enabled" "true"
append_override "${BASE_OVERRIDES_FILE}" "phase.temperature_input" "${PHASE_TEMP_INPUT}"
append_override "${BASE_OVERRIDES_FILE}" "phase.q_abs_mean" "${PHASE_QABS_MEAN}"
append_override "${BASE_OVERRIDES_FILE}" "phase.tau_field" "${PHASE_TAU_FIELD}"
append_override "${BASE_OVERRIDES_FILE}" "qstar.coeff_units" "${QSTAR_UNITS}"
append_override "${BASE_OVERRIDES_FILE}" "radiation.qpr_table_path" "marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv"
append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.enabled" "true"
append_override "${BASE_OVERRIDES_FILE}" "initial.mass_total" "${INIT_MASS_TOTAL}"
append_override "${BASE_OVERRIDES_FILE}" "supply.enabled" "true"
append_override "${BASE_OVERRIDES_FILE}" "supply.mode" "${SUPPLY_MODE}"
append_override "${BASE_OVERRIDES_FILE}" "supply.const.mu_orbit10pct" "${SUPPLY_MU_ORBIT10PCT}"
append_override "${BASE_OVERRIDES_FILE}" "supply.const.mu_reference_tau" "${SUPPLY_MU_REFERENCE_TAU}"
append_override "${BASE_OVERRIDES_FILE}" "supply.const.orbit_fraction_at_mu1" "${SUPPLY_ORBIT_FRACTION}"
append_override "${BASE_OVERRIDES_FILE}" "optical_depth.tau_stop" "${OPTICAL_TAU_STOP}"
append_override "${BASE_OVERRIDES_FILE}" "optical_depth.tau_stop_tol" "${OPTICAL_TAU_STOP_TOL}"
append_override "${BASE_OVERRIDES_FILE}" "inner_disk_mass" "null"

if [[ "${GEOMETRY_MODE}" == "1D" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "geometry.mode" "1D"
  append_override "${BASE_OVERRIDES_FILE}" "geometry.Nr" "${GEOMETRY_NR}"
  if [[ -n "${GEOMETRY_R_IN_M}" ]]; then
    append_override "${BASE_OVERRIDES_FILE}" "geometry.r_in" "${GEOMETRY_R_IN_M}"
  fi
  if [[ -n "${GEOMETRY_R_OUT_M}" ]]; then
    append_override "${BASE_OVERRIDES_FILE}" "geometry.r_out" "${GEOMETRY_R_OUT_M}"
  fi
fi

if [[ "${COOL_MODE}" == "hyodo" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.mode" "hyodo"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.hyodo.d_layer_m" "1.0e5"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.hyodo.rho" "3000"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.hyodo.cp" "1000"
else
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.mode" "table"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.table.time_unit" "day"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.table.column_time" "time_day"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.table.column_temperature" "T_K"
  append_override "${BASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.extrapolation" "hold"
fi

append_override "${BASE_OVERRIDES_FILE}" "io.streaming.enable" "${stream_enable}"
append_override "${BASE_OVERRIDES_FILE}" "io.streaming.memory_limit_gb" "${stream_mem}"
append_override "${BASE_OVERRIDES_FILE}" "io.streaming.step_flush_interval" "${stream_step}"
append_override "${BASE_OVERRIDES_FILE}" "io.streaming.merge_at_end" "${stream_merge}"

if [[ "${CHECKPOINT_ENABLE}" != "0" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "numerics.checkpoint.enabled" "true"
  append_override "${BASE_OVERRIDES_FILE}" "numerics.checkpoint.interval_years" "${CHECKPOINT_INTERVAL_YEARS}"
  append_override "${BASE_OVERRIDES_FILE}" "numerics.checkpoint.keep_last_n" "${CHECKPOINT_KEEP}"
  append_override "${BASE_OVERRIDES_FILE}" "numerics.checkpoint.format" "${CHECKPOINT_FORMAT}"
else
  append_override "${BASE_OVERRIDES_FILE}" "numerics.checkpoint.enabled" "false"
fi

# Supply/shielding defaults (overridable via env).
if [[ -n "${SUPPLY_RESERVOIR_M}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.reservoir.enabled" "true"
  append_override "${BASE_OVERRIDES_FILE}" "supply.reservoir.mass_total_Mmars" "${SUPPLY_RESERVOIR_M}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.reservoir.depletion_mode" "${SUPPLY_RESERVOIR_MODE}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.reservoir.taper_fraction" "${SUPPLY_RESERVOIR_TAPER}"
  echo "[info] supply reservoir: M=${SUPPLY_RESERVOIR_M} M_Mars mode=${SUPPLY_RESERVOIR_MODE} taper_fraction=${SUPPLY_RESERVOIR_TAPER}"
fi
if [[ "${SUPPLY_FEEDBACK_ENABLED}" != "0" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.enabled" "true"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.target_tau" "${SUPPLY_FEEDBACK_TARGET}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.gain" "${SUPPLY_FEEDBACK_GAIN}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.response_time_years" "${SUPPLY_FEEDBACK_RESPONSE_YR}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.min_scale" "${SUPPLY_FEEDBACK_MIN_SCALE}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.max_scale" "${SUPPLY_FEEDBACK_MAX_SCALE}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.tau_field" "${SUPPLY_FEEDBACK_TAU_FIELD}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.feedback.initial_scale" "${SUPPLY_FEEDBACK_INITIAL}"
  echo "[info] supply feedback enabled: target_tau=${SUPPLY_FEEDBACK_TARGET}, gain=${SUPPLY_FEEDBACK_GAIN}, tau_field=${SUPPLY_FEEDBACK_TAU_FIELD}"
fi
if [[ "${SUPPLY_TEMP_ENABLED}" != "0" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.enabled" "true"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.mode" "${SUPPLY_TEMP_MODE}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.reference_K" "${SUPPLY_TEMP_REF_K}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.exponent" "${SUPPLY_TEMP_EXP}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.scale_at_reference" "${SUPPLY_TEMP_SCALE_REF}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.floor" "${SUPPLY_TEMP_FLOOR}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.cap" "${SUPPLY_TEMP_CAP}"
  if [[ -n "${SUPPLY_TEMP_TABLE_PATH}" ]]; then
    append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.table.path" "${SUPPLY_TEMP_TABLE_PATH}"
    append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.table.value_kind" "${SUPPLY_TEMP_TABLE_VALUE_KIND}"
    append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.table.column_temperature" "${SUPPLY_TEMP_TABLE_COL_T}"
    append_override "${BASE_OVERRIDES_FILE}" "supply.temperature.table.column_value" "${SUPPLY_TEMP_TABLE_COL_VAL}"
  fi
  echo "[info] supply temperature coupling enabled: mode=${SUPPLY_TEMP_MODE}"
fi
append_override "${BASE_OVERRIDES_FILE}" "supply.injection.mode" "${SUPPLY_INJECTION_MODE}"
append_override "${BASE_OVERRIDES_FILE}" "supply.injection.q" "${SUPPLY_INJECTION_Q}"
if [[ -n "${SUPPLY_INJECTION_SMIN}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.injection.s_inj_min" "${SUPPLY_INJECTION_SMIN}"
fi
if [[ -n "${SUPPLY_INJECTION_SMAX}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.injection.s_inj_max" "${SUPPLY_INJECTION_SMAX}"
fi
if [[ -n "${SUPPLY_DEEP_TMIX_ORBITS}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.transport.t_mix_orbits" "${SUPPLY_DEEP_TMIX_ORBITS}"
  append_override "${BASE_OVERRIDES_FILE}" "supply.transport.mode" "deep_mixing"
  echo "[info] deep reservoir enabled (legacy alias): t_mix=${SUPPLY_DEEP_TMIX_ORBITS} orbits"
fi
if [[ -n "${SUPPLY_TRANSPORT_TMIX_ORBITS}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.transport.t_mix_orbits" "${SUPPLY_TRANSPORT_TMIX_ORBITS}"
fi
if [[ -n "${SUPPLY_TRANSPORT_MODE}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.transport.mode" "${SUPPLY_TRANSPORT_MODE}"
fi
if [[ -n "${SUPPLY_TRANSPORT_HEADROOM}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.transport.headroom_gate" "${SUPPLY_TRANSPORT_HEADROOM}"
fi
if [[ -n "${SUPPLY_HEADROOM_POLICY}" ]]; then
  if [[ "${SUPPLY_HEADROOM_POLICY}" == "none" || "${SUPPLY_HEADROOM_POLICY}" == "off" ]]; then
    echo "[warn] SUPPLY_HEADROOM_POLICY=${SUPPLY_HEADROOM_POLICY} ignored; use clip/spill or leave unset"
  else
    append_override "${BASE_OVERRIDES_FILE}" "supply.headroom_policy" "${SUPPLY_HEADROOM_POLICY}"
  fi
fi
append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.mode" "${SUPPLY_VEL_MODE}"
if [[ -n "${SUPPLY_VEL_E}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.e_inj" "${SUPPLY_VEL_E}"
fi
if [[ -n "${SUPPLY_VEL_I}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.i_inj" "${SUPPLY_VEL_I}"
fi
if [[ -n "${SUPPLY_VEL_FACTOR}" ]]; then
  append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.vrel_factor" "${SUPPLY_VEL_FACTOR}"
fi
append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.blend_mode" "${SUPPLY_VEL_BLEND}"
append_override "${BASE_OVERRIDES_FILE}" "supply.injection.velocity.weight_mode" "${SUPPLY_VEL_WEIGHT}"

if [[ "${SHIELDING_SIGMA}" == "auto_max" ]]; then
  echo "[warn] fixed_tau1_sigma=auto_max is debug-only; exclude from production figures"
fi

for T in "${T_LIST[@]}"; do
  T_TABLE="data/mars_temperature_T${T}p0K.csv"
  for EPS in "${EPS_LIST[@]}"; do
    EPS_TITLE="${EPS/0./0p}"
    EPS_TITLE="${EPS_TITLE/./p}"
    for TAU in "${TAU_LIST[@]}"; do
      TAU_TITLE="${TAU/0./0p}"
      TAU_TITLE="${TAU_TITLE/./p}"
      if [[ -n "${SEED_OVERRIDE}" ]]; then
        SEED="${SEED_OVERRIDE}"
      else
        SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
      fi
      TITLE="T${T}_eps${EPS_TITLE}_tau${TAU_TITLE}"
      OUTDIR="${BATCH_DIR}/${TITLE}"
      echo "[run] T=${T} eps=${EPS} tau=${TAU} -> ${OUTDIR} (batch=${BATCH_SEED}, seed=${SEED})"
      echo "[info] epsilon_mix=${EPS}; mu_orbit10pct=${SUPPLY_MU_ORBIT10PCT} orbit_fraction_at_mu1=${SUPPLY_ORBIT_FRACTION}"
      echo "[info] shielding: mode=${SHIELDING_MODE} fixed_tau1_sigma=${SHIELDING_SIGMA} auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN}"
      if [[ "${EPS}" == "0.1" ]]; then
        echo "[info] epsilon_mix=0.1 is a low-supply extreme case; expect weak blowout/sinks"
      fi
      : > "${CASE_OVERRIDES_FILE}"
      append_override "${CASE_OVERRIDES_FILE}" "io.outdir" "${OUTDIR}"
      append_override "${CASE_OVERRIDES_FILE}" "dynamics.rng_seed" "${SEED}"
      append_override "${CASE_OVERRIDES_FILE}" "radiation.TM_K" "${T}"
      append_override "${CASE_OVERRIDES_FILE}" "supply.mixing.epsilon_mix" "${EPS}"
      append_override "${CASE_OVERRIDES_FILE}" "optical_depth.tau0_target" "${TAU}"
      if [[ "${COOL_MODE}" != "hyodo" ]]; then
        append_override "${CASE_OVERRIDES_FILE}" "radiation.mars_temperature_driver.table.path" "${T_TABLE}"
      fi
      append_override "${CASE_OVERRIDES_FILE}" "shielding.mode" "${SHIELDING_MODE}"
      if [[ "${SHIELDING_MODE}" == "fixed_tau1" ]]; then
        append_override "${CASE_OVERRIDES_FILE}" "shielding.fixed_tau1_sigma" "${SHIELDING_SIGMA}"
        append_override "${CASE_OVERRIDES_FILE}" "shielding.auto_max_margin" "${SHIELDING_AUTO_MAX_MARGIN}"
      fi
      if [[ -n "${COOL_TO_K}" ]]; then
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_years" "null"
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_orbits" "null"
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_until_temperature_K" "${COOL_TO_K}"
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_temperature_margin_years" "${COOL_MARGIN_YEARS}"
        if [[ -n "${COOL_SEARCH_YEARS}" ]]; then
          append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_temperature_search_years" "${COOL_SEARCH_YEARS}"
        else
          append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_temperature_search_years" "null"
        fi
        append_override "${CASE_OVERRIDES_FILE}" "scope.analysis_years" "10"
      else
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_years" "${T_END_YEARS}"
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_orbits" "null"
        append_override "${CASE_OVERRIDES_FILE}" "numerics.t_end_until_temperature_K" "null"
        append_override "${CASE_OVERRIDES_FILE}" "scope.analysis_years" "${T_END_YEARS}"
      fi
      if [[ "${SUBSTEP_FAST_BLOWOUT}" != "0" ]]; then
        append_override "${CASE_OVERRIDES_FILE}" "io.substep_fast_blowout" "true"
        if [[ -n "${SUBSTEP_MAX_RATIO}" ]]; then
          append_override "${CASE_OVERRIDES_FILE}" "io.substep_max_ratio" "${SUBSTEP_MAX_RATIO}"
        fi
      fi

      # Override priority: base defaults < EXTRA_OVERRIDES_FILE < per-case overrides.
      # Avoid empty array expansion under `set -u` (bash 3.2 treats it as unbound).
      override_cmd=(python "${OVERRIDE_BUILDER}" --file "${BASE_OVERRIDES_FILE}")
      if ((${#EXTRA_OVERRIDE_FILE_ARGS[@]})); then
        override_cmd+=("${EXTRA_OVERRIDE_FILE_ARGS[@]}")
      fi
      override_cmd+=(--file "${CASE_OVERRIDES_FILE}")
      "${override_cmd[@]}" > "${MERGED_OVERRIDES_FILE}"

      cmd=(
        python -m marsdisk.run
        --config "${BASE_CONFIG}"
        --overrides-file "${MERGED_OVERRIDES_FILE}"
      )
      # 強制的に progress を有効化しつつ、ログは静かめに
      cmd+=(--progress --quiet)
      if [[ "${DRY_RUN}" == "1" ]]; then
        printf '[dry-run]'
        printf ' %q' "${cmd[@]}"
        echo
        continue
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
      summary_path="${final_dir}/summary.json"
      if [[ -f "${summary_path}" ]]; then
        SUMMARY_PATH="${summary_path}" python - <<'PY'
import json
import os

path = os.environ.get("SUMMARY_PATH", "")
try:
    with open(path, "r", encoding="utf-8") as handle:
        summary = json.load(handle)
except Exception as exc:
    print(f"[stop] summary read failed: {exc}")
else:
    stop_reason = summary.get("stop_reason") or summary.get("early_stop_reason") or "t_end_reached"
    cells_stopped = summary.get("cells_stopped")
    cells_total = summary.get("cells_total")
    extra = ""
    if cells_stopped is not None and cells_total is not None:
        extra = f" cells_stopped={cells_stopped}/{cells_total}"
    print(f"[stop] reason={stop_reason}{extra}")
PY
      else
        echo "[stop] summary.json not found; stop reason unavailable"
      fi

      if [[ -n "${HOOKS_ENABLE}" ]]; then
        IFS=',' read -r -a hook_list <<< "${HOOKS_ENABLE}"
        for hook in "${hook_list[@]}"; do
          hook="$(echo "${hook}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
          hook="$(echo "${hook}" | tr '[:upper:]' '[:lower:]')"
          [[ -z "${hook}" ]] && continue
          hook_rc=0
          case "${hook}" in
            preflight)
              set +e
              python scripts/runsets/common/hooks/preflight_streaming.py --run-dir "${final_dir}"
              hook_rc=$?
              set -e
              ;;
            plot)
              set +e
              python scripts/runsets/common/hooks/plot_sweep_run.py --run-dir "${final_dir}"
              hook_rc=$?
              set -e
              ;;
            eval)
              set +e
              python scripts/runsets/common/hooks/evaluate_tau_supply.py --run-dir "${final_dir}"
              hook_rc=$?
              set -e
              ;;
            archive)
              set +e
              python scripts/runsets/common/hooks/archive_run.py --run-dir "${final_dir}"
              hook_rc=$?
              set -e
              ;;
            *)
              echo "[warn] unknown hook: ${hook}"
              hook_rc=0
              ;;
          esac
          if [[ ${hook_rc} -ne 0 ]]; then
            echo "[warn] hook ${hook} failed (rc=${hook_rc}) for ${final_dir}"
            if [[ "${HOOKS_STRICT}" == "1" ]]; then
              exit ${hook_rc}
            fi
          fi
        done
      else
        # Generate quick-look plots into <final_dir>/plots
        if [[ "${PLOT_ENABLE}" != "0" ]]; then
      RUN_DIR="${final_dir}" python - <<'PY'
import os
import json
import math
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import pyarrow.parquet as pq
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


MAX_PLOT_ROWS = int(os.environ.get("PLOT_MAX_ROWS", "4000") or "4000")
PLOT_BATCH_SIZE = int(os.environ.get("PLOT_BATCH_SIZE", "4096") or "4096")


def load_downsampled_df(path: Path, columns, *, target_rows: int, batch_size: int):
    """Load a column-limited, downsampled DataFrame (0D or 1D aware)."""

    def _empty_df(cols):
        return pd.DataFrame({c: pd.Series(dtype=float) for c in cols})

    def _compute_cell_weight_map(group_df: pd.DataFrame) -> dict[int, float] | None:
        if "cell_index" not in group_df or "r_m" not in group_df:
            return None
        cells = (
            group_df[["cell_index", "r_m"]]
            .dropna()
            .drop_duplicates()
            .sort_values("cell_index")
        )
        if cells.empty:
            return None
        r_vals = cells["r_m"].to_numpy(dtype=float)
        if r_vals.size == 1:
            weights = np.array([1.0])
        else:
            edges = np.empty(r_vals.size + 1, dtype=float)
            edges[1:-1] = 0.5 * (r_vals[1:] + r_vals[:-1])
            edges[0] = r_vals[0] - (edges[1] - r_vals[0])
            edges[-1] = r_vals[-1] + (r_vals[-1] - edges[-2])
            edges = np.clip(edges, 0.0, None)
            areas = np.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
            if not np.all(np.isfinite(areas)) or np.sum(areas) <= 0.0:
                weights = np.full_like(r_vals, 1.0 / r_vals.size)
            else:
                weights = areas / np.sum(areas)
        return {
            int(cell): float(weight)
            for cell, weight in zip(cells["cell_index"].astype(int), weights)
        }

    def _weighted_mean(series: pd.Series, weights: np.ndarray | None) -> float:
        values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(values)
        if not mask.any():
            return float("nan")
        if weights is None or not np.any(np.isfinite(weights)):
            return float(np.nanmean(values))
        w = weights[mask]
        v = values[mask]
        if np.sum(w) <= 0.0:
            return float(np.nanmean(v))
        return float(np.sum(w * v) / np.sum(w))

    pf = pq.ParquetFile(path)
    schema_names = set(pf.schema.names)
    total_rows = pf.metadata.num_rows if pf.metadata is not None else 0
    is_1d = "cell_index" in schema_names
    alias_map: dict[str, str] = {}
    if "t_blow_s" in columns and "t_blow" in schema_names:
        alias_map["t_blow_s"] = "t_blow"
    if "t_coll" in columns and "t_coll_kernel_min" in schema_names:
        alias_map["t_coll"] = "t_coll_kernel_min"

    available_cols = [c for c in columns if c in schema_names]
    missing_cols = [c for c in columns if c not in schema_names and c not in alias_map]
    total_rows = pf.metadata.num_rows if pf.metadata is not None else 0
    if not available_cols or total_rows == 0:
        return _empty_df(columns), missing_cols, total_rows, 0.0

    if not is_1d:
        step = max(total_rows // target_rows, 1) if target_rows > 0 else 1
        frames = []
        row_offset = 0
        prod_sum = 0.0
        prod_count = 0

        for batch in pf.iter_batches(columns=available_cols, batch_size=batch_size, use_threads=True):
            pdf = batch.to_pandas()
            if "prod_subblow_area_rate" in pdf:
                series = pd.to_numeric(pdf["prod_subblow_area_rate"], errors="coerce")
                prod_sum += float(series.sum(skipna=True))
                prod_count += int(series.notna().sum())

            if step == 1:
                frames.append(pdf)
            else:
                idx = np.arange(len(pdf)) + row_offset
                mask = (idx % step) == 0
                if mask.any():
                    frames.append(pdf.loc[mask])
            row_offset += len(pdf)

        df = pd.concat(frames, ignore_index=True) if frames else _empty_df(available_cols)
        for col in missing_cols:
            df[col] = np.nan
        df = df.reindex(columns=columns)
        df.attrs["is_1d"] = False
        prod_mean = (prod_sum / prod_count) if prod_count else 0.0
        return df, missing_cols, total_rows, prod_mean

    required_cols = list(available_cols)
    for col in alias_map.values():
        if col not in required_cols and col in schema_names:
            required_cols.append(col)
    for extra in ("time", "cell_index", "r_m", "dt"):
        if extra in schema_names and extra not in required_cols:
            required_cols.append(extra)

    if not required_cols:
        return _empty_df(columns), missing_cols, total_rows, 0.0

    sum_cols = {
        "M_out_dot",
        "M_sink_dot",
        "M_loss_cum",
        "M_sink_cum",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "mass_total_bins",
        "mass_lost_sinks_step",
        "mass_lost_sublimation_step",
    }
    mean_cols = {
        "Sigma_surf",
        "sigma_surf",
        "sigma_deep",
        "Sigma_tau1",
        "sigma_tau1",
        "outflux_surface",
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
        "tau",
        "tau_los_mars",
        "dt_over_t_blow",
        "t_blow_s",
        "t_blow",
        "t_coll",
        "t_coll_kernel_min",
    }

    batch_iter = pf.iter_batches(columns=required_cols, batch_size=batch_size, use_threads=True)
    first_batch = next(batch_iter, None)
    if first_batch is None:
        return _empty_df(columns), missing_cols, total_rows, 0.0
    first_pdf = first_batch.to_pandas()
    n_cells = int(first_pdf["cell_index"].nunique()) if "cell_index" in first_pdf else 0
    total_steps = total_rows // max(n_cells, 1) if total_rows else 0
    step = max(total_steps // target_rows, 1) if target_rows > 0 and total_steps > 0 else 1

    aggregated_rows = []
    current_time = None
    buffer: list[pd.DataFrame] = []
    time_index = 0
    prod_sum = 0.0
    prod_count = 0
    weight_map: dict[int, float] | None = None

    def flush_group(group_df: pd.DataFrame) -> None:
        nonlocal time_index, prod_sum, prod_count, weight_map
        if group_df.empty:
            return
        keep = (step == 1) or (time_index % step == 0)
        time_index += 1
        if not keep:
            return
        if weight_map is None:
            weight_map = _compute_cell_weight_map(group_df)
        weights = None
        if weight_map is not None and "cell_index" in group_df:
            weights = (
                group_df["cell_index"]
                .map(weight_map)
                .fillna(0.0)
                .to_numpy(dtype=float)
            )

        row: dict[str, float] = {}
        for col in columns:
            if col == "time":
                row[col] = float(group_df["time"].iloc[0])
                continue
            if col == "dt" and "dt" in group_df:
                row[col] = float(group_df["dt"].iloc[0])
                continue
            if col in sum_cols and col in group_df:
                row[col] = float(pd.to_numeric(group_df[col], errors="coerce").sum(skipna=True))
                continue
            if col in mean_cols and col in group_df:
                row[col] = _weighted_mean(group_df[col], weights)
                continue
            if col in group_df:
                series = pd.to_numeric(group_df[col], errors="coerce").dropna()
                row[col] = float(series.iloc[0]) if not series.empty else float("nan")
            else:
                row[col] = float("nan")

        for target, source in alias_map.items():
            if target in columns and (target not in row or not math.isfinite(row[target])):
                if source in group_df:
                    row[target] = _weighted_mean(group_df[source], weights)

        if "prod_subblow_area_rate" in row and math.isfinite(row["prod_subblow_area_rate"]):
            prod_sum += float(row["prod_subblow_area_rate"])
            prod_count += 1
        aggregated_rows.append(row)

    def process_pdf(pdf: pd.DataFrame) -> None:
        nonlocal current_time, buffer
        if pdf.empty:
            return
        for time_val, group in pdf.groupby("time", sort=False):
            if current_time is None:
                current_time = time_val
            if time_val != current_time:
                flush_group(pd.concat(buffer, ignore_index=True))
                buffer = []
                current_time = time_val
            buffer.append(group)

    process_pdf(first_pdf)
    for batch in batch_iter:
        process_pdf(batch.to_pandas())
    if buffer:
        flush_group(pd.concat(buffer, ignore_index=True))

    df = pd.DataFrame(aggregated_rows) if aggregated_rows else _empty_df(columns)
    for col in columns:
        if col not in df:
            df[col] = np.nan
    df = df.reindex(columns=columns)
    df.attrs["is_1d"] = True
    prod_mean = (prod_sum / prod_count) if prod_count else 0.0
    return df, missing_cols, total_rows, prod_mean


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
    "M_sink_cum",
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

df, missing_cols, total_rows, prod_mean = load_downsampled_df(
    series_path,
    series_cols,
    target_rows=MAX_PLOT_ROWS,
    batch_size=PLOT_BATCH_SIZE,
)
if missing_cols:
    print(f"[warn] missing columns in run.parquet: {missing_cols}")
if total_rows > MAX_PLOT_ROWS:
    print(f"[info] downsampled series from {total_rows} rows to {len(df)} rows for plotting")
df["time_days"] = df["time"] / 86400.0
t_coll_series = df["t_coll"] if "t_coll" in df else pd.Series(np.nan, index=df.index)
t_blow_series = df["t_blow_s"] if "t_blow_s" in df else pd.Series(np.nan, index=df.index)
df["t_coll_years"] = (t_coll_series.clip(lower=1e-6)) / 31557600.0
df["t_blow_hours"] = (t_blow_series.clip(lower=1e-12)) / 3600.0
tau_los_series = df["tau_los_mars"].fillna(df["tau"])


def _finite_array(series_list):
    """Flatten finite values from multiple series."""
    if not series_list:
        return np.array([])
    arrays = []
    for s in series_list:
        if s is None:
            continue
        try:
            arr = np.asarray(s.dropna().to_numpy(), dtype=float)
        except Exception:
            continue
        arrays.append(arr)
    if not arrays:
        return np.array([])
    arr = np.concatenate(arrays)
    arr = arr[np.isfinite(arr)]
    return arr


def _auto_scale(ax, series_list, *, log_ratio=20.0, linthresh_min=1e-12, pad_frac=0.08):
    """Choose lin/log/symlog and set ylim with padding based on data spread."""

    arr = _finite_array(series_list)
    if arr.size == 0:
        return
    vmin, vmax = float(arr.min()), float(arr.max())
    if vmax == vmin:
        span = 1.0 if vmax == 0.0 else abs(vmax)
        pad = span * pad_frac
        ax.set_ylim(vmin - pad, vmax + pad)
        return

    # Decide scale
    if vmin < 0.0 < vmax:
        finite_abs = np.abs(arr[arr != 0.0])
        linthresh = max(linthresh_min, np.percentile(finite_abs, 20) if finite_abs.size else linthresh_min)
        ax.set_yscale("symlog", linthresh=linthresh)
    elif vmin > 0.0:
        ratio = vmax / max(vmin, linthresh_min)
        if ratio >= log_ratio:
            ax.set_yscale("log")

    # Set limits with padding to avoid flat lines
    span = vmax - vmin
    pad = max(span * pad_frac, linthresh_min)
    ymin = vmin - pad
    ymax = vmax + pad
    # Avoid zero/negative lower bound on log-only axes
    if ax.get_yscale() == "log":
        positive = arr[arr > 0.0]
        floor = linthresh_min
        if positive.size:
            floor = max(linthresh_min, float(positive.min()) * (1.0 - pad_frac))
        ymin = max(ymin, floor)
    ax.set_ylim(ymin, ymax)


fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
headroom_ratio = (df["Sigma_tau1"] - df["Sigma_surf"]).clip(lower=0) / df["Sigma_tau1"].clip(lower=1e-20)

axes[0].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", lw=1.2, color="tab:green")
axes[0].plot(df["time_days"], df["Sigma_tau1"], label="Sigma_tau1", lw=1.0, color="tab:orange", alpha=0.8)
axes[0].plot(df["time_days"], headroom_ratio, label="headroom_ratio", lw=0.9, color="tab:red", linestyle="--", alpha=0.7)
axes[0].set_ylabel("kg m^-2")
axes[0].legend(loc="upper right")
axes[0].set_title("Surface density and τ=1 cap")
_auto_scale(axes[0], [df["Sigma_surf"], df["Sigma_tau1"], headroom_ratio], log_ratio=10.0, linthresh_min=1e-12)

axes[1].plot(df["time_days"], df["M_loss_cum"], label="M_loss_cum (total)", lw=1.2, color="tab:blue")
axes[1].plot(df["time_days"], df["mass_lost_by_blowout"], label="mass_lost_by_blowout", lw=1.0, color="tab:red", alpha=0.8)
axes[1].plot(df["time_days"], df["M_sink_cum"], label="M_sink_cum", lw=1.0, color="tab:purple", alpha=0.8)
axes[1].set_ylabel("M_Mars")
axes[1].legend(loc="upper left")
axes[1].set_title("Cumulative losses")
_auto_scale(axes[1], [df["M_loss_cum"], df["mass_lost_by_blowout"], df["M_sink_cum"]], log_ratio=10.0)

axes[2].plot(df["time_days"], df["s_min"], label="s_min_effective", lw=1.0, color="tab:blue")
axes[2].plot(df["time_days"], df["a_blow"], label="a_blow", lw=1.0, color="tab:orange", alpha=0.8)
axes[2].set_ylabel("m")
axes[2].set_xlabel("days")
axes[2].legend(loc="upper right")
axes[2].set_title("Minimum size vs blow-out size")
_auto_scale(axes[2], [df["s_min"], df["a_blow"]], log_ratio=10.0, linthresh_min=1e-18)

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
_auto_scale(
    ax2[0],
    [
        df["supply_rate_nominal"],
        df["supply_rate_scaled"],
        df["supply_rate_applied"],
        df["prod_rate_applied_to_surf"],
        df["prod_subblow_area_rate"],
    ],
    log_ratio=10.0,
    linthresh_min=1e-14,
)

ax2[1].plot(df["time_days"], df["prod_rate_diverted_to_deep"], label="diverted→deep", color="tab:brown", alpha=0.8)
ax2[1].plot(df["time_days"], df["deep_to_surf_flux"], label="deep→surf flux", color="tab:olive", alpha=0.9)
ax2[1].plot(df["time_days"], df["sigma_deep"], label="sigma_deep", color="tab:gray", alpha=0.7)
ax2[1].set_ylabel("kg m^-2 / s")
ax2[1].legend(loc="upper right")
ax2[1].set_title("Deep reservoir routing")
_auto_scale(ax2[1], [df["prod_rate_diverted_to_deep"], df["deep_to_surf_flux"], df["sigma_deep"]], log_ratio=10.0, linthresh_min=1e-14)

ax2[2].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
ax2[2].plot(df["time_days"], df["Sigma_tau1"], label="Sigma_tau1", color="tab:orange", alpha=0.8)
ax2[2].plot(df["time_days"], df["supply_headroom"], label="headroom (legacy)", color="tab:brown", alpha=0.7)
ax2[2].plot(df["time_days"], df["headroom"], label="headroom (applied)", color="tab:blue", alpha=0.7, linestyle="--")
ax2[2].set_ylabel("kg m^-2")
ax2[2].legend(loc="upper right")
ax2[2].set_title("Surface density vs tau=1 cap")
_auto_scale(ax2[2], [df["Sigma_surf"], df["Sigma_tau1"], df["headroom"], df["supply_headroom"]], log_ratio=10.0, linthresh_min=1e-12)

ax2[3].plot(df["time_days"], df["outflux_surface"], label="outflux_surface (M_Mars/s)", color="tab:red", alpha=0.9)
ax2[3].plot(df["time_days"], tau_los_series, label="tau_los_mars", color="tab:purple", alpha=0.7)
ax2[3].axhline(1.0, color="gray", linestyle=":", alpha=0.6, label="τ=1 reference")
ax2[3].set_ylabel("outflux / tau")
ax2[3].set_xlabel("days")
ax2[3].legend(loc="upper right")
ax2[3].set_title("Surface outflux and optical depth")
_auto_scale(ax2[3], [df["outflux_surface"], tau_los_series], log_ratio=10.0, linthresh_min=1e-20)

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

# Optical depth quick-look (LOS tau)
def _plot_if_available(ax, x, y, label, **kwargs):
    if y.isna().all():
        return
    ax.plot(x, y, label=label, **kwargs)

fig3, ax3 = plt.subplots(1, 1, figsize=(10, 4))
_plot_if_available(ax3, df["time_days"], tau_los_series, label="tau_los_mars", color="tab:red", alpha=0.8)
headroom_ratio = (df["Sigma_tau1"] - df["Sigma_surf"]).clip(lower=0) / df["Sigma_tau1"].clip(lower=1e-20)
ax3.plot(df["time_days"], headroom_ratio, label="headroom ratio", color="tab:orange", alpha=0.6, linestyle=":")
ax3.axhline(1.0, color="gray", linestyle=":", alpha=0.5, label="τ=1 reference")
ax3.set_ylabel("optical depth")
ax3.set_xlabel("days")
ax3.set_title("Optical depth evolution")
ax3.legend(loc="upper right")
_auto_scale(ax3, [tau_los_series, headroom_ratio], log_ratio=10.0, linthresh_min=1e-12)
fig3.tight_layout()
fig3.savefig(plots_dir / "optical_depth.png", dpi=180)
plt.close(fig3)
print(f"[plot] saved plots to {plots_dir}")
PY
        fi
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
      fi
    done
  done
done

echo "[done] Sweep completed (batch=${BATCH_SEED}, dir=${BATCH_DIR})."
