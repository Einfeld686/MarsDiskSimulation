@echo off
rem Run over-parallelism benchmark on Windows.

setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"
set "RUNSETS_COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\venv_bootstrap.cmd"
if not exist "%VENV_BOOTSTRAP_CMD%" (
  echo [error] venv_bootstrap helper not found: "%VENV_BOOTSTRAP_CMD%"
  call :popd_safe 1
  goto :eof
)
call "%VENV_BOOTSTRAP_CMD%"
set "BOOTSTRAP_RC=!errorlevel!"
if not "!BOOTSTRAP_RC!"=="0" (
  echo [error] Failed to initialize Python environment.
  call :popd_safe !BOOTSTRAP_RC!
  goto :eof
)

"%PYTHON_EXE%" -m pip install psutil
set "PSUTIL_RC=!errorlevel!"
if not "!PSUTIL_RC!"=="0" (
  echo [warn] psutil install failed; perf logging will be limited.
)

if not defined AUTO_JOBS set "AUTO_JOBS=1"
if not defined JOB_MEM_GB set "JOB_MEM_GB=10"
if not defined MEM_RESERVE_GB set "MEM_RESERVE_GB=4"

set "TOTAL_GB="
set "CPU_LOGICAL="
if "%AUTO_JOBS%"=="1" (
  if not defined PARALLEL_MEM_FRACTION set "PARALLEL_MEM_FRACTION=1"
  for /f "usebackq tokens=1-3 delims=|" %%A in (`"%PYTHON_EXE%" scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
    set "TOTAL_GB=%%A"
    set "CPU_LOGICAL=%%B"
    if not defined PARALLEL_JOBS set "PARALLEL_JOBS=%%C"
  )
)
if not defined PARALLEL_JOBS set "PARALLEL_JOBS=1"
if "%PARALLEL_JOBS%"=="" set "PARALLEL_JOBS=1"

if not defined MARSDISK_CELL_JOBS (
  if defined NUMBER_OF_PROCESSORS (
    set "MARSDISK_CELL_JOBS=%NUMBER_OF_PROCESSORS%"
  ) else (
    set "MARSDISK_CELL_JOBS=1"
  )
)

if not defined BENCH_N_CELLS set "BENCH_N_CELLS=64"
if not defined BENCH_T_END_ORBITS set "BENCH_T_END_ORBITS=0.1"
if not defined BENCH_DT_INIT set "BENCH_DT_INIT=20"

if not defined TOTAL_GB set "TOTAL_GB=unknown"
if not defined CPU_LOGICAL set "CPU_LOGICAL=unknown"
echo [sys] mem_total_gb=%TOTAL_GB% cpu_logical=%CPU_LOGICAL% parallel_jobs=%PARALLEL_JOBS% cell_jobs=%MARSDISK_CELL_JOBS%

set "BENCH_ARGS=--parallel-jobs %PARALLEL_JOBS% --cell-jobs %MARSDISK_CELL_JOBS% --n-cells %BENCH_N_CELLS% --t-end-orbits %BENCH_T_END_ORBITS% --dt-init %BENCH_DT_INIT%"
echo [info] Benchmark defaults: %BENCH_ARGS%
"%PYTHON_EXE%" scripts\tests\overparallel_benchmark.py %BENCH_ARGS% %*
set "RC=!errorlevel!"

call :popd_safe !RC!
goto :eof

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%~1"
if "%MARSDISK_POPD_ERRORLEVEL%"=="" set "MARSDISK_POPD_ERRORLEVEL=!errorlevel!"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
endlocal & exit /b %MARSDISK_POPD_ERRORLEVEL%
