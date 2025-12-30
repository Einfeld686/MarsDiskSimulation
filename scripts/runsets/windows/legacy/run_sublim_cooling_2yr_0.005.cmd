@echo off
rem Mars disk sublimation+smol+phase runner with enforced Mars-surface cooling (cmd.exe).
rem Variant: fixes simulation duration to 2 years via override.
rem - Creates .venv if missing, installs requirements, then runs with radiative cooling table/autogen enabled.
rem - OUTDIR/TMK/TABLE can be adjusted below. Avoid ':' or other illegal path chars.
rem - Prefers Python 3.11 on PATH; falls back to python/py or set PYTHON_EXE to a full path.

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

set OUTDIR=out\run_sublim_smol_phase_cooling_2yr
set ARCHIVE_DIR=E:\marsdisk_runs
set TMK=4000.0
set TEMP_TABLE=data\mars_temperature_T4000p0K.csv
rem Use a schema-compliant config (temps.* is no longer supported)
set CONFIG=configs\mars_temperature_driver_table.yml
set VENV_DIR=.venv
set REQ_FILE=requirements.txt

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  "%PYTHON_BOOT%" -m venv "%VENV_DIR%"
  if %errorlevel% neq 0 (
    echo [error] Failed to create virtual environment.
    exit /b %errorlevel%
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
  echo [error] Failed to activate virtual environment.
  exit /b %errorlevel%
)
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if exist "%REQ_FILE%" (
  echo [setup] Installing/upgrading dependencies from %REQ_FILE% ...
  "%PYTHON_EXE%" -m pip install --upgrade pip
  "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo [error] Dependency installation failed.
    exit /b %errorlevel%
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

"%PYTHON_EXE%" -m marsdisk.run ^
  --config "%CONFIG%" ^
  --quiet ^
  --progress ^
  --override io.archive.enabled=true ^
  --override io.archive.dir=%ARCHIVE_DIR% ^
  --override io.archive.trigger=post_merge ^
  --override io.archive.merge_target=external ^
  --override io.archive.verify_level=standard_plus ^
  --override io.archive.keep_local=metadata ^
  --override io.archive.record_volume_info=true ^
  --override io.archive.warn_slow_mb_s=40.0 ^
  --override io.archive.warn_slow_min_gb=5.0 ^
  --override numerics.dt_init=auto ^
  --override numerics.safety=0.005 ^
  --override numerics.t_end_years=2.0 ^
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

if %errorlevel% neq 0 (
  echo [error] Run failed with exit code %errorlevel%.
  popd
  exit /b %errorlevel%
)

echo [done] Run finished. Output: %OUTDIR%
popd
