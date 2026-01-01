@echo off
rem Run a single temp_supply case (1D default).
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"

set "RUNSETS_COMMON_DIR=%SCRIPT_DIR%..\common"
for %%I in ("%RUNSETS_COMMON_DIR%") do set "RUNSETS_COMMON_DIR=%%~fI"
set "RESOLVE_PYTHON_CMD=%RUNSETS_COMMON_DIR%\resolve_python.cmd"
if not exist "%RESOLVE_PYTHON_CMD%" (
  echo.[error] resolve_python helper not found: "%RESOLVE_PYTHON_CMD%"
  exit /b 1
)
call "%RESOLVE_PYTHON_CMD%"
if errorlevel 1 exit /b 1

if defined CI (
  !PYTHON_CMD! -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
  if !errorlevel! geq 1 (
    echo.[error] python 3.11+ is required in CI
    exit /b 1
  )
)

set "CONFIG_PATH=scripts\runsets\common\base.yml"
set "OVERRIDES_PATH=scripts\runsets\windows\overrides.txt"
set "OUT_ROOT="
set "RUN_ONE_T="
set "RUN_ONE_EPS="
set "RUN_ONE_TAU="
set "RUN_ONE_SEED="
set "GEOMETRY_MODE=1D"
set "DRY_RUN=0"
set "NO_PLOT=0"
set "NO_EVAL=0"
set "PREFLIGHT_ONLY=0"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--t" (
  set "RUN_ONE_T=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--eps" (
  set "RUN_ONE_EPS=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--tau" (
  set "RUN_ONE_TAU=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--seed" (
  set "RUN_ONE_SEED=%~2"
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
if /i "%~1"=="--0d" (
  set "GEOMETRY_MODE=0D"
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
  echo.[error] preflight checks are mandatory; remove --no-preflight
  exit /b 1
)
if /i "%~1"=="--preflight-only" (
  set "PREFLIGHT_ONLY=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage

echo.[error] Unknown option: %~1
:usage
echo Usage: run_one.cmd --t ^<K^> --eps ^<float^> --tau ^<float^> [--seed ^<int^>]
 echo.            [--config ^<path^>] [--overrides ^<path^>] [--out-root ^<path^>]
 echo.            [--0d] [--dry-run] [--no-plot] [--no-eval] [--preflight-only]
exit /b 1

:args_done
if not defined RUN_ONE_T (
  echo.[error] --t is required
  goto :usage
)
if not defined RUN_ONE_EPS (
  echo.[error] --eps is required
  goto :usage
)
if not defined RUN_ONE_TAU (
  echo.[error] --tau is required
  goto :usage
)

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
set "RUN_ONE_T=%RUN_ONE_T%"
set "RUN_ONE_EPS=%RUN_ONE_EPS%"
set "RUN_ONE_TAU=%RUN_ONE_TAU%"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_run_one"
set "GEOMETRY_MODE=%GEOMETRY_MODE%"
if not defined GEOMETRY_NR set "GEOMETRY_NR=32"
if not defined SHIELDING_MODE set "SHIELDING_MODE=off"
if not defined SUPPLY_MU_REFERENCE_TAU set "SUPPLY_MU_REFERENCE_TAU=1.0"
if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"
if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=off"
if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=direct"
if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=off"
if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=hard"
if not defined AUTO_JOBS set "AUTO_JOBS=0"
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
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
if /i "%MARSDISK_CELL_PARALLEL%"=="1" (
  if not defined CELL_THREAD_LIMIT set "CELL_THREAD_LIMIT=1"
  if not defined NUMBA_NUM_THREADS set "NUMBA_NUM_THREADS=!CELL_THREAD_LIMIT!"
  if not defined OMP_NUM_THREADS set "OMP_NUM_THREADS=!CELL_THREAD_LIMIT!"
  if not defined MKL_NUM_THREADS set "MKL_NUM_THREADS=!CELL_THREAD_LIMIT!"
  if not defined OPENBLAS_NUM_THREADS set "OPENBLAS_NUM_THREADS=!CELL_THREAD_LIMIT!"
  if not defined NUMEXPR_NUM_THREADS set "NUMEXPR_NUM_THREADS=!CELL_THREAD_LIMIT!"
  if not defined VECLIB_MAXIMUM_THREADS set "VECLIB_MAXIMUM_THREADS=!CELL_THREAD_LIMIT!"
)

if defined RUN_ONE_SEED set "RUN_ONE_SEED=%RUN_ONE_SEED%"
if defined OUT_ROOT set "OUT_ROOT=%OUT_ROOT%"

for %%I in ("%~dp0..\..\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

if defined OUT_ROOT (
  for %%I in ("%OUT_ROOT%") do set "OUT_ROOT=%%~fI"
)

echo.[info] preflight checks
if defined CI (
  !PYTHON_CMD! "scripts\\runsets\\windows\\preflight_checks.py" --repo-root "%REPO_ROOT%" --config "%CONFIG_PATH%" --overrides "%OVERRIDES_PATH%" --out-root "%OUT_ROOT%" --require-git --cmd "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" --cmd-root "%REPO_ROOT%\\scripts\\runsets\\windows" --cmd-root "%REPO_ROOT%\\scripts\\research" --cmd-exclude "%REPO_ROOT%\\scripts\\runsets\\windows\\legacy" --cmd-allowlist "%REPO_ROOT%\\scripts\\runsets\\windows\\preflight_allowlist.txt" --profile ci --format json --allow-non-ascii
) else (
  !PYTHON_CMD! "scripts\\runsets\\windows\\preflight_checks.py" --repo-root "%REPO_ROOT%" --config "%CONFIG_PATH%" --overrides "%OVERRIDES_PATH%" --out-root "%OUT_ROOT%" --require-git --cmd "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" --cmd-root "%REPO_ROOT%\\scripts\\runsets\\windows" --cmd-root "%REPO_ROOT%\\scripts\\research" --cmd-exclude "%REPO_ROOT%\\scripts\\runsets\\windows\\legacy" --allow-non-ascii
)
if !errorlevel! geq 1 (
  echo.[error] preflight failed
  call :popd_safe
  exit /b 1
)
if "%PREFLIGHT_ONLY%"=="1" (
  echo.[info] preflight-only requested; exiting.
  call :popd_safe
  exit /b 0
)

if "%DRY_RUN%"=="1" (
  call scripts\research\run_temp_supply_sweep.cmd --dry-run
  call :popd_safe
  exit /b !errorlevel!
)

call scripts\research\run_temp_supply_sweep.cmd --run-one
set "RUN_RC=%errorlevel%"

call :popd_safe
exit /b %RUN_RC%

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%

endlocal
