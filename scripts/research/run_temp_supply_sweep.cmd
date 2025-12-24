@echo off
rem Windows CMD version of run_temp_supply_sweep.sh (logic preserved, output rooted under out/)
setlocal EnableExtensions EnableDelayedExpansion

rem Keep paths stable even if launched from another directory (double-click or direct call)
pushd "%~dp0\..\.."

rem Optional dry-run for syntax tests (skip all heavy work)
if /i "%~1"=="--dry-run" (
  echo.[dry-run] run_temp_supply_sweep.cmd syntax-only check; skipping execution.
  popd
  exit /b 0
)
if /i "%~1"=="--run-one" set "RUN_ONE_MODE=1"

rem ---------- setup ----------
if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
if not defined RUN_TS for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format \"yyyyMMdd-HHmmss\""') do set "RUN_TS=%%A"
if not defined GIT_SHA for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
if not defined GIT_SHA set "GIT_SHA=nogit"
if not defined BATCH_SEED for /f %%A in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set "BATCH_SEED=%%A"

rem Force output root to out/ as requested
if not defined BATCH_ROOT set "BATCH_ROOT=out"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep"
if not defined BATCH_DIR set "BATCH_DIR=%BATCH_ROOT%\%SWEEP_TAG%\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%"
echo.[setup] Output root: %BATCH_ROOT%
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.[setup] Creating virtual environment in %VENV_DIR%...
  python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

if "%SKIP_PIP%"=="1" (
  echo.[setup] SKIP_PIP=1; skipping dependency install.
) else if exist "%REQ_FILE%" (
  echo.[setup] Installing/upgrading dependencies from %REQ_FILE% ...
  python -m pip install --upgrade pip
  pip install -r "%REQ_FILE%"
) else (
  echo.[warn] %REQ_FILE% not found; skipping dependency install.
)

rem ---------- defaults ----------
rem Hard reset cooling params to avoid polluted values from previous shell commands
set "COOL_MODE="
set "COOL_TO_K="
set "COOL_MARGIN_YEARS="
set "COOL_SEARCH_YEARS="

if not defined BASE_CONFIG set "BASE_CONFIG=configs/sweep_temp_supply/temp_supply_T4000_eps1.yml"
if not defined QSTAR_UNITS set "QSTAR_UNITS=ba99_cgs"
if not defined GEOMETRY_MODE set "GEOMETRY_MODE=0D"
if not defined GEOMETRY_NR set "GEOMETRY_NR=32"
rem Cooling defaults (stop when Mars T_M reaches 1000 K, slab law unless overridden)
set "COOL_TO_K=1000"
if not defined COOL_MARGIN_YEARS set "COOL_MARGIN_YEARS=0"
if not defined COOL_SEARCH_YEARS set "COOL_SEARCH_YEARS="
set "COOL_MODE=slab"
if not defined EVAL set "EVAL=1"
if not defined SUBSTEP_FAST_BLOWOUT set "SUBSTEP_FAST_BLOWOUT=0"
if not defined SUBSTEP_MAX_RATIO set "SUBSTEP_MAX_RATIO="
if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=clip"
if not defined SUPPLY_MODE set "SUPPLY_MODE=const"
if not defined SUPPLY_MU_ORBIT10PCT set "SUPPLY_MU_ORBIT10PCT=1.0"
if not defined SUPPLY_MU_REFERENCE_TAU set "SUPPLY_MU_REFERENCE_TAU=1.0"
if not defined SUPPLY_ORBIT_FRACTION set "SUPPLY_ORBIT_FRACTION=0.10"
if not defined SHIELDING_MODE set "SHIELDING_MODE=off"
if not defined SHIELDING_SIGMA set "SHIELDING_SIGMA=auto"
if not defined SHIELDING_AUTO_MAX_MARGIN set "SHIELDING_AUTO_MAX_MARGIN=0.05"
if not defined OPTICAL_TAU0_TARGET set "OPTICAL_TAU0_TARGET=1.0"
if not defined OPTICAL_TAU_STOP set "OPTICAL_TAU_STOP=2.302585092994046"
if not defined OPTICAL_TAU_STOP_TOL set "OPTICAL_TAU_STOP_TOL=1.0e-6"
if not defined STOP_ON_BLOWOUT_BELOW_SMIN set "STOP_ON_BLOWOUT_BELOW_SMIN=true"
rem SUPPLY_RESERVOIR_M intentionally left undefined by default
if not defined SUPPLY_RESERVOIR_MODE set "SUPPLY_RESERVOIR_MODE=hard_stop"
if not defined SUPPLY_RESERVOIR_TAPER set "SUPPLY_RESERVOIR_TAPER=0.05"
if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"
if not defined SUPPLY_FEEDBACK_TARGET set "SUPPLY_FEEDBACK_TARGET=1.0"
if not defined SUPPLY_FEEDBACK_GAIN set "SUPPLY_FEEDBACK_GAIN=1.0"
if not defined SUPPLY_FEEDBACK_RESPONSE_YR set "SUPPLY_FEEDBACK_RESPONSE_YR=0.5"
if not defined SUPPLY_FEEDBACK_MIN_SCALE set "SUPPLY_FEEDBACK_MIN_SCALE=0.0"
if not defined SUPPLY_FEEDBACK_MAX_SCALE set "SUPPLY_FEEDBACK_MAX_SCALE=10.0"
if not defined SUPPLY_FEEDBACK_TAU_FIELD set "SUPPLY_FEEDBACK_TAU_FIELD=tau_los"
if not defined SUPPLY_FEEDBACK_INITIAL set "SUPPLY_FEEDBACK_INITIAL=1.0"
if not defined SUPPLY_TEMP_ENABLED set "SUPPLY_TEMP_ENABLED=0"
if not defined SUPPLY_TEMP_MODE set "SUPPLY_TEMP_MODE=scale"
if not defined SUPPLY_TEMP_REF_K set "SUPPLY_TEMP_REF_K=1800.0"
if not defined SUPPLY_TEMP_EXP set "SUPPLY_TEMP_EXP=1.0"
if not defined SUPPLY_TEMP_SCALE_REF set "SUPPLY_TEMP_SCALE_REF=1.0"
if not defined SUPPLY_TEMP_FLOOR set "SUPPLY_TEMP_FLOOR=0.0"
if not defined SUPPLY_TEMP_CAP set "SUPPLY_TEMP_CAP=10.0"
rem SUPPLY_TEMP_TABLE_PATH intentionally left undefined by default
if not defined SUPPLY_TEMP_TABLE_VALUE_KIND set "SUPPLY_TEMP_TABLE_VALUE_KIND=scale"
if not defined SUPPLY_TEMP_TABLE_COL_T set "SUPPLY_TEMP_TABLE_COL_T=T_K"
if not defined SUPPLY_TEMP_TABLE_COL_VAL set "SUPPLY_TEMP_TABLE_COL_VAL=value"
if not defined SUPPLY_INJECTION_MODE set "SUPPLY_INJECTION_MODE=powerlaw_bins"
if not defined SUPPLY_INJECTION_Q set "SUPPLY_INJECTION_Q=3.5"
rem SUPPLY_INJECTION_SMIN intentionally left undefined by default
rem SUPPLY_INJECTION_SMAX intentionally left undefined by default
rem SUPPLY_DEEP_TMIX_ORBITS intentionally left undefined by default
if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=deep_mixing"
if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=50"
if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=soft"
if not defined SUPPLY_VEL_MODE set "SUPPLY_VEL_MODE=inherit"
if not defined SUPPLY_VEL_E set "SUPPLY_VEL_E=0.05"
if not defined SUPPLY_VEL_I set "SUPPLY_VEL_I=0.025"
rem SUPPLY_VEL_FACTOR intentionally left undefined by default
if not defined SUPPLY_VEL_BLEND set "SUPPLY_VEL_BLEND=rms"
if not defined SUPPLY_VEL_WEIGHT set "SUPPLY_VEL_WEIGHT=delta_sigma"
rem STREAM_MEM_GB intentionally left undefined by default
rem STREAM_STEP_INTERVAL intentionally left undefined by default
if not defined ENABLE_PROGRESS set "ENABLE_PROGRESS=1"
if not defined AUTO_JOBS set "AUTO_JOBS=0"
if not defined PARALLEL_JOBS set "PARALLEL_JOBS="
if not defined JOB_MEM_GB set "JOB_MEM_GB=10"
if not defined MEM_RESERVE_GB set "MEM_RESERVE_GB=4"
if not defined PARALLEL_SLEEP_SEC set "PARALLEL_SLEEP_SEC=2"

if /i "%SUPPLY_HEADROOM_POLICY%"=="none" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_HEADROOM_POLICY%"=="off" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="none" set "SUPPLY_TRANSPORT_TMIX_ORBITS="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="off" set "SUPPLY_TRANSPORT_TMIX_ORBITS="

set "T_LIST=5000 4000 3000"
set "EPS_LIST=1.0 0.5 0.1"
set "TAU_LIST=1.0 0.5 0.1"

set "COOL_SEARCH_DISPLAY=%COOL_SEARCH_YEARS%"
if not defined COOL_SEARCH_DISPLAY set "COOL_SEARCH_DISPLAY=none"

set "COOL_STATUS="
if defined COOL_TO_K (
  set "COOL_STATUS=dynamic horizon: stop when Mars T_M reaches !COOL_TO_K! K (margin !COOL_MARGIN_YEARS! yr, search_cap=!COOL_SEARCH_DISPLAY!)"
) else (
  set "COOL_STATUS=dynamic horizon disabled (using numerics.t_end_* from config)"
)

set "TOTAL_GB="
set "CPU_LOGICAL="
if "%AUTO_JOBS%"=="1" (
  for /f %%A in ('powershell -NoProfile -Command "$mem=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; [math]::Floor($mem/1GB)"') do set "TOTAL_GB=%%A"
  for /f %%A in ('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Sum -Property NumberOfLogicalProcessors).Sum"') do set "CPU_LOGICAL=%%A"
  if not defined CPU_LOGICAL for /f %%A in ('powershell -NoProfile -Command "[Environment]::ProcessorCount"') do set "CPU_LOGICAL=%%A"
  if not defined PARALLEL_JOBS (
    for /f %%A in ('powershell -NoProfile -Command "$total=[double]$env:TOTAL_GB; $reserve=[double]$env:MEM_RESERVE_GB; $job=[double]$env:JOB_MEM_GB; if (-not $job -or $job -le 0){$job=10}; if (-not $total -or $total -le 0){$total=0}; $avail=[math]::Max($total-$reserve,1); $memJobs=[math]::Max([math]::Floor($avail/$job),1); $cpu=[int]$env:CPU_LOGICAL; if ($cpu -lt 1){$cpu=[Environment]::ProcessorCount}; [int]([math]::Max([math]::Min($cpu,$memJobs),1))"') do set "PARALLEL_JOBS=%%A"
  )
  if not defined STREAM_MEM_GB set "STREAM_MEM_GB=%JOB_MEM_GB%"
)
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if "%PARALLEL_JOBS%"=="0" set "PARALLEL_JOBS=1"
if "%AUTO_JOBS%"=="1" (
  if not defined TOTAL_GB set "TOTAL_GB=unknown"
  if not defined CPU_LOGICAL set "CPU_LOGICAL=unknown"
  echo.[sys] mem_total_gb=%TOTAL_GB% cpu_logical=%CPU_LOGICAL% job_mem_gb=%JOB_MEM_GB% parallel_jobs=%PARALLEL_JOBS%
)

echo.[config] supply multipliers: temp_enabled=%SUPPLY_TEMP_ENABLED% (mode=%SUPPLY_TEMP_MODE%) feedback_enabled=%SUPPLY_FEEDBACK_ENABLED% reservoir=%SUPPLY_RESERVOIR_M%
echo.[config] shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
echo.[config] injection: mode=%SUPPLY_INJECTION_MODE% q=%SUPPLY_INJECTION_Q% s_inj_min=%SUPPLY_INJECTION_SMIN% s_inj_max=%SUPPLY_INJECTION_SMAX%
echo.[config] transport: mode=%SUPPLY_TRANSPORT_MODE% t_mix=%SUPPLY_TRANSPORT_TMIX_ORBITS% headroom_gate=%SUPPLY_TRANSPORT_HEADROOM% velocity=%SUPPLY_VEL_MODE%
echo.[config] geometry: mode=%GEOMETRY_MODE% Nr=%GEOMETRY_NR% r_in_m=%GEOMETRY_R_IN_M% r_out_m=%GEOMETRY_R_OUT_M%
echo.[config] external supply: mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% mu_reference_tau=%SUPPLY_MU_REFERENCE_TAU% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION% (epsilon_mix swept per EPS_LIST)
echo.[config] optical_depth: tau0_target_list=%TAU_LIST% tau_stop=%OPTICAL_TAU_STOP% tau_stop_tol=%OPTICAL_TAU_STOP_TOL%
echo.[config] fast blowout substep: enabled=%SUBSTEP_FAST_BLOWOUT% substep_max_ratio=%SUBSTEP_MAX_RATIO%
echo.[config] !COOL_STATUS!
echo.[config] cooling driver mode: %COOL_MODE% (slab: T^-3, hyodo: linear flux)

set "PROGRESS_FLAG="
if "%ENABLE_PROGRESS%"=="1" set "PROGRESS_FLAG=--progress"

rem Build streaming overrides (keep branching minimal to avoid cmd.exe parse quirks)
set "STREAMING_OVERRIDES="
if defined STREAM_MEM_GB set "STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.memory_limit_gb=%STREAM_MEM_GB%"
if defined STREAM_STEP_INTERVAL set "STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.step_flush_interval=%STREAM_STEP_INTERVAL%"
if defined STREAM_MEM_GB echo.[info] override io.streaming.memory_limit_gb=%STREAM_MEM_GB%
if defined STREAM_STEP_INTERVAL echo.[info] override io.streaming.step_flush_interval=%STREAM_STEP_INTERVAL%
set "SUPPLY_OVERRIDES="
if not defined SUPPLY_RESERVOIR_M goto :skip_reservoir
set "SUPPLY_OVERRIDES=--override \"supply.reservoir.enabled=true\" --override \"supply.reservoir.mass_total_Mmars=%SUPPLY_RESERVOIR_M%\" --override \"supply.reservoir.depletion_mode=%SUPPLY_RESERVOIR_MODE%\" --override \"supply.reservoir.taper_fraction=%SUPPLY_RESERVOIR_TAPER%\""
echo.[info] supply reservoir: M=%SUPPLY_RESERVOIR_M% M_Mars mode=%SUPPLY_RESERVOIR_MODE% taper_fraction=%SUPPLY_RESERVOIR_TAPER%
:skip_reservoir
if "%SUPPLY_FEEDBACK_ENABLED%"=="0" goto :skip_feedback
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.feedback.enabled=true\" --override \"supply.feedback.target_tau=%SUPPLY_FEEDBACK_TARGET%\" --override \"supply.feedback.gain=%SUPPLY_FEEDBACK_GAIN%\" --override \"supply.feedback.response_time_years=%SUPPLY_FEEDBACK_RESPONSE_YR%\" --override \"supply.feedback.min_scale=%SUPPLY_FEEDBACK_MIN_SCALE%\" --override \"supply.feedback.max_scale=%SUPPLY_FEEDBACK_MAX_SCALE%\" --override \"supply.feedback.tau_field=%SUPPLY_FEEDBACK_TAU_FIELD%\" --override \"supply.feedback.initial_scale=%SUPPLY_FEEDBACK_INITIAL%\""
echo.[info] supply feedback enabled: target_tau=%SUPPLY_FEEDBACK_TARGET%, gain=%SUPPLY_FEEDBACK_GAIN%, tau_field=%SUPPLY_FEEDBACK_TAU_FIELD%
:skip_feedback
if "%SUPPLY_TEMP_ENABLED%"=="0" goto :skip_temp
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.temperature.enabled=true\" --override \"supply.temperature.mode=%SUPPLY_TEMP_MODE%\" --override \"supply.temperature.reference_K=%SUPPLY_TEMP_REF_K%\" --override \"supply.temperature.exponent=%SUPPLY_TEMP_EXP%\" --override \"supply.temperature.scale_at_reference=%SUPPLY_TEMP_SCALE_REF%\" --override \"supply.temperature.floor=%SUPPLY_TEMP_FLOOR%\" --override \"supply.temperature.cap=%SUPPLY_TEMP_CAP%\""
if not defined SUPPLY_TEMP_TABLE_PATH goto :skip_temp_table
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.temperature.table.path=%SUPPLY_TEMP_TABLE_PATH%\" --override \"supply.temperature.table.value_kind=%SUPPLY_TEMP_TABLE_VALUE_KIND%\" --override \"supply.temperature.table.column_temperature=%SUPPLY_TEMP_TABLE_COL_T%\" --override \"supply.temperature.table.column_value=%SUPPLY_TEMP_TABLE_COL_VAL%\""
:skip_temp_table
echo.[info] supply temperature coupling enabled: mode=%SUPPLY_TEMP_MODE%
:skip_temp
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.mode=%SUPPLY_INJECTION_MODE%\" --override \"supply.injection.q=%SUPPLY_INJECTION_Q%\""
if defined SUPPLY_INJECTION_SMIN set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.s_inj_min=%SUPPLY_INJECTION_SMIN%\""
if defined SUPPLY_INJECTION_SMAX set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.s_inj_max=%SUPPLY_INJECTION_SMAX%\""
if not defined SUPPLY_DEEP_TMIX_ORBITS goto :skip_deep_tmix
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.t_mix_orbits=%SUPPLY_DEEP_TMIX_ORBITS%\" --override \"supply.transport.mode=deep_mixing\""
echo.[info] deep reservoir enabled (legacy alias): t_mix=%SUPPLY_DEEP_TMIX_ORBITS% orbits
:skip_deep_tmix
if defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.t_mix_orbits=%SUPPLY_TRANSPORT_TMIX_ORBITS%\""
if defined SUPPLY_TRANSPORT_MODE set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.mode=%SUPPLY_TRANSPORT_MODE%\""
if defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.transport.headroom_gate=%SUPPLY_TRANSPORT_HEADROOM%\""
if defined SUPPLY_HEADROOM_POLICY set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.headroom_policy=%SUPPLY_HEADROOM_POLICY%\""
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.mode=%SUPPLY_VEL_MODE%\""
if defined SUPPLY_VEL_E set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.e_inj=%SUPPLY_VEL_E%\""
if defined SUPPLY_VEL_I set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.i_inj=%SUPPLY_VEL_I%\""
if defined SUPPLY_VEL_FACTOR set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.vrel_factor=%SUPPLY_VEL_FACTOR%\""
set "SUPPLY_OVERRIDES=!SUPPLY_OVERRIDES! --override \"supply.injection.velocity.blend_mode=%SUPPLY_VEL_BLEND%\" --override \"supply.injection.velocity.weight_mode=%SUPPLY_VEL_WEIGHT%\""

if defined RUN_ONE_MODE (
  if not defined RUN_ONE_T (
    echo.[error] RUN_ONE_T is required for --run-one
    popd
    exit /b 1
  )
  if not defined RUN_ONE_EPS (
    echo.[error] RUN_ONE_EPS is required for --run-one
    popd
    exit /b 1
  )
  if not defined RUN_ONE_TAU (
    echo.[error] RUN_ONE_TAU is required for --run-one
    popd
    exit /b 1
  )
  set "T_LIST=%RUN_ONE_T%"
  set "EPS_LIST=%RUN_ONE_EPS%"
  set "TAU_LIST=%RUN_ONE_TAU%"
  if defined RUN_ONE_SEED set "SEED_OVERRIDE=%RUN_ONE_SEED%"
  set "PARALLEL_JOBS=1"
  set "AUTO_JOBS=0"
  echo.[info] run-one mode: T=%RUN_ONE_T% eps=%RUN_ONE_EPS% tau=%RUN_ONE_TAU% seed=%RUN_ONE_SEED%
)

if %PARALLEL_JOBS% GTR 1 (
  if not defined RUN_ONE_MODE (
    call :run_parallel
    popd
    endlocal
    exit /b 0
  )
)

rem ---------- main loops ----------
for %%T in (%T_LIST%) do (
  set "T_TABLE=data/mars_temperature_T%%Tp0K.csv"
  for %%M in (%EPS_LIST%) do (
    set "EPS=%%M"
    set "EPS_TITLE=%%M"
    set "EPS_TITLE=!EPS_TITLE:0.=0p!"
    set "EPS_TITLE=!EPS_TITLE:.=p!"
    for %%U in (%TAU_LIST%) do (
      set "TAU=%%U"
      set "TAU_TITLE=!TAU!"
      set "TAU_TITLE=!TAU_TITLE:0.=0p!"
      set "TAU_TITLE=!TAU_TITLE:.=p!"
      if defined SEED_OVERRIDE (
        set "SEED=%SEED_OVERRIDE%"
      ) else (
        for /f %%S in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set "SEED=%%S"
      )
      set "TITLE=T%%T_eps!EPS_TITLE!_tau!TAU_TITLE!"
      set "OUTDIR=%BATCH_DIR%\!TITLE!"
      echo.[run] T=%%T eps=%%M tau=%%U -^> !OUTDIR! (batch=%BATCH_SEED%, seed=!SEED!)
      rem Show supply rate info (skip Python calc to avoid cmd.exe delayed expansion issues)
      echo.[info] epsilon_mix=%%M; mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION%
      echo.[info] shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
      if "%%M"=="0.1" echo.[info] epsilon_mix=0.1 is a low-supply extreme case; expect weak blowout/sinks

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

      rem Assemble the run command on a single line (avoid carets in optional blocks)
      set RUN_CMD=python -m marsdisk.run --config "%BASE_CONFIG%" --quiet
      if "%ENABLE_PROGRESS%"=="1" set RUN_CMD=!RUN_CMD! --progress
      set RUN_CMD=!RUN_CMD! --override numerics.dt_init=2
      set RUN_CMD=!RUN_CMD! --override "numerics.stop_on_blowout_below_smin=%STOP_ON_BLOWOUT_BELOW_SMIN%"
      set RUN_CMD=!RUN_CMD! --override "io.outdir=!OUTDIR!"
      set RUN_CMD=!RUN_CMD! --override "dynamics.rng_seed=!SEED!"
      set RUN_CMD=!RUN_CMD! --override "phase.enabled=true"
      if /i "!GEOMETRY_MODE!"=="1D" (
        set RUN_CMD=!RUN_CMD! --override "geometry.mode=1D"
        set RUN_CMD=!RUN_CMD! --override "geometry.Nr=!GEOMETRY_NR!"
        if defined GEOMETRY_R_IN_M set RUN_CMD=!RUN_CMD! --override "geometry.r_in=!GEOMETRY_R_IN_M!"
        if defined GEOMETRY_R_OUT_M set RUN_CMD=!RUN_CMD! --override "geometry.r_out=!GEOMETRY_R_OUT_M!"
      )
      set RUN_CMD=!RUN_CMD! --override "radiation.TM_K=%%T"
      set RUN_CMD=!RUN_CMD! --override "qstar.coeff_units=%QSTAR_UNITS%"
      set RUN_CMD=!RUN_CMD! --override "radiation.qpr_table_path=marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv"
      set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.enabled=true"
      if "%COOL_MODE%"=="hyodo" (
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.mode=hyodo"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.hyodo.d_layer_m=1.0e5"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.hyodo.rho=3000"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.hyodo.cp=1000"
      ) else (
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.mode=table"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.table.path=!T_TABLE!"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.table.time_unit=day"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.table.column_time=time_day"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.table.column_temperature=T_K"
        set RUN_CMD=!RUN_CMD! --override "radiation.mars_temperature_driver.extrapolation=hold"
      )
      set RUN_CMD=!RUN_CMD! --override "supply.enabled=true"
      set RUN_CMD=!RUN_CMD! --override "supply.mixing.epsilon_mix=%%M"
      set RUN_CMD=!RUN_CMD! --override "supply.mode=%SUPPLY_MODE%"
      set RUN_CMD=!RUN_CMD! --override "supply.const.mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT%"
      set RUN_CMD=!RUN_CMD! --override "supply.const.mu_reference_tau=%SUPPLY_MU_REFERENCE_TAU%"
      set RUN_CMD=!RUN_CMD! --override "supply.const.orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION%"
      set RUN_CMD=!RUN_CMD! --override "optical_depth.tau0_target=!TAU!"
      set RUN_CMD=!RUN_CMD! --override "optical_depth.tau_stop=%OPTICAL_TAU_STOP%"
      set RUN_CMD=!RUN_CMD! --override "optical_depth.tau_stop_tol=%OPTICAL_TAU_STOP_TOL%"
      set RUN_CMD=!RUN_CMD! --override "shielding.mode=%SHIELDING_MODE%"
      set RUN_CMD=!RUN_CMD! !SUPPLY_OVERRIDES!
      if defined STREAMING_OVERRIDES set RUN_CMD=!RUN_CMD! !STREAMING_OVERRIDES!
      if defined CMD_EXTRA set RUN_CMD=!RUN_CMD! !CMD_EXTRA!

      !RUN_CMD!

      if errorlevel 1 (
        echo.[warn] run command exited with status !errorlevel!; attempting plots anyway
      )

      set "RUN_DIR=!OUTDIR!"
      set "PYSCRIPT=%TEMP%\run_temp_supply_plot_!RANDOM!.py"
      > "!PYSCRIPT!" echo # -*- coding: utf-8 -*-
      >>"!PYSCRIPT!" echo import os, json
      >>"!PYSCRIPT!" echo from pathlib import Path
      >>"!PYSCRIPT!" echo import matplotlib
      >>"!PYSCRIPT!" echo matplotlib.use("Agg")
      >>"!PYSCRIPT!" echo import pandas as pd
      >>"!PYSCRIPT!" echo import matplotlib.pyplot as plt
      >>"!PYSCRIPT!" echo SEC_PER_YEAR = 3.15576e7
      >>"!PYSCRIPT!" echo run_dir = Path(os.environ["RUN_DIR"])
      >>"!PYSCRIPT!" echo series_dir = run_dir / "series"
      >>"!PYSCRIPT!" echo series_path = series_dir / "run.parquet"
      >>"!PYSCRIPT!" echo summary_path = run_dir / "summary.json"
      >>"!PYSCRIPT!" echo plots_dir = run_dir / "plots"
      >>"!PYSCRIPT!" echo plots_dir.mkdir(parents=True, exist_ok=True)
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo series_cols = [
      >>"!PYSCRIPT!" echo     "time","dt","M_out_dot","M_sink_dot","mass_lost_by_blowout","mass_lost_by_sinks",
      >>"!PYSCRIPT!" echo     "mass_total_bins","prod_subblow_area_rate","Sigma_surf","sigma_surf",
      >>"!PYSCRIPT!" echo     "tau","tau_los_mars","tau_eff","t_blow","dt_over_t_blow"
      >>"!PYSCRIPT!" echo ]
      >>"!PYSCRIPT!" echo def load_series():
      >>"!PYSCRIPT!" echo     if series_path.exists():
      >>"!PYSCRIPT!" echo         cols = [c for c in series_cols if c in pd.read_parquet(series_path).columns]
      >>"!PYSCRIPT!" echo         return pd.read_parquet(series_path, columns=cols)
      >>"!PYSCRIPT!" echo     chunk_paths = sorted(series_dir.glob("run_chunk_*.parquet"))
      >>"!PYSCRIPT!" echo     if not chunk_paths:
      >>"!PYSCRIPT!" echo         print(f"[warn] series not found: {series_dir}, skip plotting")
      >>"!PYSCRIPT!" echo         return None
      >>"!PYSCRIPT!" echo     first_cols = pd.read_parquet(chunk_paths[0]).columns
      >>"!PYSCRIPT!" echo     cols = [c for c in series_cols if c in first_cols]
      >>"!PYSCRIPT!" echo     frames = [pd.read_parquet(p, columns=cols) for p in chunk_paths]
      >>"!PYSCRIPT!" echo     return pd.concat(frames, ignore_index=True)
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo df = load_series()
      >>"!PYSCRIPT!" echo if df is None:
      >>"!PYSCRIPT!" echo     raise SystemExit(0)
      >>"!PYSCRIPT!" echo if "time" in df.columns:
      >>"!PYSCRIPT!" echo     df = df.sort_values("time")
      >>"!PYSCRIPT!" echo     years = df["time"] / SEC_PER_YEAR
      >>"!PYSCRIPT!" echo else:
      >>"!PYSCRIPT!" echo     years = None
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo fig, axes = plt.subplots(3,1,figsize=(10,8),sharex=True)
      >>"!PYSCRIPT!" echo ax_rates, ax_cum, ax_tau = axes
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo # loss rates
      >>"!PYSCRIPT!" echo for col in ("M_out_dot","M_sink_dot"):
      >>"!PYSCRIPT!" echo     if col in df:
      >>"!PYSCRIPT!" echo         ax_rates.plot(years, df[col], label=col)
      >>"!PYSCRIPT!" echo ax_rates.set_ylabel("loss rate [M_Mars s^-1]")
      >>"!PYSCRIPT!" echo vals = pd.concat([df[c].dropna() for c in ("M_out_dot","M_sink_dot") if c in df])
      >>"!PYSCRIPT!" echo if len(vals) and vals.min() > 0:
      >>"!PYSCRIPT!" echo     ax_rates.set_yscale("log")
      >>"!PYSCRIPT!" echo ax_rates.legend()
      >>"!PYSCRIPT!" echo ax_rates.grid(True, alpha=0.3)
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo # cumulative masses
      >>"!PYSCRIPT!" echo for col in ("mass_lost_by_blowout","mass_lost_by_sinks","mass_total_bins"):
      >>"!PYSCRIPT!" echo     if col in df:
      >>"!PYSCRIPT!" echo         ax_cum.plot(years, df[col], label=col)
      >>"!PYSCRIPT!" echo ax_cum.set_ylabel("mass [M_Mars]")
      >>"!PYSCRIPT!" echo ax_cum.legend()
      >>"!PYSCRIPT!" echo ax_cum.grid(True, alpha=0.3)
      >>"!PYSCRIPT!" echo
      >>"!PYSCRIPT!" echo # tau and supply
      >>"!PYSCRIPT!" echo if "tau_los_mars" in df:
      >>"!PYSCRIPT!" echo     ax_tau.plot(years, df["tau_los_mars"], label="tau_los_mars", color="tab:blue")
      >>"!PYSCRIPT!" echo if "tau_eff" in df:
      >>"!PYSCRIPT!" echo     ax_tau.plot(years, df["tau_eff"], label="tau_eff", color="tab:cyan")
      >>"!PYSCRIPT!" echo ax_tau.set_ylabel("tau")
      >>"!PYSCRIPT!" echo ax_tau.grid(True, alpha=0.3)
      >>"!PYSCRIPT!" echo ax_supply = ax_tau.twinx()
      >>"!PYSCRIPT!" echo if "prod_subblow_area_rate" in df:
      >>"!PYSCRIPT!" echo     ax_supply.plot(years, df["prod_subblow_area_rate"], label="prod_subblow_area_rate", color="tab:orange")
      >>"!PYSCRIPT!" echo ax_supply.set_ylabel("prod_subblow [kg m^-2 s^-1]")
      >>"!PYSCRIPT!" echo handles, labels = ax_tau.get_legend_handles_labels()
      >>"!PYSCRIPT!" echo h2, l2 = ax_supply.get_legend_handles_labels()
      >>"!PYSCRIPT!" echo ax_tau.legend(handles + h2, labels + l2, loc="upper right")
      >>"!PYSCRIPT!" echo axes[-1].set_xlabel("time [yr]")
      >>"!PYSCRIPT!" echo fig.tight_layout()
      >>"!PYSCRIPT!" echo fig.savefig(plots_dir/"quicklook.png")
      >>"!PYSCRIPT!" echo if summary_path.exists():
      >>"!PYSCRIPT!" echo     with open(summary_path,"r",encoding="utf-8") as f: summary=json.load(f)
      >>"!PYSCRIPT!" echo     with open(plots_dir/"summary.txt","w",encoding="utf-8") as f: json.dump(summary,f,indent=2)
      python "!PYSCRIPT!"
      del "!PYSCRIPT!"
    )
  )
)

popd
endlocal
exit /b %errorlevel%

:run_parallel
set "JOB_PIDS="
set "JOB_COUNT=0"
set "LAUNCHER_PS=%TEMP%\marsdisk_launch_job_%RUN_TS%_%BATCH_SEED%.ps1"
> "%LAUNCHER_PS%" echo $cmd = $env:JOB_CMD
>>"%LAUNCHER_PS%" echo if (-not $cmd) { exit 2 }
>>"%LAUNCHER_PS%" echo $p = Start-Process cmd.exe -ArgumentList '/c', $cmd -PassThru
>>"%LAUNCHER_PS%" echo $p.Id
echo.[info] parallel mode: jobs=%PARALLEL_JOBS% sleep=%PARALLEL_SLEEP_SEC%s

for %%T in (%T_LIST%) do (
  for %%M in (%EPS_LIST%) do (
    for %%U in (%TAU_LIST%) do (
      call :launch_job %%T %%M %%U
    )
  )
)

call :wait_all
if exist "%LAUNCHER_PS%" del "%LAUNCHER_PS%"
echo.[done] Parallel sweep completed (batch=%BATCH_SEED%, dir=%BATCH_DIR%).
exit /b 0

:launch_job
set "JOB_T=%~1"
set "JOB_EPS=%~2"
set "JOB_TAU=%~3"
for /f %%S in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set "JOB_SEED=%%S"
call :wait_for_slot
set "JOB_PID="
set "JOB_CMD=set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& set AUTO_JOBS=0&& set PARALLEL_JOBS=1&& set SKIP_PIP=1&& call ""%~f0"" --run-one"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_PS%"`) do set "JOB_PID=%%P"
if defined JOB_PID set "JOB_PIDS=!JOB_PIDS! !JOB_PID!"
if not defined JOB_PID echo.[warn] failed to launch job for T=!JOB_T! eps=!JOB_EPS! tau=!JOB_TAU! (check PowerShell availability)
exit /b 0

:wait_for_slot
call :refresh_jobs
if %JOB_COUNT% GEQ %PARALLEL_JOBS% (
  timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
  goto :wait_for_slot
)
exit /b 0

:refresh_jobs
set "JOB_COUNT=0"
if not defined JOB_PIDS exit /b 0
for /f "usebackq tokens=1,2 delims=|" %%A in (`powershell -NoProfile -Command "$ids=$env:JOB_PIDS -split ' ' | Where-Object {$_}; $alive=@(); foreach($id in $ids){ if (Get-Process -Id $id -ErrorAction SilentlyContinue){$alive += $id}}; $list=($alive -join ' '); if (-not $list){$list='__NONE__'}; Write-Output ($list + '|' + $alive.Count)"`) do (
  set "JOB_PIDS=%%A"
  set "JOB_COUNT=%%B"
)
if "%JOB_PIDS%"=="__NONE__" set "JOB_PIDS="
exit /b 0

:wait_all
call :refresh_jobs
if "%JOB_COUNT%"=="0" exit /b 0
timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
goto :wait_all
