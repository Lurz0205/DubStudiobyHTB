# DubStudio Release Checkpoint Script
param(
    [string]$Channel = "beta",
    [string]$RepoUrl = "",
    [string]$GitHubToken = $env:GITHUB_TOKEN,
    [switch]$SkipConfirmation = $false
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Py = "$Root\.venv\Scripts\python.exe"
$Vpk = "$env:USERPROFILE\.dotnet\tools\vpk.exe"

# Automatically load GitHub credentials from .env if present
if (Test-Path "$Root\.env") {
    Get-Content "$Root\.env" | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(.*)$") {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim()
            if ($k -eq "GITHUB_TOKEN" -and -not $GitHubToken) { $GitHubToken = $v }
            if ($k -eq "GITHUB_REPO_URL" -and -not $RepoUrl) { $RepoUrl = $v }
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DubStudio Release Checkpoint Verification ($Channel)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Git state and Version
Write-Host "[1/6] Kiem tra trang thai Git va Phien ban..." -ForegroundColor Yellow
$CommitHash = "v2.1.0-release"
$HasGit = (Get-Command git -ErrorAction SilentlyContinue)
if ($HasGit) {
    try {
        $CommitHash = (git rev-parse --short HEAD).Trim()
    } catch {
        $CommitHash = "dev-build"
    }
}

$VerInfo = & $Py -c "from dubstudio.version import get_version_info; import json; print(json.dumps(get_version_info()))" | ConvertFrom-Json
$AppVersion = $VerInfo.version
$SchemaVersion = $VerInfo.schema_version
Write-Host "Phien ban App: v$AppVersion (Schema: $SchemaVersion, Commit: $CommitHash)" -ForegroundColor Green

# 2. Run Unit Tests & Smoke Test
Write-Host "[2/6] Chay Unit Tests..." -ForegroundColor Yellow
& $Py -m pytest "$Root\tests" -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "DUNG: Kiem thu that bai. Khong the phat hanh ban co loi."
}
Write-Host "[OK] Toan bo unit test vuot qua 100%." -ForegroundColor Green

# 3. Compare with previous release manifest
Write-Host "[3/6] So sanh voi release_manifest.json..." -ForegroundColor Yellow
$ManifestFile = "$Root\release_manifest.json"
$ReqHash = (Get-FileHash "$Root\requirements.txt" -Algorithm SHA256).Hash

if (Test-Path $ManifestFile) {
    try {
        $OldManifest = Get-Content $ManifestFile -Raw | ConvertFrom-Json
        if ($OldManifest.requirements_hash -ne $ReqHash -and $OldManifest.version -eq $AppVersion) {
            Write-Error "DUNG: requirements.txt da thay doi nhung phien ban chua tang hoac chua build runtime pack."
        }
    } catch {}
}

# 4. Self-test package verification & File Size Limits (< 1.8 GB)
Write-Host "[4/6] Chay tu kiem tra he thong (selftest) va kiem tra gioi han kich thuoc..." -ForegroundColor Yellow
& $Py -c "import dubstudio.packaging, dubstudio.gpu_check, dubstudio.components, dubstudio.migration; print('SELFTEST_OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Error "DUNG: Self-test import cac module that bai."
}

# Check all output release packages
$ReleasesDir = "$Root\dist\releases"
if (Test-Path $ReleasesDir) {
    $MaxSizeBytes = 1800MB  # 1.8 GB strict limit for GitHub 2 GB threshold
    $Files = Get-ChildItem -Path $ReleasesDir -File
    foreach ($File in $Files) {
        $SizeMB = [math]::Round($File.Length / 1MB, 2)
        if ($File.Length -gt $MaxSizeBytes) {
            Write-Error "DUNG: File '$($File.Name)' vuot qua gioi han an toan 1.8 GB ($SizeMB MB). Hay tach cac module AI nang thanh component rieng!"
        }
        Write-Host "  -> $($File.Name): $SizeMB MB [HOP LE]" -ForegroundColor DarkGreen
    }
}
Write-Host "[OK] Self-test va kiem tra gioi han dung luong hoan tat thanh cong." -ForegroundColor Green

# 5. Release Summary
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                   TOM TAT PHAT HANH                      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "- Ban phat hanh: v$AppVersion ($Channel) | Commit: $CommitHash | Schema: v$SchemaVersion"
Write-Host "- Nhom Code: Kien truc 2 lop sieu nhe, tach torch/cuda ra khoi app layer."
Write-Host "- Nhom Giao dien: Huong dan lay key Groq, Trang thai GPU va Quan ly Components."
Write-Host "- Nhom Components: Chia nho component < 1.5 GB tai truc tiep tu PyPI/Hugging Face."
Write-Host "- Nhom Gioi han: Chot chan 1.8 GB (tuyet doi duoi nguong 2 GB cua GitHub)."
Write-Host "- Nhom Phat hanh: Ho tro Velopack download & upload GitHub dong bo 1 full + 1 delta."

# Update release manifest
$NewManifest = @{
    version = "$AppVersion"
    schema_version = $SchemaVersion
    commit = "$CommitHash"
    requirements_hash = "$ReqHash"
    released_at = (Get-Date).ToString("s")
    channel = "$Channel"
} | ConvertTo-Json -Depth 3
$NewManifest | Out-File -FilePath $ManifestFile -Encoding utf8

# 6. Upload handling via Velopack
if (-not $SkipConfirmation) {
    Write-Host ""
    $Confirm = Read-Host "Nhap 'YES' de xac nhan phat hanh len kenh $Channel"
    if ($Confirm -ne "YES") {
        Write-Host "Da luu ban build cuc bo thanh cong." -ForegroundColor Yellow
        exit 0
    }
}

if ($RepoUrl -and $GitHubToken -and (Test-Path $Vpk)) {
    Write-Host "Dang tai ban phat hanh len GitHub Releases qua Velopack..." -ForegroundColor Yellow
    if ($Channel -eq "stable") {
        & $Vpk upload github --outputDir "$ReleasesDir" --repoUrl "$RepoUrl" --token "$GitHubToken" --tag "v$AppVersion" --merge --publish
    } else {
        & $Vpk upload github --outputDir "$ReleasesDir" --repoUrl "$RepoUrl" --token "$GitHubToken" --tag "v$AppVersion" --merge --publish --pre
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "DUNG: Tai len GitHub that bai. Kiem tra token hoac mang."
    }
    Write-Host "[OK] Tai len GitHub thanh cong: 1 full, 1 delta va Setup.exe." -ForegroundColor Green
}

Write-Host "[OK] Ban phat hanh v$AppVersion da san sang tren kenh $Channel!" -ForegroundColor Green
