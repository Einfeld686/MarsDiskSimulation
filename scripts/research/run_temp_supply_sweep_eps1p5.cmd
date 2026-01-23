@echo off
rem Windows CMD version of run_temp_supply_sweep.sh (logic preserved, output rooted under out/)
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SCRIPT_DIR=%~dp0"

if not defined DEBUG set "DEBUG=0"
if not defined TRACE_ENABLED set "TRACE_ENABLED=0"
if /i "%DEBUG%"=="1" set "TRACE_ENABLED=1"
if not defined TRACE_ECHO set "TRACE_ECHO=0"
if not defined TRACE_DETAIL set "TRACE_DETAIL=0"
if not defined QUIET_MODE set "QUIET_MODE=1"
if /i "%DEBUG%"=="1" set "QUIET_MODE=0"
if /i "%TRACE_ENABLED%"=="1" set "QUIET_MODE=0"
set "SCRIPT_REV=run_temp_supply_sweep_cmd_trace_v2"

if not defined DEBUG_DOC_ALWAYS set "DEBUG_DOC_ALWAYS=0"
set "DEBUG_DOC_ENABLED=0"
if /i "%DEBUG%"=="1" set "DEBUG_DOC_ENABLED=1"

if not defined PYTHON_ALLOW_LAUNCHER set "PYTHON_ALLOW_LAUNCHER=0"

rem Debug: show if PYTHON_EXE was passed from parent
if "%DEBUG%"=="1" echo.[DEBUG] run_temp_supply_sweep: received PYTHON_EXE=[%PYTHON_EXE%]

rem Trim trailing spaces from PYTHON_EXE if it was passed from parent
if defined PYTHON_EXE (
  call :trim_python_exe
)

rem Python resolution is handled after repo root is known.

rem Keep paths stable even if launched from another directory (double-click or direct call)
pushd "%~dp0\..\.."
set "MARSDISK_POPD_ACTIVE=1"
set "SCRIPT_SELF="
set "JOB_CWD="
set "SCRIPT_SELF_HAS_BANG=0"
set "JOB_CWD_HAS_BANG=0"
setlocal DisableDelayedExpansion
set "SCRIPT_SELF=%~f0"
set "JOB_CWD=%CD%"
set "SCRIPT_SELF_HAS_BANG=0"
set "JOB_CWD_HAS_BANG=0"
if not "%SCRIPT_SELF:!=%"=="%SCRIPT_SELF%" set "SCRIPT_SELF_HAS_BANG=1"
if not "%JOB_CWD:!=%"=="%JOB_CWD%" set "JOB_CWD_HAS_BANG=1"
endlocal & set "SCRIPT_SELF=%SCRIPT_SELF%" & set "JOB_CWD=%JOB_CWD%" & set "SCRIPT_SELF_HAS_BANG=%SCRIPT_SELF_HAS_BANG%" & set "JOB_CWD_HAS_BANG=%JOB_CWD_HAS_BANG%"

if not defined USE_SHORT_PATHS set "USE_SHORT_PATHS=0"
if "%USE_SHORT_PATHS%"=="0" (
  if "%SCRIPT_SELF_HAS_BANG%"=="1" set "USE_SHORT_PATHS=1"
  if "%JOB_CWD_HAS_BANG%"=="1" set "USE_SHORT_PATHS=1"
)
set "SCRIPT_SELF_SHORT="
set "JOB_CWD_SHORT="
if /i "%USE_SHORT_PATHS%"=="1" (
  setlocal DisableDelayedExpansion
  for %%I in ("%SCRIPT_SELF%") do set "SCRIPT_SELF_SHORT=%%~sfI"
  for %%I in ("%JOB_CWD%") do set "JOB_CWD_SHORT=%%~sfI"
  endlocal & set "SCRIPT_SELF_SHORT=%SCRIPT_SELF_SHORT%" & set "JOB_CWD_SHORT=%JOB_CWD_SHORT%"
  if "%SCRIPT_SELF_HAS_BANG%"=="1" if not defined SCRIPT_SELF_SHORT (
    echo.[error] script path contains ! and short path unavailable: "%SCRIPT_SELF%"
    call :popd_safe
    exit /b 1
  )
  if "%JOB_CWD_HAS_BANG%"=="1" if not defined JOB_CWD_SHORT (
    echo.[error] repo path contains ! and short path unavailable: "%JOB_CWD%"
    call :popd_safe
    exit /b 1
  )
)

set "SCRIPT_SELF_USE=%SCRIPT_SELF%"
if defined SCRIPT_SELF_SHORT if exist "%SCRIPT_SELF_SHORT%" set "SCRIPT_SELF_USE=%SCRIPT_SELF_SHORT%"

set "JOB_CWD_USE=%JOB_CWD%"
if defined JOB_CWD_SHORT if exist "%JOB_CWD_SHORT%" set "JOB_CWD_USE=%JOB_CWD_SHORT%"

setlocal DisableDelayedExpansion
set "RUNSETS_COMMON_DIR=%JOB_CWD_USE%\scripts\runsets\common"
set "NEXT_SEED_PY=%RUNSETS_COMMON_DIR%\next_seed.py"
set "WIN_PROCESS_PY=%RUNSETS_COMMON_DIR%\win_process.py"
endlocal & set "RUNSETS_COMMON_DIR=%RUNSETS_COMMON_DIR%" & set "NEXT_SEED_PY=%NEXT_SEED_PY%" & set "WIN_PROCESS_PY=%WIN_PROCESS_PY%"

if not exist "%RUNSETS_COMMON_DIR%" (
  echo.[error] runsets common dir not found: "%RUNSETS_COMMON_DIR%"
  call :popd_safe
  exit /b 1
)
if not exist "%NEXT_SEED_PY%" (
  echo.[error] next_seed script not found: "%NEXT_SEED_PY%"
  call :popd_safe
  exit /b 1
)
if not exist "%WIN_PROCESS_PY%" (
  echo.[error] win_process script not found: "%WIN_PROCESS_PY%"
  call :popd_safe
  exit /b 1
)

set "PYTHON_EXEC_CMD=%RUNSETS_COMMON_DIR%\python_exec.cmd"
set "RESOLVE_PYTHON_CMD=%RUNSETS_COMMON_DIR%\resolve_python.cmd"
set "SANITIZE_TOKEN_CMD=%RUNSETS_COMMON_DIR%\sanitize_token.cmd"
if not exist "%PYTHON_EXEC_CMD%" (
  echo.[error] python_exec helper not found: "%PYTHON_EXEC_CMD%"
  call :popd_safe
  exit /b 1
)
if not exist "%RESOLVE_PYTHON_CMD%" (
  echo.[error] resolve_python helper not found: "%RESOLVE_PYTHON_CMD%"
  call :popd_safe
  exit /b 1
)
if not exist "%SANITIZE_TOKEN_CMD%" (
  echo.[error] sanitize_token helper not found: "%SANITIZE_TOKEN_CMD%"
  call :popd_safe
  exit /b 1
)
call "%RESOLVE_PYTHON_CMD%"
if !errorlevel! geq 1 (
  call :popd_safe
  exit /b 1
)
set "PYTHON_EXE_BASE=%PYTHON_EXE%"
set "PYTHON_ARGS_BASE=%PYTHON_ARGS%"
set "PYTHON_CMD_BASE=%PYTHON_CMD%"

rem Optional dry-run for syntax tests (skip all heavy work)
if /i "%~1"=="--dry-run" (
  echo.[dry-run] run_temp_supply_sweep.cmd syntax-only check; skipping execution.
  call :popd_safe
  exit /b 0
)
if /i "%~1"=="--run-one" set "RUN_ONE_MODE=1"
if "%QUIET_MODE%"=="1" (
  set "LOG_SETUP=rem"
  set "LOG_INFO=rem"
  set "LOG_SYS=rem"
  set "LOG_CONFIG=rem"
  set "LOG_RUN=rem"
  set "LOG_PATH=rem"
) else (
  set "LOG_SETUP=echo.[setup]"
  set "LOG_INFO=echo.[info]"
  set "LOG_SYS=echo.[sys]"
  set "LOG_CONFIG=echo.[config]"
  set "LOG_RUN=echo.[run]"
  set "LOG_PATH=echo.[paths]"
)
%LOG_SETUP% script_path=%~f0
%LOG_SETUP% cwd=%CD%

rem ---------- setup ----------
if not defined VENV_DIR set "VENV_DIR=.venv"
rem Convert VENV_DIR to absolute path for child processes
for %%I in ("!VENV_DIR!") do set "VENV_DIR=%%~fI"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
call "%SANITIZE_TOKEN_CMD%" RUN_TS timestamp
if !errorlevel! geq 1 (
  call :popd_safe
  exit /b 1
)
set "TMP_ROOT_BASE=%TEMP%"
set "TMP_SOURCE=TEMP"
if "!TMP_ROOT_BASE!"=="" (
  set "TMP_ROOT_BASE=%CD%\tmp"
  set "TMP_SOURCE=fallback"
)
rem Convert to short 8.3 path to avoid Unicode/space issues
for %%I in ("!TMP_ROOT_BASE!") do set "TMP_ROOT_BASE=%%~sI"
if not exist "!TMP_ROOT_BASE!" mkdir "!TMP_ROOT_BASE!" >nul 2>&1
if not exist "!TMP_ROOT_BASE!" (
  set "TMP_ROOT_BASE=%CD%\tmp"
  set "TMP_SOURCE=fallback"
  for %%I in ("!TMP_ROOT_BASE!") do set "TMP_ROOT_BASE=%%~sI"
  if not exist "!TMP_ROOT_BASE!" mkdir "!TMP_ROOT_BASE!" >nul 2>&1
)
if not exist "!TMP_ROOT_BASE!" (
  echo.[error] temp_root unavailable: "!TMP_ROOT_BASE!"
  call :popd_safe
  exit /b 1
)
if not defined GIT_SHA for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
if not defined GIT_SHA set "GIT_SHA=nogit"
if not defined BATCH_SEED (
  for /f %%A in ('call "%PYTHON_EXEC_CMD%" "!NEXT_SEED_PY!"') do set "BATCH_SEED=%%A"
)
if "%BATCH_SEED%"=="" set "BATCH_SEED=0"
set "TMP_ROOT=%TMP_ROOT_BASE%"
if "%RUN_ONE_MODE%"=="1" (
  if defined RUN_ONE_SEED (
    set "TMP_ROOT=!TMP_ROOT_BASE!\marsdisk_tmp_!RUN_TS!_!BATCH_SEED!_!RUN_ONE_SEED!"
    set "TMP_SOURCE=job"
  )
)
if not exist "!TMP_ROOT!" mkdir "!TMP_ROOT!" >nul 2>&1
if not exist "!TMP_ROOT!" (
  echo.[error] temp_root unavailable: "!TMP_ROOT!"
  call :popd_safe
  exit /b 1
)
%LOG_SETUP% temp_root=!TMP_ROOT! (source=!TMP_SOURCE!)
if "%TRACE_ENABLED%"=="1" (
  if not defined TRACE_LOG set "TRACE_LOG=!TMP_ROOT!\marsdisk_trace_!RUN_TS!_!BATCH_SEED!.log"
  > "!TRACE_LOG!" echo.[trace] start script=%~f0 rev=%SCRIPT_REV%
  if "%TRACE_DETAIL%"=="1" echo.[trace] log=!TRACE_LOG!
)
if "%TRACE_ENABLED%"=="1" if "%TRACE_ECHO%"=="1" (
  echo.[trace] echo-on enabled
  echo on
)
call :trace "setup: env ready"
set "TMP_TEST=!TMP_ROOT!\marsdisk_tmp_test_!RUN_TS!_!BATCH_SEED!.txt"
> "!TMP_TEST!" echo ok
if not exist "!TMP_TEST!" (
  echo.[error] temp_root write test failed: "!TMP_TEST!"
  echo.[error] temp_root=!TMP_ROOT!
  call :popd_safe
  exit /b 1
)
del "!TMP_TEST!"

rem Local Numba cache (gitignored under repo tmp).
if not defined NUMBA_CACHE_DIR set "NUMBA_CACHE_DIR=!JOB_CWD_USE!\tmp\numba_cache"
if not exist "!NUMBA_CACHE_DIR!" mkdir "!NUMBA_CACHE_DIR!" >nul 2>&1

rem Output root defaults to out/ unless BATCH_ROOT/OUT_ROOT is set.
if not defined BATCH_ROOT if defined OUT_ROOT set "BATCH_ROOT=%OUT_ROOT%"
if not defined BATCH_ROOT set "BATCH_ROOT=out"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep"
call "%SANITIZE_TOKEN_CMD%" SWEEP_TAG default "temp_supply_sweep"
if !errorlevel! geq 1 (
  call :popd_safe
  exit /b 1
)
%LOG_SETUP% Output root: %BATCH_ROOT%

set "USE_VENV=1"
if /i "%RUN_ONE_MODE%"=="1" if not defined SKIP_VENV set "SKIP_VENV=1"
if /i "%SKIP_VENV%"=="1" set "USE_VENV=0"
if /i "!SKIP_VENV!"=="1" set "USE_VENV=0"
if "%USE_VENV%"=="0" (
  if "%DEBUG%"=="1" echo.[DEBUG] SKIP_VENV=1: skipping venv
)
if "%USE_VENV%"=="1" if /i "%REQUIREMENTS_INSTALLED%"=="1" if /i "%SKIP_PIP%"=="1" (
  rem Child process: reuse parent venv if present; otherwise fall back to system Python.
  set "VENV_PY=!VENV_DIR!\Scripts\python.exe"
  if exist "!VENV_PY!" (
    set "USE_VENV=1"
    set "VENV_OK=1"
    if "!DEBUG!"=="1" echo.[DEBUG] Using parent venv: !VENV_DIR!
  ) else (
    set "USE_VENV=0"
    if "!DEBUG!"=="1" echo.[DEBUG] Parent venv not found, using system Python
  )
)

if "%USE_VENV%"=="1" if not "%VENV_OK%"=="1" (
  set "VENV_PY=!VENV_DIR!\Scripts\python.exe"
  set "VENV_OK=0"
  if exist "!VENV_PY!" (
    rem Use short path to avoid issues with non-ASCII characters
    for %%I in ("!VENV_PY!") do set "VENV_PY_SHORT=%%~sI"
    for /f %%V in ('"!VENV_PY_SHORT!" -c "import sys; print(1 if sys.version_info >= ^(3,11^) else 0)" 2^>nul') do set "VENV_OK=%%V"
  )
  if not "!VENV_OK!"=="1" (
    if exist "!VENV_DIR!" (
      echo.[warn] venv python is missing or ^<3.11; recreating: !VENV_DIR!
      rmdir /s /q "!VENV_DIR!"
    )
    %LOG_SETUP% Creating virtual environment in !VENV_DIR!...
    call "%PYTHON_EXEC_CMD%" -m venv "!VENV_DIR!"
  )
)

if "%USE_VENV%"=="1" (
  call "!VENV_DIR!\Scripts\activate.bat"
  set "PYTHON_EXE=!VENV_DIR!\Scripts\python.exe"
)
call "%RESOLVE_PYTHON_CMD%"
if !errorlevel! geq 1 (
  call :popd_safe
  exit /b 1
)

if "%SKIP_PIP%"=="1" (
  %LOG_SETUP% SKIP_PIP=1; skipping dependency install.
) else if /i "%REQUIREMENTS_INSTALLED%"=="1" (
  %LOG_SETUP% REQUIREMENTS_INSTALLED=1; skipping dependency install.
) else if exist "%REQ_FILE%" (
  %LOG_SETUP% Installing/upgrading dependencies from %REQ_FILE% ...
  rem --- Workaround for non-ASCII paths (e.g., Japanese usernames) ---
  rem Set pip cache and temp directories to ASCII-only paths to avoid cp932 encoding errors
  if not defined PIP_CACHE_DIR set "PIP_CACHE_DIR=C:\pip_cache"
  if not exist "!PIP_CACHE_DIR!" mkdir "!PIP_CACHE_DIR!" 2>nul
  set "MARSDISK_ORIG_TMP=!TMP!"
  set "MARSDISK_ORIG_TEMP=!TEMP!"
  if not exist "C:\tmp" mkdir "C:\tmp" 2>nul
  set "TMP=C:\tmp"
  set "TEMP=C:\tmp"
  call "%PYTHON_EXEC_CMD%" -m pip install --upgrade pip
  call "%PYTHON_EXEC_CMD%" -m pip install -r "%REQ_FILE%"
  set "PIP_RC=!errorlevel!"
  rem Restore original TMP/TEMP
  set "TMP=!MARSDISK_ORIG_TMP!"
  set "TEMP=!MARSDISK_ORIG_TEMP!"
  if !PIP_RC! neq 0 (
    echo.[error] pip install failed
    exit /b 1
  )
  echo.[info] Dependencies installed successfully
  set "REQUIREMENTS_INSTALLED=1"
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
rem Normalize BASE_CONFIG to absolute path and fix any double backslashes
for %%I in ("!BASE_CONFIG!") do set "BASE_CONFIG=%%~fI"
set "BATCH_ROOT_ABS=!BATCH_ROOT!"
for %%I in ("!BATCH_ROOT!") do set "BATCH_ROOT_ABS=%%~fI"
set "TMP_ROOT_ABS=!TMP_ROOT!"
for %%I in ("!TMP_ROOT!") do set "TMP_ROOT_ABS=%%~fI"
%LOG_PATH% repo_root="!JOB_CWD_USE!"
%LOG_PATH% tmp_root="!TMP_ROOT_ABS!"
%LOG_PATH% batch_root="!BATCH_ROOT_ABS!"
%LOG_PATH% base_config="!BASE_CONFIG!"
if "%DEBUG_DOC_ENABLED%"=="1" (
  if not defined DEBUG_DOC_DIR set "DEBUG_DOC_DIR=!BATCH_ROOT!\debug"
  if not exist "!DEBUG_DOC_DIR!" mkdir "!DEBUG_DOC_DIR!" >nul 2>&1
  if not exist "!DEBUG_DOC_DIR!" set "DEBUG_DOC_DIR=!BATCH_ROOT!"
  if not defined DEBUG_DOC_FILE set "DEBUG_DOC_FILE=!DEBUG_DOC_DIR!\run_temp_supply_debug_!RUN_TS!_!BATCH_SEED!.log"
  >"!DEBUG_DOC_FILE!" echo [debug] run_temp_supply debug doc
  >>"!DEBUG_DOC_FILE!" echo script=!SCRIPT_SELF_USE!
  >>"!DEBUG_DOC_FILE!" echo repo_root=!JOB_CWD_USE!
  >>"!DEBUG_DOC_FILE!" echo run_ts=!RUN_TS! batch_seed=!BATCH_SEED!
  >>"!DEBUG_DOC_FILE!" echo tmp_root=!TMP_ROOT_ABS!
  >>"!DEBUG_DOC_FILE!" echo batch_root=!BATCH_ROOT_ABS!
  >>"!DEBUG_DOC_FILE!" echo venv_dir=!VENV_DIR!
  >>"!DEBUG_DOC_FILE!" echo python_exe=!PYTHON_EXE!
  >>"!DEBUG_DOC_FILE!" echo python_cmd=!PYTHON_CMD!
  >>"!DEBUG_DOC_FILE!" echo base_config=!BASE_CONFIG!
  %LOG_INFO% debug doc="!DEBUG_DOC_FILE!"
)
if not defined QSTAR_UNITS set "QSTAR_UNITS=ba99_cgs"
if not defined GEOMETRY_MODE set "GEOMETRY_MODE=0D"
if not defined GEOMETRY_NR set "GEOMETRY_NR=32"
rem Cooling defaults (stop when Mars T_M reaches 1000 K, slab law unless overridden)
if not defined END_MODE set "END_MODE=fixed"
if not defined T_END_YEARS set "T_END_YEARS=10.0"
if /i "%END_MODE%"=="temperature" (
  if not defined COOL_TO_K set "COOL_TO_K=1000"
) else (
  if defined COOL_TO_K if not "%COOL_TO_K%"=="" echo.[warn] END_MODE=fixed ignores COOL_TO_K=%COOL_TO_K%
  set "COOL_TO_K="
)
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
if not defined SUPPLY_ORBIT_FRACTION set "SUPPLY_ORBIT_FRACTION=0.05"
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
if not defined SWEEP_PROGRESS set "SWEEP_PROGRESS=1"
if not defined SWEEP_PROGRESS_MILESTONE_STEP set "SWEEP_PROGRESS_MILESTONE_STEP=25"
if not defined AUTO_JOBS set "AUTO_JOBS=0"
if not defined PARALLEL_JOBS (
  set "PARALLEL_JOBS=1"
  if not defined PARALLEL_JOBS_DEFAULT set "PARALLEL_JOBS_DEFAULT=1"
) else (
  if not defined PARALLEL_JOBS_DEFAULT set "PARALLEL_JOBS_DEFAULT=0"
)
if not defined JOB_MEM_GB set "JOB_MEM_GB=10"
if not defined SWEEP_PARALLEL (
  set "SWEEP_PARALLEL=0"
  if not defined SWEEP_PARALLEL_DEFAULT set "SWEEP_PARALLEL_DEFAULT=1"
) else (
  if not defined SWEEP_PARALLEL_DEFAULT set "SWEEP_PARALLEL_DEFAULT=0"
)
if not defined SWEEP_PERSISTENT_WORKERS set "SWEEP_PERSISTENT_WORKERS=0"
rem SWEEP_WORKER_JOBS intentionally left undefined by default
rem Sweep-parallel primary: keep cell-parallel off to avoid nested parallelism.
if "%SWEEP_PARALLEL%"=="1" (
  set "MARSDISK_CELL_PARALLEL=0"
  set "MARSDISK_CELL_JOBS=1"
  if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=2"
) else (
  if not defined MARSDISK_CELL_PARALLEL set "MARSDISK_CELL_PARALLEL=1"
  if not defined MARSDISK_CELL_JOBS set "MARSDISK_CELL_JOBS=auto"
)
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
if not defined CELL_MEM_FRACTION set "CELL_MEM_FRACTION=0.7"
if not defined CELL_CPU_FRACTION set "CELL_CPU_FRACTION=0.7"
if /i "%PARALLEL_MODE%"=="numba" (
  set "MARSDISK_CELL_PARALLEL=0"
  set "MARSDISK_CELL_JOBS=1"
)
set "CELL_JOBS_RAW=%MARSDISK_CELL_JOBS%"
if /i "!MARSDISK_CELL_JOBS!"=="auto" (
  set "CELL_CPU_LOGICAL="
  set "CELL_MEM_TOTAL_GB="
  set "CELL_MEM_FRACTION_USED="
  set "CELL_CPU_FRACTION_USED="
  set "CELL_STREAM_MEM_GB="
  set "CELL_THREAD_LIMIT_AUTO="
  for /f "usebackq tokens=1-7 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_cell_jobs.py`) do (
    set "CELL_MEM_TOTAL_GB=%%A"
    set "CELL_CPU_LOGICAL=%%B"
    set "CELL_MEM_FRACTION_USED=%%C"
    set "CELL_CPU_FRACTION_USED=%%D"
    set "MARSDISK_CELL_JOBS=%%E"
    set "CELL_STREAM_MEM_GB=%%F"
    set "CELL_THREAD_LIMIT_AUTO=%%G"
  )
  if not defined MARSDISK_CELL_JOBS set "MARSDISK_CELL_JOBS=1"
  if not defined CELL_MEM_FRACTION_USED set "CELL_MEM_FRACTION_USED=%CELL_MEM_FRACTION%"
  if not defined CELL_CPU_FRACTION_USED set "CELL_CPU_FRACTION_USED=%CELL_CPU_FRACTION%"
  if not defined STREAM_MEM_GB (
    if defined CELL_STREAM_MEM_GB (
      if not "!CELL_STREAM_MEM_GB!"=="0" set "STREAM_MEM_GB=!CELL_STREAM_MEM_GB!"
    )
  )
  %LOG_SYS% cell_parallel auto: mem_total_gb=!CELL_MEM_TOTAL_GB! mem_fraction=!CELL_MEM_FRACTION_USED! cpu_logical=!CELL_CPU_LOGICAL! cpu_fraction=!CELL_CPU_FRACTION_USED! cell_jobs=!MARSDISK_CELL_JOBS!
)
if not defined CELL_CPU_FRACTION_USED set "CELL_CPU_FRACTION_USED=%CELL_CPU_FRACTION%"
set "CELL_JOBS_OK=1"
for /f "delims=0123456789" %%A in ("%MARSDISK_CELL_JOBS%") do set "CELL_JOBS_OK=0"
if "%CELL_JOBS_OK%"=="0" (
  if defined CELL_JOBS_RAW echo.[warn] MARSDISK_CELL_JOBS invalid: "%CELL_JOBS_RAW%" -^> 1
  set "MARSDISK_CELL_JOBS=1"
)
if "%MARSDISK_CELL_JOBS%"=="0" set "MARSDISK_CELL_JOBS=1"
if /i "%PARALLEL_MODE%"=="numba" (
  set "CPU_TARGET_CORES="
  for /f "usebackq tokens=1,2 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_cpu_target_jobs.py`) do (
    set "CPU_TARGET_CORES=%%A"
  )
  if not defined CPU_TARGET_CORES set "CPU_TARGET_CORES=1"
  if "!CPU_TARGET_CORES!"=="" set "CPU_TARGET_CORES=1"
  set "CELL_THREAD_LIMIT=!CPU_TARGET_CORES!"
  set "NUMBA_NUM_THREADS=!CPU_TARGET_CORES!"
  set "OMP_NUM_THREADS=!CPU_TARGET_CORES!"
  set "MKL_NUM_THREADS=!CPU_TARGET_CORES!"
  set "OPENBLAS_NUM_THREADS=!CPU_TARGET_CORES!"
  set "NUMEXPR_NUM_THREADS=!CPU_TARGET_CORES!"
  set "VECLIB_MAXIMUM_THREADS=!CPU_TARGET_CORES!"
  %LOG_SYS% numba_parallel: target_cores=!CPU_TARGET_CORES! target_percent=%CPU_UTIL_TARGET_PERCENT% max_percent=%CPU_UTIL_TARGET_MAX_PERCENT%
)
if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=auto"
set "CELL_THREAD_LIMIT_RAW=%CELL_THREAD_LIMIT%"
if /i "!CELL_THREAD_LIMIT!"=="auto" (
  if defined CELL_THREAD_LIMIT_AUTO (
    set "CELL_THREAD_LIMIT=%CELL_THREAD_LIMIT_AUTO%"
  ) else (
    for /f %%A in ('call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_thread_limit.py') do set "CELL_THREAD_LIMIT=%%A"
  )
)
if "!CELL_THREAD_LIMIT!"=="1" if "%CELL_THREAD_LIMIT_DEFAULT%"=="1" (
  if defined CELL_THREAD_LIMIT_AUTO set "CELL_THREAD_LIMIT=%CELL_THREAD_LIMIT_AUTO%"
)
if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=1"
set "CELL_THREAD_OK=1"
for /f "delims=0123456789" %%A in ("%CELL_THREAD_LIMIT%") do set "CELL_THREAD_OK=0"
if "%CELL_THREAD_OK%"=="0" (
  if defined CELL_THREAD_LIMIT_RAW echo.[warn] CELL_THREAD_LIMIT invalid: "%CELL_THREAD_LIMIT_RAW%" -^> 1
  set "CELL_THREAD_LIMIT=1"
)
if "%CELL_THREAD_LIMIT%"=="0" set "CELL_THREAD_LIMIT=1"
if not defined OMP_NUM_THREADS set "OMP_NUM_THREADS=%CELL_THREAD_LIMIT%"
if not defined MKL_NUM_THREADS set "MKL_NUM_THREADS=%CELL_THREAD_LIMIT%"
if not defined OPENBLAS_NUM_THREADS set "OPENBLAS_NUM_THREADS=%CELL_THREAD_LIMIT%"
if not defined NUMEXPR_NUM_THREADS set "NUMEXPR_NUM_THREADS=%CELL_THREAD_LIMIT%"
if not defined VECLIB_MAXIMUM_THREADS set "VECLIB_MAXIMUM_THREADS=%CELL_THREAD_LIMIT%"
if not defined NUMBA_NUM_THREADS set "NUMBA_NUM_THREADS=%CELL_THREAD_LIMIT%"
%LOG_SYS% thread caps: limit=%CELL_THREAD_LIMIT% (OMP/MKL/OPENBLAS/NUMEXPR/NUMBA)
if not defined MEM_RESERVE_GB set "MEM_RESERVE_GB=4"
if not defined PARALLEL_SLEEP_SEC set "PARALLEL_SLEEP_SEC=2"
call :normalize_int PARALLEL_SLEEP_SEC 2
if "%PARALLEL_SLEEP_SEC%"=="0" set "PARALLEL_SLEEP_SEC=1"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"

if /i "%SUPPLY_HEADROOM_POLICY%"=="none" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_HEADROOM_POLICY%"=="off" set "SUPPLY_HEADROOM_POLICY="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="none" set "SUPPLY_TRANSPORT_TMIX_ORBITS="
if /i "%SUPPLY_TRANSPORT_TMIX_ORBITS%"=="off" set "SUPPLY_TRANSPORT_TMIX_ORBITS="

set "T_LIST=5000 4000 3000"
set "EPS_LIST=1.5"
set "TAU_LIST=1.0 0.5"
set "I0_LIST=0.05"
if not defined MU_LIST set "MU_LIST=%SUPPLY_MU_ORBIT10PCT%"
if not defined EXTRA_CASES (
  set "EXTRA_CASES="
)

if defined STUDY_FILE (
  if exist "!STUDY_FILE!" (
    set "STUDY_SET=!TMP_ROOT!\marsdisk_study_!RUN_TS!_!BATCH_SEED!.cmd"
    call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\read_study_overrides.py --study "!STUDY_FILE!" --out "!STUDY_SET!"
    if not exist "!STUDY_SET!" (
      echo.[error] failed to write study overrides: "!STUDY_SET!"
      echo.[error] temp_root=!TMP_ROOT! study_file=!STUDY_FILE!
    ) else (
      call "!STUDY_SET!"
      del "!STUDY_SET!"
      %LOG_INFO% loaded study overrides from !STUDY_FILE!
      call :trace_detail "study overrides loaded"
    )
  ) else (
    echo.[warn] STUDY_FILE not found: !STUDY_FILE!
  )
)

if not defined END_MODE set "END_MODE=fixed"
if not defined T_END_YEARS set "T_END_YEARS=10.0"
if /i "%END_MODE%"=="temperature" (
  if not defined COOL_TO_K set "COOL_TO_K=1000"
) else (
  if defined COOL_TO_K if not "%COOL_TO_K%"=="" echo.[warn] END_MODE=fixed ignores COOL_TO_K=%COOL_TO_K%
  set "COOL_TO_K="
)

call :sanitize_list T_LIST
call :sanitize_list EPS_LIST
call :sanitize_list TAU_LIST
call :sanitize_list I0_LIST
call :sanitize_list MU_LIST

set "BATCH_DIR=!BATCH_ROOT!\!SWEEP_TAG!\!RUN_TS!__!GIT_SHA!__seed!BATCH_SEED!"
if not exist "!BATCH_DIR!" mkdir "!BATCH_DIR!" >nul 2>&1
if not exist "!BATCH_DIR!" (
  echo.[error] failed to create output dir: "!BATCH_DIR!"
  call :popd_safe
  exit /b 1
)

set "COOL_SEARCH_DISPLAY=!COOL_SEARCH_YEARS!"
if not defined COOL_SEARCH_DISPLAY set "COOL_SEARCH_DISPLAY=none"

set "COOL_STATUS="
if /i "%END_MODE%"=="temperature" (
  set "COOL_STATUS=end_mode=temperature: stop when Mars T_M reaches !COOL_TO_K! K (margin !COOL_MARGIN_YEARS! yr, search_cap=!COOL_SEARCH_DISPLAY!)"
) else (
  set "COOL_STATUS=end_mode=fixed: t_end_years=!T_END_YEARS!"
)

set "TOTAL_GB="
set "CPU_LOGICAL="
if "%AUTO_JOBS%"=="1" (
  for /f "usebackq tokens=1-3 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
    set "TOTAL_GB=%%A"
    set "CPU_LOGICAL=%%B"
    set "PARALLEL_JOBS=%%C"
  )
  if not defined STREAM_MEM_GB set "STREAM_MEM_GB=%JOB_MEM_GB%"
)
set "PARALLEL_JOBS_RAW=%PARALLEL_JOBS%"
set "PARALLEL_JOBS=%PARALLEL_JOBS:"=%"
if not "!PARALLEL_JOBS!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS!") do set "PARALLEL_JOBS=%%Z"
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if "%PARALLEL_JOBS%"=="" set "PARALLEL_JOBS=1"
set "PARALLEL_JOBS_OK=1"
if not "%PARALLEL_JOBS%"=="" for /f "delims=0123456789" %%A in ("%PARALLEL_JOBS%") do set "PARALLEL_JOBS_OK=0"
if "%PARALLEL_JOBS_OK%"=="0" (
  if defined PARALLEL_JOBS_RAW echo.[warn] PARALLEL_JOBS invalid: "%PARALLEL_JOBS_RAW%" -^> 1
  set "PARALLEL_JOBS=1"
)
if "%PARALLEL_JOBS%"=="0" set "PARALLEL_JOBS=1"
if "%AUTO_JOBS%"=="1" (
  if not defined TOTAL_GB set "TOTAL_GB=unknown"
  if not defined CPU_LOGICAL set "CPU_LOGICAL=unknown"
  %LOG_SYS% mem_total_gb=%TOTAL_GB% cpu_logical=%CPU_LOGICAL% job_mem_gb=%JOB_MEM_GB% parallel_jobs=%PARALLEL_JOBS%
)

if defined CPU_UTIL_TARGET_PERCENT if /i not "%PARALLEL_MODE%"=="numba" (
  if not defined CPU_UTIL_RESPECT_MEM set "CPU_UTIL_RESPECT_MEM=1"
  if not defined RUN_ONE_MODE (
    set "CPU_TARGET_OK=1"
    for /f "delims=0123456789" %%A in ("%CPU_UTIL_TARGET_PERCENT%") do set "CPU_TARGET_OK=0"
    if "!CPU_TARGET_OK!"=="1" (
      if not defined CELL_CPU_LOGICAL (
        if defined NUMBER_OF_PROCESSORS set "CELL_CPU_LOGICAL=%NUMBER_OF_PROCESSORS%"
      )
      if defined CELL_CPU_LOGICAL (
        for /f "usebackq tokens=1,2 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_cpu_target_jobs.py`) do (
          set "CPU_TARGET_CORES=%%A"
          set "PARALLEL_JOBS_TARGET=%%B"
          if not "!PARALLEL_JOBS_TARGET!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET=%%Z"
        )
        set "PARALLEL_JOBS_TARGET_OK=1"
        if "!PARALLEL_JOBS_TARGET!"=="" set "PARALLEL_JOBS_TARGET_OK=0"
        if "!PARALLEL_JOBS_TARGET_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET_OK=0"
        if "!PARALLEL_JOBS_TARGET_OK!"=="1" (
        if "!PARALLEL_JOBS_DEFAULT!"=="1" if "!PARALLEL_JOBS!"=="1" if not "!PARALLEL_JOBS_TARGET!"=="" if !PARALLEL_JOBS_TARGET! GTR 1 (
          if /i "!CPU_UTIL_RESPECT_MEM!"=="1" (
            for /f "usebackq tokens=1-3 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
              set "PARALLEL_JOBS_MEM=%%C"
              if not "!PARALLEL_JOBS_MEM!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM=%%Z"
            )
          set "PARALLEL_JOBS_MEM_OK=1"
          if "!PARALLEL_JOBS_MEM!"=="" set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" (
            if not "!PARALLEL_JOBS_TARGET!"=="" if not "!PARALLEL_JOBS_MEM!"=="" (
              if !PARALLEL_JOBS_TARGET! GTR !PARALLEL_JOBS_MEM! set "PARALLEL_JOBS_TARGET=!PARALLEL_JOBS_MEM!"
            )
          )
          )
          if not "!PARALLEL_JOBS_TARGET!"=="" if !PARALLEL_JOBS_TARGET! GTR 1 (
            if "!SWEEP_PARALLEL!"=="0" if "!SWEEP_PARALLEL_DEFAULT!"=="1" set "SWEEP_PARALLEL=1"
            if "!SWEEP_PARALLEL!"=="1" (
              set "PARALLEL_JOBS=!PARALLEL_JOBS_TARGET!"
              %LOG_SYS% cpu_target auto-parallel: target_percent=%CPU_UTIL_TARGET_PERCENT% target_cores=!CPU_TARGET_CORES! cell_jobs=%MARSDISK_CELL_JOBS% parallel_jobs=!PARALLEL_JOBS!
            )
          )
        )
        )
      )
    )
  )
)

%LOG_CONFIG% supply multipliers: temp_enabled=%SUPPLY_TEMP_ENABLED% (mode=%SUPPLY_TEMP_MODE%) feedback_enabled=%SUPPLY_FEEDBACK_ENABLED% reservoir=%SUPPLY_RESERVOIR_M%
%LOG_CONFIG% shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
%LOG_CONFIG% injection: mode=%SUPPLY_INJECTION_MODE% q=%SUPPLY_INJECTION_Q% s_inj_min=%SUPPLY_INJECTION_SMIN% s_inj_max=%SUPPLY_INJECTION_SMAX%
%LOG_CONFIG% transport: mode=%SUPPLY_TRANSPORT_MODE% t_mix=%SUPPLY_TRANSPORT_TMIX_ORBITS% headroom_gate=%SUPPLY_TRANSPORT_HEADROOM% velocity=%SUPPLY_VEL_MODE%
%LOG_CONFIG% geometry: mode=%GEOMETRY_MODE% Nr=%GEOMETRY_NR% r_in_m=%GEOMETRY_R_IN_M% r_out_m=%GEOMETRY_R_OUT_M%
%LOG_CONFIG% external supply: mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% mu_list=%MU_LIST% mu_reference_tau=%SUPPLY_MU_REFERENCE_TAU% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION% (epsilon_mix swept per EPS_LIST)
%LOG_CONFIG% optical_depth: tau0_target_list=%TAU_LIST% tau_stop=%OPTICAL_TAU_STOP% tau_stop_tol=%OPTICAL_TAU_STOP_TOL%
%LOG_CONFIG% dynamics: i0_list=%I0_LIST%
if defined EXTRA_CASES %LOG_CONFIG% extra cases: %EXTRA_CASES%
%LOG_CONFIG% fast blowout substep: enabled=%SUBSTEP_FAST_BLOWOUT% substep_max_ratio=%SUBSTEP_MAX_RATIO%
%LOG_CONFIG% !COOL_STATUS!
%LOG_CONFIG% cooling driver mode: %COOL_MODE% (slab: T^-3, hyodo: linear flux)
call :trace "config printed"

set "PROGRESS_FLAG="
if "%ENABLE_PROGRESS%"=="1" set "PROGRESS_FLAG=--progress"

set "OVERRIDE_BUILDER=scripts\runsets\common\build_overrides.py"
set "BASE_OVERRIDES_FILE=!TMP_ROOT!\marsdisk_overrides_base_!RUN_TS!_!BATCH_SEED!.txt"
set "CASE_OVERRIDES_FILE=!TMP_ROOT!\marsdisk_overrides_case_!RUN_TS!_!BATCH_SEED!.txt"
set "MERGED_OVERRIDES_FILE=!TMP_ROOT!\marsdisk_overrides_merged_!RUN_TS!_!BATCH_SEED!.txt"

if defined RUN_ONE_MODE (
  if not defined RUN_ONE_T (
    echo.[error] RUN_ONE_T is required for --run-one
    call :popd_safe
    exit /b 1
  )
  if not defined RUN_ONE_EPS (
    echo.[error] RUN_ONE_EPS is required for --run-one
    call :popd_safe
    exit /b 1
  )
  if not defined RUN_ONE_TAU (
    echo.[error] RUN_ONE_TAU is required for --run-one
    call :popd_safe
    exit /b 1
  )
  if not defined RUN_ONE_I0 (
    echo.[error] RUN_ONE_I0 is required for --run-one
    call :popd_safe
    exit /b 1
  )
  if not defined RUN_ONE_MU set "RUN_ONE_MU=%SUPPLY_MU_ORBIT10PCT%"
  %LOG_INFO% run-one mode: T=%RUN_ONE_T% eps=%RUN_ONE_EPS% tau=%RUN_ONE_TAU% i0=%RUN_ONE_I0% mu=%RUN_ONE_MU% seed=%RUN_ONE_SEED%
  call :trace_detail "run-one: dispatch to run_one.py"
  call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\run_one.py
  set "RUN_ONE_RC=!errorlevel!"
  if "!RUN_ONE_RC!"=="130" (
    %LOG_INFO% run-one interrupted by user
    call :popd_safe
    exit /b 0
  )
  if not "!RUN_ONE_RC!"=="0" (
    echo.[warn] run_one.py exited with status !RUN_ONE_RC!
  )
  call :popd_safe
  exit /b !RUN_ONE_RC!
)

set "EXTRA_OVERRIDES_EXISTS=0"
if defined EXTRA_OVERRIDES_FILE (
  if exist "%EXTRA_OVERRIDES_FILE%" (
    set "EXTRA_OVERRIDES_EXISTS=1"
  ) else (
    echo.[warn] EXTRA_OVERRIDES_FILE not found: %EXTRA_OVERRIDES_FILE%
  )
)

call :trace_detail "base_overrides_file=!BASE_OVERRIDES_FILE!"
call :trace_detail "base overrides: python build"
call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\write_base_overrides.py --out "!BASE_OVERRIDES_FILE!"
if !errorlevel! geq 1 (
  echo.[error] failed to build base overrides
  call :popd_safe
  exit /b 1
)
if not exist "!BASE_OVERRIDES_FILE!" (
  echo.[error] base overrides file missing: "!BASE_OVERRIDES_FILE!"
  call :popd_safe
  exit /b 1
)
call :trace_detail "base overrides: python done"

set "SWEEP_LIST_FILE=!TMP_ROOT!\marsdisk_sweep_list_!RUN_TS!_!BATCH_SEED!.txt"
call :trace_detail "sweep list file=!SWEEP_LIST_FILE!"
call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\write_sweep_list.py --out "!SWEEP_LIST_FILE!"
if !errorlevel! geq 1 (
  echo.[error] failed to build sweep list
  call :popd_safe
  exit /b 1
)
if not exist "!SWEEP_LIST_FILE!" (
  echo.[error] sweep list missing: "!SWEEP_LIST_FILE!"
  call :popd_safe
  exit /b 1
)

set "SWEEP_TOTAL=0"
for /f "usebackq tokens=3 delims=:" %%C in (`find /c /v "" "!SWEEP_LIST_FILE!"`) do set "SWEEP_TOTAL=%%C"
call :normalize_int SWEEP_TOTAL 0
call :get_monotonic_seconds SWEEP_START_SECS

if not defined SWEEP_SETTINGS_PATH set "SWEEP_SETTINGS_PATH=!BATCH_DIR!\sweep_settings.txt"
> "!SWEEP_SETTINGS_PATH!" echo sweep_tag=!SWEEP_TAG!
>>"!SWEEP_SETTINGS_PATH!" echo run_ts=!RUN_TS!
>>"!SWEEP_SETTINGS_PATH!" echo git_sha=!GIT_SHA!
>>"!SWEEP_SETTINGS_PATH!" echo batch_seed=!BATCH_SEED!
>>"!SWEEP_SETTINGS_PATH!" echo batch_dir=!BATCH_DIR!
>>"!SWEEP_SETTINGS_PATH!" echo batch_root=!BATCH_ROOT!
>>"!SWEEP_SETTINGS_PATH!" echo tmp_root=!TMP_ROOT!
>>"!SWEEP_SETTINGS_PATH!" echo base_config=!BASE_CONFIG!
>>"!SWEEP_SETTINGS_PATH!" echo extra_overrides_file=!EXTRA_OVERRIDES_FILE!
>>"!SWEEP_SETTINGS_PATH!" echo study_file=!STUDY_FILE!
>>"!SWEEP_SETTINGS_PATH!" echo geometry_mode=!GEOMETRY_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo geometry_nr=!GEOMETRY_NR!
>>"!SWEEP_SETTINGS_PATH!" echo shielding_mode=!SHIELDING_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo supply_mode=!SUPPLY_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo supply_mu_orbit10pct=!SUPPLY_MU_ORBIT10PCT!
>>"!SWEEP_SETTINGS_PATH!" echo supply_mu_reference_tau=!SUPPLY_MU_REFERENCE_TAU!
>>"!SWEEP_SETTINGS_PATH!" echo supply_orbit_fraction_at_mu1=!SUPPLY_ORBIT_FRACTION!
>>"!SWEEP_SETTINGS_PATH!" echo supply_headroom_policy=!SUPPLY_HEADROOM_POLICY!
>>"!SWEEP_SETTINGS_PATH!" echo supply_transport_mode=!SUPPLY_TRANSPORT_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo supply_transport_tmix_orbits=!SUPPLY_TRANSPORT_TMIX_ORBITS!
>>"!SWEEP_SETTINGS_PATH!" echo supply_transport_headroom=!SUPPLY_TRANSPORT_HEADROOM!
>>"!SWEEP_SETTINGS_PATH!" echo end_mode=!END_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo t_end_years=!T_END_YEARS!
>>"!SWEEP_SETTINGS_PATH!" echo cool_to_k=!COOL_TO_K!
>>"!SWEEP_SETTINGS_PATH!" echo cool_margin_years=!COOL_MARGIN_YEARS!
>>"!SWEEP_SETTINGS_PATH!" echo cool_search_years=!COOL_SEARCH_YEARS!
>>"!SWEEP_SETTINGS_PATH!" echo t_list=!T_LIST!
>>"!SWEEP_SETTINGS_PATH!" echo eps_list=!EPS_LIST!
>>"!SWEEP_SETTINGS_PATH!" echo tau_list=!TAU_LIST!
>>"!SWEEP_SETTINGS_PATH!" echo i0_list=!I0_LIST!
>>"!SWEEP_SETTINGS_PATH!" echo mu_list=!MU_LIST!
>>"!SWEEP_SETTINGS_PATH!" echo sweep_list_file=!SWEEP_LIST_FILE!
>>"!SWEEP_SETTINGS_PATH!" echo sweep_total=!SWEEP_TOTAL!
>>"!SWEEP_SETTINGS_PATH!" echo sweep_parallel=!SWEEP_PARALLEL!
>>"!SWEEP_SETTINGS_PATH!" echo sweep_persistent_workers=!SWEEP_PERSISTENT_WORKERS!
>>"!SWEEP_SETTINGS_PATH!" echo parallel_jobs=!PARALLEL_JOBS!
>>"!SWEEP_SETTINGS_PATH!" echo parallel_mode=!PARALLEL_MODE!
>>"!SWEEP_SETTINGS_PATH!" echo cell_parallel=!MARSDISK_CELL_PARALLEL!
>>"!SWEEP_SETTINGS_PATH!" echo cell_jobs=!MARSDISK_CELL_JOBS!
>>"!SWEEP_SETTINGS_PATH!" echo cell_thread_limit=!CELL_THREAD_LIMIT!
>>"!SWEEP_SETTINGS_PATH!" echo stream_mem_gb=!STREAM_MEM_GB!
>>"!SWEEP_SETTINGS_PATH!" echo enable_progress=!ENABLE_PROGRESS!
>>"!SWEEP_SETTINGS_PATH!" echo hooks_enable=!HOOKS_ENABLE!
>>"!SWEEP_SETTINGS_PATH!" echo hooks_strict=!HOOKS_STRICT!
>>"!SWEEP_SETTINGS_PATH!" echo plot_enable=!PLOT_ENABLE!
>>"!SWEEP_SETTINGS_PATH!" echo eval_enable=!EVAL!

call :trace_detail "parallel check"
echo.[DEBUG] Parallel check: SWEEP_PARALLEL=%SWEEP_PARALLEL% PARALLEL_JOBS=%PARALLEL_JOBS% RUN_ONE_MODE=%RUN_ONE_MODE% SWEEP_PERSISTENT_WORKERS=%SWEEP_PERSISTENT_WORKERS%
if "%SWEEP_PERSISTENT_WORKERS%"=="1" (
  call :trace_detail "persistent workers enabled"
  if "%SWEEP_PARALLEL%"=="1" if not "%PARALLEL_JOBS%"=="1" (
    echo.[DEBUG] Branch: SWEEP_PERSISTENT_WORKERS=1 and SWEEP_PARALLEL=1 -^> parallel worker mode
    call :run_parallel_workers
    call :popd_safe
    exit /b 0
  ) else (
    echo.[DEBUG] Branch: SWEEP_PERSISTENT_WORKERS=1 -^> single worker mode
    call :run_worker_single
    set "WORKER_RC=!errorlevel!"
    call :popd_safe
    exit /b !WORKER_RC!
  )
)
if "%SWEEP_PARALLEL%"=="0" (
  call :trace_detail "sweep parallel disabled"
  echo.[DEBUG] Branch: SWEEP_PARALLEL=0 -^> sequential mode
) else if not "%PARALLEL_JOBS%"=="1" (
  if not defined RUN_ONE_MODE (
    call :trace_detail "dispatch parallel"
    echo.[DEBUG] Branch: SWEEP_PARALLEL=1, PARALLEL_JOBS=%PARALLEL_JOBS%, no RUN_ONE_MODE -^> parallel mode
    call :run_parallel
    call :popd_safe
    exit /b 0
  ) else (
    echo.[DEBUG] Branch: SWEEP_PARALLEL=1, PARALLEL_JOBS!=1, but RUN_ONE_MODE defined -^> single job
  )
) else (
  echo.[DEBUG] Branch: SWEEP_PARALLEL=1 but PARALLEL_JOBS=1 -^> sequential fallback
)

rem ---------- main loops ----------
echo.[DEBUG] Entering main loops (sequential execution)
call :trace "entering main loops"
set "HAS_CASE=0"
set "SEQ_CASE_INDEX=0"
for /f "usebackq tokens=1-5 delims= " %%A in ("%SWEEP_LIST_FILE%") do (
  set "HAS_CASE=1"
  set /a SEQ_CASE_INDEX+=1
  set /a SEQ_DONE=SEQ_CASE_INDEX-1
  call :calc_eta_suffix !SEQ_DONE! !SWEEP_TOTAL!
  set "T=%%A"
  set "EPS=%%B"
  set "TAU=%%C"
  set "I0=%%D"
  set "MU=%%E"
  if "!MU!"=="" set "MU=%SUPPLY_MU_ORBIT10PCT%"
  call :validate_token T "!T!"
  if !errorlevel! geq 1 goto :abort
  call :validate_token EPS "!EPS!"
  if !errorlevel! geq 1 goto :abort
  call :validate_token TAU "!TAU!"
  if !errorlevel! geq 1 goto :abort
  call :validate_token I0 "!I0!"
  if !errorlevel! geq 1 goto :abort
  call :validate_token MU "!MU!"
  if !errorlevel! geq 1 goto :abort
  call :trace "case start T=%%A EPS=%%B TAU=%%C I0=%%D MU=%%E"
  set "T_TABLE=data/mars_temperature_T!T!p0K.csv"
  set "EPS_TITLE=!EPS!"
  set "EPS_TITLE=!EPS_TITLE:0.=0p!"
  set "EPS_TITLE=!EPS_TITLE:.=p!"
  set "TAU_TITLE=!TAU!"
  set "TAU_TITLE=!TAU_TITLE:0.=0p!"
  set "TAU_TITLE=!TAU_TITLE:.=p!"
  set "I0_TITLE=!I0!"
  set "I0_TITLE=!I0_TITLE:0.=0p!"
  set "I0_TITLE=!I0_TITLE:.=p!"
  set "MU_TITLE=!MU!"
  set "MU_TITLE=!MU_TITLE:0.=0p!"
  set "MU_TITLE=!MU_TITLE:.=p!"
  if defined SEED_OVERRIDE (
    set "SEED=%SEED_OVERRIDE%"
  ) else (
    for /f %%S in ('call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\next_seed.py') do set "SEED=%%S"
  )
  set "TITLE=T!T!_eps!EPS_TITLE!_tau!TAU_TITLE!_i0!I0_TITLE!_mu!MU_TITLE!"
  set "OUTDIR_REL=!BATCH_DIR!\!TITLE!"
  rem Convert to absolute path to avoid double-backslash issues
  for %%I in ("!OUTDIR_REL!") do set "OUTDIR=%%~fI"
  %LOG_RUN% T=!T! eps=!EPS! tau=!TAU! i0=!I0! -^> !OUTDIR! ^(batch=!BATCH_SEED!, seed=!SEED!^)
      rem Show supply rate info (skip Python calc to avoid cmd.exe delayed expansion issues)
      %LOG_INFO% epsilon_mix=!EPS!; mu_orbit10pct=!MU! orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION% !ETA_SUFFIX!
      %LOG_INFO% shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
      if "!EPS!"=="0.1" %LOG_INFO% epsilon_mix=0.1 is a low-supply extreme case; expect weak blowout/sinks

      if not exist "!OUTDIR!\series" mkdir "!OUTDIR!\series"
      if not exist "!OUTDIR!\checks" mkdir "!OUTDIR!\checks"

      > "!CASE_OVERRIDES_FILE!" echo io.outdir=!OUTDIR!
      >>"!CASE_OVERRIDES_FILE!" echo dynamics.rng_seed=!SEED!
      >>"!CASE_OVERRIDES_FILE!" echo radiation.TM_K=!T!
      >>"!CASE_OVERRIDES_FILE!" echo supply.mixing.epsilon_mix=!EPS!
      >>"!CASE_OVERRIDES_FILE!" echo supply.const.mu_orbit10pct=!MU!
      >>"!CASE_OVERRIDES_FILE!" echo optical_depth.tau0_target=!TAU!
      >>"!CASE_OVERRIDES_FILE!" echo dynamics.i0=!I0!
      if /i "!COOL_MODE!" NEQ "hyodo" (
        >>"!CASE_OVERRIDES_FILE!" echo radiation.mars_temperature_driver.table.path=!T_TABLE!
      )
      if /i "%END_MODE%"=="temperature" (
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_years=null
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_orbits=null
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_until_temperature_K=!COOL_TO_K!
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_temperature_margin_years=!COOL_MARGIN_YEARS!
        if defined COOL_SEARCH_YEARS (
          >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_temperature_search_years=!COOL_SEARCH_YEARS!
        ) else (
          >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_temperature_search_years=null
        )
        >>"!CASE_OVERRIDES_FILE!" echo scope.analysis_years=10
      ) else (
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_years=!T_END_YEARS!
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_orbits=null
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_until_temperature_K=null
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_temperature_margin_years=0.0
        >>"!CASE_OVERRIDES_FILE!" echo numerics.t_end_temperature_search_years=null
        >>"!CASE_OVERRIDES_FILE!" echo scope.analysis_years=!T_END_YEARS!
      )
      if "!SUBSTEP_FAST_BLOWOUT!" NEQ "0" (
        >>"!CASE_OVERRIDES_FILE!" echo io.substep_fast_blowout=true
        if defined SUBSTEP_MAX_RATIO (
          >>"!CASE_OVERRIDES_FILE!" echo io.substep_max_ratio=!SUBSTEP_MAX_RATIO!
        )
      )
      if defined STREAM_MEM_GB (
        >>"!CASE_OVERRIDES_FILE!" echo io.streaming.memory_limit_gb=!STREAM_MEM_GB!
      )

      rem Override priority: base defaults ^< overrides file ^< per-case overrides.
      if "!EXTRA_OVERRIDES_EXISTS!"=="1" (
        call "%PYTHON_EXEC_CMD%" !OVERRIDE_BUILDER! --file "!BASE_OVERRIDES_FILE!" --file "!EXTRA_OVERRIDES_FILE!" --file "!CASE_OVERRIDES_FILE!" --out "!MERGED_OVERRIDES_FILE!"
      ) else (
        call "%PYTHON_EXEC_CMD%" !OVERRIDE_BUILDER! --file "!BASE_OVERRIDES_FILE!" --file "!CASE_OVERRIDES_FILE!" --out "!MERGED_OVERRIDES_FILE!"
      )

      echo.[DEBUG] About to run simulation
      echo.[DEBUG] PYTHON_CMD=!PYTHON_CMD!
      echo.[DEBUG] PYTHON_EXEC_CMD=!PYTHON_EXEC_CMD!
      echo.[DEBUG] ENABLE_PROGRESS=!ENABLE_PROGRESS!
      echo.[DEBUG] BASE_CONFIG=!BASE_CONFIG!
      echo.[DEBUG] MERGED_OVERRIDES_FILE=!MERGED_OVERRIDES_FILE!
      echo.[DEBUG] Checking if files exist:
      if exist "!BASE_CONFIG!" (echo.[DEBUG] BASE_CONFIG exists) else (echo.[DEBUG] BASE_CONFIG NOT FOUND)
      if exist "!MERGED_OVERRIDES_FILE!" (echo.[DEBUG] MERGED_OVERRIDES_FILE exists) else (echo.[DEBUG] MERGED_OVERRIDES_FILE NOT FOUND)
      if "!ENABLE_PROGRESS!"=="1" (
        call "%PYTHON_EXEC_CMD%" -m marsdisk.run --config "!BASE_CONFIG!" --quiet --overrides-file "!MERGED_OVERRIDES_FILE!" --progress
      ) else (
        call "%PYTHON_EXEC_CMD%" -m marsdisk.run --config "!BASE_CONFIG!" --quiet --overrides-file "!MERGED_OVERRIDES_FILE!"
      )

      if !errorlevel! geq 1 (
        echo.[warn] run command exited with status !errorlevel!; attempting plots anyway
      )

      if "%PLOT_ENABLE%"=="0" (
        %LOG_INFO% PLOT_ENABLE=0; skipping quicklook
      ) else (
        set "RUN_DIR=!OUTDIR!"
        call :trace_detail "quicklook: start"
        call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "!RUN_DIR!"
        if !errorlevel! geq 1 (
          echo.[warn] quicklook failed [rc=!errorlevel!]
        )
      )

      if defined HOOKS_ENABLE (
        set "RUN_DIR=!OUTDIR!"
        call :run_hooks
        if "%HOOKS_STRICT%"=="1" (
          if !errorlevel! geq 1 exit /b !errorlevel!
        )
      )
)

if "%HAS_CASE%"=="0" (
  echo.[error] sweep list had no cases: "%SWEEP_LIST_FILE%"
  call :popd_safe
  exit /b 1
)

call :popd_safe
call :trace "done"
exit /b !errorlevel!

:abort
call :trace "abort"
call :popd_safe
exit /b 1

:run_hooks
set "HOOKS_FAIL=0"
set "HOOKS_LIST=%HOOKS_ENABLE:,= %"
for %%H in (%HOOKS_LIST%) do (
  call :run_hook %%H
  set "HOOK_RC=!errorlevel!"
  if not "!HOOK_RC!"=="0" (
    echo.[warn] hook %%H failed [rc=!HOOK_RC!] for %RUN_DIR%
    if "%HOOKS_STRICT%"=="1" exit /b !HOOK_RC!
    set "HOOKS_FAIL=1"
  )
)
if "%HOOKS_STRICT%"=="1" exit /b %HOOKS_FAIL%
exit /b 0

:run_hook
set "HOOK=%~1"
if /i "%HOOK%"=="preflight" (
  call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\hooks\\preflight_streaming.py --run-dir "%RUN_DIR%"
  exit /b !errorlevel!
)
if /i "%HOOK%"=="plot" (
  call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "%RUN_DIR%"
  exit /b !errorlevel!
)
if /i "%HOOK%"=="eval" (
  call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\hooks\\evaluate_tau_supply.py --run-dir "%RUN_DIR%"
  exit /b !errorlevel!
)
if /i "%HOOK%"=="archive" (
  call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\hooks\\archive_run.py --run-dir "%RUN_DIR%"
  exit /b !errorlevel!
)
echo.[warn] unknown hook: %HOOK%
exit /b 0

:run_worker_single
call :trace "run_worker_single: enter"
set "SWEEP_PART_INDEX=1"
set "SWEEP_PART_COUNT=1"
set "SWEEP_WORKER=1"
call "%PYTHON_EXEC_CMD%" scripts\\runsets\\common\\run_sweep_worker.py --sweep-list "!SWEEP_LIST_FILE!" --part-index 1 --part-count 1
exit /b !errorlevel!

:run_parallel_workers
call :trace "run_parallel_workers: enter"
set "JOB_PIDS="
set "JOB_COUNT=0"
set "WORKER_JOBS=%PARALLEL_JOBS%"
if defined SWEEP_WORKER_JOBS set "WORKER_JOBS=%SWEEP_WORKER_JOBS%"
call :normalize_int WORKER_JOBS 1
if "%WORKER_JOBS%"=="0" set "WORKER_JOBS=1"
if "%WORKER_JOBS%"=="1" (
  call :run_worker_single
  exit /b !errorlevel!
)
%LOG_INFO% persistent worker mode: jobs=%WORKER_JOBS% sleep=%PARALLEL_SLEEP_SEC%s
set "SWEEP_PART_COUNT=%WORKER_JOBS%"
for /L %%W in (1,1,%WORKER_JOBS%) do (
  call :launch_worker_job %%W %WORKER_JOBS%
)
call :wait_all
echo.[done] Parallel sweep completed [batch=!BATCH_SEED!, dir=!BATCH_DIR!].
exit /b 0

:launch_worker_job
set "WORKER_INDEX=%~1"
set "WORKER_COUNT=%~2"
if "%DEBUG%"=="1" echo.[DEBUG] launch_worker_job: worker=!WORKER_INDEX!/!WORKER_COUNT!
set "JOB_CMD_FILE=!TMP_ROOT!\marsdisk_worker_!WORKER_INDEX!.cmd"
set "WORKER_TMP_ROOT=!TMP_ROOT_BASE!\marsdisk_tmp_!RUN_TS!_!BATCH_SEED!_worker!WORKER_INDEX!"
> "!JOB_CMD_FILE!" echo @echo off
>> "!JOB_CMD_FILE!" echo set "SWEEP_WORKER=1"
>> "!JOB_CMD_FILE!" echo set "SWEEP_PART_INDEX=!WORKER_INDEX!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_PART_COUNT=!WORKER_COUNT!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_LIST_FILE=!SWEEP_LIST_FILE!"
>> "!JOB_CMD_FILE!" echo set "TMP_ROOT=!WORKER_TMP_ROOT!"
>> "!JOB_CMD_FILE!" echo set "BASE_OVERRIDES_FILE=!WORKER_TMP_ROOT!\marsdisk_overrides_base_!RUN_TS!_!BATCH_SEED!_worker!WORKER_INDEX!.txt"
>> "!JOB_CMD_FILE!" echo set "CASE_OVERRIDES_FILE=!WORKER_TMP_ROOT!\marsdisk_overrides_case_!RUN_TS!_!BATCH_SEED!_worker!WORKER_INDEX!.txt"
>> "!JOB_CMD_FILE!" echo set "MERGED_OVERRIDES_FILE=!WORKER_TMP_ROOT!\marsdisk_overrides_merged_!RUN_TS!_!BATCH_SEED!_worker!WORKER_INDEX!.txt"
>> "!JOB_CMD_FILE!" echo set "AUTO_JOBS=0"
>> "!JOB_CMD_FILE!" echo set "PARALLEL_JOBS=1"
>> "!JOB_CMD_FILE!" echo set "SKIP_PIP=1"
>> "!JOB_CMD_FILE!" echo set "REQUIREMENTS_INSTALLED=1"
>> "!JOB_CMD_FILE!" echo set "QUIET_MODE=!QUIET_MODE!"
>> "!JOB_CMD_FILE!" echo set "DEBUG=!DEBUG!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_EXE=!PYTHON_EXE!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_ARGS=!PYTHON_ARGS!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_EXEC_CMD=!PYTHON_EXEC_CMD!"
>> "!JOB_CMD_FILE!" echo set "BASE_CONFIG=!BASE_CONFIG!"
>> "!JOB_CMD_FILE!" echo set "BATCH_ROOT=!BATCH_ROOT!"
>> "!JOB_CMD_FILE!" echo set "BATCH_DIR=!BATCH_DIR!"
>> "!JOB_CMD_FILE!" echo set "BATCH_SEED=!BATCH_SEED!"
>> "!JOB_CMD_FILE!" echo set "RUN_TS=!RUN_TS!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_TAG=!SWEEP_TAG!"
>> "!JOB_CMD_FILE!" echo set "GIT_SHA=!GIT_SHA!"
>> "!JOB_CMD_FILE!" echo set "VENV_DIR=!VENV_DIR!"
>> "!JOB_CMD_FILE!" echo set "EXTRA_OVERRIDES_FILE=!EXTRA_OVERRIDES_FILE!"
>> "!JOB_CMD_FILE!" echo set "COOL_MODE=!COOL_MODE!"
>> "!JOB_CMD_FILE!" echo set "COOL_TO_K=!COOL_TO_K!"
>> "!JOB_CMD_FILE!" echo set "COOL_MARGIN_YEARS=!COOL_MARGIN_YEARS!"
>> "!JOB_CMD_FILE!" echo set "COOL_SEARCH_YEARS=!COOL_SEARCH_YEARS!"
>> "!JOB_CMD_FILE!" echo set "HOOKS_ENABLE=!HOOKS_ENABLE!"
>> "!JOB_CMD_FILE!" echo set "PLOT_ENABLE=!PLOT_ENABLE!"
>> "!JOB_CMD_FILE!" echo set "GEOMETRY_MODE=!GEOMETRY_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_MODE=!SUPPLY_MODE!"
>> "!JOB_CMD_FILE!" echo set "SHIELDING_MODE=!SHIELDING_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_INJECTION_MODE=!SUPPLY_INJECTION_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_TRANSPORT_MODE=!SUPPLY_TRANSPORT_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUBSTEP_FAST_BLOWOUT=!SUBSTEP_FAST_BLOWOUT!"
>> "!JOB_CMD_FILE!" echo set "SUBSTEP_MAX_RATIO=!SUBSTEP_MAX_RATIO!"
>> "!JOB_CMD_FILE!" echo set "STREAM_MEM_GB=!STREAM_MEM_GB!"
>> "!JOB_CMD_FILE!" echo set "ENABLE_PROGRESS=!ENABLE_PROGRESS!"
if defined SKIP_VENV >> "!JOB_CMD_FILE!" echo set "SKIP_VENV=!SKIP_VENV!"
>> "!JOB_CMD_FILE!" echo call "!PYTHON_EXEC_CMD!" scripts\\runsets\\common\\run_sweep_worker.py --sweep-list "!SWEEP_LIST_FILE!" --part-index !WORKER_INDEX! --part-count !WORKER_COUNT!
set "JOB_PID_TMP="
for /f "usebackq delims=" %%P in (`call "%PYTHON_EXEC_CMD%" "!WIN_PROCESS_PY!" launch --cmd "!JOB_CMD_FILE!" --window-style "!PARALLEL_WINDOW_STYLE!" --cwd "!JOB_CWD_USE!"`) do set "JOB_PID_TMP=%%P"
set "JOB_PID=!JOB_PID_TMP!"

if defined JOB_PID (
    echo !JOB_PID!| findstr /r "^[0-9][0-9]*$" >nul
    if !errorlevel! geq 1 (
        echo.[warn] failed to launch worker !WORKER_INDEX! - output: !JOB_PID!
        set "JOB_PID="
    ) else (
        set "JOB_PIDS=!JOB_PIDS! !JOB_PID!"
        set /a JOB_COUNT+=1
        echo.[info] launched worker !WORKER_INDEX! PID=!JOB_PID!
    )
) else (
    echo.[warn] failed to launch worker !WORKER_INDEX! - no PID returned
)
exit /b 0

:run_parallel
call :trace "run_parallel: enter"
set "JOB_PIDS="
set "JOB_COUNT=0"
%LOG_INFO% parallel mode: jobs=%PARALLEL_JOBS% sleep=%PARALLEL_SLEEP_SEC%s

if not defined SWEEP_LIST_FILE (
  echo.[error] sweep list file not set for parallel run
  exit /b 1
)
if not exist "%SWEEP_LIST_FILE%" (
  echo.[error] sweep list missing: "!SWEEP_LIST_FILE!"
  exit /b 1
)
set "PROGRESS_TOTAL=0"
set "PROGRESS_LAUNCHED=0"
set "PROGRESS_FAILED=0"
set "PROGRESS_LAST_DONE=-1"
set "PROGRESS_LAST_LAUNCHED=-1"
set "PROGRESS_MILESTONE_NEXT=%SWEEP_PROGRESS_MILESTONE_STEP%"
if "%SWEEP_PROGRESS%"=="1" (
  for /f "usebackq tokens=3 delims=:" %%C in (`find /c /v "" "!SWEEP_LIST_FILE!"`) do set "PROGRESS_TOTAL=%%C"
  call :normalize_int PROGRESS_TOTAL 0
  if "!PROGRESS_TOTAL!"=="0" (
    echo.[warn] sweep progress: case count unavailable for "!SWEEP_LIST_FILE!"
  ) else (
    call :progress_update
  )
)
for /f "usebackq tokens=1-5 delims= " %%A in ("!SWEEP_LIST_FILE!") do (
  call :launch_job %%A %%B %%C %%D %%E
)

call :wait_all
echo.[done] Parallel sweep completed [batch=!BATCH_SEED!, dir=!BATCH_DIR!].
exit /b 0

:launch_job
set "JOB_T=%~1"
set "JOB_EPS=%~2"
set "JOB_TAU=%~3"
set "JOB_I0=%~4"
set "JOB_MU=%~5"
if "%JOB_MU%"=="" set "JOB_MU=%SUPPLY_MU_ORBIT10PCT%"
set "JOB_SEED_TMP="
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: PYTHON_CMD=!PYTHON_CMD!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: NEXT_SEED_PY=!NEXT_SEED_PY!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: WIN_PROCESS_PY=!WIN_PROCESS_PY!
setlocal DisableDelayedExpansion
if "%DEBUG%"=="1" echo.[DEBUG] launch_job (DisableDelayedExpansion): PYTHON_CMD=%PYTHON_CMD%
if "%DEBUG%"=="1" echo.[DEBUG] launch_job (DisableDelayedExpansion): NEXT_SEED_PY=%NEXT_SEED_PY%
rem Use call to handle paths with spaces/unicode properly
for /f %%S in ('call "%PYTHON_EXEC_CMD%" "%NEXT_SEED_PY%" 2^>nul') do set "JOB_SEED_TMP=%%S"
if not defined JOB_SEED_TMP (
  for /f %%S in ('call "%PYTHON_EXEC_CMD%" "%NEXT_SEED_PY%"') do set "JOB_SEED_TMP=%%S"
)
endlocal & set "JOB_SEED=%JOB_SEED_TMP%"
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: JOB_SEED=!JOB_SEED!
call :wait_for_slot
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: after wait_for_slot
set "JOB_PID="
rem Generate a proper batch file with env vars on separate lines (avoids escaping issues)
set "JOB_CMD_FILE=!TMP_ROOT!\marsdisk_job_!JOB_T!_!JOB_EPS!_!JOB_TAU!_!JOB_I0!_!JOB_MU!.cmd"
> "!JOB_CMD_FILE!" echo @echo off
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_T=!JOB_T!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_EPS=!JOB_EPS!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_TAU=!JOB_TAU!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_I0=!JOB_I0!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_MU=!JOB_MU!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_SEED=!JOB_SEED!"
>> "!JOB_CMD_FILE!" echo set "RUN_ONE_MODE=1"
>> "!JOB_CMD_FILE!" echo set "AUTO_JOBS=0"
>> "!JOB_CMD_FILE!" echo set "PARALLEL_JOBS=1"
>> "!JOB_CMD_FILE!" echo set "SKIP_PIP=1"
>> "!JOB_CMD_FILE!" echo set "REQUIREMENTS_INSTALLED=1"
>> "!JOB_CMD_FILE!" echo set "QUIET_MODE=!QUIET_MODE!"
>> "!JOB_CMD_FILE!" echo set "DEBUG=!DEBUG!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_EXE=!PYTHON_EXE!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_ARGS=!PYTHON_ARGS!"
>> "!JOB_CMD_FILE!" echo set "BASE_CONFIG=!BASE_CONFIG!"
>> "!JOB_CMD_FILE!" echo set "BATCH_ROOT=!BATCH_ROOT!"
>> "!JOB_CMD_FILE!" echo set "BATCH_SEED=!BATCH_SEED!"
>> "!JOB_CMD_FILE!" echo set "RUN_TS=!RUN_TS!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_TAG=!SWEEP_TAG!"
>> "!JOB_CMD_FILE!" echo set "GIT_SHA=!GIT_SHA!"
>> "!JOB_CMD_FILE!" echo set "TMP_ROOT=!TMP_ROOT!"
>> "!JOB_CMD_FILE!" echo set "VENV_DIR=!VENV_DIR!"
>> "!JOB_CMD_FILE!" echo set "BASE_OVERRIDES_FILE=!BASE_OVERRIDES_FILE!"
>> "!JOB_CMD_FILE!" echo set "EXTRA_OVERRIDES_FILE=!EXTRA_OVERRIDES_FILE!"
>> "!JOB_CMD_FILE!" echo set "COOL_MODE=!COOL_MODE!"
>> "!JOB_CMD_FILE!" echo set "COOL_TO_K=!COOL_TO_K!"
>> "!JOB_CMD_FILE!" echo set "COOL_MARGIN_YEARS=!COOL_MARGIN_YEARS!"
>> "!JOB_CMD_FILE!" echo set "HOOKS_ENABLE=!HOOKS_ENABLE!"
>> "!JOB_CMD_FILE!" echo set "PLOT_ENABLE=!PLOT_ENABLE!"
>> "!JOB_CMD_FILE!" echo set "GEOMETRY_MODE=!GEOMETRY_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_MODE=!SUPPLY_MODE!"
>> "!JOB_CMD_FILE!" echo set "SHIELDING_MODE=!SHIELDING_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_INJECTION_MODE=!SUPPLY_INJECTION_MODE!"
>> "!JOB_CMD_FILE!" echo set "SUPPLY_TRANSPORT_MODE=!SUPPLY_TRANSPORT_MODE!"
if defined SKIP_VENV >> "!JOB_CMD_FILE!" echo set "SKIP_VENV=!SKIP_VENV!"
>> "!JOB_CMD_FILE!" echo call "!SCRIPT_SELF_USE!" --run-one
set "JOB_PID_TMP="
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: TMP_ROOT=!TMP_ROOT!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: JOB_CMD_FILE=!JOB_CMD_FILE!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: JOB_CWD_USE=!JOB_CWD_USE!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: SCRIPT_SELF_USE=!SCRIPT_SELF_USE!
if "%DEBUG%"=="1" echo.[DEBUG] launch_job: executing win_process.py
  set "JOB_PID_TMP="
  for /f "usebackq delims=" %%P in (`call "%PYTHON_EXEC_CMD%" "!WIN_PROCESS_PY!" launch --cmd "!JOB_CMD_FILE!" --window-style "!PARALLEL_WINDOW_STYLE!" --cwd "!JOB_CWD_USE!"`) do set "JOB_PID_TMP=%%P"
  if "%DEBUG%"=="1" echo.[DEBUG] launch_job: after python call, errorlevel=%errorlevel%, PID=!JOB_PID_TMP!
  rem Do not delete the job cmd file - the child process needs it
  set "JOB_PID=!JOB_PID_TMP!"

if defined JOB_PID (
    rem Check if JOB_PID is a number
    echo !JOB_PID!| findstr /r "^[0-9][0-9]*$" >nul
    if !errorlevel! geq 1 (
    echo.[warn] failed to launch job for T=!JOB_T! eps=!JOB_EPS! tau=!JOB_TAU! i0=!JOB_I0! mu=!JOB_MU! - output: !JOB_PID!
        set "JOB_PID="
        if "%SWEEP_PROGRESS%"=="1" set /a PROGRESS_FAILED+=1
    ) else (
        set "JOB_PIDS=!JOB_PIDS! !JOB_PID!"
        set /a JOB_COUNT+=1
        echo.[info] launched job T=!JOB_T! eps=!JOB_EPS! tau=!JOB_TAU! i0=!JOB_I0! mu=!JOB_MU! PID=!JOB_PID!
    )
) else (
    echo.[warn] failed to launch job for T=!JOB_T! eps=!JOB_EPS! tau=!JOB_TAU! i0=!JOB_I0! mu=!JOB_MU! - no PID returned
    if "%SWEEP_PROGRESS%"=="1" set /a PROGRESS_FAILED+=1
)
if "%SWEEP_PROGRESS%"=="1" (
  set /a PROGRESS_LAUNCHED+=1
  call :progress_update
)
exit /b 0

:wait_for_slot
call :refresh_jobs
call :normalize_int JOB_COUNT 0
call :normalize_int PARALLEL_JOBS 1
call :progress_update
if !JOB_COUNT! GEQ !PARALLEL_JOBS! (
  timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
  goto :wait_for_slot
)
exit /b 0

:refresh_jobs
set "JOB_COUNT=0"
if not defined JOB_PIDS exit /b 0
set "JOB_PIDS_TMP="
set "JOB_COUNT_TMP="
setlocal DisableDelayedExpansion
rem Use call to handle paths with spaces/unicode properly
for /f "usebackq tokens=1,2 delims=|" %%A in (`call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" alive`) do (
  set "JOB_PIDS_TMP=%%A"
  set "JOB_COUNT_TMP=%%B"
)
endlocal & set "JOB_PIDS=%JOB_PIDS_TMP%" & set "JOB_COUNT=%JOB_COUNT_TMP%"
call :normalize_int JOB_COUNT 0
if "%JOB_PIDS%"=="__NONE__" set "JOB_PIDS="
exit /b 0

:wait_all
call :refresh_jobs
call :normalize_int JOB_COUNT 0
call :progress_update
if "%JOB_COUNT%"=="0" exit /b 0
timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
goto :wait_all

:progress_update
if not "%SWEEP_PROGRESS%"=="1" exit /b 0
call :normalize_int PROGRESS_TOTAL 0
if "!PROGRESS_TOTAL!"=="0" exit /b 0
call :normalize_int PROGRESS_LAUNCHED 0
call :normalize_int JOB_COUNT 0
set /a PROGRESS_DONE=!PROGRESS_LAUNCHED!-!JOB_COUNT!
if !PROGRESS_DONE! LSS 0 set "PROGRESS_DONE=0"
if !PROGRESS_DONE! GTR !PROGRESS_TOTAL! set "PROGRESS_DONE=!PROGRESS_TOTAL!"
set /a PROGRESS_RUNNING=!JOB_COUNT!
if !PROGRESS_RUNNING! LSS 0 set "PROGRESS_RUNNING=0"
if "!PROGRESS_LAST_DONE!"=="!PROGRESS_DONE!" if "!PROGRESS_LAST_LAUNCHED!"=="!PROGRESS_LAUNCHED!" exit /b 0
set "PROGRESS_LAST_DONE=!PROGRESS_DONE!"
set "PROGRESS_LAST_LAUNCHED=!PROGRESS_LAUNCHED!"
set "PROGRESS_SUFFIX="
call :normalize_int PROGRESS_FAILED 0
if !PROGRESS_FAILED! GTR 0 set "PROGRESS_SUFFIX= failed=!PROGRESS_FAILED!"
set /a PROGRESS_PCT=0
if !PROGRESS_TOTAL! GTR 0 set /a PROGRESS_PCT=100*PROGRESS_DONE/PROGRESS_TOTAL
call :calc_eta_suffix !PROGRESS_DONE! !PROGRESS_TOTAL!
call :normalize_int SWEEP_PROGRESS_MILESTONE_STEP 25
if !SWEEP_PROGRESS_MILESTONE_STEP! LSS 1 set "SWEEP_PROGRESS_MILESTONE_STEP=25"
call :normalize_int PROGRESS_MILESTONE_NEXT 0
:progress_milestone_loop
if !PROGRESS_MILESTONE_NEXT! LEQ 0 goto progress_milestone_done
if !PROGRESS_PCT! GEQ !PROGRESS_MILESTONE_NEXT! (
  if !PROGRESS_MILESTONE_NEXT! LEQ 100 (
    echo.[info] sweep milestone: !PROGRESS_MILESTONE_NEXT!%% complete (!PROGRESS_DONE!/!PROGRESS_TOTAL!) !ETA_SUFFIX!
  )
  set /a PROGRESS_MILESTONE_NEXT+=SWEEP_PROGRESS_MILESTONE_STEP
  goto progress_milestone_loop
)
:progress_milestone_done
echo.[info] sweep progress: !PROGRESS_DONE!/!PROGRESS_TOTAL! complete (!PROGRESS_PCT!%%) running=!PROGRESS_RUNNING!!PROGRESS_SUFFIX! !ETA_SUFFIX!
exit /b 0

:calc_eta_suffix
set "ETA_DONE=%~1"
set "ETA_TOTAL=%~2"
set "ETA_SUFFIX="
call :normalize_int ETA_DONE 0
call :normalize_int ETA_TOTAL 0
if "!ETA_TOTAL!"=="0" exit /b 0
if "!ETA_DONE!"=="0" exit /b 0
if not defined SWEEP_START_SECS exit /b 0
if "!SWEEP_START_SECS!"=="0" exit /b 0
call :get_monotonic_seconds NOW_SECS
set /a ETA_ELAPSED=NOW_SECS-SWEEP_START_SECS
if !ETA_ELAPSED! LSS 0 set "ETA_ELAPSED=0"
set /a ETA_REMAIN=ETA_TOTAL-ETA_DONE
if !ETA_REMAIN! LSS 0 set "ETA_REMAIN=0"
set /a ETA_SEC=ETA_ELAPSED*ETA_REMAIN/ETA_DONE
call :format_duration ETA_SEC ETA_STR
set "ETA_SUFFIX=eta=!ETA_STR!"
exit /b 0

:get_monotonic_seconds
set "MONO_NAME=%~1"
set "MONO_VAL="
for /f "usebackq delims=" %%A in (`call "%PYTHON_EXEC_CMD%" -c "import time;print(int(time.monotonic()))"`) do set "MONO_VAL=%%A"
set "%MONO_NAME%=%MONO_VAL%"
call :normalize_int !MONO_NAME! 0
exit /b 0

:format_duration
set "DUR_SEC=%~1"
set "DUR_OUT_NAME=%~2"
call :normalize_int DUR_SEC 0
set /a DUR_DAYS=DUR_SEC/86400
set /a DUR_REM=DUR_SEC%%86400
set /a DUR_H=DUR_REM/3600
set /a DUR_REM=DUR_REM%%3600
set /a DUR_M=DUR_REM/60
set /a DUR_S=DUR_REM%%60
set "DUR_H_PAD=0%DUR_H%"
set "DUR_M_PAD=0%DUR_M%"
set "DUR_S_PAD=0%DUR_S%"
set "DUR_H_PAD=!DUR_H_PAD:~-2!"
set "DUR_M_PAD=!DUR_M_PAD:~-2!"
set "DUR_S_PAD=!DUR_S_PAD:~-2!"
if !DUR_DAYS! GTR 0 (
  set "DUR_STR=!DUR_DAYS!d !DUR_H_PAD!:!DUR_M_PAD!:!DUR_S_PAD!"
) else (
  set "DUR_STR=!DUR_H_PAD!:!DUR_M_PAD!:!DUR_S_PAD!"
)
set "%DUR_OUT_NAME%=%DUR_STR%"
exit /b 0

:normalize_int
set "NORM_NAME=%~1"
set "NORM_DEFAULT=%~2"
set "NORM_VAL=!%NORM_NAME%!"
set "NORM_VAL=!NORM_VAL:"=!"
if not "!NORM_VAL!"=="" for /f "tokens=1 delims=." %%Z in ("!NORM_VAL!") do set "NORM_VAL=%%Z"
if "!NORM_VAL!"=="" set "NORM_VAL=%NORM_DEFAULT%"
set "NORM_OK=1"
if "!NORM_OK!"=="1" for /f "delims=0123456789" %%Z in ("!NORM_VAL!") do set "NORM_OK=0"
if "!NORM_OK!"=="0" set "NORM_VAL=%NORM_DEFAULT%"
set "%NORM_NAME%=!NORM_VAL!"
exit /b 0

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
  if not "!LIST_OUT!"=="!LIST_RAW!" echo.[warn] %~1 sanitized: "!LIST_RAW!" -^> "!LIST_OUT!"
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
if !errorlevel! lss 1 (
  echo.[error] %TOK_NAME% token contains %%: %TOK_VAL%
  exit /b 1
)
exit /b 0

:trace
if "%TRACE_ENABLED%"=="0" exit /b 0
set "TRACE_MSG=%~1"
if "!TRACE_MSG!"=="" set "TRACE_MSG=trace"
echo.[trace] !TRACE_MSG!
if defined TRACE_LOG (
  >>"%TRACE_LOG%" echo.[trace] %DATE% %TIME% !TRACE_MSG!
)
exit /b 0

:trace_detail
if "%TRACE_DETAIL%"=="0" exit /b 0
call :trace "%~1"
exit /b 0

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=!errorlevel!"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b !MARSDISK_POPD_ERRORLEVEL!

:trim_python_exe
rem Trim trailing spaces from PYTHON_EXE
setlocal EnableDelayedExpansion
set "TRIM_VAL=!PYTHON_EXE!"
rem Remove leading/trailing quotes first
set "TRIM_VAL=!TRIM_VAL:"=!"
:trim_python_exe_loop
if "!TRIM_VAL:~-1!"==" " (
  set "TRIM_VAL=!TRIM_VAL:~0,-1!"
  goto :trim_python_exe_loop
)
endlocal & set "PYTHON_EXE=!TRIM_VAL!"
if "%DEBUG%"=="1" echo.[DEBUG] run_temp_supply_sweep: trimmed PYTHON_EXE=[%PYTHON_EXE%]
exit /b 0

endlocal
