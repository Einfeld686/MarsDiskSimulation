@echo off



rem Run a temp_supply sweep (1D default).



setlocal EnableExtensions EnableDelayedExpansion
if not defined DEBUG set "DEBUG=0"

if not defined TRACE_ENABLED set "TRACE_ENABLED=0"

if not defined TRACE_DETAIL set "TRACE_DETAIL=0"

if not defined TRACE_ECHO set "TRACE_ECHO=0"

if not defined PYTHON_ALLOW_LAUNCHER set "PYTHON_ALLOW_LAUNCHER=0"








if not defined PYTHON_EXE (
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 (
      py -3.11 -c "import sys" >nul 2>&1
      if not errorlevel 1 (
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
    echo.[error] python3.11/python not found in PATH
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
  set "PYTHON_EXE_CHECK=1"
  set "PYTHON_EXE_RAW_PATH=0"
  for %%I in ("!PYTHON_EXE!") do (
    if not "%%~pI"=="" set "PYTHON_EXE_RAW_PATH=1"
    if not "%%~dI"=="" set "PYTHON_EXE_RAW_PATH=1"
  )
  if "!PYTHON_EXE_RAW_PATH!"=="0" (
    echo.[warn] PYTHON_EXE should be python/python3.11 or an absolute path; ignoring "%PYTHON_EXE%".
    set "PYTHON_EXE="
  )
)
if /i "!PYTHON_EXE!"=="." (
  echo.[warn] PYTHON_EXE cannot be '.'; ignoring and falling back to PATH.
  set "PYTHON_EXE="
)
if not defined PYTHON_EXE (
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
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
if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-3" set "PYTHON_PYVER_ARG=1"
if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-2" set "PYTHON_PYVER_ARG=1"
if "!PYTHON_PYVER_ARG!"=="1" (
  set "PYTHON_KEEP_PYVER_ARG=0"
  if "!PYTHON_ALLOW_LAUNCHER!"=="1" (
    if /i "!PYTHON_EXE!"=="py" set "PYTHON_KEEP_PYVER_ARG=1"
    if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_KEEP_PYVER_ARG=1"
  )
  if "!PYTHON_KEEP_PYVER_ARG!"=="0" (
    if not "!PYTHON_ARGS_FIRST!"=="" echo.[warn] PYTHON_ARGS includes py launcher version flag; dropping it (use python3.11 instead).
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
        if not errorlevel 1 set "PYTHON_FALLBACK=%%P"
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
  if errorlevel 1 (
    set "PYTHON_FALLBACK="
    for %%P in (python3.11 python) do (
      if not defined PYTHON_FALLBACK (
        where %%P >nul 2>&1
        if not errorlevel 1 set "PYTHON_FALLBACK=%%P"
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
set "PYTHON_ARGS_FIRST="
set "PYTHON_ARGS_REST="
if not "!PYTHON_ARGS!"=="" (
  for /f "tokens=1* delims= " %%A in ("!PYTHON_ARGS!") do (
    set "PYTHON_ARGS_FIRST=%%A"
    set "PYTHON_ARGS_REST=%%B"
  )
)
set "PYTHON_PYVER_ARG=0"
if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-3" set "PYTHON_PYVER_ARG=1"
if /i "!PYTHON_ARGS_FIRST:~0,2!"=="-2" set "PYTHON_PYVER_ARG=1"
if "!PYTHON_PYVER_ARG!"=="1" (
  set "PYTHON_KEEP_PYVER_ARG=0"
  if "!PYTHON_ALLOW_LAUNCHER!"=="1" (
    if /i "!PYTHON_EXE!"=="py" set "PYTHON_KEEP_PYVER_ARG=1"
    if /i "!PYTHON_EXE_NAME!"=="py.exe" set "PYTHON_KEEP_PYVER_ARG=1"
  )
  if "!PYTHON_KEEP_PYVER_ARG!"=="0" (
    if not "!PYTHON_ARGS_FIRST!"=="" echo.[warn] PYTHON_ARGS includes py launcher version flag; dropping it (use python3.11 instead).
    set "PYTHON_ARGS=!PYTHON_ARGS_REST!"
  )
)
set "PYTHON_EXE_QUOTED=!PYTHON_EXE!"
if not "!PYTHON_EXE: =!"=="!PYTHON_EXE!" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
if not "!PYTHON_ARGS!"=="" set "PYTHON_CMD=!PYTHON_EXE_QUOTED! !PYTHON_ARGS!"
set "PYTHON_CMD_SANITY=1"
if not defined PYTHON_EXE set "PYTHON_CMD_SANITY=0"
if "!PYTHON_EXE:~0,1!"=="-" set "PYTHON_CMD_SANITY=0"
if "!PYTHON_CMD:~0,1!"=="-" set "PYTHON_CMD_SANITY=0"
if "!PYTHON_CMD:~0,1!"=="." set "PYTHON_CMD_SANITY=0"
if "!PYTHON_CMD_SANITY!"=="0" (
  echo.[warn] python command invalid; resetting to python in PATH
  set "PYTHON_EXE="
  set "PYTHON_ARGS="
  for %%P in (python3.11 python) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo.[error] python3.11/python not found in PATH
    exit /b 1
  )
  set "PYTHON_EXE_QUOTED=!PYTHON_EXE!"
  if not "!PYTHON_EXE: =!"=="!PYTHON_EXE!" set "PYTHON_EXE_QUOTED="!PYTHON_EXE!""
  set "PYTHON_CMD=!PYTHON_EXE_QUOTED!"
)
set "PYTHON_VERSION_OK=0"
!PYTHON_CMD! -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_VERSION_OK=1"

if "!PYTHON_VERSION_OK!"=="0" (
  rem py launcher fallback disabled.
)

if "!PYTHON_VERSION_OK!"=="0" (
  if defined CI (
    echo.[error] python 3.11+ is required in CI
  ) else (
    echo.[error] python 3.11+ is required. Install Python 3.11 or set PYTHON_EXE.
    echo.[error] Example: set PYTHON_EXE=python3.11
  )
  exit /b 1
)
for %%I in ("%~f0") do set "SCRIPT_DIR=%%~dpI"


set "REPO_ROOT=%SCRIPT_DIR%..\\..\\.."



for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"



set "CONFIG_PATH=%REPO_ROOT%\\scripts\\runsets\\common\\base.yml"



set "OVERRIDES_PATH=%REPO_ROOT%\\scripts\\runsets\\windows\\overrides.txt"



set "STUDY_PATH="



set "OUT_ROOT="



set "GEOMETRY_MODE=1D"



set "DRY_RUN=0"



set "NO_PLOT=0"



set "NO_EVAL=0"



set "PREFLIGHT_ONLY=0"


set "PREFLIGHT_STRICT=0"



if not defined QUIET_MODE set "QUIET_MODE=1"







:parse_args



if "%~1"=="" goto :args_done



if /i "%~1"=="--study" (



  set "STUDY_PATH=%~2"



  shift



  shift



  goto :parse_args



)



if /i "%~1"=="--config" (



  set "CONFIG_PATH=%~2"



  shift



  shift



  goto :parse_args



)



if /i "%~1"=="--overrides" (



  set "OVERRIDES_PATH=%~2"



  shift



  shift



  goto :parse_args



)



if /i "%~1"=="--out-root" (



  set "OUT_ROOT=%~2"



  shift



  shift



  goto :parse_args



)



if /i "%~1"=="--dry-run" (



  set "DRY_RUN=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--no-plot" (



  set "NO_PLOT=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--no-eval" (



  set "NO_EVAL=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--no-preflight" (

  echo.[error] preflight checks are mandatory; remove --no-preflight

  exit /b 1

)


if /i "%~1"=="--quiet" (



  set "QUIET_MODE=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--no-quiet" (



  set "QUIET_MODE=0"



  shift



  goto :parse_args



)



if /i "%~1"=="--preflight-only" (



  set "PREFLIGHT_ONLY=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--preflight-strict" (



  set "PREFLIGHT_STRICT=1"



  shift



  goto :parse_args



)



if /i "%~1"=="--debug" (



  set "DEBUG=1"



  set "TRACE_ENABLED=1"
  set "TRACE_DETAIL=1"




  set "QUIET_MODE=0"



  shift



  goto :parse_args



)



if /i "%~1"=="--help" goto :usage



if /i "%~1"=="-h" goto :usage







echo.[error] Unknown option: %~1



:usage



echo Usage: run_sweep.cmd [--study ^<path^>] [--config ^<path^>] [--overrides ^<path^>]



echo.           [--out-root ^<path^>] [--dry-run] [--no-plot] [--no-eval] [--quiet] [--no-quiet] [--preflight-only] [--preflight-strict] [--debug]


exit /b 1







:args_done







if "%QUIET_MODE%"=="1" (

  set "LOG_INFO=rem"

  set "LOG_SETUP=rem"

  set "LOG_SYS=rem"

  set "LOG_CONFIG=rem"

  set "LOG_RUN=rem"

) else (

  set "LOG_INFO=echo.[info]"

  set "LOG_SETUP=echo.[setup]"

  set "LOG_SYS=echo.[sys]"

  set "LOG_CONFIG=echo.[config]"

  set "LOG_RUN=echo.[run]"

)



if not defined AUTO_OUT_ROOT set "AUTO_OUT_ROOT=1"
if not defined INTERNAL_OUT_ROOT (
  set "INTERNAL_OUT_ROOT=out"
  set "REPO_DRIVE="
  if "!REPO_ROOT:~1,1!"==":" set "REPO_DRIVE=!REPO_ROOT:~0,2!"
  set "SYSTEM_DRIVE=%SystemDrive%"
  if not "!REPO_DRIVE!"=="" if not "%SYSTEM_DRIVE%"=="" (
    if /i not "!REPO_DRIVE!"=="%SYSTEM_DRIVE%" (
      if defined LOCALAPPDATA (
        set "INTERNAL_OUT_ROOT=%LOCALAPPDATA%\\marsdisk_out"
      ) else if defined USERPROFILE (
        set "INTERNAL_OUT_ROOT=%USERPROFILE%\\marsdisk_out"
      ) else (
        set "INTERNAL_OUT_ROOT=%SYSTEM_DRIVE%\\marsdisk_out"
      )
    )
  )
)
if not defined EXTERNAL_OUT_ROOT set "EXTERNAL_OUT_ROOT=F:\marsdisk_out"
if not defined MIN_INTERNAL_FREE_GB set "MIN_INTERNAL_FREE_GB=100"
for /f "tokens=1 delims=." %%Z in ("!MIN_INTERNAL_FREE_GB!") do set "MIN_INTERNAL_FREE_GB=%%Z"
if "!MIN_INTERNAL_FREE_GB!"=="" set "MIN_INTERNAL_FREE_GB=100"
set "MIN_INTERNAL_FREE_GB_OK=1"
for /f "delims=0123456789" %%A in ("!MIN_INTERNAL_FREE_GB!") do set "MIN_INTERNAL_FREE_GB_OK=0"
if "!MIN_INTERNAL_FREE_GB_OK!"=="0" set "MIN_INTERNAL_FREE_GB=100"


if not defined OUT_ROOT if "%AUTO_OUT_ROOT%"=="1" (
  set "OUT_ROOT=%INTERNAL_OUT_ROOT%"
  call :ensure_abs OUT_ROOT
  if not exist "!OUT_ROOT!" mkdir "!OUT_ROOT!" >nul 2>&1
  set "CHECK_PATH="
  if "!OUT_ROOT:~1,1!"==":" set "CHECK_PATH=!OUT_ROOT:~0,3!"
  if not defined CHECK_PATH if "!OUT_ROOT:~0,2!"=="\\\\" set "CHECK_PATH=!OUT_ROOT!"
  set "FREE_GB="
  for /f "usebackq delims=" %%F in (`!PYTHON_CMD! -c "import os,shutil; p=os.environ.get('CHECK_PATH',''); print(shutil.disk_usage(p).free//(1024**3) if p and os.path.exists(p) else '')"`) do set "FREE_GB=%%F"
  set "FREE_GB_RAW=!FREE_GB!"

  set "FREE_GB_OK=1"
  if "!FREE_GB!"=="" set "FREE_GB_OK=0"

  if "!FREE_GB_OK!"=="1" for /f "delims=0123456789" %%A in ("!FREE_GB!") do set "FREE_GB_OK=0"

  if "!FREE_GB_OK!"=="1" (
    if !FREE_GB! LSS %MIN_INTERNAL_FREE_GB% (
      set "OUT_ROOT=%EXTERNAL_OUT_ROOT%"
      call :ensure_abs OUT_ROOT
      set "OUT_ROOT_SOURCE=external"
    ) else (
      set "OUT_ROOT_SOURCE=internal"
    )
  ) else (
    if defined FREE_GB_RAW echo.[warn] auto-out-root free space check failed: "!FREE_GB_RAW!"

    set "OUT_ROOT_SOURCE=internal"
  )
  %LOG_SYS% out_root auto: source=!OUT_ROOT_SOURCE! free_gb=!FREE_GB! min_gb=%MIN_INTERNAL_FREE_GB% out_root="!OUT_ROOT!"
)

call :ensure_abs CONFIG_PATH
call :ensure_abs OVERRIDES_PATH
if defined STUDY_PATH call :ensure_abs STUDY_PATH
if defined OUT_ROOT call :ensure_abs OUT_ROOT
if defined OUT_ROOT call :ensure_dir OUT_ROOT
if errorlevel 1 exit /b 1

if not exist "%OVERRIDES_PATH%" (
  echo.[error] overrides file not found: "%OVERRIDES_PATH%"
  exit /b 1
)

rem If archive dir is missing/unavailable, fall back to OUT_ROOT\archive.
set "OVERRIDES_PATH_EFFECTIVE=%OVERRIDES_PATH%"
set "ARCHIVE_DIR_CFG="
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /v /r "^[ ]*#" "%OVERRIDES_PATH%"`) do (
  if /i "%%A"=="io.archive.dir" set "ARCHIVE_DIR_CFG=%%B"
)
set "ARCHIVE_DIR_OK=1"
if not defined ARCHIVE_DIR_CFG set "ARCHIVE_DIR_OK=0"
if defined ARCHIVE_DIR_CFG (
  if "!ARCHIVE_DIR_CFG:~1,1!"==":" (
    set "ARCHIVE_DRIVE=!ARCHIVE_DIR_CFG:~0,2!"
    if not exist "!ARCHIVE_DRIVE!\\" set "ARCHIVE_DIR_OK=0"
  ) else if "!ARCHIVE_DIR_CFG:~0,2!"=="\\\\" (
    if not exist "!ARCHIVE_DIR_CFG!" set "ARCHIVE_DIR_OK=0"
  )
)
if "%ARCHIVE_DIR_OK%"=="0" (
  set "OVERRIDES_TMP_DIR=%REPO_ROOT%\\tmp"
  if not exist "!OVERRIDES_TMP_DIR!" mkdir "!OVERRIDES_TMP_DIR!" >nul 2>&1
  set "OVERRIDES_PATH_EFFECTIVE=!OVERRIDES_TMP_DIR!\\marsdisk_overrides_effective_%RANDOM%.txt"
  copy /y "!OVERRIDES_PATH!" "!OVERRIDES_PATH_EFFECTIVE!" >nul 2>&1
  if errorlevel 1 (
    echo.[error] failed to prepare overrides: "!OVERRIDES_PATH_EFFECTIVE!"
    exit /b 1
  )
  >>"!OVERRIDES_PATH_EFFECTIVE!" echo io.archive.dir=!OUT_ROOT!\\archive
  set "OVERRIDES_PATH=!OVERRIDES_PATH_EFFECTIVE!"
)


%LOG_INFO% run_sweep start

%LOG_INFO% config="%CONFIG_PATH%" overrides="%OVERRIDES_PATH%" study="%STUDY_PATH%" out_root="%OUT_ROOT%"





if not defined HOOKS_ENABLE set "HOOKS_ENABLE=plot,eval,archive"



if not defined HOOKS_STRICT set "HOOKS_STRICT=0"



if not defined PLOT_ENABLE set "PLOT_ENABLE=1"







set "HOOKS_RAW=%HOOKS_ENABLE%"



if not defined HOOKS_RAW set "HOOKS_RAW=plot,eval"



set "HOOKS_ENABLE="



for %%H in (%HOOKS_RAW:,= %) do (



  set "HOOK=%%H"



  set "SKIP="



  if /i "!HOOK!"=="plot" if "%NO_PLOT%"=="1" set "SKIP=1"



  if /i "!HOOK!"=="eval" if "%NO_EVAL%"=="1" set "SKIP=1"



  if not defined SKIP (


    if defined HOOKS_ENABLE (



      set "HOOKS_ENABLE=!HOOKS_ENABLE!,!HOOK!"



    ) else (



      set "HOOKS_ENABLE=!HOOK!"



    )



  )



)







set "USE_PLOT_HOOK=0"



for %%H in (%HOOKS_ENABLE:,= %) do (



  if /i "%%H"=="plot" set "USE_PLOT_HOOK=1"



)



if "%NO_PLOT%"=="1" set "PLOT_ENABLE=0"



if "%USE_PLOT_HOOK%"=="1" set "PLOT_ENABLE=0"







set "BASE_CONFIG=%CONFIG_PATH%"



set "EXTRA_OVERRIDES_FILE=%OVERRIDES_PATH%"



if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"



set "GEOMETRY_MODE=%GEOMETRY_MODE%"



if not defined GEOMETRY_NR set "GEOMETRY_NR=32"



if not defined SHIELDING_MODE set "SHIELDING_MODE=off"



if not defined SUPPLY_MU_REFERENCE_TAU set "SUPPLY_MU_REFERENCE_TAU=1.0"



if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"



if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=off"



if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=direct"



if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=off"



if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=hard"



rem Temperature stop is the default (COOL_TO_K=1000) unless overridden.



if not defined COOL_TO_K set "COOL_TO_K=1000"



rem To force a fixed horizon, set COOL_TO_K=none and T_END_YEARS explicitly.

rem Fixed parallel settings for 24 logical processors (12 cores), ~80% target.
set "AUTO_JOBS=0"
set "PARALLEL_JOBS=10"
set "PARALLEL_JOBS_DEFAULT=0"
set "SWEEP_PARALLEL=1"
set "SWEEP_PARALLEL_DEFAULT=0"


if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"



if not defined PARALLEL_MODE set "PARALLEL_MODE=cell"

rem Sweep-parallel primary: keep cell-parallel off to avoid nested parallelism.
if "%SWEEP_PARALLEL%"=="1" (
  set "MARSDISK_CELL_PARALLEL=0"
  set "MARSDISK_CELL_JOBS=1"
) else (
  set "MARSDISK_CELL_PARALLEL=1"
  set "MARSDISK_CELL_JOBS=auto"
)



if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"



if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"



if not defined CELL_MEM_FRACTION set "CELL_MEM_FRACTION=0.8"



set "CELL_CPU_FRACTION=0.8"



if not defined CPU_UTIL_TARGET_PERCENT set "CPU_UTIL_TARGET_PERCENT=80"

if not defined CPU_UTIL_TARGET_MAX_PERCENT set "CPU_UTIL_TARGET_MAX_PERCENT=90"

if not defined CPU_UTIL_RESPECT_MEM set "CPU_UTIL_RESPECT_MEM=1"

rem Normalize CPU target and keep auto-parallel defaults when CPU target is active.
set "CPU_TARGET_OK=1"
for /f "delims=0123456789" %%A in ("%CPU_UTIL_TARGET_PERCENT%") do set "CPU_TARGET_OK=0"
if "%CPU_TARGET_OK%"=="0" set "CPU_UTIL_TARGET_PERCENT=80"
if not "%CPU_UTIL_TARGET_PERCENT%"=="0" (
  if "%PARALLEL_JOBS%"=="1" set "PARALLEL_JOBS_DEFAULT=1"
  if "%SWEEP_PARALLEL%"=="0" set "SWEEP_PARALLEL_DEFAULT=1"
)


if not defined SIZE_PROBE_ENABLE set "SIZE_PROBE_ENABLE=1"


if not defined SIZE_PROBE_RESERVE_GB set "SIZE_PROBE_RESERVE_GB=50"



if not defined SIZE_PROBE_FRACTION set "SIZE_PROBE_FRACTION=0.7"



if not defined SIZE_PROBE_T set "SIZE_PROBE_T=5000"



if not defined SIZE_PROBE_EPS set "SIZE_PROBE_EPS=1.0"



if not defined SIZE_PROBE_TAU set "SIZE_PROBE_TAU=1.0"



if not defined SIZE_PROBE_SEED set "SIZE_PROBE_SEED=0"



if not defined SIZE_PROBE_HOOKS set "SIZE_PROBE_HOOKS=plot,eval"



rem Per-process thread cap (sweep-parallel uses 1, cell-parallel uses 2).
if "%SWEEP_PARALLEL%"=="1" (
  set "CELL_THREAD_LIMIT=1"
  set "CELL_THREAD_LIMIT_DEFAULT=1"
) else (
  set "CELL_THREAD_LIMIT=2"
  set "CELL_THREAD_LIMIT_DEFAULT=0"
)

if /i "%PARALLEL_MODE%"=="cell" (

  if not defined CELL_THREAD_LIMIT (
    set "CELL_THREAD_LIMIT=1"
    if not defined CELL_THREAD_LIMIT_DEFAULT set "CELL_THREAD_LIMIT_DEFAULT=1"
  ) else (
    if not defined CELL_THREAD_LIMIT_DEFAULT set "CELL_THREAD_LIMIT_DEFAULT=0"
  )

  if not defined NUMBA_NUM_THREADS set "NUMBA_NUM_THREADS=%CELL_THREAD_LIMIT%"

  if not defined OMP_NUM_THREADS set "OMP_NUM_THREADS=%CELL_THREAD_LIMIT%"


  if not defined MKL_NUM_THREADS set "MKL_NUM_THREADS=%CELL_THREAD_LIMIT%"



  if not defined OPENBLAS_NUM_THREADS set "OPENBLAS_NUM_THREADS=%CELL_THREAD_LIMIT%"



  if not defined NUMEXPR_NUM_THREADS set "NUMEXPR_NUM_THREADS=%CELL_THREAD_LIMIT%"



  if not defined VECLIB_MAXIMUM_THREADS set "VECLIB_MAXIMUM_THREADS=%CELL_THREAD_LIMIT%"



)



if /i "%PARALLEL_MODE%"=="numba" (



  set "MARSDISK_CELL_PARALLEL=0"



  set "MARSDISK_CELL_JOBS=1"



)







if defined STUDY_PATH set "STUDY_FILE=%STUDY_PATH%"



if defined OUT_ROOT (



  set "BATCH_ROOT=%OUT_ROOT%"



) else (



  set "BATCH_ROOT=out"



)



rem Staging outputs stay on the internal disk; external archive is handled via io.archive.*



if "%DEBUG%"=="1" %LOG_INFO% batch_root="%BATCH_ROOT%"
if "%DEBUG%"=="1" (

  if not defined DEBUG_RUN_ID set "DEBUG_RUN_ID=!RANDOM!!RANDOM!"

  if not defined DEBUG_LOG_DIR set "DEBUG_LOG_DIR=!BATCH_ROOT!\debug"

  if not exist "!DEBUG_LOG_DIR!" mkdir "!DEBUG_LOG_DIR!" >nul 2>&1

  if not exist "!DEBUG_LOG_DIR!" set "DEBUG_LOG_DIR=!BATCH_ROOT!"

  if not defined DEBUG_LOG_FILE set "DEBUG_LOG_FILE=!DEBUG_LOG_DIR!\run_sweep_debug_!DEBUG_RUN_ID!.log"

  if not defined TRACE_LOG set "TRACE_LOG=!DEBUG_LOG_DIR!\run_sweep_trace_!DEBUG_RUN_ID!.log"

  >"!DEBUG_LOG_FILE!" echo [debug] run_sweep debug log

  %LOG_INFO% debug log="!DEBUG_LOG_FILE!"

  call :debug_log "debug_log=!DEBUG_LOG_FILE!"

  call :debug_log "trace_log=!TRACE_LOG!"

  call :debug_log "repo_root=!REPO_ROOT!"

  call :debug_log "config_path=!CONFIG_PATH!"

  call :debug_log "overrides_path=!OVERRIDES_PATH!"

  if defined OVERRIDES_PATH_EFFECTIVE call :debug_log "overrides_effective=!OVERRIDES_PATH_EFFECTIVE!"

  call :debug_log "study_path=!STUDY_PATH!"

  call :debug_log "out_root=!OUT_ROOT!"

  call :debug_log "batch_root=!BATCH_ROOT!"

  call :debug_log "python_exe=!PYTHON_EXE!"

  call :debug_log "python_args=!PYTHON_ARGS!"

  call :debug_log "python_cmd=!PYTHON_CMD!"

  call :debug_log "ci=!CI!"

  call :debug_log "dry_run=!DRY_RUN! no_plot=!NO_PLOT! no_eval=!NO_EVAL!"

  call :debug_log "trace_enabled=!TRACE_ENABLED! trace_detail=!TRACE_DETAIL! trace_echo=!TRACE_ECHO!"

  call :debug_log "parallel_mode=!PARALLEL_MODE! sweep_parallel=!SWEEP_PARALLEL! parallel_jobs=!PARALLEL_JOBS!"

  call :debug_log "cell_parallel=!MARSDISK_CELL_PARALLEL! cell_jobs=!MARSDISK_CELL_JOBS! cell_thread_limit=!CELL_THREAD_LIMIT!"

  call :debug_log "numba_threads=!NUMBA_NUM_THREADS! omp_threads=!OMP_NUM_THREADS!"

)








%LOG_INFO% preflight checks

set "PREFLIGHT_STRICT_FLAG="

if "%PREFLIGHT_STRICT%"=="1" set "PREFLIGHT_STRICT_FLAG=--strict"
if "%DEBUG%"=="1" call :debug_log "preflight: strict=!PREFLIGHT_STRICT! flag=!PREFLIGHT_STRICT_FLAG!"

if "%DEBUG%"=="1" call :debug_log "preflight: config=!CONFIG_PATH! overrides=!OVERRIDES_PATH! out_root=!OUT_ROOT!"

if "%DEBUG%"=="1" call :debug_log "preflight: python=!PYTHON_CMD!"


if defined CI (
  !PYTHON_CMD! "%REPO_ROOT%\\scripts\\runsets\\windows\\preflight_checks.py" --repo-root "%REPO_ROOT%" --config "%CONFIG_PATH%" --overrides "%OVERRIDES_PATH%" --out-root "%OUT_ROOT%" --python-exe "!PYTHON_EXE!" --require-git --cmd "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" --cmd-root "%REPO_ROOT%\\scripts\\runsets\\windows" --cmd-exclude "%REPO_ROOT%\\scripts\\runsets\\windows\\legacy" --cmd-allowlist "%REPO_ROOT%\\scripts\\runsets\\windows\\preflight_allowlist.txt" --allow-non-ascii --profile ci --format json %PREFLIGHT_STRICT_FLAG%
) else (
  !PYTHON_CMD! "%REPO_ROOT%\\scripts\\runsets\\windows\\preflight_checks.py" --repo-root "%REPO_ROOT%" --config "%CONFIG_PATH%" --overrides "%OVERRIDES_PATH%" --out-root "%OUT_ROOT%" --python-exe "!PYTHON_EXE!" --require-git --cmd "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" --cmd-root "%REPO_ROOT%\\scripts\\runsets\\windows" --cmd-exclude "%REPO_ROOT%\\scripts\\runsets\\windows\\legacy" --allow-non-ascii %PREFLIGHT_STRICT_FLAG%
)

set "PREFLIGHT_RC=!errorlevel!"

if "%DEBUG%"=="1" call :debug_log "preflight: rc=!PREFLIGHT_RC!"

if not "%PREFLIGHT_RC%"=="0" (

  if "%DEBUG%"=="1" if defined DEBUG_LOG_FILE echo.[error] preflight failed (rc=!PREFLIGHT_RC!) -> "!DEBUG_LOG_FILE!"

  echo.[error] preflight failed

  exit /b 1

)

if "%DEBUG%"=="1" call :debug_log "preflight: ok"



if "%PREFLIGHT_ONLY%"=="1" (



  %LOG_INFO% preflight-only requested; exiting.



  exit /b 0



)







rem Validate archive defaults in the overrides file to match the archive plan.



rem NOTE: PowerShell inlined parsing can break under cmd.exe redirection (">") and JP paths,



rem so we always parse overrides via Python and emit a temp .cmd to avoid that class of errors.



set "ARCHIVE_ENABLED_EXPECTED="



set "ARCHIVE_DIR_EXPECTED="



set "ARCHIVE_MERGE_TARGET="



set "ARCHIVE_VERIFY_LEVEL="



set "ARCHIVE_KEEP_LOCAL="



if not exist "%OVERRIDES_PATH%" (



  echo.[error] overrides file not found: "%OVERRIDES_PATH%"



  exit /b 1



)



%LOG_INFO% parsing overrides file



set "ARCHIVE_TMP=%TEMP%"



if "%ARCHIVE_TMP%"=="" set "ARCHIVE_TMP=%REPO_ROOT%\\tmp"



if not exist "%ARCHIVE_TMP%" mkdir "%ARCHIVE_TMP%" >nul 2>&1



set "ARCHIVE_SET=%ARCHIVE_TMP%\\marsdisk_archive_overrides_%RANDOM%.cmd"
if "%DEBUG%"=="1" call :debug_log "archive_parse_cmd=!ARCHIVE_SET!"




!PYTHON_CMD! "%REPO_ROOT%\\scripts\\runsets\\common\\read_overrides_cmd.py" --file "%OVERRIDES_PATH%" --out "%ARCHIVE_SET%"



if errorlevel 1 (



  echo.[error] failed to parse overrides: "%OVERRIDES_PATH%"



  exit /b 1



)



if not exist "%ARCHIVE_SET%" (



  echo.[error] overrides parse output missing: "%ARCHIVE_SET%"



  exit /b 1



)



call "%ARCHIVE_SET%"



del "%ARCHIVE_SET%"



%LOG_INFO% overrides parsed



%LOG_INFO% archive checks start



if "%DEBUG%"=="1" %LOG_INFO% archive expected: enabled="!ARCHIVE_ENABLED_EXPECTED!" dir="!ARCHIVE_DIR_EXPECTED!" merge="!ARCHIVE_MERGE_TARGET!" verify="!ARCHIVE_VERIFY_LEVEL!" keep="!ARCHIVE_KEEP_LOCAL!"
if "%DEBUG%"=="1" call :debug_log "archive_expected: enabled=!ARCHIVE_ENABLED_EXPECTED! dir=!ARCHIVE_DIR_EXPECTED! merge=!ARCHIVE_MERGE_TARGET! verify=!ARCHIVE_VERIFY_LEVEL! keep=!ARCHIVE_KEEP_LOCAL!"




if /i not "%ARCHIVE_ENABLED_EXPECTED%"=="true" goto :archive_fail_enabled



if "%DEBUG%"=="1" %LOG_INFO% archive check enabled ok



if not defined ARCHIVE_DIR_EXPECTED goto :archive_fail_dir



if "%DEBUG%"=="1" %LOG_INFO% archive check dir ok



if /i not "%ARCHIVE_MERGE_TARGET%"=="external" goto :archive_fail_merge



if "%DEBUG%"=="1" %LOG_INFO% archive check merge_target ok



if /i not "%ARCHIVE_VERIFY_LEVEL%"=="standard_plus" goto :archive_fail_verify



if "%DEBUG%"=="1" %LOG_INFO% archive check verify_level ok



if /i not "%ARCHIVE_KEEP_LOCAL%"=="metadata" goto :archive_fail_keep



if "%DEBUG%"=="1" %LOG_INFO% archive check keep_local ok



if /i "%BATCH_ROOT%"=="%ARCHIVE_DIR_EXPECTED%" goto :archive_fail_batch_root



%LOG_INFO% overrides validated



%LOG_INFO% preflight ok; preparing temp_root







set "RUN_TS_SOURCE=pre"



if defined RUN_TS (



  set "RUN_TS=!RUN_TS::=!"



  set "RUN_TS=!RUN_TS: =_!"



  set "RUN_TS=!RUN_TS:/=-!"



  set "RUN_TS=!RUN_TS:\=-!"

  set "RUN_TS=!RUN_TS:&=_!"
  set "RUN_TS=!RUN_TS:|=_!"
  set "RUN_TS=!RUN_TS:<=_!"
  set "RUN_TS=!RUN_TS:>=_!"
  set "RUN_TS=!RUN_TS:?=_!"
  set "RUN_TS=!RUN_TS:*=_!"
  set "RUN_TS=!RUN_TS:!=_!"


)



set "TEMP_ROOT=%TEMP%"



set "TEMP_SOURCE=TEMP"



%LOG_INFO% temp_root candidate="%TEMP_ROOT%"



if "%TEMP_ROOT%"=="" (



  set "TEMP_ROOT=%REPO_ROOT%\\tmp"



  set "TEMP_SOURCE=fallback"



)



if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%" >nul 2>&1



if not exist "%TEMP_ROOT%" (



  set "TEMP_ROOT=%REPO_ROOT%\\tmp"



  set "TEMP_SOURCE=fallback"



  if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%" >nul 2>&1



)



if not exist "%TEMP_ROOT%" (



  echo.[error] temp_root unavailable: "%TEMP_ROOT%"



  exit /b 1



)



set "TEMP=%TEMP_ROOT%"



%LOG_SETUP% repo_root=%REPO_ROOT%



%LOG_SETUP% temp_root=%TEMP_ROOT% (source=%TEMP_SOURCE%)
if "%DEBUG%"=="1" call :debug_log "temp_root=%TEMP_ROOT% source=%TEMP_SOURCE%"




if not exist "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd" (



  echo.[error] run_temp_supply_sweep.cmd not found: "%REPO_ROOT%\\scripts\\research\\run_temp_supply_sweep.cmd"



  exit /b 1



)



pushd "%REPO_ROOT%" >nul
set "MARSDISK_POPD_ACTIVE=1"







if "%DRY_RUN%"=="1" (



  %LOG_INFO% dry-run: calling run_temp_supply_sweep.cmd



  call scripts\research\run_temp_supply_sweep.cmd --dry-run



  call :popd_safe



  exit /b %errorlevel%



)







if "%SWEEP_PARALLEL%"=="1" if not "%SIZE_PROBE_ENABLE%"=="0" if "%PARALLEL_JOBS_DEFAULT%"=="1" (


  %LOG_INFO% size-probe: estimating per-case output for parallel job sizing



  set "SIZE_PROBE_BATCH_ROOT=%BATCH_ROOT%\\size_probe"



  set "SIZE_PROBE_JOBS="



  for /f "usebackq delims=" %%J in (`!PYTHON_CMD! scripts\\tests\\measure_case_output_size.py --batch-root "!SIZE_PROBE_BATCH_ROOT!" --sweep-tag size_probe --t %SIZE_PROBE_T% --eps %SIZE_PROBE_EPS% --tau %SIZE_PROBE_TAU% --batch-seed %SIZE_PROBE_SEED% --hooks "%SIZE_PROBE_HOOKS%" --overrides "%OVERRIDES_PATH%" --reserve-gb %SIZE_PROBE_RESERVE_GB% --safety-fraction %SIZE_PROBE_FRACTION% --temp-root "%TEMP_ROOT%" --skip-pip --print-recommended-jobs --quiet`) do set "SIZE_PROBE_JOBS=%%J"



  if errorlevel 1 echo.[warn] size-probe failed; keeping PARALLEL_JOBS=%PARALLEL_JOBS%



  set "SIZE_PROBE_JOBS_RAW=!SIZE_PROBE_JOBS!"
  if not "!SIZE_PROBE_JOBS!"=="" for /f "tokens=1 delims=." %%Z in ("!SIZE_PROBE_JOBS!") do set "SIZE_PROBE_JOBS=%%Z"



  set "SIZE_PROBE_JOBS_OK=1"
  if "!SIZE_PROBE_JOBS!"=="" set "SIZE_PROBE_JOBS_OK=0"



  if "!SIZE_PROBE_JOBS_OK!"=="1" for /f "delims=0123456789" %%A in ("!SIZE_PROBE_JOBS!") do set "SIZE_PROBE_JOBS_OK=0"



  if "!SIZE_PROBE_JOBS_OK!"=="0" (



    if defined SIZE_PROBE_JOBS_RAW echo.[warn] size-probe jobs invalid: "!SIZE_PROBE_JOBS_RAW!" -> 1



    set "SIZE_PROBE_JOBS=1"



  )



  if "!SIZE_PROBE_JOBS!"=="0" set "SIZE_PROBE_JOBS=1"



  if defined SIZE_PROBE_JOBS (

    set "PARALLEL_JOBS=!SIZE_PROBE_JOBS!"

    %LOG_INFO% size-probe recommended parallel_jobs=!PARALLEL_JOBS!

  )

)

if "%PARALLEL_JOBS_DEFAULT%"=="1" if "%PARALLEL_JOBS%"=="1" (
  if defined CPU_UTIL_TARGET_PERCENT (
    if /i "%PARALLEL_MODE%"=="cell" if /i "%MARSDISK_CELL_JOBS%"=="auto" (
      for /f "usebackq tokens=1-7 delims=|" %%A in (`!PYTHON_CMD! scripts\\runsets\\common\\calc_cell_jobs.py`) do (
        set "CELL_MEM_TOTAL_GB=%%A"
        set "CELL_CPU_LOGICAL=%%B"
        set "CELL_MEM_FRACTION_USED=%%C"
        set "CELL_CPU_FRACTION_USED=%%D"
        set "MARSDISK_CELL_JOBS=%%E"
        set "CELL_STREAM_MEM_GB=%%F"
        set "CELL_THREAD_LIMIT_AUTO=%%G"
      )
    )
    set "CPU_TARGET_CORES="
    set "PARALLEL_JOBS_TARGET="
    for /f "usebackq tokens=1,2 delims=|" %%A in (`!PYTHON_CMD! scripts\\runsets\\common\\calc_cpu_target_jobs.py`) do (
      set "CPU_TARGET_CORES=%%A"
      set "PARALLEL_JOBS_TARGET=%%B"
      if not "!PARALLEL_JOBS_TARGET!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET=%%Z"
    )
    set "PARALLEL_JOBS_TARGET_OK=1"
    if "!PARALLEL_JOBS_TARGET!"=="" set "PARALLEL_JOBS_TARGET_OK=0"
    if "!PARALLEL_JOBS_TARGET_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_TARGET!") do set "PARALLEL_JOBS_TARGET_OK=0"
    if "!PARALLEL_JOBS_TARGET_OK!"=="1" (
      if !PARALLEL_JOBS_TARGET! GTR 1 (
        if /i "%CPU_UTIL_RESPECT_MEM%"=="1" (
          set "PARALLEL_JOBS_MEM="
          for /f "usebackq tokens=1-3 delims=|" %%A in (`!PYTHON_CMD! scripts\\runsets\\common\\calc_parallel_jobs.py`) do (
            set "PARALLEL_JOBS_MEM=%%C"
            if not "!PARALLEL_JOBS_MEM!"=="" for /f "tokens=1 delims=." %%Z in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM=%%Z"
          )
          set "PARALLEL_JOBS_MEM_OK=1"
          if "!PARALLEL_JOBS_MEM!"=="" set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" for /f "delims=0123456789" %%A in ("!PARALLEL_JOBS_MEM!") do set "PARALLEL_JOBS_MEM_OK=0"
          if "!PARALLEL_JOBS_MEM_OK!"=="1" (
            if !PARALLEL_JOBS_TARGET! GTR !PARALLEL_JOBS_MEM! set "PARALLEL_JOBS_TARGET=!PARALLEL_JOBS_MEM!"
          )
        )
        set "PARALLEL_JOBS=!PARALLEL_JOBS_TARGET!"
        %LOG_INFO% cpu_target fallback: target_cores=!CPU_TARGET_CORES! parallel_jobs=!PARALLEL_JOBS!
      )
    )
  )
)



if "%DEBUG%"=="1" call :debug_log "parallel_final: mode=!PARALLEL_MODE! sweep_parallel=!SWEEP_PARALLEL! parallel_jobs=!PARALLEL_JOBS! cell_parallel=!MARSDISK_CELL_PARALLEL! cell_jobs=!MARSDISK_CELL_JOBS! cell_thread_limit=!CELL_THREAD_LIMIT! numba_threads=!NUMBA_NUM_THREADS! omp_threads=!OMP_NUM_THREADS!"

%LOG_INFO% launching run_temp_supply_sweep.cmd
if "%DEBUG%"=="1" call :debug_log "run_temp_supply: start cmd=scripts\research\run_temp_supply_sweep.cmd"

if "%DEBUG%"=="1" call :debug_log "run_temp_supply: trace_log=!TRACE_LOG!"



call scripts\research\run_temp_supply_sweep.cmd



set "RUN_RC=%errorlevel%"
if "%DEBUG%"=="1" call :debug_log "run_temp_supply: rc=!RUN_RC!"

if "%DEBUG%"=="1" if not "%RUN_RC%"=="0" if defined DEBUG_LOG_FILE echo.[error] run_temp_supply failed (rc=%RUN_RC%) -> "!DEBUG_LOG_FILE!"

if "%DEBUG%"=="1" if not "%RUN_RC%"=="0" if defined TRACE_LOG echo.[error] trace log="!TRACE_LOG!"




%LOG_INFO% run_temp_supply_sweep.cmd finished (rc=%RUN_RC%)







call :popd_safe



exit /b %RUN_RC%







:debug_log

if not "%DEBUG%"=="1" exit /b 0

if not defined DEBUG_LOG_FILE exit /b 0

setlocal DisableDelayedExpansion

set "DEBUG_LINE=%~1"

>>"%DEBUG_LOG_FILE%" echo %DEBUG_LINE%

endlocal

exit /b 0

:archive_fail_enabled



echo.[error] io.archive.enabled=true is required in %OVERRIDES_PATH%



exit /b 1







:archive_fail_dir



echo.[error] io.archive.dir is required in %OVERRIDES_PATH%



exit /b 1







:archive_fail_merge



echo.[error] io.archive.merge_target=external is required in %OVERRIDES_PATH%



exit /b 1







:archive_fail_verify



echo.[error] io.archive.verify_level=standard_plus is required in %OVERRIDES_PATH%



exit /b 1







:archive_fail_keep



echo.[error] io.archive.keep_local=metadata is required in %OVERRIDES_PATH%



exit /b 1







:archive_fail_batch_root



echo.[error] BATCH_ROOT must be internal; it matches io.archive.dir (%ARCHIVE_DIR_EXPECTED%)



exit /b 1







:ensure_abs


set "VAR_NAME=%~1"



set "VAR_VAL=!%VAR_NAME%!"



if not defined VAR_VAL exit /b 0



if "!VAR_VAL:~1,1!"==":" exit /b 0



if "!VAR_VAL:~0,2!"=="\\\\" exit /b 0



if "!VAR_VAL:~0,1!"=="\\" exit /b 0



set "%VAR_NAME%=%REPO_ROOT%\\!VAR_VAL!"

exit /b 0

:ensure_dir

set "VAR_NAME=%~1"
set "VAR_VAL=!%VAR_NAME%!"
if not defined VAR_VAL exit /b 0

set "DRIVE_OK=1"
if "!VAR_VAL:~1,1!"==":" (
  set "DRIVE_ROOT=!VAR_VAL:~0,2!"
  if not exist "!DRIVE_ROOT!\\" set "DRIVE_OK=0"
)
if "!VAR_VAL:~0,2!"=="\\\\" (
  if not exist "!VAR_VAL!" set "DRIVE_OK=0"
)
if "!DRIVE_OK!"=="0" (
  echo.[error] %VAR_NAME% drive/path unavailable: "!VAR_VAL!"
  exit /b 1
)

if not exist "!VAR_VAL!" mkdir "!VAR_VAL!" >nul 2>&1
if not exist "!VAR_VAL!" (
  echo.[error] %VAR_NAME% unavailable: "!VAR_VAL!"
  exit /b 1
)

exit /b 0



:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
exit /b %MARSDISK_POPD_ERRORLEVEL%

endlocal
