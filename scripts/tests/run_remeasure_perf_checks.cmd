@echo off
rem Run re-measurement commands for cell-parallel speed and python-loop profiling.

setlocal EnableExtensions

if not defined PYTHON_EXE (
  for %%P in (python3.11 python py) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo [error] python3.11/python/py not found in PATH
    exit /b 1
  )
) else (
  if not exist "%PYTHON_EXE%" (
    where %PYTHON_EXE% >nul 2>&1
    if errorlevel 1 (
      echo [error] %PYTHON_EXE% not found in PATH
      exit /b 1
    )
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    call :popd_safe
    exit /b 1
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  call :popd_safe
  exit /b 1
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo [setup] Installing dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency install failed.
    call :popd_safe
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

if not defined CONFIG set "CONFIG=configs/base.yml"
if not defined OUT_ROOT set "OUT_ROOT=out/tests/remeasure"

if not defined RE_T_END_YEARS set "RE_T_END_YEARS=0.1"
if not defined RE_DT_INIT set "RE_DT_INIT=5000"
if not defined RE_GEOMETRY_NR set "RE_GEOMETRY_NR=128"
if not defined RE_CELL_JOBS set "RE_CELL_JOBS=4"
if not defined RE_SEED set "RE_SEED=12345"

if not defined PROFILE_T_END_YEARS set "PROFILE_T_END_YEARS=0.05"
if not defined PROFILE_TOP_N set "PROFILE_TOP_N=40"

if not defined RUN_HEAVY_CASE set "RUN_HEAVY_CASE=0"
if not defined HEAVY_T_END_YEARS set "HEAVY_T_END_YEARS=0.2"
if not defined HEAVY_GEOMETRY_NR set "HEAVY_GEOMETRY_NR=256"
if not defined HEAVY_CELL_JOBS set "HEAVY_CELL_JOBS=8"

if not defined RUN_PROFILE_NUMBA_OFF set "RUN_PROFILE_NUMBA_OFF=0"

echo [info] cell-parallel speed check (base)
"%PYTHON_EXE%" scripts\tests\cell_parallel_speed_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %RE_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %RE_GEOMETRY_NR% --cell-jobs %RE_CELL_JOBS% --seed %RE_SEED%
if errorlevel 1 goto :fail

if "%RUN_HEAVY_CASE%"=="1" (
  echo [info] cell-parallel speed check (heavy)
  "%PYTHON_EXE%" scripts\tests\cell_parallel_speed_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %HEAVY_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %HEAVY_GEOMETRY_NR% --cell-jobs %HEAVY_CELL_JOBS% --seed %RE_SEED%
  if errorlevel 1 goto :fail
)

echo [info] python-loop profile (numba on)
"%PYTHON_EXE%" scripts\tests\python_loop_profile_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %PROFILE_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %RE_GEOMETRY_NR% --seed %RE_SEED% --top-n %PROFILE_TOP_N%
if errorlevel 1 goto :fail

if "%RUN_PROFILE_NUMBA_OFF%"=="1" (
  echo [info] python-loop profile (numba off)
  "%PYTHON_EXE%" scripts\tests\python_loop_profile_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %PROFILE_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %RE_GEOMETRY_NR% --seed %RE_SEED% --top-n %PROFILE_TOP_N% --disable-numba
  if errorlevel 1 goto :fail
)

echo [done] re-measurement commands completed.
call :popd_safe
exit /b 0

:fail
set "RC=%errorlevel%"
echo [error] re-measurement failed (rc=%RC%).
call :popd_safe
exit /b %RC%

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%
