@echo off
rem Test --run-one mode directly
rem This tests if the child process (single job execution) works

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo.Test: --run-one mode direct execution
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=!REPO_ROOT!

rem Setup required environment variables for --run-one
rem These must be set BEFORE calling the child script
set "RUN_TS=20251231_test"
set "BATCH_SEED=12345"
set "RUN_ONE_T=5000"
set "RUN_ONE_EPS=1.0"
set "RUN_ONE_TAU=1.0"
set "RUN_ONE_SEED=12345"
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=1"
if not defined SKIP_PIP set "SKIP_PIP=0"
set "DEBUG=1"
set "SWEEP_PARALLEL=1"
rem Set BASE_CONFIG explicitly to avoid inheriting from environment
set "BASE_CONFIG=!REPO_ROOT!\configs\base.yml"
set "SWEEP_TAG=temp_supply_sweep_1d"
set "GEOMETRY_MODE=1D"

echo.
echo.[info] Environment variables set:
echo.  RUN_TS=!RUN_TS!
echo.  BATCH_SEED=!BATCH_SEED!
echo.  RUN_ONE_T=!RUN_ONE_T!
echo.  RUN_ONE_EPS=!RUN_ONE_EPS!
echo.  RUN_ONE_TAU=!RUN_ONE_TAU!
echo.  RUN_ONE_SEED=!RUN_ONE_SEED!
echo.  AUTO_JOBS=!AUTO_JOBS!
echo.  PARALLEL_JOBS=!PARALLEL_JOBS!
echo.  SKIP_PIP=!SKIP_PIP!
echo.  DEBUG=!DEBUG!
echo.  SWEEP_PARALLEL=!SWEEP_PARALLEL!
echo.

set "SCRIPT=!REPO_ROOT!\scripts\research\run_temp_supply_sweep.cmd"
echo.[info] Script: !SCRIPT!
if not exist "!SCRIPT!" (
    echo.[error] Script not found!
    exit /b 1
)
echo.

echo.============================================================
echo.Calling: !SCRIPT! --run-one
echo.============================================================
echo.

call "!SCRIPT!" --run-one

echo.
echo.============================================================
echo.--run-one completed with errorlevel=!errorlevel!
echo.============================================================

endlocal
