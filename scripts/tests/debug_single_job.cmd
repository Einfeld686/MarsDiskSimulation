@echo off
rem Debug script: Run a single sweep job in foreground to see errors
rem Usage: scripts\tests\debug_single_job.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo. Debug: Single Job Foreground Execution
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=!REPO_ROOT!
cd /d "!REPO_ROOT!"

rem --- Python resolution ---
set "RUNSETS_COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
call "!RUNSETS_COMMON_DIR!\resolve_python.cmd"
set "PYTHON_RC=!errorlevel!"
if defined PYTHON_RC if !PYTHON_RC! neq 0 (
    echo.[error] Python resolution failed
    exit /b 1
)
echo.[info] PYTHON_EXE=!PYTHON_EXE!
echo.

rem --- Set environment variables for a single test job ---
set "RUN_TS=debug_test"
set "BATCH_SEED=0"
set "RUN_ONE_T=3000"
set "RUN_ONE_EPS=1.0"
set "RUN_ONE_TAU=1.0"
set "RUN_ONE_I0=0.05"
set "RUN_ONE_SEED=12345"
set "SWEEP_TAG=debug_test"
set "GEOMETRY_MODE=1D"
set "BASE_CONFIG=!REPO_ROOT!\scripts\runsets\common\base.yml"
set "DEBUG=1"
set "QUIET_MODE=0"
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=1"
set "SKIP_PIP=1"

echo.[info] Test parameters:
echo.  RUN_ONE_T=!RUN_ONE_T!
echo.  RUN_ONE_EPS=!RUN_ONE_EPS!
echo.  RUN_ONE_TAU=!RUN_ONE_TAU!
echo.  RUN_ONE_I0=!RUN_ONE_I0!
echo.  RUN_ONE_SEED=!RUN_ONE_SEED!
echo.  BASE_CONFIG=!BASE_CONFIG!
echo.

rem --- Check config file exists ---
if not exist "!BASE_CONFIG!" (
    echo.[error] Config file not found: !BASE_CONFIG!
    exit /b 1
)
echo.[OK] Config file exists
echo.

rem --- Check temperature table exists ---
set "T_TABLE=data\mars_temperature_T!RUN_ONE_T!p0K.csv"
if not exist "!T_TABLE!" (
    echo.[warn] Temperature table not found: !T_TABLE!
    echo.[warn] This may cause errors during simulation
) else (
    echo.[OK] Temperature table exists: !T_TABLE!
)
echo.

echo.============================================================
echo. Running run_one.py directly (foreground)
echo.============================================================
echo.

if defined PYTHON_ARGS (
    "!PYTHON_EXE!" !PYTHON_ARGS! scripts\runsets\common\run_one.py
) else (
    "!PYTHON_EXE!" scripts\runsets\common\run_one.py
)

set "RC=!errorlevel!"
echo.
echo.============================================================
echo. run_one.py completed with exit code: !RC!
echo.============================================================

if defined RC if !RC! neq 0 (
    echo.
    echo.[FAIL] Job failed! Check the error messages above.
    echo.
    echo.Common causes:
    echo.  1. Missing dependencies (pip install -r requirements.txt)
    echo.  2. Missing temperature table data file
    echo.  3. Config file parsing error
    echo.  4. marsdisk module import error
) else (
    echo.
    echo.[OK] Job completed successfully!
    echo.Output should be in: out\debug_test\
)

endlocal & exit /b %RC%
