# DubStudio Lightweight App Layer Builder (v2.0.0 Next-Gen)
param(
    [switch]$SkipVelopack = $false,
    [switch]$CleanupSpace = $true
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Py = "$Root\.venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Building DubStudio v2.0.0 App Layer (< 400 MB)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Stop any running DubStudio instance to avoid file locks
Get-Process DubStudio -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2. Build production React bundle into frontend/dist
Write-Host "Compiling frontend React/Tailwind bundle..." -ForegroundColor Cyan
[Environment]::SetEnvironmentVariable('PATH', 'C:\Program Files\nodejs;' + [Environment]::GetEnvironmentVariable('PATH', 'Process'), 'Process')
Push-Location "$Root\frontend"
try {
    & "C:\Program Files\nodejs\npm.cmd" run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend compilation failed."
    }
} finally {
    Pop-Location
}

# 3. Compile standalone desktop app via PyInstaller
Write-Host "Compiling binary with PyInstaller..." -ForegroundColor Cyan
& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name DubStudio `
    --icon "$Root\dubstudio.ico" `
    --collect-all webview `
    --collect-all pythonnet `
    --exclude-module torch `
    --exclude-module torchvision `
    --exclude-module torchaudio `
    --exclude-module triton `
    --exclude-module onnxruntime `
    --exclude-module ctranslate2 `
    --exclude-module nvidia `
    --exclude-module scipy `
    --exclude-module numba `
    --exclude-module llvmlite `
    --exclude-module matplotlib `
    --exclude-module sympy `
    --exclude-module mpmath `
    --exclude-module sklearn `
    --exclude-module pandas `
    --exclude-module dask `
    --exclude-module cupy `
    --exclude-module tzdata `
    --exclude-module PyQt6 `
    --exclude-module PyQt6.QtCore `
    --exclude-module PyQt6.QtGui `
    --exclude-module PyQt6.QtWidgets `
    --exclude-module PyQt6.sip `
    --exclude-module PyQt5 `
    --exclude-module tkinter `
    --exclude-module ui `
    --add-data "frontend\dist;frontend\dist" `
    --add-data "dubstudio;dubstudio" `
    --add-data "config;config" `
    "$Root\start_app.py"

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
}

# Remove tzdata if present to prevent Windows symlink packaging failures
if (Test-Path "$Root\dist\DubStudio\_internal\tzdata") {
    Remove-Item -Path "$Root\dist\DubStudio\_internal\tzdata" -Recurse -Force -ErrorAction SilentlyContinue
}

# Ensure bin (ffmpeg, ffprobe) is present in dist\DubStudio
if (Test-Path "$Root\bin") {
    Copy-Item -Path "$Root\bin" -Destination "$Root\dist\DubStudio\bin" -Recurse -Force
}

# Ensure application icon is present
if (Test-Path "$Root\dubstudio.ico") {
    Copy-Item -Path "$Root\dubstudio.ico" -Destination "$Root\dist\DubStudio\dubstudio.ico" -Force
    Copy-Item -Path "$Root\dubstudio.ico" -Destination "$Root\dist\DubStudio\app.ico" -Force
}

# 4. Create Velopack release package (optional)
$Vpk = "$env:USERPROFILE\.dotnet\tools\vpk.exe"
if (-not $SkipVelopack -and (Test-Path $Vpk)) {
    $Version = (& $Py -c "from dubstudio.version import APP_VERSION; print(APP_VERSION)").Trim()
    Write-Host "Packaging with Velopack (v$Version) into dist\releases..." -ForegroundColor Cyan
    Remove-Item -Path "$Root\dist\releases\*" -Recurse -Force -ErrorAction SilentlyContinue
    & $Vpk pack `
        --packId DubStudio `
        --packVersion $Version `
        --packTitle "DubStudio" `
        --packAuthors "DubStudio Team" `
        --packDir "$Root\dist\DubStudio" `
        --mainExe "DubStudio.exe" `
        --icon "$Root\dubstudio.ico" `
        --channel "win" `
        --noPortable `
        --outputDir "$Root\dist\releases"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Velopack packaging failed."
    }
} else {
    Write-Host "Skipping Velopack installer packaging as requested." -ForegroundColor Yellow
}

# 5. Cleanup temporary build files to free up disk space
if ($CleanupSpace) {
    Write-Host "Cleaning up temporary build artifacts and release cache to save disk space..." -ForegroundColor Cyan
    if (Test-Path "$Root\build") {
        Remove-Item -Path "$Root\build" -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($SkipVelopack -and (Test-Path "$Root\dist\releases")) {
        Remove-Item -Path "$Root\dist\releases\*" -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "App layer v2.0.0 built and packaged successfully." -ForegroundColor Green
