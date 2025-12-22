#!/usr/bin/env bash
# Wrapper for run_temp_supply_sweep.sh with 1D geometry defaults.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GEOMETRY_MODE="${GEOMETRY_MODE:-1D}"
export GEOMETRY_NR="${GEOMETRY_NR:-32}"
export SWEEP_TAG="${SWEEP_TAG:-temp_supply_sweep_1d}"
export SHIELDING_MODE="${SHIELDING_MODE:-off}"
export TAU_LIST_RAW="${TAU_LIST_RAW:-1.0 0.5 0.1}"
export SUPPLY_MU_REFERENCE_TAU="${SUPPLY_MU_REFERENCE_TAU:-1.0}"
export SUPPLY_FEEDBACK_ENABLED="${SUPPLY_FEEDBACK_ENABLED:-0}"
export SUPPLY_HEADROOM_POLICY="${SUPPLY_HEADROOM_POLICY:-}"
export SUPPLY_TRANSPORT_MODE="${SUPPLY_TRANSPORT_MODE:-direct}"
export SUPPLY_TRANSPORT_TMIX_ORBITS="${SUPPLY_TRANSPORT_TMIX_ORBITS:-}"
export SUPPLY_TRANSPORT_HEADROOM="${SUPPLY_TRANSPORT_HEADROOM:-hard}"

exec "${SCRIPT_DIR}/run_temp_supply_sweep.sh"
