@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0\.."

echo === history_007 sample: upload to YouTube (private) ===

REM Load .env at project root
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "%%a=%%b"
)

REM Map to NEW_YOUTUBE_* names that step5_upload.py reads
set "NEW_YOUTUBE_CLIENT_ID=%YOUTUBE_CLIENT_ID%"
set "NEW_YOUTUBE_CLIENT_SECRET=%YOUTUBE_CLIENT_SECRET%"
set "NEW_YOUTUBE_REFRESH_TOKEN=%YOUTUBE_REFRESH_TOKEN%"
set "NEW_YOUTUBE_SKIP_DURATION_GATE=1"

set "INPUT=C:\Users\user\Documents\10oku_samples\30min_01_history_akechi.mp4"
set "SCRIPT_JSON=youtube\history_v2\scripts\long_007.json"

if not exist "%INPUT%" (
    echo ERROR: input not found: %INPUT%
    pause
    exit /b 1
)

echo Uploading: %INPUT%
python new-youtube\scripts\step5_upload.py "%SCRIPT_JSON%" "%INPUT%"

echo.
echo === done ===
pause
