@echo off
rem Windows (cmd.exe) port of scripts/research/run_temp_supply_sweep.sh.
rem Runs 6 configs (T={2000,4000,6000} x epsilon_mix={1.0,0.1}) with dt_init=2 s,
rem writes to out\temp_supply_sweep\<timestamp>__<sha>__seed<batch>\<config>\,
rem and generates quick-look plots per run.
rem
rem Usage:
rem   run_temp_supply_sweep.cmd           -- normal execution
rem   run_temp_supply_sweep.cmd --debug   -- debug mode (show variable expansion)
rem   run_temp_supply_sweep.cmd --dry-run -- dry run (verify without execution)
rem   run_temp_supply_sweep.cmd --help    -- show help

setlocal enabledelayedexpansion

rem === Parse command line arguments ===
set DEBUG_MODE=0
set DRY_RUN=0
for %%a in (%*) do (
  if /i "%%a"=="--debug" set DEBUG_MODE=1
  if /i "%%a"=="--dry-run" set DRY_RUN=1
  if /i "%%a"=="--help" (
    echo Usage: %~nx0 [--debug] [--dry-run] [--help]
    echo   --debug   : Enable verbose output for debugging
    echo   --dry-run : Show what would be executed without running
    echo   --help    : Show this help message
    exit /b 0
  )
)
if %DEBUG_MODE%==1 (
  echo [DEBUG] Debug mode enabled - showing variable expansions
  echo on
)

rem Set streaming limits high to reduce I/O (adjust values as needed)
set STREAM_MEM_GB=70
set STREAM_STEP_INTERVAL=100000

rem Set to 1 to skip plot generation and reduce post-processing time
set SKIP_PLOTS=

set VENV_DIR=venv
set REQ_FILE=requirements.txt

rem Get the directory where this script is located
set SCRIPT_DIR=%~dp0

rem Navigate to repo root (two levels up from scripts\research\)
cd /d "%SCRIPT_DIR%"
cd ..\..
set REPO_ROOT=%CD%

set CONFIG_DIR=%REPO_ROOT%\configs\sweep_temp_supply
set CONFIGS_LIST="%CONFIG_DIR%\temp_supply_T2000_eps1.yml" "%CONFIG_DIR%\temp_supply_T2000_eps0p1.yml" "%CONFIG_DIR%\temp_supply_T4000_eps1.yml" "%CONFIG_DIR%\temp_supply_T4000_eps0p1.yml" "%CONFIG_DIR%\temp_supply_T6000_eps1.yml" "%CONFIG_DIR%\temp_supply_T6000_eps0p1.yml"
set BATCH_BASE=%REPO_ROOT%\out\temp_supply_sweep

for /f %%i in ('powershell -NoLogo -NoProfile -Command "Get-Date -Format \"yyyyMMdd-HHmmss\""') do set RUN_TS=%%i
if not defined RUN_TS set RUN_TS=run
for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set GIT_SHA=%%i
if not defined GIT_SHA set GIT_SHA=nogit
for /f %%i in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set BATCH_SEED=%%i
if not defined BATCH_SEED set BATCH_SEED=%RANDOM%
set BATCH_DIR=%BATCH_BASE%\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%

rem Check that out/temp_supply_sweep is not a file
if not exist "%BATCH_BASE%" mkdir "%BATCH_BASE%"
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    exit /b 1
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  exit /b 1
)

if exist "%REQ_FILE%" (
  echo [setup] Installing/upgrading dependencies from %REQ_FILE% ...
  python -m pip install --upgrade pip
  pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency installation failed.
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

if "%ENABLE_PROGRESS%"=="" set ENABLE_PROGRESS=1
set PROGRESS_OPT=
if "%ENABLE_PROGRESS%"=="1" set PROGRESS_OPT=--progress

set STREAMING_OVERRIDES=
if defined STREAM_MEM_GB (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
  echo [info] override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
)
if defined STREAM_STEP_INTERVAL (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
  echo [info] override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
)

for %%C in (%CONFIGS_LIST%) do (
  call :run_one "%%~fC"
)

echo [done] All 6 runs completed.
exit /b 0

:run_one
set CFG=%~1
if not exist "%CFG%" (
  echo [error] config not found: %CFG%
  exit /b 1
)
for /f %%s in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set SEED=%%s
if not defined SEED set SEED=%RANDOM%
for %%F in ("%CFG%") do set TITLE=%%~nF
set OUTDIR_BASE=%BATCH_DIR%\%TITLE%
set OUTDIR=%OUTDIR_BASE%
set OUTDIR_IDX=0

:find_outdir
if exist "%OUTDIR%\" (
  rem already a directory - OK
  goto :outdir_ready
)
if exist "%OUTDIR%" (
  rem exists as file, try alternate name
  set /a OUTDIR_IDX+=1
  set OUTDIR=%OUTDIR_BASE%__alt%OUTDIR_IDX%
  goto :find_outdir
)
rem does not exist, create it
mkdir "%OUTDIR%" 2>nul
if errorlevel 1 (
  echo [error] Failed to create OUTDIR "%OUTDIR%" (permission/lock?).
  exit /b 1
)
:outdir_ready

if %OUTDIR_IDX% gtr 0 (
  echo [info] OUTDIR existed as file; using %OUTDIR% instead
)

echo [run] %CFG% to %OUTDIR% (batch=%BATCH_SEED%, seed=%SEED%)

if %DRY_RUN%==1 (
  echo [dry-run] Would execute: python -m marsdisk.run --config "%CFG%" ...
  goto :eof
)

python -m marsdisk.run --config "%CFG%" --quiet %PROGRESS_OPT% %STREAMING_OVERRIDES% --override numerics.dt_init=2 --override "io.outdir=%OUTDIR%" --override "dynamics.rng_seed=%SEED%"
if errorlevel 1 (
  echo [error] Run failed for %CFG%
  exit /b 1
)

if not exist "%OUTDIR%\series" mkdir "%OUTDIR%\series"
if not exist "%OUTDIR%\checks" mkdir "%OUTDIR%\checks"

if /i "%SKIP_PLOTS%"=="1" (
  echo [info] SKIP_PLOTS=1, plotting skipped
) else (
  rem Delegate plot generation to external script
  python "%REPO_ROOT%\scripts\research\plot_sweep_run.py" "%OUTDIR%"
  if errorlevel 1 (
    echo [warn] Plotting failed for %CFG% (non-fatal, continuing)
  )
)
goto :eof
