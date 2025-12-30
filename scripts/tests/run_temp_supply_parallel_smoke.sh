#!/usr/bin/env bash
# Run temp_supply parallel smoke test on macOS/Linux.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_temp_supply_parallel_smoke.sh [--no-venv] [--no-install] [--] [args...]

Notes:
  - Use -- --help to show the Python script help.
  - Environment: PYTHON_EXE, VENV_DIR, REQ_FILE, SKIP_SETUP, SKIP_PIP.
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SKIP_SETUP="${SKIP_SETUP:-0}"
SKIP_PIP="${SKIP_PIP:-0}"
VENV_DIR="${VENV_DIR:-${REPO_ROOT}/.venv}"
REQ_FILE="${REQ_FILE:-${REPO_ROOT}/requirements.txt}"
PYTHON_EXE="${PYTHON_EXE:-}"
declare -a PASS_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-venv|--skip-setup)
      SKIP_SETUP=1
      shift
      ;;
    --no-install|--skip-pip)
      SKIP_PIP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        PASS_ARGS+=("$1")
        shift
      done
      break
      ;;
    *)
      PASS_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${PYTHON_EXE}" ]]; then
  for candidate in python3.11 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_EXE="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PYTHON_EXE}" ]]; then
  echo "[error] python3.11/python3/python not found in PATH" >&2
  exit 1
fi

PYTHON_BOOT="${PYTHON_EXE}"

if [[ "${SKIP_SETUP}" != "1" ]]; then
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "[setup] Creating virtual environment in ${VENV_DIR}..."
    "${PYTHON_BOOT}" -m venv "${VENV_DIR}"
  fi

  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    PYTHON_EXE="${VENV_DIR}/bin/python"
  else
    echo "[error] venv python not found under ${VENV_DIR}" >&2
    exit 1
  fi

  if [[ "${SKIP_PIP}" != "1" ]]; then
    if [[ -f "${REQ_FILE}" ]]; then
      echo "[setup] Installing dependencies from ${REQ_FILE} ..."
      "${PYTHON_EXE}" -m pip install --upgrade pip
      "${PYTHON_EXE}" -m pip install -r "${REQ_FILE}"
    else
      echo "[warn] ${REQ_FILE} not found; skipping dependency install."
    fi
  else
    echo "[setup] SKIP_PIP=1; skipping dependency install."
  fi
fi

cd "${REPO_ROOT}"
if ((${#PASS_ARGS[@]})); then
  exec "${PYTHON_EXE}" scripts/tests/temp_supply_parallel_smoke.py "${PASS_ARGS[@]}"
fi
exec "${PYTHON_EXE}" scripts/tests/temp_supply_parallel_smoke.py
