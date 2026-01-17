#!/usr/bin/env bash
# Run temp supply sweep (sublimation only)
# T_M = {4000, 3000} K
# epsilon_mix = {1.0, 0.5}
# mu_orbit10pct = 1.0 (1 orbit supplies 5% of Sigma_ref(tau=1); scaled by orbit_fraction_at_mu1)
# tau0_target = {1.0, 0.5}
# dynamics.i0 = {0.05, 0.10}
# extra cases: none (set EXTRA_CASES for optional quadruples)
# material defaults: forsterite via configs/overrides/material_forsterite.override
# Outputs under: out/temp_supply_sweep/<ts>__<sha>__seed<BATCH>/T{T}_eps{eps}_tau{tau}_i0{i0}_mode-sublimation_only/

set -euo pipefail

VENV_DIR=".venv"
REQ_FILE="requirements.txt"
RUN_TS="$(date +%Y%m%d-%H%M%S)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
BATCH_SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
BATCH_DIR="out/temp_supply_sweep/${RUN_TS}__${GIT_SHA}__seed${BATCH_SEED}"
mkdir -p "${BATCH_DIR}"

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

BASE_CONFIG="configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"
DEFAULT_MATERIAL_OVERRIDES="${DEFAULT_MATERIAL_OVERRIDES:-configs/overrides/material_forsterite.override}"
if [[ -z "${EXTRA_OVERRIDES_FILE+x}" ]]; then
  EXTRA_OVERRIDES_FILE="${DEFAULT_MATERIAL_OVERRIDES}"
fi
EXTRA_OVERRIDE_ARGS=()
if [[ -n "${EXTRA_OVERRIDES_FILE:-}" ]]; then
  if [[ -f "${EXTRA_OVERRIDES_FILE}" ]]; then
    EXTRA_OVERRIDE_ARGS=(--overrides-file "${EXTRA_OVERRIDES_FILE}")
  else
    echo "[warn] EXTRA_OVERRIDES_FILE not found: ${EXTRA_OVERRIDES_FILE}"
  fi
fi
T_LIST=("5000" "4000" "3000")
EPS_LIST=("1.0" "0.5")
TAU_LIST=("1.0" "0.5")
I0_LIST=("0.05" "0.01" "0.005")
EXTRA_CASES_DEFAULT=""
if [[ -n "${EXTRA_CASES+x}" ]]; then
  EXTRA_CASES_VALUE="${EXTRA_CASES}"
else
  EXTRA_CASES_VALUE="${EXTRA_CASES_DEFAULT}"
fi
case "${EXTRA_CASES_VALUE}" in
  [Nn][Oo][Nn][Ee]|[Oo][Ff][Ff]|[Ff][Aa][Ll][Ss][Ee]|0)
    EXTRA_CASES_VALUE=""
    ;;
esac
CASE_KEYS=()
CASE_T=()
CASE_EPS=()
CASE_TAU=()
CASE_I0=()

add_case() {
  local t="$1"
  local eps="$2"
  local tau="$3"
  local i0="$4"
  local key="${t}|${eps}|${tau}|${i0}"
  local existing
  if (( ${#CASE_KEYS[@]} )); then
    for existing in "${CASE_KEYS[@]}"; do
      if [[ "${existing}" == "${key}" ]]; then
        return 1
      fi
    done
  fi
  CASE_KEYS+=("${key}")
  CASE_T+=("${t}")
  CASE_EPS+=("${eps}")
  CASE_TAU+=("${tau}")
  CASE_I0+=("${i0}")
  return 0
}

append_extra_cases() {
  local raw="$1"
  local cleaned="${raw//;/ }"
  cleaned="${cleaned//,/ }"
  cleaned="${cleaned//:/ }"
  cleaned="${cleaned//|/ }"
  local tokens=()
  read -r -a tokens <<< "${cleaned}"
  local count=${#tokens[@]}
  if (( count == 0 )); then
    return 0
  fi
  if (( count % 4 != 0 )); then
    echo "[warn] EXTRA_CASES expects quadruples; got ${count} tokens"
  fi
  local idx=0
  while (( idx + 3 < count )); do
    add_case "${tokens[idx]}" "${tokens[idx + 1]}" "${tokens[idx + 2]}" "${tokens[idx + 3]}" || true
    idx=$((idx + 4))
  done
}

for T in "${T_LIST[@]}"; do
  for EPS in "${EPS_LIST[@]}"; do
    for TAU in "${TAU_LIST[@]}"; do
      for I0 in "${I0_LIST[@]}"; do
        add_case "${T}" "${EPS}" "${TAU}" "${I0}" || true
      done
    done
  done
done
if [[ -n "${EXTRA_CASES_VALUE}" ]]; then
  append_extra_cases "${EXTRA_CASES_VALUE}"
fi
MODE="sublimation_only"
SUPPLY_MU_ORBIT10PCT="${SUPPLY_MU_ORBIT10PCT:-1.0}"
SUPPLY_ORBIT_FRACTION="${SUPPLY_ORBIT_FRACTION:-0.05}"

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

for idx in "${!CASE_T[@]}"; do
  T="${CASE_T[$idx]}"
  EPS="${CASE_EPS[$idx]}"
  TAU="${CASE_TAU[$idx]}"
  I0="${CASE_I0[$idx]}"
  T_TABLE="data/mars_temperature_T${T}p0K.csv"
  EPS_TITLE="${EPS/0./0p}"
  EPS_TITLE="${EPS_TITLE/./p}"
  TAU_TITLE="${TAU/0./0p}"
  TAU_TITLE="${TAU_TITLE/./p}"
  I0_TITLE="${I0/0./0p}"
  I0_TITLE="${I0_TITLE/./p}"
  SEED=$(python - <<'PY'
import secrets
print(secrets.randbelow(2**31))
PY
)
  TITLE="T${T}_eps${EPS_TITLE}_tau${TAU_TITLE}_i0${I0_TITLE}_mode-${MODE}"
  OUTDIR="${BATCH_DIR}/${TITLE}"
  echo "[run] mode=${MODE} T=${T} eps=${EPS} tau=${TAU} i0=${I0} -> ${OUTDIR} (batch=${BATCH_SEED}, seed=${SEED})"
  python -m marsdisk.run \
    --config "${BASE_CONFIG}" \
    "${EXTRA_OVERRIDE_ARGS[@]}" \
    --quiet \
    "${PROGRESS_FLAG[@]}" \
    --override numerics.dt_init=20 \
    --override "io.outdir=${OUTDIR}" \
    --override "dynamics.rng_seed=${SEED}" \
    --override "radiation.TM_K=${T}" \
    --override "radiation.mars_temperature_driver.table.path=${T_TABLE}" \
    --override "supply.mixing.epsilon_mix=${EPS}" \
    --override "supply.const.mu_orbit10pct=${SUPPLY_MU_ORBIT10PCT}" \
    --override "supply.const.orbit_fraction_at_mu1=${SUPPLY_ORBIT_FRACTION}" \
    --override "optical_depth.tau0_target=${TAU}" \
    --override "dynamics.i0=${I0}" \
    --override "shielding.mode=off" \
    --override "physics_mode=${MODE}"

      RUN_DIR="${OUTDIR}" python - <<'PY'
import os
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import pyarrow.parquet as pq
import pandas as pd
import matplotlib.pyplot as plt

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
    "mass_lost_by_blowout",
    "mass_lost_by_sinks",
    "s_min",
    "a_blow",
    "prod_subblow_area_rate",
    "Sigma_surf",
    "outflux_surface",
    "cell_index",
    "r_RM",
]

summary = {}
if summary_path.exists():
    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        summary = {}

df = pd.read_parquet(series_path, columns=series_cols)

def _series_label(tag, r_rm):
    if r_rm is None:
        return tag
    return f"{tag} r_RM={r_rm:.3f}"


def _series_sets(df):
    if "cell_index" not in df.columns or "r_RM" not in df.columns:
        return [("0D", None, df)]
    cells = (
        df[["cell_index", "r_RM"]]
        .dropna()
        .drop_duplicates()
        .sort_values("r_RM")
    )
    if cells.empty:
        return [("0D", None, df)]
    inner = cells.iloc[0]
    outer = cells.iloc[-1]
    rings = [("inner", int(inner["cell_index"]), float(inner["r_RM"]))]
    if int(outer["cell_index"]) != int(inner["cell_index"]):
        rings.append(("outer", int(outer["cell_index"]), float(outer["r_RM"])))
    series_sets = []
    for tag, cell_idx, r_rm in rings:
        ring_df = df[df["cell_index"] == cell_idx].copy()
        if "time" in ring_df.columns:
            ring_df = ring_df.sort_values("time")
            ring_df = ring_df.groupby("time", as_index=False).first()
        series_sets.append((tag, r_rm, ring_df))
    return series_sets


series_sets = []
for tag, r_rm, sdf in _series_sets(df):
    n = len(sdf)
    step = max(n // 4000, 1)
    sdf = sdf.iloc[::step].copy()
    sdf["time_days"] = sdf["time"] / 86400.0
    series_sets.append((tag, r_rm, sdf))

fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
for tag, r_rm, sdf in series_sets:
    label = _series_label(tag, r_rm)
    axes[0].plot(sdf["time_days"], sdf["M_out_dot"], label=f"M_out_dot (blowout) ({label})", lw=1.2)
    axes[0].plot(sdf["time_days"], sdf["M_sink_dot"], label=f"M_sink_dot (sinks) ({label})", lw=1.0, alpha=0.7)
axes[0].set_ylabel("M_Mars / s")
axes[0].legend(loc="upper right")
axes[0].set_title("Mass loss rates")

for tag, r_rm, sdf in series_sets:
    label = _series_label(tag, r_rm)
    axes[1].plot(sdf["time_days"], sdf["M_loss_cum"], label=f"M_loss_cum (total) ({label})", lw=1.2)
    axes[1].plot(sdf["time_days"], sdf["mass_lost_by_blowout"], label=f"mass_lost_by_blowout ({label})", lw=1.0)
    axes[1].plot(sdf["time_days"], sdf["mass_lost_by_sinks"], label=f"mass_lost_by_sinks ({label})", lw=1.0)
axes[1].set_ylabel("M_Mars")
axes[1].legend(loc="upper left")
axes[1].set_title("Cumulative losses")

for tag, r_rm, sdf in series_sets:
    label = _series_label(tag, r_rm)
    axes[2].plot(sdf["time_days"], sdf["s_min"], label=f"s_min ({label})", lw=1.0)
    axes[2].plot(sdf["time_days"], sdf["a_blow"], label=f"a_blow ({label})", lw=1.0, alpha=0.8)
axes[2].set_ylabel("m")
axes[2].set_xlabel("days")
axes[2].set_yscale("log")
axes[2].legend(loc="upper right")
axes[2].set_title("Minimum size vs blowout")

mloss = summary.get("M_loss")
mass_err = summary.get("mass_budget_max_error_percent")
title_lines = [run_dir.name]
if mloss is not None:
    title_lines.append(f"M_loss={mloss:.3e} M_Mars")
if mass_err is not None:
    title_lines.append(f"mass budget err={mass_err:.3f}%")
fig.suptitle(" | ".join(title_lines))
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(plots_dir / "overview.png", dpi=180)
plt.close(fig)

fig2, ax2 = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
ax2[0].plot(df["time_days"], df["prod_subblow_area_rate"], label="prod_subblow_area_rate", color="tab:blue")
ax2[0].set_ylabel("kg m^-2 s^-1")
ax2[0].set_title("Sub-blow supply rate")

ax2[1].plot(df["time_days"], df["Sigma_surf"], label="Sigma_surf", color="tab:green")
ax2[1].plot(df["time_days"], df["outflux_surface"], label="outflux_surface (surface blowout)", color="tab:red", alpha=0.8)
ax2[1].set_ylabel("kg m^-2 / M_Mars s^-1")
ax2[1].set_xlabel("days")
ax2[1].legend(loc="upper right")
ax2[1].set_title("Surface mass and outflux")

fig2.suptitle(run_dir.name)
fig2.tight_layout(rect=(0, 0, 1, 0.95))
fig2.savefig(plots_dir / "supply_surface.png", dpi=180)
plt.close(fig2)
print(f"[plot] saved plots to {plots_dir}")
PY
done

echo "[done] Sweep (sublimation_only) completed (batch=${BATCH_SEED}, dir=${BATCH_DIR})."
