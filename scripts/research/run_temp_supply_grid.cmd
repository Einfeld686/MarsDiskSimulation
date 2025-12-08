@echo off
rem 0D Mars disk sweep over Mars surface temperature (T_M) and supply mixing (epsilon_mix).
rem Combines T_M in {2000, 4000, 6000} with epsilon_mix in {1.0, 0.1} for 6 runs.
rem Uses configs\temp_supply_sweep.yml (sublimation ON, gas-poor, Smol collisions) and enables the Mars temperature driver for radiative cooling.
rem Update SUPPLY_RATE below to set supply.const.prod_area_rate_kg_m2_s.

setlocal enabledelayedexpansion

set CONFIG=configs\temp_supply_sweep.yml
set OUTBASE=out\temp_supply_grid
set SUPPLY_RATE=1.0e-10
set STREAMING_ENABLE=true
set STREAMING_MEMORY_GB=70.0
set STREAMING_FLUSH_STEPS=10000
set MU_HKL=0.0440849

rem Prioritise the baseline T=4000 K, epsilon_mix=1.0 first for a quick sanity check.
for %%T in (4000 2000 6000) do (
  for %%M in (1.0 0.1) do (
    set "M_LABEL=%%M"
    set "M_LABEL=!M_LABEL:.=p!"
    set "MU_LABEL=%MU_HKL%"
    set "MU_LABEL=!MU_LABEL:.=p!"
    set "OUTDIR=%OUTBASE%_T%%T_eps!M_LABEL!_mu!MU_LABEL!"

    echo [run] T_M=%%T K, epsilon_mix=%%M -> !OUTDIR!
    python -m marsdisk.run ^
      --config "%CONFIG%" ^
      --override supply.const.prod_area_rate_kg_m2_s=%SUPPLY_RATE% ^
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

    if errorlevel 1 (
      echo [error] Run failed for T_M=%%T, epsilon_mix=%%M
      exit /b %errorlevel%
    )
  )
)

echo [done] All runs completed.
