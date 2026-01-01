@echo off
rem Debug script: Run parallel sweep with visible windows to see errors
rem Usage: scripts\tests\debug_parallel_sweep.cmd

setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo. Debug: Parallel Sweep with Visible Windows
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
echo.[info] REPO_ROOT=!REPO_ROOT!
cd /d "!REPO_ROOT!"

rem --- Force visible windows for debugging ---
set "PARALLEL_WINDOW_STYLE=Normal"
set "DEBUG=1"
set "QUIET_MODE=0"

rem --- Limit to just 2 jobs for testing ---
set "PARALLEL_JOBS=1"

echo.
echo.[info] Running sweep with PARALLEL_WINDOW_STYLE=Normal
echo.[info] You should see child windows open with their output
echo.[info] If windows flash and close, check for errors
echo.

rem --- Run the sweep script with minimal parameters ---
call scripts\research\run_temp_supply_sweep.cmd --debug

echo.
echo.============================================================
echo. Sweep completed
echo.============================================================
echo.
echo.Check the out\ directory for output files.
echo.If child windows closed immediately, the jobs failed.
echo.

endlocal
