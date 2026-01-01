@echo off
rem Bootstrap a local venv and resolve PYTHON_EXE for Windows cmd scripts.

setlocal EnableExtensions EnableDelayedExpansion
set "BOOTSTRAP_RC=0"

set "RUNSETS_COMMON_DIR=%~dp0"
if "%RUNSETS_COMMON_DIR%"=="" set "RUNSETS_COMMON_DIR=."
set "RESOLVE_PYTHON_CMD=%RUNSETS_COMMON_DIR%resolve_python.cmd"
if not exist "%RESOLVE_PYTHON_CMD%" (
  echo.[error] resolve_python helper not found: "%RESOLVE_PYTHON_CMD%"
  set "BOOTSTRAP_RC=1"
  goto :bootstrap_done
)

set "RESOLVE_PYTHON_SKIP_REQUIREMENTS=1"
call "%RESOLVE_PYTHON_CMD%"
if errorlevel 1 (
  set "BOOTSTRAP_RC=%errorlevel%"
  goto :bootstrap_done
)

set "PYTHON_BOOT=%PYTHON_EXE%"

if "%VENV_DIR%"=="" set "VENV_DIR=.venv"
if "%REQ_FILE%"=="" set "REQ_FILE=requirements.txt"
if "%SKIP_REQUIREMENTS%"=="" (
  if /i "%SKIP_PIP%"=="1" (
    set "SKIP_REQUIREMENTS=1"
  ) else (
    set "SKIP_REQUIREMENTS=0"
  )
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
  echo.[setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo.[error] Failed to create virtual environment.
    set "BOOTSTRAP_RC=%errorlevel%"
    goto :bootstrap_done
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo.[error] Failed to activate virtual environment.
  set "BOOTSTRAP_RC=%errorlevel%"
  goto :bootstrap_done
)

set "PYTHON_EXE=%VENV_PYTHON%"
set "PYTHON_ARGS="
set "PYTHON_CMD=%PYTHON_EXE%"

if "%SKIP_REQUIREMENTS%"=="1" (
  echo.[setup] SKIP_REQUIREMENTS=1; skipping dependency install.
  set "REQUIREMENTS_INSTALLED=0"
) else if exist "%REQ_FILE%" (
  echo.[setup] Installing/upgrading dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo.[error] Dependency install failed.
    set "BOOTSTRAP_RC=%errorlevel%"
    goto :bootstrap_done
  )
  set "REQUIREMENTS_INSTALLED=1"
) else (
  echo.[warn] %REQ_FILE% not found; skipping dependency install.
  set "REQUIREMENTS_INSTALLED=0"
)

:bootstrap_done
endlocal & (
  set "PYTHON_EXE=%PYTHON_EXE%"
  set "PYTHON_ARGS=%PYTHON_ARGS%"
  set "PYTHON_CMD=%PYTHON_CMD%"
  set "PYTHON_BOOT=%PYTHON_BOOT%"
  set "PYTHON_ALLOW_LAUNCHER=%PYTHON_ALLOW_LAUNCHER%"
  set "VENV_DIR=%VENV_DIR%"
  set "REQ_FILE=%REQ_FILE%"
  set "SKIP_REQUIREMENTS=%SKIP_REQUIREMENTS%"
  set "REQUIREMENTS_INSTALLED=%REQUIREMENTS_INSTALLED%"
)
exit /b %BOOTSTRAP_RC%
