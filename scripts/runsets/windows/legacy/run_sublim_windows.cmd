@echo off
rem Simple runner for the sublimation+smol+phase setup on Windows (cmd.exe).
rem - Creates .venv if missing, installs requirements, then runs the model.
rem - Adjust OUTDIR as desired; avoid characters like ':' that are illegal in paths.
rem - Requires Python on PATH; replace "python" below if必要ならフルパス指定。

setlocal enabledelayedexpansion

set REPO=%~dp0..\..\..\..
pushd "%REPO%"

set OUTDIR=out\run_sublim_smol_phase_MAX50M
set VENV_DIR=.venv
set REQ_FILE=requirements.txt

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [setup] Creating virtual environment in "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
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

if exist "%REQ_FILE%" (
  echo [setup] Installing/upgrading dependencies from %REQ_FILE% ...
  pip install --upgrade pip
  pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo [error] Dependency installation failed.
    exit /b %errorlevel%
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

python -m marsdisk.run ^
  --config out\run_template_sublim_smol_phase_MAX50M\config_base_sublimation.yml ^
  --quiet ^
  --progress ^
  --override io.streaming.enable=true ^
  --override io.streaming.memory_limit_gb=80.0 ^
  --override io.streaming.step_flush_interval=10000 ^
  --override io.streaming.compression=snappy ^
  --override io.streaming.merge_at_end=true ^
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
