@echo off
rem Execute Python using resolved PYTHON_EXE/PYTHON_ARGS.
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHON_EXEC_RC="

if "%PYTHON_EXE%"=="" (
  echo.[error] PYTHON_EXE is not set
  set "PYTHON_EXEC_RC=1"
  goto :python_exec_done
)

if "%PYTHON_ARGS%"=="" (
  call "%PYTHON_EXE%" %*
) else (
  call "%PYTHON_EXE%" %PYTHON_ARGS% %*
)
set "PYTHON_EXEC_RC=%errorlevel%"

:python_exec_done
endlocal & exit /b %PYTHON_EXEC_RC%
