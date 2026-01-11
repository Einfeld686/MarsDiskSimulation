@echo off
rem 0D Mars disk sweep over Mars surface temperature (T_M) and supply mixing (epsilon_mix).
rem Combines T_M in {2000, 4000, 6000} with epsilon_mix in {1.0, 0.1} for 6 runs.
rem Uses configs\temp_supply_sweep.yml (sublimation ON, gas-poor, Smol collisions) and enables the Mars temperature driver for radiative cooling.
rem External supply uses mu_orbit10pct (1 orbit supplies 5% of Sigma_surf0).

setlocal enabledelayedexpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SCRIPT_DIR=%~dp0"

set CONFIG=configs\temp_supply_sweep.yml
set OUTROOT=out\temp_supply_grid
set SUPPLY_MU_ORBIT10PCT=1.0
set SUPPLY_ORBIT_FRACTION=0.05
set OPTICAL_TAU0_TARGET=1.0
set OPTICAL_TAU_STOP=2.302585092994046
set OPTICAL_TAU_STOP_TOL=1.0e-6
set STREAMING_ENABLE=true
set STREAMING_MEMORY_GB=70.0
set STREAMING_FLUSH_STEPS=10000
set MU_HKL=0.0440849

rem Optional venv setup (portable, avoids system Python pollution)
set VENV_DIR=.venv
set REQ_FILE=requirements.txt
set "RUNSETS_COMMON_DIR=%SCRIPT_DIR%..\\runsets\\common"
for %%I in ("%RUNSETS_COMMON_DIR%") do set "RUNSETS_COMMON_DIR=%%~fI"
set "VENV_BOOTSTRAP_CMD=%RUNSETS_COMMON_DIR%\\venv_bootstrap.cmd"
if not exist "%VENV_BOOTSTRAP_CMD%" (
  echo [error] venv_bootstrap helper not found: "%VENV_BOOTSTRAP_CMD%"
  exit /b 1
)
call "%VENV_BOOTSTRAP_CMD%"
if not "!errorlevel!"=="0" (
  set "BOOTSTRAP_RC=!errorlevel!"
  echo [error] Failed to initialize Python environment.
  exit /b !BOOTSTRAP_RC!
)

rem Ensure base output directory exists and is not a file (avoid legacy \NUL checks)
if exist "%OUTROOT%\" (
  rem already a directory
) else if exist "%OUTROOT%" (
  echo [error] %OUTROOT% exists as a file. Remove or rename it before running.
  exit /b 1
) else (
  mkdir "%OUTROOT%"
)

rem Build a timestamp tag for unique subdirectories
set HOUR=%TIME:~0,2%
if "%HOUR:~0,1%"==" " set HOUR=0%HOUR:~1,1%
set RUN_TAG=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%HOUR%%TIME:~3,2%%TIME:~6,2%

rem Prioritise the baseline T=4000 K, epsilon_mix=1.0 first for a quick sanity check.
for %%T in (4000 2000 6000) do (
  for %%M in (1.0 0.1) do (
    set "M_LABEL=%%M"
    set "M_LABEL=!M_LABEL:.=p!"
    set "MU_LABEL=%MU_HKL%"
    set "MU_LABEL=!MU_LABEL:.=p!"
    set "OUTDIR=%OUTROOT%\%RUN_TAG%_T%%T_eps!M_LABEL!_mu!MU_LABEL!"

    rem Ensure OUTDIR is a directory and not an existing file (avoid legacy \NUL checks)
    if exist "!OUTDIR!\" (
      rem already a directory
    ) else if exist "!OUTDIR!" (
      echo [error] !OUTDIR! exists as a file. Remove or rename it before running.
      exit /b 1
    ) else (
      mkdir "!OUTDIR!"
    )

    echo [run] T_M=%%T K, epsilon_mix=%%M -> !OUTDIR!
    "%PYTHON_EXE%" -m marsdisk.run ^
      --config "%CONFIG%" ^
      --override supply.const.mu_orbit10pct=%SUPPLY_MU_ORBIT10PCT% ^
      --override supply.const.orbit_fraction_at_mu1=%SUPPLY_ORBIT_FRACTION% ^
      --override optical_depth.tau0_target=%OPTICAL_TAU0_TARGET% ^
      --override optical_depth.tau_stop=%OPTICAL_TAU_STOP% ^
      --override optical_depth.tau_stop_tol=%OPTICAL_TAU_STOP_TOL% ^
      --override sinks.sub_params.mu=%MU_HKL% ^
      --override radiation.mars_temperature_driver.enabled=true ^
      --override radiation.mars_temperature_driver.mode=table ^
      --override radiation.mars_temperature_driver.table.path=data/mars_temperature_T%%Tp0K.csv ^
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
      --override radiation.TM_K=%%T ^
      --override supply.mixing.epsilon_mix=%%M ^
      --override io.outdir=!OUTDIR! ^
      --override io.streaming.enable=%STREAMING_ENABLE% ^
      --override io.streaming.memory_limit_gb=%STREAMING_MEMORY_GB% ^
      --override io.streaming.step_flush_interval=%STREAMING_FLUSH_STEPS% ^
      --override io.streaming.merge_at_end=true ^
      --progress ^
      --quiet

    if not "!errorlevel!"=="0" (
      echo [error] Run failed for T_M=%%T, epsilon_mix=%%M
      exit /b !errorlevel!
    )
  )
)

echo [done] All runs completed.
endlocal
exit /b 0
