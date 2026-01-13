@echo off
rem Test script for parallel job launching on Windows
rem Usage: scripts\tests\test_parallel_launch.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.========================================
echo.Parallel Launch Test Suite
echo.========================================
echo.

rem Find repo root
for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=%REPO_ROOT%

rem Resolve Python via shared helper
set "RUNSETS_COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
set "PYTHON_EXEC_CMD=%RUNSETS_COMMON_DIR%\python_exec.cmd"
set "RESOLVE_PYTHON_CMD=%RUNSETS_COMMON_DIR%\resolve_python.cmd"
if not exist "%PYTHON_EXEC_CMD%" (
    echo.[error] python_exec helper not found: %PYTHON_EXEC_CMD%
    exit /b 1
)
if not exist "%RESOLVE_PYTHON_CMD%" (
    echo.[error] resolve_python helper not found: %RESOLVE_PYTHON_CMD%
    exit /b 1
)
call "%RESOLVE_PYTHON_CMD%"
if not "!errorlevel!"=="0" (
    echo.[error] Python resolution failed
    exit /b 1
)
echo.[info] PYTHON_CMD=%PYTHON_CMD%

rem Test Python version
call "%PYTHON_EXEC_CMD%" -c "import sys; print(f'Python {sys.version}')"
if not "!errorlevel!"=="0" (
    echo.[error] Python execution failed
    exit /b 1
)

rem Set paths
set "WIN_PROCESS_PY=%REPO_ROOT%\scripts\runsets\common\win_process.py"
set "TMP_ROOT=%TEMP%"

echo.[info] WIN_PROCESS_PY=%WIN_PROCESS_PY%
echo.[info] TMP_ROOT=%TMP_ROOT%
echo.

rem ========================================
echo.Test 1: Basic Python execution with quoted path
echo.----------------------------------------
call "%PYTHON_EXEC_CMD%" -c "print('Test 1 PASSED: Basic Python execution works')"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 1 failed
) else (
    echo.[PASS] Test 1
)
echo.

rem ========================================
echo.Test 2: win_process.py --help
echo.----------------------------------------
(
    call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" --help
) >nul 2>&1
set "TEST2_RC=!errorlevel!"
if not "!TEST2_RC!"=="0" (
    echo.[FAIL] Test 2 failed - win_process.py --help returned error
    call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" --help
) else (
    echo.[PASS] Test 2
)
echo.

rem ========================================
echo.Test 3: Simple echo command via --cmd
echo.----------------------------------------
set "TEST_CMD=echo Test3 Success"
call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "%TEST_CMD%" --window-style hidden --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 3 failed
) else (
    echo.[PASS] Test 3 - PID returned
)
echo.

rem ========================================
echo.Test 4: Command via --cmd-file
echo.----------------------------------------
set "TEST_CMD_FILE=%TMP_ROOT%\test_cmd_file.tmp"
echo echo Test4 via file > "%TEST_CMD_FILE%"
echo.[debug] Command file contents:
type "%TEST_CMD_FILE%"
call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd-file "%TEST_CMD_FILE%" --window-style hidden --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 4 failed
) else (
    echo.[PASS] Test 4 - PID returned
)
del "%TEST_CMD_FILE%" >nul 2>&1
echo.

rem ========================================
echo.Test 5: Command via stdin (pipe)
echo.----------------------------------------
echo echo Test5 via stdin | cmd /c ""%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd-stdin --window-style hidden --cwd "%REPO_ROOT%""
set "TEST5_RC=!errorlevel!"
if not "!TEST5_RC!"=="0" (
    echo.[FAIL] Test 5 failed
) else (
    echo.[PASS] Test 5 - PID returned
)
echo.

rem ========================================
echo.Test 6: Complex command with special characters
echo.----------------------------------------
set "COMPLEX_CMD=set FOO=bar&& echo FOO is set"
echo.[debug] COMPLEX_CMD=%COMPLEX_CMD%
call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "%COMPLEX_CMD%" --window-style hidden --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 6 failed
) else (
    echo.[PASS] Test 6 - PID returned
)
echo.

rem ========================================
echo.Test 7: Command with call to batch file
echo.----------------------------------------
set "BATCH_CMD=call echo Test7 with call"
echo.[debug] BATCH_CMD=%BATCH_CMD%
call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "%BATCH_CMD%" --window-style hidden --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 7 failed
) else (
    echo.[PASS] Test 7 - PID returned
)
echo.

rem ========================================
echo.Test 8: Verify spawned process actually runs (visible window)
echo.----------------------------------------
echo.[info] This test will open a visible window that should show "Test8 Success" and pause
set "VISIBLE_CMD=echo Test8 Success && echo Press any key to close... && pause"
call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "%VISIBLE_CMD%" --window-style normal --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 8 failed
) else (
    echo.[PASS] Test 8 - Check if a new window appeared with the message
)
echo.

rem ========================================
echo.Test 9: Capture PID to file and verify
echo.----------------------------------------
set "PID_FILE=%TMP_ROOT%\test_pid.tmp"
(
    call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd "echo Test9" --window-style hidden --cwd "%REPO_ROOT%"
) > "%PID_FILE%" 2>&1
echo.[debug] PID file contents:
type "%PID_FILE%"
for /f "usebackq delims=" %%P in ("%PID_FILE%") do set "TEST_PID=%%P"
echo.[debug] TEST_PID=%TEST_PID%
echo %TEST_PID%| findstr /r "^[0-9][0-9]*$" >nul
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 9 failed - PID is not a number
) else (
    echo.[PASS] Test 9 - Valid PID returned: %TEST_PID%
)
del "%PID_FILE%" >nul 2>&1
echo.

rem ========================================
echo.Test 10: Simulate actual job command structure
echo.----------------------------------------
set "RUN_TS=20251231_120000"
set "BATCH_SEED=0"
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_I0=0.05"
set "JOB_SEED=12345"
set "SCRIPT_SELF=%REPO_ROOT%\scripts\research\run_temp_supply_sweep.cmd"

rem Build command like in actual code
set "SIM_JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_I0=!JOB_I0!&& set RUN_ONE_SEED=!JOB_SEED!&& echo All vars set successfully"

echo.[debug] SIM_JOB_CMD=!SIM_JOB_CMD!

rem Write to file first
set "SIM_CMD_FILE=%TMP_ROOT%\sim_cmd.tmp"
>"%SIM_CMD_FILE%" echo !SIM_JOB_CMD!
echo.[debug] Command file contents:
type "%SIM_CMD_FILE%"

call "%PYTHON_EXEC_CMD%" "%WIN_PROCESS_PY%" launch --cmd-file "%SIM_CMD_FILE%" --window-style normal --cwd "%REPO_ROOT%"
if not "!errorlevel!"=="0" (
    echo.[FAIL] Test 10 failed
) else (
    echo.[PASS] Test 10 - Check if window shows "All vars set successfully"
)
del "%SIM_CMD_FILE%" >nul 2>&1
echo.

echo.========================================
echo.Test Suite Complete
echo.========================================

endlocal
