@echo off
rem Run a short cell-parallel on/off speed check on Windows.

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
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\\Scripts\\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    popd
    exit /b 1
  )
)

call "%VENV_DIR%\\Scripts\\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  popd
  exit /b 1
)
set "PYTHON_EXE=%VENV_DIR%\\Scripts\\python.exe"

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

"%PYTHON_EXE%" scripts\\tests\\cell_parallel_speed_check.py %*
set "RC=%errorlevel%"

popd
exit /b %RC%
