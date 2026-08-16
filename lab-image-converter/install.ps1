# LabFile Converter - Windows Installer (PowerShell)

Write-Host ""
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "  LabFile Converter - Installer" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# --- Step 1: Find Python ---
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow

$PythonCmd = $null

foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $major = & $cmd -c "import sys; print(sys.version_info.major)" 2>$null
        $minor = & $cmd -c "import sys; print(sys.version_info.minor)" 2>$null
        if ([int]$major -ge 3 -and [int]$minor -ge 10) {
            $PythonCmd = $cmd
            break
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Host "ERROR: Python 3.10 or higher is required." -ForegroundColor Red
    Write-Host ""
    Write-Host "Download from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "  Found: $PythonCmd $ver" -ForegroundColor Green

# --- Step 2: Create virtual environment ---
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow

if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "  Virtual environment already exists. Reusing."
} else {
    & $PythonCmd -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  Created: .venv" -ForegroundColor Green
}

# --- Step 3: Install dependencies ---
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow

& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet 2>$null

$installOk = $false

if (Test-Path "offline-packages") {
    $files = Get-ChildItem "offline-packages" -ErrorAction SilentlyContinue
    if ($files.Count -gt 0) {
        Write-Host "  Trying offline packages..."
        & .venv\Scripts\pip.exe install --no-index --find-links offline-packages -r requirements.txt --quiet 2>$null
        if ($LASTEXITCODE -eq 0) {
            $installOk = $true
        } else {
            Write-Host "  Offline packages not compatible, downloading from internet..." -ForegroundColor Yellow
        }
    }
}

if (-not $installOk) {
    Write-Host "  Downloading from PyPI (internet required)..."
    & .venv\Scripts\pip.exe install -r requirements.txt --quiet
    if ($LASTEXITCODE -eq 0) { $installOk = $true }
}

if (-not $installOk) {
    Write-Host ""
    Write-Host "WARNING: Some packages may have failed." -ForegroundColor Yellow
    Write-Host "  If aicspylibczi failed, install Python 3.12 from python.org" -ForegroundColor Yellow
    Write-Host "  The app may still work for TIFF/PNG/JPEG files." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "  Dependencies installed." -ForegroundColor Green

# --- Step 4: Create directories ---
Write-Host "[4/5] Creating work directories..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path "uploads" -Force | Out-Null
New-Item -ItemType Directory -Path "outputs" -Force | Out-Null
Write-Host "  uploads\ and outputs\ ready."

# --- Step 5: Desktop shortcut ---
Write-Host "[5/5] Creating desktop shortcut..." -ForegroundColor Yellow

$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "LabFile Converter.lnk"
$StartCmd = Join-Path $ScriptDir "START.cmd"

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $StartCmd
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Description = "LabFile Converter - Scientific Image Converter"
    $Shortcut.Save()
    Write-Host "  Shortcut installed on Desktop." -ForegroundColor Green
} catch {
    Write-Host "  Could not create shortcut. Double-click START.cmd to launch." -ForegroundColor Yellow
}

# --- Verify ---
Write-Host ""
Write-Host "Verifying..." -ForegroundColor Yellow

$allOk = $true
foreach ($pkg in @("fastapi", "uvicorn", "PIL", "numpy", "tifffile")) {
    & .venv\Scripts\python.exe -c "import $pkg" 2>$null
    if ($LASTEXITCODE -ne 0) { $allOk = $false }
}

if ($allOk) {
    Write-Host "  All core packages verified." -ForegroundColor Green
} else {
    Write-Host "  Some packages could not be verified." -ForegroundColor Yellow
}

# --- Done ---
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  How to start:"
Write-Host "    Option 1: Double-click 'LabFile Converter' on your Desktop"
Write-Host "    Option 2: Run in PowerShell:  .\launch.ps1"
Write-Host ""
Write-Host "  How to stop:"
Write-Host "    Close the server window, or run:  .\stop-server.ps1"
Write-Host ""
Write-Host "  Browser opens automatically at: http://localhost:8000"
Write-Host ""
Read-Host "Press Enter to close"
