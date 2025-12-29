@echo off
rem Wrapper for run_temp_supply_sweep.cmd with 1D geometry defaults.
setlocal EnableExtensions EnableDelayedExpansion

if not defined GEOMETRY_MODE set "GEOMETRY_MODE=1D"
if not defined GEOMETRY_NR set "GEOMETRY_NR=32"
if not defined SWEEP_TAG set "SWEEP_TAG=temp_supply_sweep_1d"
if not defined SHIELDING_MODE set "SHIELDING_MODE=off"
if not defined SUPPLY_MU_REFERENCE_TAU set "SUPPLY_MU_REFERENCE_TAU=1.0"
if not defined SUPPLY_FEEDBACK_ENABLED set "SUPPLY_FEEDBACK_ENABLED=0"
if not defined SUPPLY_HEADROOM_POLICY set "SUPPLY_HEADROOM_POLICY=off"
if not defined SUPPLY_TRANSPORT_MODE set "SUPPLY_TRANSPORT_MODE=direct"
if not defined SUPPLY_TRANSPORT_TMIX_ORBITS set "SUPPLY_TRANSPORT_TMIX_ORBITS=off"
if not defined SUPPLY_TRANSPORT_HEADROOM set "SUPPLY_TRANSPORT_HEADROOM=hard"
if not defined AUTO_JOBS set "AUTO_JOBS=1"
if not defined PARALLEL_WINDOW_STYLE set "PARALLEL_WINDOW_STYLE=Hidden"
if not defined MARSDISK_CELL_PARALLEL set "MARSDISK_CELL_PARALLEL=1"
if not defined MARSDISK_CELL_MIN_CELLS set "MARSDISK_CELL_MIN_CELLS=4"
if not defined MARSDISK_CELL_CHUNK_SIZE set "MARSDISK_CELL_CHUNK_SIZE=0"
if not defined MARSDISK_CELL_JOBS (
  if defined NUMBER_OF_PROCESSORS (
    set "MARSDISK_CELL_JOBS=%NUMBER_OF_PROCESSORS%"
  ) else (
    set "MARSDISK_CELL_JOBS=1"
  )
)

call "%~dp0run_temp_supply_sweep.cmd" %*

endlocal
