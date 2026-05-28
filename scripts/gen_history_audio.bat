@echo off
chcp 65001 > nul
title gen_history_audio
cd /d "%~dp0.."
echo === Generate history audio (edge-tts) ===
python "%~dp0gen_audio_for_scripts.py" --kind history
echo.
echo === Done ===
pause
