@echo off
rem Run eps=1.5-only cases for temp_supply sweep (Windows CMD).
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "SCRIPT_DIR=%~dp0"
set "RUNSETS_COMMON_DIR=%SCRIPT_DIR%..\common"
for %%I in ("%RUNSETS_COMMON_DIR%") do set "RUNSETS_COMMON_DIR=%%~fI"
set "PYTHON_EXEC_CMD=%RUNSETS_COMMON_DIR%\python_exec.cmd"
set "RESOLVE_PYTHON_CMD=%RUNSETS_COMMON_DIR%\resolve_python.cmd"
set "SANITIZE_TOKEN_CMD=%RUNSETS_COMMON_DIR%\sanitize_token.cmd"
set "NEXT_SEED_PY=%RUNSETS_COMMON_DIR%\next_seed.py"

if not exist "%PYTHON_EXEC_CMD%" (
  echo.[error] python_exec helper not found: "%PYTHON_EXEC_CMD%"
  exit /b 1
)
if not exist "%RESOLVE_PYTHON_CMD%" (
  echo.[error] resolve_python helper not found: "%RESOLVE_PYTHON_CMD%"
  exit /b 1
)
if not exist "%SANITIZE_TOKEN_CMD%" (
  echo.[error] sanitize_token helper not found: "%SANITIZE_TOKEN_CMD%"
  exit /b 1
)
call "%RESOLVE_PYTHON_CMD%"
if !errorlevel! geq 1 exit /b 1

set "REPO_ROOT=%SCRIPT_DIR%..\..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

set "DRY_RUN=0"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--batch-dir" (
  set "BATCH_DIR=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--out-root" (
  set "BATCH_ROOT=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--run-ts" (
  set "RUN_TS=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--batch-seed" (
  set "BATCH_SEED=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--git-sha" (
  set "GIT_SHA=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--sweep-tag" (
  set "SWEEP_TAG=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--base-config" (
  set "BASE_CONFIG=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--overrides" (
  set "EXTRA_OVERRIDES_FILE=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
echo.[error] unknown argument: %~1
exit /b 2

:args_done

if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"
if not defined BASE_CONFIG set "BASE_CONFIG=%REPO_ROOT%\scripts\runsets\common\base.yml"
if not defined EXTRA_OVERRIDES_FILE set "EXTRA_OVERRIDES_FILE=%REPO_ROOT%\scripts\runsets\windows\overrides.txt"
if not defined BATCH_ROOT set "BATCH_ROOT=%REPO_ROOT%\out"

for %%I in ("%BASE_CONFIG%") do set "BASE_CONFIG=%%~fI"
for %%I in ("%EXTRA_OVERRIDES_FILE%") do set "EXTRA_OVERRIDES_FILE=%%~fI"
for %%I in ("%BATCH_ROOT%") do set "BATCH_ROOT=%%~fI"
if defined BATCH_DIR for %%I in ("%BATCH_DIR%") do set "BATCH_DIR=%%~fI"

if not defined RUN_TS (
  call "%SANITIZE_TOKEN_CMD%" RUN_TS timestamp
  if !errorlevel! geq 1 exit /b 1
)
if not defined BATCH_SEED (
  for /f "usebackq delims=" %%A in (`call "%PYTHON_EXEC_CMD%" "%NEXT_SEED_PY%"`) do set "BATCH_SEED=%%A"
)
if "%BATCH_SEED%"=="" set "BATCH_SEED=0"
if not defined GIT_SHA (
  for /f %%A in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%A"
)
if not defined GIT_SHA set "GIT_SHA=nogit"

if not defined BATCH_DIR (
  set "BATCH_DIR=%BATCH_ROOT%\%SWEEP_TAG%\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%"
)
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%" >nul 2>&1
if not exist "%BATCH_DIR%" (
  echo.[error] failed to create batch dir: "%BATCH_DIR%"
  exit /b 1
)

set "SWEEP_LIST_FILE=%BATCH_DIR%\eps1p5_only.txt"
> "%SWEEP_LIST_FILE%" echo 3000 1.5 1.0 0.05 1.0
>>"%SWEEP_LIST_FILE%" echo 3000 1.5 0.5 0.05 1.0
>>"%SWEEP_LIST_FILE%" echo 4000 1.5 1.0 0.05 1.0
>>"%SWEEP_LIST_FILE%" echo 4000 1.5 0.5 0.05 1.0
>>"%SWEEP_LIST_FILE%" echo 5000 1.5 1.0 0.05 1.0
>>"%SWEEP_LIST_FILE%" echo 5000 1.5 0.5 0.05 1.0

pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

set "BASE_CONFIG=%BASE_CONFIG%"
set "EXTRA_OVERRIDES_FILE=%EXTRA_OVERRIDES_FILE%"
set "BATCH_DIR=%BATCH_DIR%"
set "BATCH_ROOT=%BATCH_ROOT%"
set "RUN_TS=%RUN_TS%"
set "BATCH_SEED=%BATCH_SEED%"
set "GIT_SHA=%GIT_SHA%"
set "SWEEP_TAG=%SWEEP_TAG%"

if "%DRY_RUN%"=="1" (
  call "%PYTHON_EXEC_CMD%" scripts\runsets\common\run_sweep_worker.py --sweep-list "%SWEEP_LIST_FILE%" --part-index 1 --part-count 1 --dry-run
) else (
  call "%PYTHON_EXEC_CMD%" scripts\runsets\common\run_sweep_worker.py --sweep-list "%SWEEP_LIST_FILE%" --part-index 1 --part-count 1
)
set "RUN_RC=!errorlevel!"

call :popd_safe
exit /b !RUN_RC!

:usage
echo Usage:
echo   run_eps1p5_only.cmd [--batch-dir DIR] [--out-root DIR] [--run-ts TS] [--batch-seed N] [--git-sha SHA]
echo                         [--sweep-tag TAG] [--base-config PATH] [--overrides PATH] [--dry-run]
exit /b 0

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%
