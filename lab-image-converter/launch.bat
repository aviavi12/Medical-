@echo off
chcp 65001 >nul 2>&1
setlocal

set "PORT=8000"
set "URL=http://localhost:%PORT%"
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

cd /d "%SCRIPT_DIR%"

:: Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

:: Check if server is already running
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%URL%/health' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo Server is already running.
    start "" "%URL%"
    exit /b 0
)

:: Start server
echo Starting LabFile Converter...
echo.
echo Server will be available at: %URL%
echo Close this window to stop the server.
echo.

start "" "%URL%"

python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
