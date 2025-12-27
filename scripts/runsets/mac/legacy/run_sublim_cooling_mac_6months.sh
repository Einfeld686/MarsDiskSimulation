#!/usr/bin/env bash
# Mars disk sublimation + smol + phase runner (macOS/Linux shell).
# - Sets up .venv, installs requirements, then runs with radiative cooling table/autogen enabled.
# - 6か月ラン向けに t_end_years を 0.5 に設定し、ストリーミング閾値を 20 GB に設定。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "${REPO_ROOT}"

OUTDIR="out/run_sublim_smol_phase_cooling_6months"
TMK="4000.0"
TEMP_TABLE="data/mars_temperature_T4000p0K.csv"
CONFIG="configs/mars_temperature_driver_table.yml"
VENV_DIR=".venv"
REQ_FILE="requirements.txt"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo "[setup] Creating virtual environment in \"${VENV_DIR}\"..."
  python -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

if [ -f "${REQ_FILE}" ]; then
  echo "[setup] Installing/upgrading dependencies from ${REQ_FILE} ..."
  python -m pip install --upgrade pip
  pip install -r "${REQ_FILE}"
else
  echo "[warn] ${REQ_FILE} not found; skipping dependency install."
fi

python -m marsdisk.run \
  --config "${CONFIG}" \
  --quiet \
  --progress \
  --override io.streaming.enable=true \
  --override io.streaming.memory_limit_gb=20.0 \
  --override io.streaming.step_flush_interval=10000 \
  --override io.streaming.compression=snappy \
  --override io.streaming.merge_at_end=true \
  --override numerics.dt_init=2.0 \
  --override numerics.safety=0.05 \
  --override numerics.t_end_years=0.5 \
  --override io.outdir="${OUTDIR}" \
  --override radiation.source=mars \
  --override radiation.TM_K="${TMK}" \
  --override radiation.mars_temperature_driver.enabled=true \
  --override radiation.mars_temperature_driver.mode=table \
  --override radiation.mars_temperature_driver.table.path="${TEMP_TABLE}" \
  --override radiation.mars_temperature_driver.table.time_unit=day \
  --override radiation.mars_temperature_driver.table.column_time=time_day \
  --override radiation.mars_temperature_driver.table.column_temperature=T_K \
  --override radiation.mars_temperature_driver.autogenerate.enabled=true \
  --override radiation.mars_temperature_driver.autogenerate.output_dir=data \
  --override radiation.mars_temperature_driver.autogenerate.dt_hours=1.0 \
  --override radiation.mars_temperature_driver.autogenerate.min_years=0.75 \
  --override radiation.mars_temperature_driver.autogenerate.time_margin_years=0.1 \
  --override radiation.mars_temperature_driver.autogenerate.time_unit=day \
  --override radiation.mars_temperature_driver.autogenerate.column_time=time_day \
  --override radiation.mars_temperature_driver.autogenerate.column_temperature=T_K \
  --override sinks.sub_params.mode=hkl \
  --override sinks.sub_params.alpha_evap=0.007 \
  --override sinks.sub_params.mu=0.0440849 \
  --override sinks.sub_params.A=13.613 \
  --override sinks.sub_params.B=17850.0

echo "[done] Run finished. Output: ${OUTDIR}"
