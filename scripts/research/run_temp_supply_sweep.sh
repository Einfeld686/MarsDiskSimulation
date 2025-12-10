#!/usr/bin/env bash
# Run the 6 pre-made temp supply configs (T={2000,4000,6000} x epsilon_mix={1.0,0.1})
# on macOS/Linux. Sets an initial time step of 20 s via CLI override and writes
# each run to a unique out/<timestamp>_<title>__<sha>__seed<n>/ directory so it
# does not clobber previous results.

set -euo pipefail

VENV_DIR=".venv"
REQ_FILE="requirements.txt"
RUN_TS="$(date +%Y%m%d-%H%M%S)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
RAW_BASE="out/temp_supply_grid"
FINAL_BASE="out"

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

CONFIG_DIR="configs/sweep_temp_supply"
CONFIGS=(
  "${CONFIG_DIR}/temp_supply_T2000_eps1.yml"
  "${CONFIG_DIR}/temp_supply_T2000_eps0p1.yml"
  "${CONFIG_DIR}/temp_supply_T4000_eps1.yml"
  "${CONFIG_DIR}/temp_supply_T4000_eps0p1.yml"
  "${CONFIG_DIR}/temp_supply_T6000_eps1.yml"
  "${CONFIG_DIR}/temp_supply_T6000_eps0p1.yml"
)

# Progress bar: default ON when stdout is a TTY; OFF otherwise to avoid CR->LF spam.
PROGRESS_FLAG=()
if [[ -t 1 ]]; then
  # TTY: enable unless explicitly disabled
  if [[ "${ENABLE_PROGRESS:-1}" != "0" ]]; then
    PROGRESS_FLAG=(--progress)
  fi
else
  # Non-TTY: disable to prevent each refresh printing a new line
  if [[ "${ENABLE_PROGRESS:-0}" == "1" ]]; then
    echo "[warn] stdout is not a TTY; progress bar disabled to avoid newline spam"
  fi
  PROGRESS_FLAG=()
fi

for cfg in "${CONFIGS[@]}"; do
  SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
  title="$(basename "${cfg%.yml}")"
  outdir="${RAW_BASE}/${RUN_TS}_${title}__${GIT_SHA}__seed${SEED}"
  echo "[run] ${cfg} -> ${outdir} (seed=${SEED})"
  python -m marsdisk.run \
    --config "${cfg}" \
    --quiet \
    "${PROGRESS_FLAG[@]}" \
    --override numerics.dt_init=20 \
    --override "io.outdir=${outdir}" \
    --override "dynamics.rng_seed=${SEED}"

  # Copy a minimal set of products to a stable final directory under out/.
  final_dir="${FINAL_BASE}/${RUN_TS}_${title}__${GIT_SHA}__seed${SEED}"
  mkdir -p "${final_dir}/series" "${final_dir}/checks"
  for f in summary.json run_config.json; do
    src="${outdir}/${f}"
    if [[ -f "${src}" ]]; then
      cp "${src}" "${final_dir}/"
    else
      echo "[warn] missing ${src}, skip copy"
    fi
  done
  if [[ -f "${outdir}/series/run.parquet" ]]; then
    cp "${outdir}/series/run.parquet" "${final_dir}/series/"
  else
    echo "[warn] missing ${outdir}/series/run.parquet, skip copy"
  fi
  if [[ -f "${outdir}/checks/mass_budget.csv" ]]; then
    cp "${outdir}/checks/mass_budget.csv" "${final_dir}/checks/"
  else
    echo "[warn] missing ${outdir}/checks/mass_budget.csv, skip copy"
  fi
done

echo "[done] All 6 runs completed."
