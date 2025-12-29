@echo off
rem Run a temp_supply sweep (1D default).
setlocal EnableExtensions EnableDelayedExpansion

if not defined PYTHON_EXE (
  for %%P in (python3.11 python py) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] python3.11/python/py not found in PATH
    exit /b 1
  )
) else (
  if not exist "%PYTHON_EXE%" (
    where %PYTHON_EXE% >nul 2>&1
    if errorlevel 1 (
      echo.[error] %PYTHON_EXE% not found in PATH
      exit /b 1
    )
  )
)

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
set "PREFLIGHT_ONLY=0"
set "PREFLIGHT_STRICT=0"
if not defined QUIET_MODE set "QUIET_MODE=1"

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
if /i "%~1"=="--quiet" (
  set "QUIET_MODE=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--no-quiet" (
  set "QUIET_MODE=0"
  shift
  goto :parse_args
)
if /i "%~1"=="--preflight-only" (
  set "PREFLIGHT_ONLY=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--preflight-strict" (
  set "PREFLIGHT_STRICT=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--debug" (
  set "DEBUG=1"
  set "TRACE_ENABLED=1"
  set "QUIET_MODE=0"
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage

echo.[error] Unknown option: %~1
:usage
echo Usage: run_sweep.cmd [--study ^<path^>] [--config ^<path^>] [--overrides ^<path^>]
 echo.           [--out-root ^<path^>] [--dry-run] [--no-plot] [--no-eval] [--no-preflight] [--quiet] [--no-quiet] [--preflight-only] [--preflight-strict] [--debug]
exit /b 1

:args_done

if "%QUIET_MODE%"=="1" (
  set "LOG_INFO=rem"
  set "LOG_SETUP=rem"
  set "LOG_SYS=rem"
  set "LOG_CONFIG=rem"
  set "LOG_RUN=rem"
) else (
  set "LOG_INFO=echo.[info]"
  set "LOG_SETUP=echo.[setup]"
  set "LOG_SYS=echo.[sys]"
  set "LOG_CONFIG=echo.[config]"
  set "LOG_RUN=echo.[run]"
)

call :ensure_abs CONFIG_PATH
call :ensure_abs OVERRIDES_PATH
if defined STUDY_PATH call :ensure_abs STUDY_PATH

%LOG_INFO% run_sweep start
%LOG_INFO% config="%CONFIG_PATH%" overrides="%OVERRIDES_PATH%" study="%STUDY_PATH%" out_root="%OUT_ROOT%"

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
rem run_temp_supply_sweep.sh defaults to COOL_TO_K=2000 (temperature stop).
rem To force a fixed horizon, set COOL_TO_K=none and T_END_YEARS explicitly.
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=1"
set "SWEEP_PARALLEL=0"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"
if not defined PARALLEL_MODE set "PARALLEL_MODE=numba"
set "MARSDISK_CELL_PARALLEL=1"
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
rem Default to cell-parallel auto sizing unless PARALLEL_MODE=numba.
set "MARSDISK_CELL_JOBS=auto"
if not defined CELL_MEM_FRACTION set "CELL_MEM_FRACTION=0.8"
set "CELL_CPU_FRACTION=0.8"
if not defined CPU_UTIL_TARGET_PERCENT set "CPU_UTIL_TARGET_PERCENT=80"
if not defined CPU_UTIL_TARGET_MAX_PERCENT set "CPU_UTIL_TARGET_MAX_PERCENT=90"
if not defined CPU_UTIL_RESPECT_MEM set "CPU_UTIL_RESPECT_MEM=1"
if /i "%PARALLEL_MODE%"=="numba" (
  set "MARSDISK_CELL_PARALLEL=0"
  set "MARSDISK_CELL_JOBS=1"
)

if defined STUDY_PATH set "STUDY_FILE=%STUDY_PATH%"
if defined OUT_ROOT (
  set "BATCH_ROOT=%OUT_ROOT%"
) else (
  set "BATCH_ROOT=out"
)
rem Staging outputs stay on the internal disk; external archive is handled via io.archive.*
if "%DEBUG%"=="1" %LOG_INFO% batch_root="%BATCH_ROOT%"

if not "%NO_PREFLIGHT%"=="1" (
  %LOG_INFO% preflight checks
  set "PREFLIGHT_STRICT_FLAG="
  if "%PREFLIGHT_STRICT%"=="1" set "PREFLIGHT_STRICT_FLAG=--strict"
  "%PYTHON_EXE%" "%REPO_ROOT%\\scripts\\runsets\\windows\\preflight_checks.py" --repo-root "%REPO_ROOT%" --config "%CONFIG_PATH%" --overrides "%OVERRIDES_PATH%" --out-root "%OUT_ROOT%" --require-git --cmd "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" --cmd-root "%REPO_ROOT%\\scripts\\runsets\\windows" --cmd-exclude "%REPO_ROOT%\\scripts\\runsets\\windows\\legacy" %PREFLIGHT_STRICT_FLAG%
  if errorlevel 1 (
    echo.[error] preflight failed
    exit /b 1
  )
)
if "%PREFLIGHT_ONLY%"=="1" (
  %LOG_INFO% preflight-only requested; exiting.
  exit /b 0
)

rem Validate archive defaults in the overrides file to match the archive plan.
rem NOTE: PowerShell inlined parsing can break under cmd.exe redirection (">") and JP paths,
rem so we always parse overrides via Python and emit a temp .cmd to avoid that class of errors.
set "ARCHIVE_ENABLED_EXPECTED="
set "ARCHIVE_DIR_EXPECTED="
set "ARCHIVE_MERGE_TARGET="
set "ARCHIVE_VERIFY_LEVEL="
set "ARCHIVE_KEEP_LOCAL="
if not exist "%OVERRIDES_PATH%" (
  echo.[error] overrides file not found: "%OVERRIDES_PATH%"
  exit /b 1
)
%LOG_INFO% parsing overrides file
set "ARCHIVE_TMP=%TEMP%"
if "%ARCHIVE_TMP%"=="" set "ARCHIVE_TMP=%REPO_ROOT%\\tmp"
if not exist "%ARCHIVE_TMP%" mkdir "%ARCHIVE_TMP%" >nul 2>&1
set "ARCHIVE_SET=%ARCHIVE_TMP%\\marsdisk_archive_overrides_%RANDOM%.cmd"
"%PYTHON_EXE%" "%REPO_ROOT%\\scripts\\runsets\\common\\read_overrides_cmd.py" --file "%OVERRIDES_PATH%" --out "%ARCHIVE_SET%"
if errorlevel 1 (
  echo.[error] failed to parse overrides: "%OVERRIDES_PATH%"
  exit /b 1
)
if not exist "%ARCHIVE_SET%" (
  echo.[error] overrides parse output missing: "%ARCHIVE_SET%"
  exit /b 1
)
call "%ARCHIVE_SET%"
del "%ARCHIVE_SET%"
%LOG_INFO% overrides parsed
%LOG_INFO% archive checks start
if "%DEBUG%"=="1" %LOG_INFO% archive expected: enabled="!ARCHIVE_ENABLED_EXPECTED!" dir="!ARCHIVE_DIR_EXPECTED!" merge="!ARCHIVE_MERGE_TARGET!" verify="!ARCHIVE_VERIFY_LEVEL!" keep="!ARCHIVE_KEEP_LOCAL!"
if /i not "%ARCHIVE_ENABLED_EXPECTED%"=="true" goto :archive_fail_enabled
if "%DEBUG%"=="1" %LOG_INFO% archive check enabled ok
if not defined ARCHIVE_DIR_EXPECTED goto :archive_fail_dir
if "%DEBUG%"=="1" %LOG_INFO% archive check dir ok
if /i not "%ARCHIVE_MERGE_TARGET%"=="external" goto :archive_fail_merge
if "%DEBUG%"=="1" %LOG_INFO% archive check merge_target ok
if /i not "%ARCHIVE_VERIFY_LEVEL%"=="standard_plus" goto :archive_fail_verify
if "%DEBUG%"=="1" %LOG_INFO% archive check verify_level ok
if /i not "%ARCHIVE_KEEP_LOCAL%"=="metadata" goto :archive_fail_keep
if "%DEBUG%"=="1" %LOG_INFO% archive check keep_local ok
if /i "%BATCH_ROOT%"=="%ARCHIVE_DIR_EXPECTED%" goto :archive_fail_batch_root
%LOG_INFO% overrides validated
%LOG_INFO% preflight ok; preparing temp_root

set "RUN_TS_SOURCE=pre"
if defined RUN_TS (
  set "RUN_TS=!RUN_TS::=!"
  set "RUN_TS=!RUN_TS: =_!"
  set "RUN_TS=!RUN_TS:/=-!"
  set "RUN_TS=!RUN_TS:\=-!"
)
set "TEMP_ROOT=%TEMP%"
set "TEMP_SOURCE=TEMP"
%LOG_INFO% temp_root candidate="%TEMP_ROOT%"
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
%LOG_SETUP% repo_root=%REPO_ROOT%
%LOG_SETUP% temp_root=%TEMP_ROOT% (source=%TEMP_SOURCE%)
if not exist "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" (
  echo.[error] run_temp_supply_sweep.cmd not found: "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd"
  exit /b 1
)
pushd "%REPO_ROOT%" >nul

if "%DRY_RUN%"=="1" (
  %LOG_INFO% dry-run: calling run_temp_supply_sweep.cmd
  call scripts\research\run_temp_supply_sweep.cmd --dry-run
  popd
  exit /b %errorlevel%
)

%LOG_INFO% launching run_temp_supply_sweep.cmd
call scripts\research\run_temp_supply_sweep.cmd
set "RUN_RC=%errorlevel%"
%LOG_INFO% run_temp_supply_sweep.cmd finished (rc=%RUN_RC%)

popd
exit /b %RUN_RC%

:archive_fail_enabled
echo.[error] io.archive.enabled=true is required in %OVERRIDES_PATH%
exit /b 1

:archive_fail_dir
echo.[error] io.archive.dir is required in %OVERRIDES_PATH%
exit /b 1

:archive_fail_merge
echo.[error] io.archive.merge_target=external is required in %OVERRIDES_PATH%
exit /b 1

:archive_fail_verify
echo.[error] io.archive.verify_level=standard_plus is required in %OVERRIDES_PATH%
exit /b 1

:archive_fail_keep
echo.[error] io.archive.keep_local=metadata is required in %OVERRIDES_PATH%
exit /b 1

:archive_fail_batch_root
echo.[error] BATCH_ROOT must be internal; it matches io.archive.dir (%ARCHIVE_DIR_EXPECTED%)
exit /b 1

:ensure_abs
set "VAR_NAME=%~1"
set "VAR_VAL=!%VAR_NAME%!"
if not defined VAR_VAL exit /b 0
if "!VAR_VAL:~1,1!"==":" exit /b 0
if "!VAR_VAL:~0,2!"=="\\\\" exit /b 0
if "!VAR_VAL:~0,1!"=="\\" exit /b 0
set "%VAR_NAME%=%REPO_ROOT%\\!VAR_VAL!"
exit /b 0
