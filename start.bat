@echo off
chcp 65001 >nul
title "DubStudio - Trinh long tieng & Chinh sua Video AI"

echo =======================================================
echo          DUBSTUDIO - HE THONG LONG TIENG AI
echo =======================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay moi truong Python tai .venv!
    echo Vui long chay lenh cai dat:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Dang khoi dong ung dung DubStudio v2.0...
start "" ".venv\Scripts\python.exe" start_app_v2.py
exit /b 0
