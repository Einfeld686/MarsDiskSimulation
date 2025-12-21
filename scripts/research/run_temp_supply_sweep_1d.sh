#!/usr/bin/env bash
# Wrapper for run_temp_supply_sweep.sh with 1D geometry defaults.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GEOMETRY_MODE="${GEOMETRY_MODE:-1D}"
export GEOMETRY_NR="${GEOMETRY_NR:-32}"
export SWEEP_TAG="${SWEEP_TAG:-temp_supply_sweep_1d}"

exec "${SCRIPT_DIR}/run_temp_supply_sweep.sh"
