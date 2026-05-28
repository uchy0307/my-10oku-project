@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0\.."

echo === psych_001 sample: burn subs + upload to YouTube (private) ===

REM Load env from new-youtube-local/.env
for /f "usebackq tokens=1,* delims==" %%a in ("new-youtube-local\.env") do (
    set "%%a=%%b"
)

set "INPUT=C:\Users\user\Documents\10oku_samples\30min_02_psych.mp4"
set "SRT=youtube\psych_v2\.work\001\narration.srt"
set "OUTPUT=C:\Users\user\Documents\10oku_samples\30min_02_psych_subs.mp4"
set "SCRIPT_JSON=youtube\psych_v2\scripts\psych_001.json"

if not exist "%INPUT%" (
    echo ERROR: input not found: %INPUT%
    pause
    exit /b 1
)
if not exist "%SRT%" (
    echo ERROR: SRT not found: %SRT%
    pause
    exit /b 1
)

echo.
echo Step 1: burn subtitles
python new-youtube\scripts\burn_subtitles.py "%INPUT%" "%SRT%" "%OUTPUT%"
if errorlevel 1 (
    echo burn_subtitles failed
    pause
    exit /b 1
)

echo.
echo Step 2: upload to YouTube (private, duration gate bypass)
set NEW_YOUTUBE_SKIP_DURATION_GATE=1
python new-youtube\scripts\step5_upload.py "%SCRIPT_JSON%" "%OUTPUT%"

echo.
echo === done ===
pause
