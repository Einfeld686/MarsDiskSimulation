@echo off
rem Diagnostic script: test run_sweep.cmd dependencies step by step
rem Run this from the repository root: scripts\tests\diag_run_sweep.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo. run_sweep.cmd Diagnostic Tool
echo.============================================================
echo.

rem --- Step 0: Basic environment ---
echo.[Step 0] Basic Environment
echo.  Current directory: %CD%
echo.  Script location:   %~dp0
echo.

rem --- Step 1: Locate repository root ---
echo.[Step 1] Repository Root
for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.  REPO_ROOT: !REPO_ROOT!
if not exist "!REPO_ROOT!\marsdisk\__init__.py" (
    echo.  [FAIL] marsdisk package not found at !REPO_ROOT!\marsdisk
    goto :summary
)
echo.  [OK] marsdisk package found
echo.

rem --- Step 2: Check common scripts directory ---
echo.[Step 2] Common Scripts Directory
set "COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
echo.  COMMON_DIR: !COMMON_DIR!
if not exist "!COMMON_DIR!" (
    echo.  [FAIL] Common directory not found
    goto :summary
)
echo.  [OK] Common directory exists
echo.

rem --- Step 3: Check required helper scripts ---
echo.[Step 3] Required Helper Scripts
set "STEP3_OK=1"
for %%F in (resolve_python.cmd python_exec.cmd base.yml) do (
    if exist "!COMMON_DIR!\%%F" (
        echo.  [OK] %%F
    ) else (
        echo.  [FAIL] %%F not found
        set "STEP3_OK=0"
    )
)
if "!STEP3_OK!"=="0" goto :summary
echo.

rem --- Step 4: Check Windows overrides ---
echo.[Step 4] Windows Overrides
set "WIN_DIR=!REPO_ROOT!\scripts\runsets\windows"
if exist "!WIN_DIR!\overrides.txt" (
    echo.  [OK] overrides.txt exists
) else (
    echo.  [WARN] overrides.txt not found (may use defaults)
)
echo.

rem --- Step 5: Python resolution ---
echo.[Step 5] Python Resolution
echo.  Calling resolve_python.cmd...
call "!COMMON_DIR!\resolve_python.cmd"
set "STEP5_RC=!errorlevel!"
if not "!STEP5_RC!"=="0" (
    echo.  [FAIL] resolve_python.cmd failed with errorlevel=!STEP5_RC!
    goto :summary
)
echo.  [OK] resolve_python.cmd succeeded
echo.  PYTHON_EXE: !PYTHON_EXE!
echo.  PYTHON_ARGS: !PYTHON_ARGS!
echo.

rem --- Step 6: Python version check ---
echo.[Step 6] Python Version
if defined PYTHON_ARGS (
    "!PYTHON_EXE!" !PYTHON_ARGS! --version
) else (
    "!PYTHON_EXE!" --version
)
set "STEP6_RC=!errorlevel!"
if not "!STEP6_RC!"=="0" (
    echo.  [FAIL] Python version check failed
    goto :summary
)
echo.  [OK] Python is working
echo.

rem --- Step 7: python_exec.cmd test ---
echo.[Step 7] python_exec.cmd Test
set "PYTHON_EXEC_CMD=!COMMON_DIR!\python_exec.cmd"
for /f "usebackq delims=" %%V in (`call "!PYTHON_EXEC_CMD!" -c "print('hello')"`) do set "PY_OUT=%%V"
if "!PY_OUT!"=="hello" (
    echo.  [OK] python_exec.cmd works
) else (
    echo.  [FAIL] python_exec.cmd output unexpected: !PY_OUT!
    goto :summary
)
echo.

rem --- Step 8: Import marsdisk ---
echo.[Step 8] Import marsdisk Module
pushd "!REPO_ROOT!"
call "!PYTHON_EXEC_CMD!" -c "import marsdisk; print('marsdisk version:', getattr(marsdisk, '__version__', 'unknown'))"
set "STEP8_RC=!errorlevel!"
popd
if not "!STEP8_RC!"=="0" (
    echo.  [FAIL] Cannot import marsdisk
    goto :summary
)
echo.  [OK] marsdisk import succeeded
echo.

rem --- Step 9: Check config file ---
echo.[Step 9] Config File Validation
set "CONFIG_PATH=!COMMON_DIR!\base.yml"
pushd "!REPO_ROOT!"
call "!PYTHON_EXEC_CMD!" -c "import yaml; yaml.safe_load(open(r'!CONFIG_PATH!'))"
set "STEP9_RC=!errorlevel!"
popd
if not "!STEP9_RC!"=="0" (
    echo.  [FAIL] Config file invalid or cannot be parsed
    goto :summary
)
echo.  [OK] Config file is valid YAML
echo.

rem --- Step 10: Check Python helper scripts ---
echo.[Step 10] Python Helper Scripts
set "STEP10_OK=1"
for %%F in (calc_parallel_jobs.py write_sweep_list.py run_one.py) do (
    if exist "!COMMON_DIR!\%%F" (
        echo.  [OK] %%F
    ) else (
        echo.  [WARN] %%F not found
        set "STEP10_OK=0"
    )
)
echo.

rem --- Step 11: Dry run of run_sweep.cmd ---
echo.[Step 11] Dry Run Test
echo.  To test run_sweep.cmd with dry-run, execute:
echo.    scripts\runsets\windows\run_sweep.cmd --dry-run --debug
echo.

:summary
echo.
echo.============================================================
echo. Diagnostic Summary
echo.============================================================
echo.
echo.If all steps show [OK], try running:
echo.  scripts\runsets\windows\run_sweep.cmd --dry-run --debug
echo.
echo.The --debug flag will show detailed progress information.
echo.============================================================

endlocal
