#!/usr/bin/env bash
# Run a temp_supply sweep (1D default).

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_sweep.sh [--study <path>] [--config <path>] [--overrides <path>]
               [--out-root <path>] [--dry-run] [--no-plot] [--no-eval] [--no-preflight]
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

CONFIG_PATH="scripts/runsets/common/base.yml"
OVERRIDES_PATH="scripts/runsets/mac/overrides.txt"
STUDY_PATH=""
OUT_ROOT=""
GEOMETRY_MODE="1D"
DRY_RUN=0
NO_PLOT=0
NO_EVAL=0
NO_PREFLIGHT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --study)
      STUDY_PATH="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --overrides)
      OVERRIDES_PATH="$2"
      shift 2
      ;;
    --out-root)
      OUT_ROOT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-plot)
      NO_PLOT=1
      shift
      ;;
    --no-eval)
      NO_EVAL=1
      shift
      ;;
    --no-preflight)
      NO_PREFLIGHT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
 done

if [[ -z "${HOOKS_ENABLE+x}" ]]; then
  HOOKS_ENABLE="plot,eval"
fi

normalize_hooks() {
  local -a hooks
  local -a kept
  IFS=',' read -r -a hooks <<< "${HOOKS_ENABLE}"
  for hook in "${hooks[@]}"; do
    hook="$(echo "${hook}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    hook="$(echo "${hook}" | tr '[:upper:]' '[:lower:]')"
    [[ -z "${hook}" ]] && continue
    case "${hook}" in
      plot)
        [[ "${NO_PLOT}" == "1" ]] && continue
        ;;
      eval)
        [[ "${NO_EVAL}" == "1" ]] && continue
        ;;
      preflight)
        [[ "${NO_PREFLIGHT}" == "1" ]] && continue
        ;;
    esac
    kept+=("${hook}")
  done
  if ((${#kept[@]})); then
    HOOKS_ENABLE="$(IFS=,; echo "${kept[*]}")"
  else
    HOOKS_ENABLE=""
  fi
}

normalize_hooks

if [[ "${NO_PLOT}" == "1" ]]; then
  export PLOT_ENABLE=0
fi
if [[ "${NO_EVAL}" == "1" ]]; then
  export EVAL=0
fi
if [[ "${HOOKS_ENABLE}" == *plot* ]]; then
  export PLOT_ENABLE=0
fi
if [[ "${HOOKS_ENABLE}" == *eval* ]]; then
  export EVAL=0
fi

export BASE_CONFIG="${CONFIG_PATH}"
export EXTRA_OVERRIDES_FILE="${OVERRIDES_PATH}"
export SWEEP_TAG="${SWEEP_TAG:-temp_supply_sweep_1d}"
export GEOMETRY_MODE="${GEOMETRY_MODE}"
export GEOMETRY_NR="${GEOMETRY_NR:-32}"
export SHIELDING_MODE="${SHIELDING_MODE:-off}"
export TAU_LIST_RAW="${TAU_LIST_RAW:-1.0 0.5 0.1}"
export SUPPLY_MU_REFERENCE_TAU="${SUPPLY_MU_REFERENCE_TAU:-1.0}"
export SUPPLY_FEEDBACK_ENABLED="${SUPPLY_FEEDBACK_ENABLED:-0}"
export SUPPLY_HEADROOM_POLICY="${SUPPLY_HEADROOM_POLICY:-}"
export SUPPLY_TRANSPORT_MODE="${SUPPLY_TRANSPORT_MODE:-direct}"
export SUPPLY_TRANSPORT_TMIX_ORBITS="${SUPPLY_TRANSPORT_TMIX_ORBITS:-}"
export SUPPLY_TRANSPORT_HEADROOM="${SUPPLY_TRANSPORT_HEADROOM:-hard}"
export HOOKS_ENABLE
if [[ -n "${STUDY_PATH}" ]]; then
  export STUDY_FILE="${STUDY_PATH}"
fi
if [[ -n "${OUT_ROOT}" ]]; then
  export OUT_ROOT="${OUT_ROOT}"
fi
if [[ "${DRY_RUN}" == "1" ]]; then
  export DRY_RUN=1
fi

cd "${REPO_ROOT}"
exec "${REPO_ROOT}/scripts/research/run_temp_supply_sweep.sh"
