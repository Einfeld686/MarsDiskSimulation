@echo off
rem Execute Python using resolved PYTHON_EXE/PYTHON_ARGS.
setlocal EnableExtensions DisableDelayedExpansion

if "%PYTHON_EXE%"=="" (
  echo.[error] PYTHON_EXE is not set
  exit /b 1
)

if "%PYTHON_ARGS%"=="" (
  call "%PYTHON_EXE%" %*
) else (
  call "%PYTHON_EXE%" %PYTHON_ARGS% %*
)
exit /b %errorlevel%
