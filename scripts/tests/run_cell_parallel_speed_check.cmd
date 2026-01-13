@echo off
rem Run a short cell-parallel on/off speed check on Windows.

setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"
set "RUNSETS_COMMON_DIR=%REPO_ROOT%\\scripts\\runsets\\common"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\\venv_bootstrap.cmd"
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

"%PYTHON_EXE%" scripts\\tests\\cell_parallel_speed_check.py %*
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
