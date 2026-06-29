@echo off
setlocal enabledelayedexpansion

rem Always run from the repo root (this script's location).
cd /d "%~dp0"

set "APP_NAME=PhastTemperatureAnalyser"
set "EXE_PATH=%~dp0dist\%APP_NAME%\%APP_NAME%.exe"

echo [build] Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

rem Prefer uv when the project is uv-managed (pyproject.toml + uv.lock).
where uv >nul 2>nul
if %errorlevel%==0 if exist "uv.lock" (
    echo [build] Using uv ^(installing 'dev' group: PyInstaller^)...
    uv sync --group dev
    if errorlevel 1 (
        echo [build] ERROR: 'uv sync --group dev' failed.
        exit /b 1
    )
    uv run --group dev pyinstaller build.spec --noconfirm --clean
    if errorlevel 1 (
        echo [build] ERROR: PyInstaller build failed.
        exit /b 1
    )
    goto :success
)

rem Fallback: use the project's virtual environment directly.
echo [build] uv not available - falling back to .venv...
if not exist ".venv\Scripts\python.exe" (
    echo [build] ERROR: No uv and no .venv found. Create a venv and install pyinstaller.
    exit /b 1
)
".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [build] Installing PyInstaller into .venv...
    ".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.11"
    if errorlevel 1 (
        echo [build] ERROR: Failed to install PyInstaller.
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m PyInstaller build.spec --noconfirm --clean
if errorlevel 1 (
    echo [build] ERROR: PyInstaller build failed.
    exit /b 1
)

:success
if not exist "%EXE_PATH%" (
    echo [build] ERROR: PyInstaller reported success but the executable is missing:
    echo         %EXE_PATH%
    echo [build] This usually means antivirus / EDR ^(e.g. Windows Defender,
    echo         SentinelOne, Trend Micro^) quarantined the PyInstaller bootloader.
    echo         Add a folder exclusion for this project's 'build' and 'dist'
    echo         directories ^(or whitelist the bootloader^) and rebuild.
    exit /b 1
)
echo.
echo [build] SUCCESS
echo [build] Executable: %EXE_PATH%
endlocal
