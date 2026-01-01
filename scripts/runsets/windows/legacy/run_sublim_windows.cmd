@echo off
rem Simple runner for the sublimation+smol+phase setup on Windows (cmd.exe).
rem - Creates .venv if missing, installs requirements, then runs the model.
rem - Adjust OUTDIR as desired; avoid characters like ':' that are illegal in paths.
rem - Prefers Python 3.11 on PATH; falls back to python/py or set PYTHON_EXE to a full path.

setlocal enabledelayedexpansion

set REPO=%~dp0..\..\..\..
for %%I in ("%REPO%") do set "REPO=%%~fI"
pushd "%REPO%"
set "MARSDISK_POPD_ACTIVE=1"

set OUTDIR=out\run_sublim_smol_phase_MAX50M
set ARCHIVE_DIR=E:\marsdisk_runs
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
  --config out\run_template_sublim_smol_phase_MAX50M\config_base_sublimation.yml ^
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
  --override sinks.sub_params.mode=hkl ^
  --override sinks.sub_params.alpha_evap=0.007 ^
  --override sinks.sub_params.mu=0.0440849 ^
  --override sinks.sub_params.A=13.613 ^
  --override sinks.sub_params.B=17850.0

if %errorlevel% neq 0 (
  echo [error] Run failed with exit code %errorlevel%.
  call :popd_safe
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
