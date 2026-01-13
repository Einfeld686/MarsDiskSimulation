@echo off
rem Run re-measurement commands for cell-parallel speed and python-loop profiling.

setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
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
if not "!errorlevel!"=="0" goto :fail

if "%RUN_HEAVY_CASE%"=="1" (
  echo [info] cell-parallel speed check (heavy)
  "%PYTHON_EXE%" scripts\tests\cell_parallel_speed_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %HEAVY_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %HEAVY_GEOMETRY_NR% --cell-jobs %HEAVY_CELL_JOBS% --seed %RE_SEED%
  if not "!errorlevel!"=="0" goto :fail
)

echo [info] python-loop profile (numba on)
"%PYTHON_EXE%" scripts\tests\python_loop_profile_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %PROFILE_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %RE_GEOMETRY_NR% --seed %RE_SEED% --top-n %PROFILE_TOP_N%
if not "!errorlevel!"=="0" goto :fail

if "%RUN_PROFILE_NUMBA_OFF%"=="1" (
  echo [info] python-loop profile (numba off)
  "%PYTHON_EXE%" scripts\tests\python_loop_profile_check.py --config "%CONFIG%" --out-root "%OUT_ROOT%" --t-end-years %PROFILE_T_END_YEARS% --dt-init %RE_DT_INIT% --geometry-nr %RE_GEOMETRY_NR% --seed %RE_SEED% --top-n %PROFILE_TOP_N% --disable-numba
  if not "!errorlevel!"=="0" goto :fail
)

echo [done] re-measurement commands completed.
call :popd_safe 0
goto :eof

:fail
set "RC=!errorlevel!"
echo [error] re-measurement failed (rc=%RC%).
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
