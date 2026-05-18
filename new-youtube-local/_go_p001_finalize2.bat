@echo off
cd /d C:\Users\user\Documents\10oku-project\new-youtube-local
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul
echo START > logs\p001_fin2_marker.txt

REM Kill any stuck python first
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

REM Step A: regenerate thumb (Gemini Imagen)
python scripts\step3b_thumbnail.py > logs\p001_fin2_thumb.log 2>&1
set RCT=%ERRORLEVEL%

REM Step B: compile via ffmpeg (NO moviepy)
python scripts\compile_ffmpeg.py > logs\p001_fin2_compile.log 2>&1
set RCC=%ERRORLEVEL%

REM Step C: upload (only if compile OK)
if %RCC% EQU 0 (
  python scripts\step5_upload.py > logs\p001_fin2_upload.log 2>&1
  set RCU=%ERRORLEVEL%
) else (
  set RCU=99
)

echo END thumb=%RCT% compile=%RCC% upload=%RCU% >> logs\p001_fin2_marker.txt
