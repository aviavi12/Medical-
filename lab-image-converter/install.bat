@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo =========================================
echo   LabFile Converter — Windows Installer
echo =========================================
echo.

:: ----------------------------------------
:: Step 1: Find Python 3.10+
:: ----------------------------------------
echo [1/5] Checking Python...

set "PYTHON_CMD="

:: Try "python" first (most common on Windows)
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "PY_VER=%%v"
    for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info.major)" 2^>nul') do set "PY_MAJOR=%%v"
    for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "PY_MINOR=%%v"
    if !PY_MAJOR! geq 3 if !PY_MINOR! geq 10 (
        set "PYTHON_CMD=python"
    )
)

:: Try "python3" as fallback
if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>&1
    if %errorlevel%==0 (
        for /f "tokens=*" %%v in ('python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "PY_VER=%%v"
        for /f "tokens=*" %%v in ('python3 -c "import sys; print(sys.version_info.major)" 2^>nul') do set "PY_MAJOR=%%v"
        for /f "tokens=*" %%v in ('python3 -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "PY_MINOR=%%v"
        if !PY_MAJOR! geq 3 if !PY_MINOR! geq 10 (
            set "PYTHON_CMD=python3"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Python 3.10 or higher is required.
    echo.
    echo Download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo   Found: %PYTHON_CMD% %PY_VER%

:: ----------------------------------------
:: Step 2: Create virtual environment
:: ----------------------------------------
echo [2/5] Creating virtual environment...

if exist ".venv\Scripts\python.exe" (
    echo   Virtual environment already exists. Reusing.
) else (
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Created: .venv
)

:: ----------------------------------------
:: Step 3: Install dependencies
:: ----------------------------------------
echo [3/5] Installing dependencies...

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet 2>nul

set "INSTALL_OK=0"

if exist "offline-packages" (
    dir /b "offline-packages\*" >nul 2>&1
    if !errorlevel!==0 (
        echo   Trying offline packages...
        pip install --no-index --find-links offline-packages -r requirements.txt --quiet 2>nul
        if !errorlevel!==0 set "INSTALL_OK=1"
    )
)

if "!INSTALL_OK!"=="0" (
    echo   Downloading from PyPI (internet required^)...
    pip install -r requirements.txt --quiet
    if !errorlevel!==0 set "INSTALL_OK=1"
)

if "!INSTALL_OK!"=="0" (
    echo ERROR: Failed to install dependencies.
    echo   If aicspylibczi fails, try installing Python 3.12 from python.org
    pause
    exit /b 1
)

echo   Dependencies installed.

:: ----------------------------------------
:: Step 4: Create directories
:: ----------------------------------------
echo [4/5] Creating work directories...

if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
echo   uploads\ and outputs\ ready.

:: ----------------------------------------
:: Step 5: Create desktop shortcut
:: ----------------------------------------
echo [5/5] Creating desktop shortcut...

set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\LabFile Converter.lnk"
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Create shortcut via PowerShell
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%\launch.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'LabFile Converter - Scientific Image Converter'; $s.Save()"

if exist "%SHORTCUT%" (
    echo   Shortcut installed on Desktop.
) else (
    echo   Could not create shortcut. You can run launch.bat manually.
)

:: ----------------------------------------
:: Step 6: Verify
:: ----------------------------------------
echo.
echo Verifying installation...

set "VERIFY_OK=1"
python -c "import fastapi" 2>nul || set "VERIFY_OK=0"
python -c "import uvicorn" 2>nul || set "VERIFY_OK=0"
python -c "import PIL" 2>nul || set "VERIFY_OK=0"
python -c "import numpy" 2>nul || set "VERIFY_OK=0"
python -c "import tifffile" 2>nul || set "VERIFY_OK=0"
python -c "import aicspylibczi" 2>nul || set "VERIFY_OK=0"

if "%VERIFY_OK%"=="1" (
    echo   All packages verified.
) else (
    echo   WARNING: Some packages may not have installed correctly.
    echo   The app may still work — try launching it.
)

:: ----------------------------------------
:: Done
:: ----------------------------------------
echo.
echo =========================================
echo   Installation Complete!
echo =========================================
echo.
echo   How to start:
echo     Option 1: Double-click "LabFile Converter" on your Desktop
echo     Option 2: Double-click launch.bat in this folder
echo.
echo   How to stop:
echo     Double-click stop-server.bat
echo     Or close the server window
echo.
echo   Browser opens automatically at: http://localhost:8000
echo.
pause
