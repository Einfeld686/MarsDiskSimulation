@echo off
rem Windows runner for tau-timescale visualization (plot_tau_timescales.py)
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
set "PYTHON_BOOT=%PYTHON_EXE%"

for %%I in ("%~dp0..\..\..") do set "REPO=%%~fI"
pushd "%REPO%"

if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.[setup] Creating virtual environment in %VENV_DIR%...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if %errorlevel% neq 0 (
    echo.[error] Failed to create virtual environment.
    popd
    exit /b %errorlevel%
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
  echo.[error] Failed to activate virtual environment.
  popd
  exit /b %errorlevel%
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo.[setup] Installing/upgrading dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo.[error] Dependency installation failed.
    popd
    exit /b %errorlevel%
  )
) else (
  echo.[warn] %REQ_FILE% not found; skipping dependency install.
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
    popd
    exit /b 2
  )
  echo.[info] Using latest run: !DEFAULT_RUN!
  set "PLOT_ARGS=--run \"!DEFAULT_RUN!\""
)

"%PYTHON_EXE%" scripts\plots\plot_tau_timescales.py !PLOT_ARGS!
set EXITCODE=%errorlevel%
if %EXITCODE% neq 0 (
  echo.[error] Plot failed with exit code %EXITCODE%.
  popd
  exit /b %EXITCODE%
)

popd
endlocal
