# LabFile Converter - Launcher (PowerShell)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Port = 8000
$Url = "http://localhost:$Port"

# Check venv exists
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment not found. Run install.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if server is already running
try {
    $response = Invoke-WebRequest -Uri "$Url/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    Write-Host "Server is already running." -ForegroundColor Green
    Start-Process $Url
    exit 0
} catch {}

# Start server
Write-Host "Starting LabFile Converter..." -ForegroundColor Blue
Write-Host "Server will be at: $Url" -ForegroundColor Blue
Write-Host "Close this window to stop the server." -ForegroundColor Yellow
Write-Host ""

Start-Process $Url

& .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port
