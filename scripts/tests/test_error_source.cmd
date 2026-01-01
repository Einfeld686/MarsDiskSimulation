@echo off
rem Test script to identify where the "invalid filename" error comes from
rem This traces each step of the launch process
rem Usage: scripts\tests\test_error_source.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo.Error Source Identification Test
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
set "WIN_PROCESS_PY=!REPO_ROOT!\scripts\runsets\common\win_process.py"
set "TMP_ROOT=%TEMP%"

set "COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
if not exist "!COMMON_DIR!\resolve_python.cmd" (
    echo.[error] resolve_python.cmd not found: "!COMMON_DIR!\resolve_python.cmd"
    exit /b 1
)
call "!COMMON_DIR!\resolve_python.cmd"
if errorlevel 1 exit /b 1

echo.[info] PYTHON_CMD=!PYTHON_CMD!
echo.[info] REPO_ROOT=!REPO_ROOT!
echo.[info] TMP_ROOT=!TMP_ROOT!
echo.

rem ============================================================
echo.Step 1: Test basic echo redirection to file
echo.------------------------------------------------------------
set "TEST1_FILE=!TMP_ROOT!\test1_!RANDOM!.tmp"
echo.[action] echo test ^> "!TEST1_FILE!"
echo test > "!TEST1_FILE!"
if exist "!TEST1_FILE!" (
    echo.[PASS] File created successfully
    type "!TEST1_FILE!"
    del "!TEST1_FILE!"
) else (
    echo.[FAIL] Could not create file
)
echo.

rem ============================================================
echo.Step 2: Test variable with special characters in filename
echo.------------------------------------------------------------
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "TEST2_FILE=!TMP_ROOT!\marsdisk_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"
echo.[action] Writing to: !TEST2_FILE!
echo test > "!TEST2_FILE!"
if exist "!TEST2_FILE!" (
    echo.[PASS] File created with dots in filename
    del "!TEST2_FILE!"
) else (
    echo.[FAIL] Could not create file with dots in name
)
echo.

rem ============================================================
echo.Step 3: Test cmd file creation with complex content
echo.------------------------------------------------------------
set "RUN_TS=20251231_120000"
set "BATCH_SEED=0"
set "JOB_SEED=12345"
set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& echo done"
set "CMD_FILE=!TMP_ROOT!\marsdisk_cmd_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"
echo.[action] Writing JOB_CMD to: !CMD_FILE!
echo.[debug] JOB_CMD=!JOB_CMD!
> "!CMD_FILE!" echo !JOB_CMD!
if exist "!CMD_FILE!" (
    echo.[PASS] Command file created
    echo.[debug] File contents:
    type "!CMD_FILE!"
    echo.
) else (
    echo.[FAIL] Could not create command file
)
echo.

rem ============================================================
echo.Step 4: Test Python call with file input
echo.------------------------------------------------------------
echo.[action] Calling win_process.py with --cmd-file
set "PID_FILE=!TMP_ROOT!\marsdisk_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"
echo.[debug] Output to: !PID_FILE!
echo.[debug] Full command:
echo !PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style hidden --cwd "!REPO_ROOT!"
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-file "!CMD_FILE!" --window-style hidden --cwd "!REPO_ROOT!" > "!PID_FILE!" 2>&1
set "LAUNCH_RC=!errorlevel!"
echo.[debug] Return code: !LAUNCH_RC!
if exist "!PID_FILE!" (
    echo.[debug] PID file contents:
    type "!PID_FILE!"
    echo.
    set /p PID_VAL=<"!PID_FILE!"
    echo.[debug] PID_VAL=!PID_VAL!
    echo !PID_VAL! | findstr /r "^[0-9][0-9]*$" >nul
    if errorlevel 1 (
        echo.[WARN] PID is not a number - may contain error message
    ) else (
        echo.[PASS] Valid PID returned: !PID_VAL!
    )
    del "!PID_FILE!"
) else (
    echo.[FAIL] PID file not created
)
del "!CMD_FILE!" >nul 2>&1
echo.

rem ============================================================
echo.Step 5: Test with 2^>^&1 redirection
echo.------------------------------------------------------------
echo.[info] Testing if the error message comes from stderr
set "TEST5_FILE=!TMP_ROOT!\test5_!RANDOM!.tmp"
echo.[action] Running command and capturing stderr separately
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd "echo test5" --window-style hidden --cwd "!REPO_ROOT!" > "!TEST5_FILE!" 2> "!TEST5_FILE!.err"
echo.[debug] stdout:
type "!TEST5_FILE!"
echo.
echo.[debug] stderr:
type "!TEST5_FILE!.err"
echo.
del "!TEST5_FILE!" >nul 2>&1
del "!TEST5_FILE!.err" >nul 2>&1
echo.

rem ============================================================
echo.Step 6: Test the actual --run-one invocation (dry run echo only)
echo.------------------------------------------------------------
set "SCRIPT_SELF_USE=!REPO_ROOT!\scripts\research\run_temp_supply_sweep.cmd"
echo.[info] SCRIPT_SELF_USE=!SCRIPT_SELF_USE!
if not exist "!SCRIPT_SELF_USE!" (
    echo.[FAIL] Script does not exist!
    goto :end
)

set "FULL_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& set AUTO_JOBS=0&& set PARALLEL_JOBS=1&& set SKIP_PIP=1&& call ""!SCRIPT_SELF_USE!"" --run-one"
echo.[debug] FULL_CMD=!FULL_CMD!
echo.
echo.[action] Writing full command to file and launching with VISIBLE window
set "FULL_CMD_FILE=!TMP_ROOT!\test6_full_cmd.tmp"
> "!FULL_CMD_FILE!" echo !FULL_CMD!
echo.[debug] Command file created: !FULL_CMD_FILE!
echo.[debug] Contents:
type "!FULL_CMD_FILE!"
echo.

echo.[question] Launch with visible window to see what happens? (Y/N)
choice /c YN /m "Launch"
if errorlevel 2 goto :skip6
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-file "!FULL_CMD_FILE!" --window-style normal --cwd "!REPO_ROOT!"
:skip6
del "!FULL_CMD_FILE!" >nul 2>&1
echo.

:end
echo.============================================================
echo.Test complete
echo.============================================================

endlocal
