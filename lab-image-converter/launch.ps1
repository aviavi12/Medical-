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

# Start server in background, wait for it, then open browser
Write-Host "Starting LabFile Converter..." -ForegroundColor Blue
Write-Host ""

$job = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $Port" `
    -WorkingDirectory $ScriptDir `
    -PassThru

# Wait up to 15 seconds for server to be ready
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-WebRequest -Uri "$Url/health" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop | Out-Null
        $ready = $true
        break
    } catch {}
}

if ($ready) {
    Write-Host "Server is running at: $Url" -ForegroundColor Green
    Start-Process $Url
    Write-Host ""
    Write-Host "The browser should open automatically." -ForegroundColor Green
    Write-Host "To stop the server, run: .\stop-server.ps1" -ForegroundColor Yellow
} else {
    Write-Host "Server may still be starting. Try opening $Url manually." -ForegroundColor Yellow
}
