@echo off
rem Test what happens when win_process.py spawns a child that runs --run-one
rem This simulates exactly what run_sweep does

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo.Test: Spawned --run-one execution (like parallel sweep)
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
set "WIN_PROCESS_PY=!REPO_ROOT!\scripts\runsets\common\win_process.py"
set "TMP_ROOT=%TEMP%"

rem Find Python 3.11
set "PYTHON_EXE="
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
) do (
    if not defined PYTHON_EXE if exist %%D set "PYTHON_EXE=%%~D"
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

echo.[info] REPO_ROOT=!REPO_ROOT!
echo.[info] PYTHON_EXE=!PYTHON_EXE!
echo.

set "SCRIPT_SELF_USE=!REPO_ROOT!\scripts\research\run_temp_supply_sweep.cmd"
echo.[info] SCRIPT_SELF_USE=!SCRIPT_SELF_USE!

rem Build the exact command that run_sweep uses
set "RUN_TS=20251231_test"
set "BATCH_SEED=0"
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_SEED=12345"

rem This is the exact format from run_temp_supply_sweep.cmd :launch_job
set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& set AUTO_JOBS=0&& set PARALLEL_JOBS=1&& set SKIP_PIP=1&& set DEBUG=1&& call ""!SCRIPT_SELF_USE!"" --run-one"

echo.[info] JOB_CMD=!JOB_CMD!
echo.

rem Write command to file
set "CMD_FILE=!TMP_ROOT!\test_spawn_run_one.tmp"
> "!CMD_FILE!" echo !JOB_CMD!
echo.[info] Command written to: !CMD_FILE!
echo.[info] File contents:
type "!CMD_FILE!"
echo.
echo.

echo.============================================================
echo.Launching with VISIBLE window to see output
echo.============================================================
echo.Watch the new window that opens - it should show the simulation running
echo.If it closes immediately, there's an error
echo.

"!PYTHON_EXE!" "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style normal --cwd "!REPO_ROOT!"

echo.
echo.[info] Process launched. Check the spawned window for output.
echo.
del "!CMD_FILE!" >nul 2>&1

pause
endlocal
