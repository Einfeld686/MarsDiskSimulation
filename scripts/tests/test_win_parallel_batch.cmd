@echo off
rem Test script for parallel job launching
rem Run this in Windows to diagnose JOB_CMD environment variable passing

setlocal EnableExtensions EnableDelayedExpansion

echo ============================================
echo Windows Parallel Job Launch Test
echo ============================================
echo.

rem Find Python
set "PYTHON_CMD="
for %%P in (python3.11 python) do (
    if not defined PYTHON_CMD (
        where %%P >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=%%P"
    )
)
if not defined PYTHON_CMD (
    echo [ERROR] Python not found
    exit /b 1
)
echo [INFO] Python: %PYTHON_CMD%

rem Get script directory
for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"
set "REPO_ROOT=%SCRIPT_DIR%..\..\..\"
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
echo [INFO] Repo root: %REPO_ROOT%

set "WIN_PROCESS_PY=%REPO_ROOT%scripts\runsets\common\win_process.py"
echo [INFO] win_process.py: %WIN_PROCESS_PY%

if not exist "%WIN_PROCESS_PY%" (
    echo [ERROR] win_process.py not found
    exit /b 1
)

echo.
echo ============================================
echo Test 1: Direct --cmd option
echo ============================================
set "TEST_CMD=echo DIRECT_CMD_SUCCESS"
echo [INFO] Command: %TEST_CMD%
%PYTHON_CMD% "%WIN_PROCESS_PY%" launch --cmd "%TEST_CMD%"
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 2: JOB_CMD environment variable
echo ============================================
set "JOB_CMD=echo JOB_CMD_ENV_SUCCESS"
echo [INFO] JOB_CMD=%JOB_CMD%
%PYTHON_CMD% "%WIN_PROCESS_PY%" launch
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 3: JOB_CMD with delayed expansion
echo ============================================
set "TEST_VAR=DELAYED_VAR_VALUE"
set "JOB_CMD=echo TEST_VAR=!TEST_VAR!"
echo [INFO] JOB_CMD=!JOB_CMD!
%PYTHON_CMD% "%WIN_PROCESS_PY%" launch
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 4: JOB_CMD with complex command
echo ============================================
set "JOB_CMD=set A=1&& set B=2&& echo A=%%A%% B=%%B%%"
echo [INFO] JOB_CMD=!JOB_CMD!
%PYTHON_CMD% "%WIN_PROCESS_PY%" launch
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 5: JOB_CMD via for /f subshell
echo ============================================
set "JOB_CMD=echo FOR_F_SUBSHELL_TEST"
echo [INFO] JOB_CMD=%JOB_CMD%
for /f "usebackq delims=" %%P in (`%PYTHON_CMD% "%WIN_PROCESS_PY%" launch`) do (
    echo [INFO] Result: %%P
)
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo Test 6: Simulating actual launch_job behavior
echo ============================================
set "RUN_TS=20251231"
set "BATCH_SEED=0"
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_SEED=12345"
set "SCRIPT_SELF=%~f0"
set "JOB_CMD=set RUN_TS=!RUN_TS!&& set BATCH_SEED=!BATCH_SEED!&& set RUN_ONE_T=!JOB_T!&& set RUN_ONE_EPS=!JOB_EPS!&& set RUN_ONE_TAU=!JOB_TAU!&& set RUN_ONE_SEED=!JOB_SEED!&& echo SIMULATED_JOB_LAUNCH"
echo [INFO] JOB_CMD length: 
echo !JOB_CMD! | find /c /v ""
echo [INFO] JOB_CMD=!JOB_CMD!
set "JOB_PID_TMP="
for /f "usebackq delims=" %%P in (`!PYTHON_CMD! "!WIN_PROCESS_PY!" launch`) do set "JOB_PID_TMP=%%P"
echo [INFO] JOB_PID_TMP=!JOB_PID_TMP!
echo [INFO] Exit code: %errorlevel%

echo.
echo ============================================
echo All tests completed
echo ============================================

endlocal
