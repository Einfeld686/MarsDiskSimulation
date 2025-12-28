@echo off
rem Run over-parallelism benchmark on Windows.

setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
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

if exist "%REQ_FILE%" (
  echo [setup] Installing dependencies from %REQ_FILE% ...
  python -m pip install --upgrade pip
  python -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency install failed.
    popd
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

python -m pip install psutil
if errorlevel 1 (
  echo [warn] psutil install failed; perf logging will be limited.
)

if not defined AUTO_JOBS set "AUTO_JOBS=1"
if not defined JOB_MEM_GB set "JOB_MEM_GB=10"
if not defined MEM_RESERVE_GB set "MEM_RESERVE_GB=4"

set "TOTAL_GB="
set "CPU_LOGICAL="
if "%AUTO_JOBS%"=="1" (
  for /f %%A in ('powershell -NoProfile -Command "$mem=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; [math]::Floor($mem/1GB)"') do set "TOTAL_GB=%%A"
  for /f %%A in ('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Sum -Property NumberOfLogicalProcessors).Sum"') do set "CPU_LOGICAL=%%A"
  if not defined CPU_LOGICAL for /f %%A in ('powershell -NoProfile -Command "[Environment]::ProcessorCount"') do set "CPU_LOGICAL=%%A"
  if not defined PARALLEL_JOBS (
    for /f %%A in ('powershell -NoProfile -Command "$total=[double]$env:TOTAL_GB; $reserve=[double]$env:MEM_RESERVE_GB; $job=[double]$env:JOB_MEM_GB; if (-not $job -or $job -le 0){$job=10}; if (-not $total -or $total -le 0){$total=0}; $avail=[math]::Max($total-$reserve,1); $memJobs=[math]::Max([math]::Floor($avail/$job),1); $cpu=[int]$env:CPU_LOGICAL; if ($cpu -lt 1){$cpu=[Environment]::ProcessorCount}; [int]([math]::Max([math]::Min($cpu,$memJobs),1))"') do set "PARALLEL_JOBS=%%A"
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
python scripts\tests\overparallel_benchmark.py %BENCH_ARGS% %*
set "RC=%errorlevel%"

popd
exit /b %RC%
