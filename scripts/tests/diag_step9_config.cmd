@echo off
rem Step 9 detailed diagnostic: Config file validation
setlocal EnableExtensions EnableDelayedExpansion

echo.============================================================
echo. Step 9 Detailed Diagnostic: Config File Validation
echo.============================================================
echo.

for %%I in ("%~dp0\..\..") do set "REPO_ROOT=%%~fI"
set "COMMON_DIR=!REPO_ROOT!\scripts\runsets\common"
set "CONFIG_PATH=!COMMON_DIR!\base.yml"

echo.[info] REPO_ROOT: !REPO_ROOT!
echo.[info] CONFIG_PATH: !CONFIG_PATH!
echo.

rem Check if file exists
if not exist "!CONFIG_PATH!" (
    echo.[FAIL] Config file does not exist: !CONFIG_PATH!
    goto :end
)
echo.[OK] Config file exists
echo.

rem Resolve Python
call "!COMMON_DIR!\resolve_python.cmd"
if !errorlevel! neq 0 (
    echo.[FAIL] Python resolution failed
    goto :end
)
echo.[OK] Python resolved: !PYTHON_EXE! !PYTHON_ARGS!
echo.

rem Change to repo root
pushd "!REPO_ROOT!"

rem Test 1: Check if yaml module is available
echo.[Test 1] Checking PyYAML installation...
if defined PYTHON_ARGS (
    "!PYTHON_EXE!" !PYTHON_ARGS! -c "import yaml; print('PyYAML version:', yaml.__version__)"
) else (
    "!PYTHON_EXE!" -c "import yaml; print('PyYAML version:', yaml.__version__)"
)
if !errorlevel! neq 0 (
    echo.[FAIL] PyYAML is not installed
    echo.
    echo.To fix, run:
    echo.  pip install pyyaml
    popd
    goto :end
)
echo.

rem Test 2: Try to load the config with detailed error
echo.[Test 2] Loading config file with error details...
if defined PYTHON_ARGS (
    "!PYTHON_EXE!" !PYTHON_ARGS! -c "import yaml; import sys; f=open(r'!CONFIG_PATH!', encoding='utf-8'); data=yaml.safe_load(f); print('Config loaded successfully'); print('Top-level keys:', list(data.keys())[:5])"
) else (
    "!PYTHON_EXE!" -c "import yaml; import sys; f=open(r'!CONFIG_PATH!', encoding='utf-8'); data=yaml.safe_load(f); print('Config loaded successfully'); print('Top-level keys:', list(data.keys())[:5])"
)
if !errorlevel! neq 0 (
    echo.
    echo.[FAIL] Config file parsing failed. See error above.
    echo.
    echo.Possible causes:
    echo.  1. YAML syntax error in the file
    echo.  2. File encoding issue (should be UTF-8)
    echo.  3. Invalid characters in file path
    popd
    goto :end
)
echo.

rem Test 3: Check ruamel.yaml (used by marsdisk)
echo.[Test 3] Checking ruamel.yaml installation...
if defined PYTHON_ARGS (
    "!PYTHON_EXE!" !PYTHON_ARGS! -c "from ruamel.yaml import YAML; print('ruamel.yaml is available')"
) else (
    "!PYTHON_EXE!" -c "from ruamel.yaml import YAML; print('ruamel.yaml is available')"
)
if !errorlevel! neq 0 (
    echo.[WARN] ruamel.yaml is not installed (marsdisk may require it)
    echo.
    echo.To fix, run:
    echo.  pip install ruamel.yaml
)
echo.

popd

echo.
echo.============================================================
echo. All config validation tests passed!
echo.============================================================

:end
endlocal
