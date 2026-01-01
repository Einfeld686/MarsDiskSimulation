@echo off
rem Detailed test for job launch mechanism
rem This test simulates what run_temp_supply_sweep.cmd does
rem Usage: scripts\tests\test_job_launch_detailed.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo.Detailed Job Launch Test
echo.============================================================
echo.

rem Find repo root
for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=!REPO_ROOT!

rem Setup paths
set "WIN_PROCESS_PY=!REPO_ROOT!\scripts\runsets\common\win_process.py"
set "TMP_ROOT=%TEMP%"

echo.[info] WIN_PROCESS_PY=!WIN_PROCESS_PY!
echo.[info] TMP_ROOT=!TMP_ROOT!
echo.

rem Resolve Python via shared helper
set "RUNSETS_COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
set "PYTHON_EXEC_CMD=!RUNSETS_COMMON_DIR!\python_exec.cmd"
set "RESOLVE_PYTHON_CMD=!RUNSETS_COMMON_DIR!\resolve_python.cmd"
if not exist "!PYTHON_EXEC_CMD!" (
    echo.[error] python_exec helper not found: !PYTHON_EXEC_CMD!
    exit /b 1
)
if not exist "!RESOLVE_PYTHON_CMD!" (
    echo.[error] resolve_python helper not found: !RESOLVE_PYTHON_CMD!
    exit /b 1
)
call "!RESOLVE_PYTHON_CMD!"
if errorlevel 1 (
    echo.[error] Python resolution failed
    exit /b 1
)

echo.[info] PYTHON_EXE=[!PYTHON_EXE!]
echo.[info] PYTHON_CMD=[!PYTHON_CMD!]
echo.

rem Verify Python works
echo.--- Test: Python version ---
call "!PYTHON_EXEC_CMD!" -c "import sys; print(f'Python {sys.version}')"
echo.

rem ============================================================
echo.============================================================
echo.Test A: Simple command launch (visible window)
echo.============================================================
set "TEST_A_CMD=echo Test A Success && echo Press any key... && pause"
echo.[debug] Command: !TEST_A_CMD!
echo.[action] Launching visible window...
call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd "!TEST_A_CMD!" --window-style normal --cwd "!REPO_ROOT!"
echo.[result] PID returned: check above, window should have appeared
echo.

rem ============================================================
echo.============================================================
echo.Test B: Command with environment variable setting
echo.============================================================
set "TEST_B_CMD=set FOO=bar&& echo FOO is: %%FOO%% && pause"
echo.[debug] Command: !TEST_B_CMD!
echo.[action] Launching visible window...
call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd "!TEST_B_CMD!" --window-style normal --cwd "!REPO_ROOT!"
echo.[result] Window should show "FOO is: bar"
echo.

rem ============================================================
echo.============================================================
echo.Test C: Command file method (like actual code)
echo.============================================================
set "TEST_C_CMD=echo Test C via file && echo Environment: && set && pause"
set "CMD_FILE=!TMP_ROOT!\test_c_cmd.tmp"
echo.[debug] Writing command to file: !CMD_FILE!
> "!CMD_FILE!" echo !TEST_C_CMD!
echo.[debug] File contents:
type "!CMD_FILE!"
echo.
echo.[action] Launching via --cmd-file...
call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style normal --cwd "!REPO_ROOT!"
echo.[result] Check window for environment dump
del "!CMD_FILE!" >nul 2>&1
echo.

rem ============================================================
echo.============================================================
echo.Test D: Simulate actual JOB_CMD structure
echo.============================================================
set "RUN_TS=20251231_120000"
set "BATCH_SEED=0"
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_SEED=12345"
set "SCRIPT_SELF=!REPO_ROOT!\scripts\research\run_temp_supply_sweep.cmd"

rem Build command exactly like in run_temp_supply_sweep.cmd
set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& echo JOB_CMD executed && echo RUN_ONE_T=%%RUN_ONE_T%% && echo RUN_ONE_EPS=%%RUN_ONE_EPS%% && pause"

echo.[debug] JOB_CMD=!JOB_CMD!
set "CMD_FILE=!TMP_ROOT!\test_d_cmd.tmp"
echo.[debug] Writing to: !CMD_FILE!
> "!CMD_FILE!" echo !JOB_CMD!
echo.[debug] File contents:
type "!CMD_FILE!"
echo.
echo.[action] Launching...
call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style normal --cwd "!REPO_ROOT!"
echo.[result] Window should show RUN_ONE_T=5000, RUN_ONE_EPS=1.0
del "!CMD_FILE!" >nul 2>&1
echo.

rem ============================================================
echo.============================================================
echo.Test E: Call batch file directly
echo.============================================================
set "TEST_BATCH=!TMP_ROOT!\test_e_batch.cmd"
echo.[debug] Creating test batch file: !TEST_BATCH!
> "!TEST_BATCH!" echo @echo off
>> "!TEST_BATCH!" echo echo Test E batch file executed
>> "!TEST_BATCH!" echo echo Current directory: %%CD%%
>> "!TEST_BATCH!" echo pause
echo.[debug] Batch file contents:
type "!TEST_BATCH!"
echo.
set "CALL_CMD=call "!TEST_BATCH!""
echo.[debug] Call command: !CALL_CMD!
call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd "!CALL_CMD!" --window-style normal --cwd "!REPO_ROOT!"
echo.[result] Window should show batch file output
del "!TEST_BATCH!" >nul 2>&1
echo.

rem ============================================================
echo.============================================================
echo.Test F: Full simulation of --run-one call
echo.============================================================
set "SCRIPT_SELF_USE=!REPO_ROOT!\scripts\research\run_temp_supply_sweep.cmd"
echo.[debug] SCRIPT_SELF_USE=!SCRIPT_SELF_USE!
echo.[debug] Does script exist?
if exist "!SCRIPT_SELF_USE!" (
    echo.[info] Script exists
) else (
    echo.[error] Script NOT found!
)

set "FULL_JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& set AUTO_JOBS=0&& set PARALLEL_JOBS=1&& set SKIP_PIP=1&& call ""!SCRIPT_SELF_USE!"" --run-one"

echo.[debug] FULL_JOB_CMD=!FULL_JOB_CMD!
echo.
echo.[question] Do you want to launch the actual script? (This will start a real simulation)
echo.[question] Press Y to continue, any other key to skip...
choice /c YN /m "Launch actual script"
if errorlevel 2 goto :skip_f
if errorlevel 1 (
    set "CMD_FILE=!TMP_ROOT!\test_f_cmd.tmp"
    > "!CMD_FILE!" echo !FULL_JOB_CMD!
    echo.[action] Launching actual --run-one...
    call "!PYTHON_EXEC_CMD!" "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style normal --cwd "!REPO_ROOT!"
    del "!CMD_FILE!" >nul 2>&1
)
:skip_f
echo.

rem ============================================================
echo.============================================================
echo.Test G: Check TMP_ROOT path handling
echo.============================================================
echo.[info] TMP_ROOT=!TMP_ROOT!
echo.[debug] Does TMP_ROOT exist?
if exist "!TMP_ROOT!" (
    echo.[info] TMP_ROOT exists
) else (
    echo.[error] TMP_ROOT NOT found!
)
echo.[debug] Can we create files there?
set "TEST_FILE=!TMP_ROOT!\marsdisk_test_!RANDOM!.tmp"
> "!TEST_FILE!" echo test
if exist "!TEST_FILE!" (
    echo.[info] Can create files in TMP_ROOT
    del "!TEST_FILE!" >nul 2>&1
) else (
    echo.[error] Cannot create files in TMP_ROOT!
)
echo.

echo.============================================================
echo.All tests complete
echo.============================================================
echo.
echo.Summary:
echo.  - If windows appeared and showed expected output, job launch works
echo.  - If windows appeared but closed immediately, there's an error in the spawned process
echo.  - If no windows appeared, the launch mechanism has a problem
echo.
echo.To debug further, try running the actual sweep with visible windows:
echo.  set PARALLEL_WINDOW_STYLE=Normal
echo.  scripts\runsets\windows\run_sweep.cmd --debug
echo.

endlocal
exit /b 0

:trim_var
rem Trims trailing spaces from the variable named %1
setlocal EnableDelayedExpansion
set "TRIM_NAME=%~1"
set "TRIM_VAL=!%TRIM_NAME%!"
:trim_loop
if "!TRIM_VAL:~-1!"==" " (
    set "TRIM_VAL=!TRIM_VAL:~0,-1!"
    goto :trim_loop
)
endlocal & set "%~1=%TRIM_VAL%"
exit /b 0
