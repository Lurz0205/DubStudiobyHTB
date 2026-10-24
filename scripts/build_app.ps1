# DubStudio Lightweight App Layer Builder
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Py = "$Root\.venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Building Lightweight App Layer (< 400 MB)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Stop any running DubStudio instance to avoid file locks
Get-Process DubStudio -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name DubStudio `
    --icon "$Root\dubstudio.ico" `
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
    --add-data "ui;ui" `
    --add-data "dubstudio;dubstudio" `
    --add-data "config;config" `
    "$Root\start_app.py"

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
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

# Create Velopack release package
$Vpk = "$env:USERPROFILE\.dotnet\tools\vpk.exe"
if (Test-Path $Vpk) {
    $Version = (& $Py -c "from dubstudio.version import APP_VERSION; print(APP_VERSION)").Trim()
    Write-Host "Packaging with Velopack (v$Version) into dist\releases..." -ForegroundColor Cyan
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
}

Write-Host "App layer built and packaged successfully." -ForegroundColor Green
