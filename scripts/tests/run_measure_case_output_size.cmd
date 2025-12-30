@echo off
rem Run a single-case output size probe on Windows.

setlocal EnableExtensions

if not defined PYTHON_EXE (
  for %%P in (python3.11 python py) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo [error] python3.11/python/py not found in PATH
    exit /b 1
  )
) else (
  if not exist "%PYTHON_EXE%" (
    where %PYTHON_EXE% >nul 2>&1
    if errorlevel 1 (
      echo [error] %PYTHON_EXE% not found in PATH
      exit /b 1
    )
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    popd
    exit /b 1
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  popd
  exit /b 1
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo [setup] Installing dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency install failed.
    popd
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
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
set "RC=%errorlevel%"

popd
exit /b %RC%
