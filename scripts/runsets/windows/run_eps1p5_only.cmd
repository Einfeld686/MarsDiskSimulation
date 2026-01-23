@echo off
rem Run eps=1.5-only cases via run_temp_supply_sweep.cmd.
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\..\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

set "RUNSETS_COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
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
if /i "%~1"=="--parallel-jobs" (
  set "PARALLEL_JOBS=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--thread-limit" (
  set "THREAD_LIMIT=%~2"
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

if defined BATCH_DIR call :parse_batch_dir

if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"
if not defined BASE_CONFIG set "BASE_CONFIG=%REPO_ROOT%\scripts\runsets\common\base.yml"
if not defined EXTRA_OVERRIDES_FILE set "EXTRA_OVERRIDES_FILE=%REPO_ROOT%\scripts\runsets\windows\overrides.txt"
if not defined BATCH_ROOT set "BATCH_ROOT=%REPO_ROOT%\out"

for %%I in ("%BASE_CONFIG%") do set "BASE_CONFIG=%%~fI"
for %%I in ("%EXTRA_OVERRIDES_FILE%") do set "EXTRA_OVERRIDES_FILE=%%~fI"
for %%I in ("%BATCH_ROOT%") do set "BATCH_ROOT=%%~fI"

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

if not defined PYTHONPATH (
  set "PYTHONPATH=%REPO_ROOT%"
) else (
  set "PYTHONPATH=%REPO_ROOT%;!PYTHONPATH!"
)

if not defined MU_LIST set "MU_LIST=1.0"

if not defined PARALLEL_JOBS set "PARALLEL_JOBS=6"
call :normalize_int PARALLEL_JOBS 1
if "%PARALLEL_JOBS%"=="0" set "PARALLEL_JOBS=1"
if "%PARALLEL_JOBS%"=="1" (
  if not defined SWEEP_PARALLEL set "SWEEP_PARALLEL=0"
) else (
  set "SWEEP_PARALLEL=1"
)

if not defined THREAD_LIMIT set "THREAD_LIMIT=3"
if defined THREAD_LIMIT (
  call :normalize_int THREAD_LIMIT 0
  if "%THREAD_LIMIT%"=="0" set "THREAD_LIMIT="
)
if defined THREAD_LIMIT set "CELL_THREAD_LIMIT=%THREAD_LIMIT%"

set "STUDY_DIR=%REPO_ROOT%\tmp"
if not exist "%STUDY_DIR%" mkdir "%STUDY_DIR%" >nul 2>&1
set "STUDY_FILE=%STUDY_DIR%\eps1p5_only_%RUN_TS%_%BATCH_SEED%.yml"
> "%STUDY_FILE%" echo T_LIST: [5000, 4000, 3000]
>>"%STUDY_FILE%" echo EPS_LIST: [1.5]
>>"%STUDY_FILE%" echo TAU_LIST: [1.0, 0.5]
>>"%STUDY_FILE%" echo I0_LIST: [0.05]
>>"%STUDY_FILE%" echo SWEEP_TAG: %SWEEP_TAG%

set "RUN_CMD=%REPO_ROOT%\scripts\research\run_temp_supply_sweep.cmd"
if not exist "%RUN_CMD%" (
  echo.[error] run_temp_supply_sweep.cmd not found: "%RUN_CMD%"
  exit /b 1
)

pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

if "%DRY_RUN%"=="1" (
  call "%RUN_CMD%" --dry-run
  set "RUN_RC=!errorlevel!"
  call :popd_safe
  exit /b !RUN_RC!
)

call "%RUN_CMD%"
set "RUN_RC=!errorlevel!"
call :popd_safe
exit /b !RUN_RC!

:usage
echo Usage:
echo   run_eps1p5_only.cmd [--batch-dir DIR] [--out-root DIR] [--run-ts TS] [--batch-seed N] [--git-sha SHA]
echo                         [--sweep-tag TAG] [--base-config PATH] [--overrides PATH]
echo                         [--parallel-jobs N] [--thread-limit N] [--dry-run]
exit /b 0

:parse_batch_dir
set "BATCH_DIR_RAW=%BATCH_DIR%"
for %%I in ("%BATCH_DIR%") do (
  set "BATCH_DIR=%%~fI"
  set "BATCH_DIR_NAME=%%~nxI"
  set "BATCH_DIR_PARENT=%%~dpI"
)
if defined BATCH_DIR_PARENT (
  for %%I in ("%BATCH_DIR_PARENT%.") do set "SWEEP_TAG=%%~nxI"
  for %%I in ("%BATCH_DIR_PARENT%..") do set "BATCH_ROOT=%%~fI"
)
set "BATCH_DIR_NAME=!BATCH_DIR_NAME:__=|!"
for /f "tokens=1,2,3 delims=|" %%A in ("!BATCH_DIR_NAME!") do (
  if not defined RUN_TS set "RUN_TS=%%A"
  if not defined GIT_SHA set "GIT_SHA=%%B"
  if not defined BATCH_SEED set "BATCH_SEED=%%C"
)
if defined BATCH_SEED set "BATCH_SEED=!BATCH_SEED:seed=!"
exit /b 0

:normalize_int
set "INT_NAME=%~1"
set "INT_DEFAULT=%~2"
set "INT_VALUE="
call set "INT_VALUE=%%%INT_NAME%%%"
set "INT_OK=1"
if "%INT_VALUE%"=="" set "INT_OK=0"
for /f "delims=0123456789" %%A in ("%INT_VALUE%") do set "INT_OK=0"
if "%INT_OK%"=="0" set "%INT_NAME%=%INT_DEFAULT%"
exit /b 0

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%
