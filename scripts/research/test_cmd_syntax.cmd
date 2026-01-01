@echo off
rem Syntax check and dry-run test for Windows batch files.
rem Usage: test_cmd_syntax.cmd [script.cmd ...]
rem
rem If no arguments given, tests all .cmd files in scripts/research/

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%A in ("%SCRIPT_DIR:~0,-1%") do set "PARENT1=%%~dpA"
for %%B in ("%PARENT1:~0,-1%") do set "REPO_ROOT=%%~dpB"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "COMMON_DIR=%REPO_ROOT%\scripts\runsets\common"
if not exist "%COMMON_DIR%\resolve_python.cmd" (
  echo [error] resolve_python.cmd not found: "%COMMON_DIR%\resolve_python.cmd"
  exit /b 1
)
call "%COMMON_DIR%\resolve_python.cmd"
if !errorlevel! geq 1 exit /b 1

set PASS=0
set FAIL=0
set TESTED=

if "%~1"=="" (
  echo [test] No arguments given, testing all .cmd files in scripts\research\
  for %%f in ("%REPO_ROOT%\scripts\research\*.cmd") do (
    if /i not "%%~nxf"=="test_cmd_syntax.cmd" (
      call :test_one "%%f"
    )
  )
) else (
  for %%f in (%*) do (
    call :test_one "%%f"
  )
)

echo.
echo ========================================
echo Test Summary: PASS=%PASS% FAIL=%FAIL%
echo ========================================
set "EXIT_CODE=0"
if %FAIL% gtr 0 set "EXIT_CODE=1"
goto :exit_main

:test_one
set "FILE=%~1"
echo.
echo [test] Checking: %FILE%

rem Check 1: File exists
if not exist "%FILE%" (
  echo   [FAIL] File not found
  set /a FAIL+=1
  goto :eof
)

rem Check 2: Line endings (Python)
!PYTHON_CMD! -c "import pathlib,sys; data=pathlib.Path(r'%FILE%').read_bytes(); sys.exit(0 if b'\r\n' in data else 1)" 2>nul
if !errorlevel! geq 1 (
  echo   [WARN] File may have Unix line endings (LF instead of CRLF)
)

rem Check 3: Check for common problematic patterns
findstr /r /c:"pushd.*\.\.\\\.\." "%FILE%" >nul 2>&1
if !errorlevel! lss 1 (
  echo   [WARN] Found 'pushd ..\..' pattern - may cause path issues
)

findstr /r /c:"\\NUL" "%FILE%" >nul 2>&1
if !errorlevel! lss 1 (
  echo   [WARN] Found '\NUL' pattern - deprecated on Windows 10+
)

findstr /r /c:"|| *(" "%FILE%" >nul 2>&1
if !errorlevel! lss 1 (
  echo   [WARN] Found '^|^| ^(' pattern - unreliable with call in cmd.exe
)

rem Check 4: Very long lines (>1000 chars, may cause issues)
!PYTHON_CMD! -c "import pathlib; p=pathlib.Path(r'%FILE%'); lines=p.read_text(encoding='utf-8', errors='replace').splitlines(); long=[(i+1, len(line)) for i, line in enumerate(lines) if len(line) > 1000]; print('  [WARN] Found lines over 1000 characters') if long else None; [print('    Line {}: {} chars'.format(i, length)) for i, length in long]" 2>nul

rem Check 5: Dry-run if script supports it
findstr /c:"--dry-run" "%FILE%" >nul 2>&1
if !errorlevel! lss 1 (
  echo   [info] Script supports --dry-run, attempting dry-run test...
  pushd "%REPO_ROOT%"
  set "MARSDISK_POPD_ACTIVE=1"
  cmd /c ""%FILE%" --dry-run >nul 2>&1"
  if !errorlevel! geq 1 (
    echo   [FAIL] Dry-run failed with errorlevel !errorlevel!
    set /a FAIL+=1
    call :popd_safe
    goto :eof
  ) else (
    echo   [PASS] Dry-run succeeded
  )
  call :popd_safe
) else (
  echo   [info] Script does not support --dry-run, skipping execution test
)

echo   [PASS] Basic checks passed
set /a PASS+=1
goto :eof

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=!errorlevel!"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b !MARSDISK_POPD_ERRORLEVEL!

:exit_main
endlocal & exit /b %EXIT_CODE%
