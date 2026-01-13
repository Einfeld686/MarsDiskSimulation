@echo off

rem Run a single-case output size probe on Windows.



setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"

for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"



set "VENV_DIR=.venv"

set "REQ_FILE=requirements.txt"

set "RUNSETS_COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\venv_bootstrap.cmd"
if not exist "%VENV_BOOTSTRAP_CMD%" (
  echo [error] venv_bootstrap helper not found: "%VENV_BOOTSTRAP_CMD%"
  call :popd_safe 1
  goto :eof
)
call "%VENV_BOOTSTRAP_CMD%"
set "BOOTSTRAP_RC=!errorlevel!"
if not "!BOOTSTRAP_RC!"=="0" (
  echo [error] Failed to initialize Python environment.
  call :popd_safe !BOOTSTRAP_RC!
  goto :eof
)

if not defined SIZE_BATCH_ROOT set "SIZE_BATCH_ROOT=out\size_probe"

if not defined SIZE_SWEEP_TAG set "SIZE_SWEEP_TAG=size_probe"

if not defined SIZE_T set "SIZE_T=5000"

if not defined SIZE_EPS set "SIZE_EPS=1.0"

if not defined SIZE_TAU set "SIZE_TAU=1.0"

if not defined SIZE_BATCH_SEED set "SIZE_BATCH_SEED=0"

if not defined SIZE_HOOKS set "SIZE_HOOKS=plot,eval"

if not defined SIZE_RESERVE_GB set "SIZE_RESERVE_GB=50"

if not defined SIZE_SAFETY_FRACTION set "SIZE_SAFETY_FRACTION=0.7"



set "SIZE_ARGS=--batch-root %SIZE_BATCH_ROOT% --sweep-tag %SIZE_SWEEP_TAG% --t %SIZE_T% --eps %SIZE_EPS% --tau %SIZE_TAU% --batch-seed %SIZE_BATCH_SEED% --hooks %SIZE_HOOKS% --reserve-gb %SIZE_RESERVE_GB% --safety-fraction %SIZE_SAFETY_FRACTION% --skip-pip"

if defined SIZE_TEMP_ROOT set "SIZE_ARGS=%SIZE_ARGS% --temp-root %SIZE_TEMP_ROOT%"

if defined SIZE_CONFIG set "SIZE_ARGS=%SIZE_ARGS% --config %SIZE_CONFIG%"

if defined SIZE_OVERRIDES set "SIZE_ARGS=%SIZE_ARGS% --overrides %SIZE_OVERRIDES%"

if defined SIZE_PRINT_JOBS_ONLY set "SIZE_ARGS=%SIZE_ARGS% --print-recommended-jobs --quiet"

if defined SIZE_QUIET set "SIZE_ARGS=%SIZE_ARGS% --quiet"



echo [info] measure_case_output_size.py %SIZE_ARGS%

"%PYTHON_EXE%" scripts\tests\measure_case_output_size.py %SIZE_ARGS% %*

set "RC=!errorlevel!"



call :popd_safe !RC!
goto :eof


:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%~1"
if "%MARSDISK_POPD_ERRORLEVEL%"=="" set "MARSDISK_POPD_ERRORLEVEL=!errorlevel!"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
endlocal & exit /b %MARSDISK_POPD_ERRORLEVEL%
