@echo off
rem Windows CMD version of run_temp_supply_sweep.sh (logic preserved, output rooted under out/)
setlocal EnableExtensions EnableDelayedExpansion

if not defined DEBUG set "DEBUG=0"
if not defined TRACE_ENABLED set "TRACE_ENABLED=0"
if /i "%DEBUG%"=="1" set "TRACE_ENABLED=1"
if not defined TRACE_ECHO set "TRACE_ECHO=0"
if not defined TRACE_DETAIL set "TRACE_DETAIL=0"
if not defined QUIET_MODE set "QUIET_MODE=1"
if /i "%DEBUG%"=="1" set "QUIET_MODE=0"
if /i "%TRACE_ENABLED%"=="1" set "QUIET_MODE=0"
set "SCRIPT_REV=run_temp_supply_sweep_cmd_trace_v2"

if not defined PYTHON_ALLOW_LAUNCHER set "PYTHON_ALLOW_LAUNCHER=0"

if not defined PYTHON_EXE (
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 (
      py -3.11 -c "import sys" >nul 2>&1
      if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ALLOW_LAUNCHER=1"
        if not defined PYTHON_ARGS (
          set "PYTHON_ARGS=-3.11"
        ) else (
          set "PYTHON_ARGS_NEEDS_VER=1"
          if /i "!PYTHON_ARGS:~0,2!"=="-3" set "PYTHON_ARGS_NEEDS_VER=0"
          if /i "!PYTHON_ARGS:~0,2!"=="-2" set "PYTHON_ARGS_NEEDS_VER=0"
          if "!PYTHON_ARGS_NEEDS_VER!"=="1" set "PYTHON_ARGS=-3.11 !PYTHON_ARGS!"
        )
      )
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] python3.11/python not found in PATH
    exit /b 1
  )
)

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

set "PYTHON_ARGS_SET=0"
if defined PYTHON_ARGS set "PYTHON_ARGS_SET=1"
set "PYTHON_EXE_RAW=%PYTHON_EXE%"
set "PYTHON_EXE_RAW=%PYTHON_EXE_RAW:"=%"
if "!PYTHON_EXE_RAW:~0,1!"=="-" (
  if "!PYTHON_ARGS_SET!"=="0" (
    set "PYTHON_ARGS=!PYTHON_EXE_RAW!"
    set "PYTHON_ARGS_SET=1"
  )
  set "PYTHON_EXE_RAW="
)
if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
set "PYTHON_EXE=!PYTHON_EXE_RAW!"
set "PYTHON_HAS_SPACE=0"
if not "!PYTHON_EXE_RAW: =!"=="!PYTHON_EXE_RAW!" set "PYTHON_HAS_SPACE=1"
set "PYTHON_RAW_LOOKS_PATH=0"
for %%I in ("!PYTHON_EXE_RAW!") do (
  if not "%%~pI"=="" set "PYTHON_RAW_LOOKS_PATH=1"
  if not "%%~dI"=="" set "PYTHON_RAW_LOOKS_PATH=1"
)
if "!PYTHON_HAS_SPACE!"=="1" if "!PYTHON_RAW_LOOKS_PATH!"=="0" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_EXE_RAW!") do (
    set "PYTHON_EXE=%%A"
    if "!PYTHON_ARGS_SET!"=="0" (
      set "PYTHON_ARGS=%%B"
    ) else (
      if not "%%B"=="" (
        if "!PYTHON_ARGS!"=="" (
          set "PYTHON_ARGS=%%B"
        ) else (
          set "PYTHON_ARGS=%%B !PYTHON_ARGS!"
        )
      )
    )
  )
)
if "!PYTHON_HAS_SPACE!"=="1" if "!PYTHON_RAW_LOOKS_PATH!"=="1" if "!PYTHON_ARGS_SET!"=="0" (
  echo.[warn] PYTHON_EXE looks like a path with spaces; quote it or set PYTHON_ARGS.
)
set "PYTHON_EXE_NAME="
for %%I in ("!PYTHON_EXE!") do set "PYTHON_EXE_NAME=%%~nxI"
if /i "!PYTHON_EXE!"=="py" set "PYTHON_ALLOW_LAUNCHER=1"
if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_ALLOW_LAUNCHER=1"
if /i "!PYTHON_EXE!"=="py" if not "!PYTHON_ALLOW_LAUNCHER!"=="1" set "PYTHON_EXE="
if /i "!PYTHON_EXE_NAME!"=="py.exe" if not "!PYTHON_ALLOW_LAUNCHER!"=="1" set "PYTHON_EXE="
if not defined PYTHON_EXE (
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] PYTHON_EXE is empty after normalization
    call :popd_safe
    exit /b 1
  )
)
set "PYTHON_ARGS_FIRST="
set "PYTHON_ARGS_REST="
if not "!PYTHON_ARGS!"=="" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_ARGS!") do (
    set "PYTHON_ARGS_FIRST=%%A"
    set "PYTHON_ARGS_REST=%%B"
  )
)
set "PYTHON_PYVER_ARG=0"
if not "!PYTHON_ARGS_FIRST!"=="" (
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-3" set "PYTHON_PYVER_ARG=1"
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-2" set "PYTHON_PYVER_ARG=1"
)
if "!PYTHON_PYVER_ARG!"=="1" (
  set "PYTHON_KEEP_PYVER_ARG=0"
  if "!PYTHON_ALLOW_LAUNCHER!"=="1" (
    if /i "!PYTHON_EXE!"=="py" set "PYTHON_KEEP_PYVER_ARG=1"
    if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_KEEP_PYVER_ARG=1"
  )
  if "!PYTHON_KEEP_PYVER_ARG!"=="0" (
    if not "!PYTHON_ARGS_FIRST!"=="" echo.[warn] PYTHON_ARGS includes py launcher version flag; dropping it - use python3.11 instead.
    set "PYTHON_ARGS=!PYTHON_ARGS_REST!"
  )
)
set "PYTHON_LOOKS_PATH=0"
for %%I in ("!PYTHON_EXE!") do (
  if not "%%~pI"=="" set "PYTHON_LOOKS_PATH=1"
  if not "%%~dI"=="" set "PYTHON_LOOKS_PATH=1"
)
if "!PYTHON_LOOKS_PATH!"=="1" (
  if not exist "!PYTHON_EXE!" (
    set "PYTHON_FALLBACK="
    for %%P in (python3.11 python) do (
      if not defined PYTHON_FALLBACK (
        where %%P >nul 2>&1
        if not errorlevel 1 set "PYTHON_FALLBACK=%%P"
      )
    )
    if defined PYTHON_FALLBACK (
      echo.[warn] python path missing; falling back to !PYTHON_FALLBACK!
      set "PYTHON_EXE=!PYTHON_FALLBACK!"
      if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
    ) else (
      echo.[error] resolved python executable not found: "!PYTHON_EXE!"
      call :popd_safe
      exit /b 1
    )
  )
) else (
  where !PYTHON_EXE! >nul 2>&1
  if errorlevel 1 (
    set "PYTHON_FALLBACK="
    for %%P in (python3.11 python) do (
      if not defined PYTHON_FALLBACK (
        where %%P >nul 2>&1
        if not errorlevel 1 set "PYTHON_FALLBACK=%%P"
      )
    )
    if defined PYTHON_FALLBACK (
      echo.[warn] !PYTHON_EXE! not found; falling back to !PYTHON_FALLBACK!
      set "PYTHON_EXE=!PYTHON_FALLBACK!"
      if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
    ) else (
      echo.[error] !PYTHON_EXE! not found in PATH
      call :popd_safe
      exit /b 1
    )
  )
)
set "PYTHON_ARGS_FIRST="
set "PYTHON_ARGS_REST="
if not "!PYTHON_ARGS!"=="" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_ARGS!") do (
    set "PYTHON_ARGS_FIRST=%%A"
    set "PYTHON_ARGS_REST=%%B"
  )
)
set "PYTHON_PYVER_ARG=0"
if not "!PYTHON_ARGS_FIRST!"=="" (
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-3" set "PYTHON_PYVER_ARG=1"
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-2" set "PYTHON_PYVER_ARG=1"
)
if "!PYTHON_PYVER_ARG!"=="1" (
  set "PYTHON_KEEP_PYVER_ARG=0"
  if "!PYTHON_ALLOW_LAUNCHER!"=="1" (
    if /i "!PYTHON_EXE!"=="py" set "PYTHON_KEEP_PYVER_ARG=1"
    if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_KEEP_PYVER_ARG=1"
  )
  if "!PYTHON_KEEP_PYVER_ARG!"=="0" (
    if not "!PYTHON_ARGS_FIRST!"=="" echo.[warn] PYTHON_ARGS includes py launcher version flag; dropping it - use python3.11 instead.
    set "PYTHON_ARGS=!PYTHON_ARGS_REST!"
  )
)
set "PYTHON_EXE_QUOTED=!PYTHON_EXE!"
if not "!PYTHON_EXE: =!"=="!PYTHON_EXE!" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
if not "!PYTHON_ARGS!"=="" set "PYTHON_CMD=!PYTHON_EXE_QUOTED! !PYTHON_ARGS!"
set "PYTHON_CMD_SANITY=1"
if not defined PYTHON_EXE set "PYTHON_CMD_SANITY=0"
if "!PYTHON_EXE:~0,1!"=="-" set "PYTHON_CMD_SANITY=0"
if "!PYTHON_CMD:~0,1!"=="-" set "PYTHON_CMD_SANITY=0"
if "!PYTHON_CMD_SANITY!"=="0" (
  echo.[warn] python command invalid; resetting to python in PATH
  set "PYTHON_EXE="
  set "PYTHON_ARGS="
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] python3.11/python not found in PATH
    call :popd_safe
    exit /b 1
  )
  set "PYTHON_EXE_QUOTED=!PYTHON_EXE!"
  if not "!PYTHON_EXE: =!"=="!PYTHON_EXE!" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
  set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
)
set "PYTHON_VERSION_OK=0"
!PYTHON_CMD! -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_VERSION_OK=1"

if "!PYTHON_VERSION_OK!"=="0" (
  rem py launcher fallback disabled.
)

if "!PYTHON_VERSION_OK!"=="0" (
  echo.[error] python 3.11+ is required. Install Python 3.11 or set PYTHON_EXE.
  echo.[error] Example: set PYTHON_EXE=python3.11
  call :popd_safe
  exit /b 1
)
set "PYTHON_BOOT_CMD=%PYTHON_CMD%"

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
) else (
  set "LOG_SETUP=echo.[setup]"
  set "LOG_INFO=echo.[info]"
  set "LOG_SYS=echo.[sys]"
  set "LOG_CONFIG=echo.[config]"
  set "LOG_RUN=echo.[run]"
)
%LOG_SETUP% script_path=%~f0
%LOG_SETUP% cwd=%CD%

rem ---------- setup ----------
if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
if not defined RUN_TS for /f %%A in ('%PYTHON_CMD% scripts\\runsets\\common\\timestamp.py') do set "RUN_TS=%%A"
if defined RUN_TS (
  set "RUN_TS_RAW=!RUN_TS!"
  rem Normalize to a filename-safe token in case a pre-set RUN_TS includes separators.
  set "RUN_TS=!RUN_TS::=!"
  set "RUN_TS=!RUN_TS: =_!"
  set "RUN_TS=!RUN_TS:/=-!"
  set "RUN_TS=!RUN_TS:\=-!"
  set "RUN_TS=!RUN_TS:&=_!"
  set "RUN_TS=!RUN_TS:|=_!"
  set "RUN_TS=!RUN_TS:<=_!"
  set "RUN_TS=!RUN_TS:>=_!"
  set "RUN_TS=!RUN_TS:?=_!"
  set "RUN_TS=!RUN_TS:*=_!"
  set "RUN_TS=!RUN_TS:!=_!"
  if not "!RUN_TS!"=="!RUN_TS_RAW!" echo.[warn] RUN_TS sanitized: "!RUN_TS_RAW!" -> "!RUN_TS!"
)
set "TMP_ROOT_BASE=%TEMP%"
set "TMP_SOURCE=TEMP"
if "%TMP_ROOT_BASE%"=="" (
  set "TMP_ROOT_BASE=%CD%\tmp"
  set "TMP_SOURCE=fallback"
)
if not exist "%TMP_ROOT_BASE%" mkdir "%TMP_ROOT_BASE%" >nul 2>&1
if not exist "%TMP_ROOT_BASE%" (
  set "TMP_ROOT_BASE=%CD%\tmp"
  set "TMP_SOURCE=fallback"
  if not exist "%TMP_ROOT_BASE%" mkdir "%TMP_ROOT_BASE%" >nul 2>&1
)
if not exist "%TMP_ROOT_BASE%" (
  echo.[error] temp_root unavailable: "%TMP_ROOT_BASE%"
  call :popd_safe
  exit /b 1
)
if not defined GIT_SHA for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
if not defined GIT_SHA set "GIT_SHA=nogit"
if not defined BATCH_SEED (
  set "BATCH_SEED_TMP="
  setlocal DisableDelayedExpansion
  for /f %%A in ('%PYTHON_CMD% "%NEXT_SEED_PY%"') do set "BATCH_SEED_TMP=%%A"
  endlocal & set "BATCH_SEED=%BATCH_SEED_TMP%"
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
  if not defined TRACE_LOG set "TRACE_LOG=%TMP_ROOT%\\marsdisk_trace_%RUN_TS%_%BATCH_SEED%.log"
  > "%TRACE_LOG%" echo.[trace] start script=%~f0 rev=%SCRIPT_REV%
  if "%TRACE_DETAIL%"=="1" echo.[trace] log=%TRACE_LOG%
)
if "%TRACE_ENABLED%"=="1" if "%TRACE_ECHO%"=="1" (
  echo.[trace] echo-on enabled
  echo on
)
call :trace "setup: env ready"
set "TMP_TEST=%TMP_ROOT%\\marsdisk_tmp_test_%RUN_TS%_%BATCH_SEED%.txt"
> "%TMP_TEST%" echo ok
if not exist "%TMP_TEST%" (
  echo.[error] temp_root write test failed: "%TMP_TEST%"
  echo.[error] temp_root=%TMP_ROOT%
  call :popd_safe
  exit /b 1
)
del "%TMP_TEST%"

rem Output root defaults to out/ unless BATCH_ROOT/OUT_ROOT is set.
if not defined BATCH_ROOT if defined OUT_ROOT set "BATCH_ROOT=%OUT_ROOT%"
if not defined BATCH_ROOT set "BATCH_ROOT=out"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep"
%LOG_SETUP% Output root: %BATCH_ROOT%

if not exist "%VENV_DIR%\Scripts\python.exe" (
  %LOG_SETUP% Creating virtual environment in %VENV_DIR%...
  !PYTHON_BOOT_CMD! -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if "%SKIP_PIP%"=="1" (
  %LOG_SETUP% SKIP_PIP=1; skipping dependency install.
) else if exist "%REQ_FILE%" (
  %LOG_SETUP% Installing/upgrading dependencies from %REQ_FILE% ...
  %PYTHON_CMD% -m pip install --upgrade pip
  %PYTHON_CMD% -m pip install -r "%REQ_FILE%"
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
rem Sweep-parallel primary: keep cell-parallel off to avoid nested parallelism.
if "%SWEEP_PARALLEL%"=="1" (
  set "MARSDISK_CELL_PARALLEL=0"
  set "MARSDISK_CELL_JOBS=1"
  if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=1"
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
if /i "%MARSDISK_CELL_JOBS%"=="auto" (
  set "CELL_CPU_LOGICAL="
  set "CELL_MEM_TOTAL_GB="
  set "CELL_MEM_FRACTION_USED="
  set "CELL_CPU_FRACTION_USED="
  set "CELL_STREAM_MEM_GB="
  set "CELL_THREAD_LIMIT_AUTO="
  for /f "usebackq tokens=1-7 delims=|" %%A in (`%PYTHON_CMD% scripts\\runsets\\common\\calc_cell_jobs.py`) do (
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
  if defined CELL_JOBS_RAW echo.[warn] MARSDISK_CELL_JOBS invalid: "%CELL_JOBS_RAW%" -> 1
  set "MARSDISK_CELL_JOBS=1"
)
if "%MARSDISK_CELL_JOBS%"=="0" set "MARSDISK_CELL_JOBS=1"
if /i "%PARALLEL_MODE%"=="numba" (
  set "CPU_TARGET_CORES="
  for /f "usebackq tokens=1,2 delims=|" %%A in (`%PYTHON_CMD% scripts\\runsets\\common\\calc_cpu_target_jobs.py`) do (
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
if /i "%CELL_THREAD_LIMIT%"=="auto" (
  if defined CELL_THREAD_LIMIT_AUTO (
    set "CELL_THREAD_LIMIT=%CELL_THREAD_LIMIT_AUTO%"
  ) else (
    for /f %%A in ('%PYTHON_CMD% scripts\\runsets\\common\\calc_thread_limit.py') do set "CELL_THREAD_LIMIT=%%A"
  )
)
if "%CELL_THREAD_LIMIT%"=="1" if "%CELL_THREAD_LIMIT_DEFAULT%"=="1" (
  if defined CELL_THREAD_LIMIT_AUTO set "CELL_THREAD_LIMIT=%CELL_THREAD_LIMIT_AUTO%"
)
if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=1"
set "CELL_THREAD_OK=1"
for /f "delims=0123456789" %%A in ("%CELL_THREAD_LIMIT%") do set "CELL_THREAD_OK=0"
if "%CELL_THREAD_OK%"=="0" (
  if defined CELL_THREAD_LIMIT_RAW echo.[warn] CELL_THREAD_LIMIT invalid: "%CELL_THREAD_LIMIT_RAW%" -> 1
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
set "EPS_LIST=1.0 0.5 0.1"
set "TAU_LIST=1.0 0.5 0.1"

if defined STUDY_FILE (
  if exist "!STUDY_FILE!" (
    set "STUDY_SET=!TMP_ROOT!\\marsdisk_study_!RUN_TS!_!BATCH_SEED!.cmd"
    %PYTHON_CMD% scripts\\runsets\\common\\read_study_overrides.py --study "!STUDY_FILE!" > "!STUDY_SET!"
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
  call :popd_safe
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
  for /f "usebackq tokens=1-3 delims=|" %%A in (`%PYTHON_CMD% scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
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
  if defined PARALLEL_JOBS_RAW echo.[warn] PARALLEL_JOBS invalid: "%PARALLEL_JOBS_RAW%" -> 1
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
    if "%CPU_TARGET_OK%"=="1" (
      if not defined CELL_CPU_LOGICAL (
        if defined NUMBER_OF_PROCESSORS set "CELL_CPU_LOGICAL=%NUMBER_OF_PROCESSORS%"
      )
      if defined CELL_CPU_LOGICAL (
        for /f "usebackq tokens=1,2 delims=|" %%A in (`%PYTHON_CMD% scripts\\runsets\\common\\calc_cpu_target_jobs.py`) do (
          set "CPU_TARGET_CORES=%%A"
          set "PARALLEL_JOBS_TARGET=%%B"
          if not "!PARALLEL_JOBS_TARGET!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET=%%Z"
        )
        set "PARALLEL_JOBS_TARGET_OK=1"
        if "!PARALLEL_JOBS_TARGET!"=="" set "PARALLEL_JOBS_TARGET_OK=0"
        if "!PARALLEL_JOBS_TARGET_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET_OK=0"
        if "!PARALLEL_JOBS_TARGET_OK!"=="1" (
        if "!PARALLEL_JOBS_DEFAULT!"=="1" if "!PARALLEL_JOBS!"=="1" if !PARALLEL_JOBS_TARGET! GTR 1 (
          if /i "!CPU_UTIL_RESPECT_MEM!"=="1" (
            for /f "usebackq tokens=1-3 delims=|" %%A in (`%PYTHON_CMD% scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
              set "PARALLEL_JOBS_MEM=%%C"
              if not "!PARALLEL_JOBS_MEM!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM=%%Z"
            )
          set "PARALLEL_JOBS_MEM_OK=1"
          if "!PARALLEL_JOBS_MEM!"=="" set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" (
            if !PARALLEL_JOBS_TARGET! GTR !PARALLEL_JOBS_MEM! set "PARALLEL_JOBS_TARGET=!PARALLEL_JOBS_MEM!"
          )
          )
          if !PARALLEL_JOBS_TARGET! GTR 1 (
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
%LOG_CONFIG% external supply: mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% mu_reference_tau=%SUPPLY_MU_REFERENCE_TAU% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION% (epsilon_mix swept per EPS_LIST)
%LOG_CONFIG% optical_depth: tau0_target_list=%TAU_LIST% tau_stop=%OPTICAL_TAU_STOP% tau_stop_tol=%OPTICAL_TAU_STOP_TOL%
%LOG_CONFIG% fast blowout substep: enabled=%SUBSTEP_FAST_BLOWOUT% substep_max_ratio=%SUBSTEP_MAX_RATIO%
%LOG_CONFIG% !COOL_STATUS!
%LOG_CONFIG% cooling driver mode: %COOL_MODE% (slab: T^-3, hyodo: linear flux)
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

call :trace_detail "base_overrides_file=%BASE_OVERRIDES_FILE%"
call :trace_detail "base overrides: python build"
%PYTHON_CMD% scripts\\runsets\\common\\write_base_overrides.py --out "%BASE_OVERRIDES_FILE%"
if errorlevel 1 (
  echo.[error] failed to build base overrides
  call :popd_safe
  exit /b 1
)
if not exist "%BASE_OVERRIDES_FILE%" (
  echo.[error] base overrides file missing: "%BASE_OVERRIDES_FILE%"
  call :popd_safe
  exit /b 1
)
call :trace_detail "base overrides: python done"

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
  set "T_LIST=%RUN_ONE_T%"
  set "EPS_LIST=%RUN_ONE_EPS%"
  set "TAU_LIST=%RUN_ONE_TAU%"
  if defined RUN_ONE_SEED set "SEED_OVERRIDE=%RUN_ONE_SEED%"
  set "PARALLEL_JOBS=1"
  set "AUTO_JOBS=0"
  %LOG_INFO% run-one mode: T=%RUN_ONE_T% eps=%RUN_ONE_EPS% tau=%RUN_ONE_TAU% seed=%RUN_ONE_SEED%
)

set "SWEEP_LIST_FILE=%TMP_ROOT%\\marsdisk_sweep_list_%RUN_TS%_%BATCH_SEED%.txt"
call :trace_detail "sweep list file=%SWEEP_LIST_FILE%"
%PYTHON_CMD% scripts\\runsets\\common\\write_sweep_list.py --out "%SWEEP_LIST_FILE%"
if errorlevel 1 (
  echo.[error] failed to build sweep list
  call :popd_safe
  exit /b 1
)
if not exist "%SWEEP_LIST_FILE%" (
  echo.[error] sweep list missing: "%SWEEP_LIST_FILE%"
  call :popd_safe
  exit /b 1
)

call :trace_detail "parallel check"
if "%SWEEP_PARALLEL%"=="0" (
  call :trace_detail "sweep parallel disabled"
) else if not "%PARALLEL_JOBS%"=="1" (
  if not defined RUN_ONE_MODE (
    call :trace_detail "dispatch parallel"
    call :run_parallel
    call :popd_safe
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
    for /f %%S in ('%PYTHON_CMD% scripts\\runsets\\common\\next_seed.py') do set "SEED=%%S"
  )
  set "TITLE=T!T!_eps!EPS_TITLE!_tau!TAU_TITLE!"
  set "OUTDIR=%BATCH_DIR%\!TITLE!"
  %LOG_RUN% T=!T! eps=!EPS! tau=!TAU! -^> !OUTDIR! (batch=%BATCH_SEED%, seed=!SEED!)
      rem Show supply rate info (skip Python calc to avoid cmd.exe delayed expansion issues)
      %LOG_INFO% epsilon_mix=!EPS!; mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION%
      %LOG_INFO% shielding: mode=%SHIELDING_MODE% fixed_tau1_sigma=%SHIELDING_SIGMA% auto_max_margin=%SHIELDING_AUTO_MAX_MARGIN%
      if "!EPS!"=="0.1" %LOG_INFO% epsilon_mix=0.1 is a low-supply extreme case; expect weak blowout/sinks

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
      if defined STREAM_MEM_GB (
        >>"%CASE_OVERRIDES_FILE%" echo io.streaming.memory_limit_gb=%STREAM_MEM_GB%
      )

      rem Override priority: base defaults ^< overrides file ^< per-case overrides.
      if "%EXTRA_OVERRIDES_EXISTS%"=="1" (
        %PYTHON_CMD% %OVERRIDE_BUILDER% --file "%BASE_OVERRIDES_FILE%" --file "%EXTRA_OVERRIDES_FILE%" --file "%CASE_OVERRIDES_FILE%" > "%MERGED_OVERRIDES_FILE%"
      ) else (
        %PYTHON_CMD% %OVERRIDE_BUILDER% --file "%BASE_OVERRIDES_FILE%" --file "%CASE_OVERRIDES_FILE%" > "%MERGED_OVERRIDES_FILE%"
      )

      rem Assemble the run command on a single line (avoid carets in optional blocks).
      rem Use overrides file to keep cmd line length manageable.
      set RUN_CMD=%PYTHON_CMD% -m marsdisk.run --config "%BASE_CONFIG%" --quiet --overrides-file "%MERGED_OVERRIDES_FILE%"
      if "%ENABLE_PROGRESS%"=="1" set RUN_CMD=!RUN_CMD! --progress

      !RUN_CMD!

      if errorlevel 1 (
        echo.[warn] run command exited with status !errorlevel!; attempting plots anyway
      )

      if "%PLOT_ENABLE%"=="0" (
        %LOG_INFO% PLOT_ENABLE=0; skipping quicklook
      ) else (
        set "RUN_DIR=!OUTDIR!"
        call :trace_detail "quicklook: start"
        %PYTHON_CMD% scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "!RUN_DIR!"
        if errorlevel 1 (
          echo.[warn] quicklook failed [rc=!errorlevel!]
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
  call :popd_safe
  exit /b 1
)

call :popd_safe
call :trace "done"
exit /b %errorlevel%

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
  %PYTHON_CMD% scripts\\runsets\\common\\hooks\\preflight_streaming.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="plot" (
  %PYTHON_CMD% scripts\\runsets\\common\\hooks\\plot_sweep_run.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="eval" (
  %PYTHON_CMD% scripts\\runsets\\common\\hooks\\evaluate_tau_supply.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
if /i "%HOOK%"=="archive" (
  %PYTHON_CMD% scripts\\runsets\\common\\hooks\\archive_run.py --run-dir "%RUN_DIR%"
  exit /b %errorlevel%
)
echo.[warn] unknown hook: %HOOK%
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
  echo.[error] sweep list missing: "%SWEEP_LIST_FILE%"
  exit /b 1
)
for /f "usebackq tokens=1-3 delims= " %%A in ("%SWEEP_LIST_FILE%") do (
  call :launch_job %%A %%B %%C
)

call :wait_all
echo.[done] Parallel sweep completed [batch=%BATCH_SEED%, dir=%BATCH_DIR%].
exit /b 0

:launch_job
set "JOB_T=%~1"
set "JOB_EPS=%~2"
set "JOB_TAU=%~3"
set "JOB_SEED_TMP="
setlocal DisableDelayedExpansion
for /f %%S in ('%PYTHON_CMD% "%NEXT_SEED_PY%"') do set "JOB_SEED_TMP=%%S"
endlocal & set "JOB_SEED=%JOB_SEED_TMP%"
call :wait_for_slot
set "JOB_PID="
  set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& set AUTO_JOBS=0&& set PARALLEL_JOBS=1&& set SKIP_PIP=1&& call ""!SCRIPT_SELF_USE!"" --run-one"
set "JOB_PID_TMP="
setlocal DisableDelayedExpansion
for /f "usebackq delims=" %%P in (`%PYTHON_CMD% "%WIN_PROCESS_PY%" launch --window-style "%PARALLEL_WINDOW_STYLE%" --cwd "%JOB_CWD_USE%"`) do set "JOB_PID_TMP=%%P"
endlocal & set "JOB_PID=%JOB_PID_TMP%"
if defined JOB_PID set "JOB_PIDS=!JOB_PIDS! !JOB_PID!"
if not defined JOB_PID echo.[warn] failed to launch job for T=!JOB_T! eps=!JOB_EPS! tau=!JOB_TAU! - check Python availability
exit /b 0

:wait_for_slot
call :refresh_jobs
call :normalize_int JOB_COUNT 0
call :normalize_int PARALLEL_JOBS 1
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
for /f "usebackq tokens=1,2 delims=|" %%A in (`%PYTHON_CMD% "%WIN_PROCESS_PY%" alive`) do (
  set "JOB_PIDS_TMP=%%A"
  set "JOB_COUNT_TMP=%%B"
)
endlocal & set "JOB_PIDS=%JOB_PIDS_TMP%" & set "JOB_COUNT=%JOB_COUNT_TMP%"
call :normalize_int JOB_COUNT 0
if "%JOB_PIDS%"=="__NONE__" set "JOB_PIDS="
exit /b 0

:wait_all
call :refresh_jobs
if "%JOB_COUNT%"=="0" exit /b 0
timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
goto :wait_all

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

:trace_detail
if "%TRACE_DETAIL%"=="0" exit /b 0
call :trace "%~1"
exit /b 0

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%

endlocal
