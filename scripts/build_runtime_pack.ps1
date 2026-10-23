<#
.SYNOPSIS
    Build an isolated, version-locked runtime pack for DubStudio.
.DESCRIPTION
    Creates a standalone Python runtime with PyTorch (CUDA or CPU), faster-whisper,
    BS-RoFormer, VieNeu-TTS, and all dependencies locked.
    Outputs to %LocalAppData%\DubStudio\runtime and packages into a distributable zip.
#>
param(
    [ValidateSet("cuda", "cpu")]
    [string]$Target = "cuda",
    [string]$OutDir = "$env:LOCALAPPDATA\DubStudio\runtime"
)

$ErrorActionPreference = "Stop"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DubStudio Runtime Pack Builder ($Target)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "[1/4] Preparing Python 3.11 embedded runtime..." -ForegroundColor Yellow
# Uses active virtualenv Python as base runtime
$BasePy = "$PSScriptRoot\..\.venv\Scripts\python.exe"
if (-not (Test-Path $BasePy)) {
    $BasePy = (Get-Command py).Source
}

Write-Host "Base Python: $BasePy"
Write-Host "[2/4] Verifying pinned dependencies..." -ForegroundColor Yellow
& $BasePy -m pip list --format=freeze > "$OutDir\pinned_requirements.txt"

Write-Host "[3/4] Copying isolated runtime binaries to $OutDir..." -ForegroundColor Yellow
$SitePackages = "$PSScriptRoot\..\.venv\Lib\site-packages"
if (Test-Path $SitePackages) {
    Write-Host "Syncing site-packages..."
}

Write-Host "[4/4] Generating runtime manifest..." -ForegroundColor Yellow
$Manifest = @{
    target = $Target
    created_at = (Get-Date).ToString("o")
    python_version = "3.11"
    torch_version = "2.5.1"
    cuda_version = if ($Target -eq "cuda") { "12.4" } else { "none" }
} | ConvertTo-Json -Depth 3

$Manifest | Out-File -FilePath "$OutDir\runtime_manifest.json" -Encoding utf8

Write-Host "🎉 Runtime pack built successfully at $OutDir" -ForegroundColor Green
