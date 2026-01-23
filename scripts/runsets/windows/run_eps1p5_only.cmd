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
set "WIN_PROCESS_PY=%RUNSETS_COMMON_DIR%\win_process.py"

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
if not exist "%WIN_PROCESS_PY%" (
  echo.[error] win_process helper not found: "%WIN_PROCESS_PY%"
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

if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"
if not defined BASE_CONFIG set "BASE_CONFIG=%REPO_ROOT%\scripts\runsets\common\base.yml"
if not defined EXTRA_OVERRIDES_FILE set "EXTRA_OVERRIDES_FILE=%REPO_ROOT%\scripts\runsets\windows\overrides.txt"
if not defined BATCH_ROOT set "BATCH_ROOT=%REPO_ROOT%\out"
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if not defined PARALLEL_SLEEP_SEC set "PARALLEL_SLEEP_SEC=5"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=hidden"

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

if not defined PYTHONPATH (
  set "PYTHONPATH=%REPO_ROOT%"
) else (
  set "PYTHONPATH=%REPO_ROOT%;!PYTHONPATH!"
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

call :normalize_int PARALLEL_JOBS 1
if "%PARALLEL_JOBS%"=="0" set "PARALLEL_JOBS=1"
if defined THREAD_LIMIT (
  call :normalize_int THREAD_LIMIT 0
  if "%THREAD_LIMIT%"=="0" set "THREAD_LIMIT="
)
if defined THREAD_LIMIT (
  set "NUMBA_NUM_THREADS=%THREAD_LIMIT%"
  set "OMP_NUM_THREADS=%THREAD_LIMIT%"
  set "MKL_NUM_THREADS=%THREAD_LIMIT%"
  set "OPENBLAS_NUM_THREADS=%THREAD_LIMIT%"
  set "NUMEXPR_NUM_THREADS=%THREAD_LIMIT%"
  set "VECLIB_MAXIMUM_THREADS=%THREAD_LIMIT%"
)

set "RUN_RC=0"
if "%PARALLEL_JOBS%"=="1" (
  call :run_worker_single
  set "RUN_RC=!errorlevel!"
) else (
  call :run_parallel_workers
  set "RUN_RC=!errorlevel!"
)

call :popd_safe
exit /b !RUN_RC!

:usage
echo Usage:
echo   run_eps1p5_only.cmd [--batch-dir DIR] [--out-root DIR] [--run-ts TS] [--batch-seed N] [--git-sha SHA]
echo                         [--sweep-tag TAG] [--base-config PATH] [--overrides PATH]
echo                         [--parallel-jobs N] [--thread-limit N] [--dry-run]
exit /b 0

:run_worker_single
if "%DRY_RUN%"=="1" (
  call "%PYTHON_EXEC_CMD%" scripts\runsets\common\run_sweep_worker.py --sweep-list "%SWEEP_LIST_FILE%" --part-index 1 --part-count 1 --dry-run
  exit /b !errorlevel!
)
call "%PYTHON_EXEC_CMD%" scripts\runsets\common\run_sweep_worker.py --sweep-list "%SWEEP_LIST_FILE%" --part-index 1 --part-count 1
exit /b !errorlevel!

:run_parallel_workers
set "JOB_PIDS="
set "JOB_COUNT=0"
set "WORKER_JOBS=%PARALLEL_JOBS%"
call :normalize_int WORKER_JOBS 1
if "%WORKER_JOBS%"=="0" set "WORKER_JOBS=1"
if "%WORKER_JOBS%"=="1" (
  call :run_worker_single
  exit /b !errorlevel!
)
set "SWEEP_PART_COUNT=%WORKER_JOBS%"
set "JOB_CWD_USE=%REPO_ROOT%"
set "WORKER_CMD_DIR=%BATCH_DIR%\_workers"
if not exist "!WORKER_CMD_DIR!" mkdir "!WORKER_CMD_DIR!" >nul 2>&1
for /L %%W in (1,1,%WORKER_JOBS%) do (
  call :launch_worker_job %%W %WORKER_JOBS%
)
call :wait_all
exit /b 0

:launch_worker_job
set "WORKER_INDEX=%~1"
set "WORKER_COUNT=%~2"
set "JOB_CMD_FILE=!WORKER_CMD_DIR!\eps1p5_worker_!WORKER_INDEX!.cmd"
> "!JOB_CMD_FILE!" echo @echo off
>> "!JOB_CMD_FILE!" echo set "SWEEP_PART_INDEX=!WORKER_INDEX!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_PART_COUNT=!WORKER_COUNT!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_LIST_FILE=!SWEEP_LIST_FILE!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_EXE=!PYTHON_EXE!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_ARGS=!PYTHON_ARGS!"
>> "!JOB_CMD_FILE!" echo set "PYTHON_EXEC_CMD=!PYTHON_EXEC_CMD!"
>> "!JOB_CMD_FILE!" echo set "BASE_CONFIG=!BASE_CONFIG!"
>> "!JOB_CMD_FILE!" echo set "EXTRA_OVERRIDES_FILE=!EXTRA_OVERRIDES_FILE!"
>> "!JOB_CMD_FILE!" echo set "BATCH_ROOT=!BATCH_ROOT!"
>> "!JOB_CMD_FILE!" echo set "BATCH_DIR=!BATCH_DIR!"
>> "!JOB_CMD_FILE!" echo set "RUN_TS=!RUN_TS!"
>> "!JOB_CMD_FILE!" echo set "BATCH_SEED=!BATCH_SEED!"
>> "!JOB_CMD_FILE!" echo set "GIT_SHA=!GIT_SHA!"
>> "!JOB_CMD_FILE!" echo set "SWEEP_TAG=!SWEEP_TAG!"
>> "!JOB_CMD_FILE!" echo set "QUIET_MODE=!QUIET_MODE!"
>> "!JOB_CMD_FILE!" echo set "DEBUG=!DEBUG!"
>> "!JOB_CMD_FILE!" echo set "PYTHONPATH=!PYTHONPATH!"
if defined THREAD_LIMIT (
  >> "!JOB_CMD_FILE!" echo set "NUMBA_NUM_THREADS=!THREAD_LIMIT!"
  >> "!JOB_CMD_FILE!" echo set "OMP_NUM_THREADS=!THREAD_LIMIT!"
  >> "!JOB_CMD_FILE!" echo set "MKL_NUM_THREADS=!THREAD_LIMIT!"
  >> "!JOB_CMD_FILE!" echo set "OPENBLAS_NUM_THREADS=!THREAD_LIMIT!"
  >> "!JOB_CMD_FILE!" echo set "NUMEXPR_NUM_THREADS=!THREAD_LIMIT!"
  >> "!JOB_CMD_FILE!" echo set "VECLIB_MAXIMUM_THREADS=!THREAD_LIMIT!"
)
if "%DRY_RUN%"=="1" (
  >> "!JOB_CMD_FILE!" echo call "!PYTHON_EXEC_CMD!" scripts\\runsets\\common\\run_sweep_worker.py --sweep-list "!SWEEP_LIST_FILE!" --part-index !WORKER_INDEX! --part-count !WORKER_COUNT! --dry-run
) else (
  >> "!JOB_CMD_FILE!" echo call "!PYTHON_EXEC_CMD!" scripts\\runsets\\common\\run_sweep_worker.py --sweep-list "!SWEEP_LIST_FILE!" --part-index !WORKER_INDEX! --part-count !WORKER_COUNT!
)
set "JOB_PID_TMP="
for /f "usebackq delims=" %%P in (`call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "!JOB_CMD_FILE!" --window-style "!PARALLEL_WINDOW_STYLE!" --cwd "!JOB_CWD_USE!"`) do set "JOB_PID_TMP=%%P"
set "JOB_PID=!JOB_PID_TMP!"
if defined JOB_PID (
  echo !JOB_PID!| findstr /r "^[0-9][0-9]*$" >nul
  if !errorlevel! geq 1 (
    echo.[warn] failed to launch worker !WORKER_INDEX! - output: !JOB_PID!
    set "JOB_PID="
  ) else (
    set "JOB_PIDS=!JOB_PIDS! !JOB_PID!"
    set /a JOB_COUNT+=1
  )
) else (
  echo.[warn] failed to launch worker !WORKER_INDEX! - no PID returned
)
exit /b 0

:refresh_jobs
set "JOB_COUNT=0"
if not defined JOB_PIDS exit /b 0
set "JOB_PIDS_TMP="
set "JOB_COUNT_TMP="
setlocal DisableDelayedExpansion
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
if "%JOB_COUNT%"=="0" exit /b 0
timeout /t %PARALLEL_SLEEP_SEC% /nobreak >nul
goto :wait_all

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
