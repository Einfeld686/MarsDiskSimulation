#!/usr/bin/env bash
# Run a short cell-parallel on/off speed check (Windows-only).

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_cell_parallel_speed_check.sh [--no-venv] [--no-install] [--skip-os-check]
                                   [--force-non-windows] [--] [args...]

Notes:
  - Use -- --help to show the Python script help.
  - Environment: PYTHON_EXE, VENV_DIR, REQ_FILE, SKIP_SETUP, SKIP_PIP.
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SKIP_SETUP="${SKIP_SETUP:-0}"
SKIP_PIP="${SKIP_PIP:-0}"
SKIP_OS_CHECK=0
FORCE_NON_WINDOWS=0
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
    --skip-os-check)
      SKIP_OS_CHECK=1
      shift
      ;;
    --force-non-windows)
      FORCE_NON_WINDOWS=1
      SKIP_OS_CHECK=1
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
  for candidate in python3.11 python3 python py; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_EXE="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PYTHON_EXE}" ]]; then
  echo "[error] python3.11/python3/python/py not found in PATH" >&2
  exit 1
fi

PYTHON_BOOT="${PYTHON_EXE}"

if [[ "${SKIP_SETUP}" != "1" ]]; then
  if [[ ! -x "${VENV_DIR}/bin/python" && ! -x "${VENV_DIR}/Scripts/python.exe" && ! -x "${VENV_DIR}/Scripts/python" ]]; then
    echo "[setup] Creating virtual environment in ${VENV_DIR}..."
    "${PYTHON_BOOT}" -m venv "${VENV_DIR}"
  fi

  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    PYTHON_EXE="${VENV_DIR}/bin/python"
  elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
    PYTHON_EXE="${VENV_DIR}/Scripts/python.exe"
  elif [[ -x "${VENV_DIR}/Scripts/python" ]]; then
    PYTHON_EXE="${VENV_DIR}/Scripts/python"
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

if [[ "${SKIP_OS_CHECK}" != "1" ]]; then
  os_name="$("${PYTHON_EXE}" -c "import os; print(os.name)")"
  if [[ "${os_name}" != "nt" ]]; then
    echo "[skip] cell parallel is Windows-only (os.name=${os_name})."
    exit 0
  fi
fi

cd "${REPO_ROOT}"
if [[ "${FORCE_NON_WINDOWS}" == "1" ]]; then
  export MARSDISK_CELL_PARALLEL_FORCE=1
  if ((${#PASS_ARGS[@]})); then
    PASS_ARGS=(--force-non-windows "${PASS_ARGS[@]}")
  else
    PASS_ARGS=(--force-non-windows)
  fi
fi
exec "${PYTHON_EXE}" scripts/tests/cell_parallel_speed_check.py "${PASS_ARGS[@]}"
