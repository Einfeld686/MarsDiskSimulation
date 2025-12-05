#!/usr/bin/env bash
set -euo pipefail
OUTDIR="${OUTDIR:-out/$(date -u +%Y%m%d-%H%M%S)_sublim_smol_phase_MAX50M}"
python -m marsdisk.run \
  --config out/run_template_sublim_smol_phase_MAX50M/config_base_sublimation.yml \
  --override io.outdir="$OUTDIR" \
  --override qstar.v_ref_kms='[1.0, 5.0]' \
  --override sinks.sub_params.mode=hkl \
  --override sinks.sub_params.alpha_evap=0.007 \
  --override sinks.sub_params.mu=0.0440849 \
  --override sinks.sub_params.A=13.613 \
  --override sinks.sub_params.B=17850.0
