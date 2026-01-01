@echo off
rem Debug script: Run ONE parallel job with output captured to log file
rem This will help identify why child processes exit without producing output

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo. Debug: Single Parallel Job with Log Capture
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=!REPO_ROOT!
cd /d "!REPO_ROOT!"

rem --- Python resolution ---
set "RUNSETS_COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
call "!RUNSETS_COMMON_DIR!\resolve_python.cmd"
if !errorlevel! neq 0 (
    echo.[error] Python resolution failed
    exit /b 1
)
echo.[info] PYTHON_EXE=!PYTHON_EXE!
echo.

rem --- Set environment variables ---
set "RUN_TS=debug_parallel"
set "BATCH_SEED=0"
set "RUN_ONE_T=3000"
set "RUN_ONE_EPS=1.0"
set "RUN_ONE_TAU=1.0"
set "RUN_ONE_SEED=12345"
set "SWEEP_TAG=debug_parallel"
set "GEOMETRY_MODE=1D"
set "BASE_CONFIG=!REPO_ROOT!\scripts\runsets\common\base.yml"
set "BATCH_ROOT=!REPO_ROOT!\out"
set "DEBUG=1"
set "QUIET_MODE=0"
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=1"
rem --- Flags to skip re-initialization in child script ---
set "SKIP_PIP=1"
set "SKIP_VENV=1"
set "REQUIREMENTS_INSTALLED=1"
set "RUN_ONE_MODE=1"

echo.[info] Test parameters:
echo.  RUN_ONE_T=!RUN_ONE_T!
echo.  RUN_ONE_EPS=!RUN_ONE_EPS!
echo.  RUN_ONE_TAU=!RUN_ONE_TAU!
echo.  BASE_CONFIG=!BASE_CONFIG!
echo.  BATCH_ROOT=!BATCH_ROOT!
echo.

rem --- Ensure dependencies are installed (like parent process would do) ---
echo.[setup] Installing dependencies from !REPO_ROOT!\requirements.txt ...
"!PYTHON_EXE!" -m pip install -r "!REPO_ROOT!\requirements.txt" --quiet
if !errorlevel! neq 0 (
    echo.[warn] pip install had warnings but continuing...
)

rem --- Create log directory ---
set "LOG_DIR=!REPO_ROOT!\out\debug"
if not exist "!LOG_DIR!" mkdir "!LOG_DIR!"
set "LOG_FILE=!LOG_DIR!\child_job_log.txt"

echo.============================================================
echo. Step 1: Test run_temp_supply_sweep.cmd --run-one directly
echo. Output will be logged to: !LOG_FILE!
echo.============================================================
echo.

echo.=== Direct call to run_temp_supply_sweep.cmd --run-one === > "!LOG_FILE!" 2>&1
echo.Environment: >> "!LOG_FILE!" 2>&1
echo.  PYTHON_EXE=!PYTHON_EXE! >> "!LOG_FILE!" 2>&1
echo.  BASE_CONFIG=!BASE_CONFIG! >> "!LOG_FILE!" 2>&1
echo.  BATCH_ROOT=!BATCH_ROOT! >> "!LOG_FILE!" 2>&1
echo.  RUN_ONE_T=!RUN_ONE_T! >> "!LOG_FILE!" 2>&1
echo.  RUN_ONE_EPS=!RUN_ONE_EPS! >> "!LOG_FILE!" 2>&1
echo.  RUN_ONE_TAU=!RUN_ONE_TAU! >> "!LOG_FILE!" 2>&1
echo. >> "!LOG_FILE!" 2>&1

call scripts\research\run_temp_supply_sweep.cmd --run-one >> "!LOG_FILE!" 2>&1
set "RC=!errorlevel!"

echo. >> "!LOG_FILE!" 2>&1
echo.=== Exit code: !RC! === >> "!LOG_FILE!" 2>&1

echo.
echo.[info] Direct call completed with exit code: !RC!
echo.[info] Check log file: !LOG_FILE!
echo.

echo.============================================================
echo. Step 2: Show last 50 lines of log
echo.============================================================
echo.

if exist "!LOG_FILE!" (
    echo.--- Last 50 lines of !LOG_FILE! ---
    powershell -Command "Get-Content '!LOG_FILE!' -Tail 50"
) else (
    echo.[error] Log file not created!
)

echo.
echo.============================================================
echo. Step 3: Check output directory
echo.============================================================
echo.

set "OUT_DIR=!REPO_ROOT!\out\debug_parallel"
if exist "!OUT_DIR!" (
    echo.[info] Output directory exists: !OUT_DIR!
    dir /s "!OUT_DIR!"
) else (
    echo.[warn] Output directory not found: !OUT_DIR!
)

echo.
echo.============================================================
echo. Debug complete. Check !LOG_FILE! for details.
echo.============================================================

endlocal
