@echo off
rem Windows helper to run the sublimation+smol+cooling case using the same settings
rem as run_sublim_windows_cooling.cmd, but with repo-relative paths so it works
rem no matter where this script is invoked from.

setlocal enabledelayedexpansion

if not defined PYTHON_EXE (
  for %%P in (python3.11 python py) do (
    if not defined PYTHON_EXE (
      where %%P >nul 2>&1
      if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
  )
  if not defined PYTHON_EXE (
    echo [error] python3.11/python/py not found in PATH
    exit /b 1
  )
) else (
  if not exist "%PYTHON_EXE%" (
    where %PYTHON_EXE% >nul 2>&1
    if errorlevel 1 (
      echo [error] %PYTHON_EXE% not found in PATH
      exit /b 1
    )
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

set REPO=%~dp0..\..\..\..
for %%I in ("%REPO%") do set "REPO=%%~fI"
pushd "%REPO%"

set OUTDIR=out\run_sublim_smol_phase_cooling
set ARCHIVE_DIR=E:\marsdisk_runs
set TMK=4000.0
set TEMP_TABLE=data\mars_temperature_T4000p0K.csv
set CONFIG=out\run_template_sublim_smol_phase_MAX50M\config_base_sublimation.yml
set VENV_DIR=.venv
set REQ_FILE=requirements.txt

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if %errorlevel% neq 0 (
    echo [error] Failed to create virtual environment.
    popd
    exit /b %errorlevel%
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
  echo [error] Failed to activate virtual environment.
  popd
  exit /b %errorlevel%
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo [setup] Installing/upgrading dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo [error] Dependency installation failed.
    popd
    exit /b %errorlevel%
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

"%PYTHON_EXE%" -m marsdisk.run ^
  --config "%CONFIG%" ^
  --quiet ^
  --progress ^
  --override io.streaming.enable=true ^
  --override io.streaming.memory_limit_gb=80.0 ^
  --override io.streaming.step_flush_interval=10000 ^
  --override io.streaming.compression=snappy ^
  --override io.streaming.merge_at_end=true ^
  --override io.archive.enabled=true ^
  --override io.archive.dir=%ARCHIVE_DIR% ^
  --override io.archive.trigger=post_merge ^
  --override io.archive.merge_target=external ^
  --override io.archive.verify_level=standard_plus ^
  --override io.archive.keep_local=metadata ^
  --override io.archive.record_volume_info=true ^
  --override io.archive.warn_slow_mb_s=40.0 ^
  --override io.archive.warn_slow_min_gb=5.0 ^
  --override io.outdir=%OUTDIR% ^
  --override radiation.source=mars ^
  --override radiation.TM_K=%TMK% ^
  --override radiation.mars_temperature_driver.enabled=true ^
  --override radiation.mars_temperature_driver.mode=table ^
  --override radiation.mars_temperature_driver.table.path=%TEMP_TABLE% ^
  --override radiation.mars_temperature_driver.table.time_unit=day ^
  --override radiation.mars_temperature_driver.table.column_time=time_day ^
  --override radiation.mars_temperature_driver.table.column_temperature=T_K ^
  --override radiation.mars_temperature_driver.autogenerate.enabled=true ^
  --override radiation.mars_temperature_driver.autogenerate.output_dir=data ^
  --override radiation.mars_temperature_driver.autogenerate.dt_hours=1.0 ^
  --override radiation.mars_temperature_driver.autogenerate.min_years=2.0 ^
  --override radiation.mars_temperature_driver.autogenerate.time_margin_years=0.5 ^
  --override radiation.mars_temperature_driver.autogenerate.time_unit=day ^
  --override radiation.mars_temperature_driver.autogenerate.column_time=time_day ^
  --override radiation.mars_temperature_driver.autogenerate.column_temperature=T_K ^
  --override sinks.sub_params.mode=hkl ^
  --override sinks.sub_params.alpha_evap=0.007 ^
  --override sinks.sub_params.mu=0.0440849 ^
  --override sinks.sub_params.A=13.613 ^
  --override sinks.sub_params.B=17850.0

set EXITCODE=%errorlevel%
if %EXITCODE% neq 0 (
  echo [error] Run failed with exit code %EXITCODE%.
  popd
  exit /b %EXITCODE%
)

echo [done] Run finished. Output: %OUTDIR%
popd
