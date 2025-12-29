@echo off
rem Smoke test: run a tiny 0D case and verify archive output lands on external HDD.

setlocal EnableExtensions EnableDelayedExpansion

if not defined PYTHON_EXE set "PYTHON_EXE=python3.11"
if not exist "%PYTHON_EXE%" (
  where %PYTHON_EXE% >nul 2>&1
  if errorlevel 1 (
    echo [error] %PYTHON_EXE% not found in PATH.
    exit /b 1
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

if not defined ARCHIVE_DIR set "ARCHIVE_DIR=E:\marsdisk_runs"
if not defined CONFIG_PATH set "CONFIG_PATH=configs\base.yml"
if not defined T_END_YEARS set "T_END_YEARS=0.001"
if not defined DT_INIT_S set "DT_INIT_S=1.0e4"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--archive-dir" (
  set "ARCHIVE_DIR=%~2"
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
if /i "%~1"=="--t-end-years" (
  set "T_END_YEARS=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--dt-init" (
  set "DT_INIT_S=%~2"
  shift
  shift
  goto :parse_args
)
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage

echo.[error] Unknown option: %~1
:usage
echo Usage: run_archive_external_smoke.cmd [--archive-dir ^<path^>] [--config ^<path^>]
echo.       [--t-end-years ^<years^>] [--dt-init ^<seconds^>]
popd
exit /b 1

:args_done

if not exist "%ARCHIVE_DIR%\\" (
  echo.[error] ARCHIVE_DIR not found: %ARCHIVE_DIR%
  popd
  exit /b 2
)

set "RUN_TS="
for /f %%A in ('"%PYTHON_EXE%" scripts\\runsets\\common\\timestamp.py') do set "RUN_TS=%%A"
set "OUTDIR=out\\archive_smoke\\%RUN_TS%__archive_smoke"
for %%F in ("%OUTDIR%") do set "RUN_NAME=%%~nxF"
set "ARCHIVE_DEST=%ARCHIVE_DIR%\\%RUN_NAME%"

set "VENV_DIR=.venv"
set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\\Scripts\\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [error] Failed to create virtual environment.
    popd
    exit /b 1
  )
)

call "%VENV_DIR%\\Scripts\\activate.bat"
if errorlevel 1 (
  echo [error] Failed to activate virtual environment.
  popd
  exit /b 1
)
set "PYTHON_EXE=%VENV_DIR%\\Scripts\\python.exe"

if "%SKIP_PIP%"=="1" (
  echo [setup] SKIP_PIP=1; skipping dependency install.
) else if exist "%REQ_FILE%" (
  echo [setup] Installing dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [error] Dependency install failed.
    popd
    exit /b 1
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

echo [run] OUTDIR=%OUTDIR%
echo [run] ARCHIVE_DEST=%ARCHIVE_DEST%

"%PYTHON_EXE%" -m marsdisk.run ^
  --config "%CONFIG_PATH%" ^
  --quiet ^
  --override geometry.mode=0D ^
  --override numerics.t_end_years=%T_END_YEARS% ^
  --override numerics.dt_init=%DT_INIT_S% ^
  --override sizes.n_bins=20 ^
  --override io.outdir=%OUTDIR% ^
  --override io.streaming.enable=true ^
  --override io.streaming.memory_limit_gb=1 ^
  --override io.streaming.step_flush_interval=50 ^
  --override io.streaming.merge_at_end=true ^
  --override io.archive.enabled=true ^
  --override io.archive.dir=%ARCHIVE_DIR% ^
  --override io.archive.trigger=post_merge ^
  --override io.archive.merge_target=external ^
  --override io.archive.verify_level=standard_plus ^
  --override io.archive.keep_local=metadata ^
  --override io.archive.record_volume_info=true ^
  --override io.archive.warn_slow_mb_s=40.0 ^
  --override io.archive.warn_slow_min_gb=5.0

set "RC=%errorlevel%"
if not "%RC%"=="0" (
  echo [error] Run failed with exit code %RC%.
  popd
  exit /b %RC%
)

if exist "%OUTDIR%\\INCOMPLETE" (
  echo [error] Archive marked INCOMPLETE; check %OUTDIR%\INCOMPLETE
  popd
  exit /b 3
)
if exist "%OUTDIR%\\ARCHIVE_SKIPPED" (
  echo [error] Archive skipped; check %OUTDIR%\ARCHIVE_SKIPPED
  popd
  exit /b 4
)
if not exist "%ARCHIVE_DEST%\\ARCHIVE_DONE" (
  echo [error] Archive marker missing: %ARCHIVE_DEST%\ARCHIVE_DONE
  popd
  exit /b 5
)
if not exist "%ARCHIVE_DEST%\\summary.json" (
  echo [error] summary.json missing in archive: %ARCHIVE_DEST%\summary.json
  popd
  exit /b 6
)
if not exist "%ARCHIVE_DEST%\\checks\\mass_budget.csv" (
  echo [error] mass_budget.csv missing in archive: %ARCHIVE_DEST%\checks\mass_budget.csv
  popd
  exit /b 7
)
if not exist "%ARCHIVE_DEST%\\series\\run.parquet" (
  echo [error] run.parquet missing in archive: %ARCHIVE_DEST%\series\run.parquet
  popd
  exit /b 8
)

echo [done] Archive smoke test passed: %ARCHIVE_DEST%
popd
exit /b 0
