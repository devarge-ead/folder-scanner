@echo off
REM One-click build script for the Folder Scanner portable executable.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    py -3 -m venv .venv
)

echo [1/3] Installing / updating dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Building portable executable with PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean folder-scanner.spec
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo [3/3] Done.
echo Executable: dist\folder-scanner.exe
pause