@echo off
rem Windows runner for tau-timescale visualization (plot_tau_timescales.py)
setlocal EnableExtensions EnableDelayedExpansion

set "REPO=%~dp0.."
pushd "%REPO%"

if not defined VENV_DIR set "VENV_DIR=.venv"
if not defined REQ_FILE set "REQ_FILE=requirements.txt"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.[setup] Creating virtual environment in %VENV_DIR%...
  python -m venv "%VENV_DIR%"
  if %errorlevel% neq 0 (
    echo.[error] Failed to create virtual environment.
    popd
    exit /b %errorlevel%
  )
)

call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
  echo.[error] Failed to activate virtual environment.
  popd
  exit /b %errorlevel%
)

if exist "%REQ_FILE%" (
  echo.[setup] Installing/upgrading dependencies from %REQ_FILE% ...
  python -m pip install --upgrade pip
  pip install -r "%REQ_FILE%"
  if %errorlevel% neq 0 (
    echo.[error] Dependency installation failed.
    popd
    exit /b %errorlevel%
  )
) else (
  echo.[warn] %REQ_FILE% not found; skipping dependency install.
)

set "MPLBACKEND=Agg"

for /f %%A in ('powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"') do set "TOTAL_BYTES=%%A"
for /f %%A in ('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Measure-Object -Sum -Property NumberOfLogicalProcessors).Sum"') do set "CPU_LOGICAL=%%A"
for /f %%A in ('powershell -NoProfile -Command "$mem=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; [math]::Round($mem/1GB,2)"') do set "TOTAL_GB=%%A"

if not defined STREAM_MEM_GB (
  for /f %%A in ('powershell -NoProfile -Command "$mem=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; $total=[math]::Floor($mem/1GB); $candidate=[math]::Max(8, [math]::Floor($total*0.6)); $limit=[math]::Max(2, $total-4); [math]::Min($candidate, $limit)"') do set "STREAM_MEM_GB=%%A"
)

if not defined CPU_LOGICAL (
  for /f %%A in ('powershell -NoProfile -Command "[Environment]::ProcessorCount"') do set "CPU_LOGICAL=%%A"
)

if not defined STREAM_MEM_GB set "STREAM_MEM_GB=8"

echo.[sys] mem_total_gb=%TOTAL_GB% cpu_logical=%CPU_LOGICAL% stream_mem_gb=%STREAM_MEM_GB%

set "PLOT_ARGS=%*"
if "%~1"=="" (
  for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "$root=Join-Path $PWD 'out'; if (-not (Test-Path $root)) { exit 2 }; $files=Get-ChildItem -Path $root -Recurse -File -Filter 'run.parquet' -ErrorAction SilentlyContinue; if (-not $files) { $files=Get-ChildItem -Path $root -Recurse -File -Filter 'run_chunk_*.parquet' -ErrorAction SilentlyContinue }; if (-not $files) { exit 3 }; $file=$files | Sort-Object LastWriteTime -Descending | Select-Object -First 1; $run=$file.Directory.Parent.FullName; Write-Output $run"`) do set "DEFAULT_RUN=%%A"
  if not defined DEFAULT_RUN (
    echo.[error] No run outputs found under out\\ (need series\\run.parquet or run_chunk_*.parquet).
    popd
    exit /b 2
  )
  echo.[info] Using latest run: !DEFAULT_RUN!
  set "PLOT_ARGS=--run \"!DEFAULT_RUN!\""
)

python scripts\plot_tau_timescales.py !PLOT_ARGS!
set EXITCODE=%errorlevel%
if %EXITCODE% neq 0 (
  echo.[error] Plot failed with exit code %EXITCODE%.
  popd
  exit /b %EXITCODE%
)

popd
endlocal
