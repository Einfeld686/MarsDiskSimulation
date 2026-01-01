@echo off
rem Windows runner for tau-timescale visualization (plot_tau_timescales.py)
setlocal EnableExtensions EnableDelayedExpansion

set "REPO=%~dp0..\..\.."
for %%I in ("%REPO%") do set "REPO=%%~fI"
pushd "%REPO%"
set "MARSDISK_POPD_ACTIVE=1"

if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"
set "RUNSETS_COMMON_DIR=%REPO%\scripts\runsets\common"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\venv_bootstrap.cmd"
if not exist "%VENV_BOOTSTRAP_CMD%" (
  echo.[error] venv_bootstrap helper not found: "%VENV_BOOTSTRAP_CMD%"
  call :popd_safe
  exit /b 1
)
call "%VENV_BOOTSTRAP_CMD%"
if errorlevel 1 (
  set "BOOTSTRAP_RC=%errorlevel%"
  echo.[error] Failed to initialize Python environment.
  call :popd_safe
  exit /b %BOOTSTRAP_RC%
)

set "MPLBACKEND=Agg"

set "TOTAL_GB="
set "CPU_LOGICAL="
for /f "usebackq tokens=1-3 delims=|" %%A in (`"%PYTHON_EXE%" scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
  set "TOTAL_GB=%%A"
  set "CPU_LOGICAL=%%B"
)
if not defined TOTAL_GB set "TOTAL_GB=0"

if not defined STREAM_MEM_GB (
  for /f %%A in ('"%PYTHON_EXE%" -c "import math,os; total=float(os.environ.get('TOTAL_GB','0') or 0); total_floor=int(math.floor(total)); candidate=max(8,int(math.floor(total_floor*0.6))); limit=max(2,total_floor-4); print(int(min(candidate,limit)))"') do set "STREAM_MEM_GB=%%A"
)

if not defined CPU_LOGICAL (
  for /f %%A in ('"%PYTHON_EXE%" -c "import os; print(os.cpu_count() or 1)"') do set "CPU_LOGICAL=%%A"
)

if not defined STREAM_MEM_GB set "STREAM_MEM_GB=8"

echo.[sys] mem_total_gb=%TOTAL_GB% cpu_logical=%CPU_LOGICAL% stream_mem_gb=%STREAM_MEM_GB%

set "PLOT_ARGS=%*"
if "%~1"=="" (
  for /f "usebackq delims=" %%A in (`"%PYTHON_EXE%" -c "from pathlib import Path; import sys; root=Path('out'); if not root.exists(): sys.exit(2); files=list(root.rglob('run.parquet')); files=files or list(root.rglob('run_chunk_*.parquet')); if not files: sys.exit(3); latest=max(files, key=lambda p: p.stat().st_mtime); print(latest.parent.parent)"`) do set "DEFAULT_RUN=%%A"
  if not defined DEFAULT_RUN (
    echo.[error] No run outputs found under out\\ (need series\\run.parquet or run_chunk_*.parquet).
    call :popd_safe
    exit /b 2
  )
  echo.[info] Using latest run: !DEFAULT_RUN!
  set "PLOT_ARGS=--run \"!DEFAULT_RUN!\""
)

"%PYTHON_EXE%" scripts\plots\plot_tau_timescales.py !PLOT_ARGS!
set EXITCODE=%errorlevel%
if %EXITCODE% neq 0 (
  echo.[error] Plot failed with exit code %EXITCODE%.
  call :popd_safe
  exit /b %EXITCODE%
)

call :popd_safe
endlocal

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%
