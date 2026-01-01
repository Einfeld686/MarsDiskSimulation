@echo off
rem Test script for parallel job launching
rem Run this in Windows to diagnose JOB_CMD environment variable passing

setlocal EnableExtensions EnableDelayedExpansion

echo ============================================
echo Windows Parallel Job Launch Test
echo ============================================
echo.

rem Get script directory
for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"
echo [DEBUG] SCRIPT_DIR=%SCRIPT_DIR%
rem scripts\tests\ -> go up 2 levels to repo root
cd /d "%SCRIPT_DIR%"
cd ..\..
set "REPO_ROOT=%CD%"
echo [INFO] Repo root: %REPO_ROOT%
set "COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
if not exist "%COMMON_DIR%\resolve_python.cmd" (
    echo [ERROR] resolve_python.cmd not found: "%COMMON_DIR%\resolve_python.cmd"
    exit /b 1
)
call "%COMMON_DIR%\resolve_python.cmd"
if errorlevel 1 exit /b 1
echo [INFO] Python: !PYTHON_CMD!

set "WIN_PROCESS_PY=%REPO_ROOT%\scripts\runsets\common\win_process.py"
echo [INFO] win_process.py: %WIN_PROCESS_PY%

if not exist "%WIN_PROCESS_PY%" (
    echo [DEBUG] Trying alternative path detection...
    rem Try finding from current directory
    if exist "scripts\runsets\common\win_process.py" (
        for %%I in (".") do set "REPO_ROOT=%%~fI"
        set "WIN_PROCESS_PY=!REPO_ROOT!\scripts\runsets\common\win_process.py"
        echo [INFO] Found via current dir: !WIN_PROCESS_PY!
    )
)

if not exist "%WIN_PROCESS_PY%" (
    echo [ERROR] win_process.py not found at: %WIN_PROCESS_PY%
    echo [ERROR] Please run this script from the repository root directory.
    echo [ERROR] Example: cd C:\path\to\MarsDiskSimulation
    echo [ERROR]          scripts\tests\test_win_parallel_batch.cmd
    exit /b 1
)

set "TMP_ROOT=%TEMP%"
if not exist "%TMP_ROOT%" set "TMP_ROOT=%REPO_ROOT%tmp"
echo [INFO] TMP_ROOT: %TMP_ROOT%

echo.
echo ============================================
echo Test 1: Direct --cmd option
echo ============================================
set "TEST_CMD=echo DIRECT_CMD_SUCCESS"
echo [INFO] Command: %TEST_CMD%
!PYTHON_CMD! "%WIN_PROCESS_PY%" launch --cmd "%TEST_CMD%"
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 2: --cmd-stdin option (new method)
echo ============================================
set "TEST_CMD=echo STDIN_CMD_SUCCESS"
echo [INFO] Command: %TEST_CMD%
echo !TEST_CMD!| !PYTHON_CMD! "%WIN_PROCESS_PY%" launch --cmd-stdin
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 3: --cmd-stdin with delayed expansion
echo ============================================
set "TEST_VAR=DELAYED_VAR_VALUE"
set "TEST_CMD=echo TEST_VAR=!TEST_VAR!"
echo [INFO] Command: !TEST_CMD!
echo !TEST_CMD!| !PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-stdin
echo [INFO] Exit code: !errorlevel!

echo.
echo ============================================
echo Test 4: --cmd-stdin with complex command
echo ============================================
set "TEST_CMD=set A=1&& set B=2&& echo Complex command executed"
echo [INFO] Command: !TEST_CMD!
echo !TEST_CMD!| !PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-stdin
echo [INFO] Exit code: !errorlevel!

echo.
echo ============================================
echo Test 5: Simulating actual launch_job (stdin + file redirect)
echo ============================================
set "RUN_TS=20251231"
set "BATCH_SEED=0"
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_SEED=12345"
set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& echo SIMULATED_JOB_LAUNCH"
echo [INFO] JOB_CMD=!JOB_CMD!

set "PID_FILE=!TMP_ROOT!\test_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"
echo [INFO] PID_FILE=!PID_FILE!

echo !JOB_CMD!| !PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-stdin > "!PID_FILE!" 2>&1
echo [INFO] Command exit code: !errorlevel!

if exist "!PID_FILE!" (
    set /p JOB_PID_TMP=<"!PID_FILE!"
    echo [INFO] PID file content: !JOB_PID_TMP!
    del "!PID_FILE!" >nul 2>&1
    
    rem Check if it's a number
    echo !JOB_PID_TMP!| findstr /r "^[0-9][0-9]*$" >nul
    if errorlevel 1 (
        echo [FAIL] Not a valid PID: !JOB_PID_TMP!
    ) else (
        echo [PASS] Valid PID: !JOB_PID_TMP!
    )
) else (
    echo [FAIL] PID file not created
)

echo.
echo ============================================
echo Test 6: Multiple parallel jobs simulation
echo ============================================
set "PIDS="
for %%T in (5000 4000 3000) do (
    set "JOB_CMD=echo Job T=%%T started && timeout /t 2 /nobreak"
    set "PID_FILE=!TMP_ROOT!\test_pid_%%T.tmp"
    echo !JOB_CMD!| !PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-stdin > "!PID_FILE!" 2>&1
    if exist "!PID_FILE!" (
        set /p TEMP_PID=<"!PID_FILE!"
        del "!PID_FILE!" >nul 2>&1
        echo !TEMP_PID!| findstr /r "^[0-9][0-9]*$" >nul
        if not errorlevel 1 (
            set "PIDS=!PIDS! !TEMP_PID!"
            echo [INFO] Launched T=%%T with PID=!TEMP_PID!
        ) else (
            echo [WARN] T=%%T: Invalid response: !TEMP_PID!
        )
    ) else (
        echo [WARN] T=%%T: No PID file created
    )
)
echo [INFO] All PIDs: !PIDS!

echo.
echo ============================================
echo All tests completed
echo ============================================

endlocal
