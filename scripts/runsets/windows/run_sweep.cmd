@echo off
rem Run a temp_supply sweep (1D default).
setlocal EnableExtensions EnableDelayedExpansion

set "CONFIG_PATH=scripts\runsets\common\base.yml"
set "OVERRIDES_PATH=scripts\runsets\windows\overrides.txt"
set "STUDY_PATH="
set "OUT_ROOT="
set "GEOMETRY_MODE=1D"
set "DRY_RUN=0"
set "NO_PLOT=0"
set "NO_EVAL=0"
set "NO_PREFLIGHT=0"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--study" (
  set "STUDY_PATH=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--config" (
  set "CONFIG_PATH=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--overrides" (
  set "OVERRIDES_PATH=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--out-root" (
  set "OUT_ROOT=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--no-plot" (
  set "NO_PLOT=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--no-eval" (
  set "NO_EVAL=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--no-preflight" (
  set "NO_PREFLIGHT=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage

echo.[error] Unknown option: %~1
:usage
echo Usage: run_sweep.cmd [--study ^<path^>] [--config ^<path^>] [--overrides ^<path^>]
 echo.           [--out-root ^<path^>] [--dry-run] [--no-plot] [--no-eval] [--no-preflight]
exit /b 1

:args_done

if not defined HOOKS_ENABLE set "HOOKS_ENABLE=plot,eval,archive"
if not defined HOOKS_STRICT set "HOOKS_STRICT=0"
if not defined PLOT_ENABLE set "PLOT_ENABLE=1"

set "HOOKS_RAW=%HOOKS_ENABLE%"
if not defined HOOKS_RAW set "HOOKS_RAW=plot,eval"
set "HOOKS_ENABLE="
for %%H in (%HOOKS_RAW:,= %) do (
  set "HOOK=%%H"
  set "SKIP="
  if /i "!HOOK!"=="plot" if "%NO_PLOT%"=="1" set "SKIP=1"
  if /i "!HOOK!"=="eval" if "%NO_EVAL%"=="1" set "SKIP=1"
  if /i "!HOOK!"=="preflight" if "%NO_PREFLIGHT%"=="1" set "SKIP=1"
  if not defined SKIP (
    if defined HOOKS_ENABLE (
      set "HOOKS_ENABLE=!HOOKS_ENABLE!,!HOOK!"
    ) else (
      set "HOOKS_ENABLE=!HOOK!"
    )
  )
)

set "USE_PLOT_HOOK=0"
for %%H in (%HOOKS_ENABLE:,= %) do (
  if /i "%%H"=="plot" set "USE_PLOT_HOOK=1"
)
if "%NO_PLOT%"=="1" set "PLOT_ENABLE=0"
if "%USE_PLOT_HOOK%"=="1" set "PLOT_ENABLE=0"

set "BASE_CONFIG=%CONFIG_PATH%"
set "EXTRA_OVERRIDES_FILE=%OVERRIDES_PATH%"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"
set "GEOMETRY_MODE=%GEOMETRY_MODE%"
if not defined GEOMETRY_NR set "GEOMETRY_NR=32"
if not defined SHIELDING_MODE set "SHIELDING_MODE=off"
if not defined SUPPLY_MU_REFERENCE_TAU set "SUPPLY_MU_REFERENCE_TAU=1.0"
if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"
if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=off"
if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=direct"
if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=off"
if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=hard"
if not defined AUTO_JOBS set "AUTO_JOBS=1"
if not defined PARALLEL_JOBS (
  if "!AUTO_JOBS!"=="1" (
    rem Leave undefined to allow auto sizing in run_temp_supply_sweep.cmd
  ) else (
    set "PARALLEL_JOBS=1"
  )
)
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"
if not defined MARSDISK_CELL_PARALLEL set "MARSDISK_CELL_PARALLEL=1"
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
if not defined MARSDISK_CELL_JOBS (
  if defined NUMBER_OF_PROCESSORS (
    set "MARSDISK_CELL_JOBS=%NUMBER_OF_PROCESSORS%"
  ) else (
    set "MARSDISK_CELL_JOBS=1"
  )
)

if defined STUDY_PATH set "STUDY_FILE=%STUDY_PATH%"
if defined OUT_ROOT set "OUT_ROOT=%OUT_ROOT%"

set "REPO_ROOT=%~dp0..\..\.."
set "RUN_TS_SOURCE=pre"
if defined RUN_TS (
  set "RUN_TS=!RUN_TS::=!"
  set "RUN_TS=!RUN_TS: =_!"
  set "RUN_TS=!RUN_TS:/=-!"
  set "RUN_TS=!RUN_TS:\=-!"
)
set "TEMP_ROOT=%TEMP%"
set "TEMP_SOURCE=TEMP"
if "%TEMP_ROOT%"=="" (
  set "TEMP_ROOT=%REPO_ROOT%\\tmp"
  set "TEMP_SOURCE=fallback"
)
if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%" >nul 2>&1
if not exist "%TEMP_ROOT%" (
  set "TEMP_ROOT=%REPO_ROOT%\\tmp"
  set "TEMP_SOURCE=fallback"
  if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%" >nul 2>&1
)
if not exist "%TEMP_ROOT%" (
  echo.[error] temp_root unavailable: "%TEMP_ROOT%"
  exit /b 1
)
set "TEMP=%TEMP_ROOT%"
echo.[setup] repo_root=%REPO_ROOT%
echo.[setup] temp_root=%TEMP_ROOT% (source=%TEMP_SOURCE%)
if not exist "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" (
  echo.[error] run_temp_supply_sweep.cmd not found: "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd"
  exit /b 1
)
pushd "%REPO_ROOT%" >nul

if "%DRY_RUN%"=="1" (
  call scripts\research\run_temp_supply_sweep.cmd --dry-run
  popd
  exit /b %errorlevel%
)

call scripts\research\run_temp_supply_sweep.cmd
set "RUN_RC=%errorlevel%"

popd
exit /b %RUN_RC%
