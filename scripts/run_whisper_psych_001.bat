@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0\.."
echo === psych_001 subtitle generation ===
python scripts\whisper_subtitle_gen.py --audio youtube\psych_v2\.work\001\narration.mp3 --model base
echo.
echo === done ===
pause
