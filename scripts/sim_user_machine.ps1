# scripts/sim_user_machine.ps1
# DubStudio Simulation Environment for End-User Machine Testing
param(
    [string]$Action = "run",            # run, selftest, test_ingest, test_asr
    [string]$VideoSample = "samples\tiny.mp4"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path "$ScriptDir\..").Path
$BuiltExe = "$ProjectRoot\dist\DubStudio\DubStudio.exe"

if (-not (Test-Path $BuiltExe)) {
    Write-Error "Khong tim thay ban build tai: $BuiltExe. Vui long build app truoc!"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DubStudio - Mo phong moi truong May Nguoi Dung thuc te" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Tao thu muc LocalAppData gia lap co dau cach va Tieng Viet
$SimBaseDir = "$env:TEMP\DubStudio Thử Nghiệm Máy Khách"
if (Test-Path $SimBaseDir) {
    Remove-Item -Recurse -Force $SimBaseDir -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path "$SimBaseDir\DubStudio" -Force | Out-Null
New-Item -ItemType Directory -Path "$SimBaseDir\DubStudio\logs" -Force | Out-Null

Write-Host "[1/4] Thu muc AppData mo phong: $SimBaseDir" -ForegroundColor Yellow

# 2. Xoa sach cac bien moi truong dev (HF_HOME, TORCH_HOME, PYTHONPATH, .venv)
$CleanEnv = @{
    "LOCALAPPDATA" = $SimBaseDir
    "DUBSTUDIO_FORCE_PACKAGED" = "1"
    "SYSTEMROOT" = $env:SystemRoot
    "TEMP" = $env:TEMP
    "TMP" = $env:TMP
    "USERPROFILE" = $SimBaseDir
    "DUBSTUDIO_DISABLE_MUTEX" = "1"
    # PATH toi thieu (CHI CO SYSTEM32, TUYET DOI KHONG CO FFMPEG HAY PYTHON .VENV)
    "PATH" = "C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem"
}

# 3. Kiem tra xem may mo phong co ffmpeg tren PATH khong
Write-Host "[2/4] Kiem tra PATH toi thieu..." -ForegroundColor Yellow
$HasFFmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue)
if ($HasFFmpeg) {
    Write-Host "  -> Luu y: FFmpeg van ton tai trong shell hien tai, dang co lap bang ProcessStartInfo." -ForegroundColor DarkYellow
} else {
    Write-Host "  -> [OK] PATH da duoc co lap, khong co ffmpeg ngoai." -ForegroundColor Green
}

# 4. Thuc thi hanh dong duoc yeu cau
Write-Host "[3/4] Chay hanh dong '$Action' tu $BuiltExe..." -ForegroundColor Yellow
$Cwd = "$SimBaseDir"

$Psi = New-Object System.Diagnostics.ProcessStartInfo
$Psi.FileName = $BuiltExe
$Psi.WorkingDirectory = $Cwd
$Psi.UseShellExecute = $false
$Psi.RedirectStandardOutput = $true
$Psi.RedirectStandardError = $true

# Set clean isolated environment variables
$Psi.EnvironmentVariables.Clear()
foreach ($k in $CleanEnv.Keys) {
    $Psi.EnvironmentVariables[$k] = $CleanEnv[$k]
}

if ($Action -eq "selftest") {
    $Psi.Arguments = "selftest"
} elseif ($Action -eq "test_cli") {
    $Psi.Arguments = "--help"
} elseif ($Action -eq "test_stage_asr") {
    $Psi.Arguments = "-m dubstudio stage asr sim_job_001"
} else {
    # Default GUI launch
    $Psi.Arguments = ""
}

$Proc = [System.Diagnostics.Process]::Start($Psi)
$StdOut = $Proc.StandardOutput.ReadToEndAsync()
$StdErr = $Proc.StandardError.ReadToEndAsync()

if ($Action -ne "run") {
    $Proc.WaitForExit(15000)
    Write-Host "--- STDOUT ---" -ForegroundColor Cyan
    Write-Host $StdOut.Result
    Write-Host "--- STDERR ---" -ForegroundColor Red
    Write-Host $StdErr.Result
    Write-Host "Exit Code: $($Proc.ExitCode)" -ForegroundColor Yellow
} else {
    Write-Host "App da khoi chay voi PID: $($Proc.Id)." -ForegroundColor Green
    Write-Host "Doi 5 giay de xem log khoi dong..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

# 5. Kiem tra file log app.log duoc sinh ra
$LogFile = "$SimBaseDir\DubStudio\logs\app.log"
Write-Host "[4/4] Kiem tra file nhat ky ($LogFile)..." -ForegroundColor Yellow
if (Test-Path $LogFile) {
    Write-Host "====================== NOI DUNG APP.LOG ======================" -ForegroundColor DarkCyan
    Get-Content $LogFile -Tail 30
    Write-Host "==============================================================" -ForegroundColor DarkCyan
} else {
    Write-Host "[CANH BAO] Chua thay file log app.log duoc tao ra!" -ForegroundColor Red
}
