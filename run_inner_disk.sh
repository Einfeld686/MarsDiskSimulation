#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Error on line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

die() {
  echo "$*" >&2
  exit 1
}

PYTHON_BIN="${PYTHON:-}"
if [ -n "$PYTHON_BIN" ]; then
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    die "PYTHON is set but command not found: ${PYTHON_BIN}"
  fi
else
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    die "Python interpreter not found. Set PYTHON."
  fi
fi
echo "Using Python interpreter: ${PYTHON_BIN}"

if ! "$PYTHON_BIN" -c "import marsdisk" >/dev/null 2>&1; then
  die "Interpreter ${PYTHON_BIN} cannot import marsdisk."
fi
echo "Verified marsdisk import."

BLOWOUT_CONFIG="simulation_results/_configs/01_inner_r1_to_r3_blowout.yml"
SUBLIMATION_CONFIG="simulation_results/_configs/02_inner_r1_to_r3_sublimation_no_floor.yml"
SWEEP_SCRIPT="scripts/sweep_heatmaps.py"
FIG_SCRIPT="tools/plotting/make_figs.py"

for required in "$BLOWOUT_CONFIG" "$SUBLIMATION_CONFIG" "$SWEEP_SCRIPT" "$FIG_SCRIPT"; do
  if [ ! -f "$required" ]; then
    die "Missing required file: ${required}"
  fi
done

QPR_PATH="${1:-tables/qpr_SiO_default.csv}"
if [ ! -f "$QPR_PATH" ]; then
  die "QPR table not found: ${QPR_PATH}"
fi
echo "Using QPR table: ${QPR_PATH}"

if [ -n "${RADII_OVERRIDE+x}" ]; then
  if [ -z "${RADII_OVERRIDE//[[:space:]]/}" ]; then
    die "RADII_OVERRIDE is set but empty."
  fi
  RADII_LIST="$RADII_OVERRIDE"
else
  RADII_LIST="1.0 2.0 3.0"
fi
echo "Target radii: ${RADII_LIST}"

OUTDIR="${OUTDIR:-simulation_results/03_inner_disk_sweep}"
echo "Sweep output directory: ${OUTDIR}"
mkdir -p "$OUTDIR"

for radius in $RADII_LIST; do
  echo "Running blowout case at R_M=${radius}"
  "$PYTHON_BIN" -m marsdisk.run \
    --config "$BLOWOUT_CONFIG" \
    --override "disk.geometry.r_in_RM=${radius}" "disk.geometry.r_out_RM=${radius}" \
    "radiation.qpr_table_path=${QPR_PATH}"
  echo "Running sublimation case at R_M=${radius}"
  "$PYTHON_BIN" -m marsdisk.run \
    --config "$SUBLIMATION_CONFIG" \
    --override "disk.geometry.r_in_RM=${radius}" "disk.geometry.r_out_RM=${radius}" \
    "radiation.qpr_table_path=${QPR_PATH}" \
    --sinks "sublimation"
done

echo "Running sweep heatmap map=1"
"$PYTHON_BIN" "scripts/sweep_heatmaps.py" \
  --map "1" \
  --rmin_rm "1.0" \
  --rmax_rm "3.0" \
  --rstep_rm "0.2" \
  --tmin_k "2000" \
  --tmax_k "6000" \
  --tstep_k "300" \
  --qpr_table "$QPR_PATH" \
  --outdir "$OUTDIR"

echo "Generating figures"
"$PYTHON_BIN" "tools/plotting/make_figs.py"

if [ -f "${OUTDIR}/fig_map1_regime.png" ]; then
  echo "Figure check OK: ${OUTDIR}/fig_map1_regime.png"
else
  echo "Figure check NG: ${OUTDIR}/fig_map1_regime.png missing" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PYCODE'
import glob
import json
import os
import sys

files = glob.glob(os.path.join("simulation_results", "**", "run_config.json"), recursive=True)
if not files:
    print("No run_config.json files found under simulation_results.", file=sys.stderr)
    sys.exit(1)
latest = max(files, key=os.path.getmtime)
with open(latest, "r", encoding="utf-8") as handle:
    data = json.load(handle)
required_keys = ["qpr_table_path", "Q_pr_used", "T_M_used", "r_RM_used"]
missing = [key for key in required_keys if key not in data]
if missing:
    print("Missing keys in {}: {}".format(latest, ", ".join(missing)), file=sys.stderr)
    sys.exit(1)
print("Latest run_config.json OK: {}".format(latest))
PYCODE

echo "All tasks completed successfully."
