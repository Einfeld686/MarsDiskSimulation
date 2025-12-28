@echo off
rem Windows CMD version of run_temp_supply_sweep.sh (logic preserved, output rooted under out/)
setlocal EnableExtensions EnableDelayedExpansion

if not defined TRACE_ENABLED set "TRACE_ENABLED=1"
if not defined TRACE_ECHO set "TRACE_ECHO=0"
set "SCRIPT_REV=run_temp_supply_sweep_cmd_trace_v2"

rem Keep paths stable even if launched from another directory (double-click or direct call)
pushd "%~dp0\..\.."

rem Optional dry-run for syntax tests (skip all heavy work)
if /i "%~1"=="--dry-run" (
  echo.[dry-run] run_temp_supply_sweep.cmd syntax-only check; skipping execution.
  popd
  exit /b 0
)
if /i "%~1"=="--run-one" set "RUN_ONE_MODE=1"
echo.[setup] script_path=%~f0
echo.[setup] cwd=%CD%

rem ---------- setup ----------
if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
if not defined RUN_TS for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format \"yyyyMMdd-HHmmss\""') do set "RUN_TS=%%A"
if defined RUN_TS (
  set "RUN_TS_RAW=!RUN_TS!"
  rem Normalize to a filename-safe token in case a pre-set RUN_TS includes separators.
  set "RUN_TS=!RUN_TS::=!"
  set "RUN_TS=!RUN_TS: =_!"
  set "RUN_TS=!RUN_TS:/=-!"
  set "RUN_TS=!RUN_TS:\=-!"
  if not "!RUN_TS!"=="!RUN_TS_RAW!" echo.[warn] RUN_TS sanitized: "!RUN_TS_RAW!" -> "!RUN_TS!"
)
set "TMP_ROOT=%TEMP%"
set "TMP_SOURCE=TEMP"
if "%TMP_ROOT%"=="" (
  set "TMP_ROOT=%CD%\tmp"
  set "TMP_SOURCE=fallback"
)
if not exist "%TMP_ROOT%" mkdir "%TMP_ROOT%" >nul 2>&1
if not exist "%TMP_ROOT%" (
  set "TMP_ROOT=%CD%\tmp"
  set "TMP_SOURCE=fallback"
  if not exist "%TMP_ROOT%" mkdir "%TMP_ROOT%" >nul 2>&1
)
if not exist "%TMP_ROOT%" (
  echo.[error] temp_root unavailable: "%TMP_ROOT%"
  popd
  exit /b 1
)
echo.[setup] temp_root=%TMP_ROOT% (source=%TMP_SOURCE%)
if not defined GIT_SHA for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
if not defined GIT_SHA set "GIT_SHA=nogit"
if not defined BATCH_SEED for /f %%A in ('python scripts\\runsets\\common\\next_seed.py') do set "BATCH_SEED=%%A"
if "%BATCH_SEED%"=="" set "BATCH_SEED=0"
if "%TRACE_ENABLED%"=="1" (
  if not defined TRACE_LOG set "TRACE_LOG=%TMP_ROOT%\\marsdisk_trace_%RUN_TS%_%BATCH_SEED%.log"
  > "%TRACE_LOG%" echo.[trace] start script=%~f0 rev=%SCRIPT_REV%
  echo.[trace] log=%TRACE_LOG%
)
if "%TRACE_ECHO%"=="1" (
  echo.[trace] echo-on enabled
  echo on
)
call :trace "setup: env ready"
set "TMP_TEST=%TMP_ROOT%\\marsdisk_tmp_test_%RUN_TS%_%BATCH_SEED%.txt"
> "%TMP_TEST%" echo ok
if not exist "%TMP_TEST%" (
  echo.[error] temp_root write test failed: "%TMP_TEST%"
  echo.[error] temp_root=%TMP_ROOT%
  popd
  exit /b 1
)
del "%TMP_TEST%"

rem Force output root to out/ as requested
if not defined BATCH_ROOT set "BATCH_ROOT=E:\marsdisk_runs"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep"
echo.[setup] Output root: %BATCH_ROOT%

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
if not defined PLOT_ENABLE set "PLOT_ENABLE=1"
if not defined HOOKS_STRICT set "HOOKS_STRICT=0"
if defined HOOKS_ENABLE (
  for %%H in (%HOOKS_ENABLE:,= %) do (
    if /i "%%H"=="plot" set "PLOT_ENABLE=0"
  )
)
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
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if not defined JOB_MEM_GB set "JOB_MEM_GB=10"
if not defined SWEEP_PARALLEL set "SWEEP_PARALLEL=0"
if not defined MARSDISK_CELL_PARALLEL set "MARSDISK_CELL_PARALLEL=1"
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
if not defined CELL_MEM_FRACTION set "CELL_MEM_FRACTION=0.7"
if not defined MARSDISK_CELL_JOBS set "MARSDISK_CELL_JOBS=auto"
set "CELL_JOBS_RAW=%MARSDISK_CELL_JOBS%"
if /i "%MARSDISK_CELL_JOBS%"=="auto" (
  set "CELL_CPU_LOGICAL="
  set "CELL_MEM_TOTAL_GB="
  set "CELL_MEM_FRACTION_USED="
  for /f "usebackq tokens=1-4 delims=|" %%A in (`powershell -NoProfile -Command "$fraction=[double]$env:CELL_MEM_FRACTION; if ($fraction -le 0 -or $fraction -gt 1){$fraction=0.7}; $mem=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; $total=[math]::Floor($mem/1GB); $cpu=(Get-CimInstance Win32_Processor | Measure-Object -Sum -Property NumberOfLogicalProcessors).Sum; if (-not $cpu -or $cpu -lt 1){$cpu=[Environment]::ProcessorCount}; if ($cpu -lt 1){$cpu=1}; $jobs=[int]([math]::Max([math]::Floor($cpu*$fraction),1)); Write-Output (\"$total|$cpu|$fraction|$jobs\")"`) do (
    set "CELL_MEM_TOTAL_GB=%%A"
    set "CELL_CPU_LOGICAL=%%B"
    set "CELL_MEM_FRACTION_USED=%%C"
    set "MARSDISK_CELL_JOBS=%%D"
  )
  if not defined MARSDISK_CELL_JOBS set "MARSDISK_CELL_JOBS=1"
  if not defined CELL_MEM_FRACTION_USED set "CELL_MEM_FRACTION_USED=%CELL_MEM_FRACTION%"
  if not defined STREAM_MEM_GB (
    if defined CELL_MEM_TOTAL_GB (
      if not "!CELL_MEM_TOTAL_GB!"=="0" (
        for /f %%A in ('powershell -NoProfile -Command "$total=[double]$env:CELL_MEM_TOTAL_GB; $fraction=[double]$env:CELL_MEM_FRACTION_USED; if ($fraction -le 0 -or $fraction -gt 1){$fraction=0.7}; [math]::Max([math]::Floor($total*$fraction),1)"') do set "STREAM_MEM_GB=%%A"
      )
    )
  )
  echo.[sys] cell_parallel auto: mem_total_gb=!CELL_MEM_TOTAL_GB! mem_fraction=!CELL_MEM_FRACTION_USED! cpu_logical=!CELL_CPU_LOGICAL! cell_jobs=!MARSDISK_CELL_JOBS!
)
set "CELL_JOBS_OK=1"
for /f "delims=0123456789" %%A in ("%MARSDISK_CELL_JOBS%") do set "CELL_JOBS_OK=0"
if "%CELL_JOBS_OK%"=="0" (
  if defined CELL_JOBS_RAW echo.[warn] MARSDISK_CELL_JOBS invalid: "%CELL_JOBS_RAW%" -> 1
  set "MARSDISK_CELL_JOBS=1"
)
if "%MARSDISK_CELL_JOBS%"=="0" set "MARSDISK_CELL_JOBS=1"
if not defined MEM_RESERVE_GB set "MEM_RESERVE_GB=4"
if not defined PARALLEL_SLEEP_SEC set "PARALLEL_SLEEP_SEC=2"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"

if /i "%SUPPLY_HEADROOM_POLICY%"=="none" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_HEADROOM_POLICY%"=="off" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="none" set "SUPPLY_TRANSPORT_TMIX_ORBITS="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="off" set "SUPPLY_TRANSPORT_TMIX_ORBITS="

set "T_LIST=5000 4000 3000"
set "EPS_LIST=1.0 0.5 0.1"
set "TAU_LIST=1.0 0.5 0.1"

if defined STUDY_FILE (
  if exist "!STUDY_FILE!" (
    set "STUDY_SET=!TMP_ROOT!\\marsdisk_study_!RUN_TS!_!BATCH_SEED!.cmd"
    python scripts\\runsets\\common\\read_study_overrides.py --study "!STUDY_FILE!" > "!STUDY_SET!"
    if not exist "!STUDY_SET!" (
      echo.[error] failed to write study overrides: "!STUDY_SET!"
      echo.[error] temp_root=!TMP_ROOT! study_file=!STUDY_FILE!
    ) else (
      call "!STUDY_SET!"
      del "!STUDY_SET!"
      echo.[info] loaded study overrides from !STUDY_FILE!
      call :trace "study overrides loaded"
    )
  ) else (
    echo.[warn] STUDY_FILE not found: !STUDY_FILE!
  )
)

call :sanitize_list T_LIST
call :sanitize_list EPS_LIST
call :sanitize_list TAU_LIST

if defined SWEEP_TAG (
  set "SWEEP_TAG_RAW=!SWEEP_TAG!"
  set "SWEEP_TAG=!SWEEP_TAG::=!"
  set "SWEEP_TAG=!SWEEP_TAG: =_!"
  set "SWEEP_TAG=!SWEEP_TAG:/=-!"
  set "SWEEP_TAG=!SWEEP_TAG:\=-!"
  if not "!SWEEP_TAG!"=="!SWEEP_TAG_RAW!" echo.[warn] SWEEP_TAG sanitized: "!SWEEP_TAG_RAW!" -> "!SWEEP_TAG!"
)

set "BATCH_DIR=%BATCH_ROOT%\\%SWEEP_TAG%\\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%"
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%" >nul 2>&1
if not exist "%BATCH_DIR%" (
  echo.[error] failed to create output dir: "%BATCH_DIR%"
  popd
  exit /b 1
)

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
set "PARALLEL_JOBS_RAW=%PARALLEL_JOBS%"
set "PARALLEL_JOBS=%PARALLEL_JOBS:"=%"
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if "%PARALLEL_JOBS%"=="" set "PARALLEL_JOBS=1"
set "PARALLEL_JOBS_OK=1"
for /f "delims=0123456789" %%A in ("%PARALLEL_JOBS%") do set "PARALLEL_JOBS_OK=0"
if "%PARALLEL_JOBS_OK%"=="0" (
  if defined PARALLEL_JOBS_RAW echo.[warn] PARALLEL_JOBS invalid: "%PARALLEL_JOBS_RAW%" -> 1
  set "PARALLEL_JOBS=1"
)
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
call :trace "config printed"

set "PROGRESS_FLAG="
if "%ENABLE_PROGRESS%"=="1" set "PROGRESS_FLAG=--progress"

set "OVERRIDE_BUILDER=scripts\\runsets\\common\\build_overrides.py"
set "BASE_OVERRIDES_FILE=%TMP_ROOT%\\marsdisk_overrides_base_%RUN_TS%_%BATCH_SEED%.txt"
set "CASE_OVERRIDES_FILE=%TMP_ROOT%\\marsdisk_overrides_case_%RUN_TS%_%BATCH_SEED%.txt"
set "MERGED_OVERRIDES_FILE=%TMP_ROOT%\\marsdisk_overrides_merged_%RUN_TS%_%BATCH_SEED%.txt"

set "EXTRA_OVERRIDES_EXISTS=0"
if defined EXTRA_OVERRIDES_FILE (
  if exist "%EXTRA_OVERRIDES_FILE%" (
    set "EXTRA_OVERRIDES_EXISTS=1"
  ) else (
    echo.[warn] EXTRA_OVERRIDES_FILE not found: %EXTRA_OVERRIDES_FILE%
  )
)

call :trace "base_overrides_file=%BASE_OVERRIDES_FILE%"
call :trace "base overrides: python build"
python scripts\\runsets\\common\\write_base_overrides.py --out "%BASE_OVERRIDES_FILE%"
if errorlevel 1 (
  echo.[error] failed to build base overrides
  popd
  exit /b 1
)
if not exist "%BASE_OVERRIDES_FILE%" (
  echo.[error] base overrides file missing: "%BASE_OVERRIDES_FILE%"
  popd
  exit /b 1
)
call :trace "base overrides: python done"

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

set "SWEEP_LIST_FILE=%TMP_ROOT%\\marsdisk_sweep_list_%RUN_TS%_%BATCH_SEED%.txt"
call :trace "sweep list file=%SWEEP_LIST_FILE%"
python scripts\\runsets\\common\\write_sweep_list.py --out "%SWEEP_LIST_FILE%"
if errorlevel 1 (
  echo.[error] failed to build sweep list
  popd
  exit /b 1
)
if not exist "%SWEEP_LIST_FILE%" (
  echo.[error] sweep list missing: "%SWEEP_LIST_FILE%"
  popd
  exit /b 1
)

call :trace "parallel check"
if "%SWEEP_PARALLEL%"=="0" (
  call :trace "sweep parallel disabled"
) else if not "%PARALLEL_JOBS%"=="1" (
  if not defined RUN_ONE_MODE (
    call :trace "dispatch parallel"
    call :run_parallel
    popd
    endlocal
    exit /b 0
  )
)

rem ---------- main loops ----------
call :trace "entering main loops"
set "HAS_CASE=0"
for /f "usebackq tokens=1-3 delims= " %%A in ("%SWEEP_LIST_FILE%") do (
  set "HAS_CASE=1"
  set "T=%%A"
  set "EPS=%%B"
  set "TAU=%%C"
  call :validate_token T "!T!"
  if errorlevel 1 goto :abort
  call :validate_token EPS "!EPS!"
  if errorlevel 1 goto :abort
  call :validate_token TAU "!TAU!"
  if errorlevel 1 goto :abort
  call :trace "case start T=%%A EPS=%%B TAU=%%C"
  set "T_TABLE=data/mars_temperature_T!T!p0K.csv"
  set "EPS_TITLE=!EPS!"
  set "EPS_TITLE=!EPS_TITLE:0.=0p!"
  set "EPS_TITLE=!EPS_TITLE:.=p!"
  set "TAU_TITLE=!TAU!"
  set "TAU_TITLE=!TAU_TITLE:0.=0p!"
  set "TAU_TITLE=!TAU_TITLE:.=p!"
  if defined SEED_OVERRIDE (
    set "SEED=%SEED_OVERRIDE%"
  ) else (
    for /f %%S in ('python scripts\\runsets\\common\\next_seed.py') do set "SEED=%%S"
  )
  set "TITLE=T!T!_eps!EPS_TITLE!_tau!TAU_TITLE!"
  set "OUTDIR=%BATCH_DIR%\!TITLE!"
  echo.[run] T=!T! eps=!EPS! tau=!TAU! -^> !OUTDIR! (batch=%BATCH_SEED%, seed=!SEED!)
      rem Show supply rate info (skip Python calc to avoid cmd.exe delayed expansion issues)
      echo.[info] epsilon_mix=!EPS!; mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION%
      echo.[info] shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
      if "!EPS!"=="0.1" echo.[info] epsilon_mix=0.1 is a low-supply extreme case; expect weak blowout/sinks

      if not exist "!OUTDIR!\series" mkdir "!OUTDIR!\series"
      if not exist "!OUTDIR!\checks" mkdir "!OUTDIR!\checks"

      > "%CASE_OVERRIDES_FILE%" echo io.outdir=!OUTDIR!
      >>"%CASE_OVERRIDES_FILE%" echo dynamics.rng_seed=!SEED!
      >>"%CASE_OVERRIDES_FILE%" echo radiation.TM_K=!T!
      >>"%CASE_OVERRIDES_FILE%" echo supply.mixing.epsilon_mix=!EPS!
      >>"%CASE_OVERRIDES_FILE%" echo optical_depth.tau0_target=!TAU!
      if /i "%COOL_MODE%" NEQ "hyodo" (
        >>"%CASE_OVERRIDES_FILE%" echo radiation.mars_temperature_driver.table.path=!T_TABLE!
      )
      if defined COOL_TO_K (
        >>"%CASE_OVERRIDES_FILE%" echo numerics.t_end_until_temperature_K=%COOL_TO_K%
        >>"%CASE_OVERRIDES_FILE%" echo numerics.t_end_temperature_margin_years=%COOL_MARGIN_YEARS%
        if defined COOL_SEARCH_YEARS (
          >>"%CASE_OVERRIDES_FILE%" echo numerics.t_end_temperature_search_years=%COOL_SEARCH_YEARS%
        )
      )
      if "%SUBSTEP_FAST_BLOWOUT%" NEQ "0" (
        >>"%CASE_OVERRIDES_FILE%" echo io.substep_fast_blowout=true
        if defined SUBSTEP_MAX_RATIO (
          >>"%CASE_OVERRIDES_FILE%" echo io.substep_max_ratio=%SUBSTEP_MAX_RATIO%
        )
      )

      rem Override priority: base defaults ^< overrides file ^< per-case overrides.
      if "%EXTRA_OVERRIDES_EXISTS%"=="1" (
        python %OVERRIDE_BUILDER% --file "%BASE_OVERRIDES_FILE%" --file "%EXTRA_OVERRIDES_FILE%" --file "%CASE_OVERRIDES_FILE%" > "%MERGED_OVERRIDES_FILE%"
      ) else (
        python %OVERRIDE_BUILDER% --file "%BASE_OVERRIDES_FILE%" --file "%CASE_OVERRIDES_FILE%" > "%MERGED_OVERRIDES_FILE%"
      )

      rem Assemble the run command on a single line (avoid carets in optional blocks)
      set RUN_CMD=python -m marsdisk.run --config "%BASE_CONFIG%" --quiet
      if "%ENABLE_PROGRESS%"=="1" set RUN_CMD=!RUN_CMD! --progress
      for /f "usebackq delims=" %%L in ("%MERGED_OVERRIDES_FILE%") do (
        set "LINE=%%L"
        if not "!LINE!"=="" set "RUN_CMD=!RUN_CMD! --override !LINE!"
      )

      !RUN_CMD!

      if errorlevel 1 (
        echo.[warn] run command exited with status !errorlevel!; attempting plots anyway
      )

      if "%PLOT_ENABLE%"=="0" (
        echo.[info] PLOT_ENABLE=0; skipping quicklook
      ) else (
        set "RUN_DIR=!OUTDIR!"
        call :trace "quicklook: start"
        python scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "!RUN_DIR!"
        if errorlevel 1 (
          echo.[warn] quicklook failed (rc=!errorlevel!)
        )
      )

      if defined HOOKS_ENABLE (
        set "RUN_DIR=!OUTDIR!"
        call :run_hooks
        if "%HOOKS_STRICT%"=="1" (
          if errorlevel 1 exit /b !errorlevel!
        )
      )
)

if "%HAS_CASE%"=="0" (
  echo.[error] sweep list had no cases: "%SWEEP_LIST_FILE%"
  popd
  endlocal
  exit /b 1
)

popd
call :trace "done"
endlocal
exit /b %errorlevel%

:abort
call :trace "abort"
popd
endlocal
exit /b 1

:run_hooks
set "HOOKS_FAIL=0"
set "HOOKS_LIST=%HOOKS_ENABLE:,= %"
for %%H in (%HOOKS_LIST%) do (
  call :run_hook %%H
  set "HOOK_RC=!errorlevel!"
  if not "!HOOK_RC!"=="0" (
    echo.[warn] hook %%H failed (rc=!HOOK_RC!) for %RUN_DIR%
    if "%HOOKS_STRICT%"=="1" exit /b !HOOK_RC!
    set "HOOKS_FAIL=1"
  )
)
if "%HOOKS_STRICT%"=="1" exit /b %HOOKS_FAIL%
exit /b 0

:run_hook
set "HOOK=%~1"
if /i "%HOOK%"=="preflight" (
  python scripts\\runsets\\common\\hooks\\preflight_streaming.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="plot" (
  python scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="eval" (
  python scripts\\runsets\\common\\hooks\\evaluate_tau_supply.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="archive" (
  python scripts\\runsets\\common\\hooks\\archive_run.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
echo.[warn] unknown hook: %HOOK%
exit /b 0

:run_parallel
call :trace "run_parallel: enter"
set "JOB_PIDS="
set "JOB_COUNT=0"
set "LAUNCHER_PS=%TMP_ROOT%\marsdisk_launch_job_%RUN_TS%_%BATCH_SEED%.ps1"
> "%LAUNCHER_PS%" echo $cmd = $env:JOB_CMD
>>"%LAUNCHER_PS%" echo if (-not $cmd) { exit 2 }
>>"%LAUNCHER_PS%" echo $style = $env:PARALLEL_WINDOW_STYLE
>>"%LAUNCHER_PS%" echo $valid = @('Normal','Hidden','Minimized','Maximized')
>>"%LAUNCHER_PS%" echo if ($style -and -not ($valid -contains $style)) { $style = $null }
>>"%LAUNCHER_PS%" echo if ($style) {
>>"%LAUNCHER_PS%" echo   $p = Start-Process cmd.exe -ArgumentList '/c', $cmd -WindowStyle $style -PassThru
>>"%LAUNCHER_PS%" echo } else {
>>"%LAUNCHER_PS%" echo   $p = Start-Process cmd.exe -ArgumentList '/c', $cmd -PassThru
>>"%LAUNCHER_PS%" echo }
>>"%LAUNCHER_PS%" echo $p.Id
echo.[info] parallel mode: jobs=%PARALLEL_JOBS% sleep=%PARALLEL_SLEEP_SEC%s

if not defined SWEEP_LIST_FILE (
  echo.[error] sweep list file not set for parallel run
  exit /b 1
)
if not exist "%SWEEP_LIST_FILE%" (
  echo.[error] sweep list missing: "%SWEEP_LIST_FILE%"
  exit /b 1
)
for /f "usebackq tokens=1-3 delims= " %%A in ("%SWEEP_LIST_FILE%") do (
  call :launch_job %%A %%B %%C
)

call :wait_all
if exist "%LAUNCHER_PS%" del "%LAUNCHER_PS%"
echo.[done] Parallel sweep completed (batch=%BATCH_SEED%, dir=%BATCH_DIR%).
exit /b 0

:launch_job
set "JOB_T=%~1"
set "JOB_EPS=%~2"
set "JOB_TAU=%~3"
for /f %%S in ('python scripts\\runsets\\common\\next_seed.py') do set "JOB_SEED=%%S"
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

:sanitize_list
set "LIST_RAW=!%~1!"
if not defined LIST_RAW exit /b 0
set "LIST_OUT="
for %%A in (!LIST_RAW!) do (
  set "TOKEN=%%~A"
  set "TOKEN=!TOKEN:"=!"
  set "TOKEN=!TOKEN:,=!"
  set "TOKEN=!TOKEN:;=!"
  set "TOKEN=!TOKEN:[=!"
  set "TOKEN=!TOKEN:]=!"
  set "TOKEN=!TOKEN:(=!"
  set "TOKEN=!TOKEN:)=!"
  set "TOKEN=!TOKEN::=!"
  if not "!TOKEN!"=="" set "LIST_OUT=!LIST_OUT! !TOKEN!"
)
if defined LIST_OUT (
  set "LIST_OUT=!LIST_OUT:~1!"
  if not "!LIST_OUT!"=="!LIST_RAW!" echo.[warn] %~1 sanitized: "!LIST_RAW!" -> "!LIST_OUT!"
  set "%~1=!LIST_OUT!"
) else (
  set "%~1="
)
exit /b 0

:validate_token
set "TOK_NAME=%~1"
set "TOK_VAL=%~2"
if "%TOK_VAL%"=="" (
  echo.[error] %TOK_NAME% token is empty
  exit /b 1
)
echo(%TOK_VAL%| findstr /c:"%%" >nul
if not errorlevel 1 (
  echo.[error] %TOK_NAME% token contains %%: %TOK_VAL%
  exit /b 1
)
exit /b 0

:trace
if "%TRACE_ENABLED%"=="0" exit /b 0
set "TRACE_MSG=%~1"
if "%TRACE_MSG%"=="" set "TRACE_MSG=trace"
echo.[trace] %TRACE_MSG%
if defined TRACE_LOG (
  >>"%TRACE_LOG%" echo.[trace] %DATE% %TIME% %TRACE_MSG%
)
exit /b 0
