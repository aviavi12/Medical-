@echo off
echo Stopping LabFile Converter server...

taskkill /f /im uvicorn.exe >nul 2>&1
powershell -NoProfile -Command "Get-Process python* | Where-Object { $_.CommandLine -like '*uvicorn*app.main*' } | Stop-Process -Force" >nul 2>&1

echo Server stopped.
pause
