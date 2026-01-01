@echo off
rem Resolve Python executable and arguments (shared by runsets).
setlocal EnableExtensions EnableDelayedExpansion

set "DEBUG_RESOLVE=0"
if defined DEBUG if /i "%DEBUG%"=="1" set "DEBUG_RESOLVE=1"
if defined DEBUG_ARG if /i "%DEBUG_ARG%"=="1" set "DEBUG_RESOLVE=1"

if not defined PYTHON_ALLOW_LAUNCHER set "PYTHON_ALLOW_LAUNCHER=0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if "%DEBUG_RESOLVE%"=="1" echo.[DEBUG] resolve_python: start
set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE_DIR="

if not defined PYTHON_EXE (
  rem Try project-local virtual environments first
  set "VENV_DIR_HINT=!VENV_DIR!"
  if not defined VENV_DIR_HINT set "VENV_DIR_HINT=.venv"
  if exist "!VENV_DIR_HINT!\Scripts\python.exe" (
    set "PYTHON_EXE=!VENV_DIR_HINT!\Scripts\python.exe"
    if "%DEBUG_RESOLVE%"=="1" echo.[DEBUG] resolve_python: found project venv python: !PYTHON_EXE!
  )

  if not defined PYTHON_EXE (
    for %%P in (python3.13 python3.12 python3.11 python) do (
      if not defined PYTHON_EXE (
        where %%P >nul 2>&1
        if !errorlevel! lss 1 set "PYTHON_EXE=%%P"
      )
    )
  )
  if not defined PYTHON_EXE (
    where py >nul 2>&1
    if !errorlevel! lss 1 (
      py -3.11 -c "import sys" >nul 2>&1
      if !errorlevel! lss 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ALLOW_LAUNCHER=1"
        if not defined PYTHON_ARGS (
          set "PYTHON_ARGS=-3.11"
        ) else (
          set "PYTHON_ARGS_NEEDS_VER=1"
          if /i "!PYTHON_ARGS:~0,2!"=="-3" set "PYTHON_ARGS_NEEDS_VER=0"
          if /i "!PYTHON_ARGS:~0,2!"=="-2" set "PYTHON_ARGS_NEEDS_VER=0"
          if "!PYTHON_ARGS_NEEDS_VER!"=="1" set "PYTHON_ARGS=-3.11 !PYTHON_ARGS!"
        )
      )
    )
  )
  if not defined PYTHON_EXE (
    set "LOCAL_APPDATA_HINT=%LOCALAPPDATA%"
    if not defined LOCAL_APPDATA_HINT if defined USERPROFILE set "LOCAL_APPDATA_HINT=%USERPROFILE%\AppData\Local"
    for %%I in ("!LOCAL_APPDATA_HINT!\Programs\Python\Python311\python.exe" "!LOCAL_APPDATA_HINT!\Programs\Python\Python312\python.exe" "!LOCAL_APPDATA_HINT!\Programs\Python\Python313\python.exe" "%ProgramW6432%\Python311\python.exe" "%ProgramW6432%\Python312\python.exe" "%ProgramW6432%\Python313\python.exe" "%ProgramFiles%\Python311\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python313\python.exe" "%ProgramFiles(x86)%\Python311\python.exe" "%ProgramFiles(x86)%\Python312\python.exe" "%ProgramFiles(x86)%\Python313\python.exe" "C:\Python311\python.exe" "C:\Python312\python.exe" "C:\Python313\python.exe") do (
      if not defined PYTHON_EXE if exist "%%~fI" set "PYTHON_EXE=%%~fI"
    )
    if defined PYTHON_EXE (
      for %%I in ("!PYTHON_EXE!") do set "PYTHON_EXE_DIR=%%~dpI"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] python3.11 or python not found in PATH
    exit /b 1
  )
)

set "PYTHON_ARGS_SET=0"
if defined PYTHON_ARGS set "PYTHON_ARGS_SET=1"
set "PYTHON_EXE_RAW=%PYTHON_EXE%"
set "PYTHON_EXE_RAW=%PYTHON_EXE_RAW:"=%"
if "!PYTHON_EXE_RAW:~0,1!"=="-" (
  if "!PYTHON_ARGS_SET!"=="0" (
    set "PYTHON_ARGS=!PYTHON_EXE_RAW!"
    set "PYTHON_ARGS_SET=1"
  )
  set "PYTHON_EXE_RAW="
)
if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
set "PYTHON_EXE=!PYTHON_EXE_RAW!"
set "PYTHON_HAS_SPACE=0"
if not "!PYTHON_EXE_RAW: =!"=="!PYTHON_EXE_RAW!" set "PYTHON_HAS_SPACE=1"
set "PYTHON_RAW_LOOKS_PATH=0"
for %%I in ("!PYTHON_EXE_RAW!") do (
  if not "%%~pI"=="" set "PYTHON_RAW_LOOKS_PATH=1"
  if not "%%~dI"=="" set "PYTHON_RAW_LOOKS_PATH=1"
)
if "!PYTHON_HAS_SPACE!"=="1" if "!PYTHON_RAW_LOOKS_PATH!"=="0" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_EXE_RAW!") do (
    set "PYTHON_EXE=%%A"
    if "!PYTHON_ARGS_SET!"=="0" (
      set "PYTHON_ARGS=%%B"
      set "PYTHON_ARGS_SET=1"
    ) else (
      if not "%%B"=="" (
        if "!PYTHON_ARGS!"=="" (
          set "PYTHON_ARGS=%%B"
        ) else (
          set "PYTHON_ARGS=%%B !PYTHON_ARGS!"
        )
      )
    )
  )
)
if "!PYTHON_HAS_SPACE!"=="1" if "!PYTHON_RAW_LOOKS_PATH!"=="1" if "!PYTHON_ARGS_SET!"=="0" (
  echo.[warn] PYTHON_EXE looks like a path with spaces; quote it or set PYTHON_ARGS.
)

set "PYTHON_EXE_NAME="
for %%I in ("!PYTHON_EXE!") do set "PYTHON_EXE_NAME=%%~nxI"
if /i "!PYTHON_EXE!"=="py" set "PYTHON_ALLOW_LAUNCHER=1"
if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_ALLOW_LAUNCHER=1"
if /i "!PYTHON_EXE!"=="py" if not "!PYTHON_ALLOW_LAUNCHER!"=="1" set "PYTHON_EXE="
if /i "!PYTHON_EXE_NAME!"=="py.exe" if not "!PYTHON_ALLOW_LAUNCHER!"=="1" set "PYTHON_EXE="
if defined PYTHON_EXE if /i not "!PYTHON_EXE!"=="python" if /i not "!PYTHON_EXE!"=="python3.11" if /i not "!PYTHON_EXE!"=="py" if /i not "!PYTHON_EXE!"=="py.exe" (
  set "PYTHON_EXE_RAW_PATH=0"
  echo.!PYTHON_EXE! | findstr /C:"\" /C:"/" >nul 2>&1
  if !errorlevel! lss 1 set "PYTHON_EXE_RAW_PATH=1"
  for %%I in ("!PYTHON_EXE!") do (
    if not "%%~pI"=="" set "PYTHON_EXE_RAW_PATH=1"
    if not "%%~dI"=="" set "PYTHON_EXE_RAW_PATH=1"
  )
  if "!PYTHON_EXE_RAW_PATH!"=="0" (
    echo.[warn] PYTHON_EXE should be python3.11 or python or an absolute path; ignoring "!PYTHON_EXE!".
    set "PYTHON_EXE="
  )
)
if /i "!PYTHON_EXE!"=="." (
  echo.[warn] PYTHON_EXE cannot be '.'; ignoring and falling back to PATH.
  set "PYTHON_EXE="
)
if not defined PYTHON_EXE (
  for %%P in (python3.13 python3.12 python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if !errorlevel! lss 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] PYTHON_EXE is empty after normalization
    exit /b 1
  )
)

set "PYTHON_ARGS_FIRST="
set "PYTHON_ARGS_REST="
if not "!PYTHON_ARGS!"=="" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_ARGS!") do (
    set "PYTHON_ARGS_FIRST=%%A"
    set "PYTHON_ARGS_REST=%%B"
  )
)
set "PYTHON_PYVER_ARG=0"
if not "!PYTHON_ARGS_FIRST!"=="" (
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-3" set "PYTHON_PYVER_ARG=1"
  if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-2" set "PYTHON_PYVER_ARG=1"
)
if "!PYTHON_PYVER_ARG!"=="1" (
  set "PYTHON_KEEP_PYVER_ARG=0"
  if "!PYTHON_ALLOW_LAUNCHER!"=="1" (
    if /i "!PYTHON_EXE!"=="py" set "PYTHON_KEEP_PYVER_ARG=1"
    if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_KEEP_PYVER_ARG=1"
  )
  if "!PYTHON_KEEP_PYVER_ARG!"=="0" (
    if not "!PYTHON_ARGS_FIRST!"=="" echo.[warn] PYTHON_ARGS includes py launcher version flag; dropping it - use python3.11 instead.
    set "PYTHON_ARGS=!PYTHON_ARGS_REST!"
  )
)

set "PYTHON_LOOKS_PATH=0"
for %%I in ("!PYTHON_EXE!") do (
  if not "%%~pI"=="" set "PYTHON_LOOKS_PATH=1"
  if not "%%~dI"=="" set "PYTHON_LOOKS_PATH=1"
)
if "!PYTHON_LOOKS_PATH!"=="1" (
  if not exist "!PYTHON_EXE!" (
    set "PYTHON_FALLBACK="
    for %%P in (python3.11 python) do (
      if not defined PYTHON_FALLBACK (
        where %%P >nul 2>&1
        if !errorlevel! lss 1 set "PYTHON_FALLBACK=%%P"
      )
    )
    if defined PYTHON_FALLBACK (
      echo.[warn] python path missing; falling back to !PYTHON_FALLBACK!
      set "PYTHON_EXE=!PYTHON_FALLBACK!"
      if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
    ) else (
      echo.[error] resolved python executable not found: "!PYTHON_EXE!"
      exit /b 1
    )
  )
) else (
  where !PYTHON_EXE! >nul 2>&1
  if !errorlevel! geq 1 (
    set "PYTHON_FALLBACK="
    for %%P in (python3.11 python) do (
      if not defined PYTHON_FALLBACK (
        where %%P >nul 2>&1
        if !errorlevel! lss 1 set "PYTHON_FALLBACK=%%P"
      )
    )
    if defined PYTHON_FALLBACK (
      echo.[warn] !PYTHON_EXE! not found; falling back to !PYTHON_FALLBACK!
      set "PYTHON_EXE=!PYTHON_FALLBACK!"
      if "!PYTHON_ARGS_SET!"=="0" set "PYTHON_ARGS="
    ) else (
      echo.[error] !PYTHON_EXE! not found in PATH
      exit /b 1
    )
  )
)

set "PYTHON_EXE_QUOTED=!PYTHON_EXE!"
if "!PYTHON_LOOKS_PATH!"=="1" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
if not "!PYTHON_EXE: =!"=="!PYTHON_EXE!" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
if not "!PYTHON_ARGS!"=="" set "PYTHON_CMD=!PYTHON_EXE_QUOTED! !PYTHON_ARGS!"

set "PYTHON_VERSION_OK=0"
call :check_python_version

if "!PYTHON_VERSION_OK!"=="0" (
  if "%DEBUG_RESOLVE%"=="1" echo.[DEBUG] resolve_python: version check failed for !PYTHON_EXE!
  call :find_python311
  set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
  set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
  if not "!PYTHON_ARGS!"=="" set "PYTHON_CMD=!PYTHON_EXE_QUOTED! !PYTHON_ARGS!"
  call :check_python_version
)

if "!PYTHON_VERSION_OK!"=="0" (
  if "%DEBUG_RESOLVE%"=="1" (
    echo.[DEBUG] resolve_python: final PYTHON_EXE=!PYTHON_EXE!
    echo.[DEBUG] resolve_python: final PYTHON_ARGS=!PYTHON_ARGS!
  )
  echo.[error] python 3.11+ is required. Install Python 3.11 or set PYTHON_EXE.
  exit /b 1
)

set "PYTHON_EXE_ABS="
if exist "!PYTHON_EXE!" (
  for %%I in ("!PYTHON_EXE!") do set "PYTHON_EXE_ABS=%%~fI"
) else (
  for /f "delims=" %%P in ('where "!PYTHON_EXE!" 2^>nul') do (
    if not defined PYTHON_EXE_ABS set "PYTHON_EXE_ABS=%%P"
  )
)
if defined PYTHON_EXE_ABS (
  set "PYTHON_EXE=!PYTHON_EXE_ABS!"
  if not defined PYTHON_EXE_DIR for %%I in ("!PYTHON_EXE_ABS!") do set "PYTHON_EXE_DIR=%%~dpI"
)

set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
if not "!PYTHON_ARGS!"=="" set "PYTHON_CMD=!PYTHON_EXE_QUOTED! !PYTHON_ARGS!"

if "%DEBUG_RESOLVE%"=="1" echo.[DEBUG] resolve_python: PYTHON_EXE=!PYTHON_EXE!
if "%DEBUG_RESOLVE%"=="1" echo.[DEBUG] resolve_python: PYTHON_ARGS=!PYTHON_ARGS!

if /i "%REQUIREMENTS_INSTALLED%"=="1" goto :requirements_done
if /i "%RESOLVE_PYTHON_SKIP_REQUIREMENTS%"=="1" (
  set "REQUIREMENTS_INSTALLED=0"
  goto :requirements_done
)
if "%SKIP_REQUIREMENTS%"=="" (
  if /i "%SKIP_PIP%"=="1" (
    set "SKIP_REQUIREMENTS=1"
  ) else (
    set "SKIP_REQUIREMENTS=0"
  )
)
if "%SKIP_REQUIREMENTS%"=="1" (
  set "REQUIREMENTS_INSTALLED=0"
  goto :requirements_done
)
if not defined REPO_ROOT (
  for %%I in ("%SCRIPT_DIR%..\..\..") do set "REPO_ROOT=%%~fI"
)
set "REQ_FILE_RESOLVED="
if not defined REQ_FILE (
  if defined REPO_ROOT (
    set "REQ_FILE_RESOLVED=%REPO_ROOT%\requirements.txt"
  ) else (
    set "REQ_FILE_RESOLVED=requirements.txt"
  )
) else (
  set "REQ_FILE_RESOLVED=%REQ_FILE%"
  if not exist "!REQ_FILE_RESOLVED!" (
    if defined REPO_ROOT if exist "!REPO_ROOT!\!REQ_FILE!" set "REQ_FILE_RESOLVED=!REPO_ROOT!\!REQ_FILE!"
  )
)
if exist "!REQ_FILE_RESOLVED!" (
  echo.[setup] Installing dependencies from !REQ_FILE_RESOLVED! ...
  if not "!PYTHON_ARGS!"=="" (
    "!PYTHON_EXE!" !PYTHON_ARGS! -m pip install -r "!REQ_FILE_RESOLVED!"
  ) else (
    "!PYTHON_EXE!" -m pip install -r "!REQ_FILE_RESOLVED!"
  )
  if !errorlevel! neq 0 (
    echo.[error] Dependency install failed.
    exit /b 1
  )
  set "REQUIREMENTS_INSTALLED=1"
) else (
  echo.[warn] requirements file not found: !REQ_FILE_RESOLVED!
  set "REQUIREMENTS_INSTALLED=0"
)

:requirements_done
endlocal & set "PYTHON_EXE=%PYTHON_EXE%" & set "PYTHON_ARGS=%PYTHON_ARGS%" & set "PYTHON_CMD=%PYTHON_CMD%" & set "PYTHON_ALLOW_LAUNCHER=%PYTHON_ALLOW_LAUNCHER%" & set "PYTHON_EXE_DIR=%PYTHON_EXE_DIR%" & set "REQUIREMENTS_INSTALLED=%REQUIREMENTS_INSTALLED%"
if not "%PYTHON_EXE_DIR%"=="" set "PATH=%PYTHON_EXE_DIR%;%PATH%" & set "PYTHON_EXE_DIR="
exit /b 0

:check_python_version
setlocal DisableDelayedExpansion
set "CHECK_RC=1"
if "%PYTHON_EXE%"=="" goto :check_python_version_done
if "%PYTHON_ARGS%"=="" (
  "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
) else (
  "%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
)
set "CHECK_RC=%errorlevel%"
:check_python_version_done
endlocal & if %CHECK_RC% lss 1 set "PYTHON_VERSION_OK=1"
exit /b 0

:check_python_candidate
setlocal DisableDelayedExpansion
set "CAND=%~1"
set "CAND_OK=0"
if "%CAND%"=="" goto :check_python_candidate_done
if /i not "%CAND:WindowsApps\\python.exe=%"=="%CAND%" goto :check_python_candidate_done
"%CAND%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if %errorlevel% lss 1 set "CAND_OK=1"
:check_python_candidate_done
endlocal & if %CAND_OK%==1 set "PYTHON_311_FOUND=%CAND%"
exit /b 0

:find_python311
set "PYTHON_311_FOUND="
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PYTHON_311_FOUND call :check_python_candidate "%%P"
)
for /f "delims=" %%P in ('where python3.13 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
for /f "delims=" %%P in ('where python3.12 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
for /f "delims=" %%P in ('where python3.11 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
for /f "delims=" %%P in ('py -3.13 -c "import sys; print(sys.executable)" 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do (
  if not defined PYTHON_311_FOUND set "PYTHON_311_FOUND=%%P"
)
set "LOCAL_APPDATA_HINT=%LOCALAPPDATA%"
if not defined LOCAL_APPDATA_HINT if defined USERPROFILE set "LOCAL_APPDATA_HINT=%USERPROFILE%\AppData\Local"
if not defined PYTHON_311_FOUND (
  for %%I in ("%LOCAL_APPDATA_HINT%\Programs\Python\Python313\python.exe" "%LOCAL_APPDATA_HINT%\Programs\Python\Python312\python.exe" "%LOCAL_APPDATA_HINT%\Programs\Python\Python311\python.exe" "%ProgramW6432%\Python313\python.exe" "%ProgramW6432%\Python312\python.exe" "%ProgramW6432%\Python311\python.exe" "%ProgramFiles%\Python313\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python311\python.exe" "%ProgramFiles(x86)%\Python313\python.exe" "%ProgramFiles(x86)%\Python312\python.exe" "%ProgramFiles(x86)%\Python311\python.exe" "C:\Python313\python.exe" "C:\Python312\python.exe" "C:\Python311\python.exe") do (
    if not defined PYTHON_311_FOUND if exist "%%~fI" set "PYTHON_311_FOUND=%%~fI"
  )
)
if defined PYTHON_311_FOUND (
  set "PYTHON_EXE=%PYTHON_311_FOUND%"
  set "PYTHON_ARGS="
  for %%I in ("%PYTHON_EXE%") do set "PYTHON_EXE_DIR=%%~dpI"
)
exit /b 0
