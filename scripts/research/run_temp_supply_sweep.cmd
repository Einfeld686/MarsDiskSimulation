@echo off
rem Run the 6 pre-made configs (T={2000,4000,6000} x epsilon_mix={1.0,0.1})
rem located under configs\sweep_temp_supply\. Output paths are set inside each YAML.

setlocal enabledelayedexpansion

rem [optional] 手元のワークステーションメモリ（GB）に合わせて streaming 閾値を上書きする。
rem 例: set STREAM_MEM_GB=128
rem デフォルトは 70GB（各 YAML の既定値と揃える）。空のままなら YAML 既定値を使用。
set STREAM_MEM_GB=70
rem サブフラッシュ間隔を上書きしたい場合だけ設定（例: 20000）。空なら既定値。
set STREAM_STEP_INTERVAL=

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
  python -m pip install --upgrade pip
  pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo [error] Dependency installation failed.
    exit /b %errorlevel%
  )
) else (
  echo [warn] %REQ_FILE% not found; skipping dependency install.
)

set CONFIG_DIR=configs\sweep_temp_supply
set CONFIGS=%CONFIG_DIR%\temp_supply_T2000_eps1.yml %CONFIG_DIR%\temp_supply_T2000_eps0p1.yml %CONFIG_DIR%\temp_supply_T4000_eps1.yml %CONFIG_DIR%\temp_supply_T4000_eps0p1.yml %CONFIG_DIR%\temp_supply_T6000_eps1.yml %CONFIG_DIR%\temp_supply_T6000_eps0p1.yml

set STREAMING_OVERRIDES=
if defined STREAM_MEM_GB (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
  echo [info] override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
)
if defined STREAM_STEP_INTERVAL (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
  echo [info] override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
)

for %%C in (%CONFIGS%) do (
  echo [run] %%C
  python -m marsdisk.run --config "%%C" --quiet --progress !STREAMING_OVERRIDES!
  if errorlevel 1 (
    echo [error] Run failed for %%C
    exit /b %errorlevel%
  )
)

echo [done] All 6 runs completed.
