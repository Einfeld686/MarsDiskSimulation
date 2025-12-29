@echo off
rem Simple runner for the sublimation+smol+phase setup on Windows (cmd.exe).
rem - Creates .venv if missing, installs requirements, then runs the model.
rem - Adjust OUTDIR as desired; avoid characters like ':' that are illegal in paths.
rem - Requires Python 3.11 on PATH; replace "python3.11" below if full path is needed.

setlocal enabledelayedexpansion

if not defined PYTHON_EXE set "PYTHON_EXE=python3.11"
if not exist "%PYTHON_EXE%" (
  where %PYTHON_EXE% >nul 2>&1
  if errorlevel 1 (
    echo [error] %PYTHON_EXE% not found in PATH.
    exit /b 1
  )
)
set "PYTHON_BOOT=%PYTHON_EXE%"

for %%I in ("%~dp0..\..\..\..") do set "REPO=%%~fI"
pushd "%REPO%"

set OUTDIR=out\run_sublim_smol_phase_MAX50M
set ARCHIVE_DIR=E:\marsdisk_runs
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
  popd
  exit /b %errorlevel%
)

echo [done] Run finished. Output: %OUTDIR%
popd
