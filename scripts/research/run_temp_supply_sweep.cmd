@echo off
rem Windows CMD version of run_temp_supply_sweep.sh (logic preserved, output rooted under out/)
setlocal EnableExtensions EnableDelayedExpansion

rem ---------- setup ----------
if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format \"yyyyMMdd-HHmmss\""') do set "RUN_TS=%%A"
for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
if not defined GIT_SHA set "GIT_SHA=nogit"
for /f %%A in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set "BATCH_SEED=%%A"

rem Force output root to out/ as requested
set "BATCH_ROOT=out"
set "BATCH_DIR=%BATCH_ROOT%\temp_supply_sweep\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%"
echo.[setup] Output root: %BATCH_ROOT%
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.[setup] Creating virtual environment in %VENV_DIR%...
  python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

if exist "%REQ_FILE%" (
  echo.[setup] Installing/upgrading dependencies from %REQ_FILE% ...
  python -m pip install --upgrade pip
  pip install -r "%REQ_FILE%"
) else (
  echo.[warn] %REQ_FILE% not found; skipping dependency install.
)

rem ---------- defaults ----------
if not defined BASE_CONFIG set "BASE_CONFIG=configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"
if not defined QSTAR_UNITS set "QSTAR_UNITS=ba99_cgs"
rem Cooling defaults (stop when Mars T_M reaches 1000 K, slab law unless overridden)
if not defined COOL_TO_K set "COOL_TO_K=1000"
if not defined COOL_MARGIN_YEARS set "COOL_MARGIN_YEARS=0"
if not defined COOL_SEARCH_YEARS set "COOL_SEARCH_YEARS="
if not defined COOL_MODE set "COOL_MODE=slab"
if not defined EVAL set "EVAL=1"
if not defined SUBSTEP_FAST_BLOWOUT set "SUBSTEP_FAST_BLOWOUT=0"
if not defined SUBSTEP_MAX_RATIO set "SUBSTEP_MAX_RATIO="
if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=clip"
if not defined SUPPLY_MODE set "SUPPLY_MODE=const"
if not defined SUPPLY_RATE set "SUPPLY_RATE=3.0e-6"
if not defined SHIELDING_MODE set "SHIELDING_MODE=psitau"
if not defined SHIELDING_SIGMA set "SHIELDING_SIGMA=auto"
if not defined SHIELDING_AUTO_MAX_MARGIN set "SHIELDING_AUTO_MAX_MARGIN=0.05"
if not defined INIT_SCALE_TO_TAU1 set "INIT_SCALE_TO_TAU1=true"
if not defined SUPPLY_RESERVOIR_M set "SUPPLY_RESERVOIR_M="
if not defined SUPPLY_RESERVOIR_MODE set "SUPPLY_RESERVOIR_MODE=hard_stop"
if not defined SUPPLY_RESERVOIR_TAPER set "SUPPLY_RESERVOIR_TAPER=0.05"
if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"
if not defined SUPPLY_FEEDBACK_TARGET set "SUPPLY_FEEDBACK_TARGET=1.0"
if not defined SUPPLY_FEEDBACK_GAIN set "SUPPLY_FEEDBACK_GAIN=1.0"
if not defined SUPPLY_FEEDBACK_RESPONSE_YR set "SUPPLY_FEEDBACK_RESPONSE_YR=0.5"
if not defined SUPPLY_FEEDBACK_MIN_SCALE set "SUPPLY_FEEDBACK_MIN_SCALE=0.0"
if not defined SUPPLY_FEEDBACK_MAX_SCALE set "SUPPLY_FEEDBACK_MAX_SCALE=10.0"
if not defined SUPPLY_FEEDBACK_TAU_FIELD set "SUPPLY_FEEDBACK_TAU_FIELD=tau_vertical"
if not defined SUPPLY_FEEDBACK_INITIAL set "SUPPLY_FEEDBACK_INITIAL=1.0"
if not defined SUPPLY_TEMP_ENABLED set "SUPPLY_TEMP_ENABLED=0"
if not defined SUPPLY_TEMP_MODE set "SUPPLY_TEMP_MODE=scale"
if not defined SUPPLY_TEMP_REF_K set "SUPPLY_TEMP_REF_K=1800.0"
if not defined SUPPLY_TEMP_EXP set "SUPPLY_TEMP_EXP=1.0"
if not defined SUPPLY_TEMP_SCALE_REF set "SUPPLY_TEMP_SCALE_REF=1.0"
if not defined SUPPLY_TEMP_FLOOR set "SUPPLY_TEMP_FLOOR=0.0"
if not defined SUPPLY_TEMP_CAP set "SUPPLY_TEMP_CAP=10.0"
if not defined SUPPLY_TEMP_TABLE_PATH set "SUPPLY_TEMP_TABLE_PATH="
if not defined SUPPLY_TEMP_TABLE_VALUE_KIND set "SUPPLY_TEMP_TABLE_VALUE_KIND=scale"
if not defined SUPPLY_TEMP_TABLE_COL_T set "SUPPLY_TEMP_TABLE_COL_T=T_K"
if not defined SUPPLY_TEMP_TABLE_COL_VAL set "SUPPLY_TEMP_TABLE_COL_VAL=value"
if not defined SUPPLY_INJECTION_MODE set "SUPPLY_INJECTION_MODE=powerlaw_bins"
if not defined SUPPLY_INJECTION_Q set "SUPPLY_INJECTION_Q=3.5"
if not defined SUPPLY_INJECTION_SMIN set "SUPPLY_INJECTION_SMIN="
if not defined SUPPLY_INJECTION_SMAX set "SUPPLY_INJECTION_SMAX="
if not defined SUPPLY_DEEP_TMIX_ORBITS set "SUPPLY_DEEP_TMIX_ORBITS="
if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=deep_mixing"
if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=50"
if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=soft"
if not defined SUPPLY_VEL_MODE set "SUPPLY_VEL_MODE=inherit"
if not defined SUPPLY_VEL_E set "SUPPLY_VEL_E=0.05"
if not defined SUPPLY_VEL_I set "SUPPLY_VEL_I=0.025"
if not defined SUPPLY_VEL_FACTOR set "SUPPLY_VEL_FACTOR="
if not defined SUPPLY_VEL_BLEND set "SUPPLY_VEL_BLEND=rms"
if not defined SUPPLY_VEL_WEIGHT set "SUPPLY_VEL_WEIGHT=delta_sigma"
if not defined STREAM_MEM_GB set "STREAM_MEM_GB="
if not defined STREAM_STEP_INTERVAL set "STREAM_STEP_INTERVAL="
if not defined ENABLE_PROGRESS set "ENABLE_PROGRESS=1"

set "T_LIST=5000 4000 3000"
set "MU_LIST=1.0 0.5 0.1"
set "PHI_LIST=20 37 60"

set "COOL_SEARCH_DISPLAY=%COOL_SEARCH_YEARS%"
if not defined COOL_SEARCH_DISPLAY set "COOL_SEARCH_DISPLAY=none"

echo.[config] supply multipliers: temp_enabled=%SUPPLY_TEMP_ENABLED% (mode=%SUPPLY_TEMP_MODE%) feedback_enabled=%SUPPLY_FEEDBACK_ENABLED% reservoir=%SUPPLY_RESERVOIR_M%
echo.[config] shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN% init_scale_to_tau1=%INIT_SCALE_TO_TAU1%
echo.[config] injection: mode=%SUPPLY_INJECTION_MODE% q=%SUPPLY_INJECTION_Q% s_inj_min=%SUPPLY_INJECTION_SMIN% s_inj_max=%SUPPLY_INJECTION_SMAX%
echo.[config] transport: mode=%SUPPLY_TRANSPORT_MODE% t_mix=%SUPPLY_TRANSPORT_TMIX_ORBITS% headroom_gate=%SUPPLY_TRANSPORT_HEADROOM% velocity=%SUPPLY_VEL_MODE%
echo.[config] const supply before mixing: %SUPPLY_RATE% kg m^-2 s^-1 (epsilon_mix swept per MU_LIST)
echo.[config] fast blowout substep: enabled=%SUBSTEP_FAST_BLOWOUT% substep_max_ratio=%SUBSTEP_MAX_RATIO%
if defined COOL_TO_K (
  echo.[config] dynamic horizon: stop when Mars T_M ^<= !COOL_TO_K! K (margin !COOL_MARGIN_YEARS! yr, search_cap=!COOL_SEARCH_DISPLAY!)
) else (
  echo.[config] dynamic horizon disabled (using numerics.t_end_* from config)
)
echo.[config] cooling driver mode: %COOL_MODE% (slab: T^-3, hyodo: linear flux)

set "PROGRESS_FLAG="
if "%ENABLE_PROGRESS%"=="1" set "PROGRESS_FLAG=--progress"

set "STREAMING_OVERRIDES="
if defined STREAM_MEM_GB (
  set "STREAMING_OVERRIDES=--override io.streaming.memory_limit_gb=%STREAM_MEM_GB%"
  echo.[info] override io.streaming.memory_limit_gb=%STREAM_MEM_GB%
)
if defined STREAM_STEP_INTERVAL (
  if defined STREAMING_OVERRIDES (
    set "STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.step_flush_interval=%STREAM_STEP_INTERVAL%"
  ) else (
    set "STREAMING_OVERRIDES=--override io.streaming.step_flush_interval=%STREAM_STEP_INTERVAL%"
  )
  echo.[info] override io.streaming.step_flush_interval=%STREAM_STEP_INTERVAL%
)

set "SUPPLY_OVERRIDES="
if defined SUPPLY_RESERVOIR_M (
  set "SUPPLY_OVERRIDES=--override \"supply.reservoir.enabled=true\" --override \"supply.reservoir.mass_total_Mmars=%SUPPLY_RESERVOIR_M%\" --override \"supply.reservoir.depletion_mode=%SUPPLY_RESERVOIR_MODE%\" --override \"supply.reservoir.taper_fraction=%SUPPLY_RESERVOIR_TAPER%\""
  echo.[info] supply reservoir: M=%SUPPLY_RESERVOIR_M% M_Mars mode=%SUPPLY_RESERVOIR_MODE% taper_fraction=%SUPPLY_RESERVOIR_TAPER%
)
if "%SUPPLY_FEEDBACK_ENABLED%" NEQ "0" (
  set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.feedback.enabled=true\" --override \"supply.feedback.target_tau=%SUPPLY_FEEDBACK_TARGET%\" --override \"supply.feedback.gain=%SUPPLY_FEEDBACK_GAIN%\" --override \"supply.feedback.response_time_years=%SUPPLY_FEEDBACK_RESPONSE_YR%\" --override \"supply.feedback.min_scale=%SUPPLY_FEEDBACK_MIN_SCALE%\" --override \"supply.feedback.max_scale=%SUPPLY_FEEDBACK_MAX_SCALE%\" --override \"supply.feedback.tau_field=%SUPPLY_FEEDBACK_TAU_FIELD%\" --override \"supply.feedback.initial_scale=%SUPPLY_FEEDBACK_INITIAL%\""
  echo.[info] supply feedback enabled: target_tau=%SUPPLY_FEEDBACK_TARGET%, gain=%SUPPLY_FEEDBACK_GAIN%, tau_field=%SUPPLY_FEEDBACK_TAU_FIELD%
)
if "%SUPPLY_TEMP_ENABLED%" NEQ "0" (
  set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.temperature.enabled=true\" --override \"supply.temperature.mode=%SUPPLY_TEMP_MODE%\" --override \"supply.temperature.reference_K=%SUPPLY_TEMP_REF_K%\" --override \"supply.temperature.exponent=%SUPPLY_TEMP_EXP%\" --override \"supply.temperature.scale_at_reference=%SUPPLY_TEMP_SCALE_REF%\" --override \"supply.temperature.floor=%SUPPLY_TEMP_FLOOR%\" --override \"supply.temperature.cap=%SUPPLY_TEMP_CAP%\""
  if defined SUPPLY_TEMP_TABLE_PATH (
    set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.temperature.table.path=%SUPPLY_TEMP_TABLE_PATH%\" --override \"supply.temperature.table.value_kind=%SUPPLY_TEMP_TABLE_VALUE_KIND%\" --override \"supply.temperature.table.column_temperature=%SUPPLY_TEMP_TABLE_COL_T%\" --override \"supply.temperature.table.column_value=%SUPPLY_TEMP_TABLE_COL_VAL%\""
  )
  echo.[info] supply temperature coupling enabled: mode=%SUPPLY_TEMP_MODE%
)
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.mode=%SUPPLY_INJECTION_MODE%\" --override \"supply.injection.q=%SUPPLY_INJECTION_Q%\""
if defined SUPPLY_INJECTION_SMIN set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.s_inj_min=%SUPPLY_INJECTION_SMIN%\""
if defined SUPPLY_INJECTION_SMAX set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.s_inj_max=%SUPPLY_INJECTION_SMAX%\""
if defined SUPPLY_DEEP_TMIX_ORBITS (
  set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.t_mix_orbits=%SUPPLY_DEEP_TMIX_ORBITS%\" --override \"supply.transport.mode=deep_mixing\""
  echo.[info] deep reservoir enabled (legacy alias): t_mix=%SUPPLY_DEEP_TMIX_ORBITS% orbits
)
if defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.t_mix_orbits=%SUPPLY_TRANSPORT_TMIX_ORBITS%\""
if defined SUPPLY_TRANSPORT_MODE set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.mode=%SUPPLY_TRANSPORT_MODE%\""
if defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.headroom_gate=%SUPPLY_TRANSPORT_HEADROOM%\""
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.headroom_policy=%SUPPLY_HEADROOM_POLICY%\" --override \"supply.injection.velocity.mode=%SUPPLY_VEL_MODE%\""
if defined SUPPLY_VEL_E set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.e_inj=%SUPPLY_VEL_E%\""
if defined SUPPLY_VEL_I set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.i_inj=%SUPPLY_VEL_I%\""
if defined SUPPLY_VEL_FACTOR set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.vrel_factor=%SUPPLY_VEL_FACTOR%\""
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.blend_mode=%SUPPLY_VEL_BLEND%\" --override \"supply.injection.velocity.weight_mode=%SUPPLY_VEL_WEIGHT%\""

rem ---------- main loops ----------
for %%T in (%T_LIST%) do (
  set "T_TABLE=data/mars_temperature_T%%Tp0K.csv"
  for %%M in (%MU_LIST%) do (
    set "MU=%%M"
    set "MU_TITLE=%%M"
    set "MU_TITLE=!MU_TITLE:0.=0p!"
    set "MU_TITLE=!MU_TITLE:.=p!"
    for %%P in (%PHI_LIST%) do (
      for /f %%S in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set "SEED=%%S"
      set "TITLE=T%%T_mu!MU_TITLE!_phi%%P"
      set "OUTDIR=%BATCH_DIR%\!TITLE!"
      echo.[run] T=%%T mu=%%M phi=%%P -^> !OUTDIR! (batch=%BATCH_SEED%, seed=!SEED!)
      for /f %%R in ('python -c "rate=float('%SUPPLY_RATE%'); mu=float('%%M'); print(f'{rate*mu:.3e}')"') do set "EFF_RATE=%%R"
      echo.[info] effective scale epsilon_mix=%%M; effective supply (const*epsilon_mix)=!EFF_RATE! kg m^-2 s^-1
      echo.[info] shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
      if "%%M"=="0.1" echo.[info] mu=0.1 is a low-supply extreme case; expect weak blowout/sinks

      if not exist "!OUTDIR!\series" mkdir "!OUTDIR!\series"
      if not exist "!OUTDIR!\checks" mkdir "!OUTDIR!\checks"

      set "CMD_EXTRA="
      if defined COOL_TO_K (
        set "CMD_EXTRA=!CMD_EXTRA! --override \"numerics.t_end_until_temperature_K=%COOL_TO_K%\" --override \"numerics.t_end_temperature_margin_years=%COOL_MARGIN_YEARS%\""
        if defined COOL_SEARCH_YEARS set "CMD_EXTRA=!CMD_EXTRA! --override \"numerics.t_end_temperature_search_years=%COOL_SEARCH_YEARS%\""
      )
      if "%SUBSTEP_FAST_BLOWOUT%" NEQ "0" (
        set "CMD_EXTRA=!CMD_EXTRA! --override \"io.substep_fast_blowout=true\""
        if defined SUBSTEP_MAX_RATIO set "CMD_EXTRA=!CMD_EXTRA! --override \"io.substep_max_ratio=%SUBSTEP_MAX_RATIO%\""
      )

      python -m marsdisk.run ^
        --config "%BASE_CONFIG%" ^
        --quiet ^
        %PROGRESS_FLAG% ^
        --override numerics.dt_init=20 ^
        --override numerics.stop_on_blowout_below_smin=true ^
        --override "io.outdir=!OUTDIR!" ^
        --override "dynamics.rng_seed=!SEED!" ^
        --override "phase.enabled=false" ^
        --override "radiation.TM_K=%%T" ^
        --override "qstar.coeff_units=%QSTAR_UNITS%" ^
        --override "radiation.mars_temperature_driver.enabled=true" ^
        --override "supply.enabled=true" ^
        --override "supply.mixing.epsilon_mix=%%M" ^
        --override "supply.mode=%SUPPLY_MODE%" ^
        --override "supply.const.prod_area_rate_kg_m2_s=%SUPPLY_RATE%" ^
        --override "init_tau1.scale_to_tau1=%INIT_SCALE_TO_TAU1%" ^
        --override "shielding.table_path=tables/phi_const_0p%%P.csv" ^
        --override "shielding.mode=%SHIELDING_MODE%" ^
        --override "radiation.mars_temperature_driver.mode=%COOL_MODE%" ^
        --override "radiation.mars_temperature_driver.table.path=!T_TABLE!" ^
        --override "radiation.mars_temperature_driver.table.time_unit=day" ^
        --override "radiation.mars_temperature_driver.table.column_time=time_day" ^
        --override "radiation.mars_temperature_driver.table.column_temperature=T_K" ^
        --override "radiation.mars_temperature_driver.extrapolation=hold" ^
        %SUPPLY_OVERRIDES% ^
        !STREAMING_OVERRIDES! ^
        !CMD_EXTRA!

      if errorlevel 1 (
        echo.[warn] run command exited with status !errorlevel!; attempting plots anyway
      )

      set "RUN_DIR=!OUTDIR!"
      set "PYSCRIPT=%TEMP%\run_temp_supply_plot_!RANDOM!.py"
      > "!PYSCRIPT!" echo import os, json
      >>"!PYSCRIPT!" echo from pathlib import Path
      >>"!PYSCRIPT!" echo import matplotlib
      >>"!PYSCRIPT!" echo matplotlib.use("Agg")
      >>"!PYSCRIPT!" echo import pandas as pd
      >>"!PYSCRIPT!" echo import matplotlib.pyplot as plt
      >>"!PYSCRIPT!" echo run_dir = Path(os.environ["RUN_DIR"])
      >>"!PYSCRIPT!" echo series_path = run_dir / "series" / "run.parquet"
      >>"!PYSCRIPT!" echo summary_path = run_dir / "summary.json"
      >>"!PYSCRIPT!" echo plots_dir = run_dir / "plots"
      >>"!PYSCRIPT!" echo plots_dir.mkdir(parents=True, exist_ok=True)
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo if not series_path.exists():
      >>"!PYSCRIPT!" echo ^^^print(f"[warn] series not found: {series_path}, skip plotting")
      >>"!PYSCRIPT!" echo ^^^raise SystemExit(0)
      >>"!PYSCRIPT!" echo series_cols = ["time","dt","M_out_dot","M_sink_dot","mass_lost_by_blowout","mass_lost_by_sinks","prod_subblow_area_rate","Sigma_surf","tau","t_blow","dt_over_t_blow"]
      >>"!PYSCRIPT!" echo df = pd.read_parquet(series_path, columns=[c for c in series_cols if c in pd.read_parquet(series_path).columns])
      >>"!PYSCRIPT!" echo fig, ax = plt.subplots(2,1,figsize=(8,6),sharex=True)
      >>"!PYSCRIPT!" echo if "M_out_dot" in df: ax[0].plot(df["time"]/3.15576e7, df["M_out_dot"], label="M_out_dot")
      >>"!PYSCRIPT!" echo if "M_sink_dot" in df: ax[0].plot(df["time"]/3.15576e7, df["M_sink_dot"], label="M_sink_dot")
      >>"!PYSCRIPT!" echo ax[0].set_ylabel("loss rate [M_Mars s^-1]"); ax[0].legend()
      >>"!PYSCRIPT!" echo if "prod_subblow_area_rate" in df: ax[1].plot(df["time"]/3.15576e7, df["prod_subblow_area_rate"], label="prod_subblow_area_rate")
      >>"!PYSCRIPT!" echo ax[1].set_xlabel("time [yr]"); ax[1].set_ylabel("prod_subblow [kg m^-2 s^-1]")
      >>"!PYSCRIPT!" echo fig.tight_layout(); fig.savefig(plots_dir/"quicklook.png")
      >>"!PYSCRIPT!" echo if summary_path.exists():
      >>"!PYSCRIPT!" echo ^^^with open(summary_path,"r",encoding="utf-8") as f: summary=json.load(f)
      >>"!PYSCRIPT!" echo ^^^with open(plots_dir/"summary.txt","w",encoding="utf-8") as f: json.dump(summary,f,indent=2)
      python "!PYSCRIPT!"
      del "!PYSCRIPT!"
    )
  )
)

endlocal
