@echo off
rem Run a temp_supply sweep (1D default).
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"
set "REPO_ROOT=%SCRIPT_DIR%..\\..\\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
set "CONFIG_PATH=%REPO_ROOT%\\scripts\\runsets\\common\\base.yml"
set "OVERRIDES_PATH=%REPO_ROOT%\\scripts\\runsets\\windows\\overrides.txt"
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
if /i "%~1"=="--debug" (
  set "DEBUG=1"
  set "TRACE_ENABLED=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage

echo.[error] Unknown option: %~1
:usage
echo Usage: run_sweep.cmd [--study ^<path^>] [--config ^<path^>] [--overrides ^<path^>]
 echo.           [--out-root ^<path^>] [--dry-run] [--no-plot] [--no-eval] [--no-preflight] [--debug]
exit /b 1

:args_done

call :ensure_abs CONFIG_PATH
call :ensure_abs OVERRIDES_PATH
if defined STUDY_PATH call :ensure_abs STUDY_PATH

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
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=1"
set "SWEEP_PARALLEL=0"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"
set "MARSDISK_CELL_PARALLEL=1"
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
if not defined MARSDISK_CELL_JOBS set "MARSDISK_CELL_JOBS=auto"
if not defined CELL_MEM_FRACTION set "CELL_MEM_FRACTION=0.7"
if not defined CELL_CPU_FRACTION set "CELL_CPU_FRACTION=0.7"

if defined STUDY_PATH set "STUDY_FILE=%STUDY_PATH%"
if defined OUT_ROOT (
  set "BATCH_ROOT=%OUT_ROOT%"
) else (
  set "BATCH_ROOT=out"
)
rem Staging outputs stay on the internal disk; external archive is handled via io.archive.*

rem Validate archive defaults in the overrides file to match the archive plan.
set "ARCHIVE_ENABLED_EXPECTED="
set "ARCHIVE_DIR_EXPECTED="
set "ARCHIVE_MERGE_TARGET="
set "ARCHIVE_VERIFY_LEVEL="
set "ARCHIVE_KEEP_LOCAL="
if exist "%OVERRIDES_PATH%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^io\\.archive\\.enabled=" "%OVERRIDES_PATH%"`) do set "ARCHIVE_ENABLED_EXPECTED=%%B"
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^io\\.archive\\.dir=" "%OVERRIDES_PATH%"`) do set "ARCHIVE_DIR_EXPECTED=%%B"
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^io\\.archive\\.merge_target=" "%OVERRIDES_PATH%"`) do set "ARCHIVE_MERGE_TARGET=%%B"
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^io\\.archive\\.verify_level=" "%OVERRIDES_PATH%"`) do set "ARCHIVE_VERIFY_LEVEL=%%B"
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^io\\.archive\\.keep_local=" "%OVERRIDES_PATH%"`) do set "ARCHIVE_KEEP_LOCAL=%%B"
)
if /i not "%ARCHIVE_ENABLED_EXPECTED%"=="true" (
  echo.[error] io.archive.enabled=true is required in %OVERRIDES_PATH%
  exit /b 1
)
if not defined ARCHIVE_DIR_EXPECTED (
  echo.[error] io.archive.dir is required in %OVERRIDES_PATH%
  exit /b 1
)
if /i not "%ARCHIVE_MERGE_TARGET%"=="external" (
  echo.[error] io.archive.merge_target=external is required in %OVERRIDES_PATH%
  exit /b 1
)
if /i not "%ARCHIVE_VERIFY_LEVEL%"=="standard_plus" (
  echo.[error] io.archive.verify_level=standard_plus is required in %OVERRIDES_PATH%
  exit /b 1
)
if /i not "%ARCHIVE_KEEP_LOCAL%"=="metadata" (
  echo.[error] io.archive.keep_local=metadata is required in %OVERRIDES_PATH%
  exit /b 1
)
if /i "%BATCH_ROOT%"=="%ARCHIVE_DIR_EXPECTED%" (
  echo.[error] BATCH_ROOT must be internal; it matches io.archive.dir (%ARCHIVE_DIR_EXPECTED%)
  exit /b 1
)

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

:ensure_abs
set "VAR_NAME=%~1"
set "VAR_VAL=!%VAR_NAME%!"
if not defined VAR_VAL exit /b 0
if "!VAR_VAL:~1,1!"==":" exit /b 0
if "!VAR_VAL:~0,2!"=="\\\\" exit /b 0
if "!VAR_VAL:~0,1!"=="\\" exit /b 0
set "%VAR_NAME%=%REPO_ROOT%\\!VAR_VAL!"
exit /b 0
