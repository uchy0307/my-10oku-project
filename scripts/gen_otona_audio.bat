@echo off
chcp 65001 > nul
title gen_otona_audio
cd /d "%~dp0.."
echo === Generate otona audio (edge-tts) ===
python "%~dp0gen_audio_for_scripts.py" --kind psych
echo.
echo === Done ===
pause
