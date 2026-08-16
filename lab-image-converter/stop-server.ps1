# LabFile Converter - Stop Server (PowerShell)

$procs = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
    try { $_.CommandLine -like "*uvicorn*app.main*" } catch { $false }
}

if ($procs) {
    $procs | Stop-Process -Force
    Write-Host "Server stopped." -ForegroundColor Green
} else {
    Write-Host "Server is not running." -ForegroundColor Yellow
}
