@echo off
rem Execute Python using resolved PYTHON_EXE/PYTHON_ARGS.
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHON_EXEC_RC="
set "SCRIPT_DIR=%~dp0"
set "RESOLVE_PYTHON_CMD=%SCRIPT_DIR%resolve_python.cmd"

if "%PYTHON_EXE%"=="" (
  if not exist "%RESOLVE_PYTHON_CMD%" (
    echo.[error] resolve_python helper not found: "%RESOLVE_PYTHON_CMD%"
    set "PYTHON_EXEC_RC=1"
    goto :python_exec_done
  )
  if /i "%REQUIREMENTS_INSTALLED%"=="1" set "RESOLVE_PYTHON_SKIP_REQUIREMENTS=1"
  call "%RESOLVE_PYTHON_CMD%"
  if errorlevel 1 (
    set "PYTHON_EXEC_RC=%errorlevel%"
    goto :python_exec_done
  )
)
if "%PYTHON_EXE%"=="" (
  echo.[error] PYTHON_EXE is not set
  set "PYTHON_EXEC_RC=1"
  goto :python_exec_done
)

set "PY_RAW=%PYTHON_EXE:"=%"
if "%PYTHON_ARGS%"=="" (
  call "%PY_RAW%" %*
) else (
  call "%PY_RAW%" %PYTHON_ARGS% %*
)
set "PYTHON_EXEC_RC=%errorlevel%"

:python_exec_done
endlocal & exit /b %PYTHON_EXEC_RC%
