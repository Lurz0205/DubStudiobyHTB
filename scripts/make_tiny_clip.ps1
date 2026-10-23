param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$InputPath,

    [Parameter(Position=1)]
    [string]$OutputPath = "samples/tiny.mp4"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InputPath)) {
    Write-Error "Tệp đầu vào không tồn tại: $InputPath"
    exit 1
}

$OutputDir = Split-Path -Parent $OutputPath
if ($OutputDir -and -not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "Đang cắt 10 giây từ '$InputPath' thành '$OutputPath'..."
ffmpeg -y -ss 00:00:00 -i "$InputPath" -t 10 -c copy "$OutputPath"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Thành công: Đã tạo '$OutputPath'."
} else {
    Write-Error "Lỗi khi chạy ffmpeg."
    exit $LASTEXITCODE
}
