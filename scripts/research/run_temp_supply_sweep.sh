#!/usr/bin/env bash
# Run the 6 pre-made temp supply configs (T={2000,4000,6000} x epsilon_mix={1.0,0.1})
# on macOS/Linux. Sets an initial time step of 20 s via CLI override.

set -euo pipefail

VENV_DIR=".venv"
REQ_FILE="requirements.txt"

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

for cfg in "${CONFIGS[@]}"; do
  echo "[run] ${cfg}"
  python -m marsdisk.run --config "${cfg}" --quiet --progress --override numerics.dt_init=20
done

echo "[done] All 6 runs completed."
