@echo off
rem Sanitize or regenerate token-like environment variables (RUN_TS/SWEEP_TAG).
setlocal EnableExtensions DisableDelayedExpansion

set "TOKEN_NAME=%~1"
set "TOKEN_MODE=%~2"
set "TOKEN_FALLBACK=%~3"

if "%TOKEN_NAME%"=="" (
  echo.[error] sanitize_token: missing token name
  exit /b 1
)
if "%TOKEN_MODE%"=="" set "TOKEN_MODE=default"

set "PYTHON_EXEC=%~dp0python_exec.cmd"
if not exist "%PYTHON_EXEC%" (
  echo.[error] sanitize_token: python_exec.cmd not found: "%PYTHON_EXEC%"
  exit /b 1
)

set "SANITIZE_PY=%~dp0sanitize_token.py"
if not exist "%SANITIZE_PY%" (
  echo.[error] sanitize_token: sanitize_token.py not found: "%SANITIZE_PY%"
  exit /b 1
)

set "TIMESTAMP_PY=%~dp0timestamp.py"

for /f "usebackq delims=" %%A in (`call "%PYTHON_EXEC%" "%SANITIZE_PY%" --name "%TOKEN_NAME%" --mode "%TOKEN_MODE%" --fallback "%TOKEN_FALLBACK%" --timestamp-script "%TIMESTAMP_PY%"`) do set "TOKEN_VALUE=%%A"

if "%TOKEN_VALUE%"=="" (
  echo.[error] sanitize_token: failed to produce value for %TOKEN_NAME%
  exit /b 1
)

endlocal & set "%TOKEN_NAME%=%TOKEN_VALUE%"
exit /b 0
