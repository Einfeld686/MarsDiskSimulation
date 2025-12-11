@echo off
rem Windows (cmd.exe) port of scripts/research/run_temp_supply_sweep.sh.
rem Runs 6 configs (T={2000,4000,6000} x epsilon_mix={1.0,0.1}) with dt_init=2 s,
rem writes to out\temp_supply_sweep\<timestamp>__<sha>__seed<batch>\<config>\,
rem and generates quick-look plots per run.

setlocal enabledelayedexpansion

rem streaming 上限を高めに設定して I/O を削減（必要に応じて値を変更可）
set STREAM_MEM_GB=70
set STREAM_STEP_INTERVAL=100000

rem プロット生成をスキップして後処理時間を短縮したい場合は 1 に設定する
set SKIP_PLOTS=

set VENV_DIR=.venv
set REQ_FILE=requirements.txt
rem スクリプトの場所からリポジトリルートを解決（どこから実行しても同じになるように）
pushd "%~dp0\..\.."
set "REPO_ROOT=%CD%"
set "CONFIG_DIR=%REPO_ROOT%\configs\sweep_temp_supply"
set CONFIGS_LIST="%CONFIG_DIR%\temp_supply_T2000_eps1.yml" "%CONFIG_DIR%\temp_supply_T2000_eps0p1.yml" "%CONFIG_DIR%\temp_supply_T4000_eps1.yml" "%CONFIG_DIR%\temp_supply_T4000_eps0p1.yml" "%CONFIG_DIR%\temp_supply_T6000_eps1.yml" "%CONFIG_DIR%\temp_supply_T6000_eps0p1.yml"
set "BATCH_BASE=%REPO_ROOT%\out\temp_supply_sweep"

for /f %%i in ('powershell -NoLogo -NoProfile -Command "Get-Date -Format \"yyyyMMdd-HHmmss\""') do set RUN_TS=%%i
if not defined RUN_TS set RUN_TS=run
for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set GIT_SHA=%%i
if not defined GIT_SHA set GIT_SHA=nogit
for /f %%i in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set BATCH_SEED=%%i
if not defined BATCH_SEED set BATCH_SEED=!RANDOM!
set "BATCH_DIR=%BATCH_BASE%\%RUN_TS%__%GIT_SHA%__seed%BATCH_SEED%"

rem out/temp_supply_sweep がファイル化していないか確認
if exist "%BATCH_BASE%\NUL" (
  rem OK: directory
) else if exist "%BATCH_BASE%" (
  echo [error] %BATCH_BASE% exists as a file. Remove or rename it, then rerun.
  popd
  exit /b 1
) else (
  mkdir "%BATCH_BASE%"
)
if not exist "%BATCH_DIR%" mkdir "%BATCH_DIR%"

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

if "%ENABLE_PROGRESS%"=="" set ENABLE_PROGRESS=1
set "PROGRESS_OPT="
if "%ENABLE_PROGRESS%"=="1" set "PROGRESS_OPT=--progress"

set STREAMING_OVERRIDES=
if defined STREAM_MEM_GB (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
  echo [info] override io.streaming.memory_limit_gb=!STREAM_MEM_GB!
)
if defined STREAM_STEP_INTERVAL (
  set STREAMING_OVERRIDES=!STREAMING_OVERRIDES! --override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
  echo [info] override io.streaming.step_flush_interval=!STREAM_STEP_INTERVAL!
)

for %%C in (%CONFIGS_LIST%) do (
  call :run_one "%%~fC"
)

echo [done] All 6 runs completed.
popd
exit /b 0

:run_one
set "CFG=%~1"
if not exist "%CFG%" (
  echo [error] config not found: %CFG%
  exit /b 1
)
for /f %%s in ('python -c "import secrets; print(secrets.randbelow(2**31))"') do set SEED=%%s
if not defined SEED set SEED=!RANDOM!
set "TITLE=%~n1"
set "OUTDIR_BASE=%BATCH_DIR%\!TITLE!"
set "OUTDIR=%OUTDIR_BASE%"
set OUTDIR_IDX=0

:find_outdir
if exist "!OUTDIR!\NUL" (
  rem already a directory -> OK
) else if exist "!OUTDIR!" (
  set /a OUTDIR_IDX+=1
  set "OUTDIR=%OUTDIR_BASE%__alt!OUTDIR_IDX!"
  goto find_outdir
) else (
  mkdir "!OUTDIR!"
)

if %OUTDIR_IDX% gtr 0 (
  echo [info] OUTDIR existed as file; using !OUTDIR! instead
)

echo [run] %CFG% -> !OUTDIR! (batch=%BATCH_SEED%, seed=!SEED!)

python -m marsdisk.run ^
  --config "%CFG%" ^
  --quiet !PROGRESS_OPT! !STREAMING_OVERRIDES! ^
  --override numerics.dt_init=2 ^
  --override "io.outdir=!OUTDIR!" ^
  --override "dynamics.rng_seed=!SEED!"
if errorlevel 1 (
  echo [error] Run failed for %CFG%
  exit /b %errorlevel%
)

if not exist "!OUTDIR!\series" mkdir "!OUTDIR!\series"
if not exist "!OUTDIR!\checks" mkdir "!OUTDIR!\checks"

if /i "!SKIP_PLOTS!"=="1" (
  echo [info] SKIP_PLOTS=1 -> plotting skipped
) else (
  set "RUN_DIR=!OUTDIR!"
  python -c "import json,sys;from pathlib import Path;import matplotlib;matplotlib.use('Agg');import pandas as pd;import matplotlib.pyplot as plt;run_dir=Path(r'!RUN_DIR!');series_path=run_dir/'series'/'run.parquet';summary_path=run_dir/'summary.json';plots_dir=run_dir/'plots';plots_dir.mkdir(parents=True, exist_ok=True);if not series_path.exists(): print(f'[warn] series not found: {series_path}, skip plotting'); sys.exit(0);series_cols=['time','M_out_dot','M_sink_dot','M_loss_cum','mass_lost_by_blowout','mass_lost_by_sinks','s_min','a_blow','prod_subblow_area_rate','Sigma_surf','outflux_surface'];summary=json.loads(summary_path.read_text()) if summary_path.exists() else {};df=pd.read_parquet(series_path, columns=series_cols);n=len(df);step=max(n//4000,1);df=df.iloc[::step].copy();df['time_days']=df['time']/86400.0;fig,axes=plt.subplots(3,1,figsize=(10,12),sharex=True);axes[0].plot(df['time_days'],df['M_out_dot'],label='M_out_dot (blowout)',lw=1.2);axes[0].plot(df['time_days'],df['M_sink_dot'],label='M_sink_dot (sinks)',lw=1.0,alpha=0.7);axes[0].set_ylabel('M_Mars / s');axes[0].legend(loc='upper right');axes[0].set_title('Mass loss rates');axes[1].plot(df['time_days'],df['M_loss_cum'],label='M_loss_cum (total)',lw=1.2);axes[1].plot(df['time_days'],df['mass_lost_by_blowout'],label='mass_lost_by_blowout',lw=1.0);axes[1].plot(df['time_days'],df['mass_lost_by_sinks'],label='mass_lost_by_sinks',lw=1.0);axes[1].set_ylabel('M_Mars');axes[1].legend(loc='upper left');axes[1].set_title('Cumulative losses');axes[2].plot(df['time_days'],df['s_min'],label='s_min',lw=1.0);axes[2].plot(df['time_days'],df['a_blow'],label='a_blow',lw=1.0,alpha=0.8);axes[2].set_ylabel('m');axes[2].set_xlabel('days');axes[2].set_yscale('log');axes[2].legend(loc='upper right');axes[2].set_title('Minimum size vs blowout');mloss=summary.get('M_loss');mass_err=summary.get('mass_budget_max_error_percent');title_lines=[run_dir.name];if mloss is not None: title_lines.append(f'M_loss={mloss:.3e} M_Mars');if mass_err is not None: title_lines.append(f'mass budget err={mass_err:.3f} pct');fig.suptitle(' / '.join(title_lines));fig.tight_layout(rect=(0,0,1,0.96));fig.savefig(plots_dir/'overview.png',dpi=180);plt.close(fig);fig2,ax2=plt.subplots(2,1,figsize=(10,8),sharex=True);ax2[0].plot(df['time_days'],df['prod_subblow_area_rate'],label='prod_subblow_area_rate',color='tab:blue');ax2[0].set_ylabel('kg m^-2 s^-1');ax2[0].set_title('Sub-blow supply rate');ax2[1].plot(df['time_days'],df['Sigma_surf'],label='Sigma_surf',color='tab:green');ax2[1].plot(df['time_days'],df['outflux_surface'],label='outflux_surface (surface blowout)',color='tab:red',alpha=0.8);ax2[1].set_ylabel('kg m^-2 / M_Mars s^-1');ax2[1].set_xlabel('days');ax2[1].legend(loc='upper right');ax2[1].set_title('Surface mass and outflux');fig2.suptitle(run_dir.name);fig2.tight_layout(rect=(0,0,1,0.95));fig2.savefig(plots_dir/'supply_surface.png',dpi=180);plt.close(fig2);print(f'[plot] saved plots to {plots_dir}')" 
  if errorlevel 1 (
    echo [error] Plotting failed for %CFG%
    exit /b %errorlevel%
  )
)
goto :eof
