@echo off
rem Windows helper to run the sublimation+smol+cooling case using the same settings
rem as run_sublim_windows_cooling.cmd, but with repo-relative paths so it works
rem no matter where this script is invoked from.

setlocal enabledelayedexpansion

set REPO=%~dp0..\..\..\..
for %%I in ("%REPO%") do set "REPO=%%~fI"
pushd "%REPO%"
set "MARSDISK_POPD_ACTIVE=1"

set OUTDIR=out\run_sublim_smol_phase_cooling
set ARCHIVE_DIR=E:\marsdisk_runs
set TMK=4000.0
set TEMP_TABLE=data\mars_temperature_T4000p0K.csv
set CONFIG=out\run_template_sublim_smol_phase_MAX50M\config_base_sublimation.yml
set VENV_DIR=.venv
set REQ_FILE=requirements.txt
set "RUNSETS_COMMON_DIR=%REPO%\scripts\runsets\common"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\venv_bootstrap.cmd"
if not exist "%VENV_BOOTSTRAP_CMD%" (
  echo [error] venv_bootstrap helper not found: "%VENV_BOOTSTRAP_CMD%"
  call :popd_safe
  exit /b 1
)
call "%VENV_BOOTSTRAP_CMD%"
if errorlevel 1 (
  set "BOOTSTRAP_RC=%errorlevel%"
  echo [error] Failed to initialize Python environment.
  call :popd_safe
  exit /b %BOOTSTRAP_RC%
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
  call :popd_safe %EXITCODE%
)

echo [done] Run finished. Output: %OUTDIR%
call :popd_safe

:popd_safe
set "MARSDISK_POPD_ERRORLEVEL=%~1"
if not defined MARSDISK_POPD_ERRORLEVEL set "MARSDISK_POPD_ERRORLEVEL=%ERRORLEVEL%"
if defined MARSDISK_POPD_ACTIVE (
  popd
  set "MARSDISK_POPD_ACTIVE="
)
endlocal & exit /b %MARSDISK_POPD_ERRORLEVEL%
