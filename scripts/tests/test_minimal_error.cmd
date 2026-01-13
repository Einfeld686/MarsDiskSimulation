@echo off
rem Minimal test to reproduce the "invalid filename" error
rem Run each step separately and identify where error occurs

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo.Minimal Error Reproduction Test
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
set "COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
if not exist "!COMMON_DIR!\resolve_python.cmd" (
    echo.[error] resolve_python.cmd not found: "!COMMON_DIR!\resolve_python.cmd"
    exit /b 1
)
call "!COMMON_DIR!\resolve_python.cmd"
if not "!errorlevel!"=="0" exit /b 1

echo.[info] REPO_ROOT=!REPO_ROOT!
echo.[info] TEMP=!TEMP!
echo.

echo.Press a key after each step to continue...
echo.

rem ============================================================
echo.Step A: Echo to console
echo.------------------------------------------------------------
echo Hello World
echo.
pause
echo.

rem ============================================================
echo.Step B: Echo to file (simple path)
echo.------------------------------------------------------------
echo test > "%TEMP%\simple_test.tmp"
echo.[result] errorlevel=%errorlevel%
del "%TEMP%\simple_test.tmp" >nul 2>&1
pause
echo.

rem ============================================================
echo.Step C: Echo to file (path with variable)
echo.------------------------------------------------------------
set "TMP_ROOT=%TEMP%"
echo test > "!TMP_ROOT!\var_test.tmp"
echo.[result] errorlevel=%errorlevel%
del "!TMP_ROOT!\var_test.tmp" >nul 2>&1
pause
echo.

rem ============================================================
echo.Step D: Echo complex content
echo.------------------------------------------------------------
set "COMPLEX=set A=1&& set B=2&& echo done"
echo !COMPLEX!
echo.[result] errorlevel=%errorlevel%
pause
echo.

rem ============================================================
echo.Step E: Echo complex content to file
echo.------------------------------------------------------------
> "!TMP_ROOT!\complex_test.tmp" echo !COMPLEX!
echo.[result] errorlevel=%errorlevel%
if exist "!TMP_ROOT!\complex_test.tmp" (
    echo.[debug] File contents:
    type "!TMP_ROOT!\complex_test.tmp"
    del "!TMP_ROOT!\complex_test.tmp"
)
pause
echo.

rem ============================================================
echo.Step F: Python simple execution
echo.------------------------------------------------------------
!PYTHON_CMD! -c "print('Python works')"
echo.[result] errorlevel=%errorlevel%
pause
echo.

rem ============================================================
echo.Step G: Python with output to file
echo.------------------------------------------------------------
!PYTHON_CMD! -c "print('test output')" > "!TMP_ROOT!\python_out.tmp" 2>&1
echo.[result] errorlevel=%errorlevel%
if exist "!TMP_ROOT!\python_out.tmp" (
    echo.[debug] File contents:
    type "!TMP_ROOT!\python_out.tmp"
    del "!TMP_ROOT!\python_out.tmp"
)
pause
echo.

rem ============================================================
echo.Step H: win_process.py simple
echo.------------------------------------------------------------
set "WIN_PROCESS_PY=!REPO_ROOT!\scripts\runsets\common\win_process.py"
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd "echo test" --window-style hidden --cwd "!REPO_ROOT!"
echo.[result] errorlevel=%errorlevel%
pause
echo.

rem ============================================================
echo.Step I: win_process.py with output redirection
echo.------------------------------------------------------------
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd "echo test" --window-style hidden --cwd "!REPO_ROOT!" > "!TMP_ROOT!\pid_out.tmp" 2>&1
echo.[result] errorlevel=%errorlevel%
if exist "!TMP_ROOT!\pid_out.tmp" (
    echo.[debug] File contents:
    type "!TMP_ROOT!\pid_out.tmp"
    del "!TMP_ROOT!\pid_out.tmp"
)
pause
echo.

rem ============================================================
echo.Step J: Full simulation with markers
echo.------------------------------------------------------------
set "JOB_T=5000"
set "JOB_EPS=1.0"
set "JOB_TAU=1.0"
set "JOB_CMD=set FOO=bar&& echo FOO set"
set "JOB_CMD_FILE=!TMP_ROOT!\marsdisk_cmd_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"

echo MARKER_1
> "!JOB_CMD_FILE!" echo !JOB_CMD!
echo MARKER_2
echo.[debug] Command file exists: 
if exist "!JOB_CMD_FILE!" (echo YES) else (echo NO)

echo MARKER_3
!PYTHON_CMD! "!WIN_PROCESS_PY!" launch --cmd-file "!JOB_CMD_FILE!" --window-style hidden --cwd "!REPO_ROOT!" > "!TMP_ROOT!\marsdisk_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp" 2>&1
echo MARKER_4
echo.[result] errorlevel=%errorlevel%

if exist "!TMP_ROOT!\marsdisk_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp" (
    echo.[debug] PID file contents:
    type "!TMP_ROOT!\marsdisk_pid_!JOB_T!_!JOB_EPS!_!JOB_TAU!.tmp"
)

echo MARKER_5
del "!JOB_CMD_FILE!" >nul 2>&1
echo MARKER_6

pause
echo.

echo.============================================================
echo.Test complete - check which step shows the error
echo.============================================================

endlocal
