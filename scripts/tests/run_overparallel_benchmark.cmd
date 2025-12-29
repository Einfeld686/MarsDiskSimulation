@echo off
rem Run over-parallelism benchmark on Windows.

setlocal EnableExtensions

if not defined PYTHON_EXE set "PYTHON_EXE=python3.11"
if not exist "%PYTHON_EXE%" (
  where %PYTHON_EXE% >nul 2>&1
  if errorlevel 1 (
    echo [error] %PYTHON_EXE% not found in PATH.
    exit /b 1
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    popd
    exit /b 1
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  popd
  exit /b 1
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo [setup] Installing dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency install failed.
    popd
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

"%PYTHON_EXE%" -m pip install psutil
if errorlevel 1 (
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
set "RC=%errorlevel%"

popd
exit /b %RC%
